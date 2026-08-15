"""Offline ownership and lifecycle checks for playback-native live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraPlaybackNativeApplication.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CameraPlaybackNativeApplicationSchemaDefaults.py").read_text(encoding="utf-8")
SCHEMA=(ROOT/"tools/trajectory/camera_playback_native_application_blueprint_schema.json").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("restore",RESTORE)):
 compile(source,label,"exec");assert "camera_playback_native_application_blueprint_schema.json" in source
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat","Transform","EXISTING_DEFAULT_PRESERVED"):assert token in CONFIG
for token in ("unreal.Transform()","CameraPlaybackNativeBaselineActorTransformV1","CameraPlaybackNativeBaselineComponentRelativeTransformV1","only_if_is_dirty=False"):assert token in CONFIG+RESTORE+SCHEMA
assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)")
assert "isinstance(value,unreal.Transform)" in RESTORE and "scale3d" in RESTORE
assert "CameraTransform" not in CONFIG and "CameraTransform" not in RESTORE
print("camera playback native-application configurator/restore contracts passed")
