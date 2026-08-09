r"""Phased deterministic PIE acceptance probe for CaptureCurrentWaypoint.

Run from the editor console while two-player PIE is active:

    py EDD_PHASE='prepare'; exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-WaypointCapturePIE.py').read())
    # focus the host viewport and press K once
    py EDD_PHASE='inspect1'; exec(open(...).read())
    # press K once again
    py EDD_PHASE='inspect2'; exec(open(...).read())

When character-creation UI owns keyboard focus, use ``capture1`` and
``capture2`` to invoke the same Blueprint function directly. The checked-in
EventGraph contract separately proves the K-edge dispatch topology.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_WAYPOINT_PIE"
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
FIRST_LOCATION = unreal.Vector(1111.0, 222.0, 888.0)
FIRST_ROTATION = unreal.Rotator(pitch=34.0, yaw=5.0, roll=12.0)
FIRST_LENS = (35.0, 2.8, 1000.0)
SECOND_LOCATION = unreal.Vector(1444.0, -333.0, 999.0)
SECOND_ROTATION = unreal.Rotator(pitch=60.0, yaw=163.0, roll=172.0)
SECOND_LENS = FIRST_LENS


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}:{message}")


def load_class(path: str):
    cls = unreal.load_class(None, path)
    require(cls is not None, f"class missing:{path}")
    return cls


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
    require(len(components) == 1, f"expected one client director on {player_controller.get_path_name()}, found {len(components)}")
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


def require_lengths(values: dict[str, list], expected: int) -> None:
    lengths = {name: len(value) for name, value in values.items()}
    require(all(length == expected for length in lengths.values()), f"lockstep lengths expected {expected}, received {lengths}")
    emit("LENGTHS", lengths)


def close_number(actual, expected: float, tolerance: float = 0.001) -> None:
    require(abs(float(actual) - expected) <= tolerance, f"expected {expected}, received {actual}")


def vector_tuple(value) -> tuple[float, float, float]:
    return float(value.x), float(value.y), float(value.z)


def rotator_tuple(value) -> tuple[float, float, float]:
    return float(value.pitch), float(value.yaw), float(value.roll)


def require_vector(actual, expected) -> None:
    for received, wanted in zip(vector_tuple(actual), vector_tuple(expected)):
        close_number(received, wanted)


def require_rotation(actual, expected) -> None:
    for received, wanted in zip(rotator_tuple(actual), rotator_tuple(expected)):
        delta = (received - wanted + 180.0) % 360.0 - 180.0
        require(abs(delta) <= 0.01, f"rotation expected {rotator_tuple(expected)}, received {rotator_tuple(actual)}")


def require_transform(actual, location, rotation) -> None:
    require_vector(actual.translation, location)
    require_rotation(actual.rotation.rotator(), rotation)


def seed_camera(drone, location, rotation, lens) -> None:
    require(drone.set_actor_location(location, False, False), "failed to set drone location")
    require(drone.set_actor_rotation(rotation, False), "failed to set drone rotation")
    close_number(get_value(drone, "FocalLength"), lens[0])
    close_number(get_value(drone, "Aperture"), lens[1])
    close_number(get_value(drone, "ManualFocusDistance"), lens[2])
    emit("SEEDED", f"{location}|{rotation}|{lens}")


def prepare_fixture():
    server_world = world(0)
    default_class = load_class(DEFAULT_PAWN_CLASS_PATH)
    pawns = exact_actors(server_world, default_class)
    while len(pawns) < 2:
        unreal.SystemLibrary.execute_console_command(server_world, "summon /Script/Engine.DefaultPawn")
        pawns = exact_actors(server_world, default_class)
    pawns.sort(key=lambda actor: actor.get_path_name())
    placements = (
        (unreal.Vector(1000.0, 0.0, 700.0), unreal.Rotator(0.0, 0.0, 0.0)),
        (unreal.Vector(1500.0, 500.0, 800.0), unreal.Rotator(0.0, 90.0, 0.0)),
    )
    for index, (location, rotation) in enumerate(placements):
        pawns[index].set_actor_location(location, False, False)
        pawns[index].set_actor_rotation(rotation, False)
        controller(server_world, index).possess(pawns[index])
    emit("FIXTURE", "server controllers possess exact DefaultPawn instances")


def force_game_input(player_controller) -> None:
    widget_library = unreal.get_default_object(
        load_class("/Script/UMG.WidgetBlueprintLibrary")
    )
    try:
        widget_library.set_input_mode_game_only(player_controller, True)
    except TypeError:
        widget_library.set_input_mode_game_only(player_controller)
    emit("INPUT_MODE", "game-only")


def prepare() -> None:
    prepare_fixture()
    server_world = world(0)
    host = controller(server_world, 0)
    force_game_input(host)
    component = director(host)
    baseline = channels(component)
    require_lengths(baseline, 0)
    require(int(get_value(component, "NextWaypointId")) == 1, "NextWaypointId baseline must be 1")
    original = host.get_controlled_pawn()
    require(original is not None and original.get_class() == load_class(DEFAULT_PAWN_CLASS_PATH), "host fixture pawn missing")
    component.call_method("EnterDroneMode")
    drones = exact_actors(server_world, load_class(DRONE_CLASS_PATH))
    require(len(drones) == 1, f"host world expected one local drone, found {len(drones)}")
    require(host.get_controlled_pawn() == original, "Drone Mode changed host possession")
    require(host.get_view_target() == drones[0], "host view target did not switch to drone")
    seed_camera(drones[0], FIRST_LOCATION, FIRST_ROTATION, FIRST_LENS)
    emit("READY_FOR_K1", True)


def inspect_first() -> None:
    server_world = world(0)
    component = director(controller(server_world, 0))
    values = channels(component)
    require_lengths(values, 1)
    require(values["DraftWaypointIds"] == [1], f"first IDs incorrect:{values['DraftWaypointIds']}")
    require_transform(values["DraftWaypointTransforms"][0], FIRST_LOCATION, FIRST_ROTATION)
    close_number(values["DraftWaypointFocalLengths"][0], FIRST_LENS[0])
    close_number(values["DraftWaypointApertures"][0], FIRST_LENS[1])
    close_number(values["DraftWaypointFocusDistances"][0], FIRST_LENS[2])
    close_number(values["DraftWaypointHoldSeconds"][0], 0.0)
    require(int(get_value(component, "NextWaypointId")) == 2, "NextWaypointId must advance to 2")
    drones = exact_actors(server_world, load_class(DRONE_CLASS_PATH))
    require(len(drones) == 1, "host drone missing before second capture")
    seed_camera(drones[0], SECOND_LOCATION, SECOND_ROTATION, SECOND_LENS)
    emit("FIRST_CAPTURE_VALID", True)
    emit("READY_FOR_K2", True)


def inspect_second() -> None:
    server_world = world(0)
    host = controller(server_world, 0)
    component = director(host)
    values = channels(component)
    require_lengths(values, 2)
    require(values["DraftWaypointIds"] == [1, 2], f"IDs incorrect:{values['DraftWaypointIds']}")
    require_transform(values["DraftWaypointTransforms"][0], FIRST_LOCATION, FIRST_ROTATION)
    require_transform(values["DraftWaypointTransforms"][1], SECOND_LOCATION, SECOND_ROTATION)
    require(values["DraftWaypointFocalLengths"] == [FIRST_LENS[0], SECOND_LENS[0]], "focal snapshots changed")
    require(values["DraftWaypointApertures"] == [FIRST_LENS[1], SECOND_LENS[1]], "aperture snapshots changed")
    require(values["DraftWaypointFocusDistances"] == [FIRST_LENS[2], SECOND_LENS[2]], "focus snapshots changed")
    require(values["DraftWaypointHoldSeconds"] == [0.0, 0.0], "hold defaults changed")
    require(int(get_value(component, "NextWaypointId")) == 3, "NextWaypointId must advance to 3")

    client_world = world(1)
    client_values = channels(director(controller(client_world, 0)))
    require_lengths(client_values, 0)
    require(len(exact_actors(client_world, load_class(DRONE_CLASS_PATH))) == 0, "host drone leaked into client world")

    original = host.get_controlled_pawn()
    require(original is not None, "host controlled pawn missing before restoration")
    component.call_method("ExitDroneMode")
    require(host.get_controlled_pawn() == original, "exit changed controlled pawn")
    require(host.get_view_target() == original, "exit did not restore exact original view target")
    emit("SECOND_CAPTURE_VALID", True)
    emit("CLIENT_ISOLATION_VALID", True)
    emit("RESTORATION_VALID", True)
    emit("COMPLETE", True)


def capture_first_direct() -> None:
    component = director(controller(world(0), 0))
    component.call_method("CaptureCurrentWaypoint")
    inspect_first()
    emit("DIRECT_FUNCTION_CALL_1", True)


def capture_second_direct() -> None:
    component = director(controller(world(0), 0))
    component.call_method("CaptureCurrentWaypoint")
    inspect_second()
    emit("DIRECT_FUNCTION_CALL_2", True)


phase = globals().get("EDD_PHASE", "")
phases = {
    "prepare": prepare,
    "inspect1": inspect_first,
    "inspect2": inspect_second,
    "capture1": capture_first_direct,
    "capture2": capture_second_direct,
}
require(phase in phases, f"unknown phase:{phase}")
phases[phase]()
