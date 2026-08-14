"""Programmatic three-session PIE acceptance for viewer-local comfort."""
from __future__ import annotations
import json,math,time,traceback
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_COMFORT_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.;SCENARIOS=("disabled_exact","maximum_reduction","fail_closed");ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_viewer_comfort_blueprint_schema.json").read_text(encoding="utf-8"));NAMES=tuple(spec["name"] for spec in SCHEMA["variables"]);INPUT_NAMES=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] in ("input","preference"));AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1");UPSTREAM=("CameraChannelResultValuesV1","CameraLookResultValuesV1","CameraApplyCurrentTargetValuesV1");RESULT_FIELDS=("CameraComfortResultPositionV1","CameraComfortResultGimbalQuatV1","CameraComfortResultChannelValuesV1","CameraComfortResultEffectiveWeightsV1","CameraComfortResultAppliedV1")
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
def roll(degrees):half=math.radians(degrees)*.5;return unreal.Quat(math.sin(half),0.,0.,math.cos(half))
def same_rotation(value,wanted,tolerance=4e-4):
    actual=normalized(value);al=math.sqrt(sum(v*v for v in actual));bl=math.sqrt(sum(v*v for v in wanted));return al>0. and bl>0. and abs(sum(a*b for a,b in zip(actual,wanted))/(al*bl))>=1.-tolerance
def defaults():cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]
CHANNELS=[35.,2.8,1000.,.8,2.,.25,.3,.4,.5,.75,.6,.2,.1]
def stage_case(obj,scenario):
    set_(obj,"CameraComfortInputFrameValidV1",True);set_(obj,"CameraComfortInputPositionV1",unreal.Vector(100.,200.,300.));set_(obj,"CameraComfortInputGimbalQuatV1",roll(40.));set_(obj,"CameraComfortInputProceduralTranslationOffsetV1",unreal.Vector(2.,-4.,6.));set_(obj,"CameraComfortInputProceduralRotationOffsetV1",unreal.Quat(0.,0.,0.,1.));set_(obj,"CameraComfortInputChannelValuesV1",CHANNELS)
    if scenario=="disabled_exact":enabled=False;weights=(0.,0.,0.,0.,0.)
    elif scenario=="maximum_reduction":enabled=True;weights=(0.,0.,0.,0.,0.)
    elif scenario=="fail_closed":enabled=True;weights=(1.,1.,1.,1.,1.);set_(obj,"CameraComfortInputFrameValidV1",False);set_(obj,"CameraComfortResultPositionV1",unreal.Vector(9.,8.,7.));set_(obj,"CameraComfortResultGimbalQuatV1",unreal.Quat(0.,0.,0.,1.));set_(obj,"CameraComfortResultChannelValuesV1",[8.]*13);set_(obj,"CameraComfortResultEffectiveWeightsV1",[.5]*5);set_(obj,"CameraComfortResultAppliedV1",True)
    else:raise RuntimeError("unknown scenario:"+scenario)
    set_(obj,"CameraComfortEnabledV1",enabled)
    for name,value in zip(("CameraComfortRollWeightV1","CameraComfortShakeWeightV1","CameraComfortBlurWeightV1","CameraComfortExposureChangeWeightV1","CameraComfortChromaticAberrationWeightV1"),weights):set_(obj,name,value)
def run_scenario(component,scenario):
    before_inputs=tuple(normalized(get(component,name)) for name in INPUT_NAMES);before_owned=tuple(normalized(get(component,name)) for name in AUTHORSHIP+UPSTREAM);prior=tuple(normalized(get(component,name)) for name in RESULT_FIELDS);component.call_method("ApplyCameraViewerComfortV1");require(tuple(normalized(get(component,name)) for name in INPUT_NAMES)==before_inputs,"inputs mutated");require(tuple(normalized(get(component,name)) for name in AUTHORSHIP+UPSTREAM)==before_owned,"upstream/body/gimbal mutated")
    if scenario=="disabled_exact":require(bool(get(component,"CameraComfortResultValidV1")),"disabled invalid");require(normalized(get(component,"CameraComfortResultPositionV1"))==(102.,196.,306.),"disabled position");require(same_rotation(get(component,"CameraComfortResultGimbalQuatV1"),normalized(roll(40.))),"disabled gimbal");require(tuple(float(v) for v in get(component,"CameraComfortResultChannelValuesV1"))==tuple(CHANNELS),"disabled channels");require(tuple(float(v) for v in get(component,"CameraComfortResultEffectiveWeightsV1"))==(1.,1.,1.,1.,1.),"disabled weights");require(not bool(get(component,"CameraComfortResultAppliedV1")),"disabled applied");emit("COMFORT_RESULT","disabled_exact:PASS")
    elif scenario=="maximum_reduction":values=tuple(float(v) for v in get(component,"CameraComfortResultChannelValuesV1"));require(bool(get(component,"CameraComfortResultValidV1")),"maximum invalid");require(normalized(get(component,"CameraComfortResultPositionV1"))==(100.,200.,300.),"maximum position");require(same_rotation(get(component,"CameraComfortResultGimbalQuatV1"),(0.,0.,0.,1.)),"maximum gimbal");require(all(abs(values[index])<1e-6 for index in (3,4,9,10)),"maximum channels");require(tuple(float(v) for v in get(component,"CameraComfortResultEffectiveWeightsV1"))==(0.,0.,0.,0.,0.),"maximum weights");require(bool(get(component,"CameraComfortResultAppliedV1")),"maximum not applied");emit("COMFORT_RESULT","maximum_reduction:PASS")
    else:require(not bool(get(component,"CameraComfortResultValidV1")),"invalid accepted");require(tuple(normalized(get(component,name)) for name in RESULT_FIELDS)==prior,"invalid overwrote snapshot");emit("FAIL_CLOSED_RESULT","PASS")
    emit("BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("SCENARIO_RESULT",scenario+":PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"):return
    target=defaults()
    for name,value in state["originals"].items():set_(target,name,clone(value))
    require(all(normalized(get(target,name))==normalized(value) for name,value in state["originals"].items()),"defaults not restored");state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CAMERA_COMFORT_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    if success:emit("GAME_WORLD_RESULT","PASS")
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_COMFORT_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"overall timeout")
        if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");target=defaults();state["originals"]={name:clone(get(target,name)) for name in NAMES};stage_case(target,SCENARIOS[0]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
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
            target=defaults();stage_case(target,SCENARIOS[state["scenario_index"]]);state["stage"]="request";state["stage_at"]=time.monotonic()
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_COMFORT_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_COMFORT_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"scenario_index":0,"callback":None,"originals":None,"restored":False};_EDD_CAMERA_COMFORT_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
