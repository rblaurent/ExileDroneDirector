"""Programmatic three-session PIE acceptance for viewer-local camera operation."""
from __future__ import annotations
import json,math,time,traceback
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_OPERATOR_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.;SCENARIOS=("distinct_directed","carrier_frame_isolation","fail_closed");ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_operator_override_blueprint_schema.json").read_text(encoding="utf-8"));NAMES=tuple(spec["name"] for spec in SCHEMA["variables"]);INPUT_POLICY=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] in ("input","policy"));STATE=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"]=="state");RESULT_VALUES=("CameraOperatorResultPositionV1","CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1","CameraOperatorResultModeV1","CameraOperatorResultOverrideActiveV1","CameraOperatorResultTransitionActiveV1","CameraOperatorResultTetherAppliedV1");AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1");DOWNSTREAM=("CameraComfortResultPositionV1","CameraComfortResultGimbalQuatV1","CameraComfortResultChannelValuesV1","CameraChannelResultValuesV1","CameraApplyCurrentTargetValuesV1")
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
def vector_close(value,wanted):return all(close(a,b) for a,b in zip(normalized(value),wanted))
def same_rotation(value,wanted,tolerance=5e-4):
    actual=normalized(value);al=math.sqrt(sum(v*v for v in actual));bl=math.sqrt(sum(v*v for v in wanted));return al>0. and bl>0. and abs(sum(a*b for a,b in zip(actual,wanted))/(al*bl))>=1.-tolerance
def axis_angle(axis,degrees):half=math.radians(degrees)*.5;factor=math.sin(half);return unreal.Quat(axis[0]*factor,axis[1]*factor,axis[2]*factor,math.cos(half))
def defaults():cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]

def stage_case(obj,scenario,originals):
    for name,value in originals.items():set_(obj,name,clone(value))
    common=(
        ("CameraOperatorInputSourceValidV1",True),("CameraOperatorInputRequestedModeV1","directed"),("CameraOperatorInputAuthoredPositionV1",unreal.Vector(100.,200.,300.)),
        ("CameraOperatorInputAuthoredBodyQuatV1",axis_angle((1.,0.,0.),20.)),("CameraOperatorInputAuthoredGimbalQuatV1",axis_angle((0.,1.,0.),-30.)),
        ("CameraOperatorInputCarrierFrameQuatV1",unreal.Quat(0.,0.,0.,1.)),("CameraOperatorInputTranslationV1",unreal.Vector(0.,0.,0.)),("CameraOperatorInputLookV1",unreal.Vector(0.,0.,0.)),
        ("CameraOperatorInputDeltaSecondsV1",.1),("CameraOperatorInputRecenterRequestedV1",False),("CameraOperatorInputReturnToDirectedRequestedV1",False),
        ("CameraOperatorPolicyTranslationFrameV1","world"),("CameraOperatorPolicyMaximumTranslationSpeedV1",1200.),("CameraOperatorPolicyTranslationAccelerationV1",2400.),
        ("CameraOperatorPolicyRecenterTranslationSpeedV1",800.),("CameraOperatorPolicyMaximumAngularSpeedV1",120.),("CameraOperatorPolicyAngularAccelerationV1",360.),
        ("CameraOperatorPolicyRecenterAngularSpeedV1",90.),("CameraOperatorPolicyTetherEnabledV1",True),("CameraOperatorPolicyTetherDistanceV1",3000.),
        ("CameraOperatorStateInitializedV1",True),("CameraOperatorStateModeV1","directed"),("CameraOperatorStateRecenterActiveV1",False),
        ("CameraOperatorStateTranslationOffsetV1",unreal.Vector(0.,0.,0.)),("CameraOperatorStateTranslationVelocityV1",unreal.Vector(0.,0.,0.)),
        ("CameraOperatorStateLookOffsetQuatV1",unreal.Quat(0.,0.,0.,1.)),("CameraOperatorStateAngularVelocityV1",unreal.Vector(0.,0.,0.)),
    )
    for name,value in common:set_(obj,name,value)
    if scenario=="distinct_directed":return
    if scenario=="carrier_frame_isolation":
        set_(obj,"CameraOperatorInputRequestedModeV1","carrier_freecam");set_(obj,"CameraOperatorInputCarrierFrameQuatV1",axis_angle((0.,0.,1.),90.));set_(obj,"CameraOperatorInputTranslationV1",unreal.Vector(1.,0.,0.));set_(obj,"CameraOperatorPolicyTranslationFrameV1","carrier");set_(obj,"CameraOperatorStateModeV1","carrier_freecam");return
    if scenario=="fail_closed":
        set_(obj,"CameraOperatorInputSourceValidV1",False);set_(obj,"CameraOperatorStateModeV1","free_look");set_(obj,"CameraOperatorStateTranslationOffsetV1",unreal.Vector(5.,6.,7.));set_(obj,"CameraOperatorStateTranslationVelocityV1",unreal.Vector(1.,2.,3.));set_(obj,"CameraOperatorResultPositionV1",unreal.Vector(9.,8.,7.));set_(obj,"CameraOperatorResultBodyQuatV1",axis_angle((1.,0.,0.),11.));set_(obj,"CameraOperatorResultGimbalQuatV1",axis_angle((0.,1.,0.),-22.));set_(obj,"CameraOperatorResultModeV1","free_look");set_(obj,"CameraOperatorResultOverrideActiveV1",True);set_(obj,"CameraOperatorResultTransitionActiveV1",True);set_(obj,"CameraOperatorResultTetherAppliedV1",False);return
    raise RuntimeError("unknown scenario:"+scenario)

