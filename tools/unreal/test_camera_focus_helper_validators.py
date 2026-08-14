"""Offline ownership and lifecycle checks for camera-focus live tooling."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (ROOT / "tools/unreal/Configure-CameraFocusHelper.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "tools/unreal/Validate-CameraFocusHelperRuntime.py").read_text(encoding="utf-8")
PIE = (ROOT / "tools/unreal/Validate-CameraFocusHelperPIE.py").read_text(encoding="utf-8")


for label, source in (("config", CONFIG), ("runtime", RUNTIME), ("PIE", PIE)):
    compile(source, label, "exec")
    assert "camera_focus_helper_blueprint_schema.json" in source
    assert "CameraTransform" not in source
    assert "Airframe" not in source
assert "get_struct_type(vector_struct)" in CONFIG
assert "VARIABLE_COUNT" in CONFIG and "FUNCTION_COUNT" in CONFIG
for mode in ("manual_distance", "fixed_world", "rack_fixed", "track_prebaked", "smoothed_autofocus"):
    assert mode in RUNTIME
for token in ("SetCameraFocusHereV1", "CompileCameraFocusDistanceChannelV1", "CommitCameraFocusDistanceChannelV1", "DEFAULTS_RESTORED", "TRACE_MISS_ZERO_MUTATION", "TRACE_HIT_ATOMIC"):
    assert token in RUNTIME
for token in ("SetCameraFocusHereV1", "CompileCameraFocusDistanceChannelV1", "RECIPROCAL_MIDPOINT", "FAIL_CLOSED_RESULT", "DEFAULTS_RESTORED", "editor_request_begin_play", "editor_request_end_play"):
    assert token in PIE
print("camera focus helper live-tool contracts passed")
