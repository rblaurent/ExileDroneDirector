"""Programmatic player-owned PIE acceptance for bounded playback events."""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
import unreal


PREFIX = "EDD_BOUNDED_EVENT_PIE"
SOURCE_LEVEL_PATH = "/Game/Dev/AlmostEmpty"
WORLD_PATH = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
TIMEOUT_SECONDS = 120.0
SCENARIOS = ("local_success", "remote_reject", "manual_scrub")
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "tools/events/bounded_event_adapter_blueprint_schema.json").read_text(encoding="utf-8")
)
NAMES = tuple(spec["name"] for spec in SCHEMA["variables"])
EXTERNAL = (
    "AirframePrebakeCompiledBodyQuatsV1",
    "AirframePrebakeCompiledGimbalQuatsV1",
    "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1",
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


def clone(value):
    if isinstance(value, (list, tuple)):
        return [clone(item) for item in value]
    return value.copy() if hasattr(value, "copy") else value


def normalized(value):
    if isinstance(value, (list, tuple)):
        return tuple(normalized(item) for item in value)
    if isinstance(value, unreal.Quat):
        return float(value.x), float(value.y), float(value.z), float(value.w)
    return value


def snapshot(obj, names):
    return tuple(normalized(get(obj, name)) for name in names)


def defaults():
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    require(cls is not None, "class")
    return unreal.get_default_object(cls)


def pie_world():
    value = unreal.find_object(None, WORLD_PATH)
    require(value is not None, "PIE world")
    return value


def director(world):
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    require(controller is not None, "controller")
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    values = controller.get_components_by_class(cls)
    require(len(values) == 1, f"director count:{len(values)}")
    return values[0]


def stage_plan(obj, remote=False):
    event_id = "wait" if remote else "subtitle"
    adapter = "door" if remote else "local.presentation"
    operation = "wait_until_open" if remote else "subtitle"
    scope = "viewer_interaction" if remote else "local_cinematic"
    binding = "door-main" if remote else ""
    region = "exiled-lands" if remote else ""
    binding_adapter = "door" if remote else ""
    binding_version = 1 if remote else 0
    enabled = remote
    values = {
        "EventCueIdsV1": [event_id], "EventCueTimesV1": [1.0],
        "EventCueAdapterIdsV1": [adapter], "EventCueAdapterVersionsV1": [1],
        "EventCueOperationIdsV1": [operation], "EventCueScopesV1": [scope],
        "EventCuePayloadsV1": ["bounded"], "EventCueDirectionPoliciesV1": ["both"],
        "EventCueRepeatPoliciesV1": ["manual_reset" if remote else "once_per_session"],
        "EventCueFailurePoliciesV1": ["skip"], "EventCueBindingIdsV1": [binding],
        "EventCueBindingRegionsV1": [region], "EventCueBindingAdapterIdsV1": [binding_adapter],
        "EventCueBindingAdapterVersionsV1": [binding_version],
        "EventCueBindingEnabledV1": [enabled], "EventCueBindingReauthorizedV1": [enabled],
        "EventCuePlanValidV1": True, "EventFlypathIdV1": "flypath-pie",
        "EventImmutableRevisionV1": 11, "EventRequestedRevisionV1": 11,
        "EventSessionIdV1": "session-pie", "EventSessionTokenV1": "token-pie",
        "EventRequesterIdV1": "player-pie", "EventPlaybackStartedV1": True,
        "EventScrubbingV1": False, "EventPreviousTimeV1": 0.0,
        "EventCurrentTimeV1": 2.0, "EventLoopIterationV1": 0,
        "EventDirectionV1": 1, "EventRegionIdV1": "exiled-lands",
        "EventResolvedBindingIdsV1": ["door-main"],
        "EventResolvedBindingDistancesV1": [100.0],
        "EventGrantedPermissionsV1": ["door.observe", "door.interact", "door.lease.admin"],
        "EventRemainingRateBudgetV1": 8, "EventServerWorldEnabledV1": False,
        "EventServerRevisionApprovedV1": False, "EventLedgerIdsV1": [],
        "EventLedgerLoopsV1": [], "EventLedgerDirectionsV1": [],
    }
    for name, value in values.items():
        set_(obj, name, value)


def stage_scenario(obj, scenario, originals):
    for name, value in originals.items():
        set_(obj, name, clone(value))
    stage_plan(obj, remote=scenario != "local_success")
    if scenario == "remote_reject":
        set_(obj, "EventSessionTokenV1", "")
    elif scenario == "manual_scrub":
        set_(obj, "EventLedgerIdsV1", ["wait", "other", "wait"])
        set_(obj, "EventLedgerLoopsV1", [0, 1, 4])
        set_(obj, "EventLedgerDirectionsV1", [1, -1, -1])
        set_(obj, "EventManualResetCueIdV1", "wait")


def run_scenario(component, scenario):
    external_before = snapshot(component, EXTERNAL)
    if scenario == "local_success":
        component.call_method("DispatchBoundedPlaybackEventsV1")
        require(bool(get(component, "EventDispatchResultValidV1")), "local decision authority")
        require(bool(get(component, "EventDispatchAuthorizedV1")), "local authorization")
        require(str(get(component, "EventDispatchCodeV1")) == "authorized_local", "local code")
        set_(component, "EventAdapterExecutionResultValidV1", True)
        set_(component, "EventAdapterExecutionSucceededV1", True)
        set_(component, "EventAdapterExecutionCodeV1", "executed")
        component.call_method("CommitCueExecutionLedgerV1")
        require(bool(get(component, "EventLedgerCommitValidV1")), "local ledger authority")
        require(list(get(component, "EventLedgerIdsV1")) == ["subtitle"], "local ledger")
        emit("LOCAL_DISPATCH_RESULT", "PASS")
    elif scenario == "remote_reject":
        component.call_method("DispatchBoundedPlaybackEventsV1")
        require(bool(get(component, "EventDispatchResultValidV1")), "remote decision authority")
        require(not bool(get(component, "EventDispatchAuthorizedV1")), "remote rejection authorized")
        require(str(get(component, "EventDispatchCodeV1")) == "event_session_token_missing", "remote code")
        require(len(get(component, "EventLedgerIdsV1")) == 0, "remote rejection ledger")
        emit("REMOTE_REJECTION_RESULT", "PASS")
    else:
        component.call_method("ResetManualCueLedgerEntryV1")
        require(bool(get(component, "EventManualResetResultValidV1")), "manual reset authority")
        require(list(get(component, "EventLedgerIdsV1")) == ["other"], "manual stable filter")
        set_(component, "EventScrubbingV1", True)
        before = snapshot(component, ("EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1"))
        component.call_method("DispatchBoundedPlaybackEventsV1")
        require(len(get(component, "EventCrossedIndicesV1")) == 0, "scrub crossing")
        require(not bool(get(component, "EventDispatchAuthorizedV1")), "scrub authorization")
        require(snapshot(component, ("EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1")) == before, "scrub ledger")
        emit("MANUAL_SCRUB_RESULT", "PASS")
    require(snapshot(component, EXTERNAL) == external_before, "body/gimbal authorship mutation")
    emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED", True)
    emit("SCENARIO_RESULT", scenario + ":PASS")


def restore(state):
    if state.get("restored") or not state.get("originals"):
        return
    target = defaults()
    for name, value in state["originals"].items():
        set_(target, name, clone(value))
    require(
        all(normalized(get(target, name)) == normalized(value) for name, value in state["originals"].items()),
        "defaults not restored",
    )
    state["restored"] = True
    emit("DEFAULTS_RESTORED", True)


def finish(success):
    state = globals().get("_EDD_BOUNDED_EVENT_PIE_STATE")
    restore(state)
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    if success:
        emit("GAME_WORLD_RESULT", "PASS")
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")


def tick(_delta):
    state = globals()["_EDD_BOUNDED_EVENT_PIE_STATE"]
    try:
        subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        require(time.monotonic() - state["armed_at"] < TIMEOUT_SECONDS, "overall timeout")
        if state["stage"] == "prepare":
            require(not subsystem.is_in_play_in_editor(), "PIE already running")
            require(subsystem.load_level(SOURCE_LEVEL_PATH), "load level")
            target = defaults()
            state["originals"] = {name: clone(get(target, name)) for name in NAMES}
            stage_scenario(target, SCENARIOS[0], state["originals"])
            state["stage"] = "request"
            state["stage_at"] = time.monotonic()
            emit("SOURCE_LEVEL_READY", SOURCE_LEVEL_PATH)
            return
        if state["stage"] == "request":
            if time.monotonic() - state["stage_at"] < 0.5:
                return
            subsystem.editor_request_begin_play()
            state["stage"] = "wait"
            emit("PIE_START_REQUESTED", SCENARIOS[state["scenario_index"]])
            return
        if state["stage"] == "wait":
            try:
                component = director(pie_world())
                require(component.get_owner().has_actor_begun_play(), "BeginPlay")
            except Exception:
                return
            state["stage"] = "settle"
            state["stage_at"] = time.monotonic()
            return
        if state["stage"] == "settle":
            if time.monotonic() - state["stage_at"] < 1.0:
                return
            run_scenario(director(pie_world()), SCENARIOS[state["scenario_index"]])
            subsystem.editor_request_end_play()
            state["stage"] = "end"
            return
        if state["stage"] == "end":
            if subsystem.is_in_play_in_editor():
                return
            state["scenario_index"] += 1
            if state["scenario_index"] == len(SCENARIOS):
                state["stage"] = "complete"
                finish(True)
                return
            target = defaults()
            stage_scenario(target, SCENARIOS[state["scenario_index"]], state["originals"])
            state["stage"] = "request"
            state["stage_at"] = time.monotonic()
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:
            state["stage"] = "failed"
            finish(False)


old = globals().get("_EDD_BOUNDED_EVENT_PIE_STATE")
if old and old.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_BOUNDED_EVENT_PIE_STATE = {
    "stage": "prepare", "armed_at": time.monotonic(), "stage_at": time.monotonic(),
    "scenario_index": 0, "callback": None, "originals": None, "restored": False,
}
_EDD_BOUNDED_EVENT_PIE_STATE["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("ARMED", True)
