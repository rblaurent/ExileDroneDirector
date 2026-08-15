"""Automatic player-owned PIE acceptance for playback-native application."""
from __future__ import annotations
import sys,time,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"tools/unreal"));import camera_playback_native_application_acceptance_common as common
PREFIX="EDD_CAMERA_PLAYBACK_NATIVE_PIE";SOURCE="/Game/Dev/AlmostEmpty";WORLD="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";DIRECTOR_CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT=120.;SCENARIOS=("success","engine_rollback","pose_rejection")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(value,message):
 if not value:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def struct_text(value):
 exporter=getattr(value,"export_text",None);return exporter() if callable(exporter) else str(value)
def defaults():
 cls=unreal.load_class(None,DIRECTOR_CLASS);require(cls is not None,"class");return unreal.get_default_object(cls)
def world():value=unreal.find_object(None,WORLD);require(value is not None,"world");return value
def director():
 controller=unreal.GameplayStatics.get_player_controller(world(),0);require(controller is not None,"controller");cls=unreal.load_class(None,DIRECTOR_CLASS);items=controller.get_components_by_class(cls);require(len(items)==1,f"director:{len(items)}");return items[0]
def camera(obj):
 actor=common.get(obj,"DroneCameraRef");require(actor is not None,"drone");items=actor.get_components_by_class(unreal.CineCameraComponent);require(len(items)==1,f"camera:{len(items)}");return actor,items[0]
def pose(actor,component):return common.norm(actor.get_actor_transform()),common.norm(component.get_relative_transform())
def engine(component):return (struct_text(common.get(component,"filmback")),float(common.get(component,"current_focal_length")),float(common.get(component,"current_aperture")),struct_text(common.get(component,"focus_settings")),struct_text(common.get(component,"post_process_settings")))
def assert_engine(component):
 film=common.get(component,"filmback");focus=common.get(component,"focus_settings");post=common.get(component,"post_process_settings");values=common.CHANNELS
 actual=(common.get(film,"sensor_width"),common.get(film,"sensor_height"),common.get(component,"current_focal_length"),common.get(component,"current_aperture"),common.get(focus,"manual_focus_distance"),common.get(post,"auto_exposure_bias"),common.get(post,"bloom_intensity"),common.get(post,"vignette_intensity"),common.get(post,"motion_blur_amount"),common.get(post,"scene_fringe_intensity"));expected=(36.,24.,values[0],values[1],values[2],values[4],values[5],values[6],values[9],values[10]);require(all(common.close(a,b,4e-4) for a,b in zip(actual,expected)),f"engine:{actual}")
def assert_success_pose(actor,component,baseline):
 actor_now,component_now=pose(actor,component);actor_base,component_base=baseline
 require(common.vector_close(actor_now[0],common.POSITION),f"actor-position:{actor_now[0]}");require(common.quat_close(actor_now[1],common.BODY),f"actor-body:{actor_now[1]}");require(actor_now[2]==actor_base[2],"actor-scale")
 require(component_now[0]==component_base[0],"component-translation");require(common.quat_close(component_now[1],common.RELATIVE),f"component-gimbal:{component_now[1]}");require(component_now[2]==component_base[2],"component-scale")
