# Exile Drone Director — Technical Architecture

Status: implementation architecture pending Enhanced DevKit API verification
Runtime model: Blueprint-only Conan Exiles Enhanced mod
Authority model: server-authoritative Flypath storage; client-local authoring and playback

## 1. Architectural goals

The architecture must provide:

- Safe local drone-camera control without unpossessing or moving the player pawn
- Responsive authoring and deterministic playback
- Server-persistent private drafts and immutable published revisions
- Server-enforced ownership, visibility, cloning, and moderation
- Continuously smooth spatial, temporal, rotational, lens, focus, and effect tracks
- Distinct cinematic, FPV, and hybrid flight behavior
- On-demand network transfer rather than replication of every editor interaction
- Schema migration and trajectory-engine versioning
- Reliable restoration after every normal and abnormal exit

The exact Conan parent classes, persistent-storage hooks, RPC attachment points,
and cooked camera modules must be confirmed in the Enhanced DevKit. Those probes
select adapters; they do not change the domain model described here.

## 2. System boundaries

```text
┌──────────────────────────── Owning client ─────────────────────────────┐
│ Input/UI → Client Director → Draft Model → Trajectory Compiler         │
│                                  ↓                                     │
│ Library Cache ← Server API     Compiled Flypath → Evaluator → Camera   │
│                                                   ↘ Preview/Debug       │
└───────────────────────────────── RPC ───────────────────────────────────┘
                                  ↕
┌──────────────────────────── Dedicated server ──────────────────────────┐
│ Request Router → Authorization → Flypath Repository → Persistence      │
│                         ↓                    ↓                          │
│                    Validation          Metadata Index                  │
└─────────────────────────────────────────────────────────────────────────┘
```

The server never receives per-frame drone transforms during normal editing or
playback. It receives bounded authoring documents on create/save/publish/clone
operations. Playback uses a downloaded immutable snapshot and evaluates locally.

## 3. Runtime components

Names are proposed asset names; base classes are finalized in the DevKit.

### 3.1 `BP_EDD_ModController`

Conan mod entry point. It registers/attaches the client and server components
using client/server copy rules supported by the Mod Controller. It contains no
substantial domain logic.

### 3.2 `BPC_EDD_ClientDirector`

One per owning client. Responsibilities:

- Own the local state machine
- Cache and restore view target, input mode, cursor, HUD, and movement-lock state
- Spawn/destroy local camera and preview actors
- Route input between game, library, editor, and playback
- Hold the active Flypath draft and undo stack
- Request lists/revisions and submit server commands
- Compile and cache trajectories
- Drive editor preview and published playback
- Enforce emergency exit on death, teleport, region transition, disconnect, or
  component end-play

### 3.3 `BPC_EDD_ServerService`

Server-authoritative request handler attached to a stable server-owned class. It
resolves authenticated request identity, validates commands, enforces policy and
ownership, and delegates persistence to the repository. RPC functions must never
accept an owner ID supplied by the client as authoritative.

### 3.4 `BP_EDD_DroneCamera`

Local non-replicated view-target actor containing:

- Scene root
- Optional sweep/collision primitive
- Camera or Cine Camera component, chosen after cooked-runtime verification
- Post-process configuration
- Optional hidden airframe and gimbal transform hierarchy
- Debug visualization disabled for clean playback

The player controller remains attached to the player pawn. The director switches
the local view target to this actor and restores the cached target on exit.

### 3.5 `BP_EDD_PathPreview`

Local non-replicated visualization actor. It renders waypoint markers, segment
curves, body/gimbal axes, focus targets, focal plane, spatial bounds, collision
samples, and warnings. It never becomes the data source.

### 3.6 `BP_EDD_FlypathRepository`

Logical server repository. Its physical form depends on the persistence API
available in the DevKit: component, singleton actor, service object, or supported
mod-data wrapper. It owns the metadata index and serialized Flypath records.

### 3.7 UI widgets

- `WBP_EDD_Library`
- `WBP_EDD_Editor`
- `WBP_EDD_Timeline`
- `WBP_EDD_CurveEditor`
- `WBP_EDD_Inspector`
- `WBP_EDD_PlaybackHUD`
- `WBP_EDD_Settings`
- `WBP_EDD_ConflictDialog`

