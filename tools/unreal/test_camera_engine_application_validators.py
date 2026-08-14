"""Offline ownership checks for the live camera-engine validators."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = (ROOT / "tools/unreal/Validate-CameraEngineApplicationRuntime.py").read_text(encoding="utf-8")
PIE = (ROOT / "tools/unreal/Validate-CameraEngineApplicationPIE.py").read_text(encoding="utf-8")


for label, source in (("runtime", RUNTIME), ("PIE", PIE)):
    compile(source, label, "exec")
    for token in (
        "ApplyEvaluatedCameraChannelFrameV1",
        "CaptureCameraEngineStateV1",
        "RestoreCameraEngineStateV1",
        "CameraApplyBaselinePostProcessSettingsV1",
        "CameraApplyAppliedFrameCountV1",
        "unsupported",
        "native_snapshot",
        "DEFAULTS_RESTORED",
    ):
        assert token in source, f"{label} missing {token}"
    assert "CameraTransform" not in source
    assert "alias" not in source.lower()

assert "spawn_actor_from_class" in RUNTIME
assert "TRANSIENT_DESTROYED" in RUNTIME
assert 'call_method("EnterDroneMode")' in PIE
assert "PLAYER_OWNED_DIRECTOR" in PIE
assert "editor_request_begin_play" in PIE
assert "editor_request_end_play" in PIE
print("camera engine application validator contracts passed")
