"""Offline ownership and lifecycle checks for playback-native live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraPlaybackNativeApplication.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CameraPlaybackNativeApplicationSchemaDefaults.py").read_text(encoding="utf-8")
SCHEMA=(ROOT/"tools/trajectory/camera_playback_native_application_blueprint_schema.json").read_text(encoding="utf-8")
COMMON=(ROOT/"tools/unreal/camera_playback_native_application_acceptance_common.py").read_text(encoding="utf-8")
RUNTIME=(ROOT/"tools/unreal/Validate-CameraPlaybackNativeApplicationRuntime.py").read_text(encoding="utf-8")
PIE=(ROOT/"tools/unreal/Validate-CameraPlaybackNativeApplicationPIE.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("restore",RESTORE)):
 compile(source,label,"exec");assert "camera_playback_native_application_blueprint_schema.json" in source
for label,source in (("common",COMMON),("runtime",RUNTIME),("PIE",PIE)):compile(source,label,"exec")
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat","Transform","EXISTING_DEFAULT_PRESERVED"):assert token in CONFIG
for token in ("unreal.Transform()","CameraPlaybackNativeBaselineActorTransformV1","CameraPlaybackNativeBaselineComponentRelativeTransformV1","only_if_is_dirty=False"):assert token in CONFIG+RESTORE+SCHEMA
assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)")
assert "isinstance(value,unreal.Transform)" in RESTORE and "scale3d" in RESTORE
assert "CameraTransform" not in CONFIG and "CameraTransform" not in RESTORE
for token in ("BODY=","RELATIVE=","GIMBAL=","quat_mul","stage_result"):assert token in COMMON
for token in ("ApplyComposedCameraPlaybackFrameV1","CAMERA_LESS_FAIL_CLOSED","PLAYBACK_RESULT_IMMUTABLE","DEFAULTS_RESTORED"):assert token in RUNTIME
for token in ("CameraFilmbackSettings","CameraFocusSettings","PostProcessSettings","struct_text(value)"):assert token in COMMON
for token in ("SCENARIOS=(\"success\",\"engine_rollback\",\"pose_rejection\")","ApplyComposedCameraPlaybackFrameV1","RestoreCameraPlaybackNativeStateV1","SUCCESS_FRAME","ENGINE_FAILURE_EXACT_ROLLBACK","POSE_REJECTION_ZERO_WRITE","editor_request_begin_play","editor_request_end_play"):assert token in PIE
assert 'obj.call_method("ApplyComposedCameraPlaybackFrameV1")' in PIE and "compile_blueprint" not in PIE
assert "CameraTransform" not in COMMON+RUNTIME+PIE
print("camera playback native-application configurator/restore contracts passed")