def checks(index):
 obj=director();scenario=SCENARIOS[index]
 if bool(common.get(obj,"DroneModeActive")):obj.call_method("ExitDroneMode")
 obj.call_method("EnterDroneMode");actor,component=camera(obj);baseline_pose=pose(actor,component);baseline_engine=engine(component);source=common.snapshot(obj,tuple(name for name in common.NAMES if name.startswith("CameraPlaybackResult")))
 obj.call_method("ApplyComposedCameraPlaybackFrameV1")
 if scenario=="success":
  require(bool(common.get(obj,"CameraPlaybackNativeResultValidV1")),f"success:{common.get(obj,'CameraPlaybackNativeFailureCodeV1')}");require(bool(common.get(obj,"CameraPlaybackNativeSessionActiveV1")),"success-session");require(int(common.get(obj,"CameraPlaybackNativeAppliedFrameCountV1"))==1,"count-1");assert_success_pose(actor,component,baseline_pose);assert_engine(component)
  captured=(common.norm(common.get(obj,"CameraPlaybackNativeBaselineActorTransformV1")),common.norm(common.get(obj,"CameraPlaybackNativeBaselineComponentRelativeTransformV1")));require(captured==baseline_pose,"verbatim-baselines")
  obj.call_method("ApplyComposedCameraPlaybackFrameV1");require(bool(common.get(obj,"CameraPlaybackNativeResultValidV1")),"repeat-result");require(int(common.get(obj,"CameraPlaybackNativeAppliedFrameCountV1"))==2,"count-2");require((common.norm(common.get(obj,"CameraPlaybackNativeBaselineActorTransformV1")),common.norm(common.get(obj,"CameraPlaybackNativeBaselineComponentRelativeTransformV1")))==captured,"repeat-capture-drift")
  obj.call_method("RestoreCameraPlaybackNativeStateV1");require(pose(actor,component)==baseline_pose,"success-pose-restore");require(engine(component)==baseline_engine,"success-engine-restore");require(not bool(common.get(obj,"CameraPlaybackNativeSessionActiveV1")),"success-active-after-restore");obj.call_method("RestoreCameraPlaybackNativeStateV1");require(pose(actor,component)==baseline_pose and engine(component)==baseline_engine,"repeat-restore")
  emit("SUCCESS_FRAME","repeat_apply_and_exact_restore")
 else:
  require(not bool(common.get(obj,"CameraPlaybackNativeResultValidV1")),scenario+":accepted");require(not bool(common.get(obj,"CameraPlaybackNativeSessionActiveV1")),scenario+":active");require(pose(actor,component)==baseline_pose,scenario+":pose-write");require(engine(component)==baseline_engine,scenario+":engine-write");require(int(common.get(obj,"CameraPlaybackNativeAppliedFrameCountV1"))==0,scenario+":count")
  wanted="native_apply_failed" if scenario=="engine_rollback" else "native_preflight_failed";require(str(common.get(obj,"CameraPlaybackNativeFailureCodeV1"))==wanted,scenario+":diagnostic");emit("FAILURE_SCENARIO",scenario+"|exact_zero_or_rollback=true")
 require(common.snapshot(obj,tuple(name for name in common.NAMES if name.startswith("CameraPlaybackResult")))==source,scenario+":source-mutated")
 obj.call_method("ExitDroneMode");require(not bool(common.get(obj,"DroneModeActive")),scenario+":exit")
def restore_defaults(state):
 if state.get("restored") or not state.get("originals"):return
 for name,value in state["originals"].items():common.set_(state["defaults"],name,common.clone(value))
 state["restored"]=True;emit("DEFAULTS_RESTORED",all(common.norm(common.get(state["defaults"],name))==common.norm(value) for name,value in state["originals"].items()))
def finish(success):
 state=globals().get("_EDD_CAMERA_PLAYBACK_NATIVE_PIE_STATE");restore_defaults(state)
 if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
 if success:emit("PLAYER_OWNED_DIRECTOR",True);emit("DISTINCT_ACTOR_COMPONENT_AUTHORSHIP",True);emit("ENGINE_FAILURE_EXACT_ROLLBACK",True);emit("POSE_REJECTION_ZERO_WRITE",True);emit("GAME_WORLD_RESULT","PASS")
 emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def arm(state):common.stage_result(state["defaults"],SCENARIOS[state["scenario"]]);state["stage"]="request";state["at"]=time.monotonic();emit("SCENARIO_ARMED",SCENARIOS[state["scenario"]])
def tick(_delta):
 state=globals()["_EDD_CAMERA_PLAYBACK_NATIVE_PIE_STATE"]
 try:
  subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
  if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"already-PIE");require(subsystem.load_level(SOURCE),"load");state["defaults"]=defaults();state["originals"]={name:common.clone(common.get(state["defaults"],name)) for name in common.NAMES};arm(state);emit("SOURCE_LEVEL_READY",SOURCE);return
  if state["stage"]=="request":
   if time.monotonic()-state["at"]<.5:return
   subsystem.editor_request_begin_play();state["stage"]="wait";state["at"]=time.monotonic();emit("PIE_START_REQUESTED",SCENARIOS[state["scenario"]]);return
  if state["stage"]=="wait":
   try:component=director();require(component.get_owner().has_actor_begun_play(),"BeginPlay")
   except Exception:require(time.monotonic()-state["at"]<TIMEOUT,"startup-timeout");return
   state["stage"]="settle";state["at"]=time.monotonic();return
  if state["stage"]=="settle":
   if time.monotonic()-state["at"]<1.:return
   checks(state["scenario"]);subsystem.editor_request_end_play();state["stage"]="end";state["at"]=time.monotonic();return
  if state["stage"]=="end":
   if subsystem.is_in_play_in_editor():require(time.monotonic()-state["at"]<TIMEOUT,"teardown-timeout");return
   state["scenario"]+=1
   if state["scenario"]<len(SCENARIOS):arm(state)
   else:state["stage"]="complete";finish(True)
 except Exception as error:
  unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
  try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
  finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_PLAYBACK_NATIVE_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_PLAYBACK_NATIVE_PIE_STATE={"stage":"prepare","scenario":0,"at":time.monotonic(),"callback":None,"defaults":None,"originals":None,"restored":False};_EDD_CAMERA_PLAYBACK_NATIVE_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
