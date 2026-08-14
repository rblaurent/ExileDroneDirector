"""Warm CDO acceptance for the engine-neutral camera application boundary."""
from __future__ import annotations

import json
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_ENGINE_RUNTIME"
ROOT = Path(__file__).resolve().parents[2]
DIRECTOR_CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_engine_application_blueprint_schema.json").read_text(encoding="utf-8"))
CHANNEL_SCHEMA = json.loads((ROOT / "tools/trajectory/camera_channel_assembly_blueprint_schema.json").read_text(encoding="utf-8"))
ENGINE_NAMES = tuple(item["name"] for item in SCHEMA["variables"])
CHANNEL_RESULTS = tuple(item["name"] for item in CHANNEL_SCHEMA["variables"] if item["name"].startswith("CameraChannelResult"))
SAVED_NAMES = tuple(dict.fromkeys((*ENGINE_NAMES, *CHANNEL_RESULTS)))
AVAILABLE = (True, True, True, True, True, False, True, True, True, False, False, True, True, False, False)
FRAMES = (
    ("runtime_forward", 32.0, 18.0, (48.0, 2.0, 320.0, 1.0, 1.25, 0.2, 0.3, 0.0, 0.0, 0.4, 0.5, 0.0, 0.0)),
    ("runtime_reverse", 44.0, 25.0, (70.0, 5.6, 800.0, 1.0, -0.75, 0.8, 0.6, 0.0, 0.0, 0.1, 0.2, 0.0, 0.0)),
)


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(value, message):
    if not value: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in variants(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"missing:{name}")
def set_(obj, name, value):
    for candidate in variants(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(f"cannot-set:{name}")
def clone(value): return list(value) if isinstance(value, (list, tuple)) else value
def norm(value): return tuple(value) if isinstance(value, (list, tuple)) else value
def struct_text(value):
    exporter = getattr(value, "export_text", None)
    return exporter() if callable(exporter) else str(value)
def stage_frame(obj, frame):
    preset,width,height,values=frame
    for name,value in (("CameraChannelResultFilmbackPresetIdV1",preset),("CameraChannelResultFilmbackSensorWidthMmV1",width),("CameraChannelResultFilmbackSensorHeightMmV1",height),("CameraChannelResultValuesV1",list(values)),("CameraChannelResultVelocitiesV1",[0.0]*13),("CameraChannelResultAccelerationsV1",[0.0]*13),("CameraChannelResultCompleteV1",True),("CameraChannelResultValidV1",True)): set_(obj,name,value)
def baseline_snapshot(obj):
    return (str(get(obj,"CameraApplyBaselineFilmbackPresetIdV1")),tuple(get(obj,"CameraApplyBaselineTargetValuesV1")),struct_text(get(obj,"CameraApplyBaselineFilmbackSettingsV1")),struct_text(get(obj,"CameraApplyBaselineFocusSettingsV1")),struct_text(get(obj,"CameraApplyBaselinePostProcessSettingsV1")))
def exercise(obj, run):
    ordered=FRAMES if run==1 else tuple(reversed(FRAMES))
    for index,frame in enumerate(ordered):
        preset,width,height,values=frame;stage_frame(obj,frame);inputs=tuple(norm(get(obj,name)) for name in CHANNEL_RESULTS);baseline=baseline_snapshot(obj)
        obj.call_method("ResetCameraEngineApplicationResultV1");obj.call_method("StageEvaluatedCameraChannelFrameV1");obj.call_method("ValidateCameraEngineApplicationInputsV1")
        require(tuple(norm(get(obj,name)) for name in CHANNEL_RESULTS)==inputs,f"warm-{run}:{index}:inputs")
        require(bool(get(obj,"CameraApplyInputValidV1")),f"warm-{run}:{index}:stage")
        require(tuple(get(obj,"CameraApplyInputTargetValuesV1"))==(width,height,*values),f"warm-{run}:{index}:canonical-order")
        require(bool(get(obj,"CameraApplyScratchStageValidV1")),f"warm-{run}:{index}:validate")
        require(str(get(obj,"CameraApplyFailureCodeV1"))=="",f"warm-{run}:{index}:failure")
        require(not bool(get(obj,"CameraApplySessionActiveV1")),f"warm-{run}:{index}:unexpected-session")
        obj.call_method("CaptureCameraEngineStateV1")
        require(not bool(get(obj,"CameraApplyResultValidV1")),f"warm-{run}:{index}:CDO-capture-accepted")
        require(not bool(get(obj,"CameraApplySessionActiveV1")),f"warm-{run}:{index}:CDO-capture-active")
        require(baseline_snapshot(obj)==baseline,f"warm-{run}:{index}:failed-capture-mutated-baseline")
    stage_frame(obj,("bad_shape",36.0,24.0,FRAMES[0][3][:-1]));obj.call_method("StageEvaluatedCameraChannelFrameV1")
    require(not bool(get(obj,"CameraApplyInputValidV1")),f"warm-{run}:bad-shape")
    require(tuple(get(obj,"CameraApplyInputTargetValuesV1"))==(),f"warm-{run}:bad-shape-values")
    before=baseline_snapshot(obj);obj.call_method("RestoreCameraEngineStateV1");require(baseline_snapshot(obj)==before,f"warm-{run}:inactive-restore")
    emit("WARM_CDO_RUN",f"{run}|canonical_frames=2|camera_less_capture_fail_closed=true|inactive_restore=true")


cls=unreal.load_class(None,DIRECTOR_CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={name:clone(get(obj,name)) for name in SAVED_NAMES}
try:
    require(tuple(bool(value) for value in get(obj,"CameraApplyCapabilityAvailableV1"))==AVAILABLE,"capability-manifest")
    exercise(obj,1);exercise(obj,2);emit("ENGINE_NEUTRAL_FRAMES",4);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,value)
    emit("DEFAULTS_RESTORED",all(norm(get(obj,name))==norm(value) for name,value in saved.items()))
