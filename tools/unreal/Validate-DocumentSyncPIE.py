r"""Multi-phase PIE acceptance probe for SyncDraftDocumentV1.

Execute once in the editor before starting PIE. The registered post-tick
callback exercises live capture/rebuild, authored-segment preservation, and
invalid-input rollback across real component constructions. The log requests
the second and third PIE starts; the callback ends every phase cleanly.
"""

from __future__ import annotations

import time
import traceback

import unreal


PREFIX = "EDD_DOCUMENT_SYNC_PIE"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
DRONE_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C"
WORLD_PATH = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"

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
    "schema": ("SchemaVersion", "schema_version", "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"),
    "engine": ("TrajectoryEngineVersion", "trajectory_engine_version", "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D"),
    "revision": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "region": ("RegionId", "region_id", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"),
    "duration": ("DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"),
    "profile": ("DefaultFlightProfile", "default_flight_profile", "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161"),
    "waypoints": ("Waypoints", "waypoints", "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"),
    "segments": ("Segments", "segments", "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"),
    "hash": ("ContentHash", "content_hash", "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"),
}
WAYPOINT_SOURCE_PROPERTIES = (
    "DraftWaypointIds",
    "DraftWaypointTransforms",
    "DraftWaypointFocalLengths",
    "DraftWaypointApertures",
    "DraftWaypointFocusDistances",
    "DraftWaypointHoldSeconds",
    "NextWaypointId",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}:{message}")


def close_number(actual, expected: float, tolerance: float = 0.001) -> None:
    require(abs(float(actual) - expected) <= tolerance, f"expected {expected}, got {actual}")


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
    for received, wanted in zip(
        (actual.scale3d.x, actual.scale3d.y, actual.scale3d.z),
        (expected.scale3d.x, expected.scale3d.y, expected.scale3d.z),
    ):
        close_number(received, wanted)


def field(value, candidates):
    errors = []
    for candidate in candidates:
        try:
            return value.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}:could not resolve field on {value}; errors={errors}")


def set_field(value, candidates, new_value) -> None:
    errors = []
    for candidate in candidates:
        try:
            value.set_editor_property(candidate, new_value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}:could not set field on {value}; errors={errors}")


def clone_property(value):
    if isinstance(value, (list, tuple)):
        return [item.copy() if hasattr(item, "copy") else item for item in value]
    return value.copy() if hasattr(value, "copy") else value


def property_snapshot(value):
    if isinstance(value, (list, tuple)):
        return tuple(item.export_text() if hasattr(item, "export_text") else item for item in value)
    return value.export_text() if hasattr(value, "export_text") else value


def pie_world():
    value = unreal.find_object(None, WORLD_PATH)
    require(value is not None, f"PIE world missing:{WORLD_PATH}")
    return value


def director(world_object):
    controller = unreal.GameplayStatics.get_player_controller(world_object, 0)
    require(controller is not None, "host PlayerController missing")
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    require(cls is not None, "client director class missing")
    values = controller.get_components_by_class(cls)
    require(len(values) == 1, f"expected one client director, found {len(values)}")
    return values[0]


def exact_drone(world_object):
    cls = unreal.load_class(None, DRONE_CLASS_PATH)
    require(cls is not None, "drone class missing")
    values = [
        actor
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world_object, cls)
        if actor.get_class() == cls
    ]
    require(len(values) == 1, f"expected one host drone, found {len(values)}")
    return values[0]


def document(component):
    return component.get_editor_property("DraftDocumentV1")


def segments(component):
    return list(component.get_editor_property("DraftSegmentsV1"))


