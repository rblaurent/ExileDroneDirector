# Exile Drone Director — Technical Architecture

Status: implementation architecture pending Enhanced DevKit API verification
Runtime model: Blueprint-only Conan Exiles Enhanced mod
Authority model: server-authoritative Flypath storage; client-local authoring and playback

## 1. Architectural goals

The architecture must provide:

- Safe local drone-camera control without moving, destroying, or unpossessing the
  player pawn
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
- Cache and restore controlled pawn, view target, input mode, cursor, HUD, and
  movement-lock state
- Spawn/destroy local camera and preview actors
- Route input between game, library, editor, and playback
- Hold the active Flypath draft and undo stack
- Request lists/revisions and submit server commands
- Compile and cache trajectories
- Drive editor preview and published playback
- Own transient operator-override state for Free Look and Carrier Freecam
- Enforce emergency exit on death, teleport, region transition, disconnect, or
  component end-play

#### Current waypoint-authoring bridge

The `0.14.0-linear-playback` implementation deliberately precedes the final
document structs. `BPC_EDD_ClientDirector` currently owns six client-local,
transient lockstep arrays:

- stable integer ID;
- world transform;
- focal length;
- aperture;
- manual focus distance;
- hold seconds.

`SelectedWaypointIndex` is `-1` when empty. Capture appends all channels,
selects the index returned by the ID append, then advances the monotonic ID.
Replace validates camera plus selected ID index and changes only transform and
lens channels; ID and hold remain stable. Delete removes the same index from all
six channels and preserves that index when a successor exists or clamps to the
last survivor/`-1`.

`ST_EDD_Waypoint` now mirrors this lossless migration subset with `WaypointId`
(Integer), `CameraTransform` (Transform), and Float `FocalLength`, `Aperture`,
`ManualFocusDistance`, and `HoldSeconds` fields. The client owns an empty typed
`DraftWaypointsV1` array and compiles cleanly against that struct. The six legacy
arrays remain runtime-authoritative until `SyncDraftWaypointsV1` is implemented
and mutation/runtime contracts prove exact parity; the typed seam is not yet a
second independently editable source of truth.

`tools/document/waypoint_bridge.py` fixes that sync function's executable
contract: validate all six channel lengths, IDs, and camera scalars before
constructing anything; then rebuild an ordered value snapshot, including the
empty case. Invalid input must leave the previously valid typed array untouched.

Linear playback evaluates this bridge from absolute game time rather than
integrating frame delta. It uses quaternion transform interpolation and keeps
ownership of the exact final authored transform until an explicit stop. That
final-frame hold is intentional: releasing ownership at completion lets the
inactive horizon-lock/manual-flight path immediately alter the authored roll.

When playback is inactive, the active-mode client dispatch maps K/R/Delete to
those three operations and then formats one shared local status message from
`Length(DraftWaypointIds)` and `SelectedWaypointIndex`. P enters a separate
start/stop arbitration path. While `PlaybackActive` is true, the tick calls only
the absolute-time playback evaluator; manual flight and authoring do not run.
Normal and emergency exits clear playback before view restoration. This bridge
and its feedback are intentionally transient; authoritative server persistence,
publication, and collaboration begin in the later repository slice.

This bridge is not a persistence or networking model. It exists to prove
atomic edit semantics and camera capture before `ST_EDD_Waypoint`,
`ST_EDD_FlypathDocument`, undo commands, serialization, and server DTOs are
authored. No other client may read these arrays, and no UI or playback system
should bind directly to them once the document model is promoted.

The current linear evaluator assigns one configurable duration to every segment,
derives segment index and local alpha from absolute game time, interpolates
transforms with quaternion rotation, and writes the final authored transform
exactly before deactivating. It is the validation kernel for the later compiled
trajectory model, not the final cinematic timing or curve representation.

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

The verified production backend never possesses this actor. Native
`SpectatorPawnMovement` was rejected because unpossessed movement input is not
consumed and client-side possession is authority-sensitive. Instead, the drone
constructs a signed six-axis local vector, scales it by configured speed and
world delta time, and applies one local transform offset. The director switches
only the owning client's view target and restores the exact cached target on
exit. BeginPlay explicitly disables actor and movement replication; this runtime
override is required because `SpectatorPawn` inheritance otherwise re-enabled
replication on spawned instances despite the intended class defaults.

