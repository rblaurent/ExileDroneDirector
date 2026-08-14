"""Offline ownership and lifecycle checks for viewer-comfort live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraViewerComfort.py").read_text(encoding="utf-8");RUNTIME=(ROOT/"tools/unreal/Validate-CameraViewerComfortRuntime.py").read_text(encoding="utf-8");PIE=(ROOT/"tools/unreal/Validate-CameraViewerComfortPIE.py").read_text(encoding="utf-8");RESTORE=(ROOT/"tools/unreal/Restore-CameraViewerComfortSchemaDefaults.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("runtime",RUNTIME),("PIE",PIE),("restore",RESTORE)):
    compile(source,label,"exec");assert "camera_viewer_comfort_blueprint_schema.json" in source;assert "CameraTransform" not in source
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat"):assert token in CONFIG
for token in ("ApplyCameraViewerComfortV1","CommitCameraViewerComfortV1","BODY_GIMBAL_AUTHORSHIP_PRESERVED","UPSTREAM_RESULTS_PRESERVED","DEFAULTS_RESTORED","FORWARD_CASES","REVERSE_CASES"):assert token in RUNTIME
for name in ("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1"):
    assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE
for name in ("CameraChannelResultValuesV1","CameraLookResultValuesV1","CameraApplyCurrentTargetValuesV1"):
    assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE
for token in ("ApplyCameraViewerComfortV1","COMFORT_RESULT","FAIL_CLOSED_RESULT","DEFAULTS_RESTORED","editor_request_begin_play","editor_request_end_play"):assert token in PIE
assert 'SCENARIOS=("disabled_exact","maximum_reduction","fail_closed")' in PIE
assert "set_(component" not in PIE and "compile_blueprint" not in PIE
assert "only_if_is_dirty=False" in RESTORE;assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)");assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
print("camera viewer-comfort live-tool contracts passed")
