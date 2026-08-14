"""Execute the saved viewer-comfort helper against its independent oracle."""
from __future__ import annotations
import importlib,json,math,sys
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_COMFORT_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_viewer_comfort_blueprint_schema.json").read_text(encoding="utf-8"));INPUTS=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] in ("input","preference"));AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1");UPSTREAM=("CameraChannelResultValuesV1","CameraLookResultValuesV1","CameraApplyCurrentTargetValuesV1");RESULT_FIELDS=("CameraComfortResultPositionV1","CameraComfortResultGimbalQuatV1","CameraComfortResultChannelValuesV1","CameraComfortResultEffectiveWeightsV1","CameraComfortResultAppliedV1")
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
def vector(value):return unreal.Vector(*(float(v) for v in value))
def quat(value):return unreal.Quat(*(float(v) for v in value))
def vt(value):return float(value.x),float(value.y),float(value.z)
def qt(value):return float(value.x),float(value.y),float(value.z),float(value.w)
def clone(value):
    if isinstance(value,(list,tuple)):return [clone(item) for item in value]
    return value.copy() if hasattr(value,"copy") else value
def normalized(value):
    if isinstance(value,(list,tuple)):return tuple(normalized(item) for item in value)
    if isinstance(value,unreal.Vector):return vt(value)
    if isinstance(value,unreal.Quat):return qt(value)
    return value
def close(left,right,tolerance=4e-4):return abs(float(left)-float(right))<=tolerance*max(1.0,abs(float(left)),abs(float(right)))
def same_rotation(left,right,tolerance=4e-4):
    a=qt(left) if isinstance(left,unreal.Quat) else tuple(left);b=tuple(right);al=math.sqrt(sum(v*v for v in a));bl=math.sqrt(sum(v*v for v in b));return al>0.0 and bl>0.0 and abs(sum(x*y for x,y in zip(a,b))/(al*bl))>=1.0-tolerance
def axis_angle(axis,degrees):
    half=math.radians(degrees)*.5;scale=math.sin(half);return axis[0]*scale,axis[1]*scale,axis[2]*scale,math.cos(half)

sys.path.insert(0,str(ROOT/"tools/trajectory"));import camera_viewer_comfort_reference as oracle;oracle=importlib.reload(oracle)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={spec["name"]:clone(get(obj,spec["name"])) for spec in SCHEMA["variables"]}
base_channels=[35.0,2.8,1000.0,.8,2.0,.25,.3,.4,.5,.75,.6,.2,.1]
cases=(
    (False,(100.,200.,300.),axis_angle((1.,0.,0.),25.),(2.,-4.,6.),axis_angle((0.,0.,1.),8.),base_channels,(.1,.2,.3,.4,.5)),
    (True,(100.,200.,300.),axis_angle((1.,0.,0.),40.),(2.,-4.,6.),axis_angle((0.,0.,1.),8.),base_channels,(0.,0.,0.,0.,0.)),
    (True,(-10.,20.,5.),axis_angle((1.,0.,0.),-35.),(8.,2.,-4.),axis_angle((0.,1.,0.),12.),base_channels,(1.,.25,.5,.25,.75)),
    (True,(0.,0.,0.),axis_angle((0.,-1.,0.),90.),(0.,0.,3.),axis_angle((1.,0.,0.),5.),base_channels,(0.,1.,1.,1.,1.)),
    (True,(5.,6.,7.),axis_angle((0.,0.,1.),170.),(-1.,3.,2.),axis_angle((1.,0.,0.),-7.),base_channels,(.35,.6,.4,.8,.2)),
    (True,(-500.,250.,1000.),axis_angle((1.,0.,0.),75.),(10.,-10.,5.),axis_angle((0.,0.,1.),15.),base_channels,(1.,1.,1.,1.,1.)),
    (True,(1.,2.,3.),axis_angle((0.,1.,0.),-50.),(.5,.25,.125),axis_angle((1.,0.,0.),3.),base_channels,(.8,.7,.6,.5,.4)),
    (True,(999.,-444.,12.),axis_angle((1.,0.,0.),5.),(-7.,9.,-2.),axis_angle((0.,1.,0.),-9.),base_channels,(.2,.4,.6,.8,1.)),
)
def stage(case):
    enabled,position,gimbal,translation,rotation,channels,weights=case;set_(obj,"CameraComfortInputFrameValidV1",True);set_(obj,"CameraComfortInputPositionV1",vector(position));set_(obj,"CameraComfortInputGimbalQuatV1",quat(gimbal));set_(obj,"CameraComfortInputProceduralTranslationOffsetV1",vector(translation));set_(obj,"CameraComfortInputProceduralRotationOffsetV1",quat(rotation));set_(obj,"CameraComfortInputChannelValuesV1",list(channels));set_(obj,"CameraComfortEnabledV1",enabled)
    for name,value in zip(("CameraComfortRollWeightV1","CameraComfortShakeWeightV1","CameraComfortBlurWeightV1","CameraComfortExposureChangeWeightV1","CameraComfortChromaticAberrationWeightV1"),weights):set_(obj,name,value)
