r"""Three-phase PIE acceptance for typed waypoint preview markers.

Arm once from the editor console, then start PIE for each requested phase::

    py exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-PathPreviewMarkersPIE.py').read())

Phase one captures two production waypoints and seeds one typed waypoint into
the preview class defaults. Phase two validates the one-marker projection and
seeds both waypoints. Phase three validates both world-space marker transforms,
then proves ClearPreviewV1 returns both instance pools to zero. The original
preview class defaults are restored even if an assertion fails.
"""

from __future__ import annotations

import time
import traceback

import unreal


PREFIX = "EDD_PATH_PREVIEW_PIE"
WORLD_PATH = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
DRONE_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C"
PREVIEW_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Trajectory/BP_EDD_PathPreview.BP_EDD_PathPreview_C"
DOCUMENT_WAYPOINT_FIELDS = (
    "Waypoints",
    "waypoints",
    "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5",
)
WAYPOINT_TRANSFORM_FIELDS = (
    "CameraTransform",
    "camera_transform",
    "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9",
)
PLACEMENTS = (
    (unreal.Vector(111.0, 222.0, 333.0), unreal.Rotator(10.0, 20.0, 30.0)),
    (unreal.Vector(-444.0, 555.0, 777.0), unreal.Rotator(-40.0, 80.0, 12.0)),
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}:{message}")


def field(value, candidates):
    errors = []
    for candidate in candidates:
        try:
            return value.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}:could not resolve struct field; errors={errors}")


def set_field(value, candidates, new_value) -> None:
    errors = []
    for candidate in candidates:
        try:
            value.set_editor_property(candidate, new_value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}:could not set struct field; errors={errors}")


def clone_struct(value):
    return value.copy() if hasattr(value, "copy") else value


def pie_world():
    value = unreal.find_object(None, WORLD_PATH)
    require(value is not None, f"PIE world missing:{WORLD_PATH}")
    return value


def exact_class(path: str):
    value = unreal.load_class(None, path)
    require(value is not None, f"class missing:{path}")
    return value


def director(world_object):
    controller = unreal.GameplayStatics.get_player_controller(world_object, 0)
    require(controller is not None, "host PlayerController missing")
    values = controller.get_components_by_class(exact_class(CLIENT_CLASS_PATH))
    require(len(values) == 1, f"expected one client director, found {len(values)}")
    return values[0]


def exact_drone(world_object):
    cls = exact_class(DRONE_CLASS_PATH)
    values = [
        actor
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world_object, cls)
        if actor.get_class() == cls
    ]
    require(len(values) == 1, f"expected one host drone, found {len(values)}")
    return values[0]


def preview_defaults():
    return unreal.get_default_object(exact_class(PREVIEW_CLASS_PATH))


def clone_document_with_waypoints(document, count: int):
    result = clone_struct(document)
    source = [clone_struct(value) for value in field(document, DOCUMENT_WAYPOINT_FIELDS)]
    require(len(source) >= count, f"document only has {len(source)} waypoints; need {count}")
    set_field(result, DOCUMENT_WAYPOINT_FIELDS, source[:count])
    return result


def restore_defaults() -> None:
    state = globals().get("_EDD_PATH_PREVIEW_STATE")
    if not state or state.get("restored"):
        return
    defaults = state["preview_defaults"]
    defaults.set_editor_property("PreviewDocumentV1", clone_struct(state["original_document"]))
    defaults.set_editor_property("PreviewEnabled", state["original_enabled"])
    require(
        defaults.get_editor_property("PreviewDocumentV1").export_text() == state["original_document_text"],
        "preview document defaults were not restored",
    )
    require(
        bool(defaults.get_editor_property("PreviewEnabled")) == state["original_enabled"],
        "PreviewEnabled default was not restored",
    )
    state["restored"] = True
    emit("DEFAULTS_RESTORED", True)


def close_number(actual, expected: float, tolerance: float = 0.01) -> None:
    require(abs(float(actual) - float(expected)) <= tolerance, f"expected {expected}, got {actual}")


def close_vector(actual, expected) -> None:
    for received, wanted in zip(
        (actual.x, actual.y, actual.z),
        (expected.x, expected.y, expected.z),
    ):
        close_number(received, wanted)