def require_document_parity(component, expected_waypoints: int, expected_segments: int) -> None:
    value = document(component)
    typed_waypoints = list(component.get_editor_property("DraftWaypointsV1"))
    typed_segments = segments(component)
    doc_waypoints = list(field(value, DOCUMENT_FIELDS["waypoints"]))
    doc_segments = list(field(value, DOCUMENT_FIELDS["segments"]))
    require(len(typed_waypoints) == expected_waypoints, f"typed waypoint count changed:{len(typed_waypoints)}")
    require(len(typed_segments) == expected_segments, f"typed segment count changed:{len(typed_segments)}")
    for index, (document_waypoint, typed_waypoint) in enumerate(zip(doc_waypoints, typed_waypoints)):
        require(
            int(field(document_waypoint, WAYPOINT_FIELDS["id"]))
            == int(field(typed_waypoint, WAYPOINT_FIELDS["id"])),
            f"document waypoint ID diverged at {index}",
        )
        close_transform(
            field(document_waypoint, WAYPOINT_FIELDS["transform"]),
            field(typed_waypoint, WAYPOINT_FIELDS["transform"]),
        )
        for scalar in ("focal", "aperture", "focus", "hold"):
            close_number(
                field(document_waypoint, WAYPOINT_FIELDS[scalar]),
                field(typed_waypoint, WAYPOINT_FIELDS[scalar]),
            )
    for index, (document_segment, typed_segment) in enumerate(zip(doc_segments, typed_segments)):
        for integer in ("id", "from", "to"):
            require(
                int(field(document_segment, SEGMENT_FIELDS[integer]))
                == int(field(typed_segment, SEGMENT_FIELDS[integer])),
                f"document segment {integer} diverged at {index}",
            )
        close_number(
            field(document_segment, SEGMENT_FIELDS["duration"]),
            field(typed_segment, SEGMENT_FIELDS["duration"]),
        )
        for text_field in ("curve", "profile"):
            require(
                str(field(document_segment, SEGMENT_FIELDS[text_field]))
                == str(field(typed_segment, SEGMENT_FIELDS[text_field])),
                f"document segment {text_field} diverged at {index}",
            )


