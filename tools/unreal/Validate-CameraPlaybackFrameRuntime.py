"""Execute the complete saved playback composer across absolute-time boundaries."""
from __future__ import annotations
import math,sys
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"tools/unreal"));import camera_playback_acceptance_common as common
PREFIX="EDD_CAMERA_PLAYBACK_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";RESULT=("CameraPlaybackResultPositionV1","CameraPlaybackResultBodyWorldQuatV1","CameraPlaybackResultGimbalWorldQuatV1","CameraPlaybackResultGimbalRelativeQuatV1","CameraPlaybackResultFilmbackPresetIdV1","CameraPlaybackResultFilmbackSensorWidthMmV1","CameraPlaybackResultFilmbackSensorHeightMmV1","CameraPlaybackResultChannelValuesV1","CameraPlaybackResultCompleteV1","CameraPlaybackResultModeV1","CameraPlaybackResultOverrideActiveV1","CameraPlaybackResultTransitionActiveV1","CameraPlaybackResultTetherAppliedV1","CameraPlaybackResultComfortEffectiveWeightsV1","CameraPlaybackResultComfortAppliedV1")
COMPILED=("PositionRouteCompiledWaypointPositionsV1","OrientationTrackCompiledAlignedQuatsV1","AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","CarrierFrameCompiledQuatsV1","CameraChannelCompiledDomainValuesV1")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(value,message):
 if not value:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def close(a,b,tol=8e-4):return abs(float(a)-float(b))<=tol*max(1.,abs(float(a)),abs(float(b)))
def quat_close(a,b,tol=1e-6):return all(close(x,y,tol) for x,y in zip(a,b)) or all(close(x,-y,tol) for x,y in zip(a,b))
def quat_mul(a,b):ax,ay,az,aw=a;bx,by,bz,bw=b;return aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={name:common.clone(common.get(obj,name)) for name in common.NAMES}
try:
 common.stage_and_compile(obj);compiled=common.snapshot(obj,COMPILED);cases=((-1.,0.,False),(.5,50.,False),(2.,100.,True))
 for index,(elapsed,x,complete) in enumerate(cases):
  common.set_(obj,"CameraPlaybackInputElapsedSecondsV1",elapsed);obj.call_method("ComposeCameraPlaybackFrameV1");require(bool(common.get(obj,"CameraPlaybackResultValidV1")),f"case:{index}:valid");require(close(common.norm(common.get(obj,"CameraPlaybackResultPositionV1"))[0],x),f"case:{index}:position");require(bool(common.get(obj,"CameraPlaybackResultCompleteV1"))==complete,f"case:{index}:complete");body=common.norm(common.get(obj,"CameraPlaybackResultBodyWorldQuatV1"));gimbal=common.norm(common.get(obj,"CameraPlaybackResultGimbalWorldQuatV1"));emit(f"CASE_{index}_BODY",body);emit(f"CASE_{index}_GIMBAL",gimbal);require(quat_close(body,common.norm(common.BODY)),f"case:{index}:body");require(quat_close(gimbal,common.norm(common.GIMBAL)),f"case:{index}:gimbal");relative=common.norm(common.get(obj,"CameraPlaybackResultGimbalRelativeQuatV1"));require(quat_close(quat_mul(body,relative),gimbal),f"case:{index}:reconstruct");require(len(common.get(obj,"CameraPlaybackResultChannelValuesV1"))==13 and len(common.get(obj,"CameraPlaybackResultComfortEffectiveWeightsV1"))==5,f"case:{index}:shape");require(str(common.get(obj,"CameraPlaybackResultFilmbackPresetIdV1"))=="playback_full_frame",f"case:{index}:filmback");require(common.snapshot(obj,COMPILED)==compiled,f"case:{index}:compiled mutated")
 prior=common.snapshot(obj,RESULT);common.set_(obj,"AirframePrebakeCompileValidV1",False);common.set_(obj,"CameraPlaybackInputElapsedSecondsV1",.5);obj.call_method("ComposeCameraPlaybackFrameV1");require(not bool(common.get(obj,"CameraPlaybackResultValidV1")),"tamper accepted");require(common.snapshot(obj,RESULT)==prior,"tamper replaced prior snapshot");require(str(common.get(obj,"CameraPlaybackFailureCodeV1"))=="commit_failed","tamper diagnostic");emit("ABSOLUTE_BOUNDARIES",len(cases));emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("CINEMATIC_ROTATION_IGNORED",True);emit("RELATIVE_RECONSTRUCTION","PASS");emit("TAMPER_FAIL_CLOSED","PASS");emit("COMPILED_SOURCES_IMMUTABLE",True);emit("RESULT","PASS")
finally:
 for name,value in saved.items():common.set_(obj,name,common.clone(value))
 restored=all(common.norm(common.get(obj,name))==common.norm(value) for name,value in saved.items());emit("DEFAULTS_RESTORED",restored);require(restored,"restoration")