def close_rotation(actual, expected) -> None:
    actual_rotator = actual.rotator()
    expected_rotator = expected.rotator()
    for received, wanted in zip(
        (actual_rotator.pitch, actual_rotator.yaw, actual_rotator.roll),
        (expected_rotator.pitch, expected_rotator.yaw, expected_rotator.roll),
    ):
        delta = (float(received) - float(wanted) + 180.0) % 360.0 - 180.0
        require(abs(delta) <= 0.05, f"rotation expected {expected_rotator}, got {actual_rotator}")


def close_transform(actual, expected, expected_scale: float) -> None:
    close_vector(actual.translation, expected.translation)
    close_rotation(actual.rotation, expected.rotation)
    close_vector(actual.scale3d, unreal.Vector(expected_scale, expected_scale, expected_scale))


def exact_preplaced_preview(world_object):
    cls = exact_class(PREVIEW_CLASS_PATH)
    values = [
        actor
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world_object, cls)
        if actor.get_class() == cls
    ]
    require(len(values) == 1, f"expected one preplaced preview actor, found {len(values)}")
    return values[0]


def cleanup_editor_actor() -> None:
    state = globals().get("_EDD_PATH_PREVIEW_STATE")
    if not state or state.get("editor_actor") is None:
        return
    require(
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(state["editor_actor"]),
        "failed to destroy temporary editor preview actor",
    )
    state["editor_actor"] = None
    emit("EDITOR_ACTOR_CLEANED", True)


def prepare_editor_actor() -> None:
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    cleanup_editor_actor()
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        exact_class(PREVIEW_CLASS_PATH),
        unreal.Vector(),
        unreal.Rotator(),
        False,
    )
    require(actor is not None, "failed to place temporary editor preview actor")
    state["editor_actor"] = actor
    state["needs_prepare"] = False
    state["armed_at"] = time.monotonic()
    emit("EDITOR_ACTOR_PREPARED", actor.get_path_name())


def component(actor, name: str):
    matches = [
        value
        for value in actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        if value.get_name() == name
    ]
    require(len(matches) == 1, f"expected one {name} component, found {len(matches)}")
    return matches[0]


def instance_transform(component_value, index: int):
    result = component_value.get_instance_transform(index, True)
    if isinstance(result, tuple):
        success = next((value for value in result if isinstance(value, bool)), True)
        transform = next((value for value in result if isinstance(value, unreal.Transform)), None)
        require(success and transform is not None, f"instance transform unavailable at {index}:{result}")
        return transform
    require(isinstance(result, unreal.Transform), f"unexpected instance transform result:{result}")
    return result


def validate_projection(expected_count: int) -> None:
    actor = exact_preplaced_preview(pie_world())
    actor.call_method("RebuildPreviewV1")
    markers = component(actor, "WaypointMarkersV1")
    segments = component(actor, "SegmentLinesV1")
    require(markers.get_instance_count() == expected_count, f"marker count expected {expected_count}, got {markers.get_instance_count()}")
    require(segments.get_instance_count() == 0, f"marker slice populated segment pool:{segments.get_instance_count()}")
    document = actor.get_editor_property("PreviewDocumentV1")
    waypoints = list(field(document, DOCUMENT_WAYPOINT_FIELDS))
    scale = float(actor.get_editor_property("MarkerScaleV1"))
    require(len(waypoints) == expected_count, f"spawned document expected {expected_count} waypoints, got {len(waypoints)}")
    for index, waypoint in enumerate(waypoints):
        expected = field(waypoint, WAYPOINT_TRANSFORM_FIELDS)
        close_transform(instance_transform(markers, index), expected, scale)
    emit(f"{expected_count}_MARKER_TRANSFORMS_VALID", True)

    actor.call_method("ClearPreviewV1")
    require(markers.get_instance_count() == 0, "ClearPreviewV1 left marker instances")
    require(segments.get_instance_count() == 0, "ClearPreviewV1 left segment instances")
    emit(f"{expected_count}_TO_ZERO_CLEAR_VALID", True)


