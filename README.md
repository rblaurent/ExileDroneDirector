# Exile Drone Director

Exile Drone Director is a Blueprint-only cinematic creation and sharing mod for
Conan Exiles Enhanced. Players fly a virtual drone, capture camera waypoints,
refine movement/timing/lens/effects, and publish immutable Flypath revisions to
their server. Other server members can play public Flypaths or clone them into
private editable copies.

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
3. `docs/implementation-plan.md` — phased build plan, exit gates, test matrix,
   risks, asset organization, and release criteria.

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

## Current status

The product design, technical architecture, implementation sequence, source
mirror, and synchronization tooling are established. Unreal `.uasset` files must
be authored and cooked through the official Conan Exiles Enhanced DevKit; they
cannot be generated faithfully as text source.

The first technical milestone is a cooked dedicated-server client that can enter,
fly, and safely exit Drone Mode without unpossessing or moving the player pawn.

## Repository layout

- `project.json` — stable project identity and first-slice asset contract.
- `docs/` — authoritative product, architecture, and implementation documents.
- `DevKitContent/ExileDroneDirector/` — source mirror for DevKit-created `.uasset`
  and `.umap` files.
- `tools/Sync-DevKitContent.ps1` — non-destructive synchronization between the
  repository and an installed DevKit.
- `tools/Test-Scaffold.ps1` — validates the textual scaffold and optionally the
  first-slice Unreal assets.

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
