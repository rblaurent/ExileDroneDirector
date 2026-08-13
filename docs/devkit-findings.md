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

The interactive editor must be launched with `-ModDevKit`:

```powershell
& 'F:\CEUE5Devkit\Engine\Binaries\Win64\UnrealEditor.exe' `
  'F:\CEUE5Devkit\UE4\ConanSandbox.uproject' `
  -ModDevKit
```

Launching the same project without `-ModDevKit` produces a normal Unreal editor
session in which `/Game/Mods/ExileDroneDirector` is not mounted. Mod asset loads
then fail despite the physical files being present. Verify the launch argument
before treating that symptom as missing or corrupt content.

## Mandatory verification before project creation

Do not create, copy, sync, open, resave, or cook project assets until all checks
pass:

1. Epic display name is exactly `Conan Exiles Enhanced Dev Kit`.
2. `Engine/Build/Build.version` reports engine major `5`, minor `6`.
3. A writable mod root exists at `UE4/Content/Mods` or the current Enhanced
   documentation's replacement path.
4. The editor launches with the Enhanced Conan project, includes `-ModDevKit`,
   and exposes the mod menu.
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

## Verified camera-relative drone placement

`PlaceDroneAtCurrentView` now owns one narrow, idempotent placement contract:

1. Validate the typed `DroneCameraRef`.
2. Resolve local Player Camera Manager 0.
3. Sample its evaluated `GetCameraLocation` and `GetCameraRotation` values.
4. Apply both values atomically to the drone with
   `SetActorLocationAndRotation` before any view-target switch.
5. Report either `[EDD] Drone placed at current view` or the guarded
   no-camera diagnostic.

Both the already-valid and newly-spawned paths in `EnterDroneMode` call this
function before `ActivateDroneView`. The isolated placement graph compiled in
77 ms; the complete client director compiled successfully in 73 ms. Its source
contract fixes the graph at 10 nodes and requires the camera guard, Player
Camera Manager 0, reciprocal location and rotation links, the typed drone as
the transform target, no sweep, no teleport, and post-write diagnostics. The
14-node Enter contract independently requires both placement delegations to
finish before their paired activation calls.

A focused PIE run on 2026-08-09 exercised two complete F10 enter/exit cycles.
The initial pre-entry camera state was:

```text
view=CameraActor_0
location=(-2173.703563, -2186.756988, -105.795139)
rotation=(pitch=0.000000, yaw=43.616007, roll=-0.000000)
```

The first entry spawned `BP_EDD_DroneCamera_C_0`; its actor transform, active
view-target transform, and Player Camera Manager transform all matched those
values exactly at the printed precision. Exit restored `CameraActor_0` at the
same transform. The second entry reused the same
`BP_EDD_DroneCamera_C_0`, placed it from the restored camera again, and produced
the same exact equality before a second successful restoration. The ordered
component diagnostics were:

```text
[EDD] Drone camera spawned
[EDD] Drone placed at current view
[EDD] Original view target cached
[EDD] Drone view active
[EDD] Player view restored
[EDD] Drone camera already valid
[EDD] Drone placed at current view
[EDD] Original view target already cached
[EDD] Drone view active
[EDD] Player view restored
```

No Blueprint runtime error or `Accessed None` occurred. Offline negative tests
also reject a missing camera-location sampler and either missing Enter placement
delegation.

This proved exact placement, reuse, activation, and normal restoration at that
stage. The character-creation phase reports `get_controlled_pawn() = None`, so a
same-character restore still requires a gameplay map. Later movement work added
explicit drone possession and a guarded no-original-pawn fallback, documented
below. That possession experiment was later rejected; the accepted multiplayer
backend and its remaining cooked-runtime gate are documented further below.

## Verified manual and invalid-camera emergency recovery

`EmergencyExitDroneMode` now owns a four-node, idempotent recovery contract:

1. Delegate view restoration to the already-guarded `ExitDroneMode` primitive.
2. Force `DroneModeActive` to `false` after restoration returns.
3. Report `[EDD] Emergency exit complete` to the log.

The client Event Graph polls F9 only after a tick does not consume F10. F9's
true path calls the emergency function directly. Its false path checks
`DroneModeActive`; only an active session continues to an `IsValid` check of
the typed `DroneCameraRef`, whose false path calls the same emergency function.
The saved executable Event Graph contains 24 Blueprint nodes, and the complete
client director compiled successfully in 102 ms.

Offline mutation checks reject changing F9 to F8, removing either emergency
caller, or changing the emergency `DroneModeActive` write from `false` to
`true`.

A focused PIE run on 2026-08-09 first exercised normal entry followed by F9:

```text
[EDD] Drone camera spawned
[EDD] Drone placed at current view
[EDD] Original view target cached
[EDD] Drone view active
[EDD] Player view restored
[EDD] Emergency exit complete
```

Calling F9 again while already restored repeated the guarded restoration and
completion diagnostics without a runtime failure, proving that the public
emergency primitive tolerates an already-inactive session.

The same PIE session then entered Drone Mode again and destroyed the active
`BP_EDD_DroneCamera_C` actor through the editor console. On the next component
tick the invalid-camera guard restored the view and cleared active state. The
queried post-recovery state was:

```text
view=/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty:PersistentLevel.CameraActor_0
active=False
drones=0
```

A subsequent F10 entry spawned a replacement camera and reported:

```text
view=BP_EDD_DroneCamera_C
active=True
drones=1
```

F9 then restored the player again. No Blueprint runtime error or `Accessed
None` occurred during the manual exit, forced camera loss, automatic recovery,
or re-entry windows.

This proves the public emergency function and the active-camera destruction
hook in PIE. It does not yet prove restoration from death, pawn replacement,
teleport, disconnect, UI close, component end-play, a cooked build, or a second
network client.

## Superseded native-movement and possession experiment

The first six-axis translation slice uses one named 17-node
`ApplyTranslationInput` function on `BP_EDD_DroneCamera`:

1. Resolve local Player Controller 0.
2. Sample W, S, D, A, E, and Q with `GetInputAnalogKeyState`.
3. Form the signed axes `W-S`, `D-A`, and `E-Q`.
4. Resolve the drone's actor forward, right, and up vectors.
5. Execute three chained `AddMovementInput` calls with `bForce = true`.

`SpectatorPawnMovement.MaxSpeed` and `BaseMoveSpeed` are both 600;
`BoostMultiplier` is 3 but is not yet applied by the first translation graph.
The client Event Graph invokes this function only while `DroneModeActive` is
true and `DroneCameraRef` is valid. The movement graph round-tripped with 17
unique nodes, exact W/S/D/A/E/Q defaults, three reciprocal forced movement
calls, and no compiler metadata errors.

An unpossessed runtime probe revealed an important engine contract:
`AddMovementInput` accumulated a pending vector, but
`SpectatorPawnMovement` did not consume it. Possessing the drone cleared the
pending vector and enabled native movement. The client lifecycle now makes that
resource transition explicit:

- `CacheOriginalPawn` stores `GetPlayerPawn(0)` in typed `OriginalPawnRef`.
- `PossessDroneCamera` validates `DroneCameraRef`, resolves Player Controller 0,
  and calls `Possess`.
- `RestoreOriginalPossession` possesses a valid cached pawn; when the cached
  pawn is invalid it calls `UnPossess`.
- `ActivateDroneView` caches the pawn before its existing view-target work.
- `SwitchToDroneView` possesses the drone before `SetViewTargetWithBlend`.
- `ExitDroneMode` restores possession before restoring the cached view target.

All helper and integration graphs were copied back from the live editor,
checked for unique node/pin IDs and reciprocal links, compiled with `Good to
go`, and saved. A focused PIE run on 2026-08-09 then proved:

- F10 automatically controlled `BP_EDD_DroneCamera_C_0`.
- Holding W moved from `(-2173.704, -2186.757, -105.795)` to
  `(-1666.702, -1703.676, -105.795)`, matching yaw `43.616` forward travel.
- Holding D moved from `(-1666.702, -1703.676, -105.795)` to
  `(-1981.526, -1373.263, -105.795)`, matching the local right axis.
- Holding E raised Z from `-105.795` to `220.903` without changing X/Y.
- F9 logged player-view restoration and emergency completion, then
  `get_controlled_pawn()` returned `None`, which is the correct guarded result
  for the character-creation map's missing original pawn.
- A second F10 reused and re-possessed the same drone actor; a second F9 again
  restored cleanly.

No Blueprint runtime error or `Accessed None` occurred. This proves the native
movement backend and the no-original-pawn lifecycle in authoritative
single-player PIE. The multiplayer test below supersedes native possession as
the production movement architecture. A gameplay-character test must still
cover Conan's concrete player pawn class.

### Valid-pawn identity and transform restoration proof

A second focused PIE run supplied the `AlmostEmpty` controller with a runtime
`DefaultPawn_0` surrogate at location `(1300, 200, 700)` and rotation
`(pitch=37, yaw=0, roll=5)`, then possessed it before entering Drone Mode. This
turns the normally unpossessed character-creation map into a deterministic
lifecycle fixture without modifying the map.

The observed state sequence was:

1. Before F10, `DefaultPawn_0` was the controlled pawn.
2. After F10, `BP_EDD_DroneCamera_C_0` was the controlled pawn and both actors
   still began at `(1300, 200, 700)`.
3. Holding W moved the drone to approximately
   `(1856.328, 200, 1119.224)` while `DefaultPawn_0` remained at its original
   transform.
4. After F9, the controller again reported the exact same `DefaultPawn_0`
   object (`SAME_OBJECT True`), still at its original location and rotation.

There was no Blueprint runtime error or `Accessed None`. This proves the valid
pawn branch preserves object identity and does not disturb the original pawn's
transform in authoritative single-player PIE. The Player Controller reported
`AUTH True`; remote-client possession and a concrete Conan character remain
separate acceptance gates.

For repeatable PIE fixtures, use
`SystemLibrary.execute_console_command(..., "summon /Script/Engine.DefaultPawn")`
and then filter `GameplayStatics.get_all_actors_of_class` by exact class. The
result set also contains SpectatorPawn subclasses. In this DevKit,
`EditorLevelLibrary.spawn_actor_from_class` refuses to run during PIE and the
Python binding does not expose
`GameplayStatics.begin_deferred_actor_spawn_from_class`.

### Two-player listen-server authority proof

PIE was configured for two players, `PIE_ListenServer`, one process, and no
separate server. This produced:

- `UEDPIE_0`: a listen-server world with one local authoritative controller and
  one remote authoritative controller;
- `UEDPIE_1`: a client world with one local non-authoritative controller and a
  separate `Client 1` preview window.

Two isolated inputs exposed both failure modes of possession-based camera
movement:

1. F10 in the listen-host viewport made both server-side director components
   react. The server spawned `BP_EDD_DroneCamera_C_0` and `_C_1`, and only the
   local listen-host controller possessed `_C_1`; the remote server controller
   remained unpossessed. Component instances are incorrectly sharing global
   Player Controller 0 instead of resolving their owning local controller.
2. After a clean restart, F10 in the dedicated `Client 1` preview invoked only
   the `Client 1` director. It spawned one drone in `UEDPIE_1`; `UEDPIE_0` had
   no drone, proving the actor was correctly client-local. However, the client
   controller remained unpossessed because `PlayerController.Possess` requires
   authority.

This is an architectural acceptance result, not an intermittent bug. Cinematic
camera state is local presentation state and should not be server-authoritative
or replicated. Production movement therefore uses explicit delta-time actor
transform integration and local view-target switching, without possessing the
drone. Director logic must resolve its owning Player Controller and execute
only when that owner is local; it must not call global Player Controller 0 from
every server-side component instance.

For repeatable testing, the PIE settings persisted as:

```ini
bLaunchSeparateServer=False
PlayNetMode=PIE_ListenServer
RunUnderOneProcess=True
PlayNumberOfClients=2
```

The remote client is a separate top-level window titled
`Conan Exiles Enhanced Preview [NetMode: Client 1]`; focus that window before
sending F10/F9.

### Accepted two-player local-view and transform backend

The possession failure above was replaced and retested in the same two-player
listen-server topology. To remove Conan's character-creation flow as a source of
camera, input, and pawn ambiguity, the acceptance fixture spawned two exact
`/Script/Engine.DefaultPawn` instances in the server world and possessed one with
each authoritative controller:

- server Player Controller 0: `DefaultPawn_0` at `(1000, 0, 700)`;
- server Player Controller 1: `DefaultPawn_1` at `(1500, 500, 800)`;
- remote client: replicated `DefaultPawn_0` as its controlled pawn and initial
  view target.

The accepted Blueprint backend makes four contracts explicit:

1. Every client-director Tick first checks
   `GetOwner() == GetPlayerController(0)`. False terminates with no input or
   lifecycle work; true continues into F10/F9 and movement dispatch.
2. `SwitchToDroneView` and `ExitDroneMode` change only the local view target.
   Neither path calls `Possess`, `UnPossess`, or a possession helper.
3. `ApplyTranslationInput` forms `(W-S, D-A, E-Q)`, scales that local vector by
   `BaseMoveSpeed`, scales again by `GetWorldDeltaSeconds`, and performs one
   `AddActorLocalOffset` with sweep and teleport both false.
4. `BP_EDD_DroneCamera.ReceiveBeginPlay` calls `SetReplicates(false)` followed by
   `SetReplicateMovement(false)`. This is required even when the intended class
   defaults are false: spawned `SpectatorPawn` instances otherwise reported both
   inherited replication flags as true.

The focused acceptance sequence then proved:

- Host F10 produced exactly one server enter sequence. Player Controller 0 kept
  controlling `DefaultPawn_0` while viewing its local drone; Player Controller 1
  kept controlling and viewing `DefaultPawn_1`. The remote client stayed on
  `DefaultPawn_0`. The server contained one drone with `replicates=False` and
  `replicate_movement=False`; the client contained zero drones.
- In the immediately preceding run, holding host W for approximately 1.2 seconds
  moved the authoritative drone by approximately 721.8 units, consistent with
  the configured 600 units/second. It also moved the inherited client replica,
  exposing the replication-default defect that the BeginPlay override fixed.
  Host F9 restored the exact `DefaultPawn_0` view target and left its controlled
  pawn unchanged.
- Client 1 F10 produced exactly one client enter sequence. The client created one
  local non-replicated drone at `(1500, 500, 800)` while the server retained only
  its inactive host-local drone. Both server controllers remained on their own
  `DefaultPawn` instances.
- Holding client W for approximately 1.2 seconds moved the client drone from
  X `1500` to `2221.485720`; the host drone remained exactly at `(1000, 0, 700)`.
- Client F9 restored `DefaultPawn_0` as both controlled pawn and view target.

No Blueprint runtime error or `Accessed None` occurred. Taken together, the
pre-fix speed probe and final post-fix isolation run prove host/client input
isolation, non-replicated local cameras, frame-rate-independent movement on the
non-authority client, unchanged possession, and exact view restoration. It
does not replace the remaining dedicated-server, cooked-runtime, concrete Conan
character, or abnormal-lifecycle acceptance gates.

## First local mouse-look slice

`BP_EDD_DroneCamera.ApplyRotationInput` is a reviewed nine-node function with a
narrow contract:

1. Resolve Player Controller 0 and sample `GetInputMouseDelta` once.
2. Multiply DeltaX by `LookSensitivity` for yaw.
3. Multiply DeltaY by the negated sensitivity for pitch.
4. Keep roll exactly zero.
5. Apply the resulting rotator once with `AddActorLocalRotation`; sweep and
   teleport are both false.

`LookSensitivity` defaults to `0.12` degrees per mouse unit. Mouse delta is not
scaled by frame delta because it is already a per-frame accumulated input
quantity. The active client Tick now executes `ApplyTranslationInput` and then
`ApplyRotationInput` on the same validated, client-local camera reference. The
function and client Event Graph compile with `Good to go`; their exported
snippets contain 9 nodes/32 pins and 31 total nodes/111 pins respectively.

The focused two-player listen-server run reused the exact deterministic
`DefaultPawn` fixture above. Host entry created only the server-world local
drone at `(1000, 0, 700)`. Its yaw changed from `-179.999893` to
`-178.880084` while the remote world contained no drone, and F9 restored
`DefaultPawn_0` as both controlled pawn and view target. Remote-client entry
then created only its own non-replicated drone at `(1500, 500, 800)` while the
host drone remained unchanged; remote F9 again restored the exact
`DefaultPawn_0` view. There was no Blueprint runtime error or `Accessed None`.

That run proves the compiled host rotation dispatch, owner-local world
separation, unchanged possession, and exact restoration. It does **not** claim a
remote-client raw-mouse or runtime pitch proof: Windows cursor/message synthesis
did not reach the detached preview's raw-input channel. The exported reciprocal
pin topology proves both pitch and yaw wiring structurally; actual remote-client
pitch/yaw feel remains a hands-on acceptance item.

## Smooth speed-control slice

`BP_EDD_DroneCamera.UpdateSpeedControls` now owns a narrow, ordered contract:

1. Sample `MouseWheelAxis` and compute a symmetric proportional factor as
   `Exp(Loge(SpeedTrimRatio) * wheel)`, so opposite wheel steps multiply and
   divide by the same ratio.
2. Multiply the existing `CruiseMoveSpeed`, clamp the result between
   `MinMoveSpeed` and `MaxMoveSpeed`, and persist it.
3. Select normal cruise or Shift boost, then wrap that selection in the Ctrl
   precision selector so precision wins if both modifiers are down.
4. `FInterpTo` from `CurrentMoveSpeed` to the selected target with world delta
   seconds and `SpeedResponse`, then persist current speed.

The active client tick executes speed, translation, then rotation on the same
validated local drone. Translation consumes `CurrentMoveSpeed`, not the legacy
base value.

The first PIE attempt exposed a real graph defect that compile/save could not:
the clamp's `Value` pin was unlinked, so both cruise and current speed fell from
600 to the 30-unit minimum immediately. The pin was repaired, the graph compiled
green, and the offline graph contract now requires the exact
trim-multiply-to-clamp link so this failure cannot silently return.

The clean two-player listen-server rerun reused the deterministic `DefaultPawn`
fixture and proved:

- initial cruise/current values remained exactly `600/600`;
- a short Shift sample produced `CurrentMoveSpeed=1427.38`, proving a smooth
  intermediate rather than a snap, and sustained Shift reached `1799.42`;
- Ctrl reached `150.79`; Ctrl+Shift converged toward the same precision target,
  proving precision precedence;
- one second of W moved about 610 units normally, 1643 while boost ramped, and
  221 while precision ramped;
- remote-client boost reached `1798.22` and moved only the client drone; the
  host drone remained exactly at its pre-client transform;
- host and client F9 each restored the exact original controlled pawn and view
  target, with no `Blueprint Runtime Error` or `Accessed None`.

Windows `mouse_event` and posted `WM_MOUSEWHEEL` messages did not reach the PIE
mouse-input channel, matching the raw-mouse automation limitation found during
look testing. Wheel behavior is therefore structurally validated—including the
clamp link and multiplicative inverse topology—but physical wheel feel remains a
hands-on acceptance item.

## Smooth manual-roll and horizon-lock slice

`BP_EDD_DroneCamera.ApplyRollAndHorizonInput` implements manual bank and smooth
horizon stabilization as one ordered contract:

1. Sample analog-compatible C and Z values from local Player Controller 0.
2. Form the signed axis as `C - Z` and multiply by `ManualRollSpeed` (default
   90 degrees/second).
3. Ease persisted `CurrentRollSpeed` toward that target with `FInterpTo`, world
   delta seconds, and `RollInputResponse` (default 8).
4. Multiply the post-write speed by the same world delta seconds and construct
   one roll-only actor-local delta.
5. Edge-toggle `HorizonLockEnabled` with H. Test held C and Z separately so
   either manual command wins even when the signed analog axis cancels to zero.
6. With neither manual key held, use the mode flag to choose between preserving
   bank through the local-delta path and stabilization through an absolute
   world-rotation path.
7. Build the level target from current actor forward and an explicit `(0,0,1)`
   world-up vector, then `RInterpTo` from current actor rotation using world
   delta seconds and `HorizonLockResponse` (default 4).

The first live paste compiled but a round-trip inspection found that the
existing function entry had no reciprocal execution link into the pasted body.
After connecting entry to the first H-toggle branch, the complete graph
compiled and saved again. Its accepted export contains 33 nodes and 116 pins;
offline contracts require both sides of that entry link, every input and
arbitration edge, the manual interpolation/integration path, and the complete
world-up stabilization path.

A later round-trip check caught a subtler generator defect: the intended Z=1
world-up value had been written into `AutogeneratedDefaultValue`, leaving the
actual pin default at zero. Unreal's math fallback happened to level the camera,
but that accidental behavior was rejected. The generator now writes
`DefaultValue="1.0"`; the compiled live export round-trips with actual Z=1 and
the contract asserts X=0, Y=0, Z=1 explicitly.

The corrected deterministic two-player PIE run proved:

- host baseline roll and current speed were exactly `0/0`;
- 800 ms of C produced roll `+71.774486` and release speed `+9.297104`, then
  decayed to `0.000179` while the bank remained at `+72.808385`;
- 800 ms of Z produced the opposite speed `-10.302718` and returned roll to
  `+2.337553`, then decayed to `-0.000198` at roll `+1.195201`;
- Client 1 independently reached roll `+71.267128` and speed `+13.433919`
  while the host drone remained exactly at roll `+1.195201` and speed `0`;
- host and client F9 each restored `DefaultPawn_0` as both controlled pawn and
  exact view target.

Pressing C/Z also exercises Conan's base `FunCombat_PlayerController`, which
reports `Accessed None` when the test controller possesses a minimal
`DefaultPawn` with no Conan character. The logged source is the base controller,
not `BP_EDD_DroneCamera` or `BPC_EDD_ClientDirector`; this is known synthetic
fixture contamination. A concrete created-character pass remains required.

The completed deterministic two-player proof additionally showed:

- H changed the client lock state from true to false and back exactly once per
  press;
- with lock disabled, an approximately 74-degree bank persisted after
  `CurrentRollSpeed` reached zero;
- enabling lock visibly eased roll from `73.652472` through `25.235981` to
  `0.001760` rather than snapping;
- the corrected explicit-world-up build took seeded pitch/yaw/roll
  `20/45/60` through `20/45/20.935211` to `20/45/0.001354`, proving pitch and
  yaw preservation;
- host bank reached `74.759562` with lock disabled while the client remained at
  its independent `20/45/~0` orientation and lock state;
- host and client F9 restored their exact original controlled pawn and view
  target.

As in the manual-roll proof, C/Z also exercises Conan's base
`FunCombat_PlayerController`; the only runtime errors came from its missing
Conan-character assumption in the synthetic `DefaultPawn` fixture. No EDD
Blueprint produced a runtime error. The corrected explicit-world-up rerun used
directly seeded rotation and completed without that fixture contamination.

## First atomic waypoint capture (2026-08-09)

The first authoring-data slice is implemented in
`BPC_EDD_ClientDirector.CaptureCurrentWaypoint`. The Enhanced editor Python API
can create typed Blueprint arrays, including native `Transform[]`, but does not
expose user-defined-struct field authoring. `ST_EDD_Waypoint` therefore remained
an empty scaffold at this checkpoint; its later authored bridge is recorded
below. The accepted transitional draft contract uses six
component-owned lockstep arrays:

- `DraftWaypointIds` (`Integer[]`)
- `DraftWaypointTransforms` (`Transform[]`)
- `DraftWaypointFocalLengths` (`Float[]`, serialized here as real/double)
- `DraftWaypointApertures` (`Float[]`, real/double)
- `DraftWaypointFocusDistances` (`Float[]`, real/double)
- `DraftWaypointHoldSeconds` (`Float[]`, real/double)

`NextWaypointId` begins at 1. The initial 24-node/86-pin capture function
validated the typed `DroneCameraRef`, appended every channel through one
uninterrupted exec chain, set the incremented ID only after all six appends, and
then emitted
`[EDD] Waypoint captured`. Hold time defaults to zero. Focal length, aperture,
and manual focus distance currently come from authored drone variables whose
verified class defaults are 35, 2.8, and 1000. The final lens-control slice must
keep those values synchronized with the CineCamera component. The subsequent
selected-waypoint slice added one setter, making the current copied live graph
25 nodes/91 pins and selecting the exact index returned by the ID append.

The client EventGraph now has 37 total nodes/131 pins. After the existing local
owner, Drone Mode active, valid camera, speed, translation, mouse rotation, and
roll/horizon work, it polls local Player Controller 0 with
`WasInputKeyJustPressed(K)`. The true path calls `CaptureCurrentWaypoint`; the
false path terminates without mutation. Unreal resolved the self-call's function
GUID, compiled the asset with `Good to go`, and the copied live graph passed both
generic reciprocal-link validation and a dedicated semantic contract.

Focused two-player PIE used exact `DefaultPawn` fixtures so the unfinished Conan
character state could not alter possession or restoration. Two direct Blueprint
function calls captured seeded transforms at `(1111,222,888)` and
`(1444,-333,999)`. Acceptance results were:

- all six arrays progressed `0 -> 1 -> 2` together;
- IDs were exactly `[1,2]`, then `NextWaypointId` was 3;
- both transforms and all three lens channels matched their capture-time values;
- both hold values were zero;
- the remote client's six arrays remained empty and its world contained no host
  drone;
- exit restored the exact original controlled pawn and view target;
- no EDD Blueprint runtime error or `Accessed None` occurred.

The active character-creation widget consumed synthetic Windows `K` events even
after the deterministic pawn fixture and game-only input mode were installed.
Do not claim an automated K-input runtime pass from this run. The function is
runtime-proven and the K-edge graph is structurally proven; one physical K press
after completing character creation remains the hands-on acceptance gate. It is
safe to complete character creation in PIE, but automated tests should keep the
fixture because character/profile state may differ across PIE worlds or fresh
saves.

Reusable tools added with this slice:

- `Configure-WaypointCapture.py` for idempotent variables/defaults/function setup;
- `Build-WaypointCaptureGraph.py` and `Build-ClientWaypointDispatch.py` for
  deterministic graph composition;
- `Test-WaypointCaptureContracts.py` for exact data/exec topology;
- `Validate-WaypointCapturePIE.py` for phased deterministic runtime inspection.

## Selected-waypoint replace/delete slice (2026-08-09)

`BPC_EDD_ClientDirector` now owns `SelectedWaypointIndex`, defaulting to `-1`.
Capture assigns the exact index returned by the ID-array append before advancing
`NextWaypointId`. Replacement first validates both `DroneCameraRef` and the
selected ID index, then writes transform, focal length, aperture, and manual
focus distance with `Array_Set` and `bSizeToFit=false`; stable ID and hold are
unchanged. Deletion removes the selected element from all six arrays in one exec
chain, then preserves the old index if it still exists or selects
`Length(IDs)-1`, which naturally becomes `-1` when the draft is empty.
The copied live graphs are capture 25 nodes/91 pins, replace 21 nodes/76 pins,
and delete 21 nodes/72 pins.

The first runtime attempt exposed an important clipboard boundary: a pasted
body can retain a textual link to `K2Node_FunctionEntry_0` while the native
entry's own `then` pin remains unlinked. The graph looks connected when the
nodes overlap and compiles without an error, but calling the function is a
no-op. Each live function was rebuilt with the native entry moved clear and
manually wired. The copied live graphs then passed contracts that require the
reciprocal link and the exact native entry pin identifiers.

The corrected deterministic two-player edit cycle reported all of the
following as true: replacement values, deletion with a survivor, deletion to an
empty draft, invalid-index no-op, remote-client isolation, original pawn/view
restoration, and restoration of the temporary drone class lens defaults. No EDD
Blueprint runtime error appeared.

The live EventGraph subsequently advanced through the 43-node K/R/Delete slice
to a 51-node/200-pin feedback slice. Real F10, K, R, Delete, and F9 input passed
PIE acceptance. The feedback build's real K press emitted both the existing
capture diagnostic and `[EDD] Draft waypoints: 1 | selected: 0`. A dedicated
semantic test requires the shared count/selection chain after capture, replace,
and delete, so the same message topology is not inferred from node count.

The first generated feedback graph revealed why compiled round-trip validation
is mandatory: its non-empty string values were incorrectly also marked as the
pins' autogenerated defaults. Unreal reconstructed the function nodes and
discarded the labels while still compiling successfully. The generator now
records an empty autogenerated default and a distinct explicit `DefaultValue`;
both labels survive paste, compile, save, copy, and contract validation.

The PIE Python bridge could read the authored lens values but would not write
those exposed properties reliably on the spawned drone instance. The accepted
replacement fixture therefore exits Drone Mode, temporarily changes the drone
Blueprint class defaults, re-enters to spawn a camera with those values, calls
replace, and restores the original `(35, 2.8, 1000)` defaults in `finally`.
Runtime tests that touch class defaults must always log the restored values and
must not leave an editor package dirty with temporary test data.

## PIE character persistence correction (2026-08-10)

`AlmostEmpty` initially logged `Couldn't find a Character Creation Actor` and
started character creation for both temporary PIE controllers. Enhanced 1.2.0
now resolves the character-creation actor through the Region Data Table tag; a
persistent actor in a custom map must carry the matching tag. The installed
assets are `/Game/Base/AlwaysCook/RegionDataTable` and
`/Game/UI/Widgets/CharacterCreation/Actors/CharacterCreationActor`.

Do not generalize the initial broken flow into “the DevKit recreates a character
every run.” After the disposable character completed and saved, the next
two-player PIE restart entered normal gameplay directly with
`BasePlayerChar_C_0`; F10/K physical acceptance then ran without recreating the
profile. A lightweight EDD validation map with the correct actor/tag remains a
useful hardening task for fresh databases, but it is not required for every
iteration on the current saved test profile.

Sources checked for this behavior:

- <https://conanexiles.fandom.com/wiki/Modding>
- <https://forums.funcom.com/t/conan-devkit-simulation-broken/106990>
- <https://forums.funcom.com/t/conan-exiles-enhanced-june-patch-1-2-0/299576>
- <https://dev.epicgames.com/documentation/unreal-engine/play-in-editor-multiplayer-options-in-unreal-engine>

Operationally, only one DevKit editor instance may own these assets. Never sync
`.uasset` files into or out of the content tree while Unreal is open. After a
verified slice: stop PIE, compile/save, close Unreal, wait for
`LogExit: Exiting.`, then run `Sync-DevKitContent.ps1 -Direction FromDevKit`.
This ordering is part of the asset-integrity contract, not housekeeping.

## Absolute-time linear playback kernel (2026-08-10)

`BPC_EDD_ClientDirector` now contains compiled `StartLinearPlayback`,
`UpdateLinearPlayback`, and `StopLinearPlayback` functions. Start requires at
least two captured transforms, a positive per-segment duration, and a valid
local drone, then snapshots `GetGameTimeInSeconds` and places the drone exactly
at waypoint zero. Update computes `elapsed = now - start`, derives segment index
and local alpha from a fixed three-second segment duration, uses transform
`TLerp` in `QuatInterp` mode, writes the exact final endpoint, and clears active
state only through an explicit stop. It does not use frame delta or integrate
the prior pose. Completion deliberately holds the exact final frame until that
stop so inactive camera effects cannot alter the authored endpoint.

The live compiled round-trips contain 17/67, 34/126, and 3/16 nodes/pins. The
first paste proved that authored numeric defaults must retain the engine's
original `AutogeneratedDefaultValue`: marking `2` and `0.001` as autogenerated
caused Unreal to reconstruct both back to zero. The corrected generator changes
only the explicit `DefaultValue`, and the values survive paste, compile, save,
copy, and semantic validation. The functions were initially landed without
dispatch so their contracts could be validated independently before changing
the live tick route.

## Linear playback dispatch and exit cleanup (2026-08-10)

The client EventGraph now contains 62 total nodes: 61 executable nodes and the
existing design comment. A P edge enters a dedicated start/stop branch. A tick
without P reads `PlaybackActive`: active playback calls only
`UpdateLinearPlayback`, while inactive playback continues through speed,
translation, rotation, roll, and K/R/Delete authoring. Starting or stopping on
P terminates that tick, so the newly changed state cannot also update movement.

All three EventGraph exit callers now execute a distinct
`StopLinearPlayback` call first: normal F10 exit, manual F9 emergency exit, and
automatic invalid-camera recovery. The generated graph, clean Unreal compile,
and copied 62-node/235-pin Unreal round-trip pass generic reciprocal-link,
waypoint authoring, mutation-feedback, and playback-dispatch contracts.

