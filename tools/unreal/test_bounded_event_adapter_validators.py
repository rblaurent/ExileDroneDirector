"""Offline ownership and lifecycle checks for bounded-event live tooling."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (ROOT / "tools/unreal/Configure-BoundedEventAdapter.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "tools/unreal/Validate-BoundedEventAdapterRuntime.py").read_text(encoding="utf-8")
PIE = (ROOT / "tools/unreal/Validate-BoundedEventAdapterPIE.py").read_text(encoding="utf-8")
RESTORE = (ROOT / "tools/unreal/Restore-BoundedEventAdapterSchemaDefaults.py").read_text(encoding="utf-8")
for label, source in (("config", CONFIG), ("runtime", RUNTIME), ("PIE", PIE), ("restore", RESTORE)):
    compile(source, label, "exec")
    assert "bounded_event_adapter_blueprint_schema.json" in source
    assert "CameraTransform" not in source
for token in (
    "VARIABLE_COUNT", "FUNCTION_COUNT", "String", "Real", "Integer",
    "Boolean", "EXISTING_DEFAULT_PRESERVED",
):
    assert token in CONFIG
for name in (
    "AirframePrebakeCompiledBodyQuatsV1",
    "AirframePrebakeCompiledGimbalQuatsV1",
    "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1",
):
    assert name in RUNTIME and name in PIE
    assert f'set_(obj, "{name}"' not in RUNTIME
    assert f'set_(component, "{name}"' not in PIE
for token in (
    "DispatchBoundedPlaybackEventsV1", "CommitCueExecutionLedgerV1",
    "ResetManualCueLedgerEntryV1", "CAPABILITIES_ACCEPTED",
    "TYPED_REMOTE_REJECTION", "SUCCESS_ONLY_LEDGER", "SCRUB_ZERO_DISPATCH",
    "REVERSE_SELECTION_ORDER", "MANUAL_REARM",
    "DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED", "NO_ADAPTER_OR_WORLD_MUTATION",
    "DEFAULTS_RESTORED",
):
    assert token in RUNTIME
for token in (
    "DispatchBoundedPlaybackEventsV1", "CommitCueExecutionLedgerV1",
    "ResetManualCueLedgerEntryV1", "LOCAL_DISPATCH_RESULT",
    "REMOTE_REJECTION_RESULT", "MANUAL_SCRUB_RESULT",
    "DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED", "DEFAULTS_RESTORED",
    "editor_request_begin_play", "editor_request_end_play",
):
    assert token in PIE
assert 'SCENARIOS = ("local_success", "remote_reject", "manual_scrub")' in PIE
assert "compile_blueprint" not in PIE
assert 'component.call_method("DispatchBoundedPlaybackEventsV1")' in PIE
assert 'component.call_method("CommitCueExecutionLedgerV1")' in PIE
assert 'component.call_method("ResetManualCueLedgerEntryV1")' in PIE
assert "only_if_is_dirty=False" in RESTORE
assert RESTORE.index("compile_blueprint(blueprint)") < RESTORE.index("load_blueprint_class(CLIENT)")
assert 'spec["container"] == "Array"' in RESTORE and "return []" in RESTORE
print("bounded event-adapter live-tool contracts passed")