Free-flight speed uses two values rather than directly multiplying input by a
mode flag. `CruiseMoveSpeed` is the persistent mouse-wheel-trimmed target base;
`CurrentMoveSpeed` is the smoothed runtime value consumed by translation. Wheel
steps multiply/divide cruise speed by 1.25 and clamp it to 30-6000 units/second.
Ctrl targets 0.25x cruise speed, Shift targets 3x, and precision wins if both are
held. `FInterpTo` with a default response of 6 interpolates current toward target
before translation, keeping trim, precision, and boost changes continuous.

Free-flight roll and leveling remain a separate orientation layer. Z/C select a
signed manual-roll target, `CurrentRollSpeed` eases toward that target, and its
delta-time-scaled value is applied locally. H toggles `HorizonLockEnabled`.
When enabled and no raw roll command is present, only world roll interpolates
toward zero; current pitch and yaw are preserved. Manual input temporarily wins,
and disabling the lock preserves bank. This actor-level free-flight behavior is
later superseded by the separate airframe/gimbal evaluator during Flypath
playback.

### 3.5 `BP_EDD_PathPreview`

Local non-replicated visualization actor. It renders waypoint markers, segment
curves, body/gimbal axes, focus targets, focal plane, spatial bounds, collision
samples, and warnings. It never becomes the data source.

The first implemented rendering seam projects `PreviewDocumentV1` into pooled
Hierarchical Instanced Static Mesh components: a sphere pool for ordered
waypoints and a thin cube pool for linear adjacencies. Components have no
collision or shadows and remain independent from the document model. Later
curve modes may replace segment transforms without changing ownership or data
flow.

`ClearPreviewV1` owns the stale-instance invariant. It always clears the
waypoint pool first and the segment pool second, is safe on already-empty pools,
and does not mutate `PreviewDocumentV1`. `RebuildPreviewV1` must begin through
that function before projecting any document state; callers never clear or add
instances directly. Its first compiled slice exits immediately when
`PreviewEnabled` is false. Otherwise it iterates the typed document's ordered
`ST_EDD_Waypoint` array and adds one world-space sphere instance per authored
`CameraTransform`, preserving location and rotation while replacing scale with
uniform `MarkerScaleV1`. After each marker it checks whether `index + 1` is in
bounds. In-bounds adjacent transforms produce a cube only when their world-space
distance is greater than `0.001`: transform interpolation at alpha `0.5` supplies
the midpoint, `FindLookAtRotation` aligns local +X toward the next waypoint, and
the scale is `(distance / SourceCubeExtentV1, LineThicknessV1,
LineThicknessV1)`. The last waypoint and degenerate adjacencies deliberately add
no `SegmentLinesV1` instance.

`BPC_EDD_ClientDirector` is the sole runtime owner of this visualization through
the nullable `PathPreviewActorV1` reference. `RefreshPathPreviewV1` is the only
creation/update boundary: it reuses the exact valid actor when possible,
otherwise spawns one collision-independently at an explicit identity transform,
then copies the complete `DraftDocumentV1` value and invokes `RebuildPreviewV1`
on either path. `DestroyPathPreviewV1` is the symmetric boundary: it clears
pooled instances, destroys a valid actor, and clears both valid and stale
references. Enter and every successful authoring mutation call refresh; normal
exit calls destroy before camera restoration. The actor and reference are
client-local and never replicated, so one client's authoring preview cannot
become server or another client's state.

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
| `ContentHash` | Reserved empty field in runtime `structural-v1`; migration seam for a future native digest |

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

### 5.6 Executable version-1 document contract

`tools/document/flypath_document.py` and
`tools/document/flypath_repository.py` are the engine-independent oracles for
the first Blueprint repository and persistence implementation. Version 1 fixes
these rules:

- serialized revision documents use canonical UTF-8 JSON with sorted keys,
  compact separators, finite numbers only, exact field/schema validation, and
  decode/re-encode equality so duplicate fields or noncanonical text fail;
  runtime integrity mode `structural-v1` requires the reserved `contentHash`
  field to remain empty instead of claiming an unavailable digest;
- waypoint and segment IDs are positive, stable, unique within a document, and
  segments join adjacent waypoints in authored order;
- positions and lens/focus/hold values are finite, rotations are normalized
  quaternions, durations are positive, and the cached total equals segment plus
  waypoint-hold duration;
