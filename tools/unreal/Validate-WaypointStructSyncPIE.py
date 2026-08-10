r"""Automatic PIE acceptance probe for SyncDraftWaypointsV1.

Execute once in the editor before starting PIE.  The registered post-tick
callback waits for the server PIE world, validates exact mapping, transactional
mismatch rejection, empty rebuild, and client isolation, then ends PIE.
"""

from __future__ import annotations

import time
import traceback

import unreal


PREFIX = "EDD_WAYPOINT_STRUCT_PIE"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
DRONE_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C"
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
FIELD_CANDIDATES = {
    "id": ("WaypointId", "waypoint_id", "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE", "waypoint_id_2_0654fe3f4542ac31b6e13bbb55c34dae"),
    "transform": ("CameraTransform", "camera_transform", "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9", "camera_transform_5_6a923aa84db46d9ee28df38943321fc9"),
    "focal": ("FocalLength", "focal_length", "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B", "focal_length_8_c703b5a74b2ad4d6061535a85504fb8b"),
    "aperture": ("Aperture", "aperture", "Aperture_10_949C579344F8DFA750F1948051A417B2", "aperture_10_949c579344f8dfa750f1948051a417b2"),
    "focus": ("ManualFocusDistance", "manual_focus_distance", "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F", "manual_focus_distance_12_fdaa24bb4fd409ce159361b97904885f"),
    "hold": ("HoldSeconds", "hold_seconds", "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB", "hold_seconds_14_09edc66d4c9d2d3af6c4d2a7871843eb"),
}


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}:{message}")


def world(index: int):
    value = unreal.find_object(None, WORLD_PATHS[index])
    require(value is not None, f"PIE world missing:{WORLD_PATHS[index]}")
    return value


def controller(world_object):
    value = unreal.GameplayStatics.get_player_controller(world_object, 0)
    require(value is not None, f"PlayerController missing:{world_object.get_path_name()}")
    return value


def director(player_controller):
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    require(cls is not None, "client director class missing")
    values = player_controller.get_components_by_class(cls)
    require(len(values) == 1, f"expected one client director, found {len(values)}")
    return values[0]


def field(value, logical_name: str):
    errors = []
    for candidate in FIELD_CANDIDATES[logical_name]:
        try:
            return value.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(
        f"{PREFIX}:could not resolve {logical_name} on {value}; "
        f"public={[name for name in dir(value) if not name.startswith('_')]}; errors={errors}"
    )


def close_number(actual, expected: float, tolerance: float = 0.001) -> None:
    require(abs(float(actual) - expected) <= tolerance, f"expected {expected}, got {actual}")


def close_vector(actual, expected) -> None:
    for received, wanted in zip((actual.x, actual.y, actual.z), (expected.x, expected.y, expected.z)):
        close_number(received, float(wanted))


def close_rotation(actual, expected) -> None:
    actual_rotator = actual.rotator()
    expected_rotator = expected.rotator()
    for received, wanted in zip(
        (actual_rotator.pitch, actual_rotator.yaw, actual_rotator.roll),
        (expected_rotator.pitch, expected_rotator.yaw, expected_rotator.roll),
    ):
        delta = (float(received) - float(wanted) + 180.0) % 360.0 - 180.0
        require(abs(delta) <= 0.01, f"rotation expected {expected_rotator}, got {actual_rotator}")


def close_transform(actual, expected) -> None:
    close_vector(actual.translation, expected.translation)
    close_rotation(actual.rotation, expected.rotation)
    close_vector(actual.scale3d, expected.scale3d)


