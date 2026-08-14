"""Execute the saved camera-focus helper against its deterministic oracle."""
from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_FOCUS_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_focus_helper_blueprint_schema.json").read_text(encoding="utf-8"))
INPUTS = tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] == "input")


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_"); return name, unreal.Name(name), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in variants(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError("missing property:" + name)
def set_(obj, name, value):
    for candidate in variants(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError("could not set property:" + name)
def vector(value): return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))
def vector_tuple(value): return (float(value.x), float(value.y), float(value.z))
def clone(value):
    if isinstance(value, unreal.Vector): return unreal.Vector(value.x, value.y, value.z)
    if isinstance(value, (list, tuple)): return [clone(item) for item in value]
    return value
def normalized(value):
    if isinstance(value, unreal.Vector): return vector_tuple(value)
    if isinstance(value, (list, tuple)): return tuple(normalized(item) for item in value)
    return value
def close(left, right): return abs(float(left) - float(right)) <= 3e-5 * max(1.0, abs(float(left)), abs(float(right)))


sys.path.insert(0, str(ROOT / "tools/trajectory"))
import camera_focus_helper_reference as oracle
oracle = importlib.reload(oracle)
cls = unreal.load_class(None, CLASS); require(cls is not None, "class")
obj = unreal.get_default_object(cls)
saved = {spec["name"]: clone(get(obj, spec["name"])) for spec in SCHEMA["variables"]}


def stage(case):
    set_(obj, "CameraFocusInputModeV1", case["mode"]); set_(obj, "CameraFocusInputDomainV1", case["domain"]); set_(obj, "CameraFocusInputFixedStepSecondsV1", case["step"])
    set_(obj, "CameraFocusInputTimesSecondsV1", list(case["times"])); set_(obj, "CameraFocusInputCameraPositionsV1", [vector(value) for value in case["cameras"]])
    set_(obj, "CameraFocusInputManualDistancesCmV1", list(case.get("manual", ()))); set_(obj, "CameraFocusInputTargetPositionsV1", [vector(value) for value in case.get("targets", ())])
    set_(obj, "CameraFocusInputRackTargetAV1", vector(case.get("rack_a", (0, 0, 0)))); set_(obj, "CameraFocusInputRackTargetBV1", vector(case.get("rack_b", (0, 0, 0))))
    set_(obj, "CameraFocusInputRackBlendWeightsV1", list(case.get("weights", ()))); set_(obj, "CameraFocusInputSmoothingResponseSecondsV1", case.get("response", 0.0))


def input_snapshot(): return tuple(normalized(get(obj, name)) for name in INPUTS)


def expected(case):
    return oracle.compile_focus_distance_samples_v1(
        case["mode"], case["domain"], case["times"], case["step"], case["cameras"],
        manual_distances_cm=case.get("manual", ()), target_positions=case.get("targets", ()),
        rack_target_a=case.get("rack_a", (0, 0, 0)), rack_target_b=case.get("rack_b", (0, 0, 0),),
        rack_blend_weights=case.get("weights", ()), smoothing_response_seconds=case.get("response", 0.0),
    )


def compile_case(case, label):
    stage(case); before = input_snapshot(); wanted = expected(case); obj.call_method("CompileCameraFocusDistanceChannelV1")
    require(input_snapshot() == before, label + ":inputs-mutated"); require(bool(get(obj, "CameraFocusCompileValidV1")), label + ":valid")
    require(str(get(obj, "CameraFocusFailureCodeV1")) == "", label + ":failure"); require(str(get(obj, "CameraFocusCompiledModeV1")) == wanted.mode, label + ":mode"); require(str(get(obj, "CameraFocusCompiledDomainV1")) == wanted.domain, label + ":domain")
    actual_times = tuple(float(value) for value in get(obj, "CameraFocusCompiledTimesSecondsV1")); actual_distances = tuple(float(value) for value in get(obj, "CameraFocusCompiledDistancesCmV1"))
    require(actual_times == wanted.times_seconds, label + ":times"); require(len(actual_distances) == len(wanted.distances_cm) and all(close(left, right) for left, right in zip(actual_distances, wanted.distances_cm)), label + ":distances")


