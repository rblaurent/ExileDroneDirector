r"""One-session PIE acceptance for physical draft-history shortcuts.

Arm this script from the editor console, start AlmostEmpty PIE, then send the
physical keys requested by its log markers::

    EDD_HISTORY_SHORTCUT_PIE:READY_FOR_UNDO:True       -> Ctrl+Z
    EDD_HISTORY_SHORTCUT_PIE:READY_FOR_REDO:True       -> Ctrl+Y
    EDD_HISTORY_SHORTCUT_PIE:READY_FOR_BRANCH_UNDO:True -> Ctrl+Z
    EDD_HISTORY_SHORTCUT_PIE:READY_FOR_EMPTY_REDO:True -> Ctrl+Y
    EDD_HISTORY_SHORTCUT_PIE:READY_FOR_INVALID_REPLACE:True -> R
    EDD_HISTORY_SHORTCUT_PIE:READY_FOR_INVALID_DELETE:True  -> Delete

The driver also requests physical F10 before the sequence and physical F9 after
it, because ``DroneModeActive`` is intentionally owned by the EventGraph input
dispatcher and is not an instance-editable Python property.

The driver seeds 65 accepted captures to prove the live 64-transaction cap,
then validates undo/redo document and preview parity, redo invalidation after a
branch edit, invalid mutation no-ops, and exact camera restoration.  It never
changes class defaults and ends PIE itself.
"""

from __future__ import annotations

import time
import traceback

import unreal


PREFIX = "EDD_HISTORY_SHORTCUT_PIE"
MANUAL_INPUT_TIMEOUT_SECONDS = 300.0
WORLD_PATH = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"

