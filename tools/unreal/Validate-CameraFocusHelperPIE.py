"""Programmatic PIE acceptance for the saved camera-focus helper."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import unreal


PREFIX="EDD_CAMERA_FOCUS_PIE"; SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty"; WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"; CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"; TIMEOUT_SECONDS=120.0
ROOT=Path(__file__).resolve().parents[2]; SCHEMA=json.loads((ROOT/"tools/trajectory/camera_focus_helper_blueprint_schema.json").read_text(encoding="utf-8")); NAMES=tuple(spec["name"] for spec in SCHEMA["variables"])
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
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
    if isinstance(value,(list,tuple)):return tuple(normalized(item) for item in value)
    return value
def close(left,right):return abs(float(left)-float(right))<=3e-4*max(1.0,abs(float(left)),abs(float(right)))
def defaults():
    cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():
    value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):
    controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]
def stage(obj):
    set_(obj,"CameraFocusInputModeV1","rack_fixed");set_(obj,"CameraFocusInputDomainV1","reciprocal");set_(obj,"CameraFocusInputFixedStepSecondsV1",.25);set_(obj,"CameraFocusInputTimesSecondsV1",[0.0,.25,.5]);set_(obj,"CameraFocusInputCameraPositionsV1",[vector((0,0,0)) for _ in range(3)]);set_(obj,"CameraFocusInputManualDistancesCmV1",[]);set_(obj,"CameraFocusInputTargetPositionsV1",[]);set_(obj,"CameraFocusInputRackTargetAV1",vector((100,0,0)));set_(obj,"CameraFocusInputRackTargetBV1",vector((400,0,0)));set_(obj,"CameraFocusInputRackBlendWeightsV1",[0.0,.5,1.0]);set_(obj,"CameraFocusInputSmoothingResponseSecondsV1",0.0)
def input_snapshot(obj):return tuple(normalized(get(obj,name)) for name in NAMES if next(spec for spec in SCHEMA["variables"] if spec["name"]==name)["role"]=="input")
def run_checks():
    component=director(pie_world());before=input_snapshot(component);component.call_method("CompileCameraFocusDistanceChannelV1");require(input_snapshot(component)==before,"inputs mutated");require(bool(get(component,"CameraFocusCompileValidV1")),"compile");actual=tuple(float(value) for value in get(component,"CameraFocusCompiledDistancesCmV1"));require(len(actual)==3 and close(actual[0],100.0) and close(actual[1],160.0) and close(actual[2],400.0),f"reciprocal rack:{actual}")
    set_(component,"CameraFocusMarkerValidV1",True);set_(component,"CameraFocusMarkerPositionV1",vector((1,2,3)));set_(component,"CameraFocusMarkerRevisionV1",8);set_(component,"CameraFocusTraceHitValidV1",False);set_(component,"CameraFocusTraceHitPositionV1",vector((900,900,900)));component.call_method("SetCameraFocusHereV1");require(normalized(get(component,"CameraFocusMarkerPositionV1"))==(1.0,2.0,3.0) and int(get(component,"CameraFocusMarkerRevisionV1"))==8,"PIE miss mutation");set_(component,"CameraFocusTraceHitValidV1",True);set_(component,"CameraFocusTraceHitPositionV1",vector((7,8,9)));component.call_method("SetCameraFocusHereV1");require(normalized(get(component,"CameraFocusMarkerPositionV1"))==(7.0,8.0,9.0) and int(get(component,"CameraFocusMarkerRevisionV1"))==9,"PIE hit")
    prior_times=list(get(component,"CameraFocusCompiledTimesSecondsV1"));prior_distances=list(get(component,"CameraFocusCompiledDistancesCmV1"));set_(component,"CameraFocusInputModeV1","rack_fixed");set_(component,"CameraFocusInputRackBlendWeightsV1",[0.0,1.25,1.0]);component.call_method("CompileCameraFocusDistanceChannelV1");require(not bool(get(component,"CameraFocusCompileValidV1")),"invalid rack accepted");require(list(get(component,"CameraFocusCompiledTimesSecondsV1"))==prior_times and list(get(component,"CameraFocusCompiledDistancesCmV1"))==prior_distances,"invalid rack overwrote snapshot");emit("RECIPROCAL_MIDPOINT",actual[1]);emit("SET_HERE_RESULT","PASS");emit("FAIL_CLOSED_RESULT","PASS");emit("GAME_WORLD_RESULT","PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"):return
    for name,value in state["originals"].items():set_(state["defaults"],name,clone(value))
    state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CAMERA_FOCUS_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_FOCUS_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if state["stage"]=="prepare":
            require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");state["defaults"]=defaults();state["originals"]={name:clone(get(state["defaults"],name)) for name in NAMES};stage(state["defaults"]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
        if state["stage"]=="request":
            if time.monotonic()-state["stage_at"]<.5:return
            subsystem.editor_request_begin_play();state["stage"]="wait";emit("PIE_START_REQUESTED",True);return
        if state["stage"]=="wait":
            try:component=director(pie_world());require(component.get_owner().has_actor_begun_play(),"BeginPlay")
            except Exception:require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"startup timeout");return
            state["stage"]="settle";state["stage_at"]=time.monotonic();return
        if state["stage"]=="settle":
            if time.monotonic()-state["stage_at"]<1.0:return
            run_checks();subsystem.editor_request_end_play();state["stage"]="end";return
        if state["stage"]=="end":
            if subsystem.is_in_play_in_editor():require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"teardown timeout");return
            state["stage"]="complete";finish(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_FOCUS_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_FOCUS_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"callback":None,"defaults":None,"originals":None,"restored":False}
_EDD_CAMERA_FOCUS_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
