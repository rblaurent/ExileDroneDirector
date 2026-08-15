"""Offline ownership and lifecycle checks for carrier-frame live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CarrierFrameTransport.py").read_text(encoding="utf-8")
RUNTIME=(ROOT/"tools/unreal/Validate-CarrierFrameTransportRuntime.py").read_text(encoding="utf-8")
PIE=(ROOT/"tools/unreal/Validate-CarrierFrameTransportPIE.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CarrierFrameTransportSchemaDefaults.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("runtime",RUNTIME),("PIE",PIE),("restore",RESTORE)):
    compile(source,label,"exec");assert "carrier_frame_transport_blueprint_schema.json" in source;assert "CameraTransform" not in source
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","Vector","Quat","String","EXISTING_DEFAULT_PRESERVED"):assert token in CONFIG
for token in ("CompileCarrierFrameTransportV1","EvaluateCompiledCarrierFrameTransportV1","PARTIAL_TERMINAL_INTERVAL","DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED","CARRIER_FRAME_INDEPENDENT","EXTERNAL_STATE_PRESERVED","DEFAULTS_RESTORED","FORWARD_CASES","REVERSE_CASES"):assert token in RUNTIME
for name in ("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1"):
    assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE;assert f'set_(component,"{name}"' not in PIE
for name in ("CameraOperatorInputCarrierFrameQuatV1","CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1"):
    assert name in RUNTIME and name in PIE;assert f'set_(obj,"{name}"' not in RUNTIME;assert f'set_(obj,"{name}"' not in PIE;assert f'set_(component,"{name}"' not in PIE
for token in ("CompileCarrierFrameTransportV1","EvaluateCompiledCarrierFrameTransportV1","PARTIAL_TERMINAL_RESULT","VERTICAL_TRANSPORT_RESULT","FAIL_CLOSED_RESULT","DEFAULTS_RESTORED","editor_request_begin_play","editor_request_end_play"):assert token in PIE
assert 'SCENARIOS=("partial_terminal","vertical_transport","fail_closed")' in PIE
assert 'set_(obj,"CarrierFrameInputElapsedSecondsV1",elapsed)' in PIE
assert 'set_(component,"CarrierFrameInputElapsedSecondsV1"' not in PIE
assert 'require(close(get(component,"CarrierFrameInputElapsedSecondsV1"),elapsed),"staged elapsed")' in PIE
assert "compile_blueprint" not in PIE and "call_method(\"CompileCarrierFrameTransportV1\")" in PIE
assert "only_if_is_dirty=False" in RESTORE;assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)");assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
print("carrier-frame transport live-tool contracts passed")
