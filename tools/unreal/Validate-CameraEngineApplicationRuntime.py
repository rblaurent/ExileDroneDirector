"""Warm runtime acceptance for transactional native camera application."""
from __future__ import annotations

import json
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_ENGINE_RUNTIME"
ROOT = Path(__file__).resolve().parents[2]
DIRECTOR_CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
DRONE_CLASS = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C"
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_engine_application_blueprint_schema.json").read_text(encoding="utf-8"))
CHANNEL_SCHEMA = json.loads((ROOT / "tools/trajectory/camera_channel_assembly_blueprint_schema.json").read_text(encoding="utf-8"))
ENGINE_NAMES = tuple(item["name"] for item in SCHEMA["variables"])
CHANNEL_RESULTS = tuple(item["name"] for item in CHANNEL_SCHEMA["variables"] if item["name"].startswith("CameraChannelResult"))
SAVED_NAMES = tuple(dict.fromkeys((*ENGINE_NAMES, *CHANNEL_RESULTS, "DroneCameraRef")))
AVAILABLE = (True, True, True, True, True, False, True, True, True, False, False, True, True, False, False)
NEUTRAL_CHANNEL = (35.0, 2.8, 1000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
FRAMES = (
    ("runtime_forward", 32.0, 18.0, (48.0, 2.0, 320.0, 1.0, 1.25, 0.2, 0.3, 0.0, 0.0, 0.4, 0.5, 0.0, 0.0)),
    ("runtime_reverse", 44.0, 25.0, (70.0, 5.6, 800.0, 1.0, -0.75, 0.8, 0.6, 0.0, 0.0, 0.1, 0.2, 0.0, 0.0)),
)


def emit(label, value):
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(value, message):
    if not value:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def get(obj, name):
    for candidate in variants(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError(f"missing:{name}")


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(f"cannot-set:{name}")


def clone(value):
    return list(value) if isinstance(value, (list, tuple)) else value


def norm(value):
    return tuple(value) if isinstance(value, (list, tuple)) else value


def close(left, right, tolerance=4e-4):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def struct_text(value):
    exporter = getattr(value, "export_text", None)
    return exporter() if callable(exporter) else str(value)


def camera_component(actor):
    items = actor.get_components_by_class(unreal.CineCameraComponent)
    require(len(items) == 1, f"camera-components:{len(items)}")
    return items[0]


def native_snapshot(camera):
    return (
        struct_text(get(camera, "filmback")),
        float(get(camera, "current_focal_length")),
        float(get(camera, "current_aperture")),
        struct_text(get(camera, "focus_settings")),
        struct_text(get(camera, "post_process_settings")),
    )


def owned_values(camera):
    filmback = get(camera, "filmback")
    focus = get(camera, "focus_settings")
    post = get(camera, "post_process_settings")
    return (
        float(get(filmback, "sensor_width")), float(get(filmback, "sensor_height")),
        float(get(camera, "current_focal_length")), float(get(camera, "current_aperture")),
        float(get(focus, "manual_focus_distance")), float(get(post, "auto_exposure_bias")),
        float(get(post, "bloom_intensity")), float(get(post, "vignette_intensity")),
        float(get(post, "motion_blur_amount")), float(get(post, "scene_fringe_intensity")),
    )


def stage_frame(obj, preset, width, height, values):
    require(len(values) == 13, "frame-shape")
    for name, value in (
        ("CameraChannelResultFilmbackPresetIdV1", preset),
        ("CameraChannelResultFilmbackSensorWidthMmV1", width),
        ("CameraChannelResultFilmbackSensorHeightMmV1", height),
        ("CameraChannelResultValuesV1", list(values)),
        ("CameraChannelResultVelocitiesV1", [0.0] * 13),
        ("CameraChannelResultAccelerationsV1", [0.0] * 13),
        ("CameraChannelResultCompleteV1", True),
        ("CameraChannelResultValidV1", True),
    ):
        set_(obj, name, value)


def assert_applied(camera, width, height, values, label):
    expected = (width, height, values[0], values[1], values[2], values[4], values[5], values[6], values[9], values[10])
    actual = owned_values(camera)
    require(all(close(left, right) for left, right in zip(actual, expected)), f"{label}:native-values:{actual}")
    post = get(camera, "post_process_settings")
    for field in ("override_auto_exposure_bias", "override_bloom_intensity", "override_vignette_intensity", "override_motion_blur_amount", "override_scene_fringe_intensity"):
        require(bool(get(post, field)), f"{label}:{field}")


def exercise(obj, camera, label):
    baseline = native_snapshot(camera)
    baseline_structs = None
    frame_count = 0
    ordered = FRAMES if label.endswith("1") else tuple(reversed(FRAMES))
    for index, (preset, width, height, values) in enumerate(ordered):
        stage_frame(obj, preset, width, height, values)
        staged = tuple(norm(get(obj, name)) for name in CHANNEL_RESULTS)
        obj.call_method("ApplyEvaluatedCameraChannelFrameV1")
        require(tuple(norm(get(obj, name)) for name in CHANNEL_RESULTS) == staged, f"{label}:{index}:inputs")
        require(bool(get(obj, "CameraApplyResultValidV1")), f"{label}:{index}:valid:{get(obj, 'CameraApplyFailureCodeV1')}")
        require(bool(get(obj, "CameraApplySessionActiveV1")), f"{label}:{index}:active")
        frame_count += 1
        require(int(get(obj, "CameraApplyAppliedFrameCountV1")) == frame_count, f"{label}:{index}:count")
        assert_applied(camera, width, height, values, f"{label}:{index}")
        current_baseline = tuple(struct_text(get(obj, name)) for name in (
            "CameraApplyBaselineFilmbackSettingsV1", "CameraApplyBaselineFocusSettingsV1", "CameraApplyBaselinePostProcessSettingsV1"
        ))
        if baseline_structs is None:
            baseline_structs = current_baseline
        else:
            before_capture = (current_baseline, tuple(get(obj, "CameraApplyBaselineTargetValuesV1")))
            obj.call_method("CaptureCameraEngineStateV1")
            after_capture = (
                tuple(struct_text(get(obj, name)) for name in ("CameraApplyBaselineFilmbackSettingsV1", "CameraApplyBaselineFocusSettingsV1", "CameraApplyBaselinePostProcessSettingsV1")),
                tuple(get(obj, "CameraApplyBaselineTargetValuesV1")),
            )
            require(after_capture == before_capture, f"{label}:repeated-capture-overwrote-baseline")

    unsupported = list(NEUTRAL_CHANNEL)
    unsupported[3] = 0.5
    stage_frame(obj, "unsupported_focus_influence", 36.0, 24.0, unsupported)
    staged = tuple(norm(get(obj, name)) for name in CHANNEL_RESULTS)
    before_failure = native_snapshot(camera)
    accepted_count = int(get(obj, "CameraApplyAppliedFrameCountV1"))
    obj.call_method("ApplyEvaluatedCameraChannelFrameV1")
    require(not bool(get(obj, "CameraApplyResultValidV1")), f"{label}:unsupported-accepted")
    require(native_snapshot(camera) == before_failure, f"{label}:unsupported-wrote-camera")
    require(int(get(obj, "CameraApplyAppliedFrameCountV1")) == accepted_count, f"{label}:unsupported-count")
    require(tuple(norm(get(obj, name)) for name in CHANNEL_RESULTS) == staged, f"{label}:unsupported-inputs")
    require("focus_influence" in tuple(str(value) for value in get(obj, "CameraApplyUnavailableTargetIdsV1")), f"{label}:unavailable-diagnostic")

    obj.call_method("RestoreCameraEngineStateV1")
    require(native_snapshot(camera) == baseline, f"{label}:exact-native-restore")
    require(not bool(get(obj, "CameraApplySessionActiveV1")), f"{label}:restore-active")
    after_first = native_snapshot(camera)
    obj.call_method("RestoreCameraEngineStateV1")
    require(native_snapshot(camera) == after_first, f"{label}:repeat-restore-wrote")
    emit("WARM_RUN", f"{label}|frames={frame_count}|unsupported_zero_write=true|exact_restore=true")


director_class = unreal.load_class(None, DIRECTOR_CLASS)
drone_class = unreal.load_class(None, DRONE_CLASS)
require(director_class is not None, "director-class")
require(drone_class is not None, "drone-class")
obj = unreal.get_default_object(director_class)
saved = {name: clone(get(obj, name)) for name in SAVED_NAMES}
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = None
try:
    actor = subsystem.spawn_actor_from_class(drone_class, unreal.Vector(), unreal.Rotator())
    require(actor is not None, "spawn")
    camera = camera_component(actor)
    set_(obj, "DroneCameraRef", actor)
    require(tuple(bool(value) for value in get(obj, "CameraApplyCapabilityAvailableV1")) == AVAILABLE, "capability-manifest")
    for run in (1, 2):
        exercise(obj, camera, f"warm-{run}")
    emit("FORWARD_REVERSE_FRAMES", 4)
    emit("INVALID_FAMILIES", 1)
    emit("RESULT", "PASS")
finally:
    try:
        if bool(get(obj, "CameraApplySessionActiveV1")):
            obj.call_method("RestoreCameraEngineStateV1")
    finally:
        for name, value in saved.items():
            set_(obj, name, value)
        emit("DEFAULTS_RESTORED", all(norm(get(obj, name)) == norm(value) for name, value in saved.items()))
        if actor is not None:
            subsystem.destroy_actor(actor)
            emit("TRANSIENT_DESTROYED", True)