WAYPOINT_FIELDS = {
    "id": ("WaypointId", "waypoint_id", "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE"),
    "transform": ("CameraTransform", "camera_transform", "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9"),
    "focal": ("FocalLength", "focal_length", "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B"),
    "aperture": ("Aperture", "aperture", "Aperture_10_949C579344F8DFA750F1948051A417B2"),
    "focus": ("ManualFocusDistance", "manual_focus_distance", "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F"),
    "hold": ("HoldSeconds", "hold_seconds", "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB"),
}
SEGMENT_FIELDS = {
    "id": ("SegmentId", "segment_id", "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0"),
    "from": ("FromWaypointId", "from_waypoint_id", "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91"),
    "to": ("ToWaypointId", "to_waypoint_id", "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B"),
    "duration": ("DurationSeconds", "duration_seconds", "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A"),
    "curve": ("SpatialCurveType", "spatial_curve_type", "SpatialCurveType_15_39D20A5A4CD2FB464BAA64839CE4012E"),
    "profile": ("TimeProfile", "time_profile", "TimeProfile_16_3195F0C3470E1AECB34316A7BFBD2FBA"),
}
DOCUMENT_FIELDS = {
    "waypoints": ("Waypoints", "waypoints", "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"),
    "segments": ("Segments", "segments", "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"),
}
SOURCE_ARRAYS = (
    "DraftWaypointIds",
    "DraftWaypointTransforms",
    "DraftWaypointFocalLengths",
    "DraftWaypointApertures",
    "DraftWaypointFocusDistances",
    "DraftWaypointHoldSeconds",
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
    raise RuntimeError(f"{PREFIX}:could not resolve field on {value}; errors={errors}")


def close_number(actual, expected: float, tolerance: float = 0.001) -> None:
    require(abs(float(actual) - float(expected)) <= tolerance, f"expected {expected}, got {actual}")


def close_transform(actual, expected) -> None:
    for received, wanted in zip(
        (actual.translation.x, actual.translation.y, actual.translation.z),
        (expected.translation.x, expected.translation.y, expected.translation.z),
    ):
        close_number(received, wanted)
    actual_rotation = actual.rotation.rotator()
    expected_rotation = expected.rotation.rotator()
    for received, wanted in zip(
        (actual_rotation.pitch, actual_rotation.yaw, actual_rotation.roll),
        (expected_rotation.pitch, expected_rotation.yaw, expected_rotation.roll),
    ):
        delta = (float(received) - float(wanted) + 180.0) % 360.0 - 180.0
        require(abs(delta) <= 0.01, f"rotation expected {expected_rotation}, got {actual_rotation}")


def pie_world():
    value = unreal.find_object(None, WORLD_PATH)
    require(value is not None, f"PIE world missing:{WORLD_PATH}")
    return value


def controller(world_object):
    value = unreal.GameplayStatics.get_player_controller(world_object, 0)
    require(value is not None, "host PlayerController missing")
    return value


def director(world_object):
    owner = controller(world_object)
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    require(cls is not None, "client director class missing")
    values = owner.get_components_by_class(cls)
    require(len(values) == 1, f"expected one client director, found {len(values)}")
    return values[0]


def force_game_input(player_controller) -> None:
    library = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    try:
        library.set_input_mode_game_only(player_controller, True)
    except TypeError:
        library.set_input_mode_game_only(player_controller)


def preview_component(actor, name: str):
    values = [
        value
        for value in actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
        if value.get_name() == name
    ]
    require(len(values) == 1, f"expected one {name}, found {len(values)}")
    return values[0]


def history_lengths(component_value) -> tuple[int, int]:
    undo = (
        len(component_value.get_editor_property("UndoDocumentsV1")),
        len(component_value.get_editor_property("UndoSelectionsV1")),
        len(component_value.get_editor_property("UndoNextWaypointIdsV1")),
    )
    redo = (
        len(component_value.get_editor_property("RedoDocumentsV1")),
        len(component_value.get_editor_property("RedoSelectionsV1")),
        len(component_value.get_editor_property("RedoNextWaypointIdsV1")),
    )
    require(len(set(undo)) == 1, f"undo storage diverged:{undo}")
    require(len(set(redo)) == 1, f"redo storage diverged:{redo}")
    return undo[0], redo[0]


def require_document_parity(component_value, count: int) -> None:
    source = [list(component_value.get_editor_property(name)) for name in SOURCE_ARRAYS]
    require(all(len(values) == count for values in source), f"source arrays diverged:{[len(values) for values in source]}")
    typed_waypoints = list(component_value.get_editor_property("DraftWaypointsV1"))
    typed_segments = list(component_value.get_editor_property("DraftSegmentsV1"))
    document = component_value.get_editor_property("DraftDocumentV1")
    document_waypoints = list(field(document, DOCUMENT_FIELDS["waypoints"]))
    document_segments = list(field(document, DOCUMENT_FIELDS["segments"]))
    expected_segments = max(count - 1, 0)
    require(len(typed_waypoints) == count, f"typed waypoint count:{len(typed_waypoints)}")
    require(len(document_waypoints) == count, f"document waypoint count:{len(document_waypoints)}")
    require(len(typed_segments) == expected_segments, f"typed segment count:{len(typed_segments)}")
    require(len(document_segments) == expected_segments, f"document segment count:{len(document_segments)}")
    for index, (typed, document_value) in enumerate(zip(typed_waypoints, document_waypoints)):
        require(int(field(typed, WAYPOINT_FIELDS["id"])) == int(source[0][index]), f"typed ID mismatch:{index}")
        require(int(field(document_value, WAYPOINT_FIELDS["id"])) == int(source[0][index]), f"document ID mismatch:{index}")
        close_transform(field(typed, WAYPOINT_FIELDS["transform"]), source[1][index])
        close_transform(field(document_value, WAYPOINT_FIELDS["transform"]), source[1][index])
        for key, values in zip(("focal", "aperture", "focus", "hold"), source[2:]):
            close_number(field(typed, WAYPOINT_FIELDS[key]), values[index])
            close_number(field(document_value, WAYPOINT_FIELDS[key]), values[index])
    for index, (typed, document_value) in enumerate(zip(typed_segments, document_segments)):
        for key in ("id", "from", "to"):
            require(int(field(typed, SEGMENT_FIELDS[key])) == int(field(document_value, SEGMENT_FIELDS[key])), f"segment {key} mismatch:{index}")
        close_number(field(typed, SEGMENT_FIELDS["duration"]), field(document_value, SEGMENT_FIELDS["duration"]))
        for key in ("curve", "profile"):
            require(str(field(typed, SEGMENT_FIELDS[key])) == str(field(document_value, SEGMENT_FIELDS[key])), f"segment {key} mismatch:{index}")


def require_preview_parity(component_value, count: int) -> None:
    actor = component_value.get_editor_property("PathPreviewActorV1")
    require(actor is not None, "owned path preview missing")
    require(
        actor.get_editor_property("PreviewDocumentV1").export_text()
        == component_value.get_editor_property("DraftDocumentV1").export_text(),
        "preview document diverged",
    )
    markers = preview_component(actor, "WaypointMarkersV1")
    segments = preview_component(actor, "SegmentLinesV1")
    require(markers.get_instance_count() == count, f"preview marker count:{markers.get_instance_count()}")
    require(segments.get_instance_count() == max(count - 1, 0), f"preview segment count:{segments.get_instance_count()}")


def require_state(component_value, count: int, selected: int, next_id: int, undo: int, redo: int, label: str) -> None:
    require_document_parity(component_value, count)
    require_preview_parity(component_value, count)
    require(int(component_value.get_editor_property("SelectedWaypointIndex")) == selected, f"{label} selection")
    require(int(component_value.get_editor_property("NextWaypointId")) == next_id, f"{label} next ID")
    require(history_lengths(component_value) == (undo, redo), f"{label} history lengths:{history_lengths(component_value)}")
    emit("STATE", f"{label}:count={count}:selected={selected}:next={next_id}:undo={undo}:redo={redo}")


def serialize(value):
    if isinstance(value, (list, tuple)):
        return tuple(serialize(item) for item in value)
    if hasattr(value, "export_text"):
        return value.export_text()
    return str(value)


def fingerprint(component_value):
    actor = component_value.get_editor_property("PathPreviewActorV1")
    return (
        tuple((name, serialize(list(component_value.get_editor_property(name)))) for name in SOURCE_ARRAYS),
        serialize(list(component_value.get_editor_property("DraftWaypointsV1"))),
        serialize(list(component_value.get_editor_property("DraftSegmentsV1"))),
        serialize(component_value.get_editor_property("DraftDocumentV1")),
        int(component_value.get_editor_property("SelectedWaypointIndex")),
        int(component_value.get_editor_property("NextWaypointId")),
        serialize(list(component_value.get_editor_property("UndoDocumentsV1"))),
        serialize(list(component_value.get_editor_property("UndoSelectionsV1"))),
        serialize(list(component_value.get_editor_property("UndoNextWaypointIdsV1"))),
        serialize(list(component_value.get_editor_property("RedoDocumentsV1"))),
        serialize(list(component_value.get_editor_property("RedoSelectionsV1"))),
        serialize(list(component_value.get_editor_property("RedoNextWaypointIdsV1"))),
        serialize(actor.get_editor_property("PreviewDocumentV1")) if actor else None,
        preview_component(actor, "WaypointMarkersV1").get_instance_count() if actor else -1,
        preview_component(actor, "SegmentLinesV1").get_instance_count() if actor else -1,
    )


def finish(success: bool) -> None:
    state = globals().get("_EDD_HISTORY_SHORTCUT_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_HISTORY_SHORTCUT_STATE"]
    try:
        if state["stage"] == "wait_for_pie":
            try:
                world_object = pie_world()
                component_value = director(world_object)
                require(component_value.get_owner().has_actor_begun_play(), "director owner not ready")
            except Exception:
                if time.monotonic() - state["armed_at"] > 45.0:
                    raise RuntimeError("PIE did not become ready within 45 seconds")
                return
            state["stage"] = "settle"
            state["stage_at"] = time.monotonic()
            emit("HOST_RUNTIME_READY", True)
            return

        if state["stage"] == "settle":
            if time.monotonic() - state["stage_at"] < 1.5:
                return
            world_object = pie_world()
            component_value = director(world_object)
            owner = controller(world_object)
            force_game_input(owner)
            if bool(component_value.get_editor_property("DroneModeActive")):
                component_value.call_method("ExitDroneMode")
            state["original_view"] = owner.get_view_target()
            state["stage"] = "wait_enter"
            state["deadline"] = time.monotonic() + MANUAL_INPUT_TIMEOUT_SECONDS
            emit("READY_FOR_ENTER", True)
            return

        component_value = director(pie_world())
        if state["stage"] == "wait_enter":
            if not bool(component_value.get_editor_property("DroneModeActive")):
                require(time.monotonic() < state["deadline"], "physical F10 timed out")
                return
            require(component_value.get_editor_property("DroneCameraRef") is not None, "physical F10 camera missing")
            require_state(component_value, 0, -1, 1, 0, 0, "baseline")
            state["seed_index"] = 0
            state["stage"] = "seed"
            emit("PHYSICAL_ENTER_VALID", True)
            return
        if state["stage"] == "seed":
            drone = component_value.get_editor_property("DroneCameraRef")
            require(drone is not None, "seed drone missing")
            for _ in range(5):
                index = state["seed_index"]
                if index >= 65:
                    break
                require(drone.set_actor_location(unreal.Vector(index * 125.0, index * 37.0, 900.0 + index * 11.0), False, False), f"seed location:{index}")
                require(drone.set_actor_rotation(unreal.Rotator(pitch=float(index % 45), yaw=float((index * 13) % 180), roll=0.0), False), f"seed rotation:{index}")
                component_value.call_method("CaptureCurrentWaypoint")
                state["seed_index"] += 1
            if state["seed_index"] == 65:
                require_state(component_value, 65, 64, 66, 64, 0, "history-cap")
                state["stage"] = "wait_undo"
                state["deadline"] = time.monotonic() + MANUAL_INPUT_TIMEOUT_SECONDS
                emit("HISTORY_CAP_VALID", True)
                emit("READY_FOR_UNDO", True)
            return

        count = len(component_value.get_editor_property("DraftWaypointIds"))
        if state["stage"] == "wait_undo":
            if count == 65:
                require(time.monotonic() < state["deadline"], "physical Ctrl+Z timed out")
                return
            require_state(component_value, 64, 63, 65, 63, 1, "physical-undo")
            state["stage"] = "wait_redo"
            state["deadline"] = time.monotonic() + MANUAL_INPUT_TIMEOUT_SECONDS
            emit("PHYSICAL_UNDO_VALID", True)
            emit("READY_FOR_REDO", True)
            return

        if state["stage"] == "wait_redo":
            if count == 64:
                require(time.monotonic() < state["deadline"], "physical Ctrl+Y timed out")
                return
            require_state(component_value, 65, 64, 66, 64, 0, "physical-redo")
            state["stage"] = "wait_branch_undo"
            state["deadline"] = time.monotonic() + MANUAL_INPUT_TIMEOUT_SECONDS
            emit("PHYSICAL_REDO_VALID", True)
            emit("READY_FOR_BRANCH_UNDO", True)
            return

        if state["stage"] == "wait_branch_undo":
            if count == 65:
                require(time.monotonic() < state["deadline"], "branch Ctrl+Z timed out")
                return
            require_state(component_value, 64, 63, 65, 63, 1, "branch-undo")
            drone = component_value.get_editor_property("DroneCameraRef")
            require(drone.set_actor_location(unreal.Vector(99000.0, -77000.0, 5555.0), False, False), "branch location")
            require(drone.set_actor_rotation(unreal.Rotator(pitch=-12.0, yaw=147.0, roll=0.0), False), "branch rotation")
            component_value.call_method("CaptureCurrentWaypoint")
            require_state(component_value, 65, 64, 66, 64, 0, "branch-edit")
            state["stable"] = fingerprint(component_value)
            state["stage"] = "wait_empty_redo"
            state["stage_at"] = time.monotonic()
            emit("REDO_BRANCH_INVALIDATION_VALID", True)
            emit("READY_FOR_EMPTY_REDO", True)
            return

        if state["stage"] == "wait_empty_redo":
            if time.monotonic() - state["stage_at"] < 2.0:
                return
            require(fingerprint(component_value) == state["stable"], "empty redo mutated state")
            require_state(component_value, 65, 64, 66, 64, 0, "empty-redo")
            for _ in range(65):
                component_value.call_method("DeleteSelectedWaypoint")
            require_state(component_value, 0, -1, 66, 64, 0, "naturally-empty")
            state["stable"] = fingerprint(component_value)
            state["stage"] = "wait_invalid_replace"
            state["stage_at"] = time.monotonic()
            emit("PHYSICAL_EMPTY_REDO_NOOP_VALID", True)
            emit("READY_FOR_INVALID_REPLACE", True)
            return

        if state["stage"] == "wait_invalid_replace":
            if time.monotonic() - state["stage_at"] < 2.0:
                return
            require(fingerprint(component_value) == state["stable"], "invalid replace mutated state/history/preview")
            state["stage"] = "wait_invalid_delete"
            state["stage_at"] = time.monotonic()
            emit("PHYSICAL_INVALID_REPLACE_NOOP_VALID", True)
            emit("READY_FOR_INVALID_DELETE", True)
            return

        if state["stage"] == "wait_invalid_delete":
            if time.monotonic() - state["stage_at"] < 2.0:
                return
            require(fingerprint(component_value) == state["stable"], "invalid delete mutated state/history/preview")
            emit("PHYSICAL_INVALID_DELETE_NOOP_VALID", True)
            state["stage"] = "wait_exit"
            state["deadline"] = time.monotonic() + MANUAL_INPUT_TIMEOUT_SECONDS
            emit("READY_FOR_EXIT", True)
            return

        if state["stage"] == "wait_exit":
            if bool(component_value.get_editor_property("DroneModeActive")):
                require(time.monotonic() < state["deadline"], "physical F9 timed out")
                return
            owner = controller(pie_world())
            require(owner.get_view_target() == state["original_view"], "physical F9 did not restore exact camera")
            require(component_value.get_editor_property("PathPreviewActorV1") is None, "physical F9 retained preview")
            before_capture = fingerprint(component_value)
            component_value.call_method("CaptureCurrentWaypoint")
            require(fingerprint(component_value) == before_capture, "invalid capture mutated state/history/preview")
            emit("INVALID_CAPTURE_NOOP_VALID", True)
            emit("CAMERA_RESTORATION_VALID", True)
            state["stage"] = "complete"
            finish(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}:AUTOMATIC_EXCEPTION:{error}\n{traceback.format_exc()}")
        state["stage"] = "failed"
        finish(False)


old_state = globals().get("_EDD_HISTORY_SHORTCUT_STATE")
if old_state and old_state.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(old_state["callback"])

_EDD_HISTORY_SHORTCUT_STATE = {
    "stage": "wait_for_pie",
    "armed_at": time.monotonic(),
    "stage_at": time.monotonic(),
    "deadline": time.monotonic() + 45.0,
    "callback": None,
}
_EDD_HISTORY_SHORTCUT_STATE["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("ARMED", True)