Complex widgets communicate through the client director and editor view-model
structures rather than mutating Blueprint actors directly.

## 4. Client state machine

```text
Inactive
  ├─ OpenLibrary → Library
  ├─ Create/Edit → EnteringEditor → Flying/Editing
  └─ Play → PreparingPlayback → Playing/Paused

Flying ↔ Editing ↔ Previewing
Playing ↔ Paused

Any active state ── exit/error/death/teleport/disconnect ─→ Restoring → Inactive
```

### 4.1 State invariants

- Only one active camera actor and one active Flypath session per client.
- `OriginalViewTarget` is captured before any view switch and never overwritten
  while active.
- Enter/exit operations are idempotent.
- `Restoring` can be called multiple times safely.
- Emergency Exit bypasses focused widgets and text-entry contexts.
- No active state survives owning-player destruction or region transition.

## 5. Server data model

Blueprint structs should mirror these logical records. Field types may be adapted
to what Conan persistence supports.

### 5.1 Flypath record

| Field | Purpose |
| --- | --- |
| `FlypathId` | Server-generated GUID/string identity |
| `OwnerAccountId` | Durable authenticated owner identity |
| `OwnerDisplayName` | Non-authoritative presentation snapshot |
| `Title` / `Description` | Library metadata |
| `Visibility` | Private or Public |
| `RegionId` | Required map/region scope |
| `CreatedUtc` / `UpdatedUtc` | Audit and sorting |
| `DraftRevisionNumber` | Monotonic editable revision |
| `PublishedRevisionNumber` | Optional immutable public revision |
| `SourceAttribution` | Optional clone source ID/revision/title/creator |
| `SchemaVersion` | Serialized document version |
| `TrajectoryEngineVersion` | Evaluation behavior version |
| `Draft` | Owner-editable revision document |
| `Published` | Immutable published revision document |

### 5.2 Revision document

| Field | Purpose |
| --- | --- |
| `RevisionNumber` | Optimistic concurrency token |
| `DurationSeconds` | Cached validated duration |
| `Bounds` | Cached route bounding box/sphere |
| `GlobalSettings` | Flight, lens, effect, and comfort metadata |
| `Waypoints` | Ordered authored waypoint array |
| `Segments` | Ordered transition array, count = waypoints - 1 |
| `AdditionalTracks` | Sparse scalar/quaternion tracks not owned by a waypoint |
| `ContentHash` | Integrity/cache key |

Published revisions are copied snapshots. An edit never mutates the published
payload in place.

### 5.3 Waypoint

| Field | Purpose |
| --- | --- |
| `WaypointId` | Stable ID for editing/undo, unique within Flypath |
| `Position` | World-space camera/drone point |
| `BodyRotation` | Authored airframe orientation or hint |
| `GimbalRotation` | Authored camera orientation |
| `CornerMode` | Stop, Glide, FlyBy, Tight, SnapTurn, Cut |
| `HoldSeconds` | Time held after arrival |
| `PositionLockFlags` | Preserve selected components during smoothing |
| `LensState` | Focal length, filmback reference, aperture |
| `FocusState` | Mode, fixed point/distance, influence |
| `EffectState` | Sparse keyed post-process values |
| `Annotations` | Optional creator note/label |

### 5.4 Segment

| Field | Purpose |
| --- | --- |
| `SegmentId` | Stable local identity |
| `DurationMode` | Explicit duration or desired speed |
| `DurationOrSpeed` | Authored timing value |
| `SpatialCurveType` | Linear, AutoCinematic, ManualHermite, ControlSpline, Orbit |
| `TimeProfile` | Preset/custom monotonic curve |
| `FlightProfileOverride` | Optional cinematic/FPV/hybrid configuration |
| `TangentData` | Manual or generated incoming/outgoing derivative hints |
| `ContinuitySettings` | Positional/rotational/scalar continuity targets |
| `CollisionPolicy` | Ignore, Warn, BlockPreview |
| `LookAtSettings` | Fixed/track/blend behavior |

