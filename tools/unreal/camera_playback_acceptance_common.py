"""Shared deterministic fixture/lifecycle helpers for playback acceptance."""
from __future__ import annotations
import json,math
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
SCHEMAS=("position_route_blueprint_schema.json","orientation_blueprint_schema.json","cinematic_pose_blueprint_schema.json","airframe_gimbal_prebake_blueprint_schema.json","airframe_desired_stream_blueprint_schema.json","carrier_frame_transport_blueprint_schema.json","camera_scalar_track_blueprint_schema.json","camera_channel_assembly_blueprint_schema.json","camera_operator_override_blueprint_schema.json","camera_viewer_comfort_blueprint_schema.json","camera_playback_frame_blueprint_schema.json")
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
def norm(value):
 if isinstance(value,(list,tuple)):return tuple(norm(item) for item in value)
 if isinstance(value,unreal.Vector):return float(value.x),float(value.y),float(value.z)
 if isinstance(value,unreal.Quat):return float(value.x),float(value.y),float(value.z),float(value.w)
 return value
def snapshot(obj,names):return tuple(norm(get(obj,name)) for name in names)
def axis_quat(axis,degrees):
 half=math.radians(degrees)*.5;s=math.sin(half);return unreal.Quat(axis[0]*s,axis[1]*s,axis[2]*s,math.cos(half))
BODY=axis_quat((0.,0.,1.),45.);GIMBAL=axis_quat((0.,1.,0.),30.);CARRIER=axis_quat((1.,0.,0.),10.);CINEMATIC=axis_quat((1.,0.,0.),180.)
def stage_and_compile(obj):
 set_(obj,"PositionRouteInputWaypointPositionsV1",[unreal.Vector(0.,0.,0.),unreal.Vector(100.,0.,0.)]);set_(obj,"PositionRouteInputDurationsV1",[1.]);set_(obj,"PositionRouteInputSpatialCurveTypesV1",["linear"]);set_(obj,"PositionRouteInputTimeProfilesV1",["linear"]);set_(obj,"PositionRouteInputArcToleranceV1",.01);set_(obj,"PositionRouteInputMaxArcDepthV1",8);set_(obj,"PositionRouteInputMaxArcOperationsV1",8191);set_(obj,"OrientationTrackInputWaypointQuatsV1",[CINEMATIC,CINEMATIC]);set_(obj,"OrientationTrackInputDurationsV1",[1.]);obj.call_method("CompileCinematicPoseV1")
 samples=5;set_(obj,"AirframePrebakeInputDesiredBodyQuatsV1",[BODY]*samples);set_(obj,"AirframePrebakeInputDesiredGimbalQuatsV1",[GIMBAL]*samples);set_(obj,"AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1",[720.]*samples);set_(obj,"AirframePrebakeInputTotalSecondsV1",1.);set_(obj,"AirframePrebakeInputFixedStepSecondsV1",.25);obj.call_method("CompileAirframePrebakeV1")
 set_(obj,"AirframeDesiredStreamCompileValidV1",True);set_(obj,"AirframeDesiredStreamInputPositionsV1",[unreal.Vector(float(i)*25.,0.,0.) for i in range(samples)]);set_(obj,"AirframeDesiredStreamInputTotalSecondsV1",1.);set_(obj,"AirframeDesiredStreamInputFixedStepSecondsV1",.25);obj.call_method("CompileCarrierFrameTransportV1")
 for name,value in (("CameraChannelInputDurationV1",1.),("CameraChannelInputFilmbackPresetIdV1","playback_full_frame"),("CameraChannelInputFilmbackSensorWidthMmV1",36.),("CameraChannelInputFilmbackSensorHeightMmV1",24.),("CameraChannelInputChannelIdsV1",[]),("CameraChannelInputKeyOffsetsV1",[]),("CameraChannelInputKeyCountsV1",[]),("CameraChannelInputKeyTimesV1",[]),("CameraChannelInputKeyValuesV1",[]),("CameraChannelInputInterpolationModesV1",[]),("CameraChannelInputArriveTangentsV1",[]),("CameraChannelInputLeaveTangentsV1",[]),("CameraChannelInputDomainsV1",[])):set_(obj,name,value)
 obj.call_method("CompileCameraChannelAssemblyV1")
 set_(obj,"CameraComfortEnabledV1",False);set_(obj,"CameraOperatorStateInitializedV1",False)
 for name,value in (("CameraPlaybackInputDeltaSecondsV1",1./60.),("CameraPlaybackInputRequestedModeV1","directed"),("CameraPlaybackInputTranslationV1",unreal.Vector()),("CameraPlaybackInputLookV1",unreal.Vector()),("CameraPlaybackInputRecenterRequestedV1",False),("CameraPlaybackInputReturnToDirectedRequestedV1",False),("CameraPlaybackInputProceduralTranslationOffsetV1",unreal.Vector()),("CameraPlaybackInputProceduralRotationOffsetV1",unreal.Quat(0.,0.,0.,1.))):set_(obj,name,value)
 required=("CinematicPoseCompileValidV1","AirframePrebakeCompileValidV1","CarrierFrameCompileValidV1","CameraChannelCompileValidV1")
 if not all(bool(get(obj,name)) for name in required):raise RuntimeError("source compile invalid:"+str(snapshot(obj,required)))