- draft saves use optimistic revision numbers; a stale expected revision fails
  rather than overwriting newer work;
- publication captures the complete sealed draft and later draft edits never
  mutate that published snapshot;
- new Flypaths and clones are private, only published snapshots are cloneable,
  clones preserve document-scoped waypoint IDs and source attribution, and have
  no live link to their source.
- complete Flypath records use a versioned canonical envelope declaring
  `integrityMode: structural-v1`, require reserved hash fields to remain empty,
  and validate exact fields, canonical UTC timestamps, revision ordering,
  optional-payload flags, and every nested document invariant;
- repository requests return stable typed result codes and never mutate the
  authoritative in-memory record when persistence fails;
- metadata queries are bounded, paged, sorted, and do not carry full revision
  payloads;
- storage uses staged copy-on-write generations, explicit commit, activation,
  committed tombstones, and newest-valid recovery. Incomplete candidates are
  ignored, a committed candidate survives a missing pointer update, corrupt
  latest payloads fall back to the previous valid generation, and a committed
  tombstone prevents deleted data from resurrecting.

The Python oracle is not shipped runtime code. `blueprint_v1_schema.json` fixes
the Blueprint-facing record, metadata, result, policy, attribution, and persisted
generation seams; nullable published/attribution values use explicit `Has...`
flags. Blueprint structs, Blueprint validation, server DTOs, and persistence
adapters must produce the same fields and pass the same fixtures before replacing
the transient six-array bridge.

The server Blueprint's codec boundary uses dedicated scratch state rather than
aliasing request or result fields. `ScratchDocumentV1` plus encoded document and
record strings are the document codec seam. Record identity, ownership,
metadata, draft/published documents, and source attribution each have explicit
`ScratchRecord...V1` fields; `HasPublishedRevision` and
`HasSourceAttribution` remain typed booleans in Blueprint while the canonical
JSON encoder writes actual `null` for absent optional payloads. This makes each
codec function independently callable and testable before CRUD graphs compose
it, and prevents a nested encode/decode call from corrupting a staged request.

The Enhanced editor-compiled quaternion seam is preserved in reviewed fixtures.
Encoding uses an unsplit `Conv_RotatorToQuaternion` followed by the native
`BreakQuat` form because Enhanced asserts while reconstructing that conversion's
split return pin in a populated graph. Decoding uses `Quat_Rotator` with its
const-reference Quat input split to X/Y/Z/W floats. The decoder copy-back is in
`repository-decoder-native-node-forms.eddgraph`; its contract proves every
regenerated parent/sub-pin GUID is reciprocal. Codec graph generation must
reuse these reviewed forms instead of guessing Quat pin serialization.

Document decoding is fail-closed and staged. Every decoder preserves its source,
projects into typed scratch state, calls the corresponding accepted encoder, and
sets `ScratchValidV1` only when the re-encoded canonical JSON is byte-for-byte
identical to the source. `DecodeDocumentV1` resets validity before work and does
not touch root fields unless `DecodeJson` succeeds. `DecodeWaypointV1` likewise
resets validity and requires position and quaternion arrays to have exactly three
and four PlayFab float elements before any array-item node can evaluate. Missing,
extra, reordered, mistyped, or noncanonical data is therefore rejected without
committing a partial result or issuing an out-of-bounds read.

Record-envelope decoding applies the same invariant one level higher. It first
preserves the complete source envelope, requires `DecodeJson` success, then
requires the `record` field's runtime JSON type string to be exactly `Object`
before any record getter or optional-payload helper can run. Published revision
and source-attribution helpers distinguish explicit null from an object, the root
decoder stages every typed field and draft/published document, and
`EncodeRecordV1` regenerates the canonical envelope. Only byte-for-byte equality
between that regenerated envelope and the preserved source can set
`ScratchValidV1=true`; every failure path terminates with validity already false.

Private draft loading is an owner-only read boundary. `LoadDraftV1` resets every
result channel, resolves `RequestFlypathIdV1` through the derived identity index,
and compares the indexed owner account ID with the authenticated requester
before exposing or decoding the record envelope. Missing, forbidden, corrupt,
and invalid records return stable typed failures with no envelope, revision, or
typed document. Success returns the canonical envelope, its current draft
revision, and `ResultDraftDocumentV1`. The shared result reset clears the typed
document as well as scalar fields, preventing a denial after a successful call
from leaking stale draft data.