def run_capture_acceptance(state) -> None:
    world_object = pie_world()
    component = director(world_object)
    if bool(component.get_editor_property("DroneModeActive")):
        component.call_method("ExitDroneMode")

    component.call_method("SyncDraftDocumentV1")
    require_document_parity(component, 0, 0)
    emit("NEXT_ID_AFTER_EMPTY", component.get_editor_property("DocumentNextSegmentIdV1"))
    empty = document(component)
    require(int(field(empty, DOCUMENT_FIELDS["schema"])) == 1, "schema version default changed")
    require(int(field(empty, DOCUMENT_FIELDS["engine"])) == 1, "engine version default changed")
    close_number(field(empty, DOCUMENT_FIELDS["duration"]), 0.0)
    require(str(field(empty, DOCUMENT_FIELDS["profile"])) == "cinematic_drone", "default flight profile changed")
    require(str(field(empty, DOCUMENT_FIELDS["hash"])) == "", "empty document retained a content hash")
    emit("EMPTY_DOCUMENT_VALID", True)

    component.call_method("EnterDroneMode")
    drone = exact_drone(world_object)
    placements = (
        (unreal.Vector(111.0, 222.0, 333.0), unreal.Rotator(10.0, 20.0, 30.0)),
        (unreal.Vector(-444.0, 555.0, 777.0), unreal.Rotator(-40.0, 80.0, 12.0)),
    )
    for index, (location, rotation) in enumerate(placements):
        require(drone.set_actor_location(location, False, False), f"failed to place drone:{index}")
        require(drone.set_actor_rotation(rotation, False), f"failed to rotate drone:{index}")
        component.call_method("CaptureCurrentWaypoint")
        component.call_method("SyncDraftDocumentV1")
        emit(
            f"NEXT_ID_AFTER_CAPTURE_{index + 1}",
            component.get_editor_property("DocumentNextSegmentIdV1"),
        )
        require_document_parity(component, index + 1, index)

    typed_waypoints = list(component.get_editor_property("DraftWaypointsV1"))
    waypoint_ids = [int(field(value, WAYPOINT_FIELDS["id"])) for value in typed_waypoints]
    require(waypoint_ids == [1, 2], f"captured waypoint IDs changed:{waypoint_ids}")
    current_segments = segments(component)
    require(len(current_segments) == 1, "two waypoints did not produce one segment")
    segment = current_segments[0]
    segment_id = int(field(segment, SEGMENT_FIELDS["id"]))
    segment_from = int(field(segment, SEGMENT_FIELDS["from"]))
    segment_to = int(field(segment, SEGMENT_FIELDS["to"]))
    emit("SEGMENT_STATE", f"id={segment_id}|from={segment_from}|to={segment_to}|raw={segment.export_text()}")
    require(segment_id == 1, f"first segment ID changed:{segment_id}")
    require(segment_from == 1, f"segment FromWaypointId changed:{segment_from}")
    require(segment_to == 2, f"segment ToWaypointId changed:{segment_to}")
    close_number(field(segment, SEGMENT_FIELDS["duration"]), 3.0)
    require(str(field(segment, SEGMENT_FIELDS["curve"])) == "linear", "new segment curve changed")
    require(str(field(segment, SEGMENT_FIELDS["profile"])) == "linear", "new segment time profile changed")
    close_number(field(document(component), DOCUMENT_FIELDS["duration"]), 3.0)
    emit("TWO_WAYPOINT_DOCUMENT_VALID", True)

    before_segments = [value.export_text() for value in current_segments]
    before_document = document(component).export_text()
    component.call_method("SyncDraftDocumentV1")
    require([value.export_text() for value in segments(component)] == before_segments, "repeat sync changed segments")
    require(document(component).export_text() == before_document, "repeat sync changed document")
    emit("IDEMPOTENT_REBUILD_VALID", True)

    authored_segment = segments(component)[0]
    set_field(authored_segment, SEGMENT_FIELDS["duration"], 7.25)
    set_field(authored_segment, SEGMENT_FIELDS["curve"], "catmull_rom")
    set_field(authored_segment, SEGMENT_FIELDS["profile"], "ease_in_out")
    close_number(field(authored_segment, SEGMENT_FIELDS["duration"]), 7.25)
    require(str(field(authored_segment, SEGMENT_FIELDS["curve"])) == "catmull_rom", "authored curve mutation failed")
    require(str(field(authored_segment, SEGMENT_FIELDS["profile"])) == "ease_in_out", "authored profile mutation failed")
    emit("AUTHORED_SEGMENT_MUTATED", authored_segment.export_text())

    authored_document = document(component)
    set_field(authored_document, DOCUMENT_FIELDS["revision"], 12)
    set_field(authored_document, DOCUMENT_FIELDS["region"], "runtime_test")
    set_field(authored_document, DOCUMENT_FIELDS["profile"], "fpv")
    set_field(authored_document, DOCUMENT_FIELDS["hash"], "stale_hash")

    # Blueprint state variables deliberately remain non-instance-editable. Unreal
    # Python therefore cannot assign authored arrays on the live component. Seed
    # the generated-class defaults between two PIE runs instead. The second real
    # component is then constructed through the game's normal attachment path,
    # exercises production sync, and restores every default before PIE ends.
    component_class = unreal.load_class(None, CLIENT_CLASS_PATH)
    component_defaults = unreal.get_default_object(component_class)
    default_waypoints = [
        value.copy() for value in component_defaults.get_editor_property("DraftWaypointsV1")
    ]
    default_segments = [
        value.copy() for value in component_defaults.get_editor_property("DraftSegmentsV1")
    ]
    default_document = component_defaults.get_editor_property("DraftDocumentV1").copy()
    default_waypoint_text = [value.export_text() for value in default_waypoints]
    default_segment_text = [value.export_text() for value in default_segments]
    default_document_text = default_document.export_text()
    state["component_defaults"] = component_defaults
    state["default_waypoints"] = default_waypoints
    state["default_segments"] = default_segments
    state["default_document"] = default_document
    state["default_waypoint_text"] = default_waypoint_text
    state["default_segment_text"] = default_segment_text
    state["default_document_text"] = default_document_text
    source_defaults = {
        name: clone_property(component_defaults.get_editor_property(name))
        for name in WAYPOINT_SOURCE_PROPERTIES
    }
    state["source_defaults"] = source_defaults
    state["source_default_snapshots"] = {
        name: property_snapshot(value) for name, value in source_defaults.items()
    }
    for name in WAYPOINT_SOURCE_PROPERTIES:
        component_defaults.set_editor_property(name, clone_property(component.get_editor_property(name)))
    component_defaults.set_editor_property("DraftWaypointsV1", typed_waypoints)
    component_defaults.set_editor_property("DraftSegmentsV1", [authored_segment])
    component_defaults.set_editor_property("DraftDocumentV1", authored_document)
    state["defaults_seeded"] = True
    seeded_segment = list(component_defaults.get_editor_property("DraftSegmentsV1"))[0]
    close_number(field(seeded_segment, SEGMENT_FIELDS["duration"]), 7.25)
    require(str(field(seeded_segment, SEGMENT_FIELDS["curve"])) == "catmull_rom", "seeded curve mutation failed")
    require(str(field(seeded_segment, SEGMENT_FIELDS["profile"])) == "ease_in_out", "seeded profile mutation failed")
    emit("AUTHORED_SEGMENT_SEEDED", seeded_segment.export_text())
    emit("AUTHORED_DEFAULTS_SEEDED", True)

    component.call_method("ExitDroneMode")
    require(not bool(component.get_editor_property("DroneModeActive")), "drone mode did not exit")
    emit("PHASE_ONE_RESULT", "PASS")


