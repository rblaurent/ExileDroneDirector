r"""Deterministic two-player PIE acceptance for the linear playback kernel.

Preferred use is to arm the automatic post-tick driver before starting a
two-player listen-server PIE session:

    py EDD_PHASE='arm'; exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-LinearPlaybackPIE.py').read())
    # Start PIE once. The driver samples, cleans up, and ends PIE by itself.

The individual phases remain available for diagnosis while PIE is active:

    py EDD_PHASE='prepare'; exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-LinearPlaybackPIE.py').read())
    # wait roughly 1.5 seconds
    py EDD_PHASE='inspect_active'; exec(open(...).read())
    # wait until at least 6.5 seconds after prepare
    py EDD_PHASE='inspect_complete'; exec(open(...).read())
    # wait roughly one second
    py EDD_PHASE='stop_and_cleanup'; exec(open(...).read())

The probe never sleeps on the game thread. It samples ordinary EventGraph tick
playback against the absolute-time formula and leaves playback stopped with the
original host view restored.
"""

from __future__ import annotations

import time
import traceback

import unreal


PREFIX = "EDD_LINEAR_PLAYBACK_PIE"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
DRONE_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C"
DEFAULT_PAWN_CLASS_PATH = "/Script/Engine.DefaultPawn"
WORLD_PATHS = (
    "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty",
    "/Game/Dev/UEDPIE_1_AlmostEmpty.AlmostEmpty",
)
CHANNELS = (
    "DraftWaypointIds",
    "DraftWaypointTransforms",
    "DraftWaypointFocalLengths",
    "DraftWaypointApertures",
    "DraftWaypointFocusDistances",
    "DraftWaypointHoldSeconds",
)
LOCATIONS = (
    unreal.Vector(1100.0, 100.0, 800.0),
    unreal.Vector(1500.0, -300.0, 1000.0),
    unreal.Vector(2100.0, 500.0, 1400.0),
)
ROTATIONS = (
    unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0),
    unreal.Rotator(pitch=20.0, yaw=90.0, roll=0.0),
    unreal.Rotator(pitch=-10.0, yaw=170.0, roll=30.0),
)
SEGMENT_SECONDS = 3.0


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}:{message}")


def load_class(path: str):
    result = unreal.load_class(None, path)
    require(result is not None, f"class missing:{path}")
    return result


def world(index: int):
    result = unreal.find_object(None, WORLD_PATHS[index])
    require(result is not None, f"PIE world missing:{WORLD_PATHS[index]}")
    return result


def controller(world_object, index: int):
    result = unreal.GameplayStatics.get_player_controller(world_object, index)
    require(result is not None, f"PlayerController {index} missing in {world_object.get_path_name()}")
    return result


def director(player_controller):
    components = player_controller.get_components_by_class(load_class(CLIENT_CLASS_PATH))
    require(len(components) == 1, f"expected one client director, found {len(components)}")
    return components[0]


def exact_actors(world_object, actor_class):
    return [
        actor
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world_object, actor_class)
        if actor.get_class() == actor_class
    ]


def get_value(obj, name: str):
    return obj.get_editor_property(name)


def channels(component) -> dict[str, list]:
    return {name: list(get_value(component, name)) for name in CHANNELS}


def require_lengths(component, expected: int) -> None:
    lengths = {name: len(value) for name, value in channels(component).items()}
    require(all(length == expected for length in lengths.values()), f"lockstep lengths expected {expected}, got {lengths}")


def close_number(actual, expected: float, tolerance: float = 0.05) -> None:
    require(abs(float(actual) - float(expected)) <= tolerance, f"expected {expected}, received {actual}")


def require_vector(actual, expected, tolerance: float = 0.05) -> None:
    for received, wanted in zip((actual.x, actual.y, actual.z), (expected.x, expected.y, expected.z)):
        close_number(received, wanted, tolerance)


