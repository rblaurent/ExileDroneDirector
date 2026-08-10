# Exile Drone Director

Exile Drone Director is a Blueprint-only cinematic creation and sharing mod for
Conan Exiles Enhanced. Players fly a virtual drone, capture camera waypoints,
refine movement/timing/lens/effects, choreograph supported timeline events, and
publish immutable Flypath revisions to their server. Other server members can
play public Flypaths or clone them into private editable copies.

It is deliberately a dedicated Flypath and camera-direction tool rather than a
general server-management framework. Playback can be fully directed, free-look
while the path carries the camera, or six-axis freecam around the moving path
carrier.

## Product loop

**Fly → capture → refine → preview → publish → discover → experience → clone → remix**

New Flypaths are private. Clones are private. A public Flypath exposes only an
immutable published revision; the creator's ongoing draft remains private until
they explicitly publish changes.

## Design documents

Read these in order:

1. `docs/product-design.md` — product behavior, permissions, library/editor UX,
   movement profiles, lens/effects, playback, and server policy.
2. `docs/architecture.md` — client/server boundaries, data model, persistence,
   trajectory compilation, deterministic evaluation, security, and recovery.
3. `docs/event-system.md` — Cues, State Clips, door/object binding, execution
   scopes, event authority, cloning safety, and synchronized-performance rules.
4. `docs/visual-design-system.md` — Conan-derived palette, design tokens,
   component library, timeline language, UMG strategy, and UI quality gates.
5. `docs/implementation-plan.md` — phased build plan, exit gates, test matrix,
   risks, asset organization, and release criteria.

6. `docs/devkit-findings.md` — verified Enhanced installation identity, exact
   integration paths, local API findings, and rejected Legacy assumptions.
7. `docs/blueprint-workflow.md` — the validated graph-snippet workflow used to
   batch Blueprint logic without relying on per-node mouse automation.

## Architectural invariants

- The player pawn is never moved, teleported, or destroyed by a Flypath.
- Drone authoring and playback use a non-replicated, client-local camera/view
  target. Drone Mode never changes controller possession and never treats the
  player's character transform as Flypath data.
- Every exit/error path restores camera, input, cursor, and HUD state.
- The server is authoritative for ownership, privacy, publishing, cloning, and
  persistence.
- Published playback uses an immutable downloaded snapshot.
- Geometry, time/speed, airframe, gimbal, lens, and effects are separate smooth
  evaluation layers.
- Published trajectories are deterministic and independent of client frame rate.
- Timeline world interactions are typed, bound, permission-checked events—not
  arbitrary remote function calls.
- Every screen uses one theme and component system derived from Conan's palette.

## Current status

The Enhanced UE 5.6.1 mod container and first Unreal asset scaffold now exist.
The scaffold includes a Funcom ModController, client-only director component,
SpectatorPawn-based CineCamera drone, spline path preview, Flypath data structs,
HUD widget, and Enhanced Input assets. All compile and save with zero errors.

