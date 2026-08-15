"""Offline ownership and lifecycle checks for playback live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraPlaybackFrame.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CameraPlaybackFrameSchemaDefaults.py").read_text(encoding="utf-8")
COMMON=(ROOT/"tools/unreal/camera_playback_acceptance_common.py").read_text(encoding="utf-8")
RUNTIME=(ROOT/"tools/unreal/Validate-CameraPlaybackFrameRuntime.py").read_text(encoding="utf-8")
PIE=(ROOT/"tools/unreal/Validate-CameraPlaybackFramePIE.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("restore",RESTORE),("common",COMMON)):
    compile(source,label,"exec");assert "camera_playback_frame_blueprint_schema.json" in source
compile(RUNTIME,"runtime","exec")
compile(PIE,"PIE","exec")
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat","String","EXISTING_DEFAULT_PRESERVED"):assert token in CONFIG
for token in ("ComposeCameraPlaybackFrameV1","DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED","CINEMATIC_ROTATION_IGNORED","RELATIVE_RECONSTRUCTION","TAMPER_FAIL_CLOSED","COMPILED_SOURCES_IMMUTABLE","DEFAULTS_RESTORED"):assert token in RUNTIME
for token in ("BODY=","GIMBAL=","CARRIER=","CINEMATIC=","CompileCinematicPoseV1","CompileAirframePrebakeV1","CompileCarrierFrameTransportV1","CompileCameraChannelAssemblyV1"):assert token in COMMON
assert 'set_(obj,"AirframePrebakeCompileValidV1",False)' in RUNTIME
assert "CameraTransform" not in COMMON and "CameraTransform" not in RUNTIME
for token in ("ComposeCameraPlaybackFrameV1","MID_FRAME_RESULT","COMPLETE_FRAME_RESULT","FAIL_CLOSED_RESULT","DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED","DEFAULTS_RESTORED","editor_request_begin_play","editor_request_end_play"):assert token in PIE
assert 'SCENARIOS=("mid_frame","complete_frame","fail_closed")' in PIE
assert "compile_blueprint" not in PIE and 'component.call_method("ComposeCameraPlaybackFrameV1")' in PIE
assert "only_if_is_dirty=False" in RESTORE
assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)")
assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
assert "CameraTransform" not in CONFIG and "CameraTransform" not in RESTORE
print("camera playback-frame configurator/restore contracts passed")
