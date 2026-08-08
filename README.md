# Exile Drone Director

`Exile Drone Director` is a Blueprint-only cinematic camera mod for Conan Exiles
Enhanced. It lets a player fly a local camera, capture deliberate camera
waypoints, refine their timing, and replay a smooth shot for video capture.

## Current status

The project is in the pre-DevKit scaffold phase. The functional design, asset
boundaries, MVP acceptance criteria, and safe DevKit synchronization tooling are
ready. Unreal `.uasset` files must be created from the official Conan Exiles
Enhanced DevKit; they cannot be generated faithfully as text files.

## Core workflow

1. Enter Drone Mode without unpossessing the player character.
2. Fly and frame the shot.
3. Capture position, rotation, FOV, and timing as a waypoint.
4. Repeat for the rest of the shot.
5. Refine waypoint and segment timing in the timeline.
6. Preview the smoothed route.
7. Run a clean playback pass while an external recorder captures the game.

Direct Movie Render Queue output is deliberately treated as a later technical
spike. It depends on which runtime modules Funcom ships in the cooked game.

## Repository layout

- `project.json` -- stable project identity and planned assets.
- `docs/architecture.md` -- Blueprint architecture and runtime behavior.
- `docs/mvp-backlog.md` -- ordered implementation and acceptance criteria.
- `DevKitContent/ExileDroneDirector/` -- source mirror for `.uasset` and `.umap`
  files created by the DevKit.
- `tools/Sync-DevKitContent.ps1` -- non-destructive synchronization between the
  workspace and an installed DevKit.
- `tools/Test-Scaffold.ps1` -- validates this scaffold and, optionally, MVP assets.

## Prerequisite

Install **Conan Exiles Enhanced Dev Kit** through Epic Games. The current
Enhanced documentation uses this content location beneath the installation:

```text
<DevKitRoot>/UE4/Content/Mods/ExileDroneDirector
```

The sync tool also recognizes the older
`Games/ConanSandbox/Content/Mods` layout for diagnostic convenience.

## First DevKit session

1. Create a new mod named exactly `ExileDroneDirector` from the DevKit menu.
2. Close the editor after the empty mod has been generated.
3. Import any existing source-mirror assets with:

```powershell
.\tools\Sync-DevKitContent.ps1 -Direction ToDevKit -DevKitRoot 'D:\ConanExilesEnhancedDevKit'
```

4. Reopen the DevKit and implement the vertical slice from
   `docs/mvp-backlog.md`.
5. Close the editor before syncing changed assets back into the workspace:

```powershell
.\tools\Sync-DevKitContent.ps1 -Direction FromDevKit -DevKitRoot 'D:\ConanExilesEnhancedDevKit' -Force
```

The sync operation never deletes files. `-Force` is required to replace a
different destination asset.
