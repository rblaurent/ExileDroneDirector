"""Offline ownership and lifecycle checks for camera-operator live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraOperatorOverride.py").read_text(encoding="utf-8")
RUNTIME=(ROOT/"tools/unreal/Validate-CameraOperatorOverrideRuntime.py").read_text(encoding="utf-8")
PIE=(ROOT/"tools/unreal/Validate-CameraOperatorOverridePIE.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CameraOperatorOverrideSchemaDefaults.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("runtime",RUNTIME),("PIE",PIE),("restore",RESTORE)):
    compile(source,label,"exec");assert "camera_operator_override_blueprint_schema.json" in source;assert "CameraTransform" not in source
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat","EXISTING_DEFAULT_PRESERVED"):assert token in CONFIG
for token in ("ApplyCameraOperatorOverrideV1","CommitCameraOperatorOverrideV1","DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED","CARRIER_FRAME_ISOLATED","EXTERNAL_STATE_PRESERVED","DEFAULTS_RESTORED","FORWARD_CASES","REVERSE_CASES"):assert token in RUNTIME
for name in ("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1"):
    assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE
for name in ("CameraComfortResultGimbalQuatV1","CameraChannelResultValuesV1","CameraApplyCurrentTargetValuesV1"):
    assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE
for name in ("CameraOperatorInputAuthoredBodyQuatV1","CameraOperatorInputAuthoredGimbalQuatV1","CameraOperatorInputCarrierFrameQuatV1","CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1"):
    assert name in RUNTIME and name in PIE
for token in ("ApplyCameraOperatorOverrideV1","DISTINCT_AUTHORSHIP_RESULT","CARRIER_FRAME_RESULT","FAIL_CLOSED_RESULT","DEFAULTS_RESTORED","editor_request_begin_play","editor_request_end_play"):assert token in PIE
assert 'SCENARIOS=("distinct_directed","carrier_frame_isolation","fail_closed")' in PIE
assert "set_(component" not in PIE and "compile_blueprint" not in PIE
assert "only_if_is_dirty=False" in RESTORE;assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)");assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
print("camera operator live-tool contracts passed")
