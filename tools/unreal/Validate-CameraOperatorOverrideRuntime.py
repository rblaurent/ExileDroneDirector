"""Execute the saved camera-operator family against its independent oracle."""
from __future__ import annotations
import importlib,json,math,random,sys
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_OPERATOR_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_operator_override_blueprint_schema.json").read_text(encoding="utf-8"))
INPUT_POLICY=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] in ("input","policy"));STATE=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"]=="state");RESULT_VALUES=("CameraOperatorResultPositionV1","CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1","CameraOperatorResultModeV1","CameraOperatorResultOverrideActiveV1","CameraOperatorResultTransitionActiveV1","CameraOperatorResultTetherAppliedV1")
AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1");DOWNSTREAM=("CameraComfortResultPositionV1","CameraComfortResultGimbalQuatV1","CameraComfortResultChannelValuesV1","CameraChannelResultValuesV1","CameraApplyCurrentTargetValuesV1")
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
def clone(value):
    if isinstance(value,(list,tuple)):return [clone(item) for item in value]
    return value.copy() if hasattr(value,"copy") else value
def normalized(value):
    if isinstance(value,(list,tuple)):return tuple(normalized(item) for item in value)
    if isinstance(value,unreal.Vector):return float(value.x),float(value.y),float(value.z)
    if isinstance(value,unreal.Quat):return float(value.x),float(value.y),float(value.z),float(value.w)
    return value
def snapshot(obj,names):return tuple(normalized(get(obj,name)) for name in names)
def close(left,right,tolerance=5e-4):return abs(float(left)-float(right))<=tolerance*max(1.,abs(float(left)),abs(float(right)))
def vector_close(left,right):return all(close(a,b) for a,b in zip(normalized(left),right))
def same_rotation(left,right,tolerance=5e-4):
    a=normalized(left);b=tuple(right);al=math.sqrt(sum(v*v for v in a));bl=math.sqrt(sum(v*v for v in b));return al>0. and bl>0. and abs(sum(x*y for x,y in zip(a,b))/(al*bl))>=1.-tolerance
def axis_angle(axis,degrees):
    half=math.radians(degrees)*.5;factor=math.sin(half);return axis[0]*factor,axis[1]*factor,axis[2]*factor,math.cos(half)

sys.path.insert(0,str(ROOT/"tools/trajectory"));import camera_operator_override_reference as oracle;oracle=importlib.reload(oracle)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={spec["name"]:clone(get(obj,spec["name"])) for spec in SCHEMA["variables"]}

def stage(case):
    policy=case["policy"];state=case["previous_state"]
    for name,value in (
        ("CameraOperatorInputSourceValidV1",case["source_valid"]),("CameraOperatorInputRequestedModeV1",case["requested_mode"]),
        ("CameraOperatorInputAuthoredPositionV1",vector(case["authored_position"])),("CameraOperatorInputAuthoredBodyQuatV1",quat(case["authored_body_rotation"])),
        ("CameraOperatorInputAuthoredGimbalQuatV1",quat(case["authored_gimbal_rotation"])),("CameraOperatorInputCarrierFrameQuatV1",quat(case["carrier_frame_rotation"])),
        ("CameraOperatorInputTranslationV1",vector(case["translation_input"])),("CameraOperatorInputLookV1",vector(case["look_input"])),
        ("CameraOperatorInputDeltaSecondsV1",case["delta_seconds"]),("CameraOperatorInputRecenterRequestedV1",case["recenter_requested"]),
        ("CameraOperatorInputReturnToDirectedRequestedV1",case["return_to_directed_requested"]),
        ("CameraOperatorPolicyTranslationFrameV1",policy.translation_frame),("CameraOperatorPolicyMaximumTranslationSpeedV1",policy.maximum_translation_speed_cm_s),
        ("CameraOperatorPolicyTranslationAccelerationV1",policy.translation_acceleration_cm_s2),("CameraOperatorPolicyRecenterTranslationSpeedV1",policy.recenter_translation_speed_cm_s),
        ("CameraOperatorPolicyMaximumAngularSpeedV1",policy.maximum_angular_speed_deg_s),("CameraOperatorPolicyAngularAccelerationV1",policy.angular_acceleration_deg_s2),
        ("CameraOperatorPolicyRecenterAngularSpeedV1",policy.recenter_angular_speed_deg_s),("CameraOperatorPolicyTetherEnabledV1",policy.tether_enabled),
        ("CameraOperatorPolicyTetherDistanceV1",policy.tether_distance_cm),("CameraOperatorStateInitializedV1",state.initialized),
        ("CameraOperatorStateModeV1",state.mode),("CameraOperatorStateRecenterActiveV1",state.recenter_active),
        ("CameraOperatorStateTranslationOffsetV1",vector(state.translation_offset_cm)),("CameraOperatorStateTranslationVelocityV1",vector(state.translation_velocity_cm_s)),
        ("CameraOperatorStateLookOffsetQuatV1",quat(state.look_offset)),("CameraOperatorStateAngularVelocityV1",vector(state.angular_velocity_deg_s)),
    ):set_(obj,name,value)