Two automation defects were found before the asset was saved. First, the old
handoff recorded the normal exit as `K2Node_CallFunction_4`; the current graph
correctly resolves the unique `ExitDroneMode` call because node 4 is Boolean
NOT. Second, reusing the feedback generator's deterministic UUID stream caused
pin collisions in cloned nodes. The playback dispatcher now owns a distinct
deterministic UUID namespace and rejects collisions with every identifier in
the source graph. Finally, generated additions must be emitted from the
post-wiring block map, not the original clone map, or only the modified legacy
nodes retain reciprocal links.

The deterministic two-player PIE gate is complete; the acceptance evidence and
the completion-policy correction are recorded below. Cook and Workshop remain
deferred to an attended session.

### Runtime correction and acceptance

The first completion policy above did not survive runtime acceptance. Clearing
`PlaybackActive` immediately returned the camera to the inactive manual-flight
path, whose default-enabled horizon lock pulled the authored 30-degree final
roll down to roughly 16.52 degrees. The corrected contract keeps playback active
and rewrites the exact endpoint every tick until explicit P/stop. This is an
intentional final-frame hold, not a stalled completion. It prevents horizon
lock, residual input, or future inactive-path effects from competing with the
authored last frame.

The final compiled Start/Update/Stop round-trips contain 17/67, 34/126, and
3/16 nodes/pins. Update contains no completion write to `PlaybackActive` and no
completion print that would spam on every hold tick. P, all three exit routes,
and `StopLinearPlayback` remain the explicit ownership-release paths.

A deterministic two-player PIE driver then exercised the production F10 entry
route and passed every required marker: empty-draft and single-waypoint no-op,
initial snap, absolute-time in-flight sample (`elapsed=1.006`, `segment=0`,
`alpha=0.335`), exact completion endpoint hold, restart snap, explicit stop,
remote-client isolation, and unchanged possession plus view restoration. The
run ended with `AUTOMATIC_RESULT:PASS` and cleanly tore down both PIE worlds.

The automation itself established several reusable DevKit rules:

- Directly calling `EnterDroneMode` is insufficient for dispatch tests because
  the real F10 dispatcher owns `DroneModeActive`; acceptance must enter through
  that production route.
- A remote PIE controller can legitimately have no pawn during login. Tests
  must preserve and compare the exact original state rather than inventing a
  non-null requirement.
- Blueprint component instance properties are not a dependable editor-Python
  control surface. The driver instead samples live state in phased Slate
  post-tick callbacks using real game time.
- Sleeping or injecting editor-console commands while PIE owns focus is brittle.
  Arming before PIE and letting the post-tick driver phase and end the run keeps
  the game thread and UI responsive.

The deterministic PIE gate recorded above is complete. The next autonomous
gate is promotion of transient waypoint storage toward explicit document
structures plus visible path preview, serialization, and undo/redo. Cook and
Workshop remain deferred to an attended session.

## First authored waypoint struct bridge (2026-08-10)

The Enhanced 5.6 Python API can create a `UserDefinedStruct` and obtain its
`EdGraphPinType`, but it exposes neither `FStructureEditorUtils` nor the struct's
editor data/variable descriptions. The earlier symbol probe was therefore
correct: field authoring requires the User Defined Structure editor UI. The
reliable UI sequence is select the member row, rename inline, open the pin-type
picker, filter, and click the filtered result; pressing Enter in the filter does
not consistently choose the result.

`ST_EDD_Waypoint` now contains the lossless migration subset matching the six
runtime-proven channels:

- `WaypointId` — Integer
- `CameraTransform` — Transform
- `FocalLength` — Float
- `Aperture` — Float
- `ManualFocusDistance` — Float
- `HoldSeconds` — Float

`Configure-WaypointDocumentBridge.py` then added `DraftWaypointsV1` as an array
of that exact user-defined struct on `BPC_EDD_ClientDirector`. Unreal compiled
and saved the client asset, verified the generated array default is empty, and
a second run logged `VARIABLE_ALREADY_PRESENT`, `EMPTY_TYPED_ARRAY_VERIFIED:0`,
and `COMPLETE:True`. This proves the authored struct is a valid Blueprint member
type and the configurator is idempotent.

The typed array is intentionally unwritten. Capture, replacement, deletion, and
playback still use the validated legacy arrays, so there is one authoritative
runtime model and no silent divergence. The next gate is a bounded
`SyncDraftWaypointsV1` function that clears and rebuilds the typed array from all
six channels, followed by mutation and round-trip parity tests. Only after that
passes may later code read the struct array as document state.

## Live typed-waypoint sync bridge (2026-08-10)

`SyncDraftWaypointsV1` is now a compiled function on
`BPC_EDD_ClientDirector`. Its five exact integer-equality guards compare the ID
array length with transform, focal, aperture, focus-distance, and hold lengths.
No mutation is reachable until all five pass. The valid path clears
`DraftWaypointsV1`, iterates IDs in source order, reads every other channel with
the same array index, makes `ST_EDD_Waypoint`, and appends exactly once.
Mismatch paths emit a channel-specific diagnostic and preserve the prior typed
snapshot.

The source is reproducible through `Build-WaypointStructSyncGraph.py`; the
40-node full graph and 39-node paste body pass
`Test-WaypointStructSyncContracts.py`. The paste body intentionally has no
external entry reference. Enhanced Unreal strips a link to an unselected native
function entry, and a one-sided serialized link can compile green as an
unreachable no-op. The reliable sequence is paste the unlinked body, draw the
single native entry-to-first-Branch wire, compile, then copy the complete graph
back out. The live round-trip passed the same reciprocal semantic contracts.

An automatic production-path PIE probe first rebuilt an empty draft, entered
Drone Mode, moved the real local drone twice, invoked the existing capture
function twice, and then called the sync function. It verified both struct IDs,
transforms, focal lengths, apertures, focus distances, and hold values exactly
against the six captured arrays. A second sync produced byte-identical exported
struct values, and exit restored the camera. The final marker was
`EDD_WAYPOINT_STRUCT_PIE:AUTOMATIC_RESULT:PASS`.

PIE Python cannot write Blueprint component instance arrays; Unreal rejects the
operation as non-editable. At this checkpoint the mismatch-preserves-prior
behavior was therefore proved by complete graph topology and the pure document
oracle rather than by mutating a live instance from Python. Positive-ID,
uniqueness, and finite/scalar-domain checks were the next bounded live slice.

## Mutation-integrated typed waypoint parity (2026-08-10)

`CaptureCurrentWaypoint`, `ReplaceSelectedWaypoint`, and
`DeleteSelectedWaypoint` now call `SyncDraftWaypointsV1` on every successful
mutation path before emitting feedback. Delete has two successful outcomes, so
its surviving-selection and repaired-selection branches each own an explicit
sync call. Invalid index paths remain mutation-free no-ops.

The three graph builders now clone and retarget a native self-call form, and
their semantic tests assert exact execution placement. Paste artifacts omit the
native function entry deliberately; after paste, the single entry wire is drawn
in the editor. Each live function compiled `Good to go`, was saved, copied back
from Unreal, and passed the same capture/edit contracts as its generated source.

`Validate-WaypointCapturePIE.py` now has an automatic `arm_edit_cycle` phase and
field-resilient typed parity checks. The real Blueprint path captured two drone
states, replaced the selected state, deleted to one survivor, deleted to empty,
and exercised invalid delete/replace calls. After every step it compared typed
ID, transform, focal length, aperture, focus distance, and hold time against the
six legacy channels. All assertions passed and the run ended with
`EDD_WAYPOINT_PIE:AUTOMATIC_RESULT:PASS`. This editor session exposed one PIE
world, so the optional client-isolation branch reported `SKIPPED`; prior
two-player authoring acceptance remains the isolation evidence.

The typed array was therefore a validated synchronized projection of every live
authoring mutation. Full preflight parity was the remaining gate before it
could become the authoritative read-side document snapshot.

## Full typed-waypoint preflight parity (2026-08-10)

`SyncDraftWaypointsV1` now reaches the complete version-1 document-oracle
boundary. After the six channel-length guards succeed, it sets a local
`WaypointPreflightValid` accumulator, scans every source index without mutating
the prior typed snapshot, and rejects:

- IDs less than one;
- duplicate IDs, using `Array_Find(CurrentId) == CurrentIndex`;
- non-finite focal length, aperture, focus distance, or hold time;
- focal length or aperture less than or equal to zero; and
- focus distance or hold time less than zero.

The finite check is Blueprint-safe and deterministic: `Value - Value == 0` is
true for finite values and false for NaN and both infinities. Every failing
branch clears the accumulator. Only the scan's completed path reads that
accumulator; rejection prints a diagnostic and leaves `DraftWaypointsV1`
untouched, while success clears and rebuilds it in a second ordered loop. Empty
drafts remain valid.

`Build-WaypointStructSyncGraph.py` now deterministically generates the complete
84-node/362-pin graph (83-node paste body). The checked-in snippet, generated
full graph, live pre-compile copy, and post-compile Unreal round-trip all pass
generic reciprocal-link validation and the expanded semantic contract. The
native function entry must still be wired after paste: zoom into the tiny entry
and first Branch, draw the pin connection, then copy the full graph back out;
the serialized contract is the acceptance check. The final Blueprint compiled
`Good to go` and saved successfully.

Two corrected automatic PIE runs passed on the compiled asset. The struct-sync
run proved empty rebuild, exact two-waypoint field mapping, idempotence, and
restoration, ending with
`EDD_WAYPOINT_STRUCT_PIE:AUTOMATIC_RESULT:PASS`. The production mutation run
proved typed parity after capture, replacement, survivor/empty deletion,
invalid-edit no-ops, and restoration, ending with
`EDD_WAYPOINT_PIE:AUTOMATIC_RESULT:PASS`. The one-world profile explicitly
skipped its optional second-client branch; prior two-player acceptance remains
the isolation evidence. No EDD Blueprint runtime error occurred.

Python still cannot inject malformed values into these live instance arrays, so
invalid-domain runtime injection is not claimed. Rejection semantics are
covered by the full live graph topology/round-trip contract and the executable
pure oracle. With those boundaries explicit, `DraftWaypointsV1` is now the
authoritative read-side waypoint snapshot after each successful authoring
mutation; the six arrays remain transitional write-side channels until direct
typed mutation replaces them.

## Typed segment and Flypath document schema bridge (2026-08-10)

The version-1 Blueprint document boundary is now authored in the Enhanced
DevKit and mirrored in source control. `ST_EDD_Segment` has these exact ordered
fields and defaults:

- `SegmentId` — Integer, `0`
- `FromWaypointId` — Integer, `0`
- `ToWaypointId` — Integer, `0`
- `DurationSeconds` — Float, `3.0`
- `SpatialCurveType` — String, `linear`
- `TimeProfile` — String, `linear`

`ST_EDD_FlypathDocument` has these exact ordered fields and defaults:

- `SchemaVersion` — Integer, `1`
- `TrajectoryEngineVersion` — Integer, `1`
- `RevisionNumber` — Integer, `0`
- `RegionId` — String, empty
- `DurationSeconds` — Float, `0.0`
- `DefaultFlightProfile` — String, `cinematic_drone`
- `Waypoints` — Array of `ST_EDD_Waypoint`
- `Segments` — Array of `ST_EDD_Segment`
- `ContentHash` — String, empty

`tools/document/blueprint_v1_schema.json` is the deterministic source-side
contract. Its test locks the field order, names, types, containers, defaults,
and the two client bridge variables against the executable document oracle.
`Configure-FlypathDocumentBridge.py` adds `DraftSegmentsV1` and
`DraftDocumentV1` to `BPC_EDD_ClientDirector`, compiles and saves the Blueprint,
verifies safe empty/default construction, and is idempotent. A second run found
both variables already present and completed successfully.

The user-defined-struct editor has a dangerous row-selection trap: the type
picker overlays later rows, and clicking near its left-side search box can also
activate the type control underneath. The reliable procedure is to open the
picker, focus the far-right side of its search field, filter, click the result
text rather than its blue struct icon, and immediately verify the selected row
before changing the container. All eighteen authored field/type/container
choices and the non-empty defaults were visually rechecked before saving.
Binary token checks then confirmed the field names, nested struct references,
array/property metadata, and `linear`/`cinematic_drone` defaults in the synced
assets.

This milestone proves the typed storage boundary, not document population.
`DraftSegmentsV1` is empty and `DraftDocumentV1` is default-constructed by
design. The next function must build both transactionally from the validated
`DraftWaypointsV1` snapshot and preserve the prior document on rejection.

## Transactional document-sync seam and native node forms (2026-08-10)

`BPC_EDD_ClientDirector.SyncDraftDocumentV1` now exists as a compiled, saved
function seam. `Configure-DocumentSync.py` idempotently creates and verifies the
private scratch members used by the eventual graph:

- `DocumentSyncValidV1` (`Boolean`)
- `DocumentTotalDurationV1` (`Float`, double precision)
- `DocumentNextSegmentIdV1` (`Integer`)
- `DocumentMatchFoundV1` (`Boolean`)
- `DocumentUsedSegmentIdsV1` (`Integer[]`)
- `DocumentSegmentsScratchV1` (`ST_EDD_Segment[]`)
- `DocumentCandidateSegmentV1` (`ST_EDD_Segment`)

The commandlet was run twice. The first run created every member and function;
the second reported every item already present. Both runs compiled, saved,
verified defaults/empty arrays, and ended with `COMPLETE|True`. The function
body remains intentionally empty until the generated graph passes source-side
semantic contracts.

`tools/document/document_bridge.py` is the executable reconciliation oracle.
It preserves the ID, duration, spatial curve, and time profile of the first
valid unused prior segment whose exact `(FromWaypointId, ToWaypointId)` pair
survives. New adjacency IDs are strictly above the highest reusable prior ID;
invalid and duplicate candidates are repaired without recycling IDs. It also
validates the typed waypoint snapshot and editable document metadata, handles
the 32-bit Blueprint integer ceiling, recomputes waypoint holds plus segment
durations, preserves revision/region/default profile, clears `ContentHash`, and
returns deep value snapshots without mutating prior state. Nine unit tests pass.

The live editor was then used only to export native Make/Break forms for
`ST_EDD_Segment` and `ST_EDD_FlypathDocument`. Temporary nodes were undone and
the function returned to its empty compiled seam before the editor was closed
normally (`LogExit: Exiting.`). The four unlinked forms are checked in as
`document-sync-struct-node-forms.eddgraph`. Their contract test locks every
generated field-pin suffix and direction, both nested array element types, and
the exact defaults. One subtle native rule is now explicit: Unreal may omit a
`DefaultValue` token entirely for an empty String pin; absence and an explicit
empty value are semantically equivalent, while non-empty defaults remain exact.

The next bounded implementation step is the deterministic graph builder and
semantic graph test. Only after that generated graph matches the oracle will it
be pasted into the live function, compiled, copied back out, and PIE-tested.

## Live transactional document sync compile (2026-08-10)

`Build-DocumentSyncGraph.py` now emits a 124-node/552-pin complete function and
a 123-node/551-pin paste body. The semantic contract validates reciprocal
links, every input's single-source invariant, output-to-input direction on all
internal edges, typed waypoint preflight, prior-segment matching, integer ID
exhaustion, monotonic ID allocation, duration accumulation, metadata carryover,
and the final atomic publication boundary.

The first live paste exposed three UE 5.6 integration details that source-only
shape checks did not catch:

- integer Max reconstructs as a native
  `K2Node_CommutativeAssociativeBinaryOperator` with `MemberName="Max"`, not
  necessarily the legacy `Max_IntInt` call-function form;
- the pure increment output must feed only the next-ID setter. The setter's
  committed `Output_Get` must fan out to both Make Segment and the used-ID
  append. Otherwise Unreal re-evaluates the pure increment after the setter has
  mutated its source variable, producing segment ID `2` while the stored counter
  remains `1`;
- the new segment duration accumulator must consume its own unlinked
  three-second default. Connecting the Make node's duration input to that input
  creates the same illegal direction error. UE serializes the corrected `3.0`
  value as `3.000000`.

The generator and validator were corrected first, then the same two links were
repaired in the live function. A freshly copied live export passes generic
validation at exactly 124 nodes/552 pins and the complete semantic contract.
Unreal compiled `BPC_EDD_ClientDirector` successfully in 140 ms with `Good to
go`; the asset was saved, the editor closed normally through
`LogExit: Exiting.`, and the 1,223,325-byte component was synced back into Git.

One tooling boundary is now explicit: `Export-BlueprintGraphClipboard.ps1`
only reads the current Windows clipboard. It does not focus Unreal or issue
Select All/Copy. During repair, a syntactically valid stale copy initially made
an already-broken pin appear unchanged in the exported evidence. The safe loop
is graph focus, Ctrl+A, Ctrl+C, export, generic validation, semantic validation,
then compile/save. Visual appearance alone is not acceptance evidence.

This milestone is compile/round-trip proof, not runtime proof. The next bounded
gate is a deterministic production-path PIE validator covering empty, single,
and multi-waypoint documents, stable repeat sync, preserved authored segments,
rollback on invalid input, and camera cleanup.

## Transactional document-sync runtime acceptance (2026-08-10)

`Validate-DocumentSyncPIE.py` now provides the deterministic production-path
runtime gate. The initial executions found two defects that source-shape and
compile checks could not expose:

- Unreal reconstructed the live schema-version and trajectory-engine equality
  constants as `0`, so every transaction stopped at metadata guard 1. Both live
  constants were repaired to `1`, and the semantic graph contract now locks
  schema `1`, engine `1`, revision floor `0`, and transaction next-ID `0`.
- A pure integer increment was connected to the setter, Make Segment, and the
  used-ID append. Pure Blueprint nodes are evaluated per consumer, so the setter
  committed `1` and the later consumers re-evaluated against the mutated source
  to obtain `2`. The increment now feeds only the setter; both consumers use the
  setter's committed `Output_Get`. The generated graph, fresh live clipboard
  export, and semantic validator all enforce this topology.

The final acceptance uses three clean PIE component constructions. Phase one
starts empty, captures two exact drone poses through `CaptureCurrentWaypoint`,
and proves empty/single/two-waypoint parity, segment ID `1`, endpoints `1 -> 2`,
the three-second default, total duration, and repeat-sync idempotence. Phase two
reconstructs a real component with an authored `7.25` second segment using
`catmull_rom` and `ease_in_out`; sync preserves every segment field plus revision
`12`, region `runtime_test`, and default profile `fpv`, clears the stale content
hash, and recomputes total duration. Phase three deliberately shortens one of
the six authoritative waypoint channels; waypoint preflight rejects it and the
typed waypoint snapshot, segment array, and complete document remain unchanged.

The private runtime members were not made Instance Editable for the test.
Instead, the harness deep-copies class defaults, seeds the complete authoritative
source state between PIE phases, constructs the normal game-attached component,
and restores every source/typed/document default in a `finally`-protected path.
It verifies restoration before reporting success. The final signals were:

- `PRESERVED_AUTHORED_SEGMENT_VALID:True`
- `INVALID_INPUT_ROLLBACK_VALID:True`
- `CLASS_DEFAULTS_RESTORED:True`
- `AUTOMATIC_RESULT:PASS`

The probe-dirty editor session was closed with Don't Save after restoration and
reached `LogExit: Exiting.` The repository retains the earlier compiled/saved
asset rather than any temporary test defaults. The next autonomous product slice
is visible path preview from the accepted typed document, followed by draft
undo/redo; cook/Workshop remains an attended release gate.

## Pooled path-preview seam (2026-08-10)

The pre-existing `BP_EDD_PathPreview` was a non-replicated shell containing only
`PreviewEnabled`, an empty EventGraph, and a `PathSpline` component. A spline
component alone does not provide reliable in-game rendering, and development
debug-draw nodes are not an acceptable cooked-product dependency.

`Configure-PathPreview.py` now creates and verifies a typed
`PreviewDocumentV1`, `MarkerScaleV1=0.20`, `LineThicknessV1=0.03`, and
`SourceCubeExtentV1=100.0`, plus empty `ClearPreviewV1` and `RebuildPreviewV1`
function seams. It adds exactly one movable, shadowless, no-collision HISM sphere
pool (`WaypointMarkersV1`) and one equivalent cube pool (`SegmentLinesV1`) using
the Engine basic-shape meshes. The actor remains non-replicated and cannot be
damaged. A second commandlet execution reused every variable, function, and
component and completed successfully, proving idempotence.

`tools/preview/linear_preview.py` defines the source-side geometry contract.
Markers retain document order and world position. Each non-degenerate linear
adjacency becomes one cube centered at the midpoint, rotated from local +X to
the segment direction, scaled along X by `length / 100`, and given the fixed Y/Z
thickness. Degenerate adjacencies keep their waypoint markers but emit no line.
Seven tests cover empty/single/multi-point paths, vertical orientation,
determinism, zero-length suppression, and invalid geometry/style values.

`ClearPreviewV1` is now a compiled and saved native Blueprint body. Its exact
execution contract is:

1. clear every instance from `WaypointMarkersV1`;
2. then clear every instance from `SegmentLinesV1`;
3. return without changing the typed preview document.

The fresh live export contains five nodes and 11 pins. It passed the generic
reciprocal-link validator and a dedicated semantic contract that binds each
`ClearInstances` target to the correct HISM getter and requires the exact
entry-to-waypoint-to-segment execution chain. The asset compiled `Good to go`,
saved without a dirty marker, the editor exited through `LogExit: Exiting.`, and
the DevKit mirror was synced only after that clean exit.

Desktop graph automation on the 4K editor must explicitly opt into DPI-aware
coordinates. A first unsaved drag landed on `PathSpline` instead of
`WaypointMarkersV1`; immediate visual inspection caught it, the node was undone,
and no incorrect graph was saved. Every subsequent node and wire was verified by
screenshot and finally by a fresh clipboard export. This is now the required
procedure for attended native-node authoring.

This is clear-path structural proof, not visible runtime proof. The next bounded
gate is the `RebuildPreviewV1` body, followed by direct PIE instance-count and
transform validation before any client-director lifecycle integration.

### Typed waypoint marker rebuild and runtime proof

`RebuildPreviewV1` now contains a compiled and saved 14-node/60-pin first
rendering slice. Its execution contract is clear, then enabled guard, then typed
waypoint loop. `PreviewDocumentV1` feeds the native
`ST_EDD_FlypathDocument` break; its waypoint array feeds `ForEachLoop`; each
native `ST_EDD_Waypoint` break supplies `CameraTransform` to `BreakTransform`.
Location and rotation pass through unchanged, while `MarkerScaleV1` drives all
three axes of a replacement scale vector. `AddInstance` targets
`WaypointMarkersV1` with `bWorldSpace=true`. The marker-only slice contains no
`SegmentLinesV1` reference.

The deterministic builder, generated full/paste forms, fresh Unreal round-trip,
generic reciprocal-link validator, and dedicated semantic validator all agree.
Unreal's round-trip inserted resolved `MemberGuid` values before
`bSelfContext=True` on same-Blueprint function/variable references. Contracts
therefore match the stable member identity and prove exact data/exec links rather
than rejecting valid native serialization normalization.

`Validate-PathPreviewMarkersPIE.py` provides the runtime gate. Phase one uses the
production drone, capture, waypoint sync, and document sync path to author two
typed waypoints. Phases two and three construct fresh preview actors with one and
two waypoints respectively. They proved exact HISM instance counts, authored
world locations/rotations, uniform `MarkerScaleV1`, an untouched zero-instance
segment pool, and one-to-zero plus two-to-zero clears. The final evidence ended in:

- `1_MARKER_TRANSFORMS_VALID:True`
- `1_TO_ZERO_CLEAR_VALID:True`
- `2_MARKER_TRANSFORMS_VALID:True`
- `2_TO_ZERO_CLEAR_VALID:True`
- `DEFAULTS_RESTORED:True`
- `EDITOR_ACTOR_CLEANED:True`
- `AUTOMATIC_RESULT:PASS`

This DevKit exposes no generic world-specific actor spawn through Python, and
its editor actor API refuses calls while PIE is active. The validated harness
pattern is to place one temporary non-transient actor before PIE so Unreal
duplicates it into the PIE world, require exactly one duplicated class instance,
then destroy the editor source after PIE. The test never saves the dirty level or
restored CDO state. Unreal exited through `LogExit: Exiting.` before the saved
package was synced; live and repository SHA-256 are both
`7E366E3CC26B37CD5949265C5255D110091EB210D692613978DF77FEDB10F69B`.

That marker-only checkpoint was then extended by the linear `SegmentLinesV1`
projection below, followed by the completed client lifecycle integration in the
subsequent section.

### Linear segment rebuild and runtime proof

`RebuildPreviewV1` now contains the compiled and saved combined 34-node/143-pin
marker-and-linear-segment graph. The marker loop continues through an adjacent
index bounds check. For every in-bounds pair, a typed array lookup and native
`ST_EDD_Waypoint` break expose the next `CameraTransform`. The segment midpoint
comes from `TLerp` at alpha `0.5`; `FindLookAtRotation` aligns the Engine cube's
local +X axis; `Vector_Distance / SourceCubeExtentV1` drives X scale; and
`LineThicknessV1` drives Y/Z. A strict `distance > 0.001` branch suppresses
unstable zero-length instances. Both segment and marker `AddInstance` calls use
world space.

`Build-PathPreviewSegmentGraph.py` deterministically extends the checked marker
graph with only captured native UE 5.6 node forms. Two independent generations
produced identical full and paste hashes. The generated graph, Unreal's fresh
post-compile round-trip, and the checked 388-line snippet all pass generic
reciprocal-link validation plus a semantic contract for the exact bounds,
adjacency, midpoint, orientation, scale, component-target, and execution links.
The live asset compiled `Good to go`.

`Validate-PathPreviewSegmentsPIE.py` is the runtime gate. It first authors two
poses through the production drone/capture/document-sync path, then uses fresh
preplaced preview actors for each projection phase. It proved:

- one typed waypoint -> one exact marker and zero segments;
- two distinct typed waypoints -> two exact markers and one exact segment;
- exact segment midpoint, pitch/yaw, zero roll, normalized X scale, and Y/Z
  thickness;
- two coincident typed waypoints -> two markers and zero segments;
- every phase clears both HISM pools back to zero;
- class defaults restore exactly and all temporary editor actors are destroyed.

The final signals were:

- `1_MARKERS_0_SEGMENTS_VALID:True`
- `DISTINCT_SEGMENT_TRANSFORM_VALID:True`
- `2_MARKERS_1_SEGMENTS_VALID:True`
- `2_MARKERS_0_SEGMENTS_VALID:True`
- `DEFAULTS_RESTORED:True`
- `EDITOR_ACTOR_CLEANED:True`
- `AUTOMATIC_RESULT:PASS`

Two workflow details are now explicit. First, mass graph replacement must be
followed by an immediate Unreal clipboard export and exact node-count check; this
caught an unsaved old-plus-new duplicate graph before compilation. Second,
Blueprint selection persists after clipboard export, so node repositioning must
first deselect the full graph or every selected node moves together. Neither
mistake reached compilation or disk. The client ownership and automatic rebuild
gate described below now consumes this isolated renderer.

## Client-owned preview lifecycle and production integration (2026-08-10)

`Configure-PathPreviewLifecycle.py` adds one typed nullable
`PathPreviewActorV1` member to `BPC_EDD_ClientDirector` plus the
`RefreshPathPreviewV1` and `DestroyPathPreviewV1` function seams. The default is
verified as `None`; a repeat run reuses the variable and functions. The matching
read-only metadata probe is `Probe-PathPreviewLifecycleTypes.py`.

`RefreshPathPreviewV1` is a closed 12-node/47-pin graph. It branches on the owned
reference's validity. The valid path copies `DraftDocumentV1` into the existing
actor's `PreviewDocumentV1` and calls `RebuildPreviewV1`. The invalid path spawns
exactly one `BP_EDD_PathPreview` with `AlwaysSpawn`, stores the returned actor,
copies the same document, and rebuilds. The Enhanced compiler rejects the
apparently valid serialized default of a by-reference `SpawnTransform` pin; an
explicit identity `MakeTransform` must be wired into the spawn node. This is a
compiler requirement, not a style preference.

`DestroyPathPreviewV1` is a closed 8-node/26-pin graph. A valid actor is cleared,
destroyed, then the member is reset to `None`. The invalid/stale path also resets
the member, making repeated cleanup and actor-loss recovery idempotent. Both live
functions compiled `Good to go`, saved, and passed exact reciprocal-link and
semantic contracts after fresh Unreal exports.

Production integration is deliberately narrow:

- both successful `EnterDroneMode` camera paths terminate in refresh;
- capture and replace call `SyncDraftDocumentV1`, refresh, then feedback;
- both successful delete paths call `SyncDraftDocumentV1` then refresh;
- `ExitDroneMode` destroys the preview before the existing view-restoration
  branch.

The five generated full graphs and five entryless paste bodies are deterministic.
Their fresh live round-trips are checked in separately because Unreal normalizes
member references and IDs after paste. The first semantic draft validated every
inner execution path but did not require the native function-entry edge. PIE
therefore exposed an Enter no-op. Strengthening the contract to assert the exact
root edge also revealed the same omission in Delete. Both were manually wired,
re-exported, and the complete live suite passed. A graph is not executable merely
because all nodes below its root are internally closed.

Two more editor boundaries are now recorded. First, deterministic UUID counters
must not be restarted for fragments pasted into a graph containing earlier output
from the same sequence; duplicate pin IDs can cause silent link failures. Generate
the complete body in one pass and paste into an emptied function. Second,
function navigation requires a double-click and breadcrumb verification; selection
in My Blueprint alone does not prove the intended graph is active.

`Validate-PathPreviewLifecyclePIE.py` is a self-contained, one-session acceptance
harness. The accepted two-client run proved:

- Enter created one exact owned preview actor with 0 markers/0 segments;
- repeated refresh and repeated Enter reused that actor;
- two real production captures rebuilt it to 2 markers/1 segment;
- linear playback start/update/stop preserved the preview;
- Exit plus repeated destroy removed the actor and cleared its reference;
- re-entry created a fresh actor instance with the same 2-marker/1-segment draft;
- final exit left zero actors and no owned reference;
- the second PIE client had neither the host reference nor a leaked preview actor.

The final signals ended in:

- `PRODUCTION_CAPTURE_REFRESHED_TWO_ONE:True`
- `PLAYBACK_PRESERVED_PREVIEW:True`
- `REENTER_CREATED_FRESH_ONE:<fresh actor path>`
- `REMOTE_ISOLATION:PASS`
- `FINAL_CLEANUP:PASS`
- `AUTOMATIC_RESULT:PASS`

The remote PIE world appears shortly before its PlayerController component is
attached, so remote isolation must wait for readiness rather than treating a
temporarily empty component list as a product failure. The gate waits up to eight
seconds, then requires exactly one remote director when the second world exists.
No direct-refresh fallback remains: the accepted run proves the production Enter
function itself creates the preview.

## Bounded draft history and mutation transactions (2026-08-10)

`Configure-DraftHistory.py` adds bounded undo/redo storage to the live client
component. The checked six-function implementation is `PushCurrentToUndoV1`,
`PushCurrentToRedoV1`, `RecordUndoSnapshotV1`, `ApplyHistorySnapshotV1`,
`UndoDraftV1`, and `RedoDraftV1`. A snapshot preserves the exact
`DraftDocumentV1`, selected index, and next waypoint ID. Restore republishes the
typed document, projects it back into all six transitional arrays, repairs the
selection/ID state, and refreshes the owned preview. The stack cap is 64;
recording a new edit clears redo; empty undo/redo is a no-op. Six pure state
tests plus generated full/paste/live Blueprint contracts pass.

`Build-DraftHistoryIntegrationGraphs.py` composes from the deterministic
production mutation sources, applies document/preview integration, and inserts
one `RecordUndoSnapshotV1` after the last precondition guard and before the first
array mutation. Capture, replace, and delete compile and save live. Their fresh
Unreal exports prove exactly one snapshot, terminal false branches, and the
expected snapshot-to-`Array_Add`/`Array_Set`/`Array_Remove` edge.

Two contract failures materially improved the workflow. First,
`ApplyHistorySnapshotV1` initially compiled while its native entry drove the
second array clear instead of the first; the root-edge contract rejected it.
Second, the pre-existing live replace graph bypassed its camera-validity guard;
strengthening the mutation contract exposed and corrected that route. During
capture/delete installation, a missed manual entry connection likewise compiled
successfully but failed the live round-trip contract. The rule is now explicit:
compiler green is necessary but never sufficient, and every function contract
must name the exact native-entry successor as well as its internal paths.

`Build-DraftHistoryDispatch.py` now extends the checked 62-node playback graph
with a deterministic, idempotent Ctrl+Z/Ctrl+Y layer. It accepts either Control
key, checks Z before Y, tests the appropriate stack before calling the history
kernel, and terminates every accepted or rejected chord. No-Control and
Control-without-Z/Y paths rejoin manual speed/translation/rotation/roll input;
active playback remains exclusive. This ordering is important because Z is also
the existing manual-roll key: Ctrl+Z must never undo and bank in one tick.