### 5.5 Curve/channel representation

Scalar tracks use key time, value, interpolation mode, and optional in/out
tangents. Values are stored in domain units: millimeters for focal length,
centimeters for focus distance, f-stops or stop offsets where appropriate, EV for
exposure, and normalized weights for blendable effects.

Quaternion rotations are stored as rotators only at serialization boundaries if
Blueprint limitations require it; compilation converts them to normalized
quaternions and enforces shortest-arc/sign consistency.

## 6. Ownership, visibility, and identity

The server derives `RequesterAccountId` from the authenticated player/controller
associated with an RPC. It compares this identity against repository ownership.
Display names are never used for authorization.

Authorization rules:

- Create: requester allowed by server policy.
- Fetch private: requester owns record or admin policy explicitly permits.
- Save draft: requester owns record and expected draft revision matches.
- Publish/unpublish/delete: requester owns record, or admin moderation path.
- Clone: source revision is published and requester may create.
- List public: permitted server member.

Each command returns a typed result such as Success, NotFound, Forbidden,
RevisionConflict, ValidationFailed, LimitExceeded, RegionForbidden, or
PersistenceUnavailable.

## 7. Network API

The concrete RPC transport depends on the verified Conan component attachment,
but the logical operations are stable.

### 7.1 Queries

- `ListMyFlypaths(page, filters)`
- `ListPublicFlypaths(page, filters)`
- `GetFlypathMetadata(id)`
- `GetDraft(id, knownRevision)`
- `GetPublishedRevision(id, revisionOrLatest, knownHash)`
- `GetServerPolicy()`

Metadata is paged and lightweight. Full payloads are fetched on edit/play/clone
and cached by Flypath ID, revision, and content hash.

### 7.2 Commands

- `CreateFlypath(initialMetadata, initialDraft)`
- `SaveDraft(id, expectedRevision, draftDeltaOrDocument)`
- `PublishDraft(id, expectedDraftRevision)`
- `Unpublish(id, expectedDraftRevision)`
- `ClonePublished(id, publishedRevision, newTitle)`
- `Rename(id, expectedRevision, title)`
- `Delete(id, expectedRevision)`
- `AdminUnpublish/Delete(id, reason)`

The first implementation may send complete bounded documents for reliability.
Delta commands are an optimization only after payload sizes are measured.

### 7.3 Concurrency

Save uses optimistic concurrency. A request contains the revision the editor
started from. A mismatch returns the current server revision without overwriting
either side. Because only the owner can edit, conflicts should be uncommon and
usually indicate multiple sessions. The conflict UI offers reload server copy,
save local as a new private Flypath, or deliberate overwrite if policy allows.

### 7.4 Active playback

Playback never subscribes to mutable server state. The client downloads one
published revision and retains it until exit. Republish or unpublish does not
change the active local evaluator.

## 8. Persistence architecture

### 8.1 Required semantics

- Dedicated-server persistence across restart
- Atomic replacement or recoverable write strategy
- Bounded list/query without loading every full revision to every client
- Versioned serialization and migration
- Protection against partial/corrupt records
- Server-owned data path, never client-local authority

### 8.2 Adapter selection spike

In priority order, inspect the Enhanced DevKit for:

1. Supported Conan mod-data/database service
2. Persisted mod actor/component participating in the server save
3. Blueprint SaveGame support executing on dedicated server
4. A documented server configuration/data-table persistence extension

Implement `Repository` functions behind one Blueprint-facing interface so the
trajectory/editor code is independent of the chosen adapter. Do not commit to a
client SaveGame for shared Flypaths.

### 8.3 Atomicity and recovery

Where the storage adapter lacks transactions, use copy-on-write records:

1. Validate complete candidate revision.
2. Write candidate with new revision/content hash.
3. Mark candidate committed.
4. Update metadata pointer.
5. Retain or later garbage-collect the previous committed revision.

On load, ignore uncommitted candidates and fall back to the latest valid hash.
The exact mechanism is adjusted to storage primitives available in Blueprint.

### 8.4 Limits