def verify(expected,case,label):
    state=expected.state
    require(bool(get(obj,"CameraOperatorResultValidV1")),label+":valid");require(str(get(obj,"CameraOperatorFailureCodeV1"))=="",label+":failure")
    require(vector_close(get(obj,"CameraOperatorResultPositionV1"),expected.position),label+":position")
    require(same_rotation(get(obj,"CameraOperatorResultBodyQuatV1"),expected.body_rotation),label+":body")
    require(normalized(get(obj,"CameraOperatorResultBodyQuatV1"))==tuple(case["authored_body_rotation"]),label+":body-not-exact")
    require(same_rotation(get(obj,"CameraOperatorResultGimbalQuatV1"),expected.gimbal_rotation),label+":gimbal")
    require(str(get(obj,"CameraOperatorResultModeV1"))==state.mode,label+":result-mode")
    require(bool(get(obj,"CameraOperatorResultOverrideActiveV1"))==expected.override_active,label+":override")
    require(bool(get(obj,"CameraOperatorResultTransitionActiveV1"))==expected.transition_active,label+":transition")
    require(bool(get(obj,"CameraOperatorResultTetherAppliedV1"))==expected.tether_applied,label+":tether")
    require(bool(get(obj,"CameraOperatorStateInitializedV1"))==state.initialized,label+":state-initialized")
    require(str(get(obj,"CameraOperatorStateModeV1"))==state.mode,label+":state-mode")
    require(bool(get(obj,"CameraOperatorStateRecenterActiveV1"))==state.recenter_active,label+":state-recenter")
    require(vector_close(get(obj,"CameraOperatorStateTranslationOffsetV1"),state.translation_offset_cm),label+":state-offset")
    require(vector_close(get(obj,"CameraOperatorStateTranslationVelocityV1"),state.translation_velocity_cm_s),label+":state-velocity")
    require(same_rotation(get(obj,"CameraOperatorStateLookOffsetQuatV1"),state.look_offset),label+":state-look")
    require(vector_close(get(obj,"CameraOperatorStateAngularVelocityV1"),state.angular_velocity_deg_s),label+":state-angular")

rng=random.Random(0xEDD0F5E7);state=oracle.CameraOperatorStateV1();cases=[]
for index in range(40):
    policy=oracle.CameraOperatorPolicyV1(rng.choice(("world","carrier")),rng.uniform(300.,1400.),rng.uniform(900.,3000.),rng.uniform(200.,900.),rng.uniform(45.,150.),rng.uniform(120.,420.),rng.uniform(30.,100.),rng.choice((True,False)),rng.uniform(250.,4000.))
    case={"source_valid":True,"requested_mode":oracle.MODES_V1[index%3],"authored_position":(100.+index,-50.+index*.5,300.-index),"authored_body_rotation":axis_angle((1.,0.,0.),10.+index*.2),"authored_gimbal_rotation":axis_angle((0.,1.,0.),-25.+index*.3),"carrier_frame_rotation":axis_angle((0.,0.,1.),(index*17.)%170.),"translation_input":tuple(rng.uniform(-.9,.9) for _ in range(3)),"look_input":tuple(rng.uniform(-.9,.9) for _ in range(3)),"delta_seconds":rng.choice((1./60.,.025,.05)),"recenter_requested":index>0 and index%17==0,"return_to_directed_requested":index>0 and index%29==0,"policy":policy,"previous_state":state}
    expected=oracle.apply_camera_operator_override_v1(**case);cases.append((case,expected));state=expected.state