The installed result is an 86-node/355-pin EventGraph. It compiled in the
Enhanced DevKit, saved, copied back from Unreal, and passed the generic graph,
waypoint-authoring, feedback, playback-arbitration, and history-dispatch
contracts. Stable runtime messages are `[EDD] Undo applied`,
`[EDD] Redo applied`, `[EDD] Undo ignored: history empty`, and
`[EDD] Redo ignored: history empty`; successful history actions also emit the
existing dynamic waypoint-count/selection line. The 62-node pre-history graph is
retained as `client-director-event-playback-v1.eddgraph` so the repository tests
generation from a known base instead of merely accepting an already-extended
graph.

The next runtime slice remains intentionally UI-free: complete stable mutation
diagnostics and prove the shortcut route in PIE, a cooked normal client, and the
controlled G-Portal environment. Timeline/editor UI design is deferred until
those tests reveal the minimum workflow that is actually useful.

## Conan-native Clean Frame HUD path (2026-08-10)

The Enhanced DevKit exposes a real Conan-owned HUD route; Clean Frame must use
that route rather than relying on Unreal's generic `AHUD.bShowHUD` alone. The
player-controller interface `/Game/Systems/FunCombat_PlayerControllerInterface`
defines `ToggleHUD(bool ShowHud?)`, and the stock
`/Game/Systems/FunCombat_PlayerController` implementation performs three steps:

1. `GUIModuleController.EnableCategory(Popup, ShowHud?)`;
2. `GUIModuleController.EnableCategory(HUD, ShowHud?)`;
3. cast `GetHUD()` to `BaseGameHUD` and call
   `ConanHUD.SetHUDVisibility`, selecting `Hidden` when false and
   `SelfHitTestInvisible` when true.

`BaseHUD.SetHUDVisibility` by itself only changes `HudLootLogWidget` and
`HudGeneralNotificationsWidget`, so it is not an adequate global cinematic
toggle. Conversely, the interface event combines category suppression with
those remaining widgets and is the supported native behavior to reproduce.

The mod-owned implementation now follows that exact boundary in three compiled
client functions. `EnterCleanFrameV1` captures `Popup` and `HUD` independently,
disables both categories, sets the BaseGameHUD notification layer to `Hidden`
when the owner/HUD casts succeed, hides the existing preview actor, and only
then commits `CleanFrameActiveV1=true`. `ExitCleanFrameV1` restores each captured
category, derives notification visibility from the captured HUD state, reveals
the same preview actor, and commits false. `ToggleCleanFrameV1` selects the
appropriate idempotent primitive from the active flag. Their accepted live
Unreal round-trips contain 25/22/5 nodes and all reciprocal entry links are
covered by semantic contracts; one missing Exit entry link was caught and
repaired even though Unreal had compiled the disconnected body green.

The client EventGraph now contains 89 nodes. Its F7 poll occurs after owning
local controller, `DroneModeActive`, and valid-camera guards, but before the P
playback branch. Clean Frame therefore remains reachable during playback while
remaining unavailable outside an active local drone session. The F7 path
terminates the current tick after toggling. Normal `ExitDroneMode` calls
`ExitCleanFrameV1` before `DestroyPathPreviewV1`; emergency exit and invalid
camera recovery inherit that restoration because they delegate to the normal
exit primitive.

A focused AlmostEmpty PIE run deliberately used divergent starting categories
(`HUD=false`, `Popup=true`), proved exact capture, suppression, preview hiding,
repeated-enter non-overwrite, exact restore, and repeated-exit stability, then
proved separate normal-exit and emergency-exit restoration cases. It ended in
`EDD_CLEAN_FRAME_PIE:AUTOMATIC_RESULT:PASS` without an EDD Blueprint runtime
error. The fixture does not create Conan's normal `BaseGameHUD`, so the cast
failure path was exercised and correctly converged on preview/state handling;
visual proof that every native notification widget disappears remains a cooked
normal-client gate. This distinction must remain explicit: category and state
restoration are runtime-proven now, while complete native-HUD appearance is not
claimed until the real client test.

After the accepted run, the client asset compiled `Good to go`, saved, and the
editor closed through `LogExit: Exiting.`. `FromDevKit` copied only
`BPC_EDD_ClientDirector.uasset`; repository and live source both hash to
`2A32E93710603AAD7C66EF02F4131C36FBBDA70BB1E3DE1C31DDF9B979BE5E54`.

## Mutation diagnostics and attended shortcut boundary (2026-08-10)

The three production mutation functions now have complete deterministic graph
generators and accepted live Unreal round-trips. Capture contains 29 nodes/110
pins, Replace contains 26/105, and Delete contains 29/117. Their entryless paste
bodies are 28/109, 25/104, and 28/116 respectively. Every live function
compiled `Good to go`, was saved, exported again from Unreal, and passed the
combined history, document-sync, path-preview, native-entry, and diagnostic
contracts.

The stable messages are `[EDD] Waypoint captured`, `[EDD] Selected waypoint
replaced`, `[EDD] Selected waypoint deleted`, `[EDD] Capture ignored: no drone
camera`, `[EDD] Replace ignored: no drone camera`, `[EDD] Replace ignored:
invalid selection`, and `[EDD] Delete ignored: invalid selection`. All are
`PrintString` calls with screen output disabled and log output enabled. A
rejected path terminates before history capture, mutation, document sync, or
preview refresh. Successful paths retain the existing dynamic count/selection
feedback owned by the EventGraph.

`Validate-DraftHistoryShortcutsPIE.py` is the focused runtime semantic harness.
`tools\Run-DraftHistoryPIE.ps1` gives it one isolated, repeatable entry point.
The runner launches the editor with `-ModDevKit` and a unique run ID; the Python
state machine loads `/Game/Dev/AlmostEmpty`, requests PIE through
`LevelEditorSubsystem`, applies `God` as a survival guard, executes the public
Enter/Capture/Undo/Redo/Exit operations, requests teardown, and emits PASS only
after `is_in_play_in_editor()` becomes false. The PowerShell runner accepts only
markers containing its own run ID and then closes the exact editor process it
created. It does not edit Blueprint defaults or require an unlocked desktop.

The accepted runs `415b7ce7438e41d7994171928e9b7f6f` and
`d8a991a262e44212bb44e42bf1aa97f1` each captured 65 waypoints,
proved the 64-entry cap, undo, redo, branch-edit redo invalidation, full typed
document/source-array/preview parity, exact view restoration, and no-camera
capture, empty redo, invalid replace, and invalid delete edge cases through
complete before/after fingerprints. It requested PIE teardown and ended in a
run-scoped `AUTOMATIC_RESULT:PASS`; the editor then closed cleanly. Total wall
time was 89 seconds per run, dominated by DevKit startup. The second run used
the exact files prepared for commit and proves the command is repeatable.

The separation of proof is deliberate. Deterministic `.eddgraph` contracts
prove F10/K/Ctrl+Z/Y/F9 routing and arbitration. Programmatic PIE proves the
called Blueprint functions' runtime semantics. A single attended cooked-client
dogfood pass owns physical keyboard feel and final end-to-end routing. Unreal
Python exposes input queries but no raw-key injection, and Windows can silently
drop synthetic keys on a locked desktop, so unattended OS-key automation is not
a release gate.

## History pop repair and cold-load package gate (2026-08-10)

The first attended Ctrl+Y run exposed a real Blueprint evaluation trap. Undo and
redo shared the pure expression `Length(SourceDocumentsV1) - 1` across all three
snapshot arrays, then removed the document entry first. Pure Blueprint nodes are
not cached values: each downstream consumer re-evaluated the expression. After
the document removal, the parallel selection and next-ID removals received
`-1`, producing `RedoSelectionsV1 [-1/0]` and
`RedoNextWaypointIdsV1 [-1/0]` warnings and diverging the stacks.

`UndoDraftV1` and `RedoDraftV1` now remove the selection array first, the
next-ID array second, and the primary document array last. The document length
therefore remains stable for every consumer of the shared last-index expression.
The graph builder and semantic contract encode that order explicitly. Fresh
live graph exports include reciprocal native entry links and pass the complete
history lifecycle contract; the saved client asset then passed the physical PIE
sequence above without an EDD runtime error.

The repair also established a critical Conan Enhanced launch/package rule.
Files under the physical mod source directory
`Content/Mods/ExileDroneDirector/Local/...` are exposed at
`/Game/Mods/ExileDroneDirector/...` by the `-ModDevKit` platform layer. A normal
Unreal launch without that flag does not install the mapping. In that invalid
session, the physical tree appeared as `/Game/Mods/ExileDroneDirector/Local/...`,
root-path dependencies were unavailable, Blueprint structs degraded to unknown
types, and save could fail with `DeleteFile was unable to delete`,
`Failed to move ... from temp directory`, and `Error saving`.

The safe recovery is to close the generic editor without saving and relaunch
the Conan project with `-ModDevKit`; do not move assets out of `Local` and do not
repair the resulting phantom compiler errors. The committed client asset's
SHA-256 is `7B50872A3C2B33124B72915EC07FA78F67027F05E6E40A8F99509EDDDA10543C`.
`tools/Test-ColdAssetLoad.ps1` now starts a fresh mod-aware commandlet, loads all
seven core assets through their root virtual paths, compiles all four
Blueprints in memory, and requires `EDD_COLD_LOAD|RESULT|PASS`. The accepted
history asset passed that gate with zero commandlet errors after a fully cold
start. This gate is mandatory after every promoted `.uasset`; a warm PIE pass
alone cannot prove restart-safe package resolution.

After that PIE gate, the first packaged-runtime target is a normal local Conan
Enhanced single-player save. It must prove load, F10 entry, flight, authoring,
undo/redo, playback, F7 native-HUD suppression/restoration, F9 recovery, and
safe relaunch before any Workshop or G-Portal deployment is attempted.

The native GUI module controller also exposes `IsCategoryEnabled`, so Clean
Frame can capture the HUD and Popup category states before suppression. Exit
must call the Conan-native show path and then restore both saved category flags
explicitly; repeated enter/exit is idempotent, and Drone Mode exit/emergency
cleanup must always restore the captured state. Mod-owned overlays and preview
actors are suppressed in the same local presentation transaction without
destroying or rebuilding Flypath state.

The stock assets were inspected read-only. No Conan source asset is compiled,
saved, copied, or committed. The exact Enhanced build observed was Unreal
Editor 5.6.1 CL 370197.

## Cook, Workshop, and G-Portal reconnaissance (2026-08-09)

The installed `DreamworldMods` plugin declares editor support for cooking,
packaging, and uploading mods. Its bundled change log also states that a mod's
Steam Workshop ID is included on the first cook. That proves the supported GUI
path exists, but it does not yet prove a stable headless commandlet, output
layout, or unattended authentication flow. Those remain bounded next-session
reconnaissance items.

Steam's official Workshop integration supports updates with `steamcmd` and a
VDF containing the application ID, persistent published-file ID, content
folder, preview, visibility, and change note. Initial creation/legal-agreement
acceptance and Steam Guard may remain manual. The intended automation is a
self-hosted Windows GitHub Actions runner that keeps the very large Enhanced
DevKit installed locally, validates the small Git repository, cooks/packages,
and updates an existing test Workshop item. Credentials never enter Git.

G-Portal's Enhanced servers install mods from Steam Workshop. GitHub source is
therefore not directly deployable. The safe first deployment keeps G-Portal
restart as an explicit human approval: publish the test item, back up the
server, install the exact Workshop version/load order, then deliberately
restart. Initial server acceptance covers only local Drone Mode and transient
authoring; shared/persistent Flypaths require the later server-repository phases.

References:

- <https://partner.steamgames.com/doc/features/workshop/implementation>
- <https://www.g-portal.com/wiki/en/how-do-i-install-conan-exiles-mods/>
- <https://www.g-portal.com/en/gameserver/conan-exiles-server-hosting>

## Blueprint graph automation boundary

The editor Python API can locate the component Event Graph, but the graph object
has no node insertion methods. This Enhanced build exposes base `EdGraph` and
`K2Node` types without the concrete event/call/branch constructors required for
safe graph authoring.

Unreal's native Blueprint clipboard serialization is available and includes node
classes, function references, pins, links, positions, defaults, and identifiers.
The project therefore uses reviewed `.eddgraph` snippets for batch graph work.
See `docs/blueprint-workflow.md` and `tools/blueprint/`.

## Repository persistence adapter proof (2026-08-10)

- Enhanced 5.6 exposes Conan `PersistenceComponent`,
  `ActorPersistenceComponent`, and `WorldPersistenceComponent`. They surface
  database-loaded state plus data-loaded/pre-save signals, but no official mod
  contract or arbitrary-record API was found. Their world-actor lifecycle remains
  a dedicated-server research candidate, not the accepted first adapter.
- Standard `GameplayStatics` SaveGame create/save/load/existence/delete calls are
  exposed to Blueprint and Python. This is the first accepted server-invoked
  adapter; clients must never become repository authority.
- `Configure-RepositorySaveGame.py` idempotently creates
  `SG_EDD_RepositoryStorage` under the correct virtual path and fixes six
  automatable fields: schema version, generation, committed flag, reserved
  snapshot-hash seam,
  opaque record envelopes, and tombstone IDs.
- Blueprint variables had to be marked instance-editable before Python could set
  values on a runtime SaveGame instance. CDO reads/writes alone do not prove the
  runtime object contract.
- A failed first generator run was safe: it stopped before save and produced no
  `.uasset`. A second first-create run completed and saved the asset but returned
  commandlet exit 1 because calling `load_asset` on a missing path logs an Unreal
  error even when creation later succeeds. Guard first-create loads with
  `does_asset_exist` so successful generation exits cleanly.
- `Test-RepositorySaveGame.ps1` now reproduces three isolated processes:
  configure/idempotence, writer plus same-process read, and fresh-process read
  plus cleanup. Exact ints, bool, hash string, arrays, canonical record text, and
  Unicode (`Unicode flight — 北風`) survived. The automation slot was deleted.
- Cold asset load compiled the SaveGame Blueprint in a fresh commandlet. The
  synced live/repository asset SHA-256 at acceptance was
  `B6F3E471C7FD19EBE2A2B698BE1B4F1ACE13B3CEE59DE86932AF9D88810791E7`.
- `UserDefinedStructureEditorUtils` is not exposed to Enhanced Python. New UDS
  members cannot be authored with the current Python API; prefer Blueprint-class
  variables for automatable runtime seams or treat a UDS edit as an explicit
  one-time attended step.

## Repository service and JSON codec seam (2026-08-10)

- Enhanced exposes `PlayFabJsonObject` to Blueprint/Python with object, object
  array, generic array, string, boolean, and number get/set operations plus
  `EncodeJson` and `DecodeJson`. `PlayFabJsonValue` supplies typed JSON values.
- A fresh commandlet proved nested object, boolean, string array, numeric values
  encoded as strings, and exact Unicode (`Unicode flight — 北風`) survive an
  encode/decode round trip.
- `EncodeJson` is compact but preserves insertion order: adding `zeta` then
  `alpha` produced `{"zeta":"last","alpha":"first"}`, while the reverse
  insertion produced the reverse byte order. Canonical encoder graphs must add
  every object field in a fixed ascending-key execution chain.
- Deliberately decoding malformed JSON returns false but logs a PlayFab engine
  error, which makes an otherwise successful Python commandlet exit nonzero.
  Do not poison a commandlet acceptance log with expected malformed input;
  exercise malformed-record rejection through repository validation fixtures.
- No Blueprint/Python SHA-256, MD5, digest, or general string-hash helper was
  exposed by this build. Do not substitute an undocumented weak checksum while
  claiming the canonical SHA-256 contract. Runtime version 1 now explicitly uses
  `structural-v1`: canonical JSON, exact field/schema validation, full semantic
  validation, alternating committed generations, tombstones, and newest-valid
  recovery. `ContentHash`, `RecordContentHash`, and `SnapshotHash` remain empty
  reserved migration seams. This detects malformed and semantically corrupt
  storage but deliberately does not claim adversarial tamper detection.
- `BP_EDD_FlypathRepository` is generated idempotently as a non-replicated Actor
  with active snapshot state, request/result staging, policy values, typed
  `ST_EDD_FlypathDocument` exchange, PlayFab JSON scratch references, and named
  codec/validation/storage/private-CRUD function seams. The asset compiles, but
  empty function seams are not runtime CRUD evidence.
- The repository actor cold-loaded and compiled in a fresh commandlet. Its
  synchronized live/repository SHA-256 is
  `19E8BC241C48A45473A0C826FD22B4D6E7A884542F9D035FB393E0DCE416EE4A`.
- `Test-RepositoryService.ps1` is the focused seam gate: schema contracts,
  idempotent asset configuration, and the runtime JSON dependency round trip.

## Repository core graph runtime installation (2026-08-11)

- `AssetEditorSubsystem.open_editor_for_assets` reliably opens the mod-owned
  repository Blueprint from an interactive `-ModDevKit` session. The Enhanced
  Python API still does not expose graph-focus or graph-edit operations.
- `PrintWindow` can capture the exact background Blueprint top-level window
  without bringing Unreal over the user's foreground application. Direct
  `WM_*` messages work for ordinary tab clicks, compile/save clicks, paste, and
  graph framing. Slate pin drags additionally require the physical cursor to be
  synchronized with every drag step.
- Keyboard graph-copy commands require real focus. Attach the automation thread
  to the foreground and Unreal window threads, activate the exact Blueprint
  top-level window, click the graph canvas, and only accept clipboard text that
  begins with `Begin Object Class=/Script/BlueprintGraph.` and contains the
  expected function name. This prevents silently exporting a stale graph or a
  `BPGraph(...)` document wrapper.
- Unreal removes `DefaultValue=""` from an empty string pin when a pasted graph
  is saved and copied back out. Semantic contracts must accept the absent field
  as the canonical empty-string equivalent while rejecting every explicit
  non-empty value.
- The installed `ResetRepositoryResultV1` and `FindRecordIndexV1` graphs compiled
  successfully, reported `All Saved`, exported with native function entries and
  reciprocal links, and passed complete semantic contracts. A fresh Enhanced
  commandlet cold-loaded the asset with zero errors. The synchronized live/Git
  asset SHA-256 is
  `51CEDB0DDC7BA4C1FFAE0162315CBEFB4162C2F6C4BE6389B409850CBA34D9D7`.
- Rerunning `Configure-RepositoryService.py` resaves the package and may change
  its binary hash even when the schema is already correct. After that resave,
  re-export and semantically validate every installed graph, cold-load the final
  package, and only then accept and synchronize its new hash.

## Repository JSON native node forms (2026-08-11)

- A disposable `Developer/Automation/BP_EDD_JsonNodeProbe` harvested the exact
  Enhanced 5.6 PlayFab JSON call-node forms. The checked-in fixture contains 22
  calls and 87 pins covering construction, string/bool/float/object fields,
  string/float/object arrays, explicit nulls, generic values, field-name
  enumeration, existence checks, encode, and decode.
- `HasField`, `EncodeJson`, and `DecodeJson` exist as native UFunctions and are
  Python-visible, but the unbound Blueprint action menu does not list them
  reliably. Their nodes were derived from reflected sibling signatures, pasted
  into the probe, compiled to a green Blueprint, and copied back out by Unreal.
  The native round-trip confirmed `HasField(FieldName) -> bool`, pure
  `EncodeJson() -> string`, and impure `DecodeJson(JsonString) -> bool`.
- Fresh reflection and a second green compile/copy-back prove
  `Set/GetNumberField`, `Set/GetNumberArrayField`, `SetFieldNull`, `GetField`,
  and `PlayFabJsonValue.IsNull`. PlayFab JSON numbers are Blueprint single-
  precision floats. Optional `published` and `sourceAttribution` record fields
  can therefore retain canonical JSON `null`; do not replace null with sentinel
  strings or ambiguous zeroes.
- Array getters (`GetStringArrayField` and `GetObjectArrayField`) are impure in
  this build and own execution pins. Treating all JSON getters as pure produces
  an invalid execution contract.
- The action menu is a separate Slate top-level HWND. Reliable harvesting uses
  the exact Blueprint HWND for graph focus, the popup HWND for search, disables
  Context Sensitive once, and accepts clipboard data only after native compile
  and copy-back. `PrintWindow` does not include the separate popup; capture the
  screen region or popup HWND when diagnosing the search menu.
- The probe asset is disposable and was deleted after export. Production graphs
  consume `repository-json-node-forms.eddgraph`; they never depend on a
  Developer/Automation asset.
- A loaded probe may remain rooted by `GCObjectReferencer` after its asset editor
  closes, and in-session `DeleteAsset` then refuses with an ensure. Do not keep
  retrying or force-delete the package. Close the isolated editor without saving
  the disposable changes, then run `Delete-RepositoryJsonNodeProbe.py` in a fresh
  commandlet; the accepted cleanup marker is
  `EDD_JSON_NODE_PROBE_DELETE:DELETED:True` and the physical package must be
  absent afterward.
- Conan's Python module does not expose `unreal.KismetMathLibrary` directly.
  Load `/Script/Engine.KismetMathLibrary` with `unreal.load_class`, then call
  `unreal.get_type_from_class`; Enhanced returns the generated `MathLibrary`
  Python type. Reflection proves the codec-critical
  `conv_rotator_to_quaternion`, `quat_rotator`, `quat_is_finite`,
  `quat_is_normalized`, and `quat_normalized` functions. This preserves the
  canonical quaternion document contract while the current authoring bridge
  still stores an Unreal `Transform`.

## Repository decoder native forms accepted (2026-08-11)

- The editor-accepted fixture is
  `tools/blueprint/templates/repository-decoder-native-node-forms.eddgraph`.
  It contains native `EqualEqual_StrStr`, `Quat_Rotator`, and array-item forms
  copied back from a green Enhanced 5.6.1 compile. The disposable probe was
  deleted in a fresh commandlet and no editor process remained.
- An unlinked `K2Node_GetArrayItem` canonicalizes back to wildcard after
  compilation. This is correct: the decoder builder must explicitly specialize
  its input/output to PlayFab float, and the connected production compile must
  prove that specialization. Do not reject the native wildcard copy-back or
  mistake an unlinked speculative float annotation for runtime evidence.
- The shared node cloner previously regenerated each `PinId` but left split-pin
  `SubPins` and `ParentPin` references pointing at the source GUIDs. That can
  produce a plausible text fixture which asserts during K2 reconstruction.
  `Node.clone` now rewrites every internal old-node/old-pin reference to the new
  node/new-pin pair. Decoder contracts require the Quat parent to enumerate the
  exact four regenerated component GUIDs and every component to point back to
  the regenerated parent.
- A single click in My Blueprint selects a function but leaves the current graph
  open. The first disposable copy-back therefore contained EventGraph Actor
  events, and the node-count/graph-identity check rejected it. Functions require
  an explicit double-click and breadcrumb verification.
  `Export-BlueprintGraphClipboard.ps1` now supports `-ExpectedGraph` and
  `-ExpectedNodeCount` so this mistake fails before writing an artifact.
- `unreal.SystemLibrary.quit_editor()` is the reliable exact-process shutdown
  after remote work. `Process.CloseMainWindow()` can report success while the
  main editor remains alive. Avoid the PowerShell variable name `$pid` in Win32
  enumeration callbacks because `$PID` is a read-only automatic variable.

## Repository transform and precision forms accepted (2026-08-11)

- A second disposable probe compiled `BreakTransform` and `MakeTransform`
  successfully in Enhanced 5.6.1 and was copied back from Unreal. The accepted
  fixture is
  `tools/blueprint/templates/repository-codec-transform-node-forms.eddgraph`:
  entry plus two pure Kismet Math Library calls, 11 pins, unit default scale,
  const-reference Transform input, and zero orphaned pins.
- Unreal Engine 5 uses a precision subtype on Blueprint `real` pins. The
  Transform bridge exposes doubles while PlayFab JSON number pins expose
  single-precision floats. Enhanced does not expose a standalone global
  double-to-float action: supported float/double pin connections are coerced by
  the Blueprint compiler. Do not keep searching the action menu for a missing
  conversion node. Prove the seam by compiling the actual codec graph and by
  exercising finite, fractional, negative, large, and boundary values through
  encode/decode acceptance.
- The disposable probe was closed by exact PID and removed in a fresh
  commandlet. Accepted cleanup evidence was
  `EDD_JSON_NODE_PROBE_DELETE:DELETED:True`, `COMPLETE:True`, and physical asset
  absence.
- This is node-form proof only. `EncodeDocumentV1`/`DecodeDocumentV1` are still
  the current implementation slice; no private CRUD, collaboration, cinematic
  trajectory, lens/event backend, polished UI, or cook is claimed by it.

## Split quaternion clipboard reconstruction failure (2026-08-11)

- Linked-subset bisection proved that Enhanced 5.6.1 can paste the native array
  nodes, repository variable nodes, waypoint Break Struct, PlayFab JSON calls,
  Break Transform, Break Vector, and each corresponding data/exec bridge.
  The full 21-node `EncodeWaypointV1` body without the quaternion conversion
  also survives in a real repository function graph.
- A split `Conv_RotatorToQuaternion` node asserts in `K2Node.cpp:1360` with
  `NumNewPins == InNewPins.Num()` when imported with, or subsequently pasted
  into, that populated graph. Removing Rotation->Quat and X/Y/Z/W->array links
  does not prevent the assertion. The mod asset remains safe because every
  failed run was isolated and unsaved.
- Do not treat repeated full-editor paste attempts as testing. Generated probe
  files under the session scratch directory isolate node families and linked
  seams, and canonical/paste contract suites must pass before any live attempt.
- Production installation must avoid the toxic clipboard shape: validate an
  unsplit Rotator->Quaternion plus explicit Break Quat node form, or create and
  split that one conversion node natively after the safe body is installed.
  Export, semantic validation, compile/save, fresh cold load, and runtime value
  round trips remain mandatory before accepting the encoder.
- A derived native unsplit `Conv_RotatorToQuaternion` form (three pins) pasted
  successfully into the populated 21-node body, confirming that the split call
  pin—not quaternion conversion—is the failing representation. Before any live
  paste, the runner must copy the active graph and verify the intended function
  name; a visual row click or coordinate alone is not accepted evidence.

### Repeated-assertion containment rule

- Eleven editor crashes between 05:31 and 06:35 UTC carried the identical
  `NumNewPins == InNewPins.Num()` assertion. They were retries of one clipboard
  reconstruction defect, not independent mod/runtime failures. Repeating an
  unchanged import after this signature is prohibited: one recurrence stops
  editor automation and returns the graph to offline reduction/fixture proof.
- The invalid working state produced a distinct repository autosave. Its exact
  path, timestamp, size, and SHA-256 were inspected before deleting only that
  autosave. The live repository package was preserved.
- After containment, a fresh `-ModDevKit` commandlet cold-loaded and compiled
  every core asset, including `BP_EDD_FlypathRepository`, and exited with zero
  errors. This proves the live package was not corrupted by the failed imports.
- The production waypoint encoder now avoids the toxic split-return form. It
  uses an unsplit `Conv_RotatorToQuaternion`, the editor-harvested native
  `BreakQuat` fixture, and explicit `Conv_IntToDouble` bridges before PlayFab
  JSON number nodes. Canonical and paste-ready semantic contracts must pass
  before the single permitted controlled editor import.
- The controlled import passed. `EncodeWaypointV1` reconstructed as 25
  nodes/112 pins, compiled green, exported from the live graph, and passed the
  full semantic contract. Unreal canonicalizes an unlinked empty string by
  omitting `DefaultValue=""`; contracts accept either omitted-empty or explicit
  empty while still rejecting links and non-empty annotation defaults.
- The saved repository package survived a fresh-process cold compile and the
  complete `-RequireMvpAssets` scaffold. Its live and Git-mirror SHA-256 is
  `8AB8D7CEA2AEF7D1FBA205CC89E969058DE3054D57ED9C3EECD26F87BB39104B`.
- A session-only command-line INI override enables Unreal's official Python
  remote-execution node without permanently changing the DevKit:
  `-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=True`.
  The official `remote_execution.py` client discovered exactly one
  `ConanSandbox` node and opened the repository asset with structured success
  output. Prefer this channel for editor scripting; retain UI input only for
  graph-front selection, clipboard import/export, and the final pin seam that
  Enhanced does not expose through Python.

## Pending local reconnaissance

- Concrete Conan-character view restoration in a gameplay-map PIE run
- Hands-on remote-client raw-mouse pitch/yaw and physical-wheel feel
- Remaining death, teleport, disconnect, UI-close, and component-end-play hooks
- Emergency camera restoration and the view lifecycle in cooked runtime
- Exact Enhanced cook command/commandlet, output layout, and Workshop metadata
- First normal-game `.pak` load and controlled Workshop update
- Authenticated server identity and dedicated-server SaveGame behavior

## EncodeSegmentV1 accepted live (2026-08-11)

- `tools/Start-EnhancedDevKitRemote.ps1` now verifies Enhanced 5.6, refuses any
  existing `UnrealEditor` or `ConanSandbox` process, launches with `-ModDevKit`,
  and enables remote execution only for that editor process.
- `tools/unreal/invoke_unreal_remote.py` wraps Epic's bundled transport and
  fails closed unless discovery returns exactly one `ConanSandbox` node. Its
  ambiguity, missing-node, exact-name, and success-selection behavior is covered
  by four offline tests in the full scaffold.
- The controlled segment install proved the empty target identity before paste,
  reconstructed the 13-node body without a crash (`Saved/Crashes` remained
  16), and exported the wired live graph as 14 nodes/57 pins. Both the pre-wire
  body and complete live graph passed their semantic contracts.
- Interactive compilation uses
  `unreal.BlueprintEditorLibrary.compile_blueprint`; this Enhanced build does
  not expose `unreal.KismetEditorUtilities`. Read the active Unreal log with
  `FileShare.ReadWrite` because a normal `ReadAllText` may lose a race against
  the editor's log handle.
- Unreal API save returned true, the editor exited gracefully, and a fresh
  `-ModDevKit` commandlet loaded and compiled every core Blueprint with
  `EDD_COLD_LOAD|RESULT|PASS` and zero errors. The repository package's exact
  live/Git mirror SHA-256 is
  `912E7ABB6514F0A94CE5F36005ADD9DDFE8B408716272BCA2C8ED7DA13A2F9B6`.
- Next codec target is `EncodeDocumentV1`; no cook or polished UI is authorized
  yet.

## EncodeDocumentV1 accepted live (2026-08-11)

- The deterministic 36-node paste body was installed only after the empty
  `EncodeDocumentV1` target identity was exported and proven. The final native
  function entry was connected to `ScratchRootJsonV1` at 1:1 zoom, then the
  complete live export passed the document semantic contract as exactly 37
  nodes/146 pins.
- At `Zoom -4`, overlapping native entry/output nodes and tiny execution pins
  produced harmless no-op drags. The reliable procedure is: export exact node
  coordinates, separate overlaps, frame the entry/root seam, zoom to 1:1, make
  one pin-center connection, and immediately re-export. Do not infer success
  from cursor movement.
- Moving the heavily connected `ScratchRootJsonV1` setter caused Enhanced to
  insert 26 reroute knots. The closed-node contract rejected the 63-node state.
  Undoing the connection and reroute transaction restored exactly 37 nodes;
  reconnecting at 1:1 without another move preserved zero knots. Node count and
  semantic closure are mandatory evidence, not formatting preferences.
- `BlueprintEditorLibrary.compile_blueprint` completed with zero Blueprint/K2
  warnings or errors, `save_loaded_asset(..., only_if_is_dirty=False)` returned
  true, and the post-save graph contract passed again. The editor exited
  gracefully with crash directories unchanged at 16.
- A fresh `-ModDevKit` commandlet loaded and compiled every core Blueprint and
  emitted `EDD_COLD_LOAD|RESULT|PASS` with zero errors. Dry sync found exactly
  one repository asset conflict and 16 unchanged assets; forced FromDevKit sync
  copied only that asset. Live and Git-mirror SHA-256 are both
  `52DF21CC7428D0472549E0233F3633FF9C0973887B347F005413C1EBA437DCF9`.
- Checked-in post-save evidence is
  `tools/blueprint/live-snippets/encode-document-v1.eddgraph`, and the full
  scaffold now validates its structure and document semantics. Next work is
  document decoding, record-envelope codecs, private CRUD, and restart
  persistence. No cook or polished UI is authorized yet.

## Repository document decoders closed offline (2026-08-11)

