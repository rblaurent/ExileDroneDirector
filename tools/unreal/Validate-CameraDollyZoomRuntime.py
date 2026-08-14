"""Execute the saved dolly-zoom helper against its deterministic oracle."""
from __future__ import annotations
import importlib, json, sys
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_DOLLY_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_dolly_zoom_blueprint_schema.json").read_text(encoding="utf-8"));INPUTS=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"]=="input")
AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
    for candidate in variants(name):
        try:return obj.get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError("missing property:"+name)
def set_(obj,name,value):
    for candidate in variants(name):
        try:obj.set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError("could not set property:"+name)
def vector(value):return unreal.Vector(float(value[0]),float(value[1]),float(value[2]))
def clone(value):
    if isinstance(value,unreal.Vector):return unreal.Vector(value.x,value.y,value.z)
    if isinstance(value,(list,tuple)):return [clone(item) for item in value]
    return value
def normalized(value):
    if isinstance(value,unreal.Vector):return (float(value.x),float(value.y),float(value.z))
    if hasattr(value,"x") and hasattr(value,"y") and hasattr(value,"z") and hasattr(value,"w"):return (float(value.x),float(value.y),float(value.z),float(value.w))
    if isinstance(value,(list,tuple)):return tuple(normalized(item) for item in value)
    return value
def close(left,right):return abs(float(left)-float(right))<=3e-5*max(1.0,abs(float(left)),abs(float(right)))

sys.path.insert(0,str(ROOT/"tools/trajectory"));import camera_dolly_zoom_reference as oracle;oracle=importlib.reload(oracle)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={spec["name"]:clone(get(obj,spec["name"])) for spec in SCHEMA["variables"]}
def stage(case):set_(obj,"CameraDollyInputTimesSecondsV1",list(case["times"]));set_(obj,"CameraDollyInputCameraPositionsV1",[vector(value) for value in case["positions"]]);set_(obj,"CameraDollyInputSubjectPositionV1",vector(case["subject"]));set_(obj,"CameraDollyInputReferenceSampleIndexV1",case["reference"]);set_(obj,"CameraDollyInputReferenceFocalLengthMmV1",case["focal"])
def input_snapshot():return tuple(normalized(get(obj,name)) for name in INPUTS)
def authorship_snapshot():return tuple(normalized(get(obj,name)) for name in AUTHORSHIP)
def expected(case):return oracle.compile_camera_dolly_zoom_v1(case["times"],case["positions"],case["subject"],case["reference"],case["focal"])
def emit_stage_state(label):
    emit("STAGE_STATE",f"{label}|validation:{get(obj,'CameraDollyValidationValidV1')}|candidate:{get(obj,'CameraDollyCandidateValidV1')}|compile:{get(obj,'CameraDollyCompileValidV1')}|distances:{len(get(obj,'CameraDollyCandidateSubjectDistancesCmV1'))}|focals:{len(get(obj,'CameraDollyCandidateFocalLengthsMmV1'))}|failure:{get(obj,'CameraDollyFailureCodeV1')}")
def compile_case(case,label):
    stage(case);before_inputs=input_snapshot();before_authorship=authorship_snapshot();wanted=expected(case);obj.call_method("CompileCameraDollyZoomV1")
    if not bool(get(obj,"CameraDollyCompileValidV1")):
        emit("CASE_INVALID",f"{label}|validation:{get(obj,'CameraDollyValidationValidV1')}|candidate:{get(obj,'CameraDollyCandidateValidV1')}|distances:{len(get(obj,'CameraDollyCandidateSubjectDistancesCmV1'))}|focals:{len(get(obj,'CameraDollyCandidateFocalLengthsMmV1'))}|failure:{get(obj,'CameraDollyFailureCodeV1')}")
        stage(case)
        for method in ("ResetCameraDollyZoomV1","ValidateCameraDollyZoomInputsV1","BuildCameraDollyZoomCandidatesV1","CommitCameraDollyZoomV1"):
            obj.call_method(method);emit_stage_state(method)
    require(input_snapshot()==before_inputs,label+":inputs-mutated");require(authorship_snapshot()==before_authorship,label+":body-gimbal-mutated");require(bool(get(obj,"CameraDollyCompileValidV1")),label+":valid");require(str(get(obj,"CameraDollyFailureCodeV1"))=="",label+":failure")
    actual_times=tuple(float(value) for value in get(obj,"CameraDollyCompiledTimesSecondsV1"));actual_distances=tuple(float(value) for value in get(obj,"CameraDollyCompiledSubjectDistancesCmV1"));actual_focals=tuple(float(value) for value in get(obj,"CameraDollyCompiledFocalLengthsMmV1"));actual_reference=float(get(obj,"CameraDollyCompiledReferenceDistanceCmV1"));require(actual_times==wanted.times_seconds,label+":times");require(len(actual_distances)==len(wanted.subject_distances_cm) and all(close(a,b) for a,b in zip(actual_distances,wanted.subject_distances_cm)),label+":distances");require(len(actual_focals)==len(wanted.focal_lengths_mm) and all(close(a,b) for a,b in zip(actual_focals,wanted.focal_lengths_mm)),label+":focals");require(close(actual_reference,wanted.reference_distance_cm),label+":reference")
