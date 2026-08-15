"""Warm CDO fail-closed acceptance for the playback-native boundary."""
from __future__ import annotations
import importlib,sys
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"tools/unreal"));import camera_playback_native_application_acceptance_common as common;common=importlib.reload(common)
PREFIX="EDD_CAMERA_PLAYBACK_NATIVE_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
RESULT=("CameraPlaybackResultPositionV1","CameraPlaybackResultBodyWorldQuatV1","CameraPlaybackResultGimbalWorldQuatV1","CameraPlaybackResultGimbalRelativeQuatV1","CameraPlaybackResultFilmbackPresetIdV1","CameraPlaybackResultFilmbackSensorWidthMmV1","CameraPlaybackResultFilmbackSensorHeightMmV1","CameraPlaybackResultChannelValuesV1","CameraPlaybackResultCompleteV1","CameraPlaybackResultModeV1","CameraPlaybackResultOverrideActiveV1","CameraPlaybackResultTransitionActiveV1","CameraPlaybackResultTetherAppliedV1","CameraPlaybackResultComfortEffectiveWeightsV1","CameraPlaybackResultComfortAppliedV1","CameraPlaybackResultValidV1")
BASELINES=("CameraPlaybackNativeBaselineActorTransformV1","CameraPlaybackNativeBaselineComponentRelativeTransformV1","CameraApplyBaselineTargetValuesV1")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(value,message):
 if not value:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);saved={name:common.clone(common.get(obj,name)) for name in common.NAMES}
try:
 for run,scenario in ((1,"success"),(2,"pose_rejection")):
  common.stage_result(obj,scenario);source=common.snapshot(obj,RESULT);baselines=common.snapshot(obj,BASELINES);obj.call_method("ApplyComposedCameraPlaybackFrameV1")
  require(not bool(common.get(obj,"CameraPlaybackNativeResultValidV1")),f"run-{run}:camera-less accepted")
  require(not bool(common.get(obj,"CameraPlaybackNativeSessionActiveV1")),f"run-{run}:session")
  require(common.snapshot(obj,RESULT)==source,f"run-{run}:source mutated")
  require(common.snapshot(obj,BASELINES)==baselines,f"run-{run}:baseline mutated")
  require(str(common.get(obj,"CameraPlaybackNativeFailureCodeV1"))=="native_preflight_failed",f"run-{run}:diagnostic")
  emit("CAMERA_LESS_FAIL_CLOSED",run)
 before=common.snapshot(obj,BASELINES);obj.call_method("RestoreCameraPlaybackNativeStateV1");require(common.snapshot(obj,BASELINES)==before,"inactive restore")
 emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("WORLD_GIMBAL_VALIDATION_ONLY",True);emit("PLAYBACK_RESULT_IMMUTABLE",True);emit("INACTIVE_RESTORE_IDEMPOTENT",True);emit("RESULT","PASS")
finally:
 for name,value in saved.items():common.set_(obj,name,common.clone(value))
 mismatches=[]
 for name,value in saved.items():
  actual,wanted=common.norm(common.get(obj,name)),common.norm(value)
  if actual!=wanted:
   mismatches.append(name);emit("DEFAULT_MISMATCH",f"{name}|ACTUAL:{actual}|WANTED:{wanted}")
 restored=not mismatches;emit("DEFAULTS_RESTORED",restored);require(restored,"restoration:"+",".join(mismatches))