Private creation is a commit-gated write boundary. `CreatePrivateFlypathV1`
accepts a server-staged deterministic `RequestFlypathIdV1`, rejects an existing
identity before any work, validates required scalar fields, title/region/owner
limits, and the complete staged record, then fixes visibility to `private` and
both record/document revision semantics to revision 1. It encodes the record,
enforces the configured serialized-size bound, calls
`PreparePersistenceCandidateV1`, appends the envelope to candidate records, and
delegates physical A/B writes to `PersistRepositoryV1`. Active record envelopes
and the derived ID/owner/visibility/updated-time indexes are promoted only after
`ScratchPersistenceCommitSavedV1` is true. Failures therefore return a typed
result without advancing generation or exposing a partial record. Successful
creation returns the committed index, canonical envelope, revision 1, and typed
draft; the existing owner-only load boundary remains the only private read path.

The current Enhanced graph uses `KismetStringLibrary.Len` for the serialized
limit. This is an executable UTF-16 code-unit bound, not a claim of exact UTF-8
byte counting; the conservative default and strict title limits keep version-1
records far below the storage ceiling. Exact byte accounting remains an explicit
future parity improvement if Enhanced exposes a safe Blueprint seam.

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
and cached by Flypath ID plus immutable revision. A future supported digest may
augment that key without changing the version-1 Blueprint structs.

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

The first accepted adapter is a **server-invoked Blueprint SaveGame**. The
`SG_EDD_RepositoryStorage` asset carries a version, generation, committed flag,
a reserved empty snapshot-hash field, opaque canonical record envelopes, and
explicit tombstones. Two
alternating slots (`EDD_Repository_A` and `EDD_Repository_B`) prevent an in-place
overwrite from destroying the last accepted snapshot. A same-process writer and
fresh-process reader proved exact scalar, array, canonical text, and Unicode
round trips in Enhanced 5.6. This does not authorize client-local repository
authority: only the server service may call the adapter. Conan's native
`PersistenceComponent` remains a possible later adapter after its undocumented
world-actor/database lifecycle is proven on a dedicated server.

The compiled repository boundary is `BP_EDD_FlypathRepository`, a non-replicated
server actor. Because Enhanced Python cannot author User Defined Struct members
or Blueprint function parameters, its first automatable contract uses explicit
versioned request/result staging members and no-parameter named functions. The
later server RPC adapter derives identity, fills one request transaction, invokes
one repository function, and copies its typed result; clients never access the
actor directly. Record envelopes are decoded and encoded with the bundled
`PlayFabJsonObject` Blueprint API, whose nested object, array, boolean,
numeric-text, and Unicode round trip has been proven locally. No Blueprint SHA-256
helper was exposed. Runtime version 1 therefore declares `structural-v1` and
uses strict schema/semantic validation plus transactional generations; it does
not silently substitute a weak checksum or claim cryptographic tamper detection.
The server-owned SaveGame is a trusted storage boundary. Native SHA-256 can be
introduced later as a new integrity mode without changing authored structs.

`EncodeJson` preserves insertion order rather than sorting object keys. Every
canonical encoder graph must therefore set fields in explicit ascending-key
order, and semantic graph contracts must lock that execution chain. Generic
iteration over a JSON object's fields is forbidden for canonical output.

### 8.3 Atomicity and recovery

Where the storage adapter lacks transactions, use copy-on-write records:

1. Validate complete candidate revision.
2. Write the canonical candidate to the inactive generation.
3. Mark candidate committed.
4. Update metadata pointer.
5. Retain or later garbage-collect the previous committed revision.

On load, ignore uncommitted candidates. A committed slot header is eligible only
when its schema version, positive generation, committed flag, and reserved empty
hash are valid. Eligible slots are scanned newest first at record granularity:
each canonical record envelope is decoded and semantically validated, and a
corrupt newest envelope may fall back to the matching older record without
discarding unrelated valid records from the new snapshot. Tombstones are
collected with their generation before records are selected, so a newer
committed tombstone masks every older copy of that Flypath. Malformed or
duplicate tombstone channels fail the repository load closed rather than risk
resurrection. Divergent committed slots with the same generation are a split
brain and also fail closed.