def restore_component_defaults(state) -> None:
    if not state.get("defaults_seeded"):
        return
    component_defaults = state["component_defaults"]
    for name, value in state["source_defaults"].items():
        component_defaults.set_editor_property(name, value)
    component_defaults.set_editor_property("DraftWaypointsV1", state["default_waypoints"])
    component_defaults.set_editor_property("DraftSegmentsV1", state["default_segments"])
    component_defaults.set_editor_property("DraftDocumentV1", state["default_document"])
    require(
        [value.export_text() for value in component_defaults.get_editor_property("DraftWaypointsV1")]
        == state["default_waypoint_text"],
        "waypoint class defaults were not restored",
    )
    require(
        [value.export_text() for value in component_defaults.get_editor_property("DraftSegmentsV1")]
        == state["default_segment_text"],
        "segment class defaults were not restored",
    )
    require(
        component_defaults.get_editor_property("DraftDocumentV1").export_text()
        == state["default_document_text"],
        "document class default was not restored",
    )
    for name, expected in state["source_default_snapshots"].items():
        require(
            property_snapshot(component_defaults.get_editor_property(name)) == expected,
            f"{name} class default was not restored",
        )
    state["defaults_seeded"] = False
    emit("CLASS_DEFAULTS_RESTORED", True)


def run_preservation_acceptance(state) -> None:
    authored_component = director(pie_world())
    seeded_waypoints = list(authored_component.get_editor_property("DraftWaypointsV1"))
    seeded_segments = segments(authored_component)
    require(len(seeded_waypoints) == 2, f"second PIE waypoint count changed:{len(seeded_waypoints)}")
    require(len(seeded_segments) == 1, f"second PIE segment count changed:{len(seeded_segments)}")
    seeded_segment = seeded_segments[0]
    close_number(field(seeded_segment, SEGMENT_FIELDS["duration"]), 7.25)
    require(str(field(seeded_segment, SEGMENT_FIELDS["curve"])) == "catmull_rom", "second PIE seeded curve was lost")
    require(str(field(seeded_segment, SEGMENT_FIELDS["profile"])) == "ease_in_out", "second PIE seeded profile was lost")
    emit("SECOND_PIE_SEGMENT_SEEDED", seeded_segment.export_text())
    seeded_document = document(authored_component)
    require(int(field(seeded_document, DOCUMENT_FIELDS["revision"])) == 12, "seeded revision was lost")
    require(str(field(seeded_document, DOCUMENT_FIELDS["region"])) == "runtime_test", "seeded region was lost")
    require(str(field(seeded_document, DOCUMENT_FIELDS["profile"])) == "fpv", "seeded profile was lost")
    require(str(field(seeded_document, DOCUMENT_FIELDS["hash"])) == "stale_hash", "seeded hash was lost")

    authored_component.call_method("SyncDraftDocumentV1")
    preserved = segments(authored_component)[0]
    require(int(field(preserved, SEGMENT_FIELDS["id"])) == 1, "preserved segment ID changed")
    close_number(field(preserved, SEGMENT_FIELDS["duration"]), 7.25)
    require(str(field(preserved, SEGMENT_FIELDS["curve"])) == "catmull_rom", "spatial curve edit was lost")
    require(str(field(preserved, SEGMENT_FIELDS["profile"])) == "ease_in_out", "time profile edit was lost")
    rebuilt_document = document(authored_component)
    require(int(field(rebuilt_document, DOCUMENT_FIELDS["revision"])) == 12, "revision metadata was lost")
    require(str(field(rebuilt_document, DOCUMENT_FIELDS["region"])) == "runtime_test", "region metadata was lost")
    require(str(field(rebuilt_document, DOCUMENT_FIELDS["profile"])) == "fpv", "flight profile metadata was lost")
    require(str(field(rebuilt_document, DOCUMENT_FIELDS["hash"])) == "", "content hash was not cleared")
    close_number(field(rebuilt_document, DOCUMENT_FIELDS["duration"]), 7.25)
    require_document_parity(authored_component, 2, 1)
    emit("PRESERVED_AUTHORED_SEGMENT_VALID", True)
    require(not bool(authored_component.get_editor_property("DroneModeActive")), "second PIE began in drone mode")

    component_defaults = state["component_defaults"]
    for name in WAYPOINT_SOURCE_PROPERTIES:
        component_defaults.set_editor_property(
            name,
            clone_property(authored_component.get_editor_property(name)),
        )
    invalid_holds = list(component_defaults.get_editor_property("DraftWaypointHoldSeconds"))
    require(len(invalid_holds) == 2, f"expected two holds before invalid seed:{len(invalid_holds)}")
    component_defaults.set_editor_property("DraftWaypointHoldSeconds", invalid_holds[:-1])
    rollback_waypoints = [value.copy() for value in authored_component.get_editor_property("DraftWaypointsV1")]
    rollback_segments = [value.copy() for value in authored_component.get_editor_property("DraftSegmentsV1")]
    rollback_document = authored_component.get_editor_property("DraftDocumentV1").copy()
    component_defaults.set_editor_property("DraftWaypointsV1", rollback_waypoints)
    component_defaults.set_editor_property("DraftSegmentsV1", rollback_segments)
    component_defaults.set_editor_property("DraftDocumentV1", rollback_document)
    state["rollback_waypoint_text"] = [value.export_text() for value in rollback_waypoints]
    state["rollback_segment_text"] = [value.export_text() for value in rollback_segments]
    state["rollback_document_text"] = rollback_document.export_text()
    emit("INVALID_SOURCE_DEFAULTS_SEEDED", True)
    emit("PHASE_TWO_RESULT", "PASS")


