# Exile Drone Director — Implementation Plan

Status: execution plan for Conan Exiles Enhanced DevKit development
Planning rule: every phase ends in a cooked, testable vertical capability
Release strategy: prove safety and persistence before investing in maximal polish
Current internal build: `0.23.1-path-preview-clear`

## 1. Delivery strategy

Development proceeds through vertical slices rather than building all UI, all
math, or all networking in isolation. The first complete loop is intentionally
small:

**Create private Flypath → capture two waypoints → save on server → publish →
second client plays → second client clones privately**

That loop establishes the camera boundary, client/server attachment, durable
identity, persistence, authorization, network transport, immutable publication,
local evaluation, and cloning. Subsequent phases improve trajectory quality,
editor depth, camera visuals, and release hardening without replacing the core.

## 1.1 Current implementation checkpoint

This section is the authoritative handoff. Detailed evidence remains in
`devkit-findings.md`; exact clipboard procedure remains in
`blueprint-workflow.md`.

### Live in the Enhanced DevKit

- Project source is `T:\Projects\ExileDroneDirector`; the installed Enhanced
  DevKit root is `F:\CEUE5Devkit` (Unreal Engine 5.6.1).
- `BP_EDD_ModController`, `BPC_EDD_ClientDirector`, and
  `BP_EDD_DroneCamera` provide the current runtime slice.
- F10 enters/exits local Drone Mode; F9 performs idempotent emergency exit.
- The camera is a non-replicated local view target. It never possesses or moves
  the player pawn.
- W/S, D/A, and E/Q fly; mouse controls pitch/yaw; wheel trims cruise speed;
  Ctrl is precision; Shift is boost; C/Z bank; H toggles horizon lock.
- `CaptureCurrentWaypoint`, `ReplaceSelectedWaypoint`, and
  `DeleteSelectedWaypoint` are compiled live functions with reciprocal native
  entry links. Every successful mutation now invokes `SyncDraftWaypointsV1`
  before feedback, so the typed waypoint document is updated atomically with
  the six proven legacy channels.
- `StartLinearPlayback`, `UpdateLinearPlayback`, and `StopLinearPlayback` are
  compiled absolute-time functions. P toggles playback; active playback ticks
  suppress manual flight and waypoint edits. Completion holds the exact final
  authored transform until explicit stop, preventing horizon stabilization or
  manual input from pulling the camera off its last frame.
- The live 62-node/235-pin client EventGraph retains mutually exclusive K
  capture, R replace, and Delete removal shortcuts while inactive. Each
  successful mutation continues to shared dynamic feedback:
  `[EDD] Draft waypoints: N | selected: I`.
- Normal F10 exit, manual F9 emergency exit, and invalid-camera recovery each
  stop playback before restoring the player view.

### Runtime and structural evidence

- Two-player listen-server fixtures prove owning-client isolation, one local
  drone per client, unchanged controlled pawns, and exact view restoration.
- The selected-waypoint edit cycle proves two atomic captures, exact transform
  and lens replacement, survivor and empty deletion behavior, invalid-index
  no-ops, remote-client isolation, and restored drone class defaults.
- Physical PIE acceptance proves F10 entry, K capture, R replacement, Delete
  removal, and F9 restoration. The feedback build additionally proves a real K
  press emits `[EDD] Draft waypoints: 1 | selected: 0`.
- Pure reference tests prove direct-time linear evaluation, exact authored
  endpoints, equal segment duration, negative-time clamping, history
  independence, and shortest quaternion interpolation. A deterministic
  two-player PIE run through the real F10 entry route proves empty and
  single-waypoint no-ops, initial snap, absolute-time movement, exact final-frame
  hold, restart, explicit stop, client isolation, and unchanged possession/view
  restoration. It ended with `AUTOMATIC_RESULT:PASS`.
- Reviewed live graph snippets cover capture, replace, and delete. Their tests
  validate pin types, execution order, stable ID/hold behavior, all six array
  mutations, selection repair, and exact native function-entry linkage.
- The executable version-1 Flypath document oracle proves canonical lossless
  serialization and content hashes, structural waypoint/segment validation,
  optimistic revision conflicts, immutable published snapshots, owner-only
  editing, private-by-default creation/cloning, and clone attribution plus
  independence. Blueprint and server implementations must conform to it.
- `ST_EDD_Waypoint` contains the exact six-field lossless bridge and
  `BPC_EDD_ClientDirector` now compiles with a live `SyncDraftWaypointsV1`
  function. It checks all six channel lengths, positive unique IDs, finite
  camera scalars, positive focal length/aperture, and non-negative focus/hold
  values before mutation. It preserves the prior typed snapshot on any
  rejection, clears only after every guard succeeds, and rebuilds
  `DraftWaypointsV1` in ID-array order.
- The pure `SyncDraftWaypointsV1` oracle proves all-or-nothing lockstep
  validation, positive unique IDs, finite/valid camera scalars, ordered exact
  value copies, empty drafts, and snapshot independence. The live Blueprint now
  matches that complete preflight contract. `DraftWaypointsV1` is the validated
  authoritative read-side snapshot; the legacy arrays remain transitional
  write-side mutation channels until the authoring functions are migrated.