def phase_capture() -> None:
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    world_object = pie_world()
    component_value = director(world_object)
    require(len(component_value.get_editor_property("DraftWaypointsV1")) == 0, "capture fixture did not start empty")
    if bool(component_value.get_editor_property("DroneModeActive")):
        component_value.call_method("ExitDroneMode")
    component_value.call_method("EnterDroneMode")
    drone = exact_drone(world_object)
    for location, rotation in PLACEMENTS:
        require(drone.set_actor_location(location, False, False), f"failed to place drone:{location}")
        require(drone.set_actor_rotation(rotation, False), f"failed to rotate drone:{rotation}")
        component_value.call_method("CaptureCurrentWaypoint")
    component_value.call_method("SyncDraftDocumentV1")
    document = clone_struct(component_value.get_editor_property("DraftDocumentV1"))
    require(len(field(document, DOCUMENT_WAYPOINT_FIELDS)) == 2, "production sync did not build two typed waypoints")
    state["captured_document"] = document
    defaults = state["preview_defaults"]
    defaults.set_editor_property("PreviewEnabled", True)
    defaults.set_editor_property("PreviewDocumentV1", clone_document_with_waypoints(document, 1))
    component_value.call_method("ExitDroneMode")
    state["phase"] = "one"
    state["needs_prepare"] = True
    emit("CAPTURE_AND_ONE_DEFAULT_SEED_VALID", True)


def phase_one() -> None:
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    validate_projection(1)
    state["preview_defaults"].set_editor_property(
        "PreviewDocumentV1",
        clone_document_with_waypoints(state["captured_document"], 2),
    )
    state["phase"] = "two"
    state["needs_prepare"] = True
    emit("ONE_MARKER_PHASE_RESULT", "PASS")


def phase_two() -> None:
    validate_projection(2)
    restore_defaults()
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    state["phase"] = "cleanup"
    emit("TWO_MARKER_PHASE_RESULT", "PASS")


def unregister() -> None:
    state = globals().get("_EDD_PATH_PREVIEW_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None


def end_phase() -> None:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    globals()["_EDD_PATH_PREVIEW_STATE"]["armed_at"] = time.monotonic()


def tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    world_object = unreal.find_object(None, WORLD_PATH)
    if world_object is None:
        try:
            if state["phase"] == "cleanup":
                cleanup_editor_actor()
                unregister()
                emit("AUTOMATIC_RESULT", state.get("result", "PASS"))
                return
            if state.get("needs_prepare"):
                prepare_editor_actor()
                if state["phase"] == "one":
                    emit("NEXT", "START_PIE_FOR_ONE_MARKER")
                elif state["phase"] == "two":
                    emit("NEXT", "START_PIE_FOR_TWO_MARKERS")
                return
        except Exception as error:
            unreal.log_error(f"{PREFIX}:AUTOMATIC_RESULT:FAIL:{error}\n{traceback.format_exc()}")
            try:
                restore_defaults()
                cleanup_editor_actor()
            finally:
                unregister()
            return
        if time.monotonic() - state["armed_at"] > 45.0:
            unreal.log_error(f"{PREFIX}:AUTOMATIC_RESULT:FAIL:PIE did not become ready within 45 seconds")
            restore_defaults()
            cleanup_editor_actor()
            unregister()
        return

    try:
        phase = state["phase"]
        if phase == "capture":
            phase_capture()
            end_phase()
        elif phase == "one":
            phase_one()
            end_phase()
        elif phase == "two":
            phase_two()
            end_phase()
    except Exception as error:
        unreal.log_error(f"{PREFIX}:AUTOMATIC_RESULT:FAIL:{error}\n{traceback.format_exc()}")
        state["result"] = "FAIL"
        try:
            restore_defaults()
        except Exception as restore_error:
            unreal.log_error(f"{PREFIX}:RESTORE_FAILED:{restore_error}\n{traceback.format_exc()}")
        state["phase"] = "cleanup"
        end_phase()


existing = globals().get("_EDD_PATH_PREVIEW_STATE")
if existing and existing.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(existing["callback"])
defaults = preview_defaults()
original_document = clone_struct(defaults.get_editor_property("PreviewDocumentV1"))
state = {
    "armed_at": time.monotonic(),
    "callback": None,
    "phase": "capture",
    "preview_defaults": defaults,
    "original_document": original_document,
    "original_document_text": original_document.export_text(),
    "original_enabled": bool(defaults.get_editor_property("PreviewEnabled")),
    "restored": False,
    "editor_actor": None,
    "needs_prepare": False,
    "result": "PASS",
}
globals()["_EDD_PATH_PREVIEW_STATE"] = state
state["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("AUTOMATIC_ARMED", True)
emit("NEXT", "START_PIE_FOR_CAPTURE")