Candidate output is deterministic: records are ordered by Flypath ID,
tombstones are sorted and monotonic, and live IDs are disjoint from tombstones.
The repository only replaces authoritative memory after the inactive-slot
uncommitted stage write and its committed rewrite both succeed. The exact
Blueprint contract is mirrored by
`tools/persistence/alternating_snapshot_oracle.py`.

The live Blueprint state layer splits this contract into four narrow functions:
`ResetRepositoryStateV1`, `ValidateStorageHeadersV1`,
`PreparePersistenceCandidateV1`, and `CommitPersistenceCandidateV1`. They own
only deterministic scratch-state transitions and never imply that disk I/O has
succeeded. A separate adapter must perform `DoesSaveGameExist`, load/cast both
slots, stage the inactive uncommitted object, rewrite it committed, and feed
every success/failure edge back into these functions. Recovery then decodes
records individually according to the oracle above before replacing active
memory.

The read adapter is split into three accepted functions.
`ReadRepositoryStorageSlotAV1` and `ReadRepositoryStorageSlotBV1` each perform
their own existence check, load, executed cast to `SG_EDD_RepositoryStorage`,
and copy of schema version, generation, committed flag, reserved hash, record
envelopes, and tombstones into the corresponding scratch channel.
`ReadRepositoryStorageSlotsV1` resets both channels, invokes A then B, and
validates the two headers. Missing slots and failed casts terminate that slot
reader; a load failure leaves the reset defaults, so header validation rejects
the candidate. This layer deliberately does not select the authoritative
generation, recover individual records, replace repository memory, or report a
successful repository load. Those responsibilities remain in the recovery
layer, keeping raw I/O failure terminals separate from semantic recovery.

The write adapter is split into five accepted functions.
`ResetPersistenceWriteV1` clears only writer scratch flags;
`BuildPersistenceWriteStorageV1` creates `SG_EDD_RepositoryStorage` and fills
schema, candidate generation, uncommitted state, reserved empty hash, record
envelopes, and tombstones; `StagePersistenceWriteV1` writes that object to the
candidate inactive slot; `CommitPersistenceWriteV1` flips the same object to
committed and rewrites the same slot; `PersistRepositoryV1` coordinates those
steps and calls `CommitPersistenceCandidateV1` only after both physical writes
succeed. Create, stage, and commit failures return `PersistenceUnavailable`
with stable details and leave the previous authority unchanged. A real compiled
Blueprint invocation and a second fresh Unreal process prove success-path
authority promotion and exact physical payload persistence. Native disk-failure
injection remains a semantic-oracle test because Enhanced exposes no safe
failure-injection seam for `SaveGameToSlot`.

Recovery ordering is a second accepted layer, deliberately separate from raw
I/O and record decoding. `ResetRecoverySelectionV1` clears every recovery
scratch channel. `CompareRecoveryStringArraysV1` compares ordered arrays by
length and exact item equality; `CompareEqualGenerationStorageV1` applies it to
both record envelopes and tombstones. Four staging functions copy an eligible
A-only, B-only, A-newer, or B-newer pair into explicit newest/older channels.
`SelectRepositoryRecoveryOrderV1` chooses among those cases after header
validation. Identical equal-generation peers select B deterministically without
claiming two generations; unequal equal-generation peers set
`ScratchRecoveryFailedV1` and `DivergentEqualGeneration` and stage no authority.
This layer still does not validate tombstone semantics, decode individual
records, fall back corrupt newest records to older envelopes, replace active
repository memory, or set `RepositoryLoadedV1`.

The accepted Enhanced 5.6 construction seam is deliberately version-specific.
All four `GameplayStatics` calls (`DoesSaveGameExist`, `LoadGameFromSlot`,
`CreateSaveGameObject`, `SaveGameToSlot`) carry execution pins. Configuring
Create with `SG_EDD_RepositoryStorage` specializes its return pin to that class;
Load continues to return base `SaveGame`, so its completion and object output
must both feed a dynamic cast to `SG_EDD_RepositoryStorage`. Storage fields are
then accessed through object-targeted get/set nodes, never self-context guesses.
`Test-RepositorySaveGameNodeForms.py` owns these serialization contracts.

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

### 12.5 Deterministic desired-pose boundary

