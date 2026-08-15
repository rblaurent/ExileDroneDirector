"""Shared deterministic fixture helpers for playback-native acceptance."""
from __future__ import annotations
import json,math
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
SCHEMAS=("camera_engine_application_blueprint_schema.json","camera_playback_frame_blueprint_schema.json","camera_playback_native_application_blueprint_schema.json")
def schema_names():
 names=[]
 for filename in SCHEMAS:
  data=json.loads((ROOT/"tools/trajectory"/filename).read_text(encoding="utf-8"))
  for spec in data["variables"]:
   if spec["name"] not in names:names.append(spec["name"])
 return tuple(names)
NAMES=schema_names()
def variants(name):snake="".join(("_"+c.lower()) if c.isupper() else c for c in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
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
def clone(value):
 if isinstance(value,(list,tuple)):return [clone(item) for item in value]
 return value.copy() if hasattr(value,"copy") else value
def field(value,*names):
 for name in names:
  try:return value.get_editor_property(name)
  except Exception:pass
  try:return getattr(value,name)
  except Exception:pass
 raise RuntimeError("missing-field:"+str(names))
def struct_text(value):
 exporter=getattr(value,"export_text",None)
 return exporter() if callable(exporter) else str(value)
def norm(value):
 if isinstance(value,(list,tuple)):return tuple(norm(item) for item in value)
 if isinstance(value,unreal.Vector):return float(value.x),float(value.y),float(value.z)
 if isinstance(value,unreal.Quat):return float(value.x),float(value.y),float(value.z),float(value.w)
 if isinstance(value,unreal.Transform):return norm(field(value,"translation","location")),norm(field(value,"rotation")),norm(field(value,"scale3d","scale"))
 if isinstance(value,(unreal.CameraFilmbackSettings,unreal.CameraFocusSettings,unreal.PostProcessSettings)):
  return type(value).__name__,struct_text(value)
 return value
def snapshot(obj,names):return tuple(norm(get(obj,name)) for name in names)
def close(a,b,tol=1e-5):return abs(float(a)-float(b))<=tol*max(1.,abs(float(a)),abs(float(b)))
def vector_close(a,b,tol=1e-5):return all(close(x,y,tol) for x,y in zip(norm(a),norm(b)))
def quat_close(a,b,tol=1e-6):
 left,right=norm(a),norm(b);return all(close(x,y,tol) for x,y in zip(left,right)) or all(close(x,-y,tol) for x,y in zip(left,right))
def axis_quat(axis,degrees):
 half=math.radians(degrees)*.5;s=math.sin(half);return unreal.Quat(axis[0]*s,axis[1]*s,axis[2]*s,math.cos(half))
def quat_mul(left,right):
 ax,ay,az,aw=norm(left);bx,by,bz,bw=norm(right)
 return unreal.Quat(aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz)
BODY=axis_quat((0.,0.,1.),45.);RELATIVE=axis_quat((0.,1.,0.),30.);GIMBAL=quat_mul(BODY,RELATIVE);POSITION=unreal.Vector(1200.,-350.,480.)
CHANNELS=(52.,2.8,700.,1.,.25,.35,.45,0.,0.,.15,.2,0.,0.)
def stage_result(obj,scenario="success"):
 channels=list(CHANNELS);gimbal=GIMBAL
 if scenario=="engine_rollback":channels[7]=.25
 if scenario=="pose_rejection":gimbal=axis_quat((1.,0.,0.),80.)
 for name,value in (
  ("CameraPlaybackResultPositionV1",POSITION),("CameraPlaybackResultBodyWorldQuatV1",BODY),
  ("CameraPlaybackResultGimbalWorldQuatV1",gimbal),("CameraPlaybackResultGimbalRelativeQuatV1",RELATIVE),
  ("CameraPlaybackResultFilmbackPresetIdV1","native_acceptance"),("CameraPlaybackResultFilmbackSensorWidthMmV1",36.),
  ("CameraPlaybackResultFilmbackSensorHeightMmV1",24.),("CameraPlaybackResultChannelValuesV1",channels),
  ("CameraPlaybackResultCompleteV1",False),("CameraPlaybackResultModeV1","directed"),
  ("CameraPlaybackResultOverrideActiveV1",False),("CameraPlaybackResultTransitionActiveV1",False),
  ("CameraPlaybackResultTetherAppliedV1",False),("CameraPlaybackResultComfortEffectiveWeightsV1",[1.]*5),
  ("CameraPlaybackResultComfortAppliedV1",False),("CameraPlaybackResultValidV1",True),
 ):set_(obj,name,value)
