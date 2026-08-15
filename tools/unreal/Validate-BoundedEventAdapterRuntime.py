"""Execute the saved bounded event-adapter family on Client Director defaults."""

from __future__ import annotations

import json
from pathlib import Path
import unreal


PREFIX = "EDD_BOUNDED_EVENT_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "tools/events/bounded_event_adapter_blueprint_schema.json").read_text(encoding="utf-8")
)
EXTERNAL = (
    "AirframePrebakeCompiledBodyQuatsV1",
    "AirframePrebakeCompiledGimbalQuatsV1",
    "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1",
)
CAPABILITIES = (
    ("subtitle", "local.presentation", "subtitle", "local_cinematic", "", "", "", 0, False, False, "once_per_session"),
    ("marker", "local.recording", "marker", "local_cinematic", "", "", "", 0, False, False, "every_loop"),
    ("wait", "door", "wait_until_open", "viewer_interaction", "door-main", "exiled-lands", "door", 1, True, True, "manual_reset"),
    ("interact", "door", "request_normal_interaction", "viewer_interaction", "door-main", "exiled-lands", "door", 1, True, True, "once_per_session"),
    ("lease", "door", "cinematic_state_lease", "server_world", "door-main", "exiled-lands", "door", 1, True, True, "once_per_session"),
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


def stage_common(obj):
    values = {
        "EventCuePlanValidV1": True,
        "EventFlypathIdV1": "flypath-live",
        "EventImmutableRevisionV1": 7,
        "EventRequestedRevisionV1": 7,
        "EventSessionIdV1": "session-live",
        "EventSessionTokenV1": "token-live",
        "EventRequesterIdV1": "player-live",
        "EventPlaybackStartedV1": True,
        "EventScrubbingV1": False,
        "EventPreviousTimeV1": 0.0,
        "EventCurrentTimeV1": 2.0,
        "EventLoopIterationV1": 0,
        "EventDirectionV1": 1,
        "EventRegionIdV1": "exiled-lands",
        "EventResolvedBindingIdsV1": ["door-main"],
        "EventResolvedBindingDistancesV1": [100.0],
        "EventGrantedPermissionsV1": ["door.observe", "door.interact", "door.lease.admin"],
        "EventRemainingRateBudgetV1": 8,
        "EventServerWorldEnabledV1": True,
        "EventServerRevisionApprovedV1": True,
        "EventLedgerIdsV1": [],
        "EventLedgerLoopsV1": [],
        "EventLedgerDirectionsV1": [],
    }
    for name, value in values.items():
        set_(obj, name, value)


def stage_capability(obj, capability, event_time=1.0):
    label, adapter, operation, scope, binding, region, binding_adapter, binding_version, enabled, reauthorized, repeat = capability
    arrays = {
        "EventCueIdsV1": [label],
        "EventCueTimesV1": [event_time],
        "EventCueAdapterIdsV1": [adapter],
        "EventCueAdapterVersionsV1": [1],
        "EventCueOperationIdsV1": [operation],
        "EventCueScopesV1": [scope],
        "EventCuePayloadsV1": ["bounded"],
        "EventCueDirectionPoliciesV1": ["both"],
        "EventCueRepeatPoliciesV1": [repeat],
        "EventCueFailurePoliciesV1": ["skip"],
        "EventCueBindingIdsV1": [binding],
        "EventCueBindingRegionsV1": [region],
        "EventCueBindingAdapterIdsV1": [binding_adapter],
        "EventCueBindingAdapterVersionsV1": [binding_version],
        "EventCueBindingEnabledV1": [enabled],
        "EventCueBindingReauthorizedV1": [reauthorized],
    }
    for name, value in arrays.items():
        set_(obj, name, value)


def dispatch(obj, expected_index=0, expected_code=None):
    obj.call_method("DispatchBoundedPlaybackEventsV1")
    require(bool(get(obj, "EventPlanValidationValidV1")), "plan validation")
    require(bool(get(obj, "EventCrossingCollectionValidV1")), "crossing collection")
    require(bool(get(obj, "EventSelectionValidV1")), "selection authority")
    require(bool(get(obj, "EventDispatchResultValidV1")), "decision authority")
    require(int(get(obj, "EventDispatchIndexV1")) == expected_index, "selected index")
    if expected_code is not None:
        require(str(get(obj, "EventDispatchCodeV1")) == expected_code, "decision code")


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
owned = tuple(spec["name"] for spec in SCHEMA["variables"])
saved = {name: clone(get(obj, name)) for name in owned}
external_before = snapshot(obj, EXTERNAL)
try:
    accepted = 0
    for capability in CAPABILITIES:
        stage_common(obj)
        stage_capability(obj, capability)
        expected = "authorized_local" if capability[3] == "local_cinematic" else "authorized_remote"
        dispatch(obj, expected_code=expected)
        require(bool(get(obj, "EventDispatchAuthorizedV1")), capability[0] + ":authorized")
        require(snapshot(obj, EXTERNAL) == external_before, capability[0] + ":authorship mutated")
        set_(obj, "EventAdapterExecutionResultValidV1", True)
        set_(obj, "EventAdapterExecutionSucceededV1", True)
        set_(obj, "EventAdapterExecutionCodeV1", "state_satisfied" if capability[0] == "wait" else "executed")
        obj.call_method("CommitCueExecutionLedgerV1")
        require(bool(get(obj, "EventLedgerCommitValidV1")), capability[0] + ":ledger authority")
        require(list(get(obj, "EventLedgerIdsV1")) == [capability[0]], capability[0] + ":ledger ID")
        require(list(get(obj, "EventLedgerLoopsV1")) == [0], capability[0] + ":ledger loop")
        require(list(get(obj, "EventLedgerDirectionsV1")) == [1], capability[0] + ":ledger direction")
        accepted += 1

    stage_common(obj)
    stage_capability(obj, CAPABILITIES[2])
    set_(obj, "EventSessionTokenV1", "")
    dispatch(obj, expected_code="event_session_token_missing")
    require(not bool(get(obj, "EventDispatchAuthorizedV1")), "remote rejection authorized")
    require(len(get(obj, "EventLedgerIdsV1")) == 0, "remote rejection ledger mutation")
    emit("TYPED_REMOTE_REJECTION", "PASS")

    stage_common(obj)
    stage_capability(obj, CAPABILITIES[0])
    dispatch(obj, expected_code="authorized_local")
    set_(obj, "EventAdapterExecutionResultValidV1", True)
    set_(obj, "EventAdapterExecutionSucceededV1", False)
    set_(obj, "EventAdapterExecutionCodeV1", "adapter_failed")
    obj.call_method("CommitCueExecutionLedgerV1")
    require(not bool(get(obj, "EventLedgerCommitValidV1")), "failed receipt committed")
    require(str(get(obj, "EventDispatchCodeV1")) == "event_adapter_execution_failed", "failed receipt code")
    require(len(get(obj, "EventLedgerIdsV1")) == 0, "failed receipt ledger mutation")
    emit("SUCCESS_ONLY_LEDGER", "PASS")

    stage_common(obj)
    stage_capability(obj, CAPABILITIES[0])
    set_(obj, "EventScrubbingV1", True)
    before_ledger = snapshot(obj, ("EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1"))
    obj.call_method("DispatchBoundedPlaybackEventsV1")
    require(bool(get(obj, "EventCrossingCollectionValidV1")), "scrub crossing authority")
    require(len(get(obj, "EventCrossedIndicesV1")) == 0, "scrub crossing")
    require(not bool(get(obj, "EventDispatchAuthorizedV1")), "scrub authorized")
    require(snapshot(obj, ("EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1")) == before_ledger, "scrub ledger")
    emit("SCRUB_ZERO_DISPATCH", "PASS")

    stage_common(obj)
    first, second = CAPABILITIES[0], CAPABILITIES[1]
    stage_capability(obj, first, 1.0)
    for name, value in {
        "EventCueIdsV1": [first[0], second[0]],
        "EventCueTimesV1": [1.0, 2.0],
        "EventCueAdapterIdsV1": [first[1], second[1]],
        "EventCueAdapterVersionsV1": [1, 1],
        "EventCueOperationIdsV1": [first[2], second[2]],
        "EventCueScopesV1": [first[3], second[3]],
        "EventCuePayloadsV1": ["a", "b"],
        "EventCueDirectionPoliciesV1": ["both", "both"],
        "EventCueRepeatPoliciesV1": [first[10], second[10]],
        "EventCueFailurePoliciesV1": ["skip", "skip"],
        "EventCueBindingIdsV1": ["", ""],
        "EventCueBindingRegionsV1": ["", ""],
        "EventCueBindingAdapterIdsV1": ["", ""],
        "EventCueBindingAdapterVersionsV1": [0, 0],
        "EventCueBindingEnabledV1": [False, False],
        "EventCueBindingReauthorizedV1": [False, False],
        "EventPreviousTimeV1": 3.0,
        "EventCurrentTimeV1": 0.0,
        "EventDirectionV1": -1,
    }.items():
        set_(obj, name, value)
    dispatch(obj, expected_index=1, expected_code="authorized_local")
    require(list(get(obj, "EventCrossedIndicesV1")) == [0, 1], "canonical reverse scratch")
    emit("REVERSE_SELECTION_ORDER", "PASS")

    stage_common(obj)
    stage_capability(obj, CAPABILITIES[2])
    set_(obj, "EventLedgerIdsV1", ["wait", "other", "wait"])
    set_(obj, "EventLedgerLoopsV1", [0, 1, 4])
    set_(obj, "EventLedgerDirectionsV1", [1, -1, -1])
    set_(obj, "EventManualResetCueIdV1", "wait")
    obj.call_method("ResetManualCueLedgerEntryV1")
    require(bool(get(obj, "EventManualResetResultValidV1")), "manual reset authority")
    require(str(get(obj, "EventDispatchCodeV1")) == "event_manual_reset_completed", "manual reset code")
    require(list(get(obj, "EventLedgerIdsV1")) == ["other"], "manual reset IDs")
    require(list(get(obj, "EventLedgerLoopsV1")) == [1], "manual reset loops")
    require(list(get(obj, "EventLedgerDirectionsV1")) == [-1], "manual reset directions")
    emit("MANUAL_REARM", "PASS")

    require(snapshot(obj, EXTERNAL) == external_before, "final body/gimbal authorship mutation")
    emit("CAPABILITIES_ACCEPTED", accepted)
    emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED", True)
    emit("NO_ADAPTER_OR_WORLD_MUTATION", True)
    emit("RESULT", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, clone(value))
    restored = all(normalized(get(obj, name)) == normalized(value) for name, value in saved.items())
    emit("DEFAULTS_RESTORED", restored)
    require(restored, "state restoration")