Server policy sets conservative limits for paths per owner/server, waypoint and
track-key count, duration, bounds, string lengths, and serialized bytes. Validate
NaN/infinite numbers, impossible transforms, negative time, non-monotonic time
keys, and invalid enum/schema values before persistence or publication.

## 9. Trajectory compilation pipeline

Authoring data is editable and sparse. Playback data is precomputed and fast.

```text
Revision document
  → structural validation
  → semantic/default resolution
  → spatial curve solve
  → arc-length sampling table
  → time-profile solve
  → airframe/gimbal solve
  → scalar/quaternion track compile
  → bounds/collision/continuity analysis
  → compiled Flypath + diagnostics
```

Compilation occurs locally after edits and before playback. Publication repeats
server-safe structural validation; a client may send cached diagnostics but the
server does not trust them.

### 9.1 Determinism

Compiled results depend only on revision data, schema version, trajectory-engine
version, and a stored procedural seed. Avoid frame-rate-dependent integration for
published playback. If an FPV solver uses numeric integration, compile it with a
fixed timestep into a deterministic sample/coefficients table, then interpolate
that table at runtime.

### 9.2 Scrubbing

The evaluator must produce the same result when jumped directly to time `t` as it
does during forward playback. Stateless closed-form curves satisfy this. Stateful
features such as autofocus springs or live actor tracking require either analytic
evaluation, deterministic prebaking, or an explicitly degraded scrub preview.

## 10. Spatial trajectory engine

### 10.1 Linear

Position is a straight interpolation between exact endpoints. Time may still use
a smooth profile. Linear is valid for cable-camera shots and is never removed as
“inferior.”

### 10.2 Manual cubic Hermite/Bezier

Endpoints and incoming/outgoing tangent handles define the segment. Adjacent
segments share tangent constraints for C1 continuity when requested. C2
continuity is enforced only when handle relations make it possible; otherwise the
editor shows a continuity warning.

### 10.3 Auto Cinematic

Use piecewise quintic minimum-jerk or seventh-order minimum-snap polynomials.

- Quintic segments satisfy position, velocity, and acceleration boundary values
  and can maintain C2 continuity.
- Seventh-order segments can also satisfy jerk boundary values and maintain C3
  continuity, producing stronger drone-like smoothness.

Boundary derivatives are solved across neighboring waypoints, respecting Stop,
Glide, Fly-by, Tight, locked tangent, and duration constraints. The first
Blueprint implementation may begin with quintic C2 and add a global minimum-snap
solver after correctness/performance measurements.

### 10.4 Smooth control curve

A cubic B-spline-style curve offers C2 smoothness but normally treats authored
points as controls rather than guaranteed intersections. The UI labels this
behavior clearly and renders the control polygon.

### 10.5 Orbit/arc

Analytic position around a fixed center/axis/radius produces predictable reveals
and subject orbits. Entry/exit blends are compiled into neighboring trajectories
rather than hard-switching derivatives.

### 10.6 Overshoot and collision

Automatic tangents are bounded relative to neighboring chord lengths and use
centripetal weighting to reduce loops. The compiler samples curves for terrain,
building, and bound violations. Default behavior reports diagnostics; it does not
silently deform a published composition. The creator may choose linear fallback,
manual handles, or an explicit avoidance tool later.

## 11. Time and speed engine

### 11.1 Arc-length parameterization

Naive spline parameter `u` does not correspond to traveled distance. Compilation
adaptively samples each spatial segment into a cumulative arc-length lookup. At
runtime the evaluator inverts distance to `u` through binary search and local
interpolation.

### 11.2 Time profile

A monotonic normalized curve maps segment time to normalized distance. Its
derivatives describe speed and acceleration. Supported presets include Linear,
Smoothstep, quintic smootherstep, jerk-limited cinematic S-curve, accelerate
through, brake into, and creator-authored monotonic curves.

Custom time curves are clamped/validated for monotonicity so the drone does not
reverse accidentally. Explicit reverse motion is represented as path direction,
not a malformed time curve.

### 11.3 Duration and physical constraints

