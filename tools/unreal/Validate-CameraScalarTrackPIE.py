"""Programmatic PIE acceptance for the saved camera scalar-track engine."""
from __future__ import annotations

import time
import traceback

import unreal


PREFIX="EDD_CAMERA_SCALAR_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.0
INPUTS=("CameraScalarTrackInputDurationV1","CameraScalarTrackInputKeyTimesV1","CameraScalarTrackInputKeyValuesV1","CameraScalarTrackInputInterpolationModesV1","CameraScalarTrackInputArriveTangentsV1","CameraScalarTrackInputLeaveTangentsV1","CameraScalarTrackInputDomainV1","CameraScalarTrackInputHasMinimumV1","CameraScalarTrackInputMinimumV1","CameraScalarTrackInputHasMaximumV1","CameraScalarTrackInputMaximumV1","CameraScalarTrackInputClampOutputV1","CameraScalarTrackQueryTimeV1")
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
def clone(value):return list(value) if isinstance(value,(list,tuple)) else value
def close(left,right):return abs(float(left)-float(right))<=3e-4*max(1.0,abs(float(left)),abs(float(right)))
def defaults():
    cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():
    value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):
    controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]
def stage(obj):
    set_(obj,"CameraScalarTrackInputDurationV1",2.0);set_(obj,"CameraScalarTrackInputKeyTimesV1",[0.0,2.0]);set_(obj,"CameraScalarTrackInputKeyValuesV1",[100.0,400.0]);set_(obj,"CameraScalarTrackInputInterpolationModesV1",["linear"]);set_(obj,"CameraScalarTrackInputArriveTangentsV1",[0.0,0.0]);set_(obj,"CameraScalarTrackInputLeaveTangentsV1",[0.0,0.0]);set_(obj,"CameraScalarTrackInputDomainV1","reciprocal");set_(obj,"CameraScalarTrackInputHasMinimumV1",True);set_(obj,"CameraScalarTrackInputMinimumV1",1.0);set_(obj,"CameraScalarTrackInputHasMaximumV1",False);set_(obj,"CameraScalarTrackInputMaximumV1",0.0);set_(obj,"CameraScalarTrackInputClampOutputV1",False);set_(obj,"CameraScalarTrackQueryTimeV1",1.0)
def run_checks():
    component=director(pie_world());before=tuple(clone(get(component,name)) for name in INPUTS);component.call_method("CompileCameraScalarTrackV1");require(bool(get(component,"CameraScalarTrackCompileValidV1")),"compile");component.call_method("EvaluateCameraScalarTrackV1");require(bool(get(component,"CameraScalarTrackResultValidV1")),"evaluate");require(close(get(component,"CameraScalarTrackResultValueV1"),160.0),"optical midpoint");require(int(get(component,"CameraScalarTrackResultSegmentIndexV1"))==0,"segment");require(close(get(component,"CameraScalarTrackResultLocalAlphaV1"),.5),"alpha");require(tuple(clone(get(component,name)) for name in INPUTS)==before,"inputs mutated");emit("OPTICAL_MIDPOINT",get(component,"CameraScalarTrackResultValueV1"));emit("GAME_WORLD_RESULT","PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"):return
    for name,value in state["originals"].items():set_(state["defaults"],name,clone(value))
    state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CAMERA_SCALAR_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_SCALAR_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if state["stage"]=="prepare":
            require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");state["defaults"]=defaults();state["originals"]={name:clone(get(state["defaults"],name)) for name in INPUTS};stage(state["defaults"]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
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
old=globals().get("_EDD_CAMERA_SCALAR_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_SCALAR_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"callback":None,"defaults":None,"originals":None,"restored":False}
_EDD_CAMERA_SCALAR_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