- `ST_EDD_Segment` and `ST_EDD_FlypathDocument` now contain the exact checked-in
  version-1 Blueprint schema. The client component compiles with empty
  `DraftSegmentsV1` and default-constructed `DraftDocumentV1` members. The
  schema/configurator contract is deterministic, executable, and idempotent;
  document population is deliberately the next transactional slice.
- `SyncDraftDocumentV1` is now a compiled, saved 124-node/552-pin live function.
  It invokes the typed waypoint preflight, reconciles surviving adjacencies by
  exact endpoint IDs, preserves every authored field of the first valid unused
  prior segment, allocates new monotonic segment IDs, rejects integer
  exhaustion, recomputes total duration, preserves editable document metadata,
  clears the stale content hash, and publishes `DraftSegmentsV1` plus
  `DraftDocumentV1` only after every guard succeeds. Nine pure executable cases
  cover the same transaction contract. A three-phase production-path PIE run
  now proves empty/single/two-waypoint rebuilds, exact endpoint references,
  segment ID `1`, repeat-sync idempotence, preservation of an authored `7.25`
  second Catmull-Rom/ease-in-out segment and document metadata, stale-hash
  clearing, malformed-channel rollback, and exact test-default restoration. It
  ended in `EDD_DOCUMENT_SYNC_PIE:AUTOMATIC_RESULT:PASS`.
- The exact native UE 5.6 Make/Break serialization for `ST_EDD_Segment` and
  `ST_EDD_FlypathDocument` is checked in and contract-tested. The generated pin
  suffixes, nested array element types, defaults, directions, and the native
  omission of explicit empty-string defaults are now stable inputs to the
  deterministic graph builder rather than undocumented editor knowledge.
- The generated 84-node/362-pin waypoint sync graph and copied post-compile
  Unreal round-trip both pass reciprocal-link and semantic contracts. A production-path
  PIE run
  proved empty rebuild, two exact captured struct values, repeat-sync
  idempotence, and clean camera restoration, ending in
  `EDD_WAYPOINT_STRUCT_PIE:AUTOMATIC_RESULT:PASS`.
- The generated capture/replace/delete bodies and their copied live Unreal
  round-trips now require the sync call on every successful execution path.
  An adaptive production-path PIE edit cycle proved exact typed parity after
  capture 1, capture 2, replacement, survivor deletion, empty deletion, and
  invalid-edit no-ops. It ended in
  `EDD_WAYPOINT_PIE:AUTOMATIC_RESULT:PASS`; the optional second-world isolation
  branch was explicitly skipped in that one-player run and remains covered by
  the earlier two-player authoring acceptance.
- Repository scaffold, semantic graph contracts, Python syntax, and the 1 GiB
  repository budget pass. Tracked source is only a few MiB; DevKit and cooked
  outputs are never committed.
- `BP_EDD_PathPreview` now has a typed `PreviewDocumentV1` seam, explicit marker
  and line-scale defaults, and two non-colliding movable HISM pools using Engine
  sphere and cube meshes. `ClearPreviewV1` is a compiled and saved five-node
  live function that clears `WaypointMarkersV1` before `SegmentLinesV1`; its
  fresh Unreal export has 11 pins and passes reciprocal-link plus dedicated
  semantic contracts. `RebuildPreviewV1` now has a compiled 14-node/60-pin
  marker slice: clear both pools, guard on `PreviewEnabled`, break the typed
  document, iterate ordered typed waypoints, preserve each camera location and
  rotation, replace scale with uniform `MarkerScaleV1`, and add one world-space
  sphere instance. The checked live export and deterministic generator both pass
  structural and semantic contracts. A three-phase production-path PIE gate
  proved exact one/two-marker counts and transforms, zero segment instances,
  clear-to-zero behavior, class-default restoration, and temporary-actor cleanup.
  A seven-case pure geometry oracle also locks ordered marker placement,
  midpoint/orientation/length scaling for linear segments, vertical paths,
  degenerate adjacency suppression, invalid-value rejection, and history
  independence. Linear segment projection is the next bounded preview gate;
  client lifecycle wiring follows it. Visible marker runtime output is now
  claimed, while visible segment output is not.

### Reproducible graph evidence

- `Build-ClientWaypointEditDispatch.py` produces the proven 43-node K/R/Delete
  dispatch; `Build-WaypointFeedbackDispatch.py` extends it to the live 51-node
  feedback graph; `Build-LinearPlaybackDispatch.py` extends that to the live
  62-node playback-arbitrated graph.
- The generated graph and the copied post-compile Unreal round-trip both pass
  generic reciprocal-link validation, capture/edit semantics, and the dedicated
  feedback contract. The contract caught and prevented an invalid first draft
  whose string defaults were discarded during Unreal reconstruction.

### Not implemented yet

- No polished editor UI, visible waypoint/path preview, timeline, cinematic
  curves, lens playback, save/load, server repository, sharing, permissions,
  cloning, or event execution exists yet. The current playback is deliberately
  limited to equal-duration transform interpolation over the transient draft.
- Draft waypoint data is client-local and transient. Other server members
  cannot see or play it.
- No cooked `.pak` or Steam Workshop item exists. GitHub source cannot be added
  directly to G-Portal.

### Exact next autonomous slice

The attended cook/Workshop step remains deliberately separate. The next
autonomous implementation slice is:

1. Complete `RebuildPreviewV1` as a bounded, independently validated projection
   from the accepted typed document: clear both pools, add ordered waypoint
   sphere instances, add one oriented/scaled cube for each non-degenerate
   adjacency, and prove exact instance counts/transforms in PIE.
