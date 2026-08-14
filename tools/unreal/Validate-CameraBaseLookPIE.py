"""Programmatic multi-session PIE acceptance for the saved named-look helper."""
from __future__ import annotations
import json,time,traceback
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_LOOK_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.0;SCENARIOS=("raw","authored_override","fail_closed");ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_base_look_blueprint_schema.json").read_text(encoding="utf-8"));NAMES=tuple(spec["name"] for spec in SCHEMA["variables"]);INPUT_NAMES=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"]=="input");AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1");RESULT_FIELDS=("CameraLookResultPresetIdV1","CameraLookResultChannelIdsV1","CameraLookResultBaseValuesV1","CameraLookResultValuesV1","CameraLookResultOverrideMaskV1")
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
def defaults():cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]
def stage_case(obj,scenario):
    if scenario=="raw":preset="raw";ids=[];values=[]
    elif scenario=="authored_override":preset="dreamy_shallow_focus";ids=["focal_length_mm","exposure_ev"];values=[105.0,-.75]
    elif scenario=="fail_closed":preset="unknown";ids=[];values=[];set_(obj,"CameraLookResultPresetIdV1","prior");set_(obj,"CameraLookResultChannelIdsV1",["prior"]);set_(obj,"CameraLookResultBaseValuesV1",[9.0]);set_(obj,"CameraLookResultValuesV1",[8.0]);set_(obj,"CameraLookResultOverrideMaskV1",[True])
    else:raise RuntimeError("unknown scenario:"+scenario)
    set_(obj,"CameraLookInputPresetIdV1",preset);set_(obj,"CameraLookInputAuthoredChannelIdsV1",ids);set_(obj,"CameraLookInputAuthoredValuesV1",values)
def run_scenario(component,scenario):
    before_inputs=tuple(normalized(get(component,name)) for name in INPUT_NAMES);before_authorship=tuple(normalized(get(component,name)) for name in AUTHORSHIP);prior=tuple(normalized(get(component,name)) for name in RESULT_FIELDS);component.call_method("ComposeCameraLookV1");require(tuple(normalized(get(component,name)) for name in INPUT_NAMES)==before_inputs,"inputs mutated");require(tuple(normalized(get(component,name)) for name in AUTHORSHIP)==before_authorship,"body/gimbal mutated")
    if scenario=="raw":require(bool(get(component,"CameraLookResultValidV1")),"raw invalid");require(tuple(float(v) for v in get(component,"CameraLookResultValuesV1"))==(35.0,2.8,1000.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0),"raw values");emit("LOOK_RESULT","raw:PASS")
    elif scenario=="authored_override":require(bool(get(component,"CameraLookResultValidV1")),"override invalid");values=tuple(float(v) for v in get(component,"CameraLookResultValuesV1"));mask=tuple(bool(v) for v in get(component,"CameraLookResultOverrideMaskV1"));require(values[0]==105.0 and values[4]==-.75 and mask[0] and mask[4] and sum(mask)==2,"override result");emit("LOOK_RESULT","authored_override:PASS")
    else:require(not bool(get(component,"CameraLookResultValidV1")),"invalid accepted");require(tuple(normalized(get(component,name)) for name in RESULT_FIELDS)==prior,"invalid overwrote snapshot");emit("FAIL_CLOSED_RESULT","PASS")
    emit("SCENARIO_RESULT",scenario+":PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"):return
    target=defaults()
    for name,value in state["originals"].items():set_(target,name,clone(value))
    require(all(normalized(get(target,name))==normalized(value) for name,value in state["originals"].items()),"defaults not restored");state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CAMERA_LOOK_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    if success:emit("GAME_WORLD_RESULT","PASS")
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_LOOK_PIE_STATE"]
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
            if time.monotonic()-state["stage_at"]<1.0:return
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
old=globals().get("_EDD_CAMERA_LOOK_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_LOOK_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"scenario_index":0,"callback":None,"originals":None,"restored":False};_EDD_CAMERA_LOOK_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