- `Build-RepositoryDocumentDecoderGraphs.py` now deterministically emits full
  and paste bodies for `DecodeWaypointV1`, `DecodeSegmentV1`, and
  `DecodeDocumentV1`. All six graphs pass generic reciprocal-link validation
  and exact semantic contracts in the complete scaffold.
- Every decoder preserves the source before nested work, projects into its typed
  scratch struct, calls the already accepted matching encoder, and commits
  `ScratchValidV1` only from exact canonical string equality. This makes
  PlayFab's permissive getter defaults fail closed for missing, extra,
  mistyped, reordered, or otherwise noncanonical payloads.
- The PlayFab 5.6 plugin source confirms `GetObjectField` returns a UObject
  wrapper whose invalid internal JSON pointer makes subsequent getters return
  defaults rather than exposing a Blueprint `None`. `DecodeJson` explicitly
  returns failure and resets its object after malformed input.
- Runtime guards now prevent noisy unsafe reads as well as logical acceptance:
  `DecodeDocumentV1` resets validity and branches on `DecodeJson` before any
  root field; `DecodeWaypointV1` resets validity and requires exact three-value
  position and four-value quaternion arrays before any `GetArrayItem` can
  evaluate. False branches terminate with validity already false.
- Accepted offline sizes are 38 nodes/136 pins for waypoint, 21/67 for segment,
  and 46/167 for document; body-only forms are one entry node and one pin less.
  Live schema application, editor reconstruction, compile/save, cold load, and
  mirror synchronization remain mandatory before these decoders are accepted.

## Repository document decoders accepted live (2026-08-11)

- `ScratchSourceJsonV1` and `ScratchSourceDocumentJsonV1` were added through the
  checked repository-schema configurator, and all three empty decoder targets
  were proven by graph name and one-node export before any body paste.
- Post-compile live evidence is checked in under
  `tools/blueprint/live-snippets/`: `DecodeWaypointV1` is 38 nodes/136 pins,
  `DecodeSegmentV1` is 21/67, and `DecodeDocumentV1` is 46/167. All semantic
  contracts passed both immediately after wiring and after repository-wide
  compile/save.
- The schema resave did not regress existing behavior. Fresh exports of
  `ResetRepositoryResultV1` (9 nodes), `FindRecordIndexV1` (5),
  `EncodeWaypointV1` (25), `EncodeSegmentV1` (14), and `EncodeDocumentV1` (37)
  all passed their closed-graph semantic contracts.
- Epic's remote executor does not define `__file__`. Script-file execution must
  use `exec(compile(source, absolute_path, 'exec'), globals())` after setting
  `__file__`; prepending text directly before a script's `from __future__`
  import is invalid. The runner now owns this wrapper and its offline test.
- Live Unreal copy-back injects a `MemberGuid` between `MemberName` and
  `bSelfContext` in self-call references. Contracts must match a call node by
  function name and node class, not by adjacency of serialized fields.
- Pasting a multi-node graph centers its bounding box under the cursor, so the
  exposed first executable node may land far from the native function entry.
  Use `Home`, export exact coordinates, and enlarge only the final seam.
- `Ctrl+A`/copy leaves every graph node selected. Before moving one node,
  explicitly click empty canvas to clear selection; otherwise dragging one
  selected node translates the entire graph. This caused harmless layout-only
  translations during the document install, which exact coordinate export
  diagnosed before the final entry connection.
- `Blueprint.status` is protected in Enhanced Python and cannot be used as a
  compile-status probe. Compile through `BlueprintEditorLibrary`, require the
  remote command and API save to succeed, inspect the live log for K2 errors,
  re-export the graph, and finish with a fresh commandlet cold compile.
- The saved package remained healthy, but directly calling
  `unreal.SystemLibrary.quit_editor()` while the repository Blueprint editor
  was open created one shutdown-only assert:
  `PreviewScene.GetWorld()` in `BlueprintEditor.cpp:10423`. This is distinct
  from the earlier K2 clipboard assertion and happened after API save.
  `tools/unreal/Quit-EnhancedEditorSafely.py` now closes all asset editors,
  waits at least three Slate ticks (up to 120 for closure), and only then calls
  `quit_editor()`. Use that script for future interactive shutdowns.
- A new `-ModDevKit -NullRHI` process loaded all nine core assets, compiled
  every Blueprint, and emitted `EDD_COLD_LOAD|RESULT|PASS` with zero errors,
  proving the shutdown assert did not damage the package. Sync copied exactly
  the changed repository package; its live and mirror SHA-256 is
  `C0E8C7F3368E873C1774E8CBDADC8F402EF96320AFBCA9A7D6BCA279ED56E59F`.
- Next backend slice: record-envelope codecs followed by private CRUD and
  deterministic restart recovery. There is still no authorization to cook or
  build the polished UI.

## Repository record encoder accepted live (2026-08-11)

- `EncodeRecordPublishedFieldsV1` and `EncodeRecordSourceAttributionV1` are
  accepted at 17 nodes/57 pins each; `EncodeRecordV1` is 44/157. Exact live
  copy-backs passed before and after compile/save. The semantic suite proves
  canonical record/envelope order, explicit null publication and attribution,
  numeric revision conversion, isolated document staging, native entry
  reachability, and the terminal `ScratchEncodedRecordV1` commit.
- At `Zoom -7`, a visually plausible execution-pin drag was a verified no-op.
  The reliable seam was: export exact identities and graph positions, deselect
  all nodes after copy, move only the native entry beside the target, zoom to
  `-2`, pan with explicit relative `mouse_event(MOVE, ...)` calls, and connect
  the labelled `ScratchRecordJsonV1` setter. The contract rejected the no-op
  and accepted only the serialized reciprocal link.
- The repository-wide resave did not regress sibling functions. Fresh live
  exports passed for the two repository-core graphs, all three document
  encoders, and all three strict document decoders.
- Invoke the remote runner with `--script`, not `--file`. Enhanced's
  `AssetEditorSubsystem` exposes `close_all_editors_for_asset` but not
  `get_all_edited_assets` or `close_all_asset_editors`; the safe-quit helper now
  uses an explicit-path compatibility fallback and defaults to the repository
  Blueprint. The editor then exited cleanly after closing the asset editor and
  waiting three Slate ticks.
- `Sync-DevKitContent.ps1` requires explicit
  `-DevKitRoot F:\CEUE5Devkit`. A conflict-only dry run intentionally throws,
  so run the reviewed `-Force` invocation separately rather than chaining it
  behind the expected nonzero dry run.
- A fresh `-ModDevKit -NullRHI` commandlet loaded and compiled all nine core
  assets with `EDD_COLD_LOAD|RESULT|PASS` and zero errors. Sync copied exactly
  one repository package; live and mirror SHA-256 is
  `DB56429B5F83CBC6923D0761FA6B62A01A858C526A8B6AE3C963ED13AE655A64`.
- Next backend slice: private CRUD and deterministic restart recovery. No cook
  or polished UI is authorized yet.

## Repository record decoder accepted live (2026-08-11)

- `ScratchSourceRecordJsonV1` and the three decoder functions were applied and
  verified through the repository schema configurator before graph mutation.
  Every target was exported as exactly one native function-entry node before its
  body was pasted.
- Accepted post-compile live shapes are
  `DecodeRecordPublishedFieldsV1` 16 nodes/53 pins,
  `DecodeRecordSourceAttributionV1` 19/67, and `DecodeRecordV1` 50/180.
  Checked-in copy-backs live under `tools/blueprint/live-snippets/`, and the
  full scaffold owns their structural and semantic contracts.
- The PlayFab plugin source proves `GetField` returns a value wrapper whose
  missing field has an invalid root and whose `GetTypeString()` is a Blueprint
  `String`. The root decoder uses
  `GetField("record") -> GetTypeString() == "Object" -> Branch`; malformed JSON,
  missing records, null records, arrays, and scalar records terminate before any
  typed record read.
- Optional published and source-attribution helpers branch on explicit null,
  stage their typed values only on the object path, and preserve false-path
  termination. The root preserves the complete source, stages all record fields,
  calls both helpers and the accepted document decoder, regenerates through
  `EncodeRecordV1`, and sets validity only from exact canonical equality.
- Unreal centers pasted selections by bounding box. The original long root
  decoder placed its first setter 3,296 graph units from the native entry. The
  generator now folds only the root paste representation into alternating rows
  (49 nodes/179 pins, X span 0..1280) while leaving node identities, links, and
  the full semantic graph unchanged. Offline full/paste contracts passed before
  the compact body was attempted live.
- Compile/save succeeded through the remote Unreal API. All three compiled
  decoders re-exported at the exact expected sizes and passed again, including
  reconstruction of the source-derived `GetTypeString` node. Fresh exports of
  all eleven existing repository graphs also passed their core, document-codec,
  and record-encoder suites; no new crash or K2 compiler error was produced. A
  fresh `-ModDevKit -NullRHI` commandlet compiled all nine core assets with zero
  errors. Sync copied exactly the repository package, and live/mirror SHA-256 is
  `DBCCCACC223F164276AAE887C804CCEB2F9F30F399019302BF72B7DAFCD22B2B`.
- Next backend slice remains private create/save/load/list/delete followed by
  deterministic restart recovery. No cook and no polished UI yet.

## Repository semantic validators accepted live (2026-08-11)

- The live repository actor now contains complete `ValidateWaypointV1` (66
  nodes), `ValidateSegmentV1` (40), `ValidateDocumentV1` (47),
  `ValidateRecordPublishedV1` (18),
  `ValidateRecordSourceAttributionV1` (12), and `ValidateRecordV1` (47).
  Their generated full forms, compact paste forms, and all six exact Unreal
  round-trips pass the same semantic suite.
- `BlueprintEditorLibrary.get_basic_type_by_name("double")` is a trap in this
  Enhanced 5.6 build: the library logs an unrecognized primitive warning and
  silently returns an integer pin. The supported key for a Blueprint
  double-precision float is `"real"`, which exports
  `PinCategory="real",PinSubCategory="double"`. The repository configurator
  now validates exported basic pin types before adding any variable, and its
  schema contract forbids the incorrect key.
- Unreal silently omitted the generated `Max_IntInt` node from the first
  document paste even though the remaining body imported. The node-count gate
  caught the loss before compile. Document topology now uses an explicit
  boolean formulation: `(waypoints == 0 && segments == 0) ||
  (waypoints > 0 && segments == waypoints - 1)`. This is clearer, imports
  reliably, and covers empty documents without a fragile max node.
- Live reconstruction adds `AutogeneratedDefaultValue` fields. Contract code
  must match the exact comma-delimited `DefaultValue` field; substring matching
  can misclassify an autogenerated default as an authored rejection value.
- Acceptance order was enforced per function: paste, native entry connection,
  exact node-count export, hybrid live semantic suite, repository compile, API
  save, and a log interval with zero K2 warnings/errors. Final evidence is a
  fresh `-ModDevKit -NullRHI` cold compile with zero errors, full scaffold pass,
  and exact live/mirror SHA-256
  `AF95AA2E9DF5F3AFEC28307A0B441CE398E0D7FC5B3727385930A1F184C96E5B`.
- Blueprint validation now owns finite/domain-safe waypoint values, positive
  unique waypoint/segment IDs, exact adjacency, finite positive duration,
  required/versioned document metadata, exact accumulated duration,
  private/public policy, publication/revision rules, and clone attribution.
  Whitespace trimming and canonical/non-reversed UTC timestamps remain explicit
  gaps versus the Python oracle. Do not claim complete parity until those are
  enforced at this or a proven persistence boundary.
- Next backend slice is alternating-slot persistence and private CRUD/recovery.
  There is still no authorization to cook or begin the polished UI.

## Physical alternating-slot recovery contract closed (2026-08-11)

- The logical repository oracle previously modeled per-record generations while
  the accepted Blueprint adapter stores two complete repository snapshots. A
  dedicated physical-layout oracle now removes that ambiguity:
  `tools/persistence/alternating_snapshot_oracle.py`.
- Its 11 cases lock A/B alternation, positive monotonically increasing
  generations, uncommitted-candidate rejection, stage/commit failure isolation,
  deterministic Flypath/tombstone ordering, invalid-header rejection, and
  equal-generation split-brain rejection.
- Recovery is deliberately record-granular inside valid committed slot headers.
  A malformed newest record envelope can fall back to the older copy while
  unrelated valid new records survive. Tombstones are collected by generation
  before records are selected, so a newer committed tombstone masks every older
  record for that ID.
- Tombstone corruption is not treated like record corruption. An empty,
  whitespace-padded, or duplicate tombstone channel fails repository load
  closed; falling back would risk resurrecting a deletion. Blueprint recovery
  must preserve this distinction.
- Full scaffold passes at `0.36.0-snapshot-oracle-contract`. Next work is the
  modular Blueprint staging/selection/commit graphs and the native
  `GameplayStatics` SaveGame node seam, followed by private CRUD. No cook/UI.

## Repository persistence state graphs accepted live (2026-08-11)

- Checkpoint `0.37.0-persistence-state-contract` adds sixteen explicit scratch
  members to `BP_EDD_FlypathRepository`: existence, schema version, generation,
  committed flag, reserved snapshot hash, record envelopes, tombstone IDs, and
  derived header validity for each A/B slot.
- Four deliberately small functions are installed and accepted:
  `ResetRepositoryStateV1` 25 nodes, `ValidateStorageHeadersV1` 31,
  `PreparePersistenceCandidateV1` 14, and `CommitPersistenceCandidateV1` 10.
  Their compact paste bodies are respectively 24, 30, 13, and 9 nodes before
  connection to the native function entry.
- Boolean member getters do not expose a generic `ReturnValue` pin in copied
  Blueprint text. The deterministic generator therefore compares `Exists` and
  `Committed` explicitly to `true` with `EqualEqual_BoolBool`; never infer a
  value-pin name from arithmetic node conventions.
- The guarded installation cycle is now mandatory: exact function search,
  export the empty target and prove exactly one native entry, paste, export and
  prove exact node count, connect only the native entry edge, then run the live
  semantic contract. All four functions passed this cycle without omitted
  nodes or reroute insertion.
- Do not send multiline Python to Enhanced remote execution with literal `\\n`
  shell escaping. That form failed before mutation. The reusable
  `tools/unreal/Compile-And-SaveRepository.py` performs repository-wide compile
  and save with explicit markers and a checkable log interval.
- Repository-wide compile/save completed with zero Blueprint, K2 compiler, or
  SavePackage warnings/errors in its interval. All four graphs were re-exported
  and passed again after the save. The editor was closed through the guarded
  quit helper; a separate `-ModDevKit -NullRHI` process loaded and compiled all
  nine core assets with `EDD_COLD_LOAD|RESULT|PASS`, exit code 0, and zero
  errors. Known missing base-game DLC packages remain unrelated DevKit warnings.
- Sync copied exactly one package. Live and Git-mirror repository SHA-256 is
  `DCE427182D85FAECEEBB78B209A9DD5CF120689635D2F9ECDEA959E801596F88`.
- These graphs prove state transitions, not persistence I/O. Next: harvest and
  accept `DoesSaveGameExist`, `LoadGameFromSlot`, `CreateSaveGameObject`,
  `SaveGameToSlot`, the storage cast/property forms, then implement
  record-granular recovery and private CRUD. No cook or polished UI.

## Native repository SaveGame node forms accepted (2026-08-11)

- Internal checkpoint `0.38.0-savegame-node-forms` captures the exact Enhanced
  5.6 serialization of `DoesSaveGameExist`, `LoadGameFromSlot`,
  `CreateSaveGameObject`, and `SaveGameToSlot`. Contrary to a stock-UE
  assumption, all four expose `execute` and `then` pins in this DevKit build.
- `LoadGameFromSlot` returns base `/Script/Engine.SaveGame`. Dragging from that
  return to `Cast To SG_EDD_RepositoryStorage` automatically connected both the
  data pin and Load's completion pin. Both reciprocal links are now required.
- Selecting `SG_EDD_RepositoryStorage` on `CreateSaveGameObject.SaveGameClass`
  serializes the custom class default and specializes Create's return pin to the
  generated storage class. `SaveGameToSlot.SaveGameObject` remains base
  `SaveGame`, as expected.
- A typed `SG_EDD_RepositoryStorage` member was required to expose the object-
  targeted `RepositorySchemaVersion` getter and setter. When context-sensitive
  actions are absent, create/drag a typed object reference first and search from
  its output pin; do not guess a self-context node form.
- The 5-node native fixture and 9-node typed-storage fixture both compiled with
  zero Blueprint/K2 errors and now pass exact node, pin type/direction/default,
  specialized-class, cast, and reciprocal-link contracts in the full scaffold.
- Deleting the disposable probe in the same session failed safely because the
  editor transaction/clipboard retained it through `GCObjectReferencer`, even
  after its asset editor closed and Python released its direct reference. The
  guarded procedure is: quit cleanly, relaunch without opening the probe, delete
  immediately through `EditorAssetLibrary`, then guarded quit. That returned
  `EDD_SAVEGAME_NODE_PROBE|DELETED|True`; the package is physically absent.
- A post-cleanup `Sync-DevKitContent.ps1 -WhatIf` reported copied 0, unchanged
  17, conflicts 0. No runtime `.uasset` changed in this discovery slice.
- Next: generate, install, compile, and runtime-test the actual alternating-slot
  load/write adapter and record-granular recovery. Node-form acceptance alone is
  not disk persistence. No private CRUD, cook, or polished UI is claimed.

## Raw repository SaveGame readers accepted (2026-08-11)

- Internal checkpoint `0.39.0-savegame-read-adapter` connects the accepted
  Enhanced SaveGame forms into the read half of the physical adapter.
- `ReadRepositoryStorageSlotAV1` and `ReadRepositoryStorageSlotBV1` are each 19
  nodes/75 pins. Each performs existence -> load -> executed typed cast, then
  stages schema, generation, committed, reserved hash, record envelopes, and
  tombstones into its explicit slot channel. Missing-slot and cast-failure paths
  terminate without mutating another slot. A failed load leaves reset defaults
  and is rejected by later header validation.
- `ReadRepositoryStorageSlotsV1` is 5 nodes/13 pins and owns only
  `ResetRepositoryStateV1 -> Slot A -> Slot B -> ValidateStorageHeadersV1`.
  It does not choose authority, recover records, replace active memory, or set
  `RepositoryLoadedV1`; those are separate recovery contracts.
- The guarded install cycle caught two subtle editor hazards. A first paste
  overlapped the native entry and was undone before moving the entry and
  repasting. A first export contained only 18 nodes because the pasted body
  retained selection; clicking empty canvas before `Ctrl+A` restored the native
  entry to the export. Exact count plus entry-link contracts prevented both
  transient canvases from being accepted.
- Generator block discovery must anchor concrete `Begin Object Class` lines.
  Loose searches initially selected nodes merely linked to a Branch or Cast;
  the accepted generator anchors `K2Node_IfThenElse`, `K2Node_DynamicCast`, and
  `K2Node_VariableGet` explicitly.
- All three live exports passed semantic contracts before compile/save and
  again after Unreal reconstructed them. The marked compile interval had zero
  Blueprint/K2/SavePackage warnings or errors. A fresh `-ModDevKit -NullRHI`
  commandlet loaded all nine core assets and emitted
  `EDD_COLD_LOAD|RESULT|PASS` with zero errors.
- Sync copied exactly the repository package. Live and Git-mirror SHA-256 is
  `8A9882A355DFB2FA634E857AFC6D18E58AFF577117F38FC9DF862F938AC0B45F`.
- Next: deterministic authority selection and per-record corrupt-newest
  fallback, then the inactive-slot two-phase writer, then private CRUD. No cook
  or polished UI.

## Deterministic repository recovery ordering accepted (2026-08-11)

- Internal checkpoint `0.40.0-recovery-selection` adds eight compiled functions
  without conflating raw SaveGame reads with semantic record recovery.
- `ResetRecoverySelectionV1` is 22 nodes, `CompareRecoveryStringArraysV1` 14,
  `CompareEqualGenerationStorageV1` 17, A-only/B-only staging 14 each,
  A-newer/B-newer staging 15 each, and
  `SelectRepositoryRecoveryOrderV1` 23. Every native entry is reciprocally
  linked and every execution path is closed.
- Missing/invalid peers stage the sole eligible slot. Unequal generations stage
  newest then older. Exact ordered equality of both record and tombstone arrays
  accepts equal-generation peers with deterministic B-only tie-breaking.
  Divergence at the same generation fails closed with
  `ScratchRecoveryFailedV1=true` and
  `ScratchRecoveryDetailV1=DivergentEqualGeneration`.
- The contract parser must match authored `DefaultValue` as an exact serialized
  property. Substring matching can accidentally accept
  `AutogeneratedDefaultValue`; the accepted parser uses a comma-delimited exact
  property expression.
- Each empty function was first exported as a one-node native-entry baseline.
  Each pasted body was then manually linked, exported, and focused-contract
  tested. Two missed root drags were rejected immediately by the entry-link
  contract rather than inferred from the canvas.
- All eight live graphs passed together before compile/save and again after
  Unreal reconstruction. The marked compile interval contained no Blueprint,
  K2, SavePackage, warning, or error diagnostic. Guarded quit completed without
  a shutdown crash. A fresh commandlet loaded all nine assets and emitted
  `EDD_COLD_LOAD|RESULT|PASS` with zero errors.
- FromDevKit preview reported 16 unchanged assets and exactly one conflict.
  The reviewed force copied only
  `BP_EDD_FlypathRepository.uasset`; live and mirror SHA-256 is
  `92158F96ED04E3ABA8C23659945CF8A53310F7E771A1823C2D3D6F021A0314B4`.
- Next: validate/merge tombstones, recover records newest-first with per-record
  older fallback, and only then replace authoritative memory. The writer, CRUD,
  cook, and polished UI remain unimplemented.

## Repository tombstone recovery accepted (2026-08-11)

- Internal checkpoint `0.41.0-tombstone-recovery` adds four compiled functions
  after authority selection and before record-envelope recovery:
  `ResetRecoveryTombstonesV1` 16 nodes,
  `FindRecoveryStringIndexV1` 8,
  `ValidateRecoveryTombstoneChannelV1` 40, and
  `MergeRecoveryTombstonesV1` 22. Every native entry is reciprocally linked;
  full, paste, first live, and post-compile exports pass the same contracts.
- The reset owns only tombstone-merge scratch. It deliberately preserves
  `ScratchRecoveryFailedV1` and `ScratchRecoveryDetailV1`, so a prior
  `DivergentEqualGeneration` result cannot be erased by a later stage.
- Each selected channel rejects empty IDs, leading/trailing whitespace, and
  duplicates within that generation. Failure is monotonic and stable as
  `MalformedTombstone` or `DuplicateTombstone`; later loop iterations cannot
  overwrite the first failure.
- Newest tombstones are processed before older tombstones. A flypath deleted
  in both snapshots appears once and retains the newest deletion generation;
  disjoint older deletions are appended with their own generation. The two
  merged arrays are written in lockstep.
- The semantic oracle covers no selected slot, newest-only, disjoint snapshots,
  overlap/newer precedence, duplicate IDs in either channel, empty and padded
  identifiers, and preservation of a pre-existing split-brain failure.
- Enhanced exposes the required normalization operation as the pure native
  `KismetStringLibrary.Trim` node. Its exact two-string-pin serialization is
  captured in `repository-string-trim-node-form.eddgraph`; no guessed node form
  is used.
- The repeated focus/click/key/drag/wheel operations are now centralized in
  `Invoke-EnhancedEditorInput.ps1`. It validates the exact HWND and client
  coordinates before input. This converts the previously ad-hoc pin-linking
  seam into a small reusable operation while serialized reciprocal links remain
  the source of truth.
- The marked compile/save interval contained zero Blueprint, K2, FileManager,
  or SavePackage warnings/errors. Guarded quit reached `LogExit: Exiting.` A
  fresh `-ModDevKit -NullRHI` commandlet loaded all nine core assets and emitted
  `EDD_COLD_LOAD|RESULT|PASS` with zero errors.
- FromDevKit preview reported 16 unchanged assets and exactly one reviewed
  conflict. The forced sync copied only the repository package. Live and mirror
  SHA-256 is
  `CB46362D20BE8E12C2D7F7A04D984E1ABD23B8419D35370CD23BC793FA9F5B70`.
- Next: recover record envelopes newest-first with per-record fallback to the
  older snapshot, apply tombstone masks, and commit authoritative memory only
  after the complete candidate validates. Writer, CRUD, cook, and polished UI
  remain pending.

## Repository record recovery accepted (2026-08-11)

- Internal checkpoint `0.42.0-record-recovery` adds nine compiled functions:
  `ResetRecoveryRecordsV1` 19 nodes,
  `DecodeValidateRecoveryEnvelopeV1` 7,
  `ScanRecoveryRecordIdentityV1` 20,
  `AppendRecoveryRecordIfNewV1` 23,
  `TryMergeRecoveryRecordV1` 23,
  `RecoverRecordChannelV1` 19,
  `RecoverRepositoryRecordsV1` 20,
  `CommitRecoveredRepositoryV1` 20, and `LoadRepositoryV1` 6.
- Recovery uses two passes per selected snapshot. Pass one decodes and validates
  identities and marks same-generation duplicate IDs ambiguous. Pass two skips
  ambiguous or invalid envelopes and merges valid records newest-first. This
  permits an ambiguous or corrupt newest record to fall back to an older valid
  envelope without allowing one duplicate to win by array order.
- Tombstone masks are generation-aware: a tombstone at the same or newer
  generation suppresses a record, an older tombstone cannot suppress a newer
  record, and records already recovered from the newest snapshot cannot be
  replaced by the older snapshot.
- Recovered envelope, ID, owner, visibility, and updated-time arrays are
  appended in lockstep. `CommitRecoveredRepositoryV1` copies them and the
  merged tombstones into authoritative state only while recovery remains
  failure-free; `RepositoryLoadedV1` is set last.
- The semantic oracle covers newest-only, disjoint snapshots, newest-wins,
  corrupt-newest fallback, duplicate ambiguity fallback, all tombstone
  generation relations, duplicate-only omission, and metadata alignment.
  Generated full/paste graphs, initial live exports, and all nine post-compile
  exports pass the same contracts.
- Windows can return false from `SetForegroundWindow` even after an activation
  request. `Invoke-EnhancedEditorInput.ps1` now attaches input threads when
  necessary and validates the actual foreground HWND. The new
  `Export-BlueprintFunctions.ps1` opens exact functions through My Blueprint,
  exports exact node counts, and fails closed on graph identity.
- Compile/save returned true and its marked interval contained no Blueprint,
  K2, FileManager, or SavePackage diagnostics. Guarded quit reached
  `LogExit: Exiting.` A fresh nine-asset commandlet emitted
  `EDD_COLD_LOAD|RESULT|PASS` with zero errors.
- FromDevKit preview reported 16 unchanged assets and exactly one reviewed
  repository conflict. Forced sync copied that package only. Live and mirror
  SHA-256 is
  `8B9E3DE940835A2442911A3A84559EF461214DD4D0E154D096582A8F1DA833FF`.
- Next: inactive-slot two-phase writer, then private create/save/load/list/delete.
  Ownership, privacy/publication/cloning, cinematic tracks, cook, and polished
  UI remain pending.

## Two-phase persistence writer accepted (2026-08-11)

- Internal checkpoint `0.43.0-persistence-writer` adds five compiled functions:
  `ResetPersistenceWriteV1` 5 nodes,
  `BuildPersistenceWriteStorageV1` 19,
  `StagePersistenceWriteV1` 8,
  `CommitPersistenceWriteV1` 10, and `PersistRepositoryV1` 9.
- The caller prepares and validates its copy-on-write candidate before invoking
  the writer. The writer never calls `PreparePersistenceCandidateV1` itself,
  because doing so after CRUD mutation would overwrite the candidate.
- The typed storage object is populated uncommitted and saved to
  `CandidateTargetSlotV1`; the same object is then marked committed and saved to
  the same slot. Authority is promoted only after both saves return true.
  Create/stage/commit failures keep authority unchanged and emit stable
  `PersistenceUnavailable` details.
- Full and paste generators, exact first-live exports, and exact post-compile
  exports pass the same structural and semantic contracts. The semantic oracle
  covers create, stage, and commit failure plus successful promotion.
- Compile/save returned true with no Blueprint/K2/FileManager/SavePackage
  diagnostics. Guarded quit was clean; a fresh nine-asset commandlet emitted
  `EDD_COLD_LOAD|RESULT|PASS` with zero errors.
- A controlled executable probe spawned the real compiled repository actor,
  changed prior authority generation 41 to candidate 42, called
  `PersistRepositoryV1`, and verified all three physical-write flags plus the
  exact committed Unicode payload. A second fresh Unreal process read the same
  payload and removed the isolated automation slot. Native SaveGame failure
  injection remains covered by the semantic oracle because the DevKit exposes
  no safe `SaveGameToSlot` failure seam.
- `Invoke-EnhancedEditorInput.ps1` previously called `ShowWindow(...,
  SW_RESTORE)` on every focus request. That silently unmaximized Blueprint
  windows and invalidated known coordinates. It now checks `IsIconic` and only
  restores minimized windows; maximized placement is preserved and enforced by
  the scaffold source contract. Editor input uses client coordinates, while
  screenshot crops are physical pixels; `ClientToScreen` measured an `-8,-8`
  client origin in this layout, so pin centers require the corresponding offset.
- FromDevKit preview found 16 unchanged assets and exactly one reviewed
  repository conflict. Forced sync copied only that package. Live and mirror
  SHA-256 is
  `F25458BC4D3B0FB7EF962A970FE39F42882606AF9453E09A6423BC8DF1C153DE`.
- Next: private create/save/load/list/delete using the accepted writer. No cook
  and no polished UI.

## Owner-only private draft load accepted (2026-08-11)

- Internal checkpoint `0.44.0-private-draft-load` implements the first private
  CRUD boundary: `LoadDraftV1` is 34 nodes and returns a typed draft only after
  derived-ID lookup, exact owner-account authorization, strict record decoding,
  and semantic record validation. Stable failures are `NotFound /
  FlypathNotFound`, `Forbidden / OwnerRequired`, `ValidationFailed /
  StoredRecordDecodeFailed`, and `ValidationFailed / StoredRecordInvalid`.
- The first generated draft duplicated the owner-array link because
  `ValidationBuilder.array_item()` already wires its source. Enhanced compiled
  the paste but reported `failed building connection with 'Replace existing
  input connections' at Get (a copy)`. The explicit second `bp.connect` was
  removed and every contract now rejects duplicate `(node,pin)` links on any
  pin. Never infer compile success from `save_asset=True`; scan the marked
  compile interval for Blueprint/K2 errors.
- The executable probe then found a real stale-data privacy bug: scalar result
  channels reset, but `ResultDraftDocumentV1` survived a successful load and
  remained readable after a later wrong-owner request. The shared
  `ResetRepositoryResultV1` is now 10 nodes and resets the typed document before
  clearing metadata. The same runtime probe now passes missing, wrong-owner,
  corrupt-envelope, valid-owner, and denial-after-success cases on the real
  compiled repository actor.
- Runtime fixtures must use the shipped Blueprint `EncodeRecordV1` output.
  Python-oracle JSON is semantically equivalent but PlayFab preserves insertion
  order, while strict Blueprint decoders require byte-canonical order. Build the
  typed document through its full user-defined-struct field GUIDs, invoke the
  Blueprint encoder, and feed that exact envelope into runtime acceptance.
- The Blueprint editor and Conan main editor are separate top-level windows in
  the same Unreal process. In this run the Blueprint HWND was `27265536` and the
  Conan main HWND was `44239610`; using the process main-window handle caused
  mouse actions to land behind/outside the graph and clipboard copies to become
  no-ops. Enumerate visible process windows by title and target the exact
  Blueprint HWND. Client origin measured `-8,-8`; convert physical screenshot
  pin centers to client coordinates accordingly. Every edit still requires an
  immediate exact graph-name/node-count export and reciprocal-link contract.
- Generated full/paste graphs, exact live and post-compile exports, duplicate
  link regression, clean marked compile/save, the five-case compiled-actor
  runtime probe, guarded quit, and fresh-process cold load all pass. FromDevKit
  preview reported 16 unchanged assets and one reviewed repository conflict;
  forced sync copied that package only. Live and mirror SHA-256 is
  `0FA85E9243035AF70AE311CC10B1406AFFF6E959422B42E90D10D3E97B38B0CD`.
- Next: private create, save, list, and delete on the accepted writer. No cook
  and no polished UI.

## Private-by-default Flypath creation accepted (2026-08-11)