The first shared airframe/gimbal primitive is a history-free desired-pose
solver. Its inputs are absolute-time trajectory derivatives (current velocity,
look-ahead velocity sampled at the profile offset, acceleration, and jerk), two
normalized authored quaternions, and the accepted smoothed profile. It returns
normalized body, gimbal, and path quaternions plus finite speed, lateral
acceleration, turn-radius, and bank diagnostics. A turn-radius result of zero is
the explicit sentinel for stationary or straight motion; every finite turn is
positive.

The solver rejects invalid structure, non-finite values, non-unit quaternions,
profile-domain violations, acceleration/jerk excess, and finite turns tighter
than the active profile before publishing any result. Result validity is written
last after the complete record is safe. It never mutates trajectory or profile
inputs.

This desired-pose boundary intentionally does not consume frame delta and does
not apply `MaxAngularRateDegreesPerSecond`. The deterministic fixed-step compiler
above it applies angular-rate limits and prebakes any stateful continuity. This
separation keeps direct scrubbing history-independent while allowing the same
instantaneous target to drive Cinematic, Hybrid, Cinewhoop, Freestyle, and
Long-range compilation.

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
7. Apply transient local operator look/translation offsets.
8. Apply viewer comfort overrides.
9. Set camera transform and post-process state.

Evaluation uses precomputed tables/coefficients and avoids solving global curves
per frame.

### 14.1 Interactive carrier override

The compiled Flypath always produces a deterministic carrier transform. A
non-serialized `ST_EDD_OperatorOverrideState` can then add one of three local
runtime modes:

- `Directed`: zero live offset; use the authored camera result.
- `FreeLook`: keep authored/carrier position and replace or add to gimbal aim.
- `CarrierFreecam`: apply live six-axis translation and rotation relative to a
  stable carrier frame.

The carrier frame uses parallel transport or an equivalent twist-minimizing
construction rather than raw Frenet normals, which become unstable near straight
segments and inflection points. Operator translation may be world-aligned or
carrier/body-relative. Mode entry captures the current evaluated pose as the
zero-error blend origin. Recenter and mode exit decay position and rotation
offsets smoothly to zero with bounded velocity and acceleration.

Operator state is client-local, allocation-free during Tick, excluded from
published snapshot identity, and discarded on session restoration. It cannot affect Cue or
State Clip timing. If an author explicitly records an operator pass, sampled
input is reduced into normal editable gimbal/carrier-offset tracks before save;
raw per-frame input is never placed in a published record.

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
- Network: bounded documents, immutable revision keys, no per-frame transform RPCs
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

## 25. Event subsystem boundary

The timeline event subsystem is a sibling of trajectory/camera evaluation. It
compiles typed Cues and State Clips into a deterministic execution plan with an
absolute-time state index and Cue-crossing ledger. It never accepts arbitrary
class/function names from a client.

Local Cinematic events execute entirely on the viewer. Viewer Interaction and
Server World scopes cross a dedicated server-authoritative adapter layer that
validates authenticated identity, published Flypath ID/revision, target binding,
operation, server policy, rate limit, and current object state. Stateful
interactions may use bounded server leases only when an adapter supports reliable
read/restore/conflict behavior.

Serialized target bindings use durable Conan object IDs when available or an EDD
Event Anchor fallback. Transient actor pointers and unvalidated transform-only
lookup are not authoritative. Clone operations disable world bindings until the
new owner rebinds them. Full structures, RPC sequence, adapter behavior, door
policies, and acceptance scenarios are defined in `docs/event-system.md`.

## 26. UI and theme architecture

All UMG screens consume semantic tokens and shared components defined by the
visual design system. Theme assets provide palette, typography, spacing, borders,
icons, motion, track styles, and interaction states. Literal one-off styling in
screen widgets is rejected during review.

Timeline grids/curves/static guides use batched custom painting where the DevKit
allows it. Only visible interactive keys, handles, Cues, and State Clips receive
pooled widgets. Library/track rows are virtualized, and one authoritative
time-to-screen transform drives drawing, hit testing, snapping, zoom, and pan.

UI view models remain separate from Flypath documents and actors. A focus router
coordinates text entry, drone controls, viewport gestures, timeline shortcuts,
modals, and Emergency Exit. The UMG technology foundation is proven early rather
than deferred until polish. The token values, component inventory, visual states,
performance strategy, anti-patterns, and release quality gate are defined in
`docs/visual-design-system.md`.