try:
    for order_name,order in (("forward",range(len(cases))),("reverse",reversed(range(len(cases))))):
        for run_index,index in enumerate(order):
            case,expected=cases[index];stage(case);before_inputs=snapshot(obj,INPUT_POLICY);before_external=snapshot(obj,AUTHORSHIP+DOWNSTREAM);obj.call_method("ApplyCameraOperatorOverrideV1");require(snapshot(obj,INPUT_POLICY)==before_inputs,f"{order_name}:{run_index}:inputs");require(snapshot(obj,AUTHORSHIP+DOWNSTREAM)==before_external,f"{order_name}:{run_index}:external");verify(expected,case,f"{order_name}:{run_index}")
    case,_=cases[12];stage(case);obj.call_method("ApplyCameraOperatorOverrideV1");accepted=snapshot(obj,RESULT_VALUES)
    failures=(
        ("source",lambda:set_(obj,"CameraOperatorInputSourceValidV1",False)),
        ("mode",lambda:set_(obj,"CameraOperatorInputRequestedModeV1","orbit")),
        ("body",lambda:set_(obj,"CameraOperatorInputAuthoredBodyQuatV1",unreal.Quat(0.,0.,0.,2.))),
        ("delta",lambda:set_(obj,"CameraOperatorInputDeltaSecondsV1",0.)),
        ("frame",lambda:set_(obj,"CameraOperatorPolicyTranslationFrameV1","body")),
    )
    for label,poison in failures:
        stage(case);poison();before_state=snapshot(obj,STATE);before_inputs=snapshot(obj,INPUT_POLICY);before_external=snapshot(obj,AUTHORSHIP+DOWNSTREAM);obj.call_method("ApplyCameraOperatorOverrideV1");require(not bool(get(obj,"CameraOperatorResultValidV1")),label+":accepted");require(str(get(obj,"CameraOperatorFailureCodeV1"))=="validation_failed",label+":failure-code");require(snapshot(obj,STATE)==before_state,label+":state");require(snapshot(obj,RESULT_VALUES)==accepted,label+":result");require(snapshot(obj,INPUT_POLICY)==before_inputs,label+":inputs");require(snapshot(obj,AUTHORSHIP+DOWNSTREAM)==before_external,label+":external")
    stage(case);obj.call_method("ApplyCameraOperatorOverrideV1");accepted=snapshot(obj,RESULT_VALUES);accepted_state=snapshot(obj,STATE);set_(obj,"CameraOperatorValidationValidV1",True);set_(obj,"CameraOperatorScratchValidV1",True);set_(obj,"CameraOperatorCandidateValidV1",True);set_(obj,"CameraOperatorCandidateBodyQuatV1",unreal.Quat(0.,0.,0.,2.));obj.call_method("CommitCameraOperatorOverrideV1");require(not bool(get(obj,"CameraOperatorResultValidV1")),"direct-commit:accepted");require(str(get(obj,"CameraOperatorFailureCodeV1"))=="candidate_invalid","direct-commit:code");require(snapshot(obj,RESULT_VALUES)==accepted,"direct-commit:result");require(snapshot(obj,STATE)==accepted_state,"direct-commit:state")
    emit("FORWARD_CASES",len(cases));emit("REVERSE_CASES",len(cases));emit("FAILURE_CASES",len(failures)+1);emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("CARRIER_FRAME_ISOLATED",True);emit("EXTERNAL_STATE_PRESERVED",True);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,clone(value))
    restored=all(normalized(get(obj,name))==normalized(value) for name,value in saved.items());emit("DEFAULTS_RESTORED",restored);require(restored,"state restoration")
