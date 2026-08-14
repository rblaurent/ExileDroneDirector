"""Programmatic multi-session PIE acceptance for the saved dolly-zoom helper."""
from __future__ import annotations
import json,time,traceback
from pathlib import Path
import unreal

PREFIX="EDD_CAMERA_DOLLY_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.0;SCENARIOS=("shrinking","expanding","fail_closed");ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_dolly_zoom_blueprint_schema.json").read_text(encoding="utf-8"));NAMES=tuple(spec["name"] for spec in SCHEMA["variables"]);INPUT_NAMES=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"]=="input");AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1")
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
def close(left,right):return abs(float(left)-float(right))<=3e-4*max(1.0,abs(float(left)),abs(float(right)))
def defaults():cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):
    controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]
def stage_case(obj,scenario):
    if scenario=="shrinking":positions=((0,0,0),(1000,0,0),(1500,0,0));reference=1;focal=50.0
    elif scenario=="expanding":positions=((1500,0,0),(1000,0,0),(0,0,0));reference=1;focal=50.0
    elif scenario=="fail_closed":positions=((1,0,0),(1001,0,0));reference=0;focal=1000.0
    else:raise RuntimeError("unknown scenario:"+scenario)
    set_(obj,"CameraDollyInputTimesSecondsV1",[0.0,.5,1.0] if scenario!="fail_closed" else [0.0,1.0]);set_(obj,"CameraDollyInputCameraPositionsV1",[vector(value) for value in positions]);set_(obj,"CameraDollyInputSubjectPositionV1",vector((2000,0,0) if scenario!="fail_closed" else (0,0,0)));set_(obj,"CameraDollyInputReferenceSampleIndexV1",reference);set_(obj,"CameraDollyInputReferenceFocalLengthMmV1",focal)
    if scenario=="fail_closed":set_(obj,"CameraDollyCompiledTimesSecondsV1",[10.0,11.0]);set_(obj,"CameraDollyCompiledSubjectDistancesCmV1",[333.0,444.0]);set_(obj,"CameraDollyCompiledFocalLengthsMmV1",[33.0,44.0]);set_(obj,"CameraDollyCompiledReferenceDistanceCmV1",333.0)
def input_snapshot(obj):return tuple(normalized(get(obj,name)) for name in INPUT_NAMES)
def authorship_snapshot(obj):return tuple(normalized(get(obj,name)) for name in AUTHORSHIP)
def run_scenario(component,scenario):
    before_inputs=input_snapshot(component);before_authorship=authorship_snapshot(component)
    if scenario in ("shrinking","expanding"):
        component.call_method("CompileCameraDollyZoomV1");require(input_snapshot(component)==before_inputs,"inputs mutated");require(authorship_snapshot(component)==before_authorship,"body/gimbal mutated");require(bool(get(component,"CameraDollyCompileValidV1")),"compile");actual=tuple(float(value) for value in get(component,"CameraDollyCompiledFocalLengthsMmV1"));wanted=(100.0,50.0,25.0) if scenario=="shrinking" else (25.0,50.0,100.0);require(len(actual)==3 and all(close(a,b) for a,b in zip(actual,wanted)),f"{scenario}:{actual}");emit("FOCAL_RESULT",scenario+":"+str(actual))
    elif scenario=="fail_closed":
        prior=tuple(normalized(get(component,name)) for name in ("CameraDollyCompiledTimesSecondsV1","CameraDollyCompiledSubjectDistancesCmV1","CameraDollyCompiledFocalLengthsMmV1","CameraDollyCompiledReferenceDistanceCmV1"));component.call_method("CompileCameraDollyZoomV1");require(not bool(get(component,"CameraDollyCompileValidV1")),"invalid accepted");require(tuple(normalized(get(component,name)) for name in ("CameraDollyCompiledTimesSecondsV1","CameraDollyCompiledSubjectDistancesCmV1","CameraDollyCompiledFocalLengthsMmV1","CameraDollyCompiledReferenceDistanceCmV1"))==prior,"invalid overwrote snapshot");require(authorship_snapshot(component)==before_authorship,"failure mutated body/gimbal");emit("FAIL_CLOSED_RESULT","PASS")
    emit("SCENARIO_RESULT",scenario+":PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"):return
    target=defaults()
    for name,value in state["originals"].items():set_(target,name,clone(value))
    require(all(normalized(get(target,name))==normalized(value) for name,value in state["originals"].items()),"current class defaults not restored");state["defaults"]=target;state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CAMERA_DOLLY_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    if success:emit("GAME_WORLD_RESULT","PASS")
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_DOLLY_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"overall timeout")
        if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");state["defaults"]=defaults();state["originals"]={name:clone(get(state["defaults"],name)) for name in NAMES};stage_case(state["defaults"],SCENARIOS[state["scenario_index"]]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
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
            state["defaults"]=defaults();stage_case(state["defaults"],SCENARIOS[state["scenario_index"]]);state["stage"]="request";state["stage_at"]=time.monotonic()
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_DOLLY_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_DOLLY_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"scenario_index":0,"callback":None,"defaults":None,"originals":None,"restored":False};_EDD_CAMERA_DOLLY_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
