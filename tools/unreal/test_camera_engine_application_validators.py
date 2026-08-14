"""Offline ownership checks for the live camera-engine validators."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = (ROOT / "tools/unreal/Validate-CameraEngineApplicationRuntime.py").read_text(encoding="utf-8")
PIE = (ROOT / "tools/unreal/Validate-CameraEngineApplicationPIE.py").read_text(encoding="utf-8")


for label, source in (("runtime", RUNTIME), ("PIE", PIE)):
    compile(source, label, "exec")
    for token in (
        "CaptureCameraEngineStateV1",
        "RestoreCameraEngineStateV1",
        "CameraApplyBaselinePostProcessSettingsV1",
        "DEFAULTS_RESTORED",
    ):
        assert token in source, f"{label} missing {token}"
    assert "CameraTransform" not in source
    assert "alias" not in source.lower()

assert "WARM_CDO_RUN" in RUNTIME
assert "camera_less_capture_fail_closed" in RUNTIME
assert "StageEvaluatedCameraChannelFrameV1" in RUNTIME
assert "ValidateCameraEngineApplicationInputsV1" in RUNTIME
assert 'call_method("EnterDroneMode")' in PIE
assert "ApplyEvaluatedCameraChannelFrameV1" in PIE
assert "CameraApplyAppliedFrameCountV1" in PIE
assert "unsupported" in PIE
assert "native_snapshot" in PIE
assert "PLAYER_OWNED_DIRECTOR" in PIE
assert "editor_request_begin_play" in PIE
assert "editor_request_end_play" in PIE
print("camera engine application validator contracts passed")