def wanted(case):
    enabled,position,gimbal,translation,rotation,channels,weights=case;settings=oracle.CameraViewerComfortSettingsV1(enabled,*weights);return oracle.apply_camera_viewer_comfort_v1(True,position,gimbal,translation,rotation,channels,settings)
def snapshot(names):return tuple(normalized(get(obj,name)) for name in names)
def verify(expected,label):
    require(bool(get(obj,"CameraComfortResultValidV1")),label+":valid");require(str(get(obj,"CameraComfortFailureCodeV1"))=="",label+":failure");actual_position=vt(get(obj,"CameraComfortResultPositionV1"));require(all(close(a,b) for a,b in zip(actual_position,expected.position)),label+":position");require(same_rotation(get(obj,"CameraComfortResultGimbalQuatV1"),expected.gimbal_rotation),label+":gimbal");actual_values=tuple(float(v) for v in get(obj,"CameraComfortResultChannelValuesV1"));require(len(actual_values)==13 and all(close(a,b) for a,b in zip(actual_values,expected.camera_channel_values)),label+":channels");actual_weights=tuple(float(v) for v in get(obj,"CameraComfortResultEffectiveWeightsV1"));require(len(actual_weights)==5 and all(close(a,b) for a,b in zip(actual_weights,expected.effective_weights)),label+":weights");require(bool(get(obj,"CameraComfortResultAppliedV1"))==expected.comfort_applied,label+":applied")
try:
    expected=tuple(wanted(case) for case in cases)
    for order_name,order in (("forward",tuple(range(len(cases)))),("reverse",tuple(reversed(range(len(cases)))))):
        for run_index,index in enumerate(order):
            stage(cases[index]);before_inputs=snapshot(INPUTS);before_owned=snapshot(AUTHORSHIP+UPSTREAM);obj.call_method("ApplyCameraViewerComfortV1");require(snapshot(INPUTS)==before_inputs,f"{order_name}:{run_index}:inputs");require(snapshot(AUTHORSHIP+UPSTREAM)==before_owned,f"{order_name}:{run_index}:ownership");verify(expected[index],f"{order_name}:{run_index}")
    accepted=snapshot(RESULT_FIELDS);failures=(
        ("frame",lambda:set_(obj,"CameraComfortInputFrameValidV1",False)),
        ("shape",lambda:set_(obj,"CameraComfortInputChannelValuesV1",base_channels[:-1])),
        ("weight",lambda:set_(obj,"CameraComfortRollWeightV1",-0.1)),
        ("quat",lambda:set_(obj,"CameraComfortInputGimbalQuatV1",unreal.Quat(0.,0.,0.,2.))),
        ("channel",lambda:set_(obj,"CameraComfortInputChannelValuesV1",[0.0]+base_channels[1:])),
    )
    for label,poison in failures:
        stage(cases[0]);poison();before_owned=snapshot(AUTHORSHIP+UPSTREAM);obj.call_method("ApplyCameraViewerComfortV1");require(not bool(get(obj,"CameraComfortResultValidV1")),label+":accepted");require(snapshot(RESULT_FIELDS)==accepted,label+":snapshot");require(snapshot(AUTHORSHIP+UPSTREAM)==before_owned,label+":ownership")
    stage(cases[1]);obj.call_method("ApplyCameraViewerComfortV1");accepted=snapshot(RESULT_FIELDS);set_(obj,"CameraComfortCandidateValidV1",True);set_(obj,"CameraComfortCandidateChannelValuesV1",[0.0]*12);set_(obj,"CameraComfortCandidateEffectiveWeightsV1",[1.0]*5);obj.call_method("CommitCameraViewerComfortV1");require(not bool(get(obj,"CameraComfortResultValidV1")) and str(get(obj,"CameraComfortFailureCodeV1"))=="commit_failed","direct-commit");require(snapshot(RESULT_FIELDS)==accepted,"direct-commit:snapshot")
    emit("FORWARD_CASES",len(cases));emit("REVERSE_CASES",len(cases));emit("FAILURE_CASES",len(failures)+1);emit("BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("UPSTREAM_RESULTS_PRESERVED",True);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,clone(value))
    restored=all(normalized(get(obj,name))==normalized(value) for name,value in saved.items());emit("DEFAULTS_RESTORED",restored);require(restored,"state restoration")
