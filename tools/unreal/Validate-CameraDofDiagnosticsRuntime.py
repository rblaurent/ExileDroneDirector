"""Execute the saved camera DOF family against its independent oracle."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_DOF_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_dof_diagnostics_blueprint_schema.json").read_text(encoding="utf-8"))
UPSTREAM = ("CameraChannelResultValuesV1", "CameraChannelResultFilmbackSensorWidthMmV1", "CameraChannelResultFilmbackSensorHeightMmV1", "CameraChannelResultValidV1")
RESULTS = {
    "circle_of_confusion_mm": "CameraDofCircleOfConfusionMmV1",
    "hyperfocal_distance_cm": "CameraDofHyperfocalDistanceCmV1",
    "focal_plane_distance_cm": "CameraDofFocalPlaneDistanceCmV1",
    "near_limit_cm": "CameraDofNearLimitCmV1",
    "far_limit_cm": "CameraDofFarLimitCmV1",
    "far_unbounded": "CameraDofFarUnboundedV1",
    "front_depth_cm": "CameraDofFrontDepthCmV1",
    "rear_depth_cm": "CameraDofRearDepthCmV1",
    "focal_plane_width_cm": "CameraDofFocalPlaneWidthCmV1",
    "focal_plane_height_cm": "CameraDofFocalPlaneHeightCmV1",
}


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)
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
def clone(value):
    if isinstance(value, (list, tuple)): return [clone(item) for item in value]
    return value
def normalized(value):
    if isinstance(value, (list, tuple)): return tuple(normalized(item) for item in value)
    return value
def close(left, right): return abs(float(left) - float(right)) <= 4e-5 * max(1.0, abs(float(left)), abs(float(right)))


sys.path.insert(0, str(ROOT / "tools/trajectory"))
import camera_dof_diagnostics_reference as oracle
oracle = importlib.reload(oracle)
cls = unreal.load_class(None, CLASS); require(cls is not None, "class")
obj = unreal.get_default_object(cls)
owned = tuple(spec["name"] for spec in SCHEMA["variables"])
saved = {name: clone(get(obj, name)) for name in (*owned, *UPSTREAM)}


def frame(case): return [case["focal"], case["aperture"], case["focus"], *case.get("tail", [0.0] * 10)]
def stage(case):
    set_(obj, "CameraChannelResultValidV1", case.get("valid", True))
    set_(obj, "CameraChannelResultFilmbackSensorWidthMmV1", case["width"])
    set_(obj, "CameraChannelResultFilmbackSensorHeightMmV1", case["height"])
    set_(obj, "CameraChannelResultValuesV1", frame(case))
def execute(case, label):
    before = tuple(normalized(get(obj, name)) for name in UPSTREAM)
    expected = oracle.evaluate_camera_dof_diagnostics_v1(True, case["width"], case["height"], frame(case))
    obj.call_method("EvaluateCameraDofDiagnosticsV1")
    require(tuple(normalized(get(obj, name)) for name in UPSTREAM) == before, label + ":frame-mutated")
    require(bool(get(obj, "CameraDofResultValidV1")), label + ":valid")
    require(str(get(obj, "CameraDofFailureCodeV1")) == "", label + ":failure")
    for field, name in RESULTS.items():
        actual, wanted = get(obj, name), getattr(expected, field)
        require(actual == wanted if isinstance(wanted, bool) else close(actual, wanted), label + ":" + field)
    return expected


cases = (
    {"width":36.0,"height":24.0,"focal":50.0,"aperture":2.8,"focus":1000.0},
    {"width":36.0,"height":24.0,"focal":24.0,"aperture":16.0,"focus":300.0},
    {"width":22.2,"height":14.8,"focal":85.0,"aperture":1.4,"focus":250.0},
    {"width":70.0,"height":52.0,"focal":300.0,"aperture":8.0,"focus":5000.0},
    {"width":12.8,"height":9.6,"focal":8.0,"aperture":22.0,"focus":100000.0},
    {"width":36.0,"height":24.0,"focal":1000.0,"aperture":64.0,"focus":100.001},
)
try:
    domains = set()
    for order_name, order in (("forward", cases), ("reverse", tuple(reversed(cases)))):
        for index, case in enumerate(order):
            stage(case); expected = execute(case, f"{order_name}:{index}"); domains.add(expected.far_unbounded)
    require(domains == {False, True}, "far-domain-coverage")
    set_(obj, "CameraDofCircleOfConfusionMmV1", 17.0); set_(obj, "CameraDofFarLimitCmV1", 19.0); set_(obj, "CameraDofFarUnboundedV1", True)
    set_(obj, "CameraDofStageValidV1", True); set_(obj, "CameraDofStageFilmbackWidthMmV1", 36.0); set_(obj, "CameraDofStageFilmbackHeightMmV1", 24.0)
    set_(obj, "CameraDofStageFocalLengthMmV1", 1000.0); set_(obj, "CameraDofStageApertureFstopV1", 2.8); set_(obj, "CameraDofStageFocusDistanceCmV1", 100.0)
    obj.call_method("ComputeCameraDofDiagnosticsV1")
    require(not bool(get(obj, "CameraDofResultValidV1")) and str(get(obj, "CameraDofFailureCodeV1")) == "camera_dof_compute_failed", "direct-compute-failure")
    require(close(get(obj, "CameraDofCircleOfConfusionMmV1"), 17.0) and close(get(obj, "CameraDofFarLimitCmV1"), 19.0) and bool(get(obj, "CameraDofFarUnboundedV1")), "direct-compute-overwrite")
    bad = dict(cases[0]); bad["valid"] = False; stage(bad); obj.call_method("EvaluateCameraDofDiagnosticsV1")
    require(not bool(get(obj, "CameraDofResultValidV1")) and str(get(obj, "CameraDofFailureCodeV1")) == "camera_dof_compute_failed", "invalid-frame")
    require(not bool(get(obj, "CameraDofStageValidV1")), "invalid-frame-stage")
    emit("FORWARD_CASES", len(cases)); emit("REVERSE_CASES", len(cases)); emit("BOUNDED_AND_UNBOUNDED", True); emit("FAILURE_FAMILIES", 2); emit("RESULT", "PASS")
finally:
    for name, value in saved.items(): set_(obj, name, clone(value))
    emit("DEFAULTS_RESTORED", all(normalized(get(obj, name)) == normalized(value) for name, value in saved.items()))
