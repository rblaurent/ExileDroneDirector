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

- The player pawn remains possessed and is never moved by a Flypath.
- Drone authoring and playback use a local camera view target.
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
typed local drone camera that is reused on the next entry. The next technical
milestone is the view lifecycle: cache the original view target, place the
drone at the current camera, switch locally, and restore safely without
unpossessing or moving the player pawn.

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