2. Add draft undo/redo with explicit transaction boundaries for capture,
   replace, delete, and later segment edits.
3. Preserve the physical F10/K/P/P/F9 route and the three-phase document-sync
   validator as regression acceptance paths
   for every change that touches playback or authoring.
4. Close, sync, run the complete repository suite, commit, and push after each
   meaningful compiled milestone.

The first supported cook/package and normal-client test remain mandatory before
any public release or Workshop/G-Portal deployment; they resume in an attended
session without invalidating the implementation work above.

The shortcut-extension preparation sequence, run from the repository root after
copying the complete live EventGraph, is:

```powershell
$liveEvent = Join-Path $env:REDLEAF_SCRATCH_DIR 'client-event-live.eddgraph'
$editEvent = Join-Path $env:REDLEAF_SCRATCH_DIR 'client-event-k-r-delete.eddgraph'

.\tools\blueprint\Export-BlueprintGraphClipboard.ps1 `
  -DestinationPath $liveEvent
python .\tools\blueprint\Build-ClientWaypointEditDispatch.py `
  --input $liveEvent --output $editEvent
.\tools\blueprint\Test-BlueprintGraphSnippet.ps1 -Path $editEvent
python .\tools\blueprint\Test-WaypointCaptureContracts.py `
  --capture .\tools\blueprint\snippets\capture-current-waypoint.eddgraph `
  --event $editEvent
.\tools\blueprint\Set-BlueprintGraphClipboard.ps1 -SnippetPath $editEvent
```

After paste/compile/save, copy the complete live EventGraph again and substitute
that round-trip export for `$editEvent` in both validators. The generated file
passing before paste is necessary but not sufficient.

### Near-term test gates

- **Hands-on PIE gate:** Laurent can fly for several minutes, capture at least
  three points, replace/delete the selection, and exit with the original camera
  and pawn intact.
- **Cooked local gate:** the same slice loads from a packaged mod in normal
  Conan Enhanced, survives relaunch, and restores safely outside PIE.
- **G-Portal gate:** publish a test Workshop item, install it on an Enhanced
  backup/staging server, use identical client/server mod version and load order,
  and repeat the camera-restoration test. This gate initially tests only local
  camera/authoring behavior; server-shared Flypaths arrive in Phases 7-8.

## 2. Engineering rules

- Build Blueprint assets only inside the official Enhanced DevKit.
- Keep all mod-owned assets under `Content/Mods/ExileDroneDirector`.
- Never edit or relocate base-game assets; attach components through the Mod
  Controller and subclass/reference supported classes.
- Sync closed-editor `.uasset` source back to the Git repository after each
  verified slice.
- Test both PIE and cooked mod behavior; PIE success alone is insufficient.
- Test on a dedicated server as soon as the first RPC exists.
- Keep authoring data, compiled trajectory data, and UI state separate.
- Never use display name as ownership authority.
- Never add a smoothness feature without a discontinuity/scrub test.
- Never enter a camera state without a tested restoration path.

## 3. Phase 0 — DevKit reconnaissance and project creation

### Objectives

Confirm the Enhanced-specific integration points and create the real mod asset
root.

### Tasks

1. Complete and verify the DevKit installation.
2. Launch the DevKit and create `ExileDroneDirector` through its mod menu.
3. Record exact generated paths and Mod Controller conventions.
4. Identify candidate player controller, player character, HUD, game state,
   game mode, and server-owned persistence hosts.
5. Inspect component attachment rules for Client, Server, and Server and Client
   Copies.
6. Identify available input system and safe custom-action strategy.
7. Confirm camera, Cine Camera, post-process, SaveGame, GUID, quaternion, spline,
   and file/runtime rendering nodes exposed to Blueprint.
8. Identify the durable authenticated account/player ID exposed server-side.
9. Create a findings document with exact asset paths, screenshots, and rejected
   alternatives.

### Verification

- Mod loads in PIE with a visible diagnostic message.
- Cooked empty mod loads in local game without modifying a base asset.
- Client and dedicated-server component BeginPlay can be distinguished in logs.
- The repository's sync tool recognizes the actual DevKit layout.

### Exit gate

The project cooks, loads, and has confirmed client/server attachment candidates.

## 3.1 UI technology and design-system spike

This bounded spike begins immediately after the empty mod cooks; it does not wait
for the full-editor phase.

### Objectives

Prove that the Enhanced DevKit exposes the UMG painting, focus, pooling, and input
hooks needed for a polished production timeline and establish the shared theme
before one-off widgets proliferate.

### Tasks

1. Create central theme/token assets using the palette, type, spacing, shape,
   motion, track, and state definitions in `docs/visual-design-system.md`.
2. Build production candidates for button, numeric field, slider, panel, icon,
   tooltip, track row, key, Cue, and State Clip components.
3. Prototype the responsive viewport/list/inspector/timeline workspace.
4. Demonstrate adaptive timeline grid/ruler, pan/zoom, playhead scrub, batched
   curve drawing, pooled key/clip dragging, and context-inspector switching.
5. Prove text focus does not leak drone/timeline shortcuts and Emergency Exit
   remains reachable.
6. Measure at 1080p, 1440p, 4K, ultrawide, and representative UI scales.