def run_invalid_rollback_acceptance(state) -> None:
    component = director(pie_world())
    before_waypoints = [value.export_text() for value in component.get_editor_property("DraftWaypointsV1")]
    before_segments = [value.export_text() for value in component.get_editor_property("DraftSegmentsV1")]
    before_document = component.get_editor_property("DraftDocumentV1").export_text()
    require(before_waypoints == state["rollback_waypoint_text"], "third PIE waypoint seed changed")
    require(before_segments == state["rollback_segment_text"], "third PIE segment seed changed")
    require(before_document == state["rollback_document_text"], "third PIE document seed changed")

    component.call_method("SyncDraftDocumentV1")
    require(not bool(component.get_editor_property("WaypointPreflightValid")), "invalid source passed waypoint preflight")
    require(
        [value.export_text() for value in component.get_editor_property("DraftWaypointsV1")]
        == before_waypoints,
        "invalid input mutated typed waypoints",
    )
    require(
        [value.export_text() for value in component.get_editor_property("DraftSegmentsV1")]
        == before_segments,
        "invalid input mutated segments",
    )
    require(
        component.get_editor_property("DraftDocumentV1").export_text() == before_document,
        "invalid input mutated document",
    )
    emit("INVALID_INPUT_ROLLBACK_VALID", True)
    restore_component_defaults(state)
    require(not bool(component.get_editor_property("DroneModeActive")), "third PIE began in drone mode")
    emit("RESTORATION_VALID", True)
    emit("AUTOMATIC_RESULT", "PASS")


def finish() -> None:
    state = globals().get("_EDD_DOCUMENT_SYNC_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_DOCUMENT_SYNC_STATE"]
    try:
        if state["phase"] == "await_world_exit":
            if unreal.find_object(None, WORLD_PATH) is None:
                state["phase"] = state["next_phase"]
                state["armed_at"] = time.monotonic()
                emit(state["next_marker"], True)
            return
        try:
            director(pie_world())
        except Exception:
            if time.monotonic() - state["armed_at"] > 45.0:
                raise RuntimeError(f"{PREFIX}:PIE did not become ready within 45 seconds")
            return
        if state["phase"] == "capture":
            run_capture_acceptance(state)
            state["phase"] = "await_world_exit"
            state["next_phase"] = "preservation"
            state["next_marker"] = "SECOND_PIE_REQUIRED"
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        elif state["phase"] == "preservation":
            run_preservation_acceptance(state)
            state["phase"] = "await_world_exit"
            state["next_phase"] = "invalid_rollback"
            state["next_marker"] = "THIRD_PIE_REQUIRED"
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        elif state["phase"] == "invalid_rollback":
            run_invalid_rollback_acceptance(state)
            finish()
        else:
            raise RuntimeError(f"{PREFIX}:unknown acceptance phase:{state['phase']}")
    except Exception as error:
        try:
            restore_component_defaults(state)
        except Exception as restore_error:
            unreal.log_error(f"{PREFIX}:DEFAULT_RESTORE_FAIL:{restore_error}")
        unreal.log_error(f"{PREFIX}:AUTOMATIC_RESULT:FAIL:{error}\n{traceback.format_exc()}")
        finish()


existing = globals().get("_EDD_DOCUMENT_SYNC_STATE")
if existing and existing.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(existing["callback"])
state = {
    "armed_at": time.monotonic(),
    "callback": None,
    "phase": "capture",
    "defaults_seeded": False,
}
globals()["_EDD_DOCUMENT_SYNC_STATE"] = state
state["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("AUTOMATIC_ARMED", True)
