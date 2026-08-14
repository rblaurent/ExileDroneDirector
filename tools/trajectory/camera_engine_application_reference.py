"""Engine-neutral camera-frame application and restoration oracle.

The camera-channel evaluator deliberately stops at a complete numeric frame.
This module freezes the next boundary: a probed engine capability manifest,
preflight that happens before any camera mutation, one non-overwriting baseline
capture per playback session, deterministic application, and exact restoration.

The oracle does not pretend that every desired effect maps to an Unreal
property.  A target is writable only when the frozen capability manifest says
so.  An unavailable optional target may be skipped only when the desired value
is neutral; it has no concrete engine field to inspect or mutate.  Hidden
post-process override state is represented inside an opaque whole-struct
snapshot, never as a Blueprint-readable Boolean array.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from camera_channel_assembly_reference import (
    CHANNEL_IDS_V1,
    CHANNEL_POLICIES_V1,
    CameraFrameStateV1,
)


class CameraEngineApplicationError(ValueError):
    """A camera frame cannot be applied without violating the adapter contract."""

    def __init__(self, code: str, unavailable_target_ids: Sequence[str] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.unavailable_target_ids = tuple(unavailable_target_ids)


FILMBACK_TARGET_IDS_V1 = (
    "filmback_sensor_width_mm",
    "filmback_sensor_height_mm",
)
TARGET_IDS_V1 = FILMBACK_TARGET_IDS_V1 + CHANNEL_IDS_V1
TARGET_COUNT_V1 = len(TARGET_IDS_V1)
REQUIRED_TARGET_IDS_V1 = (
    "filmback_sensor_width_mm",
    "filmback_sensor_height_mm",
    "focal_length_mm",
    "aperture_fstop",
    "focus_distance_cm",
)
POST_PROCESS_OVERRIDE_TARGET_IDS_V1 = (
    "exposure_ev",
    "bloom_weight",
    "vignette_weight",
    "color_grading_weight",
    "tint_weight",
    "motion_blur_weight",
    "chromatic_aberration_weight",
    "sharpening_weight",
    "matte_weight",
)
NEUTRAL_TARGET_VALUES_V1 = (
    36.0,
    24.0,
    *(policy.default_value for policy in CHANNEL_POLICIES_V1),
)
_TARGET_INDEX = {target_id: index for index, target_id in enumerate(TARGET_IDS_V1)}
_POLICY_BY_ID = {policy.channel_id: policy for policy in CHANNEL_POLICIES_V1}
_POST_PROCESS_FIELDS_V1 = {
    "exposure_ev": "AutoExposureBias",
    "bloom_weight": "BloomIntensity",
    "vignette_weight": "VignetteIntensity",
    "motion_blur_weight": "MotionBlurAmount",
    "chromatic_aberration_weight": "SceneFringeIntensity",
}


@dataclass(frozen=True)
class CameraEngineCapabilitySnapshotV1:
    engine_version: str
    manifest_id: str
    target_ids: tuple[str, ...]
    available: tuple[bool, ...]


@dataclass(frozen=True)
class CameraEngineNativeStructSnapshotV1:
    """Exact native struct payloads, including fields Blueprint cannot split."""

    filmback: tuple[tuple[str, object], ...]
    focus: tuple[tuple[str, object], ...]
    post_process: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class CameraEngineStateSnapshotV1:
    filmback_preset_id: str
    target_values: tuple[float, ...]
    native_structs: CameraEngineNativeStructSnapshotV1


@dataclass(frozen=True)
class CameraEngineApplicationPlanV1:
    filmback_preset_id: str
    target_values: tuple[float, ...]
    write_mask: tuple[bool, ...]
    owned_post_process_mask: tuple[bool, ...]
    unavailable_target_ids: tuple[str, ...]


@dataclass(frozen=True)
class CameraEngineApplicationSessionV1:
    capabilities: CameraEngineCapabilitySnapshotV1
    baseline: CameraEngineStateSnapshotV1
    current: CameraEngineStateSnapshotV1
    active: bool
    applied_frame_count: int
    last_unavailable_target_ids: tuple[str, ...] = ()


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise CameraEngineApplicationError(f"invalid_{field}")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraEngineApplicationError(f"invalid_{field}") from error
    if not isfinite(result):
        raise CameraEngineApplicationError(f"invalid_{field}")
    return result


def validate_camera_engine_capabilities_v1(
    capabilities: CameraEngineCapabilitySnapshotV1,
) -> CameraEngineCapabilitySnapshotV1:
    if not isinstance(capabilities.engine_version, str) or not capabilities.engine_version.strip():
        raise CameraEngineApplicationError("invalid_engine_version")
    if not isinstance(capabilities.manifest_id, str) or not capabilities.manifest_id.strip():
        raise CameraEngineApplicationError("invalid_manifest_id")
    if capabilities.target_ids != TARGET_IDS_V1:
        raise CameraEngineApplicationError("invalid_capability_target_order")
    if len(capabilities.available) != TARGET_COUNT_V1 or any(
        not isinstance(value, bool) for value in capabilities.available
    ):
        raise CameraEngineApplicationError("invalid_capability_shape")
    missing_required = tuple(
        target_id
        for target_id in REQUIRED_TARGET_IDS_V1
        if not capabilities.available[_TARGET_INDEX[target_id]]
    )
    if missing_required:
        raise CameraEngineApplicationError("required_target_unavailable", missing_required)
    return capabilities


def validate_camera_engine_state_v1(
    state: CameraEngineStateSnapshotV1,
) -> CameraEngineStateSnapshotV1:
    if not isinstance(state.filmback_preset_id, str) or not state.filmback_preset_id.strip():
        raise CameraEngineApplicationError("invalid_state_filmback_id")
    if len(state.target_values) != TARGET_COUNT_V1:
        raise CameraEngineApplicationError("invalid_state_value_shape")
    if not isinstance(state.native_structs, CameraEngineNativeStructSnapshotV1):
        raise CameraEngineApplicationError("invalid_native_struct_snapshot")
    for field, payload in (
        ("filmback", state.native_structs.filmback),
        ("focus", state.native_structs.focus),
        ("post_process", state.native_structs.post_process),
    ):
        if not isinstance(payload, tuple) or any(
            not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str)
            for item in payload
        ):
            raise CameraEngineApplicationError(f"invalid_native_{field}_snapshot")
        if len({item[0] for item in payload}) != len(payload):
            raise CameraEngineApplicationError(f"duplicate_native_{field}_field")
    values = tuple(_finite(value, f"state_{TARGET_IDS_V1[index]}") for index, value in enumerate(state.target_values))
    if values[0] <= 0.0 or values[1] <= 0.0:
        raise CameraEngineApplicationError("invalid_state_filmback_dimensions")
    return CameraEngineStateSnapshotV1(
        state.filmback_preset_id,
        values,
        state.native_structs,
    )


def camera_frame_target_values_v1(frame: CameraFrameStateV1) -> tuple[float, ...]:
    """Validate a published channel frame and return canonical engine values."""

    if not isinstance(frame.filmback.preset_id, str) or not frame.filmback.preset_id.strip():
        raise CameraEngineApplicationError("invalid_frame_filmback_id")
    width = _finite(frame.filmback.sensor_width_mm, "frame_filmback_width")
    height = _finite(frame.filmback.sensor_height_mm, "frame_filmback_height")
    if width <= 0.0 or height <= 0.0:
        raise CameraEngineApplicationError("invalid_frame_filmback_dimensions")
    if tuple(channel_id for channel_id, _sample in frame.samples) != CHANNEL_IDS_V1:
        raise CameraEngineApplicationError("invalid_frame_sample_order")

    channel_values: list[float] = []
    for channel_id, sample in frame.samples:
        value = _finite(getattr(frame, channel_id), f"frame_{channel_id}")
        if value != _finite(sample.value, f"sample_{channel_id}_value"):
            raise CameraEngineApplicationError("frame_sample_value_mismatch")
        _finite(sample.velocity, f"sample_{channel_id}_velocity")
        _finite(sample.acceleration, f"sample_{channel_id}_acceleration")
        policy = _POLICY_BY_ID[channel_id]
        if policy.minimum is not None and value < policy.minimum:
            raise CameraEngineApplicationError(f"frame_{channel_id}_below_minimum")
        if policy.maximum is not None and value > policy.maximum:
            raise CameraEngineApplicationError(f"frame_{channel_id}_above_maximum")
        channel_values.append(value)
    return (width, height, *channel_values)


def begin_camera_engine_application_v1(
    current_state: CameraEngineStateSnapshotV1,
    capabilities: CameraEngineCapabilitySnapshotV1,
    existing_session: CameraEngineApplicationSessionV1 | None = None,
) -> CameraEngineApplicationSessionV1:
    """Capture the viewer baseline once; repeated begin cannot overwrite it."""

    accepted_capabilities = validate_camera_engine_capabilities_v1(capabilities)
    if existing_session is not None and existing_session.active:
        if existing_session.capabilities != accepted_capabilities:
            raise CameraEngineApplicationError("capabilities_changed_during_session")
        return existing_session
    baseline = validate_camera_engine_state_v1(current_state)
    return CameraEngineApplicationSessionV1(
        accepted_capabilities,
        baseline,
        baseline,
        True,
        0,
        (),
    )


def plan_camera_engine_application_v1(
    session: CameraEngineApplicationSessionV1,
    frame: CameraFrameStateV1,
) -> CameraEngineApplicationPlanV1:
    if not session.active:
        raise CameraEngineApplicationError("application_session_inactive")
    capabilities = validate_camera_engine_capabilities_v1(session.capabilities)
    current = validate_camera_engine_state_v1(session.current)
    target_values = camera_frame_target_values_v1(frame)
    unavailable = tuple(
        target_id
        for index, target_id in enumerate(TARGET_IDS_V1)
        if not capabilities.available[index]
    )

    unsafe_unavailable = tuple(
        target_id
        for target_id in unavailable
        if (
            target_values[_TARGET_INDEX[target_id]] != NEUTRAL_TARGET_VALUES_V1[_TARGET_INDEX[target_id]]
        )
    )
    if unsafe_unavailable:
        raise CameraEngineApplicationError("requested_target_unavailable", unsafe_unavailable)

    write_mask = capabilities.available
    owned_post_process_mask = tuple(
        available and target_id in POST_PROCESS_OVERRIDE_TARGET_IDS_V1
        for target_id, available in zip(TARGET_IDS_V1, capabilities.available)
    )
    return CameraEngineApplicationPlanV1(
        frame.filmback.preset_id,
        target_values,
        write_mask,
        owned_post_process_mask,
        unavailable,
    )


def apply_camera_engine_frame_v1(
    session: CameraEngineApplicationSessionV1,
    frame: CameraFrameStateV1,
) -> CameraEngineApplicationSessionV1:
    """Apply one frame after complete preflight; failures leave session untouched."""

    plan = plan_camera_engine_application_v1(session, frame)
    values = list(session.current.target_values)
    for index, should_write in enumerate(plan.write_mask):
        if should_write:
            values[index] = plan.target_values[index]

    def replace_fields(
        payload: tuple[tuple[str, object], ...], updates: dict[str, object]
    ) -> tuple[tuple[str, object], ...]:
        result = dict(payload)
        result.update(updates)
        return tuple(sorted(result.items()))

    native = session.current.native_structs
    filmback_updates = {
        "SensorWidth": plan.target_values[0],
        "SensorHeight": plan.target_values[1],
    }
    focus_updates = {"ManualFocusDistance": plan.target_values[_TARGET_INDEX["focus_distance_cm"]]}
    post_process_updates: dict[str, object] = {}
    for target_id, field in _POST_PROCESS_FIELDS_V1.items():
        index = _TARGET_INDEX[target_id]
        if plan.write_mask[index]:
            post_process_updates[field] = plan.target_values[index]
            post_process_updates[f"bOverride_{field}"] = True
    current_native = CameraEngineNativeStructSnapshotV1(
        replace_fields(native.filmback, filmback_updates),
        replace_fields(native.focus, focus_updates),
        replace_fields(native.post_process, post_process_updates),
    )
    current = CameraEngineStateSnapshotV1(
        plan.filmback_preset_id,
        tuple(values),
        current_native,
    )
    return CameraEngineApplicationSessionV1(
        session.capabilities,
        session.baseline,
        current,
        True,
        session.applied_frame_count + 1,
        plan.unavailable_target_ids,
    )


def restore_camera_engine_state_v1(
    session: CameraEngineApplicationSessionV1,
) -> CameraEngineApplicationSessionV1:
    """Restore the exact baseline. Repeated restore is stable and write-free."""

    if not session.active:
        return session
    return CameraEngineApplicationSessionV1(
        session.capabilities,
        session.baseline,
        session.baseline,
        False,
        session.applied_frame_count,
        (),
    )