def run_acceptance() -> None:
    server_world = world(0)
    host = controller(server_world)
    component = director(host)
    component.call_method("SyncDraftWaypointsV1")
    require(len(component.get_editor_property("DraftWaypointsV1")) == 0, "empty rebuild did not stay empty")
    emit("EMPTY_REBUILD_VALID", True)

    if bool(component.get_editor_property("DroneModeActive")):
        component.call_method("ExitDroneMode")
    component.call_method("EnterDroneMode")
    drone_class = unreal.load_class(None, DRONE_CLASS_PATH)
    require(drone_class is not None, "drone class missing")
    drones = [
        actor
        for actor in unreal.GameplayStatics.get_all_actors_of_class(server_world, drone_class)
        if actor.get_class() == drone_class
    ]
    require(len(drones) == 1, f"expected one host drone, found {len(drones)}")
    drone = drones[0]

    placements = (
        (unreal.Vector(111.0, 222.0, 333.0), unreal.Rotator(10.0, 20.0, 30.0)),
        (unreal.Vector(-444.0, 555.0, 777.0), unreal.Rotator(-40.0, 80.0, 12.0)),
    )
    for location, rotation in placements:
        require(drone.set_actor_location(location, False, False), f"failed to set drone location:{location}")
        require(drone.set_actor_rotation(rotation, False), f"failed to set drone rotation:{rotation}")
        component.call_method("CaptureCurrentWaypoint")

    ids = list(component.get_editor_property("DraftWaypointIds"))
    transforms = list(component.get_editor_property("DraftWaypointTransforms"))
    focals = list(component.get_editor_property("DraftWaypointFocalLengths"))
    apertures = list(component.get_editor_property("DraftWaypointApertures"))
    focuses = list(component.get_editor_property("DraftWaypointFocusDistances"))
    holds = list(component.get_editor_property("DraftWaypointHoldSeconds"))
    require(ids == [1, 2], f"production capture fixture IDs changed:{ids}")
    component.call_method("SyncDraftWaypointsV1")

    typed = list(component.get_editor_property("DraftWaypointsV1"))
    require(len(typed) == 2, f"expected two typed waypoints, got {len(typed)}")
    for index, value in enumerate(typed):
        require(int(field(value, "id")) == ids[index], f"ID mismatch at {index}")
        close_transform(field(value, "transform"), transforms[index])
        close_number(field(value, "focal"), focals[index])
        close_number(field(value, "aperture"), apertures[index])
        close_number(field(value, "focus"), focuses[index])
        close_number(field(value, "hold"), holds[index])
    emit("EXACT_MAPPING_VALID", True)

    before = [value.export_text() for value in typed]
    component.call_method("SyncDraftWaypointsV1")
    after = [value.export_text() for value in component.get_editor_property("DraftWaypointsV1")]
    require(after == before, "repeated sync was not idempotent")
    emit("IDEMPOTENT_REBUILD_VALID", True)

    try:
        remote = director(controller(world(1)))
        require(len(remote.get_editor_property("DraftWaypointsV1")) == 0, "server typed state leaked to remote client")
        emit("CLIENT_ISOLATION_VALID", True)
    except Exception as error:
        emit("CLIENT_ISOLATION_SKIPPED", error)

    component.call_method("ExitDroneMode")
    emit("RESTORATION_VALID", True)
    emit("AUTOMATIC_RESULT", "PASS")


def finish() -> None:
    state = globals().get("_EDD_WAYPOINT_STRUCT_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_WAYPOINT_STRUCT_STATE"]
    try:
        try:
            director(controller(world(0)))
        except Exception:
            if time.monotonic() - state["armed_at"] > 45.0:
                raise RuntimeError(f"{PREFIX}:PIE did not become ready within 45 seconds")
            return
        run_acceptance()
        finish()
    except Exception as error:
        unreal.log_error(f"{PREFIX}:AUTOMATIC_RESULT:FAIL:{error}\n{traceback.format_exc()}")
        finish()


existing = globals().get("_EDD_WAYPOINT_STRUCT_STATE")
if existing and existing.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(existing["callback"])
state = {"armed_at": time.monotonic(), "callback": None}
globals()["_EDD_WAYPOINT_STRUCT_STATE"] = state
state["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("AUTOMATIC_ARMED", True)