def require_rotation(actual_quat, expected_rotator, tolerance: float = 0.05) -> None:
    actual = actual_quat.rotator()
    for received, wanted in zip(
        (actual.pitch, actual.yaw, actual.roll),
        (expected_rotator.pitch, expected_rotator.yaw, expected_rotator.roll),
    ):
        delta = (float(received) - float(wanted) + 180.0) % 360.0 - 180.0
        require(abs(delta) <= tolerance, f"rotation expected {expected_rotator}, received {actual}")


def require_transform(actual, expected, *, exact_rotation: bool = True) -> None:
    require_vector(actual.translation, expected.translation)
    if exact_rotation:
        require_rotation(actual.rotation, expected.rotation.rotator())


def midpoint(left, right):
    return unreal.Vector(
        (left.x + right.x) * 0.5,
        (left.y + right.y) * 0.5,
        (left.z + right.z) * 0.5,
    )


def game_time(world_object) -> float:
    return float(unreal.SystemLibrary.get_game_time_in_seconds(world_object))


def force_game_input(player_controller) -> None:
    widget_library = unreal.get_default_object(load_class("/Script/UMG.WidgetBlueprintLibrary"))
    try:
        widget_library.set_input_mode_game_only(player_controller, True)
    except TypeError:
        widget_library.set_input_mode_game_only(player_controller)
    emit("INPUT_MODE", "game-only")


def prepare_fixture():
    server_world = world(0)
    pawn_class = load_class(DEFAULT_PAWN_CLASS_PATH)
    pawns = exact_actors(server_world, pawn_class)
    while len(pawns) < 2:
        unreal.SystemLibrary.execute_console_command(server_world, "summon /Script/Engine.DefaultPawn")
        pawns = exact_actors(server_world, pawn_class)
    pawns.sort(key=lambda actor: actor.get_path_name())
    for index, pawn in enumerate(pawns[:2]):
        pawn.set_actor_location(unreal.Vector(500.0 + index * 400.0, 0.0, 700.0), False, False)
        controller(server_world, index).possess(pawn)
    emit("FIXTURE", "two server controllers possess exact DefaultPawn instances")


def live_context():
    server_world = world(0)
    client_world = world(1)
    host = controller(server_world, 0)
    remote = controller(client_world, 0)
    component = director(host)
    remote_component = director(remote)
    drones = exact_actors(server_world, load_class(DRONE_CLASS_PATH))
    require(len(drones) == 1, f"expected one host drone, found {len(drones)}")
    return server_world, client_world, host, remote, component, remote_component, drones[0]


def cleanup(component) -> None:
    component.call_method("StopLinearPlayback")
    if bool(get_value(component, "DroneModeActive")):
        component.call_method("ExitDroneMode")


def seed_playback_fixture(component, drone) -> None:
    try:
        initial_transform = drone.get_actor_transform()
        component.call_method("StartLinearPlayback")
        require(not bool(get_value(component, "PlaybackActive")), "empty draft started playback")
        require_transform(drone.get_actor_transform(), initial_transform)
        emit("EMPTY_DRAFT_NOOP", True)

        captured = []
        for index, (location, rotation) in enumerate(zip(LOCATIONS, ROTATIONS)):
            require(drone.set_actor_location(location, False, False), f"failed to seed location {index}")
            require(drone.set_actor_rotation(rotation, False), f"failed to seed rotation {index}")
            component.call_method("CaptureCurrentWaypoint")
            captured.append(channels(component)["DraftWaypointTransforms"][index])
            if index == 0:
                component.call_method("StartLinearPlayback")
                require(not bool(get_value(component, "PlaybackActive")), "single-waypoint draft started playback")
                emit("SINGLE_WAYPOINT_NOOP", True)

        require_lengths(component, 3)
        close_number(get_value(component, "PlaybackSecondsPerSegment"), SEGMENT_SECONDS, 0.0001)
        component.call_method("StartLinearPlayback")
        require(bool(get_value(component, "PlaybackActive")), "valid draft did not start playback")
        require_transform(drone.get_actor_transform(), captured[0])
        emit("START_SNAP_VALID", True)
        emit("READY_FOR_ACTIVE_SAMPLE", True)
    except Exception:
        cleanup(component)
        raise


