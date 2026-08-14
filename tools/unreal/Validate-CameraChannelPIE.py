"""Programmatic real-world PIE acceptance for the camera channel assembly."""
from __future__ import annotations
import json,time,traceback
from pathlib import Path
import unreal
PREFIX="EDD_CAMERA_CHANNEL_PIE";SOURCE="/Game/Dev/AlmostEmpty";WORLD="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_channel_assembly_blueprint_schema.json").read_text(encoding="utf-8"));SCALAR=json.loads((ROOT/"tools/trajectory/camera_scalar_track_blueprint_schema.json").read_text(encoding="utf-8"));NAMES=tuple(dict.fromkeys(spec["name"] for spec in (*SCHEMA["variables"],*SCALAR["variables"])));INPUTS=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] in ("input","query"));TIMEOUT=120.0
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(value,message):
 if not value:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
 for candidate in variants(name):
  try:return obj.get_editor_property(candidate)
  except Exception:pass
 raise RuntimeError("missing:"+name)
def set_(obj,name,value):
 for candidate in variants(name):
  try:obj.set_editor_property(candidate,value);return
  except Exception:pass
 raise RuntimeError("cannot set:"+name)
def clone(value):return list(value) if isinstance(value,(list,tuple)) else value
def norm(value):return tuple(value) if isinstance(value,(list,tuple)) else value
def close(a,b):return abs(float(a)-float(b))<=4e-4*max(1.0,abs(float(a)),abs(float(b)))
def defaults():
 cls=unreal.load_class(None,CLASS);require(cls is not None,"class");return unreal.get_default_object(cls)
def world():value=unreal.find_object(None,WORLD);require(value is not None,"world");return value
def director():controller=unreal.GameplayStatics.get_player_controller(world(),0);require(controller is not None,"controller");cls=unreal.load_class(None,CLASS);items=controller.get_components_by_class(cls);require(len(items)==1,f"director:{len(items)}");return items[0]
def stage(obj):
 values=(("CameraChannelInputDurationV1",2.0),("CameraChannelInputFilmbackPresetIdV1","pie_full_frame"),("CameraChannelInputFilmbackSensorWidthMmV1",36.0),("CameraChannelInputFilmbackSensorHeightMmV1",24.0),("CameraChannelInputChannelIdsV1",["focus_distance_cm","bloom_weight","motion_blur_weight"]),("CameraChannelInputKeyOffsetsV1",[0,2,4]),("CameraChannelInputKeyCountsV1",[2,2,2]),("CameraChannelInputKeyTimesV1",[0.0,2.0,0.0,2.0,0.0,2.0]),("CameraChannelInputKeyValuesV1",[100.0,400.0,.2,.8,.1,.3]),("CameraChannelInputInterpolationModesV1",["linear","linear","linear"]),("CameraChannelInputArriveTangentsV1",[0.0]*6),("CameraChannelInputLeaveTangentsV1",[0.0]*6),("CameraChannelInputDomainsV1",["reciprocal","linear","linear"]),("CameraChannelQueryTimeV1",1.0))
 for name,value in values:set_(obj,name,value)
def checks():
 obj=director();before=tuple(norm(get(obj,name)) for name in INPUTS);obj.call_method("CompileCameraChannelAssemblyV1");require(bool(get(obj,"CameraChannelCompileValidV1")),"compile");obj.call_method("EvaluateCameraChannelAssemblyV1");require(bool(get(obj,"CameraChannelResultValidV1")),"evaluate");result=tuple(get(obj,"CameraChannelResultValuesV1"));require(len(result)==13,"shape");require(close(result[0],35.0),"default focal");require(close(result[1],2.8),"default aperture");require(close(result[2],160.0),"optical focus");require(close(result[5],.5),"bloom");require(close(result[9],.2),"motion blur");require(str(get(obj,"CameraChannelResultFilmbackPresetIdV1"))=="pie_full_frame","filmback");require(tuple(norm(get(obj,name)) for name in INPUTS)==before,"inputs mutated");emit("OPTICAL_MIDPOINT",result[2]);emit("INDEPENDENT_BLOOM",result[5]);emit("FRAME_CHANNELS",len(result));emit("GAME_WORLD_RESULT","PASS")
def restore(state):
 if state.get("restored") or not state.get("originals"):return
 for name,value in state["originals"].items():set_(state["defaults"],name,clone(value))
 state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
 state=globals().get("_EDD_CAMERA_CHANNEL_PIE_STATE");restore(state)
 if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
 emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
 state=globals()["_EDD_CAMERA_CHANNEL_PIE_STATE"]
 try:
  subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
  if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"already PIE");require(subsystem.load_level(SOURCE),"load");state["defaults"]=defaults();state["originals"]={name:clone(get(state["defaults"],name)) for name in NAMES};stage(state["defaults"]);state["stage"]="request";state["at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE);return
  if state["stage"]=="request":
   if time.monotonic()-state["at"]<.5:return
   subsystem.editor_request_begin_play();state["stage"]="wait";emit("PIE_START_REQUESTED",True);return
  if state["stage"]=="wait":
   try:component=director();require(component.get_owner().has_actor_begun_play(),"BeginPlay")
   except Exception:require(time.monotonic()-state["armed"]<TIMEOUT,"startup timeout");return
   state["stage"]="settle";state["at"]=time.monotonic();return
  if state["stage"]=="settle":
   if time.monotonic()-state["at"]<1.0:return
   checks();subsystem.editor_request_end_play();state["stage"]="end";return
  if state["stage"]=="end":
   if subsystem.is_in_play_in_editor():require(time.monotonic()-state["armed"]<TIMEOUT,"teardown timeout");return
   state["stage"]="complete";finish(True)
 except Exception as error:
  unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
  try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
  finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_CHANNEL_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_CHANNEL_PIE_STATE={"stage":"prepare","armed":time.monotonic(),"at":time.monotonic(),"callback":None,"defaults":None,"originals":None,"restored":False};_EDD_CAMERA_CHANNEL_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)

