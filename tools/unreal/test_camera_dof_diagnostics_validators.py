"""Offline ownership and lifecycle checks for camera DOF live tooling."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (ROOT / "tools/unreal/Configure-CameraDofDiagnostics.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "tools/unreal/Validate-CameraDofDiagnosticsRuntime.py").read_text(encoding="utf-8")
PIE = (ROOT / "tools/unreal/Validate-CameraDofDiagnosticsPIE.py").read_text(encoding="utf-8")
RESTORE = (ROOT / "tools/unreal/Restore-CameraDofDiagnosticsSchemaDefaults.py").read_text(encoding="utf-8")


for label, source in (("config", CONFIG), ("runtime", RUNTIME), ("PIE", PIE), ("restore", RESTORE)):
    compile(source, label, "exec")
    assert "camera_dof_diagnostics_blueprint_schema.json" in source
    assert "CameraTransform" not in source
    assert "Airframe" not in source
    assert "Gimbal" not in source
assert "VARIABLE_COUNT" in CONFIG and "FUNCTION_COUNT" in CONFIG
for token in ("EvaluateCameraDofDiagnosticsV1", "ComputeCameraDofDiagnosticsV1", "BOUNDED_AND_UNBOUNDED", "DEFAULTS_RESTORED", "camera_dof_compute_failed"):
    assert token in RUNTIME
for token in ("EvaluateCameraDofDiagnosticsV1", "BOUNDED_RESULT", "UNBOUNDED_RESULT", "FAIL_CLOSED_RESULT", "DEFAULTS_RESTORED", "editor_request_begin_play", "editor_request_end_play"):
    assert token in PIE
assert 'SCENARIOS = ("bounded", "unbounded", "fail_closed")' in PIE
assert "compile_blueprint" not in PIE
assert "save_asset" not in PIE
assert "camera_channel_assembly_blueprint_schema.json" in RESTORE
assert "UPSTREAM_NAMES" in RESTORE
assert "only_if_is_dirty=False" in RESTORE
assert RESTORE.index("compile_blueprint(blueprint)") < RESTORE.index("load_blueprint_class(CLIENT)")
print("camera DOF diagnostics live-tool contracts passed")