- Internal checkpoint `0.45.0-private-flypath-create` implements
  `CreatePrivateFlypathV1` as a 113-node/422-pin compiled function (112/421
  body-only). The server-staged `RequestFlypathIdV1` is deterministic and
  collision-checked; creation fixes owner, `private` visibility, created/updated
  time, draft revision 1, no published snapshot, and no source attribution.
- The graph validates required scalar inputs, title length, allowed region,
  owner count, complete record semantics, and serialized-size policy. It encodes
  the record, prepares the copy-on-write candidate, appends the envelope, calls
  the accepted two-phase writer, and changes active envelopes/derived indexes
  only after `ScratchPersistenceCommitSavedV1`. Typed errors leave authority,
  result envelope, and revision channels unchanged.
- Generation is deterministic at the persistence boundary: the first accepted
  create committed generation 1 to `EDD_Repository_A`; the second retained the
  first record and committed generation 2 to `EDD_Repository_B`. Both returned
  revision 1 and stable indexes 0 then 1. Reusing the first ID returned
  `AlreadyExists / FlypathIdCollision` without advancing generation.
- The compiled-actor executable suite passed invalid owner and ID, title limit,
  region policy, pre-existing collision, owner limit before/after commits, and
  serialized-size rejection. Every rejection proved unchanged authoritative
  arrays and no physical SaveGame before the success cases. Both new records
  were private, owner-a could immediately load them through `LoadDraftV1`, and
  owner-b received `Forbidden` without an envelope or revision.
- A clean editor shutdown was followed by a separate `-ModDevKit -NullRHI`
  process. It recovered generation 2/slot B, exact ID/owner/private/timestamp
  order, loaded both revision-1 drafts for owner-a, denied owner-b, and then
  deleted both A/B fixtures. A second fresh cold-load commandlet loaded and
  compiled all required assets and emitted `EDD_COLD_LOAD|RESULT|PASS`.
- Python assignment to arrays inside Unreal user-defined structs is not a safe
  typed Blueprint fixture boundary: raw `[]` values can lack the native array
  identity expected by Blueprint, and nested struct mutation may read back in
  Python while Blueprint receives the prior native value. Valid document
  fixtures must round-trip through the shipped Blueprint encoder/decoder.
  Negative document semantics remain enforced by generated/live graph contracts
  and the engine-independent oracle; executable runtime negatives use reliable
  scalar request boundaries unless a Blueprint-native fixture producer exists.
- The serialized-size graph uses `KismetStringLibrary.Len`; this is a tested
  UTF-16 code-unit ceiling, not exact UTF-8 byte accounting. The conservative
  storage limit plus strict title limits keep version-1 records far below the
  boundary. Do not describe it as cryptographic or byte-exact integrity.
- Generated full/paste graphs are byte-deterministic. The exact post-compile
  live export hash is
  `66C27F151BDB6570DE079C9B0AFD0438966C8C8C72552CA5E9037A5597EE0EFA`.
  FromDevKit preview reported 16 unchanged assets and exactly one reviewed
  repository conflict; forced sync copied only that package. Live and mirror
  repository SHA-256 is
  `6FBB5204F23C6FDC113C50B335F89A2BACC3FF6EFB47FD17CFDC796F858237FC`.
- Next ordered private CRUD slice: `SaveDraftV1` with owner authorization,
  optimistic revision conflict, atomic candidate replacement, real SaveGame
  restart evidence, cleanup, regression, commit, and push. No UI, cook, or
  Workshop work.

## Owner-only optimistic private draft saving accepted (2026-08-11)

- Internal checkpoint `0.46.0-private-draft-save` implements `SaveDraftV1` as
  a 98-node/382-pin compiled function (97-node body-only). It resolves the
  derived record index, enforces the derived and decoded owner identities,
  strictly decodes and validates the stored record, compares the caller's
  expected revision, rebuilds the request document with server-forced
  `current+1`, validates/encodes the updated record, replaces exactly one
  candidate envelope, and invokes the accepted two-phase writer.
- Executable proof caught three defects which structural shape alone had not:
  the valid-index result was initially disconnected from the found branch;
  `PersistRepositoryV1` reset `ResultRecordIndexV1` before the post-commit
  derived update; and the pure `current+1` node reevaluated after staging,
  reporting one revision too high. The permanent contracts now require the
  found condition link, pre-writer `ScratchIndexV1` cache/post-writer restore,
  and success outputs sourced from the already-staged authoritative revision
  and document rather than mutable pure recomputation.
- The compiled-actor suite passed a private revision-1 fixture, missing ID,
  wrong owner, optimistic conflict with current-revision disclosure, blank
  timestamp, waypoint ceiling, region mismatch, serialized ceiling, two
  successful saves, immutable ID/owner/title/visibility/creation/publication/
  attribution preservation, stale-write rejection, owner-only reload, and the
  exact committed physical payload. Rejections proved unchanged generation,
  slot, envelopes, tombstones, and derived indexes.
- Deterministic progression was `revision 1 / generation 1 / slot A`, then
  `revision 2 / generation 2 / slot B`, then `revision 3 / generation 3 /
  slot A`. After guarded editor exit, a fresh commandlet recovered revision 3,
  denied the wrong owner, rejected stale expected revision 2 without mutation,
  resumed at revision 4/generation 4/slot B, verified the committed physical
  payload, and deleted both A/B fixtures.
- A separate fresh `-ModDevKit -NullRHI` process loaded all nine core assets,
  compiled every Blueprint, emitted `EDD_COLD_LOAD|RESULT|PASS`, and reported
  zero errors. Exact post-compile SaveDraftV1 export SHA-256 is
  `2873CEEA9250D963FC2E89EF4204523F991492B92FA3C83C43218E7174938347`.
  FromDevKit preview found 16 unchanged assets and exactly one reviewed
  repository conflict; forced sync copied only that package. Live/mirror
  repository SHA-256 is
  `5057B36DD2347F0DF51DEA3B938874EC2A61B00353801F9F94D58422EF45D879`.
- Next ordered private CRUD slice is owner-filtered private listing. No UI,
  cook, or Workshop work.

## Owner-filtered private metadata listing accepted (2026-08-11)

- Internal checkpoint `0.47.0-private-list` implements `ListMineV1` with two
  private helpers: `CompareStringsOrdinalV1` and `EncodeMetadataV1`. Enhanced's
  pasted `Array_Sort` form was rejected at compile time, so ordering uses a
  contract-tested ordinal comparator built from `GetCharacterAsNumber` and a
  deterministic insertion pass. The stable order is `updatedUtc` descending,
  then `flypathId` descending for equal timestamps.
- The accepted list graph filters only by the derived owner-account index,
  validates parallel index alignment before reading rows, clamps offset to zero
  and limit to `[1,100]`, strictly decodes only selected owner rows, confirms
  decoded/index identity, and emits an exact nine-field metadata envelope. It
  never returns the owner account ID, description, draft document, or published
  document. Any selected-record decode/identity failure clears the entire page.
- Executable runtime proof caught a real missing edge that graph-size and broad
  shape checks had missed: `RequestLimitV1` was not connected to the lower-bound
  predicate, so every request collapsed to one row. The generator now connects
  that exact pin and the contract requires the reciprocal link. The corrected
  compiled graph returned four rows for `limit=1000` with safe limit 100 and
  passed low/high clamps, middle/beyond pages, timestamp ties, owner isolation,
  public/private metadata, published/unpublished metadata, foreign corruption,
  selected corruption, identity mismatch, index misalignment, authority
  immutability, and physical SaveGame immutability.
- The full compiled runtime order was
  `owner-z-tie, owner-a-tie, owner-middle, owner-old`. A separate canonical
  writer fixture committed two private records to generation 2/slot B. After a
  guarded editor exit, a fresh `-ModDevKit -NullRHI` process recovered the A/B
  state, listed `create-runtime-b` then `create-runtime-a`, proved exact private
  metadata and wrong-owner emptiness without writes, and deleted both fixtures.
  A second fresh commandlet loaded and compiled every required asset and emitted
  `EDD_COLD_LOAD|RESULT|PASS`.
- Clipboard exports must click a canvas point known not to overlap a Boolean
  checkbox in folded graphs. `Export-BlueprintFunctions.ps1` uses the explicit
  safe point `(1300,740)` for these captures; the older default `(900,500)` can
  silently toggle a node default before copying. Native entry seams are wired
  only after hover tooltips prove both endpoints are `Exec`, followed by exact
  node-count export and reciprocal-link contracts.
- Exact post-compile SHA-256 values are
  `4471F2239DFE16D76AFDB908F9C3C05647FCD72C54F08A70031DC8EB2313781E`
  (`CompareStringsOrdinalV1`),
  `D19DD3729FE8CC6340E8206FF43CD9B4A43159798A405EAC1096FA55FF5DF673`
  (`EncodeMetadataV1`), and
  `791167C439ECD31FFE35B1E5424C341718E60E0E4447B40082A07522E21E26B5`
  (`ListMineV1`). The closed-editor FromDevKit sync copied exactly one package;
  live and mirror repository SHA-256 is
  `6360F36C3FC2EA620514595F4DFD55CAE30FBF6C94C0F90A17366C1CE2CE65A4`.
- Next ordered private CRUD slice is owner-only private delete through the
  accepted tombstone/persistence boundary. No UI, cook, or Workshop work.

## Owner-only optimistic private delete accepted (2026-08-12)

- Internal checkpoint `0.48.0-private-delete` implements `DeleteFlypathV1` as
  a 64-node live function. It resets results, resolves the derived index,
  caches that index privately, immediately sanitizes the public result index,
  then authorizes the exact owner before decoding any stored envelope. The
  decoded ID/owner and parallel derived arrays must agree before the optimistic
  expected-revision check is allowed to disclose the current revision.
- The mutation is copy-on-write: `PreparePersistenceCandidateV1` clones active
  state, the cached index is removed from the candidate record array, the ID is
  appended to the candidate tombstone channel, and `PersistRepositoryV1` calls
  the accepted two-phase writer. Only its committed-success branch removes the
  same cached index, in order, from all four derived arrays. Rejections and
  failed persistence therefore cannot alter authoritative in-memory state.
- The first executable run caught a real result-hygiene bug: the shared lookup
  helper exposed its found index to wrong owners. Graph v2 now copies the index
  to `ScratchIndexV1` and clears `ResultRecordIndexV1` to `-1` before any found,
  authorization, decode, or revision branch. The semantic contract requires
  those exact reciprocal links and execution order; the corrected runtime proves
  missing ID, wrong owner, blank owner, stale revision, corrupt envelope,
  decoded/index identity mismatch, and repeat delete are mutation- and
  SaveGame-free with all non-conflict result payloads cleared.
- Successful runtime deletion removed only fixture A, committed generation 3 to
  slot A, retained fixture B, aligned every derived index, and persisted the A
  tombstone. Owner load, list, and repeat-delete boundaries agreed immediately.
  After guarded editor shutdown, a fresh `-ModDevKit -NullRHI` process recovered
  generation 3/slot A, proved A remained deleted and B loadable/listed, deleted B
  through the compiled function, committed generation 4 to slot B with no
  records and ordered tombstones `[A,B]`, reloaded that state, proved both IDs
  absent and the owner list empty, then removed both acceptance slots.
- Exact compile/save log interval `2013..2021` contained the marked begin/save/
  end sequence with `SAVED|True` and zero errors. The exact post-compile graph
  SHA-256 is
  `C0CDE0523650BC3B93A54081B497A46FB506CBDC7A44300EF5EFE3C21F2EF854`.
  A separate fresh commandlet loaded all nine required assets, compiled every
  Blueprint, emitted `EDD_COLD_LOAD|RESULT|PASS`, and reported zero errors.
- Closed-editor FromDevKit preview found 16 unchanged assets and exactly one
  reviewed repository conflict; forced sync copied only that package. Live and
  mirror repository SHA-256 is
  `F9D40D02D107353C8FDB3CD7ECBC563E8B61F6760A108CA2052187C4A043F970`.
- A folded delete layout placed a node under the list-era `(1300,740)` export
  point; selection there silently captured the wrong count. The verified blank
  canvas point for this function is `(600,700)`. As with prior seams, hover both
  endpoints until their tooltips say `Exec`, wire once, export the exact node
  count, and require reciprocal-link contracts before compiling.
- Private create/load/save/list/delete is now accepted backend work. The next
  ordered slice is publication and sharing policy—not UI, cook, or Workshop.

## Owner-only optimistic publication accepted (2026-08-12)

- Internal checkpoint `0.49.0-publish-draft` implements `PublishDraftV1` as an
  88-node/337-pin compiled function (87-node body-only). It resolves and caches
  the derived record index, sanitizes the public result index before every
  authorization branch, authorizes the exact owner before decode, validates the
  decoded/index identities, and applies optimistic concurrency against the
  current draft revision.
- Publication is an immutable snapshot operation, not a draft save. The current
  draft document is copied into `PublishedDocument`, published revision is set
  equal to the current draft revision, `HasPublishedRevision` becomes true,
  visibility becomes `public`, and the server timestamp is updated. The draft
  revision and draft document do not advance. The staged record must validate,
  encode, and satisfy the serialized ceiling before one copy-on-write candidate
  envelope is replaced and passed to `PersistRepositoryV1`.
- Only `ScratchPersistenceCommitSavedV1` promotes derived visibility/timestamp
  and restores the success result envelope, cached index, current revision, and
  typed draft. The writer-failure branch has no links. Every rejection proved
  unchanged authoritative arrays and byte-for-byte unchanged physical A/B slot
  snapshots; non-conflict rejections clear envelope, metadata, revision, index,
  and typed-draft result channels.
- Executable in-process acceptance passed NotFound, wrong owner, blank owner,
  stale expected revision, blank timestamp, corrupt stored envelope,
  decoded/index identity mismatch, serialized-size ceiling, first publication,
  an intervening `SaveDraftV1`, republish, stale republish, and exact metadata.
  The intervening save advanced draft revision 1 to 2 while the published
  revision and typed published document remained at revision 1; republish moved
  only the public snapshot to revision 2. Deterministic authority progression
  was create `1/A`, first publish `2/B`, draft save `3/A`, republish `4/B`.
- After guarded editor shutdown, a separate `-ModDevKit -NullRHI` process
  recovered generation 4/slot B and the public revision-2 snapshot. It loaded
  the owner draft and metadata, saved a materially different 44-second draft as
  generation 5/slot A while proving the published zero-second revision-2
  snapshot remained unchanged, then republished it as generation 6/slot B,
  reloaded the exact physical payload, and deleted both acceptance slots. A
  second fresh commandlet loaded all nine required assets, compiled every
  Blueprint, and emitted `EDD_COLD_LOAD|RESULT|PASS` with zero errors.
- Deterministic generated graph SHA-256 values are
  `989AA13496DDE86412229A03A4C1E2DF3B0EA04FB7F8BED6D236CCB5E727764B`
  (full) and
  `8D95F18A1EB0C2CA60C4429652D23680D63FE2388E48570E89F824DA6D31BDC5`
  (paste). Exact post-compile export SHA-256 is
  `FDB762F3291BB043C4E50CAB1E034A55BA55D73BB3664C75FC3A53E31444B08E`.
  Closed-editor FromDevKit preview found 16 unchanged assets and one reviewed
  repository conflict; forced sync copied only that package. Live and mirror
  repository SHA-256 is
  `54B609B2665180D66B2BC878125FDB15238D59E4EFBE1412DFCC3F2E07AAB08B`;
  the reverse diff check reported 17 unchanged assets and zero conflicts.
- Publication's folded layout uses verified blank export point `(500,750)`.
  The exact reciprocal native-entry link and post-compile graph contracts are
  the authoritative seam proof; do not spend repeated editor cycles chasing a
  tooltip when exact export already proves both ends of the link.
- Next ordered sharing slice is owner-only unpublish, followed by public
  discovery, immutable published fetch, and private clone with attribution. No
  polished UI, cook, or Workshop work begins at this checkpoint.

## Owner-only history-preserving unpublish accepted (2026-08-11)

- Internal checkpoint `0.50.0-unpublish` implements `UnpublishV1` as an
  85-node compiled function (84-node paste body). It applies the same
  owner-first authorization, strict stored-record identity, optimistic draft
  revision, result sanitation, serialized-size ceiling, and copy-on-write A/B
  persistence boundary as publication.
- Unpublish changes only `visibility` to `private` and the server-owned update
  timestamp. It deliberately does not clear `HasPublishedRevision`, does not
  alter `PublishedRevisionNumber` or `PublishedDocument`, and does not advance
  or replace the private draft. The staged record is revalidated and encoded
  before one candidate envelope is replaced; derived visibility/timestamp and
  success results change only after `ScratchPersistenceCommitSavedV1` is true.
- The executable runtime oracle created revision 1 privately (`1/A`), published
  it (`2/B`), saved a materially different 22-second revision-2 draft (`3/A`),
  and proved the original zero-second published snapshot was unchanged. It then
  passed mutation-free NotFound, wrong-owner, blank-owner, stale-revision,
  blank-timestamp, corrupt-envelope, decoded/index mismatch, and serialized-size
  rejection cases with clean result payloads and byte-identical physical slots.
- The first accepted unpublish committed `4/B`, made metadata private, retained
  draft revision 2 plus published revision 1, and retained the original
  published payload. Republish committed `5/A` and promoted the 22-second
  revision-2 snapshot; a second unpublish committed `6/B` while retaining that
  snapshot. After guarded shutdown, a fresh `-ModDevKit -NullRHI` process
  recovered private generation 6/B, owner-loaded and listed it, republished to
  `7/A`, unpublished to `8/B`, reloaded the exact physical payload, and removed
  both acceptance slots.
- Deterministic generated SHA-256 values are
  `15587C052DCE11ABB67A46AD7FF2A967422100A9F232AFB4F682AFD131A0345F`
  (full) and
  `42D9BB2F699E27AB13F7B604F178B40804497F1C3145467DB65B72DFFF5715BE`
  (paste). Exact post-compile export SHA-256 is
  `9E21EC9C78239B2CB4B721D7E4D89F9D24ECBC1640BDF3AECA97279AB6F85F58`.
  Live and closed-editor mirror package SHA-256 is
  `86DA629F0C695EF422CFD93A9CAF065F02FD47A4BA4A257FEBE8F6E305EE5369`.
  A separate cold commandlet loaded all nine required assets, compiled every
  Blueprint, emitted `EDD_COLD_LOAD|RESULT|PASS`, and reported zero errors.
- Interactive remote automation is now provisioned without preference-window
  navigation. The effective config owner is
  `[/Script/PythonScriptPlugin.PythonScriptPluginSettings]` in the project's
  generated `WindowsEditor/Engine.ini`; the similarly named user-settings
  section and `EditorPerProjectUserSettings.ini` do not enable the endpoint.
  `Enable-EnhancedEditorRemoteExecution.ps1` idempotently preserves unrelated
  section values while enforcing Epic's local defaults; its automated fixture
  regression also covers missing sections and rejects duplicate sections or
  required keys. A live editor then
  advertised exactly one `ConanSandbox` node and executed a marked command.
  `Get-EnhancedEditorWindows.ps1` and `Save-WindowScreenshot.ps1` make window
  selection and endpoint inspection explicit instead of rebuilding fragile
  one-off UI probes.
- Public discovery is the next ordered sharing slice, followed by immutable
  published fetch and private clone with attribution. No polished UI, cook, or
  Workshop work begins at this checkpoint.

## Bounded metadata-only public discovery accepted (2026-08-12)

- Internal checkpoint `0.51.0-public-discovery` adds compiled `ListPublicV1`
  as a 145-node query. Its generator transforms the accepted `ListMineV1`
  graph, retaining one implementation lineage for ordinal sorting, paging,
  selected-record decoding/validation, metadata encoding, and atomic failure.
  The transform removes requester input entirely and replaces owner filtering
  and authorization with derived-plus-decoded public visibility checks.
- Public results are deterministically ordered by `(updatedUtc, flypathId)`
  descending, offsets are clamped nonnegative, limits are clamped to 1..100,
  and every page reports total/offset/has-more without carrying draft or
  published documents, descriptions, or durable owner account IDs.
- Executable acceptance created five records through `CreatePrivateFlypathV1`,
  published three through `PublishDraftV1`, and hid one through
  `UnpublishV1`. It proved exact ordering, low/high clamps, middle and
  beyond-end pages, metadata shape, private-row non-disclosure, ignored corrupt
  private payloads, atomic selected-public decode and identity failures,
  derived-private hiding, aligned-index failure, and byte-identical authority
  plus physical A/B SaveGame state around every query.
- A fresh `-ModDevKit -NullRHI` process recovered generation 9/A, returned
  exactly the two still-public records in deterministic order, repeated the
  read-only physical-state proof, and cleaned both acceptance slots. A separate
  cold process loaded and compiled all nine core assets with
  `EDD_COLD_LOAD|RESULT|PASS`.
- Deterministic graph hashes are
  `E3797B800A32BE951BC7BD6EF4C6827745B3A28D2020ED38A34F0AD035E29473`
  (full) and
  `2615D6840B5ABF8FEF71718ECD02CF7F2F9A1819ABBD089BD5C431733079F06E`
  (paste). The exact post-compile live export hash is
  `97DDF84500DF12EBBD4A2818EEC57B4F601A8091E8B49785652A038E965A7879`;
  synchronized live/mirror package hash is
  `ED905741A83736ADBD16E3C661C3560958DE349AFFE0C95772227C21D40DBDFB`.
- Immutable published playback fetch is the next ordered backend slice,
  followed by private clone with attribution. No polished UI, cook, or Workshop
  work begins at this checkpoint.

## Immutable published playback fetch accepted (2026-08-12)

- Internal checkpoint `0.52.0-published-fetch` adds compiled
  `FetchPublishedRevisionV1`. Request revision `0` selects the current published
  snapshot; a positive revision must match exactly; a negative revision returns
  `ValidationFailed|InvalidPublishedRevisionRequest`. Private derived rows are
  hidden as `NotFound|FlypathNotFound` before record decoding.
- The query validates the selected envelope, record identity, decoded public
  visibility, published-state flag, and document/revision consistency. It
  returns only `ResultPublishedDocumentV1`, `ResultCurrentRevisionV1`, and
  `ResultHasCurrentRevisionV1`; it cannot return the record envelope, private
  draft, or owner ID and has no writer/persistence call path. The shared result
  reset now clears the published document as well, preventing stale payload
  disclosure after a later denial.
- Live runtime proved private hiding, latest and exact fetch, immutable playback
  after a materially different private save, negative/wrong/missing revisions,
  corrupt public storage, derived-private hiding, and selected-row index
  misalignment. It left a generation-3/slot-A fixture. A fresh headless process
  recovered it, proved the published snapshot immutable and the query read-only,
  proved stale-payload reset, then cleaned both A/B slots. A separate fresh
  process loaded and compiled every core asset with `EDD_COLD_LOAD|RESULT|PASS`.
- Deterministic graph hashes are
  `8CC6C608E0C818AD54D88A05CD0398ACD3C12FDCF3FAABBD2E78BC6BD2ABEA5E`
  (full) and
  `965276E6DC279C19A7382A71AA36457EE75D7CD8ABD343868D4DB02AFD1846BE`
  (paste). Exact post-compile live hashes are
  `EB707AA6F4D01FE9177A5365B520B3EDACA6400ACD5CAD72E7D58A43D0EF927C`
  for fetch and
  `4EE6A9504F754118EF939E05DDA85BFB07925D66BD8F247E38FEF0705685FE26`
  for shared result reset. The synchronized package hash is
  `3F0E53730C3E072C89DD14B238D2D26439531F45C59B9BAED36D8CD08C3182C6`.
- The full scaffold caught an obsolete deterministic baseline for
  `FindRecordIndexV1` after the reset graph gained one node. Regenerating the
  checked-in full/paste helper snippets restored byte determinism; all semantic
  contracts and the complete regression then passed. This is a tooling-hygiene
  correction, not a runtime behavior change.
- Private clone with attribution is the next ordered backend slice. No polished
  UI, cook, or Workshop work begins at this checkpoint.

## Private published clone with attribution accepted (2026-08-12)

- Internal checkpoint `0.53.0-private-clone` adds compiled
  `ClonePublishedV1`. The request names a logical requester, an exact positive
  published source revision, a collision-checked target ID, title/description,
  and timestamp. The source must pass aligned-index, decode, record,
  decoded-public, publication, exact-revision, region, and waypoint checks.
- Success deep-rebuilds the immutable published document as a revision-one
  private draft with an empty content hash. The target is owned only by the
  requester, has no published snapshot, and stores immutable source
  ID/revision/title/creator attribution captured before scratch reuse. The
  accepted copy-on-write A/B writer is the sole mutation boundary.
- Executable acceptance proved all blank inputs, zero/negative source
  revisions, title/region/waypoint/owner/serialized-size limits,
  missing/private/corrupt/misaligned sources, exact-revision conflict, and
  target collision. Every rejection preserved byte-identical authority and
  physical SaveGame snapshots and cleared stale results.
- The successful clone was deterministically appended as the second record at
  generation 6/B, private by default, owned by player B, revision 1, and copied
  the published duration-22 snapshot rather than the newer private draft.
  Owner-only load, owner listing, public-list exclusion, full attribution, and
  source-edit independence passed. A fresh process recovered generation 7/A,
  repeated those boundaries, edited the clone to revision 2 at generation 8/B,
  proved the source draft and published snapshot unchanged, and cleaned both
  test slots.
- A separate fresh commandlet loaded and compiled all core assets with
  `EDD_COLD_LOAD|RESULT|PASS`. The complete scaffold, deterministic generation,
  schema/oracle suite, live round-trip contract, repository budget, and exact
  17-file source mirror pass. Deterministic SHA-256 values are
  `5FA3022F03D45745BDB87D7DBE0DC974E8FD9B604D1E9A6A7F9ABEC459E1B984`
  (full) and
  `32D0E885A9D4D2614A60ECD5370674E791A031EA8762EF7408579272783F79EE`
  (paste); the post-compile live export is
  `693944A85CA50DBADD7350D39662A3EDB31BFFEA7A71C1EBF57F00C3B57E07CF`.
  Live/mirror package SHA-256 is
  `9392FCE07AE4F3CB0E5148219BFCAF9A77F52560AAD15100C24C80B3A9118411`.
- Unreal omits an explicit `DefaultValue=""` token for an empty string pin
  after paste/export. Contracts accept that native omission as empty while
  still rejecting non-empty hashes. Screenshots remain navigation evidence;
  the exact exported reciprocal graph is authoritative. No polished UI, cook,
  or Workshop work begins at this checkpoint.

## Cinematic position/timing oracle frozen (2026-08-12)

- `tools/trajectory/cinematic_reference.py` freezes the next Blueprint slice
  before graph construction. Version 1 supports deliberate `linear` space and
  bounded `auto_cinematic` quintic space, plus `linear`, `smoothstep`,
  `smootherstep`, seventh-order `cinematic_s_curve`, `accelerate_through`, and
  `brake_into` monotonic distance profiles.
- Auto-cinematic segments share velocity and zero acceleration at compatible
  joins for C2 continuity. Component-wise monotonic limiting stops an axis when
  adjacent secants reverse or one side is flat; this deliberately favors no
  loop/overshoot over forcing nonzero fly-through motion at incompatible exact
  corners. Later persisted corner modes may explicitly select a different
  tradeoff.
- Arc tables use a deterministic six-level sampling floor plus bounded adaptive
  geometric refinement. The floor is required because a spatially straight
  quintic may still have nonlinear parameter speed even when chord error is
  zero. Distance inversion uses ordered cumulative samples and local linear
  interpolation.
- Sixteen executable contracts cover exact endpoints, C2 derivatives,
  reverse-corner stop, per-axis local bounds on adversarial fixtures, 100 seeded
  randomized paths, finite/bounded tables, zero-length stability, approximate
  constant-distance traversal, all timing presets, direct-scrub/frame-rate
  independence, deterministic compilation, and invalid/non-finite rejection.
  The complete project scaffold and repository budget remain green. This is a
  reference checkpoint only; compiled Blueprint parity is the next gate.

## Cinematic scalar Blueprint evaluators accepted (2026-08-12)

- Internal checkpoint `0.54.0-trajectory-scalars` adds compiled and saved
  `EvaluateTimeProfileV1` and `EvaluateQuinticScalarV1` to
  `BPC_EDD_ClientDirector`. The first supports `linear`, `smoothstep`,
  `smootherstep`, `cinematic_s_curve`, `accelerate_through`, and `brake_into`;
  the second evaluates the clamped quintic Hermite value plus first and second
  derivatives from six boundary scalars.
- Enhanced 5.6 exposes no scalar `IsFinite` function through the reflected
  Blueprint API. The initially plausible predicate `x - x == 0` passed the
  serialized interpreter but failed compiled runtime because optimization made
  NaN appear valid. The accepted finite predicate is
  `-1.7976931348623157e+308 <= x && x <= 1.7976931348623157e+308`. It rejects
  NaN and both infinities in actual compiled Blueprint bytecode.
- Deterministic full graph hashes are
  `81E387C80A5A69BEFD1640488DD5B5AF74B62D83948BA3296C526A7B5E940C09`
  (time, 67 nodes) and
  `12BF3BBD889BC5C5D78CC954301AF76DAB80CCD2A7EA47FA054231697D50B8FE`
  (quintic, 117 nodes). Exact post-compile live exports are
  `6DEEB5194F4AC8792B2EDB3863428BCA1C9030ACE223F0D28320A40DBD20F30D`
  and
  `6C3F9380E0B9069CBFCF09130E0D58D56760EC214C6319E087446CCACB224DA2`.
  Both post-compile graphs retain their exact node counts, reciprocal native
  entry seams, executable contracts, and zero `K2Node_Knot` nodes.
- Live compiled execution passed 48 supported time-profile cases, five invalid
  profile/non-finite cases, 69 deterministic quintic fixtures, and all 21
  combinations of NaN/positive infinity/negative infinity across the seven
  scalar inputs. Every invalid case reset stale outputs and validity; the
  validator restored every staged CDO property in `finally`.
- Guarded editor quit completed cleanly. A fresh `NullRHI` commandlet repeated
  the same 48/5/69/21 runtime evidence from the saved package, and the separate
  cold asset-load suite returned zero errors. Closed-editor mirror preview
  found 16 unchanged files and only the reviewed Client Director conflict;
  forced sync copied exactly one package, then all 17 files were unchanged.
  Live/mirror package SHA-256 is
  `7171DE5393C1F2F466B9769FC5EA673208FCC4ECA6AD378948911CB13768C48C`.
- Blueprint Assist can inject reroute nodes when a dense graph is active during
  formatting/compile. One unsaved quintic graph grew from 117 to 171 nodes;
  diagnostic export proved all 54 extras were `K2Node_Knot`. The accepted
  recovery is wholesale replacement from the deterministic paste graph,
  native-entry reconnection, exact export validation, then switching to a small
  function such as `EnterDroneMode` before compile. Never accept screenshots or
  visual plausibility in place of the exact post-compile export.
- Complete scaffold regression passes, including deterministic repeat
  generation, full and paste executable interpretation, all existing backend
  contracts, and the 17-file source mirror. This accepts only the scalar
  trajectory kernel; vector position composition and quaternion orientation are
  the next ordered backend work. UI, cook, and Workshop remain out of scope.

## Compiled quintic vector composition accepted (2026-08-12)

- Internal checkpoint `0.55.0-trajectory-vector` adds the compiled and saved
  `EvaluateQuinticVectorV1` wrapper on `BPC_EDD_ClientDirector`. Six native
  vector boundary members are split into X/Y/Z, evaluated through the accepted
  scalar quintic kernel with one shared alpha, staged in nine scalar scratch
  members, and committed atomically as position plus first and second
  derivatives only after all axes report valid.
- Native Blueprint member creation must use
  `/Script/CoreUObject.Vector` with `get_struct_type`. Passing the primitive
  name `vector` to `get_basic_type_by_name` is unsupported in Enhanced 5.6 and
  silently defaults to integer. The failed configuration process never saved;
  the corrected process verified every native vector default before saving.
- The deterministic source graph is 78 nodes/296 pins and the entryless paste
  body is 77 nodes/295 pins. Full and paste forms pass 103 valid and all 57
  non-finite-placement executable fixtures. The exact Unreal post-compile
  export remains 78 nodes, has a reciprocal native entry seam and zero
  `K2Node_Knot` nodes, and has SHA-256
  `788DAB6DDEDA3CBE9865AE50C2DC935AB40E5AFDAD98639166652293167039A9`.
- Live compiled runtime passed 67 deterministic/boundary vector trajectories.
  Of 57 attempted non-finite placements, all 39 values that reached Blueprint
  were rejected with cleared outputs. Enhanced's Python property bridge
  sanitized the other 18 non-finite native-vector components to finite values
  before Blueprint execution; the permanent harness reads properties back and
  reports those cases separately. The independent serialized-graph interpreter
  still exercises and rejects all 57 placements. Both live and fresh NullRHI
  runs restore every touched class-default property in `finally`.