def prepare() -> None:
    prepare_fixture()
    server_world = world(0)
    client_world = world(1)
    host = controller(server_world, 0)
    remote = controller(client_world, 0)
    component = director(host)
    remote_component = director(remote)
    host_pawn = host.get_controlled_pawn()
    remote_pawn = remote.get_controlled_pawn()
    original_view = host.get_view_target()
    require(host_pawn is not None and original_view is not None, "host pawn/view baseline missing")
    require_lengths(component, 0)
    require_lengths(remote_component, 0)
    require(not bool(get_value(component, "PlaybackActive")), "host playback active at baseline")
    require(not bool(get_value(remote_component, "PlaybackActive")), "remote playback active at baseline")
    emit(
        "TICK_BASELINE",
        (
            f"host_enabled={component.is_component_tick_enabled()}|"
            f"remote_enabled={remote_component.is_component_tick_enabled()}|"
            f"host_owner_exact={component.get_owner() == host}"
        ),
    )

    if bool(get_value(component, "DroneModeActive")):
        component.call_method("ExitDroneMode")
    component.call_method("EnterDroneMode")
    drone_class = load_class(DRONE_CLASS_PATH)
    drones = exact_actors(server_world, drone_class)
    require(len(drones) == 1, f"expected one host drone, found {len(drones)}")
    drone = drones[0]
    require(host.get_controlled_pawn() == host_pawn, "Drone Mode changed host possession")
    require(host.get_view_target() == drone, "Drone Mode did not switch to host drone")

    seed_playback_fixture(component, drone)


def prepare_automatic_baseline() -> None:
    prepare_fixture()
    server_world = world(0)
    client_world = world(1)
    host = controller(server_world, 0)
    remote = controller(client_world, 0)
    component = director(host)
    remote_component = director(remote)
    force_game_input(host)
    require(host.get_controlled_pawn() is not None, "automatic host pawn baseline missing")
    require_lengths(component, 0)
    require_lengths(remote_component, 0)
    require(not bool(get_value(component, "DroneModeActive")), "automatic host Drone Mode active at baseline")
    require(not bool(get_value(component, "PlaybackActive")), "automatic host playback active at baseline")
    require(not bool(get_value(remote_component, "PlaybackActive")), "automatic remote playback active at baseline")
    emit(
        "TICK_BASELINE",
        (
            f"host_enabled={component.is_component_tick_enabled()}|"
            f"remote_enabled={remote_component.is_component_tick_enabled()}|"
            f"host_owner_exact={component.get_owner() == host}"
        ),
    )
    emit("AUTOMATIC_READY_FOR_F10", True)


def prepare_automatic_after_enter() -> None:
    server_world = world(0)
    host = controller(server_world, 0)
    component = director(host)
    require(bool(get_value(component, "DroneModeActive")), "physical F10 did not activate Drone Mode")
    drones = exact_actors(server_world, load_class(DRONE_CLASS_PATH))
    require(len(drones) == 1, f"physical F10 expected one host drone, found {len(drones)}")
    require(host.get_view_target() == drones[0], "physical F10 did not switch to the host drone")
    emit("PHYSICAL_F10_VALID", True)
    seed_playback_fixture(component, drones[0])


