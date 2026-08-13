r"""Programmatic PIE acceptance for the lossless document adapter.

The harness starts AlmostEmpty PIE itself, exercises the saved adapter on the
real player-controller-owned Client Director component, and tears PIE down. It
proves end-to-end validity, distinct body/gimbal authorship, diagnostic IDs, and
input immutability without saving test state. The exhaustive success/failure and
diagnostic-policy matrix lives in Validate-AirframeDocumentAdapterRuntime.py.
"""

from __future__ import annotations

import math
import time
import traceback

import unreal


PREFIX = "EDD_AIRFRAME_DOCUMENT_ADAPTER_PIE"
SOURCE_LEVEL_PATH = "/Game/Dev/AlmostEmpty"
WORLD_PATH = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
TIMEOUT_SECONDS = 120.0

INPUTS = (
    "AirframeDocumentInputSchemaVersionV2",
    "AirframeDocumentInputTrajectoryEngineVersionV2",
    "AirframeDocumentInputDurationSecondsV2",
    "AirframeDocumentInputDefaultFlightProfileV2",
    "AirframeDocumentInputFixedStepSecondsV2",
    "AirframeDocumentInputWaypointIdsV2",
    "AirframeDocumentInputWaypointPositionsV2",
    "AirframeDocumentInputWaypointBodyQuatsV2",
    "AirframeDocumentInputWaypointGimbalQuatsV2",
    "AirframeDocumentInputSegmentIdsV2",
    "AirframeDocumentInputSegmentFromWaypointIdsV2",
    "AirframeDocumentInputSegmentToWaypointIdsV2",
    "AirframeDocumentInputSegmentDurationsV2",
    "AirframeDocumentInputSegmentSpatialCurveTypesV2",
    "AirframeDocumentInputSegmentTimeProfilesV2",
    "AirframeDocumentInputSegmentFlightProfileOverridesV2",
)
THRESHOLDS = (
    "AirframeDocumentDiagnosticPositionVelocityThresholdV2",
    "AirframeDocumentDiagnosticPositionAccelerationThresholdV2",
    "AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2",
)


