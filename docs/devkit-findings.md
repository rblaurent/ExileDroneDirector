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

## Pending local reconnaissance

- Concrete Conan-character view restoration in a gameplay-map PIE run
- Hands-on remote-client raw-mouse pitch/yaw and physical-wheel feel
- Remaining death, teleport, disconnect, UI-close, and component-end-play hooks
- Emergency camera restoration and the view lifecycle in cooked runtime
- Exact Enhanced cook command/commandlet, output layout, and Workshop metadata
- First normal-game `.pak` load and controlled Workshop update
- Authenticated server identity and persistence APIs