try:
    cases = (
        {"mode":"manual_distance","domain":"linear","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"manual":[100,200,300]},
        {"mode":"manual_distance","domain":"reciprocal","step":.25,"times":[0,.25,.5],"cameras":[(1,2,3)]*3,"manual":[300,200,100]},
        {"mode":"fixed_world","domain":"linear","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0),(25,0,0),(50,0,0)],"targets":[(400,0,0)]},
        {"mode":"fixed_world","domain":"reciprocal","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0),(0,30,0),(0,60,0)],"targets":[(0,500,0)]},
        {"mode":"rack_fixed","domain":"linear","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"rack_a":(100,0,0),"rack_b":(400,0,0),"weights":[0,.5,1]},
        {"mode":"rack_fixed","domain":"reciprocal","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"rack_a":(100,0,0),"rack_b":(400,0,0),"weights":[0,.5,1]},
        {"mode":"track_prebaked","domain":"linear","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0),(10,0,0),(20,0,0)],"targets":[(100,0,0),(210,0,0),(420,0,0)]},
        {"mode":"track_prebaked","domain":"reciprocal","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"targets":[(100,0,0),(200,0,0),(400,0,0)]},
        {"mode":"smoothed_autofocus","domain":"linear","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"targets":[(100,0,0),(400,0,0),(200,0,0)],"response":.5},
        {"mode":"smoothed_autofocus","domain":"reciprocal","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"targets":[(400,0,0),(100,0,0),(300,0,0)],"response":.25},
    )
    for order_name, order in (("forward", cases), ("reverse", tuple(reversed(cases)))):
        for index, case in enumerate(order): compile_case(case, f"{order_name}:{index}")
    set_(obj, "CameraFocusMarkerValidV1", True); set_(obj, "CameraFocusMarkerPositionV1", vector((9,8,7))); set_(obj, "CameraFocusMarkerRevisionV1", 41)
    set_(obj, "CameraFocusTraceHitValidV1", False); set_(obj, "CameraFocusTraceHitPositionV1", vector((999,999,999))); before_marker = (bool(get(obj,"CameraFocusMarkerValidV1")), normalized(get(obj,"CameraFocusMarkerPositionV1")), int(get(obj,"CameraFocusMarkerRevisionV1"))); obj.call_method("SetCameraFocusHereV1"); require((bool(get(obj,"CameraFocusMarkerValidV1")), normalized(get(obj,"CameraFocusMarkerPositionV1")), int(get(obj,"CameraFocusMarkerRevisionV1"))) == before_marker, "trace-miss-mutated")
    set_(obj, "CameraFocusTraceHitValidV1", True); set_(obj, "CameraFocusTraceHitPositionV1", vector((123,456,789))); obj.call_method("SetCameraFocusHereV1"); require(bool(get(obj,"CameraFocusMarkerValidV1")) and normalized(get(obj,"CameraFocusMarkerPositionV1")) == (123.0,456.0,789.0) and int(get(obj,"CameraFocusMarkerRevisionV1")) == 42, "trace-hit")
    prior_times = list(get(obj, "CameraFocusCompiledTimesSecondsV1")); prior_distances = list(get(obj, "CameraFocusCompiledDistancesCmV1")); prior_mode = str(get(obj,"CameraFocusCompiledModeV1")); prior_domain = str(get(obj,"CameraFocusCompiledDomainV1"))
    invalid = {"mode":"track_prebaked","domain":"linear","step":.25,"times":[0,.25,.5],"cameras":[(0,0,0)]*3,"targets":[(100,0,0),(0,0,0),(300,0,0)]}; stage(invalid); obj.call_method("CompileCameraFocusDistanceChannelV1"); require(not bool(get(obj,"CameraFocusCompileValidV1")), "invalid-full-compile"); require(list(get(obj,"CameraFocusCompiledTimesSecondsV1")) == prior_times and list(get(obj,"CameraFocusCompiledDistancesCmV1")) == prior_distances and str(get(obj,"CameraFocusCompiledModeV1")) == prior_mode and str(get(obj,"CameraFocusCompiledDomainV1")) == prior_domain, "invalid-full-overwrote-snapshot")
    set_(obj,"CameraFocusCandidateValidV1",True); set_(obj,"CameraFocusInputTimesSecondsV1",[0.0,.25,.5]); set_(obj,"CameraFocusCandidateDistancesCmV1",[100.0,200.0]); obj.call_method("CommitCameraFocusDistanceChannelV1"); require(not bool(get(obj,"CameraFocusCompileValidV1")) and str(get(obj,"CameraFocusFailureCodeV1")) == "commit_failed", "direct-commit-failure"); require(list(get(obj,"CameraFocusCompiledTimesSecondsV1")) == prior_times and list(get(obj,"CameraFocusCompiledDistancesCmV1")) == prior_distances, "direct-commit-overwrote-snapshot")
    emit("FORWARD_CASES",len(cases)); emit("REVERSE_CASES",len(cases)); emit("TRACE_MISS_ZERO_MUTATION",True); emit("TRACE_HIT_ATOMIC",True); emit("FAILURE_FAMILIES",2); emit("RESULT","PASS")
finally:
    for name, value in saved.items(): set_(obj, name, clone(value))
    emit("DEFAULTS_RESTORED", all(normalized(get(obj,name)) == normalized(value) for name,value in saved.items()))
