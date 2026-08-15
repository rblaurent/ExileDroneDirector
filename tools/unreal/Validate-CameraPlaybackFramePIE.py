"""Programmatic player-owned PIE acceptance for complete playback composition."""
from __future__ import annotations
import math,sys,time,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"tools/unreal"));import camera_playback_acceptance_common as common
PREFIX="EDD_CAMERA_PLAYBACK_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.;SCENARIOS=("mid_frame","complete_frame","fail_closed");COMPILED=("PositionRouteCompiledWaypointPositionsV1","OrientationTrackCompiledAlignedQuatsV1","AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","CarrierFrameCompiledQuatsV1","CameraChannelCompiledDomainValuesV1")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(value,message):
 if not value:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def close(a,b,tol=1e-3):return abs(float(a)-float(b))<=tol*max(1.,abs(float(a)),abs(float(b)))
def quat_close(a,b,tol=1e-6):return all(close(x,y,tol) for x,y in zip(a,b)) or all(close(x,-y,tol) for x,y in zip(a,b))
def mul(a,b):ax,ay,az,aw=a;bx,by,bz,bw=b;return aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz
def defaults():cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]
def stage_case(obj,scenario,originals):
 for name,value in originals.items():common.set_(obj,name,common.clone(value))
 common.stage_and_compile(obj);common.set_(obj,"CameraPlaybackInputElapsedSecondsV1",.5 if scenario!="complete_frame" else 2.)
 if scenario=="fail_closed":common.set_(obj,"AirframePrebakeCompileValidV1",False)
def run_scenario(component,scenario):
 compiled=common.snapshot(component,COMPILED);component.call_method("ComposeCameraPlaybackFrameV1");require(common.snapshot(component,COMPILED)==compiled,"compiled sources mutated")
 if scenario=="fail_closed":require(not bool(common.get(component,"CameraPlaybackResultValidV1")),"invalid source accepted");emit("FAIL_CLOSED_RESULT","PASS")
 else:
  require(bool(common.get(component,"CameraPlaybackResultValidV1")),"frame invalid");wanted_x=50. if scenario=="mid_frame" else 100.;require(close(common.norm(common.get(component,"CameraPlaybackResultPositionV1"))[0],wanted_x),"position");require(bool(common.get(component,"CameraPlaybackResultCompleteV1"))==(scenario=="complete_frame"),"completion");body=common.norm(common.get(component,"CameraPlaybackResultBodyWorldQuatV1"));gimbal=common.norm(common.get(component,"CameraPlaybackResultGimbalWorldQuatV1"));relative=common.norm(common.get(component,"CameraPlaybackResultGimbalRelativeQuatV1"));require(quat_close(body,common.norm(common.BODY)) and quat_close(gimbal,common.norm(common.GIMBAL)),"distinct authorship");require(quat_close(mul(body,relative),gimbal),"relative reconstruction");require(len(common.get(component,"CameraPlaybackResultChannelValuesV1"))==13,"channels");emit("MID_FRAME_RESULT" if scenario=="mid_frame" else "COMPLETE_FRAME_RESULT","PASS")
 emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("SCENARIO_RESULT",scenario+":PASS")
def restore(state):
 if state.get("restored") or not state.get("originals"):return
 target=defaults()
 for name,value in state["originals"].items():common.set_(target,name,common.clone(value))
 require(all(common.norm(common.get(target,name))==common.norm(value) for name,value in state["originals"].items()),"defaults not restored");state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
 state=globals().get("_EDD_CAMERA_PLAYBACK_PIE_STATE");restore(state)
 if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
 if success:emit("GAME_WORLD_RESULT","PASS")
 emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
 state=globals()["_EDD_CAMERA_PLAYBACK_PIE_STATE"]
 try:
  subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"overall timeout")
  if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");target=defaults();state["originals"]={name:common.clone(common.get(target,name)) for name in common.NAMES};stage_case(target,SCENARIOS[0],state["originals"]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
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
old=globals().get("_EDD_CAMERA_PLAYBACK_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_PLAYBACK_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"scenario_index":0,"callback":None,"originals":None,"restored":False};_EDD_CAMERA_PLAYBACK_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
