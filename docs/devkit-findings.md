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