### Exit gate

The interaction foundation meets its frame-time budget, scales correctly, and
passes the initial visual QA checklist using mock data. These widgets become the
production component library rather than a disposable mockup.

## 4. Phase 1 — Safe local camera vertical slice

### Objectives

Enter Drone Mode, move a local camera, and restore the game perfectly.

### Assets

- `BP_EDD_ModController`
- `BPC_EDD_ClientDirector`
- `BP_EDD_DroneCamera`
- `WBP_EDD_DroneHUD`
- Initial state/input enums and settings struct

### Tasks

1. Attach the client director only to the owning local player context.
2. Implement the client state machine: Inactive, Entering, Flying, Restoring.
3. Cache original pawn, view target, input mode, cursor, HUD state, and movement
   policy.
4. Spawn a non-replicated camera actor and call local view-target switching.
5. Implement six-axis movement, mouse look, speed trim, normal/fine/boost modes,
   and optional horizon lock.
6. Separate camera input from carrier motion so the same controller can support
   Directed, Free Look, and Carrier Freecam modes during later playback.
7. Keep the player pawn physically unchanged and never change possession. Drive
   the non-replicated local drone with explicit delta-time transform integration,
   and restore only the cached view target on exit.
8. Implement idempotent Emergency Exit.
9. Bind restoration to death, pawn replacement, teleport, disconnect, UI close,
   camera destruction, and component end-play.
10. Add an opt-in collision sweep and diagnostic HUD.

Current vertical-slice progress: tasks 1, 4, and 7 are proven in a two-player
listen-server PIE fixture. Each director gates input by owning-local-controller
identity; host and remote client create non-replicated local drones, move them
independently at the expected 600 units/second, retain their original controlled
pawns, and restore their exact prior view targets. Task 5 has proven W/S, D/A,
and E/Q translation and now contains compiled local mouse-look dispatch using
raw mouse delta, configurable sensitivity, inverted pitch, and zero roll. Host
yaw plus host/client world isolation were observed in PIE; hands-on client
pitch/yaw feel remains pending because the automation layer cannot inject raw
mouse input into the detached preview. Speed trim, precision, and boost are now
implemented as a separate named contract: proportional 1.25x wheel trim,
30-6000 clamp, 0.25x Ctrl precision, 3x Shift boost, precision precedence, and
delta-time `FInterpTo` smoothing. Host and remote-client runtime checks proved
baseline, easing, target speeds, movement-distance ordering, isolation, and
exact F9 restoration. Physical-wheel feel remains a hands-on gate. Smooth
horizon lock is now compiled and runtime-proven: H toggles it, held C/Z wins,
disabled lock preserves bank, and enabled lock eases toward explicit world up
without changing current pitch/yaw. Host/client isolation and exact F9
restoration were re-proven with the completed 33-node function.
Task 8 is proven idempotent through F9, and camera destruction within task 9 is
proven through the active-camera validity guard. Death, teleport, disconnect,
UI-close, component-end-play, dedicated-server, and cooked-runtime acceptance
remain explicit gates.

### Test matrix

- Single-player PIE
- Listen server as host and client
- Dedicated server with two clients
- Enter/exit ten consecutive times
- Exit while moving and while UI has keyboard focus
- Die/respawn, teleport, disconnect, and close UI while active
- Destroy camera actor artificially
- Reload mod/session and verify normal Conan camera/input

### Exit gate

The cooked mod can fly for ten minutes and survives every restoration test without
moving the pawn, losing input, retaining a cursor/HUD override, or duplicating a
camera actor.

## 5. Phase 2 — Local Flypath authoring core

### Objectives

Create an in-memory private Flypath and edit intentional waypoints.

### Assets

- `ST_EDD_FlypathDocument`
- `ST_EDD_Waypoint`
- `ST_EDD_Segment`
- `BP_EDD_PathPreview`
- Editor command/undo structs
- Expanded `WBP_EDD_Editor`

### Tasks

1. Implement stable IDs for waypoints, segments, and editor commands.
2. Capture current drone position, body/gimbal rotation, basic focal length/FOV,
   and focus distance into a waypoint.
3. Append, insert, replace, duplicate, reorder, and delete waypoints.
4. Jump the editor camera to a selected waypoint without moving the pawn.
5. Provide exact numeric transform editing plus WASD/mouse fine adjustment.
6. Render numbered markers and a linear path preview.
7. Implement transactional undo/redo for all waypoint operations.
8. Implement structural validation and clear diagnostics.
9. Keep draft model independent from preview actor components.

Current vertical-slice progress: task 1 now has a stable monotonic waypoint ID
source, and the append/replace/delete core is implemented and runtime-proven.
`CaptureCurrentWaypoint` snapshots the local drone transform plus focal length,
aperture, manual focus distance, and zero hold time into six temporary lockstep
arrays owned only by `BPC_EDD_ClientDirector`; it selects the appended index and
advances the ID only after every channel append completes.
`ReplaceSelectedWaypoint` preserves the stable ID and hold while replacing the
five camera-state channels at a valid selection. `DeleteSelectedWaypoint`
removes all six channels atomically and clamps selection to the surviving item
or `-1`. These arrays remain the explicit transitional runtime model while the
new typed bridge is integrated; they are not the final server document. All
three live graphs have semantic pin-level contracts.
A deterministic two-player edit cycle proved two captures, lens/transform
replacement, middle/end/empty deletion behavior, invalid-index no-op behavior,
remote-client isolation, exact pawn/view restoration, and restoration of the
drone class defaults. The reviewed K/R/Delete dispatch and shared dynamic
count/selection feedback are live in the 51-node EventGraph. Real keyboard input
passed after the one-time PIE character was saved, and the complete compiled
graph now round-trips into the checked-in textual source with capture, edit, and
feedback contracts.