def inspect_active() -> None:
    server_world, _, host, _, component, _, drone = live_context()
    transforms = channels(component)["DraftWaypointTransforms"]
    require(len(transforms) == 3, "active sample lost authored transforms")
    duration = float(get_value(component, "PlaybackSecondsPerSegment"))
    elapsed = game_time(server_world) - float(get_value(component, "PlaybackStartTimeSeconds"))
    total = duration * (len(transforms) - 1)
    require(0.2 < elapsed < total - 0.2, f"active sample outside traversal:{elapsed}/{total}")
    require(bool(get_value(component, "PlaybackActive")), "playback inactive during traversal sample")
    segment = min(int(elapsed // duration), len(transforms) - 2)
    alpha = (elapsed - segment * duration) / duration
    left = transforms[segment].translation
    right = transforms[segment + 1].translation
    expected = unreal.Vector(
        left.x + (right.x - left.x) * alpha,
        left.y + (right.y - left.y) * alpha,
        left.z + (right.z - left.z) * alpha,
    )
    location_before_direct_call = drone.get_actor_location()
    try:
        require_vector(location_before_direct_call, expected, 12.0)
    except Exception:
        component.call_method("UpdateLinearPlayback")
        location_after_direct_call = drone.get_actor_location()
        emit(
            "UPDATE_DISPATCH_DIAGNOSTIC",
            (
                f"elapsed={elapsed:.3f}|expected={expected}|"
                f"before={location_before_direct_call}|after_direct_call={location_after_direct_call}|"
                f"active_after={bool(get_value(component, 'PlaybackActive'))}|"
                f"tick_enabled={component.is_component_tick_enabled()}|"
                f"owner_exact={component.get_owner() == host}|"
                f"local_controller_exact={controller(server_world, 0) == host}|"
                f"drone_mode_active={bool(get_value(component, 'DroneModeActive'))}"
            ),
        )
        raise
    require(int(get_value(component, "SelectedWaypointIndex")) == segment, "active sample selected wrong segment")
    require(host.get_controlled_pawn() is not None, "active sample lost host possession")
    emit("ACTIVE_ABSOLUTE_TIME_SAMPLE_VALID", f"elapsed={elapsed:.3f}|segment={segment}|alpha={alpha:.3f}")
    emit("READY_FOR_COMPLETION_SAMPLE", True)


def inspect_complete() -> None:
    server_world, _, host, _, component, _, drone = live_context()
    transforms = channels(component)["DraftWaypointTransforms"]
    duration = float(get_value(component, "PlaybackSecondsPerSegment"))
    elapsed = game_time(server_world) - float(get_value(component, "PlaybackStartTimeSeconds"))
    total = duration * (len(transforms) - 1)
    require(elapsed >= total, f"completion sampled too early:{elapsed}/{total}")
    require(bool(get_value(component, "PlaybackActive")), "playback did not hold the final endpoint")
    require_transform(drone.get_actor_transform(), transforms[-1])
    require(int(get_value(component, "SelectedWaypointIndex")) == len(transforms) - 1, "completion selected wrong waypoint")
    require(host.get_controlled_pawn() is not None, "completion lost host possession")
    emit("COMPLETION_ENDPOINT_HOLD_VALID", True)

    component.call_method("StopLinearPlayback")
    require(not bool(get_value(component, "PlaybackActive")), "completion hold did not stop explicitly")
    require_transform(drone.get_actor_transform(), transforms[-1])
    component.call_method("StartLinearPlayback")
    require(bool(get_value(component, "PlaybackActive")), "restart failed before explicit stop")
    require_transform(drone.get_actor_transform(), transforms[0])
    emit("RESTART_SNAP_VALID", True)
    emit("READY_FOR_STOP_SAMPLE", True)


def stop_and_cleanup() -> None:
    server_world, client_world, host, remote, component, remote_component, drone = live_context()
    host_pawn = host.get_controlled_pawn()
    remote_pawn = remote.get_controlled_pawn()
    original_view = get_value(component, "OriginalViewTargetRef")
    elapsed = game_time(server_world) - float(get_value(component, "PlaybackStartTimeSeconds"))
    require(elapsed > 0.2, f"stop sample did not traverse:{elapsed}")
    require(bool(get_value(component, "PlaybackActive")), "playback inactive before explicit stop")
    stopped_transform = drone.get_actor_transform()
    component.call_method("StopLinearPlayback")
    require(not bool(get_value(component, "PlaybackActive")), "explicit stop did not clear PlaybackActive")
    require_transform(drone.get_actor_transform(), stopped_transform)
    emit("EXPLICIT_STOP_VALID", True)

    require_lengths(remote_component, 0)
    require(not bool(get_value(remote_component, "PlaybackActive")), "host playback state leaked to remote client")
    require(len(exact_actors(client_world, load_class(DRONE_CLASS_PATH))) == 0, "host drone leaked to remote client world")
    require(remote.get_controlled_pawn() == remote_pawn, "remote possession changed")
    emit("CLIENT_ISOLATION_VALID", True)

    require(host.get_controlled_pawn() == host_pawn, "playback changed host possession")
    component.call_method("ExitDroneMode")
    require(not bool(get_value(component, "PlaybackActive")), "exit left playback active")
    require(host.get_controlled_pawn() == host_pawn, "exit changed host possession")
    require(original_view is not None and host.get_view_target() == original_view, "exit did not restore exact original view")
    emit("POSSESSION_AND_RESTORATION_VALID", True)
    emit("COMPLETE", True)


def _finish_automatic(success: bool) -> None:
    state = globals().get("_EDD_AUTOMATIC_STATE")
    if not state:
        return
    handle = state.get("callback")
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        state["callback"] = None
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def _automatic_tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_AUTOMATIC_STATE"]
    try:
        stage = state["stage"]
        if stage == "wait_for_pie":
            try:
                server_world = world(0)
                client_world = world(1)
                director(controller(server_world, 0))
                director(controller(client_world, 0))
            except Exception:
                if time.monotonic() - state["armed_at"] > 45.0:
                    raise RuntimeError(f"{PREFIX}:PIE did not become ready within 45 seconds")
                return
            prepare_automatic_baseline()
            state["stage"] = "wait_for_mode"
            state["mode_wait_started"] = time.monotonic()
            emit("AUTOMATIC_STAGE", "wait_for_mode")
            return

        if stage == "wait_for_mode":
            server_world = world(0)
            component = director(controller(server_world, 0))
            if not bool(get_value(component, "DroneModeActive")):
                if time.monotonic() - state["mode_wait_started"] > 30.0:
                    raise RuntimeError(f"{PREFIX}:physical F10 was not received within 30 seconds")
                return
            prepare_automatic_after_enter()
            state["stage"] = "active"
            emit("AUTOMATIC_STAGE", "active")
            return

        server_world, _, _, _, component, _, _ = live_context()
        elapsed = game_time(server_world) - float(get_value(component, "PlaybackStartTimeSeconds"))
        duration = float(get_value(component, "PlaybackSecondsPerSegment"))
        total = duration * (len(channels(component)["DraftWaypointTransforms"]) - 1)

        if stage == "active" and elapsed >= 1.0:
            inspect_active()
            state["stage"] = "completion"
            emit("AUTOMATIC_STAGE", "completion")
            return

        if stage == "completion" and elapsed >= total + 0.15:
            inspect_complete()
            state["stage"] = "stop"
            emit("AUTOMATIC_STAGE", "stop")
            return

        if stage == "stop" and elapsed >= 0.8:
            stop_and_cleanup()
            state["stage"] = "complete"
            _finish_automatic(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}:AUTOMATIC_EXCEPTION:{error}\n{traceback.format_exc()}")
        try:
            server_world = world(0)
            cleanup(director(controller(server_world, 0)))
        except Exception as cleanup_error:
            unreal.log_error(f"{PREFIX}:AUTOMATIC_CLEANUP_EXCEPTION:{cleanup_error}")
        state["stage"] = "failed"
        _finish_automatic(False)


def arm_automatic() -> None:
    existing = globals().get("_EDD_AUTOMATIC_STATE")
    if existing and existing.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(existing["callback"])
    state = {
        "stage": "wait_for_pie",
        "armed_at": time.monotonic(),
        "callback": None,
    }
    globals()["_EDD_AUTOMATIC_STATE"] = state
    state["callback"] = unreal.register_slate_post_tick_callback(_automatic_tick)
    emit("AUTOMATIC_ARMED", True)


phase = globals().get("EDD_PHASE", "")
phases = {
    "arm": arm_automatic,
    "prepare": prepare,
    "inspect_active": inspect_active,
    "inspect_complete": inspect_complete,
    "stop_and_cleanup": stop_and_cleanup,
}
require(phase in phases, f"unknown phase:{phase}")
phases[phase]()