try:
    cases=(
        {"times":[0,.5,1],"positions":[(0,0,0),(500,0,0),(1000,0,0)],"subject":(2000,0,0),"reference":1,"focal":50},
        {"times":[0,.5,1],"positions":[(1500,0,0),(1000,0,0),(0,0,0)],"subject":(2000,0,0),"reference":1,"focal":50},
        {"times":[0,.2,.4],"positions":[(0,0,0),(100,200,300),(300,400,500)],"subject":(1000,1000,1000),"reference":1,"focal":35},
        {"times":[0,1,2],"positions":[(100,0,0),(200,0,0),(400,0,0)],"subject":(0,0,0),"reference":1,"focal":80},
        {"times":[0,.25,.5,.75],"positions":[(0,0,0),(1000,0,0),(2000,0,0),(3000,0,0)],"subject":(5000,0,0),"reference":3,"focal":25},
        {"times":[0,.1,.2],"positions":[(250,0,0),(500,0,0),(750,0,0)],"subject":(0,0,0),"reference":0,"focal":10},
    )
    for order_name,order in (("forward",cases),("reverse",tuple(reversed(cases)))):
        for index,case in enumerate(order):compile_case(case,f"{order_name}:{index}")
    prior={name:clone(get(obj,name)) for name in ("CameraDollyCompiledTimesSecondsV1","CameraDollyCompiledSubjectDistancesCmV1","CameraDollyCompiledFocalLengthsMmV1","CameraDollyCompiledReferenceDistanceCmV1")};before_authorship=authorship_snapshot();invalid={"times":[0,1],"positions":[(1,0,0),(1001,0,0)],"subject":(0,0,0),"reference":0,"focal":1000};stage(invalid);obj.call_method("CompileCameraDollyZoomV1");require(not bool(get(obj,"CameraDollyCompileValidV1")),"invalid-full-compile");require(all(normalized(get(obj,name))==normalized(value) for name,value in prior.items()),"invalid-full-overwrote-snapshot");require(authorship_snapshot()==before_authorship,"invalid-mutated-body-gimbal")
    set_(obj,"CameraDollyCandidateValidV1",True);set_(obj,"CameraDollyInputTimesSecondsV1",[0.0,.5,1.0]);set_(obj,"CameraDollyCandidateSubjectDistancesCmV1",[100.0,200.0]);set_(obj,"CameraDollyCandidateFocalLengthsMmV1",[35.0,70.0,105.0]);obj.call_method("CommitCameraDollyZoomV1");require(not bool(get(obj,"CameraDollyCompileValidV1")) and str(get(obj,"CameraDollyFailureCodeV1"))=="commit_failed","direct-commit-failure");require(all(normalized(get(obj,name))==normalized(value) for name,value in prior.items()),"direct-commit-overwrote-snapshot")
    emit("FORWARD_CASES",len(cases));emit("REVERSE_CASES",len(cases));emit("BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("FAILURE_FAMILIES",2);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,clone(value))
    emit("DEFAULTS_RESTORED",all(normalized(get(obj,name))==normalized(value) for name,value in saved.items()))