PIE now proves that Funcom discovers and spawns `BP_EDD_ModController`, attaches
`BPC_EDD_ClientDirector` to the Conan player controller, executes the client
component, edge-toggles persistent Drone Mode state, and spawns exactly one
typed local drone camera that is reused on the next entry. It also captures the
local controller's original view target exactly once and reuses that reference
on later entries. The client now switches Player Controller 0 to the guarded
drone view and restores the cached player view on exit. A four-transition PIE
run now proves exact pre-switch placement as well: both the first camera and
the reused camera copied Player Camera Manager 0's evaluated location and
rotation before activation, then restored the same original view target on
exit. Manual F9 emergency exit is now idempotent, and an active camera validity
guard automatically restores the player if the drone actor disappears. A
forced-destruction PIE test restored `CameraActor_0`, cleared
`DroneModeActive`, left zero drone actors, and then spawned a fresh drone on the
next entry. The drone now has frame-rate-independent six-axis local translation:
W/S, D/A, and E/Q form one local vector, scaled by smoothed
`CurrentMoveSpeed` and world delta time, then applied as a single actor-local
offset. Mouse look now samples
Player Controller 0's `GetInputMouseDelta`, applies a configurable
`LookSensitivity` of 0.12 degrees per mouse unit, inverts pitch, preserves zero
roll, and performs one actor-local rotation after translation on each active
tick. The nine-node function and its client dispatch round-trip through reviewed
Blueprint graph snippets and compile without errors. A two-player
listen-server PIE test used two deterministic possessed `DefaultPawn` fixtures
so Conan's unfinished character-creation flow could not contaminate the camera
contract. Across the focused runs, host and remote client independently entered,
moved, and exited Drone Mode; neither controller changed its controlled pawn and
each exact original view target was restored. The final post-fix run proved
isolated client motion with a stationary host drone and no cross-world drone
replication. Runtime BeginPlay explicitly disables both
actor and movement replication because `SpectatorPawn` otherwise forced
inherited replication on spawned instances. No Blueprint runtime error or
`Accessed None` occurred. A focused follow-up run also exercised host yaw while
the remote PIE world remained free of host drones, then independently entered
and exited the remote client's local drone with both exact original view targets
restored. Automated raw-mouse injection into the separate client preview did not
reach Unreal's raw-input path, so client pitch/yaw feel remains an explicit
hands-on acceptance check rather than an overclaimed automated proof.
`UpdateSpeedControls` now owns proportional mouse-wheel cruise trim, clamping,
Ctrl precision, Shift boost, precision precedence, and smoothed target changes.
A deterministic two-player PIE run proved a 600 baseline, intermediate easing,
approximately 1800 boost and 150 precision targets, normal/boost/precision
movement-distance ordering, local client isolation, and exact F9 restoration.
Synthetic wheel events did not reach Conan's mouse-input channel, so physical
wheel feel remains a manual check while its complete pin topology is enforced
offline. `ApplyRollAndHorizonInput` now adds smooth manual bank after mouse
rotation on the same guarded active tick. C-minus-Z selects a signed target of
up to 90 degrees/second, `CurrentRollSpeed` eases with response 8, and the
post-write speed is integrated with world delta time into one roll-only local
rotation. In the deterministic two-player PIE fixture, C moved host roll from
0 to +71.77 degrees and released at 9.30 degrees/second before decaying to
0.00018; Z then drove the opposite direction at -10.30 degrees/second and
returned the bank near level. Client 1 independently reached +71.27 degrees
while the host remained exactly at 1.195 degrees, and both F9 exits restored
their exact original pawn and view target. The C/Z fixture triggers known
`FunCombat_PlayerController` null-character errors because the deliberately
minimal `DefaultPawn` has no Conan character; neither EDD Blueprint emitted a
runtime error. H now toggles smooth horizon lock. Held C/Z always wins; with
lock disabled the authored bank persists, and with lock enabled the camera
interpolates toward a level frame built from its current forward direction and
explicit world up. The corrected two-player proof held about 74 degrees of bank
with lock off, visibly eased it toward zero after H, preserved seeded pitch 20
and yaw 45, isolated host/client state, and restored exact prior view targets.
The first waypoint authoring core is now live. `CaptureCurrentWaypoint` creates
an atomic client-local draft snapshot and selects it;
`ReplaceSelectedWaypoint` updates its camera state without changing stable ID or
hold; `DeleteSelectedWaypoint` removes all six lockstep channels and repairs the
selection. The three live functions round-trip through Unreal and pass semantic
pin-level contracts. A deterministic two-player PIE edit cycle proved two
captures, exact replacement, survivor/empty deletion, invalid-index no-ops,
remote isolation, exact original pawn/view restoration, and restoration of lens
class defaults. The guarded active-mode EventGraph now exposes mutually
exclusive `K`, `R`, and `Delete` edges and prints the current draft count and
selected index after each successful mutation. The client now also has compiled
absolute-time start/update/stop playback functions. P toggles the equal-duration
linear path; active playback suppresses manual flight and edits, and every
normal/emergency exit stops playback first. The generated and Unreal-round-trip
62-node/235-pin EventGraph passes reciprocal-link and semantic contracts. The
real F10 production route has now passed deterministic two-player PIE acceptance
for invalid drafts, initial snap, absolute-time movement, exact final-frame hold,
restart, explicit stop, isolation, and possession/view restoration. An
engine-independent Flypath document oracle now locks down canonical JSON,
content hashes, revision conflicts, immutable publication, private creation and
cloning, attribution, and structural camera/path validation. The compiled
`SyncDraftWaypointsV1` bridge now validates all six channel lengths, positive
unique IDs, finite camera scalars, positive focal length and aperture, and
non-negative focus distance and hold time before mutation. Its generated and
live Unreal round-trip graphs contain 84 nodes/362 pins and pass reciprocal-link
plus semantic contracts. Capture, replace, and delete invoke the bridge before
feedback on every successful mutation. Production-path PIE proved empty
rebuild, exact two-waypoint mapping, idempotence, exact typed parity after both
captures/replacement/survivor and empty deletion, invalid-edit no-ops, and
restoration. `DraftWaypointsV1` is now the validated authoritative read-side
snapshot; the six legacy arrays remain only the transitional write-side
capture/edit channels. The exact version-1 `ST_EDD_Segment` and
`ST_EDD_FlypathDocument` schemas are now authored and compiled as well, and the
client owns empty typed `DraftSegmentsV1` plus default-constructed
`DraftDocumentV1` bridge members. Their checked-in schema contract and
configurator are deterministic and idempotent. `SyncDraftDocumentV1` now
transactionally reconciles those members from `DraftWaypointsV1` in a compiled,
saved 124-node/552-pin live graph. Structural contracts prove valid pin
directions, monotonic ID fan-out, preserved-segment selection, three-second new
segment defaults, duration accumulation, metadata preservation, and atomic
publication. A three-phase runtime PIE gate now also proves empty, single, and
two-waypoint rebuilds, authored-segment and metadata preservation, idempotence,
malformed-input rollback, and exact class-default restoration.
`BP_EDD_PathPreview` now owns typed document input plus pooled sphere/cube HISM
components. Its first live body, `ClearPreviewV1`, compiles and clears both pools
in a contract-tested order. The visible document-to-instance rebuild and PIE
transform proof are next, followed by client lifecycle integration and undo/redo.
Cooked-package validation remains required but is explicitly deferred until an
attended session.