Creators author either segment duration or target speed. Flight profiles define
max speed, acceleration, braking, jerk, angular rate, and turn radius. The
compiler reports impossible constraints and can calculate the minimum valid
duration. It never silently adds a discontinuity to honor an impossible time.

### 11.4 Holds and cuts

Holds are explicit timeline intervals with independent camera/lens animation.
Cuts create separate shots and reset continuity intentionally. A Flypath may
therefore contain multiple shots while remaining one published experience.

## 12. Rotation, airframe, and gimbal

### 12.1 Quaternion continuity

Serialized rotations are normalized and signs aligned so adjacent quaternions
follow the shortest intended arc. Multi-key authored rotation uses quaternion
spline interpolation such as SQUAD rather than component-wise Euler lerp or
isolated pairwise Slerp. This preserves smoother angular velocity across keys.

### 12.2 Cinematic body solution

Body forward orientation follows a configurable blend of path tangent,
look-ahead tangent, and authored yaw. Banking is derived from curvature/speed and
clamped by profile. Horizon stabilization affects the gimbal, not necessarily the
airframe.

### 12.3 FPV body solution

The FPV compiler treats waypoints as gates and generates deterministic desired
velocity/acceleration. Approximate bank can derive from path curvature and speed;
pitch derives from forward/vertical acceleration and camera uptilt. Profile
limits constrain turn rate, roll rate, acceleration, and correction strength.

This is a cinematographic flight model, not a claim to reproduce every rotor and
flight-controller loop. Its requirements are credible inertia, expressive motion,
repeatability, and tunable profiles.

### 12.4 Gimbal solution

Gimbal modes are authored orientation, fixed look-at, target tracking, velocity
look-ahead, horizon stabilization, and weighted blends. Gimbal angular rates and
acceleration are limited/smoothed. A hybrid stabilization weight continuously
blends body-locked FPV with stabilized cinematic framing.

## 13. Scalar camera and effect channels

All scalar channels use the common compiled track interface:

`Evaluate(Channel, Time) → Value`

Each key supports interpolation preset and optional tangents. Continuous tracks
default to at least value/velocity continuity; cinematic presets target smooth
acceleration where practical.

Domain-aware interpolation includes:

- Focal length in millimeters rather than arbitrary FOV blending
- Focus in linear distance or reciprocal-distance/diopter space
- Exposure in EV stops
- Aperture with an explicit optical/creative interpolation choice
- Blend weights clamped to `[0, 1]`
- Angles through quaternion/vector methods rather than scalar wraparound

Boolean-looking effects use continuous weights plus thresholded activation only
when the engine property requires a boolean.

## 14. Camera evaluation order

At playback time `t`:

1. Resolve shot, hold, and travel segment.
2. Evaluate normalized time profile and world-space position.
3. Evaluate/derive airframe rotation.
4. Evaluate gimbal orientation and look-at blend.
5. Evaluate focal length, aperture, focus, exposure, and effect channels.
6. Apply deterministic procedural offsets/noise.
7. Apply viewer comfort overrides.
8. Set camera transform and post-process state.

Evaluation uses precomputed tables/coefficients and avoids solving global curves
per frame.

## 15. Procedural motion

Procedural wind, vibration, and stabilization error use seeded coherent signals
with defined frequency bands. Each source is evaluated as a deterministic
function of absolute Flypath time, allowing scrubbing and identical replays.
Amplitude and blend weight are ordinary smooth tracks. Per-frame random values
are prohibited.

## 16. Editing model and undo

The client holds an editable draft model separate from the server DTO and
compiled trajectory. An edit command:

1. Captures minimal before/after data for undo.
2. Mutates the draft model.
3. Marks dirty channels/segments.
4. Incrementally recompiles affected ranges where possible.
5. Updates diagnostics and preview.
6. Schedules a debounced server save.

Undo/redo operates on stable waypoint/segment/key IDs, not array indices alone.
Bulk operations form one transaction.

## 17. Validation and diagnostics

Validation levels:

- **Error:** cannot save/publish/play safely.
- **Warning:** valid but likely undesirable, such as collision or comfort risk.
- **Info:** optimization or quality suggestion.