The version-1 document oracle is also complete. It gives the Blueprint data
assets a tested target contract before runtime migration. Nine executable
tests cover canonical round-trip serialization, content-integrity rejection,
finite and normalized camera state, ID/topology validation, private creation,
optimistic saves, immutable publication, private deep clones, attribution, and
owner/viewer access. Runtime save/load is not claimed until the Blueprint
adapter and server persistence layer consume this contract.

The first mapping step is live: `ST_EDD_Waypoint` has Integer `WaypointId`,
Transform `CameraTransform`, and Float `FocalLength`, `Aperture`,
`ManualFocusDistance`, and `HoldSeconds`. `SyncDraftWaypointsV1` now performs a
guarded structural migration from the six legacy channels into
`DraftWaypointsV1`. It validates every channel length, positive unique IDs, and
the complete finite/scalar camera domain before clearing the prior typed
snapshot, then maps one indexed value from every channel into each struct. The
complete 84-node/362-pin graph compiles green, round-trips with reciprocal links,
and passed production-path PIE for empty, exact two-waypoint, idempotent, and
restoration behavior. Capture/edit dispatch calls it on every successful
mutation, making the typed array the authoritative read-side document snapshot
while the legacy arrays remain temporary write-side channels.

The first visible preview slice is also live. `RebuildPreviewV1` consumes the
accepted `ST_EDD_FlypathDocument` directly, clears both HISM pools before every
evaluation, stops cleanly when preview is disabled, and adds one ordered
world-space marker for every typed waypoint. A three-phase PIE harness uses the
real capture/document pipeline to seed one and then two waypoints into fresh
preview actors. It proves exact instance transforms and counts, confirms the
segment pool stays empty in the marker-only slice, exercises one-to-zero and two-to-zero
clears, restores class defaults, and removes every temporary editor actor. The
next step is the independently contract-tested linear segment loop, followed by
client-owned spawn/update/teardown wiring.

### Verification

- Author twenty waypoints and edit the middle ten.
- Undo/redo the full operation chain without changing IDs/order incorrectly.
- Delete and reinsert endpoints.
- Feed invalid/NaN-equivalent values through UI boundaries and reject them.
- Maintain acceptable editor frame time with the initial maximum waypoint count.

### Exit gate

A creator can compose and revise a local multi-waypoint Flypath reliably, and its
document can be serialized/deserialized in memory without loss.

## 6. Phase 3 — Trajectory compiler v1

### Objectives

Produce deterministic, scrub-safe playback with linear, manual cubic, and smooth
cinematic trajectories.

### Assets

- Trajectory compiler Blueprint/function library
- Compiled segment/sample structs
- Arc-length table implementation
- Time-profile curve assets/presets
- Trajectory diagnostics

### Tasks

1. Define the compiled Flypath representation and engine version `1`.
2. Implement Linear spatial segments.
3. Implement cubic Hermite/Bezier with generated and manual tangents.
4. Implement quintic position interpolation with shared position, velocity, and
   acceleration boundary constraints for C2 cinematic continuity.
5. Implement Stop, Glide, Fly-by, Tight, and Cut corner modes.
6. Build adaptive arc-length tables and distance-to-parameter inversion.
7. Implement monotonic Linear, Smoothstep, Smootherstep, and Cinematic S-curve
   time profiles.
8. Implement duration and target-speed modes plus impossible-constraint warnings.
9. Sample curves for overshoot, collision, duration, and continuity diagnostics.
10. Make evaluation a pure function of compiled data and absolute time.

### Verification

- Constant-speed test over unequal curved segments.
- Direct scrub to arbitrary time equals forward playback result.
- Position is exact at required interpolating waypoints.
- Numeric derivative probes show expected C0/C1/C2 continuity.
- No curve loop/overshoot with standard auto presets on adversarial waypoint sets.
- Linear and Cut remain deliberately discontinuous only where requested.
- Identical document and engine version produce identical sampled outputs.

### Exit gate

The editor plays and scrubs linear, manual, and C2 cinematic paths with stable
timing and actionable diagnostics.

## 7. Phase 4 — Rotation, flight profiles, and deterministic drone character

### Objectives

Separate airframe and gimbal and deliver Cinematic, Hybrid, and FPV identities.

### Tasks

1. Normalize and sign-align serialized rotations.
2. Implement quaternion multi-key interpolation using SQUAD or a Blueprint-safe
   equivalent with smooth angular velocity.
3. Implement Cinematic airframe tangent/look-ahead orientation and clamped
   curvature-derived banking.
4. Implement independent gimbal orientation, horizon lock, fixed look-at, and
   weighted body-lock.
5. Implement Hybrid stabilization as a continuous blend.
6. Build deterministic FPV compilation with gates, acceleration/turn limits,
   bank/pitch derivation, camera uptilt, and fixed-timestep prebaking.
