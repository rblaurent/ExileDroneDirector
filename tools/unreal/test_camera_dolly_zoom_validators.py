"""Offline ownership and lifecycle checks for dolly-zoom live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraDollyZoom.py").read_text(encoding="utf-8");RUNTIME=(ROOT/"tools/unreal/Validate-CameraDollyZoomRuntime.py").read_text(encoding="utf-8");PIE=(ROOT/"tools/unreal/Validate-CameraDollyZoomPIE.py").read_text(encoding="utf-8");RESTORE=(ROOT/"tools/unreal/Restore-CameraDollyZoomSchemaDefaults.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("runtime",RUNTIME),("PIE",PIE),("restore",RESTORE)):
    compile(source,label,"exec");assert "camera_dolly_zoom_blueprint_schema.json" in source;assert "CameraTransform" not in source
assert "get_struct_type(vector_struct)" in CONFIG and "VARIABLE_COUNT" in CONFIG and "FUNCTION_COUNT" in CONFIG
for token in ("CompileCameraDollyZoomV1","CommitCameraDollyZoomV1","BODY_GIMBAL_AUTHORSHIP_PRESERVED","DEFAULTS_RESTORED","FORWARD_CASES","REVERSE_CASES") :assert token in RUNTIME
for name in ("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1"):assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE
for token in ("CompileCameraDollyZoomV1","FOCAL_RESULT","FAIL_CLOSED_RESULT","DEFAULTS_RESTORED","editor_request_begin_play","editor_request_end_play"):assert token in PIE
assert 'SCENARIOS=("shrinking","expanding","fail_closed")' in PIE
assert "set_(component" not in PIE and "compile_blueprint" not in PIE
assert "only_if_is_dirty=False" in RESTORE;assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)");assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
print("camera dolly zoom live-tool contracts passed")
