r"""Four-phase PIE acceptance for marker and linear-segment projection.

Arm once from the editor console, then start PIE whenever ``NEXT`` requests it::

    py exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-PathPreviewSegmentsPIE.py').read())

The harness uses the proven marker-test lifecycle support, captures two typed
waypoints through the production director, validates the one-waypoint case,
validates one exact segment between two distinct waypoints, then validates that
a degenerate adjacency keeps both markers but emits no segment.  Every phase
proves ClearPreviewV1 returns both pools to zero, and class defaults are restored.
"""

from __future__ import annotations

import math


SUPPORT_PATH = r"T:\Projects\ExileDroneDirector\tools\unreal\Validate-PathPreviewMarkersPIE.py"
with open(SUPPORT_PATH, encoding="utf-8") as support_file:
    support_source = support_file.read().split("\ndef validate_projection", 1)[0]
exec(compile(support_source, SUPPORT_PATH, "exec"), globals())

PREFIX = "EDD_PATH_PREVIEW_SEGMENTS_PIE"


def unregister() -> None:
    state = globals().get("_EDD_PATH_PREVIEW_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None


def end_phase() -> None:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    globals()["_EDD_PATH_PREVIEW_STATE"]["armed_at"] = time.monotonic()


def clone_document_degenerate(document):
    result = clone_document_with_waypoints(document, 2)
    waypoints = [clone_struct(value) for value in field(result, DOCUMENT_WAYPOINT_FIELDS)]
    first_transform = field(waypoints[0], WAYPOINT_TRANSFORM_FIELDS)
    set_field(waypoints[1], WAYPOINT_TRANSFORM_FIELDS, first_transform)
    set_field(result, DOCUMENT_WAYPOINT_FIELDS, waypoints)
    return result


def close_rotator(actual, expected_pitch: float, expected_yaw: float, expected_roll: float = 0.0) -> None:
    value = actual.rotator()
    for received, wanted, label in (
        (value.pitch, expected_pitch, "pitch"),
        (value.yaw, expected_yaw, "yaw"),
        (value.roll, expected_roll, "roll"),
    ):
        delta = (float(received) - float(wanted) + 180.0) % 360.0 - 180.0
        require(abs(delta) <= 0.05, f"segment {label} expected {wanted}, got {received}")


def validate_markers(actor, markers, waypoints) -> None:
    scale = float(actor.get_editor_property("MarkerScaleV1"))
    require(markers.get_instance_count() == len(waypoints), (
        f"marker count expected {len(waypoints)}, got {markers.get_instance_count()}"
    ))
    for index, waypoint in enumerate(waypoints):
        close_transform(
            instance_transform(markers, index),
            field(waypoint, WAYPOINT_TRANSFORM_FIELDS),
            scale,
        )


def validate_distinct_segment(actor, segments, waypoints) -> None:
    require(len(waypoints) == 2, f"distinct segment fixture expected two waypoints, got {len(waypoints)}")
    require(segments.get_instance_count() == 1, (
        f"distinct adjacency expected one segment, got {segments.get_instance_count()}"
    ))
    start = field(waypoints[0], WAYPOINT_TRANSFORM_FIELDS).translation
    end = field(waypoints[1], WAYPOINT_TRANSFORM_FIELDS).translation
    dx = float(end.x - start.x)
    dy = float(end.y - start.y)
    dz = float(end.z - start.z)
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    require(length > 0.001, f"distinct fixture unexpectedly degenerate:{length}")
    actual = instance_transform(segments, 0)
    close_vector(
        actual.translation,
        unreal.Vector(
            (start.x + end.x) * 0.5,
            (start.y + end.y) * 0.5,
            (start.z + end.z) * 0.5,
        ),
    )
    close_rotator(
        actual.rotation,
        math.degrees(math.atan2(dz, math.sqrt(dx * dx + dy * dy))),
        math.degrees(math.atan2(dy, dx)),
    )
    close_vector(
        actual.scale3d,
        unreal.Vector(
            length / float(actor.get_editor_property("SourceCubeExtentV1")),
            float(actor.get_editor_property("LineThicknessV1")),
            float(actor.get_editor_property("LineThicknessV1")),
        ),
    )
    emit("DISTINCT_SEGMENT_TRANSFORM_VALID", True)


def validate_projection(expected_markers: int, expected_segments: int, distinct: bool = False) -> None:
    actor = exact_preplaced_preview(pie_world())
    actor.call_method("RebuildPreviewV1")
    markers = component(actor, "WaypointMarkersV1")
    segments = component(actor, "SegmentLinesV1")
    document = actor.get_editor_property("PreviewDocumentV1")
    waypoints = list(field(document, DOCUMENT_WAYPOINT_FIELDS))
    require(len(waypoints) == expected_markers, (
        f"spawned document expected {expected_markers} waypoints, got {len(waypoints)}"
    ))
    validate_markers(actor, markers, waypoints)
    require(segments.get_instance_count() == expected_segments, (
        f"segment count expected {expected_segments}, got {segments.get_instance_count()}"
    ))
    if distinct:
        validate_distinct_segment(actor, segments, waypoints)
    emit(f"{expected_markers}_MARKERS_{expected_segments}_SEGMENTS_VALID", True)

    actor.call_method("ClearPreviewV1")
    require(markers.get_instance_count() == 0, "ClearPreviewV1 left marker instances")
    require(segments.get_instance_count() == 0, "ClearPreviewV1 left segment instances")
    emit(f"{expected_markers}_{expected_segments}_TO_ZERO_CLEAR_VALID", True)


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
    validate_projection(1, 0)
    state["preview_defaults"].set_editor_property(
        "PreviewDocumentV1",
        clone_document_with_waypoints(state["captured_document"], 2),
    )
    state["phase"] = "two"
    state["needs_prepare"] = True
    emit("ONE_WAYPOINT_PHASE_RESULT", "PASS")


def phase_two() -> None:
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    validate_projection(2, 1, distinct=True)
    state["preview_defaults"].set_editor_property(
        "PreviewDocumentV1",
        clone_document_degenerate(state["captured_document"]),
    )
    state["phase"] = "degenerate"
    state["needs_prepare"] = True
    emit("DISTINCT_SEGMENT_PHASE_RESULT", "PASS")


def phase_degenerate() -> None:
    validate_projection(2, 0)
    restore_defaults()
    state = globals()["_EDD_PATH_PREVIEW_STATE"]
    state["phase"] = "cleanup"
    emit("DEGENERATE_SEGMENT_PHASE_RESULT", "PASS")


def segment_tick(_delta_seconds: float) -> None:
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
                emit("NEXT", f"START_PIE_FOR_{state['phase'].upper()}")
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
        elif phase == "one":
            phase_one()
        elif phase == "two":
            phase_two()
        elif phase == "degenerate":
            phase_degenerate()
        else:
            return
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
state["callback"] = unreal.register_slate_post_tick_callback(segment_tick)
emit("AUTOMATIC_ARMED", True)
emit("NEXT", "START_PIE_FOR_CAPTURE")