7. Add Cinewhoop, Freestyle, Long-range, Cinematic, and Hybrid presets.
8. Add deterministic coherent wind/vibration tracks with stored seeds.
9. Add a minimum-snap/seventh-order spike; adopt only if Blueprint solve cost and
   numerical stability beat the quintic system meaningfully.

### Verification

- No quaternion long-way flips or Euler wrap artifacts.
- Angular velocity does not visibly jump at smooth waypoint boundaries.
- Scrubbing produces stable body/gimbal transforms.
- FPV playback is identical at different game frame rates.
- Presets produce observably distinct behavior from identical waypoints.
- Procedural motion repeats exactly and blends in/out continuously.

### Exit gate

One waypoint layout can be replayed convincingly as stabilized cinematic,
body-expressive hybrid, and momentum-driven FPV without reauthoring positions.

## 8. Phase 5 — Camera, lens, focus, and visual tracks

### Objectives

Turn trajectory playback into authored cinematography.

### Tasks

1. Confirm cooked Cine Camera/post-process property availability.
2. Implement the common scalar-track evaluator and curve presets.
3. Add focal length, filmback, aperture, focus distance, focus influence,
   exposure EV, and effect blend-weight tracks.
4. Implement manual focus, Set Focus Here trace, fixed focus marker, rack focus,
   and smoothed fixed-target autofocus.
5. Add linear-distance and reciprocal-distance/diopter focus interpolation.
6. Visualize focal plane and approximate depth-of-field range in editor.
7. Add dolly-zoom authoring helper.
8. Add supported bloom, vignette, grading/tint, motion blur, chromatic aberration,
   sharpening, matte, and other verified effect tracks.
9. Build named base looks without hiding individual values.
10. Implement viewer comfort overrides for roll, shake, blur, exposure changes,
    and chromatic aberration.

### Verification

- Every continuous scalar track passes value/derivative boundary probes.
- Focus and focal-length pulls scrub and replay identically.
- Dolly zoom keeps the selected fixed subject approximately constant in frame.
- Unsupported cooked properties fail as unavailable, not as broken controls.
- Comfort overrides are local and do not mutate the Flypath document.

### Exit gate

A creator can author a smooth lens/focus/effect sequence aligned with movement,
and another viewer can safely reduce comfort-sensitive effects.

## 9. Phase 6 — Full editor UI

### Objectives

Deliver the library/editor/timeline workflow described by the product design.

### Tasks

1. Implement responsive editor layout with collapsible panels.
2. Build waypoint list, viewport overlays, and property inspector.
3. Build timeline travel/hold blocks and draggable playhead.
4. Add track visibility, key selection, key dragging, box selection, and retime.
5. Build curve editor with semantic presets and advanced tangent controls.
6. Add Smooth Selected/Everything with lock-aware transactions.
7. Add error/warning navigation to exact waypoint/segment/track.
8. Add remappable controls and prevent bindings while editing text.
9. Add dirty/saving/conflict/recovery status.
10. Add keyboard navigation and usable scaling at supported resolutions.

### Verification

- Complete an authoring task using primarily mouse/UI.
- Repeat using primarily keyboard/drone controls.
- Undo/redo bulk retime and smoothing as single transactions.
- Resize/collapse panels without losing selection or active edit.
- Test input focus, text fields, sliders, curve handles, and Emergency Exit.

### Exit gate

A knowledgeable player can create and fine-tune a polished Flypath without
opening debug tools or understanding the underlying Blueprint graph.

## 10. Phase 7 — Server repository, identity, and private drafts

### Objectives

Persist owner-editable private Flypaths across dedicated-server restarts.

### Tasks

1. Complete storage-adapter spike and select the supported server persistence
   mechanism.
2. Implement server repository and metadata index.
3. Resolve durable authenticated account identity.
4. Implement server policy and validation limits.
5. Implement Create, List Mine, Fetch Draft, Save Draft, Rename, and Delete.
6. Add optimistic concurrency and typed errors.
7. Add debounced save, retry/backoff, offline-change state, and save-as-new conflict
   recovery.
8. Add schema/version serialization and first migration harness.
9. Add bounded rate limiting and server logs.

### Verification

- Create/save/reconnect/reload private Flypath.
- Restart dedicated server and recover identical data/ownership.
- Attempt update/delete from a second account and receive Forbidden.
- Open same path in two sessions and exercise RevisionConflict.
- Corrupt/incompletely write a test candidate and recover previous committed data.
- Exceed every configured limit and receive a safe typed failure.

### Exit gate

Private Flypaths are durable, server-authoritative, owner-protected, and
recoverable.

## 11. Phase 8 — Publishing, discovery, playback, and cloning

### Objectives

Complete the social Flypath loop.

### Tasks

1. Implement atomic Publish Draft and Unpublish.
2. Implement paged My Flypaths and Server Flypaths metadata queries.
3. Implement published snapshot fetch/cache by ID, revision, and hash.
4. Implement library search/filter/sort and compatibility badges.
5. Implement individual viewer playback preparation, countdown, controls, and
   safe restoration.
6. Implement Directed, Free Look, and Carrier Freecam playback modes with
   snap-free entry, recenter, return-to-directed, speed trim, and emergency exit.
7. Implement a stable twist-minimizing carrier frame plus world-aligned and
   body-relative operator controls.
8. Keep operator offsets local and outside published snapshot hashes, event
   evaluation, and server authority.