- Guarded editor quit completed cleanly. A separate NullRHI process loaded and
  compiled every core asset with zero errors, and another fresh process repeated
  the exact 67/39/18/PASS runtime markers. Closed-editor mirror preview found
  16 unchanged assets and only the reviewed Client Director conflict; forced
  sync copied exactly one package, after which all 17 files were unchanged.
  Live and mirror package SHA-256 is
  `A6F5EBEECD1D5536194A9B33DE2CFA4E439AF25F0C72AFC0CB88D2B6D44D7057`.
- This accepts vector position composition, not the complete trajectory engine.
  Quaternion orientation is the next ordered backend slice. Segment/route
  compilation, arc-length inversion, runtime shortcut dogfood, UI, cook, and
  Workshop remain out of scope.

## Compiled spherical quaternion evaluator accepted (2026-08-12)

- Internal checkpoint `0.56.0-trajectory-quaternion` adds compiled
  `EvaluateSphericalBezierQuaternionV1` on `BPC_EDD_ClientDirector`. It validates
  finite normalized start/control/control/end quaternions plus finite alpha,
  clamps alpha, evaluates spherical cubic Bezier through six native
  `Quat_Slerp` calls, and commits identity/false on every invalid path.
- Enhanced exposes native unsplit `Quat_IsFinite`, `Quat_IsNormalized`,
  `Quat_Normalized`, and `Quat_Slerp`. Preserve those exact live node forms;
  split quaternion pins remain unsafe. The deterministic full/paste hashes are
  `D0C92616DCBE270AC452FD921057C20F90B6F90E844399F4E227FC5B848C4E39`
  and `47CCEEF27EFCADE2DE9E400273C982772FA988E0E1E48A67A0B968CCF542AB60`.
  Exact post-compile live export is 37 nodes/zero knots with SHA-256
  `C40E040DF53B116293A3897C0E5C0C294F3C8D4A34EAD8D76B26932AD8C315E8`.
- All three serialized graphs pass 707 frozen-oracle valid evaluations and all
  19 invalid/non-finite placements, including fail-closed stale-output proof.
  Warm and fresh NullRHI compiled runtime independently repeat 707/19 with zero
  reflection sanitization and restore every touched CDO property. Separate cold
  loading compiles all six core Blueprints without errors.
- Finicky seam lesson: native function entry and the first pasted setter can
  overlap while appearing connected. Exact export caught an entry bypass that
  would have leaked stale quaternion output. Move only the native entry, use
  modifier-held Alt-click to break links deterministically, then accept only the
  reciprocal entry -> identity reset -> validity reset chain. Unreal may
  canonicalize identity as either `0, 0, 0, 1` or
  `(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)`; executable contracts support
  both exact serializations.
- Closed-editor mirror copied exactly the changed Client Director package;
  live and mirror SHA-256 is
  `8DF4A13DD0BE7742821CA844FB33CE47785AD2AE3087D07C585C7349BE99FF0A`.
  The disposable JSON node probe was deleted in a fresh commandlet.
- This accepts one quaternion segment evaluator, not the whole trajectory
  engine or mod. Next is the time-aware multi-key quaternion control compiler,
  followed by segment/route and arc-length integration. UI, cook, and Workshop
  remain out of scope.

## Atomic orientation track publication accepted (2026-08-12)

- Internal checkpoint `0.63.0-orientation-track-commit` adds compiled
  `CommitCompiledOrientationTrackV1` to `BPC_EDD_ClientDirector`. It begins by
  clearing all compiled arrays, total/validity, and evaluation outputs. Only a
  complete candidate with exact array cardinalities, two or more keys, finite
  positive durations/total, exact cumulative starts, and an exact accumulated
  final total is published. Failure leaves no stale or partial compiled track.
- Deterministic full/paste graphs contain 85/84 nodes; the exact post-compile
  live export contains 85. Full, paste, and post-compile contracts assert the
  native entry seam, six resets, full validation chain, sticky-false failure,
  duration loop, and all six publication copies.
- Warm and fresh NullRHI compiled runtime each publish 48 seeded candidates
  with component-exact waypoint/control copies (`0.0` maximum publication
  error), exact duration/rate/start/total copies, and complete evaluation-result
  reset. Eleven malformed cases cover prior-invalid state, duration/tangent/
  start/start-control/end-control cardinality, first and late start corruption,
  wrong and non-finite total, and zero duration. All clear compiled/evaluation
  state, set stage false, and restore every touched CDO property afterward.
- Exact export caught the pasted graph's disconnected native entry before any
  compile/save. The visible Clear chain was internally connected, but the
  entry itself was not. Zoom the whole graph, locate the small purple entry and
  the first Clear, wire the single exec seam, then re-export and require the
  85-node contract. Spatial proximity is never acceptance evidence.
- Guarded shutdown emitted `EDITORS_CLOSED|0` and `LogExit: Exiting`; reverse
  sync copied exactly ClientDirector (16 unchanged). Live/mirror package
  SHA-256 is
  `BD82BF4AE047A4BBE2E365CDBDD6AB393E2AE65F6F5383D6DF3F0AA4D95A6BF8`.
  Fresh runtime and cold compilation of all core assets pass. This accepts only
  atomic publication; ordered orchestration and absolute-time evaluation remain.

## Ordered orientation track compilation accepted (2026-08-12)

- Internal checkpoint `0.64.0-orientation-track-compile` adds compiled
  `CompileOrientationTrackV1`. It is deliberately thin: one native entry and
  seven self calls, strictly reset -> validate -> align -> forward deltas ->
  tangent rates -> segments -> commit. Source/paste/exact post-compile graphs
  contain 8/7/8 nodes, and the exact contract proves the complete reciprocal
  exec chain with no bypass.
- Warm and fresh NullRHI runtime each compile 64 seeded oracle tracks, prove
  replacement of an earlier compiled track, reject eight malformed inputs, and
  clear all stale compiled arrays, total, validity, and evaluator outputs.
  Hardened fresh acceptance additionally compares every tangent-rate component:
  maximum quaternion/control angular error is `2.475566823160076e-7` radians;
  maximum tangent component error is `1.0380794996933673e-6`. Full CDO restore
  passes.
- The native entry's tiny exec pin was unreliable at 1:1 zoom. Move only the
  entry through an empty lane, then connect the seam at whole-graph overview
  zoom and export immediately. Compile only after the exact 8-node reciprocal
  contract passes. Switch the active editor tab to a small function before
  compile to avoid dense-graph formatting side effects.
- Guarded exit, reverse sync, fresh runtime, and cold compilation of all core
  assets pass. Live/mirror Client Director SHA-256 is
  `D2962520E15F52A6993B3BB3274935EB75A6DBF3ED5915A38D1B026FBBC71CA7`.
  Absolute-time orientation evaluation remains next; no UI, cook, or Workshop.

## Absolute-time orientation track evaluation accepted (2026-08-12)

- Internal checkpoint `0.65.0-orientation-track-evaluation` adds compiled
  `EvaluateCompiledOrientationTrackV1` to `BPC_EDD_ClientDirector`. It resets
  all public and primitive results before work, validates the compiled boundary,
  chooses segments from absolute elapsed time, clamps negative scrubs to alpha
  zero, emits the exact final key at/after total time, and delegates spherical
  interpolation to the already-accepted quaternion primitive.
- Deterministic source/paste graphs contain 113/112 nodes. The exact live graph
  before and after compile is 113 nodes, zero reroutes, and SHA-256
  `479AAE1B581E65D5EA72002D24E1CC3E61A709D5DCE300B9ADCA45462266C770`.
  The executable contract proves the reciprocal native entry seam, atomic reset,
  cardinality/finite guards, first-match segment selection, completion branch,
  staged primitive call, success publication, and every fail-closed path.
- Warm and fresh NullRHI compiled runtime each pass 32 seeded tracks and 3,016
  oracle evaluations spanning negative time, every key boundary, near-boundary
  values, mid-segment samples, completion, and random scrubs. Thirty-two shuffled
  history-independence probes repeat exactly. Maximum angular error is
  `3.2917740992269735e-7`; maximum alpha error is `0.0`.
- Nine malformed compiled-state cases reject prior invalidity, every compiled
  array cardinality family, zero total, and a selected zero-duration segment.
  NaN, positive infinity, and negative infinity all reach Blueprint and reject.
  Every rejection clears stale public and primitive outputs; every run restores
  all touched CDO properties.
- Exact live export caught the disconnected native entry before compile. Its
  coordinates were moved through an empty lane with per-drag clipboard identity
  checks, aligned beside the first reset, then connected once and immediately
  re-exported. `CloseMainWindow()` again reported success without exiting; the
  proven `Quit-EnhancedEditorSafely.py` closed the asset editor and exited in
  seconds. Use safe quit directly after remote sessions instead of waiting on
  the ineffective window-close request.
- Closed-editor reverse sync copied exactly Client Director (16 unchanged).
  Live/mirror package SHA-256 is
  `DF6C28E9FD6314B88F82994200F237E862C12657E5F14B29F7C5002193AA733E`.
  Fresh runtime, cold compilation of every core asset, and full scaffold pass.
  Next is position-route composition and adaptive arc-length compilation; no UI,
  cook, or Workshop.

## Quaternion orientation controls accepted (2026-08-12)

- Internal checkpoint `0.57.0-orientation-compiler` adds compiled
  `ComputeOrientationLogDeltaV1`, `ComputeOrientationTangentRateV1`, and
  `BuildOrientationSegmentControlsV1` to `BPC_EDD_ClientDirector`. Quaternion
  values remain native Quats; logarithmic deltas and angular rates use Vectors.
  Controls are built through native `Quat_SetComponents` scratch variables and
  `Quat_Exp`, avoiding the invalid reflected Make Quat struct node.
- Exact post-compile graphs contain 26, 85, and 76 Blueprint nodes. Their
  SHA-256 values are `AB16B8F030C7CE3495896ED27CBCEF5525F34A360F5B0FC2433B2FB2FA303FCD`,
  `BA229EB5F9CA1131C508CC005B3414E3B75CAE0E2F2BC567715CD51BC115B708`,
  and `3E9B94DE0259675272D976F1FE74176227F230C665F8E8BA83CE25B185171A78`.
  Full and paste executable contracts pass 554 valid plus 18 invalid fixtures;
  the exact post-compile exports repeat the full suite.
- Warm and fresh compiled execution pass 142 valid and 16 invalid cases with
  stale-output clearing and full CDO restoration. Maximum observed errors are
  `1.6038519136203196e-07` (log Vector),
  `9.356918024671317e-13` (tangent Vector), and
  `2.7236137991954443e-07` radians (control Quat). The `1e-6` runtime tolerance
  is therefore a measured engine-precision boundary, not an algorithm waiver.
- Pure Blueprint math is eagerly evaluated. A conditional scale expression
  still emitted divide-by-zero warnings on a zero tangent, so the accepted
  denominator is `magnitude + 1e-12`; the semantic zero path stays exact and
  the warning disappears. A synthetic `Max_DoubleDouble` retarget was rejected
  during paste; reuse a known serialized arithmetic form instead of inventing
  an unproven function reference.
- Graph movement is now bounded and observable through
  `Move-SelectedBlueprintNode.ps1`: it reads the selected node back after every
  grid-aligned drag, requires convergence, and can require a stable node marker
  so overlapping nodes cannot silently transfer selection. Move native entries
  into an empty lane before connecting them; never drag them through the dense
  computation field.
- Coordinate-based search failed after the saved layout changed: text was typed
  into the graph and created one unsaved comment. The transaction was undone,
  exact 26/85/76 exports proved restoration, and the durable path is now
  `Open-BlueprintFunctionViaFindResults.ps1`, which explicitly submits the Find
  Results query and opens the exact result. Do not use the older fixed search
  coordinates on this layout.
- Compile/save, warm runtime, guarded editor exit, exact post-compile contracts,
  closed-editor mirror equality, fresh NullRHI runtime, and cold core-asset load
  all pass. Live/mirror Client Director SHA-256 is
  `71EFD4779C6B526C9E006664B0E9C852A446A9188CF16BA39D82AA7D57793952`.
  This completes only the per-segment control primitives. Multi-key assembly,
  route/arc-length integration, cinematic tracks, keyboard dogfood, UI, cook,
  and Workshop remain out of scope.
## Arc-table inversion primitive accepted (2026-08-12)

- Internal checkpoint `0.66.0-arc-table-inversion` adds compiled
  `InvertArcLengthTableV1` to `BPC_EDD_ClientDirector`. It validates the exact
  published cumulative-table representation before performing a bounded
  linear scan and local interpolation. Zero length, plateaus, clamped alpha,
  stale outputs, and history-independent direct scrubbing are explicit.
- Deterministic full/paste graphs contain 98/97 nodes. The exact post-compile
  export has 98 nodes, zero knots, reciprocal native-entry/reset wiring, and
  SHA-256 `AE4FED2A84AFFE02845607918AC54AF9AEECF08C3089187639FBB1FC209FE4D7`.
  Warm and fresh compiled runtime each pass 4,266 valid evaluations over 195
  actual compiled segments, all 16 malformed families, and one shuffled scrub
  proof with exactly `0.0` maximum `u` error and full CDO restoration.
- Pasted Blueprint bodies are translated as a block. Here the generated reset
  at `(256,1760)` landed at `(-4768,1504)`, while the native entry remained at
  `(-64,1760)`. Do not infer the seam offset from generator coordinates. Export
  the live graph, parse both exact positions, then move the verified sole
  `K2Node_FunctionEntry` through an empty lane to 256 units left of the live
  reset. Require the complete reciprocal graph contract before compile.
- Live/mirror Client Director SHA-256 is
  `EB2BE085DDA0693CFB5AEA0003EE9FFD542F0B6EEA967FAA031A2431526BF727`.
  Fresh runtime and cold compilation pass. Adaptive table construction and
  position-route integration remain; UI, cook, and Workshop are still out of
  scope.

## Adaptive arc construction boundary accepted (2026-08-12)

- Internal checkpoint `0.67.0-adaptive-arc-boundary` freezes a bounded iterative
  construction oracle equivalent to the recursive reference across more than
  200 seeded segments. Version 1 rejects non-finite controls, non-positive
  tolerance, depth outside 1..12, and operation budgets outside 1..8191 or
  exhausted before completion.
- `ResetAdaptiveArcBuildV1` clears ten work/candidate/published arrays and
  twelve scalar fields before any build. `ValidateAdaptiveArcBuildInputsV1`
  stages the six quintic controls and alpha 0.5 through the accepted
  `EvaluateQuinticVectorV1` primitive, then applies the scalar and budget
  bounds. Linear/cinematic selection does not weaken validation.
- Deterministic source graphs are 33/32 reset nodes and 36/35 validation nodes
  in full/paste form. Exact post-compile live exports remain 33 and 36 nodes,
  with SHA-256 `907E4C3E47DE96F0D8948C3322D69941BA647A3D69F9F1B50AF1D9874A055337`
  and `A561FEF4334A1E1F4A984F97E6ECC0759C0D0FF630956C8ACF3F2D06E344F3C9`.
- Warm and fresh NullRHI runtime prove all 22 reset fields, 64 valid seeded
  inputs, eight invalid scalar/depth/operation families, stale validity
  replacement, and full CDO restoration. Enhanced reflection sanitizes each of
  the 18 NaN Vector-component placements before Blueprint receives them;
  the harness detects and reports those separately instead of claiming an
  unexecuted invalid-vector path.
- Clipboard paste translated each graph body away from its native entry. Exact
  exports identified the real first reset nodes; the verified sole native entry
  was routed through empty space and joined once. A failed guarded move can
  still move a node before detecting selection transfer, so export immediately,
  undo once, and re-run the exact contract. Never infer the seam from the node
  that merely looks nearest.
- Enhanced's exposed Python graph API can add/find/remove/rename graphs but does
  not expose protected node arrays or a safe pin-link operation. The disposable
  reflection probe was removed. Editor input remains bounded by exact export,
  class/marker guards, reciprocal graph contracts, compile/save, and compiled
  runtime proof.
- The input helper now supports bounded pre-drag hold and pre-release dwell.
  This improves node/pin drag reliability without weakening post-action proof.
  Fixed-coordinate graph exporters remain unsafe after layout changes; open the
  exact function through Find Results.
- Live and mirrored Client Director packages are byte-identical at SHA-256
  `539401B52E672CDBE272AED19F76604C4BD36221F686182A1289814A2B37CE9A`.
  Initialization, iterative processing, atomic publication, and the thin
  orchestrator remain. No UI, cook, or Workshop work has started.

## Adaptive arc initialization accepted (2026-08-12)

- Internal checkpoint `0.68.0-adaptive-arc-initialization` compiles
  `InitializeAdaptiveArcBuildV1`. It always clears all five stack arrays and
  three candidate arrays, operation count, and candidate length before gating
  on prior stage validity. A valid stage seeds the single root interval and the
  `(u=0, position=start, distance=0)` candidate; invalid prior state stays false
  and exposes no partial work.
- Deterministic full/paste graphs contain 31/30 nodes with hashes
  `47CE7E54D70DC14870B2B1BF7CCA9F635FB195F1A838277A629851C8DA696A21`
  and `E1918C08B091B52965D494A33F66C1FEF5A20231D192964F62A1DCD6D3C4E801`.
  Exact post-compile live graph is 31 nodes with SHA-256
  `C83A1D3552320793ABDBDC8D78B9D9BD07AD8BBF8E6E0A76857EB7871070663A`.
- Warm and fresh compiled runtime each pass 64 randomized start/end pairs and
  one invalid-prior-stage case, proving exact stack/candidate replacement,
  sticky failure, and complete default restoration. Cold compilation of all
  core assets passes. Live/mirror package SHA-256 is
  `FA73C614869EA9B18831C072527A2BCDA9DD68AB69B32C22D604453875E567EC`.
- The guarded entry move caught a real selection transfer into a variable
  getter. One bounded undo restored the exact graph, export proved the entry at
  `(-1904,-608)`, and a shorter collision-free route aligned it at
  `(-1904,224)`, 256 units left of the true first clear. The single pin drag
  used bounded hold/release dwell and the immediate 31-node contract passed.
- Unreal canonicalizes zero `Array_Add.NewItem` defaults by omitting the
  `DefaultValue` field. Exact contracts must treat omission as the type's zero
  only where the generator explicitly requires zero. Bounded stack processing,
  commit, and orchestration remain; no UI, cook, or Workshop.

## Adaptive arc bounded processing accepted (2026-08-12)

- Internal checkpoint `0.69.0-adaptive-arc-processing` compiles and saves
  `ProcessAdaptiveArcBuildV1`. One bounded ForLoop consumes the synchronized
  five-array interval stack, evaluates the midpoint through the accepted
  quintic-vector primitive, selects the linear midpoint only for linear input,
  refines right-then-left to preserve recursive left-first LIFO order, and
  appends accepted `u`, position, and cumulative-distance samples.
- Deterministic full/paste graphs contain 119/118 nodes with SHA-256
  `6F34719F13EF4D6391FA5ED7E8E30A53ABD4E933D8F2C9F8CDFCDB8DA708C479` /
  `B47CA5C7D282199A3EAB48547E1B46DFF71E484343D0068CA4F1E573C19F2984`.
  The exact post-compile graph contains 119 nodes with SHA-256
  `9E0FAA811EF5B8AF149F1AA8BA8B3B361B857DFC54C5AAB1C5E17983722E1524`.
- Warm and fresh compiled runtime each pass 23 deterministic linear/cinematic
  cases, 1,017 exact oracle samples, operation counts up to 127, exact-budget
  success, one-short budget exhaustion, all eight array-cardinality
  malformations plus prior-invalid state, sticky failure, and full CDO
  restoration. A separate fresh process loads and compiles every core asset;
  the complete scaffold passes.
- Pure `Array_Length(U0) - 1` is reevaluated between impure nodes. Removing U0
  first shrank the array and changed later remove indices to `-1`. The accepted
  pop transaction removes U1, P0, P1, and Depth before removing U0 last. The
  exact contract fixes this order; never treat a pure Blueprint value as an
  eager snapshot across mutations unless it is explicitly staged.
- The initially pasted current-value setters overlapped the root branch/loop,
  making the native seam unreliable. The generator now places those setters in
  a separate lane, and its exact contract rejects any variable-set collision
  with the root or loop. A duplicate `Array_Add.NewItem` source, a wrong result
  property name, and a Vector multiply default serialized as a Vector instead
  of scalar were likewise caught before acceptance.
- Removing and adding the same function graph through Enhanced's Python API in
  one command invalidates the live tab and can return a falsey add. Use separate
  remote transactions. `reload_packages(..., ASSUME_POSITIVE)` safely restored
  the last saved package after a known bad unsaved graph. Prefer direct
  `BlueprintEditorLibrary.compile_blueprint` over an ambiguous toolbar click.
- The disposable JSON probe was deleted through `EditorAssetLibrary`, guarded
  shutdown ended at `LogExit: Exiting.`, FromDevKit copied exactly Client
  Director (16 unchanged), and reverse preview found all 17 assets unchanged.
  Live/mirror Client Director SHA-256 is
  `581544AF09F830B2BD2945E0DF332088DF9DC63D10C0B24C1E4AEED2A1059A40`.
  Next is atomic candidate publication in `CommitAdaptiveArcBuildV1`; no UI,
  cook, or Workshop.

## Adaptive arc atomic publication accepted (2026-08-12)

- Internal checkpoint `0.70.0-adaptive-arc-publication` compiles and saves
  `CommitAdaptiveArcBuildV1`. It first clears both published arrays, published
  length, and public validity. Publication then requires sticky stage success,
  all five work stacks empty, exact candidate cardinalities, at least two
  samples, finite nonnegative length, exact `(0,0)..(1,length)` endpoints,
  strictly increasing `u`, and nondecreasing cumulative distance.
- Full/paste graphs contain 95/94 nodes with SHA-256
  `7F70F61C4EEA81206ED32C21BC7923B8AF806D2C6902D1ECB843C7E666731F8E` /
  `425910293A83F5754CFA48AA43DD29A10EBEC23076A7161CD8A2C05DCDE38011`.
  The exact post-compile 95-node graph has SHA-256
  `69FFF166DFE3351919D3A28C5700AE0EECBE148DC92B00EA27EC45E9EFD03E71`.
- Warm and fresh compiled runtime each publish 32 seeded oracle tables with
  exact `u`, distance, and length copies. Nineteen failures cover false prior
  stage, each nonempty work stack, too few samples, both candidate-cardinality
  mismatches, all four endpoint/length corruptions, negative/non-finite length,
  duplicate `u`, decreasing distance, and non-finite interior values. Every
  failure clears a poisoned prior publication, makes stage validity false, and
  restores all CDO properties afterward.
- The empty native function retained its entry when the validated paste body
  replaced its old selection, so the first live export correctly contained 95
  nodes rather than the 94 pasted nodes. Exact export proved only the reciprocal
  entry seam missing. The guarded mover placed the verified entry at
  `(-3696,208)`, 256 units left of the first clear, one measured pin drag joined
  it, and the complete contract passed before compile.
- The runtime harness initially used obsolete `CompiledSegment` keyword names;
  it failed before Blueprint execution and still restored state. Align harness
  fixtures with the frozen oracle dataclass, and do not classify setup failures
  as Blueprint failures or successes.
- Guarded shutdown reached `LogExit: Exiting.`; FromDevKit found exactly Client
  Director changed (16 unchanged), reverse preview found all 17 assets equal,
  and fresh NullRHI runtime plus cold compilation passed. Live/mirror Client
  Director SHA-256 is
  `99BACEF4455F43FB0321F294BD13FC8C7743BA2D6693C6EBF8FBA7B32FC64055`.
  Next is the five-stage `BuildAdaptiveArcTableV1` orchestrator; no UI, cook,
  or Workshop.

## Ordered adaptive arc compilation accepted (2026-08-12)

- Internal checkpoint `0.71.0-adaptive-arc-compiler` adds compiled
  `BuildAdaptiveArcTableV1`. Its only executable path is reset -> validate ->
  initialize -> process -> commit, so invalid inputs and exhausted budgets
  cannot bypass reset or expose an intermediate candidate.
- Deterministic full/paste graphs contain 6/5 nodes with SHA-256
  `1E298C4807518EDB97AB587DD632823CFB9C2164E50C75153B13F883A08C7429` /
  `FD55E8E2CE0B5E835DDD07361CEE043BA072FEE25F71A786A4BA3AD8038F1034`.
  The exact post-compile six-node graph has SHA-256
  `1CCCA47D53B3FE0AC439735384A3B86147BFA66CD7E2913C3F10A30A9601D7CD`.
  All three exact contracts prove the complete reciprocal execution chain.
- Warm and fresh NullRHI runtime each compile 32 seeded linear/cinematic
  tables, replace an earlier valid result, reject six scalar/depth/budget
  cases including a one-operation-short request, clear every public channel on
  rejection, match exact operation counts, and restore every touched CDO
  property. Maximum distance and length errors versus the double-precision
  oracle are `1.08002496e-12` and `6.82121026e-13`.
- The first orchestrator harness incorrectly required Python-double identity
  for distances stored by Blueprint. The accepted lower-level boundary already
  owns a strict `3e-4` float tolerance. The corrected end-to-end harness keeps
  exact cardinality, ordering, operation, failure, replacement, and restoration
  assertions, reports the measured maximum error, and rejects any error above
  that established boundary. A test's numeric representation must match the
  runtime contract; an impossible assertion is not stronger evidence.
- Guarded exit reached `LogExit: Exiting.`. Closed-editor FromDevKit preview
  found 16 unchanged assets and only Client Director changed; the reviewed
  copy moved one package. Reverse preview with the absolute project root found
  all 17 assets unchanged. Live/mirror Client Director SHA-256 is
  `433A3461D56686AB539033201F58E5E4D4F8FAAFC73DAF64E3CBEA9915E75565`.
  Fresh runtime, cold load of all nine core assets, and compilation of all six
  Blueprint assets pass. Position-route integration is next; no UI, cook, or
  Workshop.

## Position-route reset accepted (2026-08-12)

- Internal checkpoint `0.72.0-position-route-reset` introduces the separated
  candidate/compiled/evaluation storage contract and compiles
  `ResetPositionRouteCandidateV1` on Client Director. The function clears 18
  arrays and resets 14 scalars, including stale validity and evaluation output,
  without touching the eight authored/evaluation inputs.
- Deterministic full/paste graphs contain 51/50 nodes with SHA-256
  `324E152D111E86C432CB80876307CE73DC6F2139B01CEC5B704AEDC1DEB00C1D` /
  `AC382699DE96DFFBE94CC1742585FE51EE33AB6EE1BF7660CCA641B90AB8B2AB`.
  The exact post-compile 51-node export has SHA-256
  `D93A4110F2306910E75403A0B130D1BA00C5A283992C105C2468EDC64417D2B9`.
- Warm and fresh compiled execution each prove 18 empty arrays, 14 exact scalar
  defaults, eight preserved inputs, two idempotent calls, and complete CDO
  restoration. Fresh cold load independently loads all nine core assets and
  compiles all six Blueprint assets. Live and normal Git mirror match at
  SHA-256 `FEC775EF7C15449B3170FBA9967326B4BA1823FF295D947FF0131FC1B6152B3E`.
- Enhanced's graph surface ignored absolute-cursor `SetCursorPos` movement while
  dragging at this zoom/state. Raw relative `mouse_event(MOVE)` deltas moved the
  selected native entry reliably; the guarded mover now uses that primitive and
  still requires exact clipboard position/marker readback after every attempt.
  The entry moved to `(-5776,-224)`, 256 units left of the first clear, and one
  measured pin drag created the reciprocal native seam.
- The DevKit-created `KitContent` directory sits inside the mod root and must
  never be recursively mirrored as authored mod content. The sync helper now
  scopes transfer to root `modinfo.json` plus the `Local` asset tree. Its
  reverse preview reports the expected 17 unchanged files, and the accidental
  untracked nested duplicate was removed after hash verification.
- This accepts only the reset transaction. Input validation is next; no UI,
  cook, Workshop, or complete-route claim is implied.

## Position-route input validation accepted (2026-08-12)

- Internal checkpoint `0.73.0-position-route-validation` compiles
  `ValidatePositionRouteInputsV1`. It validates 2..512 waypoint positions,
  exact per-segment duration/curve/profile cardinality, finite positions,
  positive finite durations/tolerance, depth 1..12, operation budget 1..8191,
  `linear`/`auto_cinematic` geometry, and all six proven timing profiles.
- Validation resets stage validity false, accepts only after every shape and
  scalar setting passes, then uses four bounded ForEach loops. Per-position
  finiteness is delegated to the proven quintic-vector primitive; time-profile
  recognition is delegated to the proven timing primitive. Any element failure
  only writes false, so a later valid element cannot heal an earlier rejection.
- Full/paste graphs contain 72/71 nodes with hashes
  `80DA4C892A9973BEF8DD945911994114CFEF081CCB96AFC444EF747F68659E73` /
  `B281119C47B854CEE39727F2F3A5FD79C52FFE43382B54CEC445D1600EB7BC4E`.
  Exact post-compile graph SHA-256 is
  `45969BA00C0E662A2958D73DBC4F0710E62528BE0BAE7679D724334C6146D0AD`.
- Warm and fresh NullRHI runtime each pass five valid cardinalities including
  512 waypoints and reject 28 malformed cases. Enhanced reflection sanitized
  all 12 injected NaN Vector-component cases before the graph received them;
  the harness reports that boundary explicitly. Full CDO restoration passes.
- Opening the function initially targeted the main editor HWND even though the
  Blueprint lives in its own 1800x1000 top-level window. Export failed safely
  with map text/empty clipboard. Enumerate windows and use the exact titled
  Blueprint HWND; after that the one-node empty export, paste, guarded entry
  move, reciprocal seam, compile/save, and post-compile contract all passed.
- Live/mirror Client Director SHA-256 is
  `C8FCBF4A21B65D67FD85AB4FE62D3E1BEE37FD4ED8B85A62BF4E5EFDC8178F07`.
  Velocity construction is next. No UI, cook, or Workshop work has started.

## Position-route velocity construction accepted (2026-08-13)

- Internal checkpoint `0.74.0-position-route-velocities` compiles
  `ComputePositionRouteVelocitiesV1`. It clears candidate velocities before
  inspecting the sticky stage verdict, leaves invalid stages invalid and empty,
  emits zero endpoint velocities, and emits exactly one velocity per interior
  waypoint. Interior velocities are nonzero only when both adjacent spatial
  curves are `auto_cinematic`.
- Each interior component compares the time-normalized incoming and outgoing
  secants. Equal-sign positive slopes choose the smaller value, equal-sign
  negative slopes choose the larger value (the value closer to zero), and
  reversal or flat-side cases choose zero. This is the frozen cinematic oracle,
  not a geometric average which would change speed when authored durations
  differ.
- Deterministic full/paste graphs contain 83/82 nodes with SHA-256
  `03160E2376B1CA457EC08B8CAB2B24322DFA5D5D0B860883C7698751E009DB12` /
  `486FC1EC9421BFC8FA45009AFEE72C2DC8A8032E7859FB9D9154DFEF2F8AE6CB`.
  The exact post-compile 83-node export has SHA-256
  `3759271529E7B769064D3EEB4BC45A2305119EA0875AB06F2DE9B617FD2E19B1`.
- The native entry could not connect to the first impure array clear while the
  function's `Pure` flag remained checked. Uncheck `Pure` first, then separate
  the entry from the generated body, connect the two execution-pin centers at
  1:1 zoom, and immediately re-export the complete graph. This run accepted
  only after the exact 83-node contract proved the reciprocal entry-to-clear
  seam.
- Owned Blueprint windows require explicit activation and keyboard focus after
  bringing them forward; focusing only the root owner can send verified keys
  into the main editor instead. `Invoke-EnhancedEditorInput.ps1` now attaches
  the target thread and explicitly calls `SetActiveWindow`/`SetFocus`.
- Do not write `bRemoteExecution=True` into the default Enhanced DevKit config
  while an editor from that DevKit is running. The live editor can later flush
  its stale settings and silently erase the change on shutdown. The provisioner
  now refuses that unsafe state; close the editor, provision, verify the flag,
  and only then relaunch.
- Warm and fresh NullRHI execution independently pass 101 valid routes, 10,968
  component checks, and a 512-waypoint route with maximum component error
  exactly zero. Both runs prove stale-output clearing on a prior-invalid stage
  and restore every touched CDO property. Fresh cold load loads all nine core
  assets and compiles all six Blueprints. The complete scaffold passes.