def emit(label, value):
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition, message):
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def get(obj, name):
    for candidate in variants(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError("missing property:" + name)


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError("could not set property:" + name)


def yaw(degrees):
    half = math.radians(degrees) * 0.5
    return unreal.Quat(0.0, 0.0, math.sin(half), math.cos(half))


def pitch(degrees):
    half = math.radians(degrees) * 0.5
    return unreal.Quat(0.0, math.sin(half), 0.0, math.cos(half))


def quat_tuple(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def same_rotation(left, right, tolerance=1.0e-5):
    a = quat_tuple(left)
    b = quat_tuple(right)
    al = math.sqrt(sum(value * value for value in a))
    bl = math.sqrt(sum(value * value for value in b))
    return al > 0.0 and bl > 0.0 and abs(sum(x * y for x, y in zip(a, b)) / (al * bl)) >= 1.0 - tolerance


def normalized(value):
    if isinstance(value, (list, tuple)):
        return tuple(normalized(item) for item in value)
    if isinstance(value, unreal.Vector):
        return float(value.x), float(value.y), float(value.z)
    if isinstance(value, unreal.Quat):
        return quat_tuple(value)
    return value


def clone(value):
    if isinstance(value, (list, tuple)):
        return [clone(item) for item in value]
    return value.copy() if hasattr(value, "copy") else value


def defaults():
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    require(cls is not None, "client director class missing")
    return unreal.get_default_object(cls)


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


def fixture(four=False):
    ids = [100, 107, 114, 121] if four else [100, 107, 114]
    durations = [0.5, 0.75, 1.0] if four else [0.5, 0.5]
    positions = [unreal.Vector(float(index) * 50.0, 0.0, 0.0) for index in range(len(ids))]
    body_angles = [0.0, 4.0, 10.0, 18.0][: len(ids)]
    gimbal_angles = [0.0, -3.0, -8.0, -14.0][: len(ids)]
    return {
        "ids": ids,
        "durations": durations,
        "positions": positions,
        "body": [yaw(value) for value in body_angles],
        "gimbal": [pitch(value) for value in gimbal_angles],
        "segment_ids": [1000 + index * 11 for index in range(len(durations))],
    }


def stage(obj, data, thresholds=(0.0, 0.0, 0.0)):
    ids = data["ids"]
    durations = data["durations"]
    set_(obj, "AirframeDocumentInputSchemaVersionV2", 2)
    set_(obj, "AirframeDocumentInputTrajectoryEngineVersionV2", 1)
    set_(obj, "AirframeDocumentInputDurationSecondsV2", sum(durations))
    set_(obj, "AirframeDocumentInputDefaultFlightProfileV2", "cinematic_drone")
    set_(obj, "AirframeDocumentInputFixedStepSecondsV2", 0.25)
    set_(obj, "AirframeDocumentInputWaypointIdsV2", ids)
    set_(obj, "AirframeDocumentInputWaypointPositionsV2", data["positions"])
    set_(obj, "AirframeDocumentInputWaypointBodyQuatsV2", data["body"])
    set_(obj, "AirframeDocumentInputWaypointGimbalQuatsV2", data["gimbal"])
    set_(obj, "AirframeDocumentInputSegmentIdsV2", data["segment_ids"])
    set_(obj, "AirframeDocumentInputSegmentFromWaypointIdsV2", ids[:-1])
    set_(obj, "AirframeDocumentInputSegmentToWaypointIdsV2", ids[1:])
    set_(obj, "AirframeDocumentInputSegmentDurationsV2", durations)
    set_(obj, "AirframeDocumentInputSegmentSpatialCurveTypesV2", ["linear"] * len(durations))
    set_(obj, "AirframeDocumentInputSegmentTimeProfilesV2", ["linear"] * len(durations))
    set_(obj, "AirframeDocumentInputSegmentFlightProfileOverridesV2", [""] * len(durations))
    set_(obj, "AirframeDocumentDiagnosticPositionVelocityThresholdV2", thresholds[0])
    set_(obj, "AirframeDocumentDiagnosticPositionAccelerationThresholdV2", thresholds[1])
    set_(obj, "AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2", thresholds[2])


def input_fingerprint(obj):
    return tuple(normalized(get(obj, name)) for name in INPUTS)


def require_success(obj, data, label):
    for name in (
        "AirframeDocumentAdapterStageValidV2",
        "AirframeDocumentAdapterCompileValidV2",
        "AirframeSourceCompileValidV1",
        "AirframeDesiredStreamCompileValidV1",
        "AirframePrebakeCompileValidV1",
        "AirframeDocumentDiagnosticsValidV2",
    ):
        require(bool(get(obj, name)), f"{label}:{name}")
    body = list(get(obj, "AirframeSourceInputBodyWaypointQuatsV1"))
    gimbal = list(get(obj, "AirframeSourceInputGimbalWaypointQuatsV1"))
    require(len(body) == len(data["body"]) and len(gimbal) == len(data["gimbal"]), f"{label}:authorship shape")
    require(all(same_rotation(actual, wanted) for actual, wanted in zip(body, data["body"])), f"{label}:body values")
    require(all(same_rotation(actual, wanted) for actual, wanted in zip(gimbal, data["gimbal"])), f"{label}:gimbal values")
    require(any(not same_rotation(a, b) for a, b in zip(body, gimbal)), f"{label}:body/gimbal alias")
    require(
        list(get(obj, "AirframeDocumentDiagnosticWaypointIdsV2")) == data["ids"][1:-1],
        f"{label}:diagnostic waypoint IDs",
    )


def run_checks():
    component = director(pie_world())
    first = fixture(False)
    before = input_fingerprint(component)
    component.call_method("CompileAirframeDocumentSourceAdapterV2")
    require(input_fingerprint(component) == before, "inputs mutated")
    require_success(component, first, "PIE")
    require(int(get(component, "AirframeDocumentDiagnosticCountV2")) > 0, "tight thresholds produced no warning")
    emit("DISTINCT_AUTHORSHIP", "PASS")
    emit("DIAGNOSTIC_WAYPOINT_IDS", list(get(component, "AirframeDocumentDiagnosticWaypointIdsV2")))
    emit("GAME_WORLD_RESULT", "PASS")


def seed_scenario(state):
    stage(state["defaults"], fixture(False))


def restore_defaults(state):
    if state.get("restored") or not state.get("originals"):
        return
    target = state["defaults"]
    for name, value in state["originals"].items():
        set_(target, name, clone(value))
    state["restored"] = True
    emit("DEFAULTS_RESTORED", True)


def finish(success):
    state = globals().get("_EDD_AIRFRAME_DOCUMENT_ADAPTER_PIE_STATE")
    if state:
        restore_defaults(state)
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")


def tick(_delta_seconds):
    state = globals()["_EDD_AIRFRAME_DOCUMENT_ADAPTER_PIE_STATE"]
    try:
        subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if state["stage"] == "prepare_editor":
            require(not subsystem.is_in_play_in_editor(), "PIE already running")
            require(subsystem.load_level(SOURCE_LEVEL_PATH), f"could not load {SOURCE_LEVEL_PATH}")
            target = defaults()
            state["defaults"] = target
            state["originals"] = {name: clone(get(target, name)) for name in INPUTS + THRESHOLDS}
            seed_scenario(state)
            state["stage"] = "request_pie"
            state["stage_at"] = time.monotonic()
            emit("SOURCE_LEVEL_READY", SOURCE_LEVEL_PATH)
            return
        if state["stage"] == "request_pie":
            if time.monotonic() - state["stage_at"] < 0.5:
                return
            subsystem.editor_request_begin_play()
            state["stage"] = "wait_for_pie"
            emit("PIE_START_REQUESTED", True)
            return
        if state["stage"] == "wait_for_pie":
            try:
                component = director(pie_world())
                require(component.get_owner().has_actor_begun_play(), "director owner BeginPlay pending")
            except Exception:
                require(time.monotonic() - state["armed_at"] < TIMEOUT_SECONDS, "PIE startup timed out")
                return
            state["stage"] = "settle"
            state["stage_at"] = time.monotonic()
            emit("HOST_RUNTIME_READY", True)
            return
        if state["stage"] == "settle":
            if time.monotonic() - state["stage_at"] < 1.0:
                return
            run_checks()
            subsystem.editor_request_end_play()
            state["stage"] = "wait_for_end"
            emit("PIE_END_REQUESTED", True)
            return
        if state["stage"] == "wait_for_end":
            if subsystem.is_in_play_in_editor():
                require(time.monotonic() - state["armed_at"] < TIMEOUT_SECONDS, "PIE teardown timed out")
                return
            state["stage"] = "complete"
            finish(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:
            state["stage"] = "failed"
            finish(False)


old_state = globals().get("_EDD_AIRFRAME_DOCUMENT_ADAPTER_PIE_STATE")
if old_state and old_state.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(old_state["callback"])

_EDD_AIRFRAME_DOCUMENT_ADAPTER_PIE_STATE = {
    "stage": "prepare_editor",
    "armed_at": time.monotonic(),
    "stage_at": time.monotonic(),
    "callback": None,
    "defaults": None,
    "originals": None,
    "restored": False,
}
_EDD_AIRFRAME_DOCUMENT_ADAPTER_PIE_STATE["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("ARMED", True)