9. Implement Clone Published as a deep private copy with attribution.
10. Ensure draft edits never mutate published revision.
11. Ensure republish never changes active playback snapshots.
12. Add administrative unpublish/delete and policy controls.
13. Add region/bounds compatibility checks.

### Two-client acceptance scenario

1. Player A creates and saves a private Flypath.
2. Player B cannot list or fetch it.
3. Player A publishes revision 1.
4. Player B discovers and begins revision 1 playback.
5. Player A edits the draft and publishes revision 2.
6. Player B finishes revision 1 unchanged.
7. Player B replays and receives revision 2.
8. Player B clones revision 2; clone is private and owned by B.
9. Player A edits/deletes the source; B's clone remains unchanged.

### Exit gate

The complete create/refine/publish/discover/play/clone/remix loop works on a
dedicated server with enforced privacy and immutable playback.

## 11.1 Event tracks and world-interaction vertical slice

### Objectives

Add safe local Cues and server-authorized State Clips without turning Flypaths
into an unrestricted remote-control mechanism.

### Tasks

1. Implement Event track, Cue, State Clip, target-binding, adapter, and compiled
   execution-plan structures from `docs/event-system.md`.
2. Implement local presentation Cues and deterministic Cue-crossing ledger.
3. Implement absolute-time State Clip evaluation and scrub-safe preview.
4. Build Bind Target viewport interaction and resolution diagnostics.
5. Implement EDD Event Anchor, then a narrow door adapter.
6. Ship `Wait Until Open` before any mutating door operation.
7. Add viewer-authorized interaction and typed server results.
8. Add bounded cinematic state leases only after cancellation, disconnect,
   conflict, and restoration tests pass.
9. Add publishing capability metadata, policy controls, rate limits, and clone
   binding disable/rebind behavior.

### Acceptance sequence

- Scrubbing across a Cue never executes a world action.
- Real playback fires each configured Cue exactly once per loop/direction policy.
- A door State Clip reaches open state before camera arrival or applies its
  explicit failure policy.
- Unauthorized viewers cannot change the door.
- Cancel/disconnect restores or safely yields leases without affecting camera
  restoration.
- A clone is private and cannot use the source world binding until reauthorized.

### Exit gate

Local Cues and one narrow door workflow operate predictably on a dedicated server
with explicit permission, failure, clone, and cleanup behavior.

## 12. Phase 9 — Streaming, capture, and playback polish

### Objectives

Make real-world server playback and recording dependable.

### Tasks

1. Test camera-driven streaming at route extremes and different regions.
2. Implement route preparation/prewarming supported by Conan.
3. Add conservative bounds/speed policy where streaming cannot keep up.
4. Implement Clean Playback HUD suppression and configurable countdown.
5. Document OBS and Steam Recording workflows.
6. Add loop, selection playback, and deterministic repeated takes.
7. Add optional authoring-pass capture that reduces live Free Look/Carrier
   Freecam operation into editable gimbal and carrier-offset keys.
8. Verify that pausing freezes the carrier while preserving live camera control.
9. Probe runtime Movie Render Pipeline and image/video outputs in cooked build.
10. Add direct rendering only behind an experimental flag if completely safe.
11. Investigate optional local thumbnail capture.

### Verification

- Long route, fast FPV route, dense build, dungeon/interior, and low-client-FPS
  cases.
- Cancel capture at every stage and restore UI/view.
- Repeated takes produce identical evaluated transforms.
- Remote recording never moves the player pawn.

### Exit gate

Clean external recording is reliable; direct rendering is either verified and
isolated or explicitly documented as unsupported.

## 13. Phase 10 — Release hardening

### Objectives

Ship a supportable public Workshop release.

### Tasks

1. Profile Blueprint CPU, allocations, preview component counts, network payloads,
   server storage, and load times.
2. Tune policy defaults and waypoint/key limits from measurements.
3. Complete schema migration and downgrade/future-version messages.
4. Test mod load order and known UI/input conflicts.
5. Validate installation/update on fresh client and dedicated server.
6. Write player guide, server-admin guide, privacy/PvP warning, troubleshooting,
   and recovery instructions.
7. Add in-mod version/build diagnostics.
8. Produce sample Flypaths covering cinematic, hybrid, FPV, orbit, rack focus,
   and dolly zoom.
9. Run a closed two-server beta before public Workshop publication.

### Exit gate

No critical camera-restoration, ownership, privacy, persistence, or corrupt-save
defects remain; public documentation matches actual cooked behavior.

## 14. Test strategy

### 14.1 Automated/math harnesses

Where Blueprint automation is available, build data-driven tests for:

- Curve endpoints and finite values
- C0/C1/C2/C3 derivative continuity expectations
- Arc-length constant-speed error tolerance
- Time-curve monotonicity
- Quaternion shortest path and angular continuity
- Deterministic procedural noise
- Serialization round-trip and migration
- Authorization decision tables
- Document bounds and validation

If the DevKit lacks a useful automation runner, expose deterministic editor
utility tests and golden sampled outputs that can be run before cooking.

### 14.2 Manual runtime matrix

- Single-player
- Listen server host/client
- Dedicated server with at least two accounts
- High/low frame rate
- Death/respawn
- Teleport and region transition
- Disconnect/reconnect
- Server restart
- Mod update/schema migration
- Dense player build and empty landscape
- Long cinematic and high-speed FPV paths
- Different UI scaling/resolutions and remapped controls