- Guarded editor shutdown added no crash directory. FromDevKit preview found
  exactly one conflict and 16 unchanged files; forced sync copied only Client
  Director, and reverse preview found all 17 files unchanged. Live/mirror
  SHA-256 is
  `976374E79CF3E156AF20C283D612CD51B3EF801C8763742645534AB7168162B8`.
- Position segment assembly is next. This checkpoint does not claim route
  publication, evaluation, dogfood controls, UI, cook, or Workshop readiness.

## Position-route segment assembly accepted (2026-08-13)

- Internal checkpoint `0.75.0-position-route-segments` compiles
  `BuildPositionRouteSegmentsV1` on Client Director. The stage begins by
  clearing all six segment/flat-arc arrays and all three totals, then requires
  the sticky position-stage verdict and exact waypoint-velocity cardinality.
  For each segment it stages endpoint positions, duration-scaled u-domain
  velocities, zero accelerations, curve kind, tolerance, depth, and operation
  budget into the already accepted adaptive-arc compiler. Only a completely
  valid primitive is appended to the candidate prefix.
- Candidate starts, flat offsets/counts, `u` values, local distances, segment
  lengths, total time, total distance, and exact operation count are therefore
  deterministic. Failure before the first completed segment leaves the
  candidate empty; failure on a later segment leaves only the exact completed
  prefix and keeps validity false. This stage cannot touch any compiled route
  field; only the next atomic publication function may do that.
- Deterministic position-segment full/paste graphs contain 78/77 nodes with
  SHA-256
  `BC9DB6FDF1229E1DFEAF5DEDC6404576DDD6B271CBBF813DF2187C1F270503EE` /
  `CE2801316AC6419580CB26C0BB801383B202AA1C77709FF2A8195B3F31790788`.
  The exact post-compile live graph contains 78 nodes and hashes to
  `6C437135BD353F0409D4D4ACDA43233352AFEC76613E7A9FC522769ABC305B9B`.
- Fresh composition testing caught a real regression that source topology and
  ordinary cases could not: the old adaptive processor exhausted every
  configured `ForLoop` iteration as a no-op after its work stack emptied.
  Replacing it with the DevKit-native `ForLoopWithBreak` removed that waste,
  but the 512-linear-segment boundary still crossed Unreal's one-million-step
  Blueprint watchdog because every explicitly linear interval was needlessly
  evaluated and subdivided to depth six.
- Version 1 now makes spatial linearity an exact primitive fast path. One pop
  publishes `(u,distance) = (0,0)` and `(1,|end-start|)` without calling the
  quintic evaluator or refining. Nonlinear segments retain the complete
  minimum-depth, tolerance, max-depth, and operation-budget contract. The
  frozen Python oracle, scalar tests, warm runtime, and fresh runtime all use
  this same distinction.
- The corrected adaptive process deterministic full/paste graphs contain
  117/116 nodes with hashes
  `5E478579EA324EA4B35CEB7E579D3F9150135EB545E452E79AC0D90F15FD6F8D` /
  `C461CA26B8B765291EBE10B1EE6701218F3A17E263C2834467BCE1FBB8B7ED0E`.
  The exact compiled 117-node export hashes to
  `825B22142367BA64F19CD3EEAF23C1F6B556E364C92F2030C8C71753D9EAB222`.
  Its contract proves one breakable loop, exact empty-stack break wiring, an
  explicit linear branch directly into endpoint acceptance, and that only the
  nonlinear branch can execute `EvaluateQuinticVectorV1`.
- Warm execution passes 23 adaptive process cases (463 samples), 32 full
  adaptive compiler tables, and 32 position routes. Route evidence covers 662
  segments, 7,498 flattened samples, the 512-waypoint ceiling, exact `u`,
  maximum distance error `9.094947017729282e-13`, maximum length error
  `3.126388037344441e-13`, prior-invalid and velocity-cardinality rejection,
  early primitive failure, deterministic late-prefix failure, and complete
  CDO restoration.
- Three separate fresh NullRHI processes repeat adaptive-process, full-compiler,
  and route-assembly execution. Each log was checked immediately and contained
  zero `Runaway loop detected` and zero `Infinite loop detected` matches. Fresh
  cold load then loaded all nine core assets and compiled all six Blueprints;
  the full `-RequireMvpAssets` scaffold, deterministic regeneration, schemas,
  graph contracts, and repository regression suite passed.
- Warm runtime harnesses now explicitly reload the frozen oracle module. This
  prevents a long-lived editor process from comparing new Blueprint semantics
  against a stale Python module cached by an earlier remote run. The one-short
  adaptive failure fixture also selects a nonlinear table whose exact budget
  is greater than one; it cannot accidentally turn into a successful linear
  fast-path case.
- The action-menu automation helper gained `KeysAfterClick` while harvesting
  the native breakable-loop node. Text is sent while the popup still owns
  focus, avoiding the old second-invocation refocus that dismissed the menu.
  Exact export caught one initially miswired native entry seam; it was corrected
  before acceptance. Visual wire appearance was never treated as proof.
- Guarded exit reached `LogExit: Exiting.` with crash directories unchanged at
  25. Closed-editor FromDevKit preview found exactly Client Director changed and
  16 files unchanged; forced sync copied one package and reverse preview found
  all 17 unchanged. Live/mirror SHA-256 is
  `8AF62111F2235A8840CE02719A6920B96D45B51CC05D9912FE7FFC15634E4E25`.
- Atomic publication through `CommitCompiledPositionRouteV1` is next. This
  checkpoint does not claim compiled-route evaluation, cinematic dogfood,
  polished UI, cook, or Workshop readiness.

## Position-route atomic publication accepted (2026-08-13)

- Internal checkpoint `0.76.0-position-route-commit` compiles and saves
  `CommitCompiledPositionRouteV1` on Client Director. Entry first clears all
  eleven compiled arrays, the compiled time/distance totals, compile validity,
  and the seven evaluation-result fields. The result segment sentinel is `-1`.
- Candidate publication requires a prior-valid sticky stage; 2..512 waypoints;
  exact waypoint, segment, velocity, start, count, length, and flat-table
  cardinalities; finite positive duration and total time; finite nonnegative
  lengths and total distance; exact cumulative segment starts; contiguous flat
  sample ranges; at least two samples per segment; bounded operation telemetry;
  and exact local table endpoints `(0,0)..(1,segment length)`. Accumulated time,
  distance, and sample count must exactly exhaust the advertised totals.
- The eleven arrays are copied only after the complete validation walk. The
  compile-valid flag is set last. A rejection exposes no stale or partial
  compiled route, clears all evaluation output, resets its segment sentinel,
  and turns stage validity sticky-false without mutating candidate inputs.
- Deterministic full/paste graphs contain 182/181 nodes and hash to
  `FA86FC2A490C4F863BAABD5695885E0019B82327E393BF690DE7D45EFAF6DD1B` /
  `95B6961CFF70BF6AAA529AD877A7FF817E7F5B2DF81455B143A2B065F66C7FAD`.
  The exact compiled 182-node export hashes to
  `9A06CD6825699A31A9059666B3B25563EAF2ED45D03FD5547009EEBAA3A4004A`.
- Runtime composition found a real preflight defect before acceptance: the
  sample accumulator reused `PositionRouteResultSegmentIndexV1` and initialized
  it to zero, but a preflight rejection bypassed the inner reset. The first
  invalid fixture therefore observed segment zero instead of the public `-1`
  sentinel. A dedicated outer failure reset fixed it, and the contract now
  requires all four `-1` failure/success resets plus the accumulator lifecycle.
- The contract parser also stopped substring-matching `DefaultValue`; that had
  confused `AutogeneratedDefaultValue="0"` for an explicit serialized default.
  Exact comma-delimited property parsing is required when Blueprint clipboard
  pins carry both fields.
- The accepted warm and fresh NullRHI runs independently pass 24 valid routes,
  658 segments, 7,679 flattened samples, the 512-waypoint ceiling, and 35
  malformed/prior-invalid cases. Both prove exact arrays/totals, unchanged
  candidates, atomic poisoned-state clearing, evaluation reset, sticky failure,
  and full CDO restoration. Fresh log inspection found no runaway or infinite
  loop marker.
- All upstream position reset, validation, velocity, and segment execution
  suites passed after publication was installed. Fresh cold load loaded nine
  core assets and compiled all six Blueprints. The full scaffold, deterministic
  regeneration, live graph contract, schemas, and repository regressions pass.
- Visual seam attempts were never accepted as evidence. Two pin drags produced
  no reciprocal serialized link and were rejected. After framing the exposed
  exec pins, the third drag produced the required entry-to-first-clear link;
  the exact export passed before compile and again after compile.
- Guarded shutdown exited PID 53364 without adding a crash directory (25 to
  25). Closed-editor FromDevKit preview found exactly Client Director changed
  and 16 files unchanged; forced sync copied that one package, reverse preview
  found all 17 unchanged, and live/mirror SHA-256 is
  `B389EFAB838464EC09FE2DF04204D9B24FCE418D3176A00D1CB13E034EFEE5C9`.
- The next ordered slice is the thin `CompilePositionRouteV1` orchestrator.
  Position-route time/distance evaluation, cinematic dogfood shortcuts,
  polished UI, cook, Workshop, and whole-mod completion remain unclaimed.

## Position-route compiler orchestration accepted (2026-08-13)

- Internal checkpoint `0.77.0-position-route-compile` compiles and saves the
  thin `CompilePositionRouteV1` boundary. Its only execution path calls
  `ResetPositionRouteCandidateV1`, `ValidatePositionRouteInputsV1`,
  `ComputePositionRouteVelocitiesV1`, `BuildPositionRouteSegmentsV1`, and
  `CommitCompiledPositionRouteV1` in that exact order.
- Deterministic full/paste graphs contain 6/5 nodes and hash to
  `C30B61819CF6F9A7ACD41592B84F59B86205A6C91C773A7E999AE9EBED1AE5E8` /
  `2A11766A037E0CF8E4CDAFCCAD02ADDBDB04C5ABEAF6234C38B12D158D6995D4`.
  The exact accepted post-compile six-node export hashes to
  `D4960A9F6236E706D4159D5E0422C41163B7DFBEA923C9128DD926AB6923D07A`.
- Warm and fresh NullRHI executable tests stage only the seven authored input
  fields and invoke the orchestrator once. Each run accepts 24 seeded routes,
  614 segments, 5,701 flattened samples, and the 512-waypoint boundary. It
  proves exact oracle candidate and compiled arrays/totals, authored-input
  preservation, replacement of a prior valid compilation, 14 malformed-input
  rejection families with poisoned candidate/compiled/evaluation clearing,
  and complete CDO restoration.
- The accepted runtime evidence therefore proves composition, not merely the
  graph call shape or isolated stages. Fresh log inspection found no runaway
  or infinite-loop marker. Fresh cold load loaded nine core assets and compiled
  all six Blueprints; the full scaffold passed with the generator, paste/full
  contracts, live graph, and runtime harness included.
- Guarded shutdown kept crash directories unchanged at 25. FromDevKit preview
  found exactly Client Director changed and 16 files unchanged; forced sync
  copied one package and reverse preview found all 17 unchanged. Live/mirror
  package SHA-256 is
  `0FBE2FE9A52AA9A15681938B7B9FE22F30AF44DAADD4438A315893403AEB4758`.
- Absolute-time evaluation through `EvaluateCompiledPositionRouteV1` is next.
  Cinematic dogfood shortcuts, polished UI, cook, Workshop, and whole-mod
  completion remain unclaimed.

## Selected position-route arc slice accepted (2026-08-13)

- Internal checkpoint `0.78.0-position-route-arc-slice` adds compiled
  `StagePositionRouteArcSliceV1` as a deliberately narrow adapter between the
  flattened compiled route publication and `InvertArcLengthTableV1`. It resets
  the shared arc primitive, validates compile validity, selected segment,
  metadata/flat-array cardinalities, bounded slice range, finite nonnegative
  segment length, and finite `[0,1]` distance alpha, then copies only that
  segment's contiguous `u` and cumulative-distance samples. Validity is the
  final write.
- Deterministic source/paste graphs contain 68/67 nodes and hash to
  `BB3AB3A286703BE4C59D466432374B6818D81A1B67D7FB9C9302E9950989563F` /
  `BB163444025E73E5D8852E038699B19B4E5C0CE223B2F0D51B2C211BF6EF656A`.
  The exact post-compile 68-node export passes the same reciprocal-link
  contracts and hashes to
  `8FCC4E4564AA5640C27C74D9777FF2665173F59B11ACB4131A865A02287BA626`.
- Warm and fresh compiled runtime each pass 726 valid selected slices across
  1,976 route segments and 25,735 flat samples. Evidence includes unequal
  per-segment table sizes, zero-length segments, repeated shuffled access, and
  511 segments from the 512-waypoint route ceiling. Fifteen malformed families
  cover prior-invalid publication, index bounds, all metadata cardinality
  mismatches, flat mismatch, count/start/end bounds (including maximum-integer
  start overflow), negative/non-finite length, and out-of-range/non-finite
  alpha. All 15 reach Blueprint and clear poisoned primitive state without
  mutating compiled source data; complete CDO restore passes. The accepted
  bound uses `count <= flatLength - start` only after proving nonnegative start,
  avoiding a wrapped `start + count` comparison.
- The live editor exposed an automation defect before graph installation:
  `Configure-PositionRouteAssembly.py` rejected legitimate restored nonempty
  arrays during an idempotent schema upgrade. It now tracks variables created
  by the current run, initializes only those, and explicitly preserves all
  existing CDO values. The corrected rerun created/saved the function boundary
  without erasing the three-waypoint authored route.
- The exact seam was measured, not assumed: paste-form contract passed first,
  the native entry moved from `(0,0)` to `(-4144,1648)`, one pin drag created the
  reciprocal entry-to-first-clear link, and exact contracts passed before and
  after compile. The first full-scaffold attempt was a harness invocation issue:
  capturing its combined output promoted normal unittest stderr progress into
  a PowerShell terminating error. Direct invocation completed successfully; no
  product or graph test failed.
- Every warm upstream position-route runtime and the downstream arc inverter
  remain green. Guarded shutdown exited cleanly with crash directories unchanged
  at 25. Closed-editor preview found exactly Client Director changed plus 16
  unchanged files; forced mirror copied that package, reverse preview found all
  17 unchanged, and live/mirror SHA-256 is
  `7906D5220E777F6D5EC6479F82143D0EB960608A3ECAFDB19985205E503BC87D`.
  Fresh helper/compiler/inverter runs, cold compilation of all core assets, and
  the full scaffold pass.
- Next is full `EvaluateCompiledPositionRouteV1` absolute-time composition.
  This helper acceptance does not claim route evaluation, cinematic shortcuts,
  UI, cook, Workshop, or whole-mod completion.

## Compiled position-route absolute-time evaluation accepted (2026-08-13)

- Internal checkpoint `0.79.0-position-route-evaluator` compiles and saves
  `EvaluateCompiledPositionRouteV1`. It begins by clearing seven public result
  fields and all three shared primitive validity flags. It validates publication
  shape, finite elapsed/total time, and positive total time; scans every segment
  duration with sticky finite-positive validation while selecting the first
  containing segment; then evaluates timing, clamps normalized distance to
  `[0,1]`, stages the accepted flattened arc slice, inverts it to curve `u`, and
  evaluates exact linear interpolation or the accepted quintic-vector primitive.
  Completion at/after total time returns the final waypoint directly.
- Deterministic full/paste graphs contain 237/236 nodes with hashes
  `9616D10AC7D08CA2FCBE59366F0D9B70ADB705AD0E6605FA470D6F414A2F4607` /
  `13C72D6817F87C4673741C5ADD2B7DCD5ED45CD2864585A25972018C300EBAB4`.
  The exact accepted post-compile 237-node export hashes to
  `766327739AEA1D71617364445C5E828BDE7B2B9A7BB4EB19FD12BA790E080D5F`.
- Runtime acceptance caught three defects that graph topology alone could not.
  First, `smoothstep(0.999999999)` produced `1.0000000000000002`, which the
  strict arc-slice boundary correctly rejected; normalized timing output is now
  clamped before publication and staging. Second, selection could skip an
  earlier corrupt zero-duration segment; the single bounded scan now validates
  every duration sticky-false. Third, a late unknown-curve rejection cleared
  public results but left the successful timing primitive valid; all seven late
  failure paths now clear public results plus timing, arc, and vector validity.
  Exact contracts require both clamps, the sticky scan, and every complete
  ten-write failure chain.
- Warm and fresh NullRHI execution independently pass 17 routes, 3,605
  evaluations, 17 shuffled direct-scrub proofs, all supported timing/spatial
  modes, exact segment boundaries, and the 512-waypoint ceiling. Seventeen
  malformed compiled-state families and all three scalar non-finite elapsed
  values reach Blueprint and fail closed; compiled publication never mutates and
  every touched CDO property restores. Warm/fresh maximum position error is
  `4.547473508864641e-13`; fresh maximum distance/u errors are
  `7.105427357601002e-15` / `1.6266987756807794e-12`.
- All eight warm upstream/downstream position-route/arc runtime suites passed.
  Separate fresh route-compiler and arc-inverter processes passed. Guarded
  shutdown reached `LogExit: Exiting.` with crash directories unchanged at 25.
  Closed-editor FromDevKit preview found 16 unchanged assets and exactly Client
  Director changed; forced sync copied one package, reverse preview found all 17
  unchanged, and live/mirror SHA-256 is
  `A995511B77A6D6E237561AAAEC03915B6773962E7162B234CA83F5218FB57208`.
  Fresh cold load loaded nine core assets and compiled all six Blueprints.
- The exact client-coordinate lesson is now explicit: coordinates measured from
  `Save-WindowScreenshot.ps1` are already client coordinates for the input
  helpers; subtracting the title bar misses the pin. When the Find Results panel
  is collapsed, send `Ctrl+F` before using
  `Open-BlueprintFunctionViaFindResults.ps1`. These two rules made the native
  entry seam deterministic instead of a blind-click loop.
- The full `Test-Scaffold.ps1 -RequireMvpAssets` gate passes with deterministic
  regeneration, checked source/paste/live evaluator contracts, every schema and
  repository regression, and the mirrored MVP assets. A final clean-candidate
  rerun passed in 50.9 seconds before commit `b79b985` was pushed to `main`.
  This does not claim remaining cinematic tracks, shortcut dogfood, polished
  UI, cook, Workshop, or whole-mod completion.

## Atomic cinematic-pose composition frozen offline (2026-08-13)

- Position and orientation are deliberately composed as a narrow transaction,
  not reimplemented as a third interpolation engine. The frozen oracle compiles
  both accepted component tracks from one duration sequence and rejects any
  disagreement in segment cardinality, cumulative starts, durations, or total.
- Evaluation is absolute-time and fail-closed. A combined pose exists only when
  both component evaluators agree exactly on segment, local alpha, completion,
  and total; position keeps its independent distance alpha and arc parameter.
- Seven oracle tests pass deterministic and malformed authored data, negative,
  boundary, terminal, non-finite, repeated, and shuffled queries; 80 seeded
  tracks are compared directly against both accepted component evaluators. Six
  separately constructed corrupt compiled timelines are rejected before a pose
  can be returned.
- The Blueprint schema fixes one sticky stage bit, two compiled-result fields,
  one evaluation input, eight evaluation outputs, and five ordered functions:
  reset, authored-input validation, combined commit, ordered compile, and atomic
  evaluation. Five schema tests pass. The idempotent configurator creates only
  absent fields/functions and preserves existing defaults.
- This checkpoint is offline contract evidence only. No live Blueprint body,
  compile/save, runtime, package mirror, or new feature-version claim has been
  made yet.

## Atomic cinematic-pose composition accepted live (2026-08-13)

- Internal checkpoint `0.80.0-cinematic-pose-composition` installs, compiles,
  saves, mirrors, and executes the five ordered Client Director functions:
  `ResetCinematicPoseStateV1` (12 nodes),
  `ValidateCinematicPoseInputsV1` (27),
  `CommitCompiledCinematicPoseV1` (57),
  `CompileCinematicPoseV1` (6), and
  `EvaluateCompiledCinematicPoseV1` (65). Exact post-compile exports pass the
  same reciprocal-link and semantic contracts as their generated source and
  paste forms; graph-shape confidence alone was not accepted.
- Deterministic source/paste hashes are, in function order:
  `2773686FAAC6FA991A518A0508FAD20C07EC17DCC8299C67F788A6651C7B2E2F` /
  `70B60D09A6EF57AC264241BF9F59DDE0D0EB09481226B01994F390EBF03DE031`,
  `81901AC7BAC08D4C1C20A5871F5B25ECD88F1B3B386C4AF8FC34D5532299BB63` /
  `CBCF8842256E1B4E2110A79A7138EB09E192A3E9950FB540F2DD7F343956D470`,
  `135FFC9EAFEFDED5C58F463D3C11CFBF32C14F54F8AA134214D9F186917E96E0` /
  `DF7059B38469B16DE87602AA9CECD8A06CC301E0ADE4A88EB44F4D9663E9E8AF`,
  `924AA7CE3C96FFFEE347A7B78EF040F40B3EB7747AAE1C1A9DAFC462161D75DB` /
  `4EC021A6998F6DBD124A5E139EA08207FBB72159607DDCFB44465C067D057BF9`,
  and
  `BCF7D1FBBD38F3C60BACB042CE805D27A08B43C0DE960E582A71550B7455CC4F` /
  `1C8995EE54412CF401965EBB12CB4848A271FC5B030D8B6E7BBE2FA0E58F7E59`.
  Accepted live-export hashes are
  `547E3BB75E67B651D8C2CD093C891499D08363DA44DBF1D0DE7ACB8D6F9CC6EE`,
  `8BCF35A47CD7C0FEF25A08F200F3D5225C20B059A4E90703218CF81179B78173`,
  `414600CE42C9895370FF0FCF3717553CF5E92A31EB5449E587D172CE521EC85B`,
  `3555903505B7E5D2F3519CFD465114B940576AACBE4F90AE262B71558D620CEA`,
  and
  `3C5D045D85745050138AF0DEEC138C360173B120B7526CFE54292079A7A58559`.
- Warm-editor and separate fresh NullRHI execution each pass 13 valid pose
  routes, 3,223 absolute-time evaluations, 13 shuffled direct-scrub sequences,
  exact boundaries, deterministic recompilation, and the 512-waypoint ceiling.
  Maximum position error is `3.410605131648481e-13`; maximum angular error is
  `1.032382731180714e-07` degrees. Eight compile-invalid families, seven corrupt
  commit families, eight corrupt evaluation families, and all three non-finite
  elapsed values reach Blueprint and fail closed. Authored inputs and component
  publications remain unchanged, poisoned combined outputs clear, and every
  touched CDO property restores.
- All accepted scalar, vector, quaternion, arc, position-route, and orientation
  runtime suites passed before the repository-wide scaffold gate. A separate
  fresh cold-load process loaded nine core assets and compiled all six
  Blueprints with zero errors. Guarded shutdown left no editor or crash reporter
  process. Closed-editor sync copied exactly Client Director; its live and
  mirrored package hashes match at
  `CF2A983EA78EBA040D65C3A2407DDA65CD326FD2C52C64D27B07A50BB33803BC`.
- The full `Test-Scaffold.ps1 -RequireMvpAssets` gate passes with deterministic
  regeneration, source/paste/live contracts, runtime harness registration,
  schema checks, repository regressions, and mirrored MVP assets. A mistyped
  orientation-runtime filename during one manually assembled runner list was
  an orchestration typo, not a feature failure; the corrected suite and full
  scaffold both passed.
- Dense-graph seam rule: at minimum zoom after `Home`, the native function
  entry may visually overlap the pasted first node. Do not repeat blind pin
  drags. Export exact graph coordinates, clear selection, select and move the
  native entry from an unobstructed header region, prove its serialized new
  position, then connect the measured pins. Re-export after compile and let the
  exact contract—not the canvas appearance—decide acceptance. The final commit
  seam was `(464,639) -> (635,625)` and the evaluator seam was
  `(500,296) -> (250,454)` in their respective captured client layouts; these
  coordinates are evidence for those layouts, not universal constants.
- Next ordered backend work is flight-profile behavior followed by camera lens,
  focus, and effect tracks, then shortcut/debug dogfood. Polished UI, cooking,
  Workshop publication, and whole-mod completion remain explicitly unclaimed.

## Flight-profile compiler and resolver frozen offline (2026-08-13)

- The bounded first flight-profile slice owns deterministic profile identity and
  parameters only. It intentionally does not derive airframe/gimbal transforms
  or procedural wind. This prevents those later solvers from branching directly
  on loosely authored strings or embedding preset constants in multiple graphs.
- Supported IDs and order are exactly `cinematic_drone`, `hybrid`,
  `fpv_cinewhoop`, `fpv_freestyle`, and `fpv_long_range`. Each immutable preset
  defines path-follow and horizon-stabilization weights, look-ahead, bank gain
  and clamp, camera uptilt, angular-rate/acceleration/jerk limits, and minimum
  turn radius. All fields have explicit finite domain bounds.
- Compilation accepts one canonical default and exactly one optional override
  string per segment. Empty means inherit; nonempty values must be exact,
  trimmed, and known. Every override is validated, including values outside the
  segment later selected for evaluation. Segment cardinality is bounded to
  1..511 and compiled lookup accepts only a bounded integer index with no
  fallback behavior.
- Eight oracle tests pass all planned presets, authored-input independence,
  deterministic ceiling compilation, shuffled history-independent lookup, 200
  seeded mixed publications, invalid identifier/shape/type/index families, and
  corruption of cardinality, identity, every non-finite parameter, and every
  finite-but-noncanonical parameter. Five schema tests initially froze the
  document/candidate/compiled/evaluation seam, ten one-to-one
  candidate/compiled/result parameter channels,
  seven ordered functions, and atomic fail-closed contracts. The full repository
  scaffold remains green after registration.
- A generated-name abstraction was rejected during review before Unreal work:
  pluralization was ambiguous and the configurator needs an explicit field list.
  The accepted schema enumerates every concrete Blueprint variable and maps each
  channel explicitly. Next is generated graph bodies plus exact contracts, then
  live compile/save and executable warm/fresh proof; no live flight-profile claim
  is made by this checkpoint.

- Pre-resolver review caught that the named `ResolveFlightProfilePresetV1`
  boundary had no explicit call scratch. The schema now enumerates one resolver
  input plus 12 resettable resolver results (ID, ten parameters, validity), for
  53 total variables. This keeps resolver output disjoint from candidate,
  compiled, and evaluation publications and makes the function executable in
  isolation. The omission was corrected before any live asset mutation.

### Flight-profile reset and validation graphs frozen (2026-08-13)

- `ResetFlightProfileStateV1` deterministically emits 59/58-node full/paste
  graphs. Its one ordered execution chain clears the 11 candidate arrays and 11
  compiled arrays, then resets stage/compile validity, the public profile ID,
  ten public numeric results, and result validity. Authored inputs and the query
  segment index are deliberately preserved. Source/paste SHA-256 is
  `8C2F80567039EDE4B3E6964E45D00A2B04F369E36E1823C6157FE64A2ED59C5E` /
  `831512E3BF08C9D218A7E0427BC103D52F866E79ACBDA1EF006D591815BD3C32`.
- `ValidateFlightProfileInputsV1` deterministically emits 37/36-node full/paste
  graphs. It resets stage validity false, proves explicit count 1..511 and exact
  override-array cardinality, accepts only one of the five canonical defaults,
  tentatively publishes stage validity true, then loops through every override
  and writes it sticky-false for anything other than empty or a canonical ID.
  Source/paste SHA-256 is
  `2C41C3276965ECEA939BF0DC0B4A2CDDA6BA9533971B6CA13B98042B1ED3DA4B` /
  `2F0794A646B94B25F6409F42C6DF56B4AB2023C4E7827D9FB78C7B27E2D089B5`.
- Exact contracts require every array clear, scalar default, reciprocal execution
  link, integer bound, identity literal, array source, and sticky validity write.
  Repeated generation is byte-identical and the full scaffold passes. These are
  generated offline bodies only; they are not yet live, compiled, or runtime
  accepted. Next is canonical preset resolution and candidate construction.

### Flight-profile resolver and candidate construction frozen (2026-08-13)

- `ResolveFlightProfilePresetV1` uses an isolated one-string input and 12-field
  result seam. Its 84/83-node full/paste graphs reset ID, ten parameters, and
  validity first; compare the input against all five IDs in canonical order;
  write the complete matching preset; and publish validity last. The final
  unknown-ID `else` is deliberately unconnected, retaining the reset invalid
  result. Source/paste SHA-256 is
  `2F9F2D867C6B236AC400BFF5C4CA1EDDD411DE5BE7669D12E376E8C3C1248C20` /
  `7C574DF2B1D79FFD4A730C62860DA0D73185A2311DA4C6E22F18869272F38D97`.
- `BuildFlightProfileCandidatesV1` uses 58/57 nodes. It clears all 11 candidate
  arrays, checks sticky stage validity, loops the authored override array, stages
  either the document default or nonempty override into the resolver input,
  invokes the isolated resolver, writes stage validity false on resolver failure,
  and otherwise appends the resolved ID plus every numeric parameter in one
  ordered chain. Source/paste SHA-256 is
  `CC41DC566F37D1CB193F8706C545C8C7F41241F9D7D599049424B41BE7550C27` /
  `A8AB86DECAB913E6511C46DD9F8AE819ABB9792F14ABED20EBC62ADC582B61A6`.
- Exact contracts prove reset-before-branch behavior, canonical literal order,
  complete preset setter chains, unknown-ID fail-closed behavior, explicit
  inheritance staging, self-context helper invocation, resolver validity guard,
  sticky rejection, and one-to-one source for every candidate append. Repeated
  generation is byte-identical and the full scaffold remains green. These bodies
  are not live yet; next is atomic candidate commit and orchestration/evaluation.

### Flight-profile atomic commit and compiler frozen (2026-08-13)

- `CommitCompiledFlightProfilesV1` emits 115/114-node full/paste graphs. It
  invalidates prior compile publication immediately, proves stage validity,
  count 1..511, and exact cardinality for the ID plus all ten candidate arrays.
  It then loops every candidate ID, resolves the canonical preset again, compares
  the resolved ID and all ten numeric values to indexed candidate data, and
  writes stage validity sticky-false on any mismatch. Only a completed valid scan
  replaces all 11 compiled arrays; `FlightProfileCompileValidV1=true` is the last
  write. Source/paste SHA-256 is
  `199367ED38F248D8CCC1063A6D91FF36805994F858F3986C5FE66438F2BF8A25` /
  `C85B3B9E7B64112043C3E03DE7A140FDE10512F96DF3B41EC78D8857D9CE37FE`.
- `CompileFlightProfilesV1` is the deliberately thin 5/4-node full/paste
  orchestrator: reset, input validation, candidate construction, atomic commit.
  Source/paste SHA-256 is
  `A378CAFA6D37EA2296D412D16995FDFEC99806152C70EBB2D1D789FC0DBD41A5` /
  `3356002F290CF7F1FCD92129DD89E37B896EDA51C0D07E26975D1409AB1A4982`.
- Exact contracts require initial invalidation, every cardinality comparison,
  canonical resolver call and per-parameter equality, both rejection seams,
  completed-loop stage guard, candidate-to-compiled source mapping, ordered
  publication, and validity-last. Deterministic regeneration and the full
  scaffold pass. These bodies remain offline until evaluation is frozen and the
  seven-function set is installed, compiled, saved, and executed in Unreal.

### Flight-profile evaluator frozen offline (2026-08-13)

- `EvaluateCompiledFlightProfileV1` emits 142/141-node full/paste graphs. It
  clears a dedicated evaluation-stage bit, profile ID, all ten numeric outputs,
  and result validity first. Preconditions require compile validity, 1..511
  compiled IDs, exact cardinality for all ten parameter arrays, and a bounded
  integer query index.
- A complete scan re-resolves every compiled ID and compares all ten indexed
  compiled parameters with its immutable preset. Any bad ID or hidden corruption
  writes evaluation-stage validity sticky-false. Only the completed valid scan
  reads the requested index from all 11 arrays, publishes ID then ten parameters,
  and writes result validity last. Compiled arrays and compile validity are never
  mutated by evaluation.
