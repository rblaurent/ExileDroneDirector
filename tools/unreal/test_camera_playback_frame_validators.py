"""Offline ownership and lifecycle checks for playback live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraPlaybackFrame.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CameraPlaybackFrameSchemaDefaults.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("restore",RESTORE)):
    compile(source,label,"exec");assert "camera_playback_frame_blueprint_schema.json" in source
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat","String","EXISTING_DEFAULT_PRESERVED"):assert token in CONFIG
for token in ("CameraPlaybackResultBodyWorldQuatV1","CameraPlaybackResultGimbalWorldQuatV1","CameraPlaybackResultGimbalRelativeQuatV1"):assert token not in CONFIG or "SCHEMA" in CONFIG
assert "only_if_is_dirty=False" in RESTORE
assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)")
assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
assert "CameraTransform" not in CONFIG and "CameraTransform" not in RESTORE
print("camera playback-frame configurator/restore contracts passed")