### 14.3 Release-blocking defect classes

- Player camera/input cannot be restored
- Player pawn moved/teleported unintentionally
- Unauthorized private data access or mutation
- Clone linked to or mutating its source
- Published revision changes during active playback
- Server persistence corruption or destructive migration
- Non-deterministic published trajectory at different frame rates
- Unbounded RPC/storage payload

## 15. Risk register and mitigation

| Risk | Impact | Mitigation/spike |
| --- | --- | --- |
| No clean dedicated-server mod persistence | Critical | Repository adapter spike; persisted actor or supported server SaveGame fallback |
| No durable Blueprint account ID | Critical | Inspect authenticated controller/player state; block sharing until authoritative identity exists |
| Camera view target does not drive streaming | High | Early remote-route spike; prewarm/bounds restrictions; same-region policy |
| Cine Camera/post-process stripped in cook | High | Cooked Phase 0/5 probes; fallback Camera component and supported properties |
| Blueprint global minimum-snap solve unstable | Medium | Ship quintic C2 first; precompute bounded systems; reserve seventh-order for verified cases |
| FPV integration depends on frame rate | High | Fixed-step compile/prebake and absolute-time sample evaluation |
| UMG curve editor too expensive/fragile | Medium | Semantic presets first; advanced editor built after core evaluator |
| Public Flypaths enable PvP scouting | High | Admin/creative defaults, range/region policy, explicit warnings |
| Large revisions overload RPC/storage | High | Limits, on-demand fetch, hashes, full-document measurement before deltas |
| DevKit update moves private base members | Medium | Attachment adapters, minimal base coupling, version diagnostics |
| Enhanced cook/upload has no stable headless entry point | High | Prove the Funcom plugin commandlet; otherwise use a self-hosted Windows runner with a narrowly automated editor cook step |
| Workshop credentials or Steam Guard make unattended CI fragile | High | Create and accept the first item manually; keep secrets off Git; prefer an authenticated self-hosted runner and deliberate release approval |
| Direct video output unavailable | Low | External recording is the supported baseline |
| World events become a remote-control/PvP exploit | Critical | Typed adapters, server policy, revision validation, target binding, rate limits, clone rebind |
| Stateful event rollback overwrites concurrent changes | High | Adapter conflict detection, bounded leases, conservative yield, explicit persistent actions |
| Blueprint UMG timeline becomes slow/incoherent | High | Early production UI spike, batched drawing, pooling/virtualization, token/component enforcement |

## 16. Planned asset organization

```text
Content/Mods/ExileDroneDirector/
  BP_EDD_ModController
  Core/
    Client/
    Server/
    Camera/
    Validation/
  Data/
    Structs/
    Enums/
    Presets/
    Curves/
  Trajectory/
    Compiler/
    Evaluator/
    FlightProfiles/
    Diagnostics/
  Persistence/
    Repository/
    Adapters/
    Migration/
  UI/
    Library/
    Editor/
    Timeline/
    Playback/
    Settings/
    Style/
    Components/
  Events/
    Adapters/
    Bindings/
    Execution/
    Anchors/
  Debug/
  Tests/
```

## 17. Version roadmap

- **0.1 Camera Spike:** safe enter/fly/exit in cooked multiplayer.
- **0.2 Local Authoring:** waypoints, undo, linear and cinematic playback.
- **0.3 Drone Motion:** quaternion/gimbal, cinematic/hybrid/FPV profiles.
- **0.4 Camera Suite:** lens, focus, effects, full timeline.
- **0.5 Server Drafts:** identity, persistence, ownership, conflicts.
- **0.6 Sharing Alpha:** publish, library, viewer playback, cloning.
- **0.7 Directing Alpha:** local Cues, State Clips, bindings, and safe door adapter.
- **0.8 Capture Beta:** streaming/capture polish, admin policy, migrations.
- **1.0 Public Release:** hardened complete loop and documentation.

Version numbers describe capability gates, not calendar promises.

Internal checkpoint versions such as `0.21.0-flypath-schema-bridge` count validated
development slices. They do not claim that the public **0.1 Camera Spike** gate
is complete; that gate still requires cooked multiplayer acceptance.

## 18. Immediate execution priority

The installation and initial camera reconnaissance are complete. Follow the
exact session runbook in section 1.1. The immediate sequence is:

1. Generate, paste, compile, and round-trip `SyncDraftDocumentV1` against its
   reconciliation oracle; then connect every successful waypoint mutation to
   it and prove the transaction in PIE.
2. Visible path preview, serialization, and undo/redo.
3. Cinematic interpolation profiles built on the validated absolute-time kernel.
4. First cook/package proof in normal Conan Enhanced when an attended session is
   available.
5. Test Workshop item and controlled G-Portal deployment only after that cooked
   build passes locally.

The first public capability milestone is not “the camera moved in PIE.” It is
“the cooked mod entered, flew, authored a small draft, and exited safely on a
dedicated-server client.”

## 19. Definition of done for 1.0

The release is done when the product release criteria in the design specification
pass on a dedicated server, all release-blocking defect classes are cleared, the
server can restart without losing or exposing Flypaths, motion and camera tracks
remain smooth and deterministic, and a normal player can complete the full
creative/social loop without developer assistance.