## Repository layout

- `project.json` — stable project identity and first-slice asset contract.
- `docs/` — authoritative product, architecture, and implementation documents.
- `DevKitContent/ExileDroneDirector/` — source mirror for DevKit-created `.uasset`
  and `.umap` files.
- `tools/Sync-DevKitContent.ps1` — non-destructive synchronization between the
  repository and an installed DevKit.
- `tools/Test-Scaffold.ps1` — validates the textual scaffold and optionally the
  first-slice Unreal assets.
- `tools/blueprint/` — validates, exports, and prepares native Blueprint graph
  clipboard snippets without launching the DevKit.
- `tools/document/` — executable Flypath serialization, revision, publication,
  ownership, and clone contracts for the Blueprint/server implementation.

## DevKit setup

Install **Conan Exiles Enhanced Dev Kit** through Epic Games. The current
Enhanced layout places mod source beneath:

```text
<DevKitRoot>/UE4/Content/Mods/ExileDroneDirector
```

The sync tool also recognizes the older
`Games/ConanSandbox/Content/Mods` layout for diagnostic convenience.

Create the mod named exactly `ExileDroneDirector` through the DevKit menu before
synchronizing assets. Close the editor before copying binary assets in either
direction.

```powershell
.\tools\Sync-DevKitContent.ps1 -Direction ToDevKit -DevKitRoot 'F:\ConanExilesDevKit'
.\tools\Sync-DevKitContent.ps1 -Direction FromDevKit -DevKitRoot 'F:\ConanExilesDevKit' -Force
```

The sync operation never deletes files. `-Force` is required to replace a
different destination asset.
