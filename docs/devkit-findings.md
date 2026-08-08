# Enhanced DevKit Findings

Status: active reconnaissance log
Target: Conan Exiles Enhanced Dev Kit, Unreal Engine 5.6.1

## Installation identity

The Epic library contains two similarly named products. They are not
interchangeable:

| Product | Expected engine | Suitable for this project |
| --- | --- | --- |
| Conan Exiles Dev Kit | Unreal Engine 4.15.x | No; Legacy only |
| Conan Exiles Enhanced Dev Kit | Unreal Engine 5.6.1 | Yes |

On 2026-08-08, an installation at `F:\ConanExilesDevKit` was verified as the
Legacy kit using all of the following local evidence:

- Epic display name: `Conan Exiles Dev Kit`
- Epic namespace/app: `conanexiles` / `ConanExiles`
- Launch executable: `Engine/Binaries/Win64/UE4Editor.exe`
- `Engine/Build/Build.version`: `4.15.3`
- Content root: `Games/ConanSandbox/Content/Mods`

It was rejected before any Exile Drone Director asset was created.

The correct Enhanced kit was subsequently installed and verified:

- Install root: `F:\CEUE5Devkit`
- Project: `F:\CEUE5Devkit\UE4\ConanSandbox.uproject`
- Editor: `Engine\Binaries\Win64\UnrealEditor.exe`
- Engine: Unreal Engine `5.6.1`, changelist `370197`
- Branch: `++exiles+release`
- DevKit content root: `F:\CEUE5Devkit\UE4\Content`
- DevKit mod root: `F:\CEUE5Devkit\UE4\Content\Mods`
- Epic manifest status: complete (`bIsIncompleteInstall: false`)

## Mandatory verification before project creation

Do not create, copy, sync, open, resave, or cook project assets until all checks
pass:

1. Epic display name is exactly `Conan Exiles Enhanced Dev Kit`.
2. `Engine/Build/Build.version` reports engine major `5`, minor `6`.
3. A writable mod root exists at `UE4/Content/Mods` or the current Enhanced
   documentation's replacement path.
4. The editor launches with the Enhanced Conan project and exposes the mod menu.
5. The generated mod folder and `modinfo.json` are recorded before adding assets.

`tools/Sync-DevKitContent.ps1` independently enforces the engine-major/minor
check. A path merely containing the word `Enhanced` is not accepted as proof.

## Confirmed Enhanced documentation assumptions

- The Enhanced DevKit is based on Unreal Engine 5.6.1.
- Existing UE4 mod concepts remain relevant, but assets and cooked packages are
  not cross-compatible.
- Mod-owned assets remain isolated under the selected mod's Content/Mods root.
- The Mod Controller remains the supported hub for component attachment and
  data-table merging unless local inspection proves an Enhanced-specific change.

## Generated mod container

The Funcom DevKit creator generated and activated:

`F:\CEUE5Devkit\UE4\Content\Mods\ExileDroneDirector`

Initial contents are `active.txt`, `modinfo.json`, `Content/`, and `Shared/`.
The generated metadata identifies `minimumVersion` as `Enhanced`. The mod was
created through Funcom's Dreamworld Mods UI; its metadata schema was not guessed
or copied from the Legacy kit.

The editor was launched with Python Script Plugin and Editor Scripting Utilities
enabled. Both mounted successfully, making repeatable editor automation possible.

## Verified first asset scaffold

The first idempotent generation pass created 14 mod-owned packages beneath the
Dreamworld `Local/` overlay (142 KB total). The commandlet completed with zero
errors and no scaffold warnings.

Verified integration points:

- `BP_EDD_ModController` inherits Funcom's `ModController`.
- `BPC_EDD_ClientDirector` is attached to
  `FunCombat_PlayerController` using `AdditionalClassComponent` with the
  client-only `CLIENT` rule.
- `BP_EDD_DroneCamera` inherits `SpectatorPawn` and owns a
  `CineCameraComponent` named `DroneCamera`.
- `BP_EDD_PathPreview` owns a `SplineComponent` named `PathSpline`.
- Enhanced Input actions and a mapping context were created for toggle, move,
  look, boost, and waypoint capture.
- Flypath document, waypoint, and segment struct assets plus the initial HUD
  Widget Blueprint were created.

The source mirror sync was verified under Windows PowerShell 5.1 and all Unreal
binary extensions are covered by Git LFS.

## Verified first runtime integration

A single-player PIE run in `/Game/Dev/AlmostEmpty` proved the complete first
client attachment chain:

1. `LogModManager` found `BP_EDD_ModController_C` in the active mod.
2. Persistence spawned `BP_EDD_ModController_C` alongside the example controller.
3. `BPC_EDD_ClientDirector_C` executed its BeginPlay `Print String` node.
4. PIE reached the Conan character-creation UI without modifying or possessing a
   base-game pawn.

The initial diagnostic string was `Hello`; its value is unimportant. The log
owner was `[BPC_EDD_ClientDirector_C]`, which is the acceptance evidence that the
Funcom client-only `AdditionalClassComponent` rule instantiates and runs the
project component.

This proves local PIE discovery and attachment. It does not yet prove cooked,
listen-server, dedicated-server, restoration, or authenticated-player behavior.

## Verified local Drone Mode state transition

A focused PIE acceptance run on 2026-08-08 proved the first executable Drone
Mode contract inside `BPC_EDD_ClientDirector`:

1. Event Tick polls local Player Controller 0 with
   `WasInputKeyJustPressed(F10)`.
2. Only the true edge executes the state transition.
3. The transition computes and stores
   `DroneModeActive = NOT DroneModeActive`.