- Exact contracts prove 13 ordered resets, all bounds/cardinalities, the full
  resolver integrity scan, both rejection seams, final sticky-stage guard,
  selected-index reads, one-to-one publication sources, and validity-last.
  Source/paste SHA-256 is
  `E026C15A386D0894B40C7E6A2C9E9FA93EE8D5F65B0FC273686ECB00FDBA7A59` /
  `3463ACA8EEEB314D980C8BB156AC3C3EFAF000AA840824EC7094EA75DC2C55DD`.
  Repeated generation and the full scaffold pass. The complete seven-function
  flight-profile graph set is now frozen offline; no live compile/runtime claim
  is made until the DevKit installation and executable harness pass.

### Flight-profile compile/evaluate accepted live (2026-08-13)

- `ResetFlightProfileStateV1`, `ValidateFlightProfileInputsV1`,
  `ResolveFlightProfilePresetV1`, `BuildFlightProfileCandidatesV1`,
  `CommitCompiledFlightProfilesV1`, `CompileFlightProfilesV1`, and
  `EvaluateCompiledFlightProfileV1` are installed in
  `BPC_EDD_ClientDirector`, compiled, saved, mirrored, cold-loaded, and
  executable. Exact post-compile exports contain 60, 37, 84, 58, 155, 5, and
  182 nodes respectively, with no `K2Node_Knot` reroutes.
- Live-export SHA-256 values in that order are
  `05D8143DF9FFC593D9EAE874E344A36B60B62070A0C02ACDDC12D3F12E2DA4B0`,
  `60CC4472D563E347FA36A50294B6B60FAACD5A0B5A6F637A4DF141CA05269DAB`,
  `080C51AC5FF445E836A3716BF2E8E138C47943416860399BDB5279FCD41E9581`,
  `698C225788644D5AC371E4AB14CB308D289039BDCE35688C48B328CF1B94C543`,
  `F64E15CFF07D38DA06BF58D73E54C5CC1C104D5E06A47BC909F99FFCBD333DBF`,
  `97F14D3D2A67DA6B0D7EC1AEF48BFC8443C65F18FAFC81931E2F7AEC5948FAC5`,
  and
  `F349DA2AAC42CF84CA3F699B0D7CEB4E143112EC0E0D07337223B3DDBB057F25`.
  Every focused exact contract passes against the promoted live export, not
  merely the generated source graph.
- Warm-editor and separate fresh NullRHI execution each pass 9 resolver cases,
  7 valid compiles, 14 indexed evaluations, the 511-segment ceiling, 12 invalid
  compile families, 24 candidate-corruption families, 24 compiled-corruption
  families, and 5 invalid indices. Actual non-finite floats reach Blueprint and
  fail closed; no reflection sanitization masked those cases. Authored inputs
  and accepted compiled publication obey their mutation contracts, poisoned
  result state clears, and every touched CDO property restores.
- The complete cinematic-pose suite remains green in the same live editor:
  13 valid poses, 3,223 evaluations, 13 shuffled direct-scrub cases, the
  512-waypoint ceiling, 8 compile failures, 7 commit failures, 8 evaluation
  failures, and 3 non-finite elapsed values. Maximum local-alpha error is zero,
  maximum position error is `3.410605131648481e-13`, and maximum angular error
  is `1.032382731180714e-07`. Position-route and orientation-track compiler
  regressions also pass with full restoration.
- After guarded editor shutdown, reverse sync copied exactly one asset with no
  conflicts. Live and mirrored Client Director SHA-256 both equal
  `B411E7414A74119D0F094D3CFD87C4C2772BCD17F40AB90DD80D12F20FBD55DB`.
  A fresh cold-load process loaded all nine core assets and compiled all six
  Blueprints with zero errors. A second fresh executable run repeated the full
  flight-profile matrix and restoration proof with zero errors. The complete
  `Test-Scaffold.ps1 -RequireMvpAssets` gate passes.
- Unreal 5.6 preserved a stale hidden self pin when a generated string-equality
  call changed from `MathLibrary` to `StringLibrary` but only the first textual
  class reference was replaced. Generators now replace every occurrence, and
  equality contracts reject any residual `MathLibrary` reference. This removed
  the cold-load `Target`-pin warning rather than merely suppressing it.
- Do not use Blueprint File > Refresh All Nodes on these dense generated graphs
  while Blueprint Assist is active. One refresh inserted exactly 84 reroute
  knots into the 155-node commit graph. Exact export caught the 239-node result;
  the graph was rebuilt from deterministic source, the native entry was moved
  using serialized coordinates, and its one exec seam was reconnected and
  re-exported. Compile while a small unrelated function is active so Blueprint
  Assist cannot rewrite the dense target graph.
- Transient Unreal menus require foreground preservation. Both
  `Invoke-EnhancedEditorInput.ps1` and `Save-WindowScreenshot.ps1` now expose
  `-PreserveForeground`; without it their normal focus step dismisses the popup
  before the click or capture. Use the switch only after the owning editor
  window is already foreground and the popup is open.
- Accepted scope is canonical profile parameter compilation and indexed lookup.
  Profile-driven airframe/gimbal dynamics, coherent wind/vibration, lens/focus/
  effects, shortcut dogfood, polished UI, cook, Workshop, and whole-mod
  completion remain unclaimed. The next ordered slice consumes the immutable
  profile result in deterministic cinematic, hybrid, and FPV motion behavior.

### C2 flight-profile transition contract frozen offline (2026-08-13)

- Directly applying one exact preset per segment would create visible parameter
  jumps at every override boundary. The accepted consumer contract therefore
  smooths all ten numeric channels before any airframe or gimbal solver sees
  them. This is required even though indexed canonical lookup itself remains
  deliberately exact and discrete.
- Each segment owns its canonical preset at local alpha `0.5`. On the first
  half, it transitions from the previous/current 50/50 boundary to the current
  preset; on the second half, it transitions to the current/next 50/50 boundary.
  A quintic smootherstep makes value, first derivative, and second derivative
  agree at the midpoint and shared waypoint. Track endpoints and single-profile
  runs remain exactly canonical.
- The evaluator returns current ID, at most one neighbor ID, neighbor weight in
  `[0, 0.5]`, and ten blended parameters. Convex interpolation preserves every
  validated domain. It rejects invalid indices, booleans masquerading as
  integers/scalars, non-finite or out-of-range alpha, malformed cardinality,
  noncanonical or non-finite stored presets, and never mutates the compiled
  publication.
- Ten oracle tests pass exact midpoints/endpoints, identical neighbors, exact
  cross-segment boundary equality, numerical C1/C2 convergence with unequal
  neighboring durations, convex-domain checks for every field, shuffled
  history-independent scrubbing, corruption families, and 1,000 seeded queries
  on the 511-segment ceiling. Six schema tests freeze 40 explicit variables,
  four ordered functions, complete one-to-one parameter channels, disjoint
  current/neighbor/result state, helper restoration, reset-first behavior, and
  validity-last publication.
- This is an offline contract checkpoint only. Next are deterministic
  `ResetSmoothedFlightProfileV1`, `StageSmoothedFlightProfileSamplesV1`,
  `PublishSmoothedFlightProfileV1`, and `EvaluateSmoothedFlightProfileV1`
  generated graphs, exact contracts, live compile/save, and warm/fresh runtime
  proof. No airframe/gimbal, UI, cook, or Workshop claim is made here.

### Smoothed flight-profile reset graph frozen (2026-08-13)

- `ResetSmoothedFlightProfileV1` is now a deterministic 39/38-node full/paste
  graph. It preserves the segment-index and local-alpha inputs while clearing
  stage validity, current and neighbor IDs, all twenty current/neighbor numeric
  scratch values, neighbor weight, both public IDs, all eleven numeric public
  values, and public validity in one exact ordered execution chain.
- Exact contracts require every setter/default, forbid array operations and
  input mutation, require the native-entry seam only in the full form, reject
  reroute knots and external links, and prove the entire reciprocal execution
  chain. Full/paste SHA-256 is
  `2DD0DE130CF17F3E1F05BC5E19C84D5C06BF8020881904FF630A3F9567972572` /
  `0214BCC468EAD5365C945EF6DB1A02DC1CFD0C375954280180B048258C2DD239`.
- Repeated generation is byte-identical and the complete repository scaffold
  passes. This graph remains offline until the full four-function consumer set
  is frozen and installed together. Next is current/neighbor sample staging;
  no live reset, airframe/gimbal, UI, cook, or Workshop claim is made.

### Smoothed flight-profile sample staging frozen (2026-08-13)

- `StageSmoothedFlightProfileSamplesV1` is now a deterministic 120/119-node
  full/paste graph. It reads the actual immutable compiled-ID array length,
  requires valid compiled state, bounds count to 1..511 and requested index to
  the array, and rejects non-finite or out-of-range local alpha before calling
  the accepted indexed evaluator.
- A valid current helper result is copied completely into current scratch. A
  pure clamped previous/next/half-selection network chooses at most one
  neighbor without `Max_IntInt` or `Min_IntInt`; a valid neighbor helper result
  is copied completely into separate neighbor scratch. The right half uses the
  direct quintic smootherstep kernel; the left uses the symmetric stable form
  `0.5*smootherstep(1-2*alpha)` and an explicit 0..0.5 clamp. A self-neighbor at
  either endpoint is forced to exact zero.
- Four evaluator calls are deliberate: current, neighbor, restored current on
  success, and restored current after neighbor failure. The helper input is set
  to the requested index before validation and is explicitly restored on both
  neighbor exits. Stage validity is the sole acceptance write and occurs last;
  staging owns no public smoothed-result setter and mutates no array.
- Exact contracts cover every reciprocal execution/data edge, guard/default,
  complete eleven-field current and neighbor snapshots, all five Select nodes,
  both quintic coefficient sets, both restoration paths, stage-valid-last, and
  the absence of public publication. Full/paste SHA-256 is
  `8C0F1FC984156091B240CF854870BB930CA63F8A773A837072188F5C23DDE68F` /
  `F79DD2667557F8BB7EF8C2C506C9A74693BC38F877986A9925CB520CA2ACB69F`.
  Repeated generation is byte-identical and the complete scaffold passes.
- This graph remains offline with reset until atomic publication and the final
  orchestrator are frozen. Next is `PublishSmoothedFlightProfileV1`; no live
  smoothing, airframe/gimbal, UI, cook, or Workshop claim is made.

### Smoothed flight-profile atomic publication frozen (2026-08-13)

- `PublishSmoothedFlightProfileV1` is now a deterministic 210/209-node
  full/paste graph. It invalidates public validity first, clears both public
  IDs and all eleven public numeric values, then requires valid staging plus an
  explicitly finite neighbor weight inside 0..0.5. This complete clear prevents
  a rejected stage from exposing stale data from an earlier success.
- Current and neighbor IDs are independently passed through the accepted
  canonical resolver. Resolver validity, exact canonical identity, and all ten
  exact canonical numeric values must agree for each staged record before any
  result field can be written. All string equalities use StringLibrary with no
  hidden stale MathLibrary self pin.
- Zero weight or identical current/neighbor IDs normalize public metadata to
  current ID, current ID, exact zero. Otherwise the staged neighbor ID/weight
  survive. Each numeric result uses the symmetric convex form
  `current*(1-weight)+neighbor*weight`; all ten blended values must pass their
  inclusive or strict canonical domain bounds before one ordered thirteen-field
  publication chain begins. Public validity is the fourteenth and final write.
- Exact contracts prove both resolver boundaries, twenty value equalities,
  normalization BooleanOR and two typed Select nodes, every interpolation edge,
  every result bound, the atomic publication chain, no stage mutation, and no
  array operation. Full/paste SHA-256 is
  `2E82A0C1157115188D49B78F2320F3D269C054211ADBC69FA3139DB4D9E1E8C2` /
  `3639C0DD05EE4C35751593A8FFBC5BA2AE09F270EE577B450D5A56C3BB84CA1A`.
  Repeated generation is byte-identical.

- Dense graph installation exposed a reusable placement rule. Enhanced 5.6.1
  always translates a pasted selection so its bounding-box center lands under
  the cursor; viewport panning does not affect that translation. Therefore the
  reset, staging, and publication generators place their first executable node
  near the selection's geometric center on a clear vertical lane. After paste,
  the native entry and intended seam root are locally reachable without moving
  the native entry. Full/paste semantic contracts remain unchanged apart from
  deterministic layout hashes, and byte-identical regeneration was re-proven.
- Enhanced 5.6.1 normalizes ignored defaults on linked real-valued Select pins
  from `0` to `0.0` during paste. Exact contracts must identify an authored
  zero fallback by both its numeric value and its intentionally unlinked pin;
  counting the textual default alone falsely conflates linked data inputs with
  the fail-safe zero branch. The stage contract now enforces that distinction.
- Reset, staging, and publication remain offline until the orchestration graph
  is frozen and the four functions can be installed and tested together. Next
  is `EvaluateSmoothedFlightProfileV1`; no live smoothing, airframe/gimbal, UI,
  cook, or Workshop claim is made.

### Smoothed flight-profile orchestration frozen (2026-08-13)

- `EvaluateSmoothedFlightProfileV1` is a deliberately minimal deterministic
  4/3-node full/paste graph: `ResetSmoothedFlightProfileV1` executes first,
  `StageSmoothedFlightProfileSamplesV1` second, and
  `PublishSmoothedFlightProfileV1` last. Publish always runs, so reset clears
  stale fields and publication invalidates the public boundary even when stage
  acceptance remains false.
- Exact contracts require one self-context call per stage, the reciprocal
  reset-stage-publish execution chain, no variable access, no reroute knot, no
  alternate path, and no external link. Repeated generation is byte-identical;
  full/paste SHA-256 is
  `D741FC97E2E37D5DC1F44872F5E87F2DB99C3A2980CA8F9D39E2860E61078570` /
  `675F4780D43DB9C5968F9A57D73D692883B4B3B992A4A682795925C6077993F2`.
- The complete four-function smoothing graph set is now frozen offline and the
  complete repository scaffold passes. Next is joint live installation,
  compile/save, exact post-compile export contracts, cold load, and executable
  warm/fresh oracle/failure/restoration proof. No live smoothing,
  airframe/gimbal, UI, cook, or Workshop claim is made yet.

### Smoothed flight-profile runtime accepted (2026-08-13)

- Reset, stage, publish, and orchestration are installed together in
  `BPC_EDD_ClientDirector`, compiled, saved, mirrored, cold-loaded, and
  executable. Exact post-compile exports contain 39, 120, 210, and 4 nodes and
  hash respectively to
  `C5EC00928D582D1C25C3AB4B05BBE7D4F3987B359AA2664EBD4A348FAFF744B2`,
  `8213A3229E0C890B5E01D8B22A941DB7F98C5BB577777EF84E897E563B41C5EF`,
  `AC69E8B0BDBB9AB4B5CC664B25EA6F9DE35159BD59253F956A0F82394E96EDC4`,
  and `2C2AA34B47D285B9310AA2A60CCF6CA5ECF5E9A7FB7C09314E57DF632E6D9144`.
  All four pass the same reciprocal-link contracts as deterministic source.
- Warm execution and an independent fresh `-ModDevKit -NullRHI` process each
  pass 75 valid evaluations, four exact shared waypoint boundaries, 160
  reversed-order direct-scrub checks, five widely separated samples on the
  511-segment ceiling, 12 invalid inputs, five corrupt compiled publications,
  seven corrupt staged publications, and exact restoration of every touched
  CDO property.
- Executable evidence found three defects that graph shape alone could not.
  The original left-half subtraction produced `-4.440892098500626e-16` near
  the midpoint; the symmetric smootherstep form plus a final clamp removes the
  cancellation. Directional affine interpolation produced a one-ulp mismatch
  when current/neighbor identities swap across a waypoint; the symmetric convex
  form publishes identical boundary values. Finally, publication originally
  cleared only validity, leaving stale public payload after a rejected stage;
  the accepted graph now clears the complete public record before validation.
- Exact node counts caught one attempted replacement that retained 110 stale
  nodes before compile/save. The accepted workflow proves the cleared graph is
  exactly the immutable native entry, pastes once, re-exports the expected
  count, connects the one native seam, then re-exports and runs full contracts
  before compile. Serialized `NodePosX/NodePosY` and clipboard node identity are
  the authority; viewport appearance is not.
- Guarded shutdown completed without a crash reporter. A separate cold-load
  process loaded all nine core assets and compiled all six Blueprints with zero
  errors. Closed-editor live and mirrored Client Director SHA-256 both equal
  `349E21CF5EA7309273FCBADA668871B9C5BD2BA1825D53F08229D56D83557CA2`.
  `Test-Scaffold.ps1 -RequireMvpAssets` passes and now requires plus validates
  all four live smoothing exports and the executable runtime harness.
- Accepted scope is smooth, deterministic profile parameters only. The next
  ordered backend slice consumes them in cinematic/hybrid/FPV airframe and
  gimbal dynamics. Lens/focus/effects, shortcut dogfood, polished UI, cook,
  Workshop, and whole-mod completion remain unclaimed.

### Airframe/gimbal desired-pose contract frozen offline (2026-08-13)

- `airframe_gimbal_reference.py` now freezes the first shared motion primitive:
  a stateless desired body/gimbal pose from absolute-time velocity,
  look-ahead velocity, acceleration, jerk, authored body/gimbal quaternions,
  and the complete accepted smoothed profile. The profile look-ahead offset is
  consumed by the upstream absolute-time sampler; max angular rate is consumed
  by the later deterministic fixed-step compiler.
- The path frame uses local X forward/Y right/Z up, with deterministic current
  velocity and authored-forward fallbacks. Vertical tangents project authored
  up to prevent an arbitrary roll choice. Signed lateral acceleration produces
  gain-scaled, clamped bank; shortest-arc blends implement both path-follow body
  weight and body-lock-to-authored-world gimbal stabilization. Positive camera
  uptilt rotates around local negative Y.
- Acceleration, jerk, and finite-turn-radius gates run before result creation.
  Straight/stationary motion publishes the finite zero-radius sentinel rather
  than infinity. Every other diagnostic must remain finite. Boolean numeric
  impostors, malformed/non-unit quaternions, profile-domain errors, physical
  excess, and overflow-capable motion reject explicitly.
- Eleven executable reference tests cover exact endpoints, all three principal
  flight characters, signed clamp behavior, geometry/fallbacks, vertical and
  stationary cases, exact limit boundaries, invalid/corrupt input families,
  quaternion sign invariance, and 1,000 seeded samples evaluated forward and
  reverse. Five Blueprint-schema tests freeze 25 variables, reset/validate/
  solve ordering, all ten profile channels, fail-closed defaults, history
  independence, and validity-last publication. The full scaffold invokes both
  suites.
- This is offline contract evidence, not a live Blueprint claim. Next are
  deterministic reset, validation, and solve graph sources with exact
  reciprocal-link contracts, then joint install/compile/save, exact post-compile
  export, cold load, and warm/fresh oracle/failure/restoration execution. UI,
  cook, Workshop, and whole-mod completion remain unclaimed.

### Airframe/gimbal result reset graph frozen (2026-08-13)

- `ResetAirframeGimbalV1` is a deterministic 10/9-node full/paste transaction.
  It clears stage validity, resets body/gimbal/path results to identity
  quaternions, clears all four finite diagnostics to zero, and writes public
  result validity false last in one exact execution chain.
- The reset deliberately owns no input getter or setter. Exact contracts prove
  every default, reciprocal execution order, the sole native-entry seam in the
  full form, the exposed first setter in paste form, no external links, and no
  reroute knots. Repeated generation is byte-identical; full/paste SHA-256 is
  `3E2EC3EA46C1E20E9EB821EAAB3C79602FFD104192ABB94E6A837B431B12B56B` /
  `0551C908E4DABADFD44981A94086AD1372BA0AF6E3587B54F9B463544FD90721`.
- This reset remains offline until validation and solve are frozen and the
  three functions can be installed and executed together. No live
  airframe/gimbal, UI, cook, or Workshop claim is made.

### Airframe/gimbal input validation graph frozen (2026-08-13)

- `ValidateAirframeGimbalInputsV1` is a deterministic 165/164-node full/paste
  graph. It resets stage validity false, independently validates four
  three-component vectors, two quaternions, and all ten profile channels, then
  writes stage validity true only through one final acceptance branch.
- Each vector component and profile scalar uses explicit representable-double
  lower/upper bounds, avoiding the bytecode-foldable `x - x == 0` predicate.
  Each quaternion must pass native finiteness and an explicit magnitude window
  of `0.999999..1.000001`. Every profile channel has the same inclusive or
  strict bounds as the accepted canonical-profile and smoothing boundaries.
- Exact contracts prove one read-only getter per input, all twelve vector
  component finite guards, both quaternion finite/norm guards, all thirty
  profile finite/domain guards, 69 BooleanAND nodes (22 finite pairs plus the
  47-link aggregate), reset-before-branch, acceptance-only publication, no
  result publication, no external links, and no reroute knots. Repeated
  generation is byte-identical; full/paste SHA-256 is
  `BCFDB2694FD8381B1A508206C6456A5B77260E7B9C874178350B12E9BE364EED` /
  `C8316BEEC27C943A7E56A32E5ACDC5246CA96AC465DCDDA927BF320C16A4A091`.
- Reset and validation remain offline until desired-pose solve is frozen and
  all three functions can be installed/tested together. No live
  airframe/gimbal, UI, cook, or Workshop claim is made.

### Airframe/gimbal desired-pose solve graph frozen offline (2026-08-13)

- `SolveAirframeGimbalV1` is now deterministic source in 100/99-node
  full/paste forms. Full/paste SHA-256 is
  `C91776C45B72934322E9260649395C48A4E8F600F1A067FE70D581DA5BA25D4E` /
  `6B838FB982A40C32C7866111782F02C0A8E9DB444D2980C0130F9AD8D6063D89`.
  Repeated generation and checked-in artifacts are byte-identical.
- Execution is reset -> validate -> validation branch -> physical branch ->
  seven result setters -> validity true. Exact contracts prove the velocity
  look-ahead/current/authored fallback chain, stable vertical up reference,
  acceleration/jerk/radius limits, all diagnostic finite guards, signed bank
  derivation and clamp, local-X bank composition, local-Y Unreal uptilt
  composition, body/gimbal slerp endpoints, and valid-last publication.
- A real pure-node hazard was removed before freezing: Blueprint may evaluate
  both Select inputs, so radius division no longer consumes raw lateral
  acceleration in the no-turn case. A first Select supplies `1.0` unless a
  finite turn exists; a second Select publishes the required `0.0` straight or
  stationary sentinel. Thus the graph never asks the VM to evaluate `0 / 0`.
- Headless Enhanced API reflection confirmed native quaternion axis, Euler,
  vector-dot/normalize, and `Atan2` functions. Their ten reusable call forms,
  including rotator-to-quaternion conversion, are generated as an 11-node
  unsplit fixture with SHA-256
  `AAA9F712186D9AC55E85A2573CB4A881F2194666A25B2A39134339AF47808301`.
  The unsplit conversion deliberately replaces a harvested template whose
  quaternion output retained four stale float subpins.
- This is still offline source and semantic-contract evidence. The accepted
  reference oracle and schema tests pass, but there is no live airframe/gimbal
  claim until reset, validation, and solve are installed together, compile and
  save, survive an independent cold load, and match warm plus fresh executable
  oracle/failure/restoration cases. UI, cook, Workshop, and whole-mod
  completion remain unclaimed.

### Airframe/gimbal desired-pose live semantic acceptance (2026-08-13)

- `ResetAirframeGimbalV1`, `ValidateAirframeGimbalInputsV1`, and
  `SolveAirframeGimbalV1` are installed together on the live ClientDirector,
  compile and save successfully, and re-export as exact 10/165/100-node full
  graphs. Each post-compile export passes its original reciprocal-link and
  atomic-publication contract; graph shape is not being used as a substitute
  for runtime evidence.
- `Validate-AirframeGimbalRuntime.py` transactionally snapshots and restores
  all 25 touched CDO properties. Warm execution passes 16 directed valid
  cases, 27 poisoned fail-closed cases, 160 seeded cases in forward and reverse
  order, exact reset/input-immutability boundaries, physical limits,
  quaternion sign equivalence, overflow, non-finite input handling, and a
  final `STATE_RESTORED|True` marker.
- Two engine-native semantics were learned from the executable comparison and
  encoded in the independent oracle. Unreal Euler X/roll is left-handed, so
  its local roll quaternion corresponds to the reference helper's negative X
  axis. At an exactly vertical path with parallel up hint,
  `MakeRotFromXZ -> RotatorToQuaternion` chooses a deterministic negative-vector
  half-turn representative; that sign selects the intended shortest-arc slerp
  branch even though either sign represents the same terminal rotation.
- `AirframeGimbalStageValidV1` reports structural input/profile validity.
  Therefore structurally valid samples that later fail acceleration, jerk,
  radius, or derived-finiteness gates retain stage validity while every public
  result is reset and `AirframeGimbalResultValidV1` stays false. Invalid
  structural inputs clear both stage and result validity.
- Find Results does not refresh when automation merely replaces its query.
  `Export-BlueprintFunctions.ps1` now sends Enter explicitly before opening a
  result, and every export still has an exact expected-node-count gate. This
  prevents a superficially successful run from silently copying the previously
  selected function.
- Guarded shutdown produced no new crash report. A separate NullRHI process
  loaded all nine core assets and compiled all six Blueprints with zero errors;
  a second fresh process repeated the complete 16/27/160 runtime matrix and
  restored state. The live and Git-mirror ClientDirector hashes are identical
  at `3B0E5782D14B6762D8E8212292517215C7126CD743F4DF8186FB8E3CFBDCA04F`,
  and the full repository scaffold passes. No fixed-step angular-rate compiler,
  UI, cook, Workshop, or whole-mod completion is claimed here.

### Fixed-step airframe/gimbal prebake contract frozen offline (2026-08-13)

- `airframe_gimbal_prebake_reference.py` owns the first stateful motion layer
  above the accepted history-free desired-pose solver. Its deterministic
  schedule is time zero, integer fixed steps, and one exact terminal sample;
  sample count is `ceil(total / step) + 1` and is rejected above 65,536 before
  candidate allocation.
- The first body/gimbal samples seed a shot exactly. Later samples limit body
  and gimbal independently over the shortest quaternion arc, using the real
  interval duration and the stricter angular-rate value at the two interval
  endpoints. This makes smoothly changing profile limits safe without using
  game-frame delta. Cuts intentionally begin a new seeded compilation.
- Quaternion signs are canonicalized before limiting. Exact 180-degree arcs use
  a scalar-then-vector lexicographic tie-break, after which compiled samples are
  sign-continuous. Entire `q`/`-q` input streams therefore produce identical
  serialized results rather than merely equivalent physical rotations.
- Candidate and compiled payloads each carry body/gimbal quaternions, measured
  rates, and rate-limited flags. The Blueprint schema reserves 29 explicit
  variables plus eleven isolated limiter scratch fields, and seven ordered
  functions for reset, validation, the limiter primitive, sample build, atomic
  commit, orchestration, and absolute-time evaluation. The evaluator
  rejects malformed compiled cardinality, schedule, quaternion, boolean, or
  measured-rate state before returning a pose.
- Nineteen oracle tests and six schema tests pass, including 100 seeded streams
  in forward/reverse invocation order, terminal partial intervals, exact rate
  boundaries, changing endpoint limits, antipodal and half-turn input,
  independent body/gimbal clamping, corrupt publications, and arbitrary scrub
  order. The full scaffold includes these suites. This checkpoint does not yet
  claim Blueprint graph bodies, live compile/runtime evidence, desired-stream
  orchestration, angular acceleration, UI, cook, or Workshop readiness.

### Fixed-step airframe/gimbal reset graph frozen (2026-08-13)

- `ResetAirframePrebakeCandidateV1` is generated as exact 36/35-node full/paste
  graphs. It clears six candidate arrays and their six compiled mirrors, resets
  the candidate index/validity, compiled schedule/validity, and all absolute-time
  evaluation results. Body and gimbal results return to identity, segment index
  to `-1`, and every validity flag to false.
- The graph never reads or mutates desired body/gimbal samples, per-sample rate
  limits, total time, fixed step, or elapsed-time input. Contracts require one
  execution chain, reciprocal internal links, exact defaults, no reroutes, no
  external graph links, and byte-identical regeneration. This remains offline
  until validation and the remaining prebake stages are frozen together.

### Fixed-step airframe/gimbal validation graph frozen (2026-08-13)

- `ValidateAirframePrebakeInputsV1` generates as exact 73/72-node full/paste
  graphs. Sample count is bounded to `2..65536`; body, gimbal, and rate arrays
  must have equal cardinality. Total time and fixed step are finite and bounded.
- The exact `ceil(total / step) + 1` schedule is checked without division or a
  missing ceiling node: `(count - 2) * step < total <= (count - 1) * step`.
  This remains safe under eager pure-node evaluation even for rejected small
  counts. Both quaternion loops require finite values and magnitude in the
  inclusive `1 +/- 1e-6` window; each rate is finite and `0 < rate <= 720`.
- A graph interpreter executes both generated forms across 103 valid schedules
  and 28 invalid families, including cardinality, schedule edges, scalar
  non-finites, quaternion zero/nonunit/nonfinite values, and rate bounds. Stage
  validity is accepted once and can only be rejected by the three loops;
  compiled and evaluation state is never written. Exact links, unsafe forms,
  byte reproducibility, and the complete scaffold also pass. Sample build is
  next; no live prebake, UI, cook, or Workshop claim is made.

### Atomic airframe angular-rate limiter frozen offline (2026-08-13)

- `ApplyAirframeAngularRateLimitV1` uses four explicit input scratch fields and
  four explicit result fields so the later sample loop has a narrow, observable
  call boundary despite Enhanced Blueprint automation not providing reliable
  parameter creation. It never writes authored, candidate, compiled, or
  evaluation publication state.
- Each call first resets result quaternion/rate/limited/valid to identity, zero,
  false, false. Previous and desired quaternions must be finite with magnitude
  in the inclusive `1 +/- 1e-6` window; delta must be finite in `(0, 0.5]`; max
  rate must be finite in `(0, 720]`. Rejection terminates after reset.
- Accepted inputs preserve the authoritative previous sample's normalized
  hemisphere. Authored desired input is canonicalized by scalar-first then vector
  lexicographic sign and aligned to the previous
  representative, and one native `Quat_AngularDistance` plus one `Quat_Slerp`
  applies `clamp(delta * maxRate / angle, 0, 1)`. Selected nonzero denominators
  make pure-node evaluation safe even if an invalid call is inspected.
- The deterministic graph has 109 full nodes and 108 paste nodes. An executable
  graph interpreter proves both forms against the independent Python oracle for
  five directed and 200 seeded valid cases, 20 poisoned invalid cases, input
  immutability, exact-boundary limited flags, and three byte-identical
  antipodal half-turn pairs. Native node-form shape, reciprocal links, exact
  node counts, unsafe-form absence, and repeated-generation hashes are also
  enforced by the full scaffold.
- This remains an offline primitive. The next ordered slice is
  `BuildAirframePrebakeSamplesV1`; there is still no live prebake, UI, cook,
  Workshop, or whole-mod readiness claim.

### Fixed-step airframe/gimbal sample builder frozen offline (2026-08-13)

- `BuildAirframePrebakeSamplesV1` clears its six private candidate arrays and
  stage index before inspecting upstream validation. A false stage exits with
  empty candidates. Sample zero is deliberately handled before the loop:
  identity plus a `0.5 * 720 = 360` degree budget canonicalizes any authored
  unit quaternion without limiting it, so the first desired body/gimbal pose is
  seeded exactly and deterministically.
- One `ForLoopWithBreak` starts at index one. The prior candidate sample is
  always available, avoiding speculative `array[-1]` reads. Interior intervals
  use fixed step; the terminal interval uses
  `total - (index - 1) * step`. The rate passed to each body and gimbal helper
  call is `min(rate[index-1], rate[index])`.
- Each successful helper invocation appends quaternion, analytic angular rate,
  and limited flag in a single execution chain. Any helper rejection marks the
  stage invalid and breaks. Partial candidates are never authoritative and the
  later commit boundary must reject them whenever stage validity is false.
- Deterministic full/paste graphs contain 81/80 nodes. Their executable graph
  interpreters match the independent full-stream compiler for three directed
  and 100 seeded schedules, including long and partial-terminal schedules;
  also proven are whole-stream antipodal byte equivalence, input immutability,
  false-stage empty output, and injected seed/loop helper failures. Repeated
  generation, reciprocal links, exact counts, and the full repository scaffold
  enforce the checkpoint.
- The composition tests exposed and corrected a prior-isolated-contract flaw:
  the limiter now preserves the authoritative previous compiled hemisphere and
  canonicalizes only authored targets. This maintains serialized continuity
  across repeated calls while retaining deterministic desired `q`/`-q`
  equivalence. Atomic commit is next; no live prebake, UI, cook, Workshop, or
  whole-mod readiness claim is made.