def run_scenario(component,scenario):
    before_inputs=snapshot(component,INPUT_POLICY);before_external=snapshot(component,AUTHORSHIP+DOWNSTREAM);prior_state=snapshot(component,STATE);prior_result=snapshot(component,RESULT_VALUES);component.call_method("ApplyCameraOperatorOverrideV1");require(snapshot(component,INPUT_POLICY)==before_inputs,"inputs mutated");require(snapshot(component,AUTHORSHIP+DOWNSTREAM)==before_external,"external state mutated")
    body=normalized(get(component,"CameraOperatorResultBodyQuatV1"));gimbal=normalized(get(component,"CameraOperatorResultGimbalQuatV1"))
    if scenario=="distinct_directed":
        require(bool(get(component,"CameraOperatorResultValidV1")),"directed invalid");require(vector_close(get(component,"CameraOperatorResultPositionV1"),(100.,200.,300.)),"directed position");require(body==normalized(axis_angle((1.,0.,0.),20.)),"body not exact");require(same_rotation(get(component,"CameraOperatorResultGimbalQuatV1"),normalized(axis_angle((0.,1.,0.),-30.))),"gimbal");require(body!=gimbal,"body/gimbal aliased");require(str(get(component,"CameraOperatorResultModeV1"))=="directed","directed mode");require(not bool(get(component,"CameraOperatorResultOverrideActiveV1")),"directed override");emit("DISTINCT_AUTHORSHIP_RESULT","PASS")
    elif scenario=="carrier_frame_isolation":
        require(bool(get(component,"CameraOperatorResultValidV1")),"carrier invalid");require(vector_close(get(component,"CameraOperatorStateTranslationOffsetV1"),(0.,24.,0.)),"carrier offset");require(vector_close(get(component,"CameraOperatorResultPositionV1"),(100.,224.,300.)),"carrier position");require(body==normalized(axis_angle((1.,0.,0.),20.)),"carrier body");require(same_rotation(get(component,"CameraOperatorResultGimbalQuatV1"),normalized(axis_angle((0.,1.,0.),-30.))),"carrier gimbal");emit("CARRIER_FRAME_RESULT","PASS")
    else:
        require(not bool(get(component,"CameraOperatorResultValidV1")),"invalid accepted");require(str(get(component,"CameraOperatorFailureCodeV1"))=="validation_failed","invalid code");require(snapshot(component,STATE)==prior_state,"invalid state");require(snapshot(component,RESULT_VALUES)==prior_result,"invalid result");emit("FAIL_CLOSED_RESULT","PASS")
    emit("EXTERNAL_STATE_PRESERVED",True);emit("SCENARIO_RESULT",scenario+":PASS")

def restore(state):
    if state.get("restored") or not state.get("originals"):return
    target=defaults()
    for name,value in state["originals"].items():set_(target,name,clone(value))
    require(all(normalized(get(target,name))==normalized(value) for name,value in state["originals"].items()),"defaults not restored");state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CAMERA_OPERATOR_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    if success:emit("GAME_WORLD_RESULT","PASS")
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_OPERATOR_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"overall timeout")
        if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");target=defaults();state["originals"]={name:clone(get(target,name)) for name in NAMES};stage_case(target,SCENARIOS[0],state["originals"]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
        if state["stage"]=="request":
            if time.monotonic()-state["stage_at"]<.5:return
            subsystem.editor_request_begin_play();state["stage"]="wait";emit("PIE_START_REQUESTED",SCENARIOS[state["scenario_index"]]);return
        if state["stage"]=="wait":
            try:component=director(pie_world());require(component.get_owner().has_actor_begun_play(),"BeginPlay")
            except Exception:return
            state["stage"]="settle";state["stage_at"]=time.monotonic();return
        if state["stage"]=="settle":
            if time.monotonic()-state["stage_at"]<1.:return
            run_scenario(director(pie_world()),SCENARIOS[state["scenario_index"]]);subsystem.editor_request_end_play();state["stage"]="end";return
        if state["stage"]=="end":
            if subsystem.is_in_play_in_editor():return
            state["scenario_index"]+=1
            if state["scenario_index"]==len(SCENARIOS):state["stage"]="complete";finish(True);return
            target=defaults();stage_case(target,SCENARIOS[state["scenario_index"]],state["originals"]);state["stage"]="request";state["stage_at"]=time.monotonic()
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_OPERATOR_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_OPERATOR_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"scenario_index":0,"callback":None,"originals":None,"restored":False};_EDD_CAMERA_OPERATOR_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