4. The diagnostic converts the Set node's post-write output to a string and
   logs only after the write completes.

The compiled Blueprint reported green status and `All Saved`. In one PIE
session, two F10 presses produced these ordered component-owned messages:

```text
[BPC_EDD_ClientDirector_C] true
[BPC_EDD_ClientDirector_C] false
```

This proves edge detection, persistent component state, correct inversion, and
post-write diagnostic ordering. It does not yet prove view-target switching,
restoration, or input-context installation.

## Verified idempotent local drone-camera spawn

A second focused PIE acceptance run on 2026-08-08 proved the first
`EnterDroneMode` function contract:

1. `DroneCameraRef` is checked with `Is Valid` before any spawn attempt.
2. An invalid reference spawns exactly `BP_EDD_DroneCamera` with an explicit
   identity transform and caches the returned typed reference.
3. A valid reference bypasses spawning and takes the reuse path.
4. The Event Graph dispatches the post-write `DroneModeActive` value to
   `EnterDroneMode` or `ExitDroneMode`.

Three F10 presses in one PIE session produced these ordered component-owned
messages:

```text
[BPC_EDD_ClientDirector_C] true
[BPC_EDD_ClientDirector_C] [EDD] Drone camera spawned
[BPC_EDD_ClientDirector_C] false
[BPC_EDD_ClientDirector_C] true
[BPC_EDD_ClientDirector_C] [EDD] Drone camera already valid
```

The Blueprint compiled successfully in 96 ms and was saved before PIE. The
third-press reuse diagnostic proves that the first spawned reference remained
valid and that the function did not create a second camera. This does not yet
prove camera placement at the current view, view-target switching, restoration,
destruction, or cooked behavior.

## Verified idempotent original-view-target capture

`ActivateDroneView` now owns a separate, focused cache contract. It resolves
local Player Controller 0, reads `Get View Target`, and writes
`OriginalViewTargetRef` only when the existing reference is not valid. Both
camera-ready paths in `EnterDroneMode` delegate to this function.

The component compiled successfully after the isolated function was built and
again after both delegation calls were added. A three-press PIE run produced:

```text
[BPC_EDD_ClientDirector_C] true
[BPC_EDD_ClientDirector_C] [EDD] Drone camera spawned
[BPC_EDD_ClientDirector_C] [EDD] Original view target cached
[BPC_EDD_ClientDirector_C] false
[BPC_EDD_ClientDirector_C] true
[BPC_EDD_ClientDirector_C] [EDD] Drone camera already valid
[BPC_EDD_ClientDirector_C] [EDD] Original view target already cached
```

This proves the original view is captured before any future view switch,
persists across a normal Drone Mode exit/re-entry, and is not overwritten by a
later entry. It does not yet prove drone placement, local view-target switching,
restoration, destruction, or cooked behavior.

## Verified reusable local view lifecycle

Three named functions now divide the camera lifecycle into explicit contracts:

1. `ActivateDroneView` caches the current view target once, then delegates both
   the new-cache and reuse paths to `SwitchToDroneView`.
2. `SwitchToDroneView` validates `DroneCameraRef`, resolves local Player
   Controller 0, and calls `SetViewTargetWithBlend` with the typed drone camera.
3. `ExitDroneMode` independently validates `OriginalViewTargetRef` and restores
   that actor through the same local Player Controller 0 API.

Both view calls currently use a zero-second blend. This keeps the first
acceptance contract immediate and deterministic; cinematic transition shaping
belongs to a later camera-profile layer rather than this lifecycle primitive.

The complete client director compiled successfully in 81 ms. One PIE session
then exercised four F10 transitions and produced these ordered diagnostics:

```text
[BPC_EDD_ClientDirector_C] [EDD] Drone camera spawned
[BPC_EDD_ClientDirector_C] [EDD] Original view target cached
[BPC_EDD_ClientDirector_C] [EDD] Drone view active
[BPC_EDD_ClientDirector_C] [EDD] Player view restored
[BPC_EDD_ClientDirector_C] [EDD] Drone camera already valid
[BPC_EDD_ClientDirector_C] [EDD] Original view target already cached
[BPC_EDD_ClientDirector_C] [EDD] Drone view active
[BPC_EDD_ClientDirector_C] [EDD] Player view restored
```

No `Accessed None`, Blueprint runtime error, or PIE error appeared. The second
entry proves both references are reusable; the second exit proves restoration
is not a one-shot path. Source contracts additionally require both validity
guards, both exact view targets, local Player Controller 0, and diagnostics that
execute only after `SetViewTargetWithBlend` returns. Deliberate mutations of the
view API and restoration reference were rejected by the offline suite.

This proves reusable local view switching and normal restoration. It does not
yet prove placement at the pre-switch camera transform, emergency restoration
after teardown/disconnect, input-context cleanup, cooked behavior, or
multiplayer isolation.

## Blueprint graph automation boundary

The editor Python API can locate the component Event Graph, but the graph object
has no node insertion methods. This Enhanced build exposes base `EdGraph` and
`K2Node` types without the concrete event/call/branch constructors required for
safe graph authoring.

Unreal's native Blueprint clipboard serialization is available and includes node
classes, function references, pins, links, positions, defaults, and identifiers.
The project therefore uses reviewed `.eddgraph` snippets for batch graph work.
See `docs/blueprint-workflow.md` and `tools/blueprint/`.

## Pending local reconnaissance

- Drone placement at the pre-switch camera and movement graphs
- Emergency camera restoration and the view lifecycle in cooked runtime
- PIE and cook commands/output locations
- Authenticated server identity and persistence APIs