Checks include structural counts, finite numeric values, ordering, duration,
monotonic time profiles, curve solvability, continuity, region/bounds, collision
sampling, focal-range sanity, effect comfort thresholds, and schema compatibility.

Diagnostics identify exact waypoint, segment, track, and time range and provide a
focused Fix/Select action where possible.

## 18. World streaming and playback preparation

The route stores region and bounds. Before playback the client verifies region
compatibility and tests whether the camera viewpoint acts as a valid streaming
source in Conan Enhanced. If prewarming is possible, preparation samples future
camera positions before the countdown. Otherwise playback begins only after a
minimum streaming readiness check and exposes a conservative speed/bounds limit.

Cross-region playback is disabled until explicitly implemented and tested. The
player pawn is never silently teleported to make streaming work.

## 19. Performance budgets

- Runtime camera evaluation: allocation-free Blueprint path where possible
- Global trajectory solve: editor/publish time, never every frame
- Arc-length and FPV samples: adaptive but capped by server/client policy
- Library: metadata paging, full payload on demand
- Preview visualization: pooled components/meshes, density reduced with distance
- Network: bounded documents, hashes, no per-frame transform RPCs
- Server: no Tick required for stored Flypaths

Measure Blueprint time and memory in PIE and cooked client before increasing
default waypoint/key limits.

## 20. Failure recovery

The client director enters `Restoring` on:

- Manual/emergency exit
- Player death or pawn replacement
- Teleport or region transition
- Server disconnect
- Camera actor destruction
- UI closure while active
- Compile/evaluation exception-equivalent error
- Mod component end-play

Restoration attempts, in order: stop evaluator, remove local overlays, restore
HUD/input/cursor, restore a valid original/player view target, destroy local
camera/preview actors, clear active state. Each step tolerates already-destroyed
objects.

Unsaved local edits remain in a recovery buffer until acknowledged or a new
session begins, subject to what local SaveGame support allows.

## 21. Schema and trajectory migrations

`SchemaVersion` describes serialized fields. `TrajectoryEngineVersion` describes
how identical authoring data is interpreted. On load:

1. Reject unsupported future major versions with a clear message.
2. Migrate older schemas through sequential pure transforms.
3. Preserve the original stored record until migrated data validates.
4. Mark published revisions as needing owner review if a trajectory-engine change
   would materially alter playback.

Published snapshots should retain their trajectory-engine version. Compatibility
code may evaluate an older version, or the owner may explicitly upgrade and
republish.

## 22. Security and abuse resistance

- Validate identity on the server for every mutation.
- Bound every array, string, duration, and spatial value.
- Reject NaN/infinity and invalid transforms.
- Rate-limit save/list/fetch/clone commands.
- Fetch private payloads only after authorization.
- Avoid replicating the entire repository to clients.
- Treat public coordinates as sensitive on PvP servers.
- Make remote range, publishing, and playback policy configurable.
- Log administrative moderation and validation failures without logging private
  payload contents unnecessarily.

## 23. Recording architecture

Clean Playback emits local start/countdown/finish events, hides configured UI,
and supplies deterministic evaluation for external recording. It must not attempt
to control OBS or another process from a pure Workshop mod.

After the core is stable, probe `MoviePipelineQueueEngineSubsystem` and available
runtime output settings in PIE and cooked Conan. Direct render output is added
only when the necessary plugin modules are already shipped, output paths are safe,
and cancellation/restoration work reliably.

## 24. DevKit decisions that must be verified

1. Correct base blueprint for attaching client and server components.
2. Available input mapping/injection system in cooked mods.
3. Camera versus Cine Camera and post-process properties surviving cook.
4. Dedicated-server persistent mod-data mechanism.
5. RPC size/reliability constraints and callable ownership chain.
6. Durable account identity exposed to Blueprint.
7. Region transition and streaming-source behavior for remote view targets.
8. UMG mouse capture/focus behavior alongside game input.
9. Runtime screenshot/thumbnail feasibility.
10. Movie Render Pipeline module availability.

Each unknown has a bounded spike in the implementation plan. Findings update the
adapter layer and asset parent classes, not the domain semantics.
