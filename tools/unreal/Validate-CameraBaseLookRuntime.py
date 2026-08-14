"""Execute the saved named camera-look helper against its independent oracle."""
from __future__ import annotations
import importlib,json,sys
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_LOOK_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_base_look_blueprint_schema.json").read_text(encoding="utf-8"));INPUTS=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"]=="input");AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1")
RESULT_FIELDS=("CameraLookResultPresetIdV1","CameraLookResultChannelIdsV1","CameraLookResultBaseValuesV1","CameraLookResultValuesV1","CameraLookResultOverrideMaskV1")
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
def clone(value):return [clone(item) for item in value] if isinstance(value,(list,tuple)) else value
def normalized(value):return tuple(normalized(item) for item in value) if isinstance(value,(list,tuple)) else value
def close(left,right):return abs(float(left)-float(right))<=3e-5*max(1.0,abs(float(left)),abs(float(right)))

sys.path.insert(0,str(ROOT/"tools/trajectory"));import camera_base_look_reference as oracle;oracle=importlib.reload(oracle)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={spec["name"]:clone(get(obj,spec["name"])) for spec in SCHEMA["variables"]}
def stage(preset,ids,values):set_(obj,"CameraLookInputPresetIdV1",preset);set_(obj,"CameraLookInputAuthoredChannelIdsV1",list(ids));set_(obj,"CameraLookInputAuthoredValuesV1",list(values))
def input_snapshot():return tuple(normalized(get(obj,name)) for name in INPUTS)
def authorship_snapshot():return tuple(normalized(get(obj,name)) for name in AUTHORSHIP)
def compile_case(preset,ids,values,label):
    stage(preset,ids,values);before_inputs=input_snapshot();before_authorship=authorship_snapshot();wanted=oracle.compose_camera_base_look_v1(preset,ids,values);obj.call_method("ComposeCameraLookV1");require(input_snapshot()==before_inputs,label+":inputs");require(authorship_snapshot()==before_authorship,label+":body-gimbal");require(bool(get(obj,"CameraLookResultValidV1")),label+":valid");require(str(get(obj,"CameraLookFailureCodeV1"))=="",label+":failure");require(str(get(obj,"CameraLookResultPresetIdV1"))==wanted.preset_id,label+":preset");require(tuple(str(v) for v in get(obj,"CameraLookResultChannelIdsV1"))==wanted.channel_ids,label+":channels");actual_base=tuple(float(v) for v in get(obj,"CameraLookResultBaseValuesV1"));actual=tuple(float(v) for v in get(obj,"CameraLookResultValuesV1"));mask=tuple(bool(v) for v in get(obj,"CameraLookResultOverrideMaskV1"));require(all(close(a,b) for a,b in zip(actual_base,wanted.base_values)) and len(actual_base)==13,label+":base");require(all(close(a,b) for a,b in zip(actual,wanted.values)) and len(actual)==13,label+":values");require(mask==wanted.authored_override_mask,label+":mask")
try:
    cases=(("raw",(),()),("clean_cinematic",("focal_length_mm",),(72.0,)),("epic_landscape",("exposure_ev","vignette_weight"),(-0.5,.25)),("dreamy_shallow_focus",("focus_distance_cm","aperture_fstop"),(350.0,1.2)),("dark_sorcery",("bloom_weight",),(.8,)),("high_speed_fpv",("motion_blur_weight","chromatic_aberration_weight"),(.2,.4)),("vintage_lens",("focal_length_mm","exposure_ev"),(105.0,-.2)),("documentary",("focus_distance_cm",),(2500.0,)))
    for order_name,order in (("forward",cases),("reverse",tuple(reversed(cases)))):
        for index,case in enumerate(order):compile_case(*case,f"{order_name}:{index}")
    prior={name:clone(get(obj,name)) for name in RESULT_FIELDS};before_authorship=authorship_snapshot();stage("unknown",(),());obj.call_method("ComposeCameraLookV1");require(not bool(get(obj,"CameraLookResultValidV1")),"invalid-preset accepted");require(all(normalized(get(obj,name))==normalized(value) for name,value in prior.items()),"invalid-preset overwrote snapshot");require(authorship_snapshot()==before_authorship,"invalid-preset body-gimbal")
    stage("raw",("bloom_weight","bloom_weight"),(.2,.3));obj.call_method("ComposeCameraLookV1");require(not bool(get(obj,"CameraLookResultValidV1")),"duplicate accepted");require(all(normalized(get(obj,name))==normalized(value) for name,value in prior.items()),"duplicate overwrote snapshot")
    set_(obj,"CameraLookCandidateValidV1",True);set_(obj,"CameraLookCandidateBaseValuesV1",[0.0]*13);set_(obj,"CameraLookCandidateValuesV1",[0.0]*12);set_(obj,"CameraLookCandidateOverrideMaskV1",[False]*13);obj.call_method("CommitCameraLookCompositionV1");require(not bool(get(obj,"CameraLookResultValidV1")) and str(get(obj,"CameraLookFailureCodeV1"))=="commit_failed","direct commit failure");require(all(normalized(get(obj,name))==normalized(value) for name,value in prior.items()),"direct commit overwrote snapshot")
    emit("FORWARD_CASES",len(cases));emit("REVERSE_CASES",len(cases));emit("BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("FAILURE_FAMILIES",3);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,clone(value))
    emit("DEFAULTS_RESTORED",all(normalized(get(obj,name))==normalized(value) for name,value in saved.items()))
