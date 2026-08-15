"""Transactional adapter from a composed playback frame to native camera state.

The playback composer owns camera intent, while the drone actor, its Cine Camera
component, and the accepted engine-property applicator own native mutation.  This
module freezes the seam between them without collapsing body and gimbal
authorship: body becomes actor world rotation and only ``inverse(body) *
gimbal`` becomes component-relative rotation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence

from camera_channel_assembly_reference import CHANNEL_IDS_V1, CameraFrameStateV1
from camera_engine_application_reference import (
    CameraEngineApplicationError,
    CameraEngineApplicationPlanV1,
    CameraEngineApplicationSessionV1,
    CameraEngineCapabilitySnapshotV1,
    CameraEngineStateSnapshotV1,
    apply_camera_engine_frame_v1,
    begin_camera_engine_application_v1,
    plan_camera_engine_application_v1,
    restore_camera_engine_state_v1,
)
from camera_playback_frame_reference import CameraPlaybackFrameV1
from camera_scalar_track_reference import CameraScalarSample


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
QUATERNION_TOLERANCE = 1.0e-6


class CameraPlaybackNativeApplicationError(ValueError):
    """A complete playback frame cannot cross the native mutation boundary."""

    def __init__(
        self,
        code: str,
        detail: str = "",
        unavailable_target_ids: Sequence[str] = (),
    ) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.unavailable_target_ids = tuple(unavailable_target_ids)


@dataclass(frozen=True)
class CameraNativeTransformStateV1:
    actor_position: Vector3
    actor_world_rotation: Quaternion
    actor_scale: Vector3
    component_relative_position: Vector3
    component_relative_rotation: Quaternion
    component_relative_scale: Vector3


@dataclass(frozen=True)
class CameraPlaybackNativeApplicationPlanV1:
    native_state: CameraNativeTransformStateV1
    engine_plan: CameraEngineApplicationPlanV1


@dataclass(frozen=True)
class CameraPlaybackNativeApplicationSessionV1:
    baseline_native_state: CameraNativeTransformStateV1
    current_native_state: CameraNativeTransformStateV1
    engine_session: CameraEngineApplicationSessionV1
    active: bool
    applied_frame_count: int


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise CameraPlaybackNativeApplicationError(f"{label}_invalid")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraPlaybackNativeApplicationError(f"{label}_invalid") from error
    if not isfinite(result):
        raise CameraPlaybackNativeApplicationError(f"{label}_invalid")
    return result


def _vector(value: Sequence[float], label: str) -> Vector3:
    if len(value) != 3:
        raise CameraPlaybackNativeApplicationError(f"{label}_invalid")
    return tuple(_finite(component, label) for component in value)  # type: ignore[return-value]


def _quat(value: Sequence[float], label: str) -> Quaternion:
    if len(value) != 4:
        raise CameraPlaybackNativeApplicationError(f"{label}_invalid")
    result = tuple(_finite(component, label) for component in value)
    magnitude = sqrt(sum(component * component for component in result))
    if abs(magnitude - 1.0) > QUATERNION_TOLERANCE:
        raise CameraPlaybackNativeApplicationError(f"{label}_invalid")
    return tuple(component / magnitude for component in result)  # type: ignore[return-value]


def _multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return _quat((
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    ), "reconstructed_gimbal")


def _same_rotation(left: Quaternion, right: Quaternion) -> bool:
    return all(abs(a - b) <= QUATERNION_TOLERANCE for a, b in zip(left, right)) or all(
        abs(a + b) <= QUATERNION_TOLERANCE for a, b in zip(left, right)
    )


def validate_camera_native_transform_state_v1(
    state: CameraNativeTransformStateV1,
) -> CameraNativeTransformStateV1:
    actor_scale = _vector(state.actor_scale, "actor_scale")
    component_scale = _vector(state.component_relative_scale, "component_scale")
    if any(abs(value) <= 1.0e-9 for value in (*actor_scale, *component_scale)):
        raise CameraPlaybackNativeApplicationError("native_scale_invalid")
    return CameraNativeTransformStateV1(
        _vector(state.actor_position, "actor_position"),
        _quat(state.actor_world_rotation, "actor_rotation"),
        actor_scale,
        _vector(state.component_relative_position, "component_position"),
        _quat(state.component_relative_rotation, "component_rotation"),
        component_scale,
    )


def camera_engine_frame_from_playback_v1(
    frame: CameraPlaybackFrameV1,
    playback_result_valid: bool,
) -> CameraFrameStateV1:
    """Value-copy the final filmback/channels; never read compiled sources."""

    if playback_result_valid is not True:
        raise CameraPlaybackNativeApplicationError("playback_frame_invalid")
    position = _vector(frame.position, "playback_position")
    body = _quat(frame.body_world_rotation, "playback_body")
    gimbal = _quat(frame.gimbal_world_rotation, "playback_gimbal")
    relative = _quat(frame.gimbal_relative_rotation, "playback_relative")
    if not _same_rotation(_multiply(body, relative), gimbal):
        raise CameraPlaybackNativeApplicationError("playback_pose_reconstruction_failed")
    if len(frame.camera_channel_values) != len(CHANNEL_IDS_V1):
        raise CameraPlaybackNativeApplicationError("playback_channel_shape_invalid")
    values = tuple(
        _finite(value, f"playback_{channel_id}")
        for channel_id, value in zip(CHANNEL_IDS_V1, frame.camera_channel_values)
    )
    samples = tuple(
        (
            channel_id,
            CameraScalarSample(value, 0.0, 0.0, 0, 0.0, bool(frame.complete)),
        )
        for channel_id, value in zip(CHANNEL_IDS_V1, values)
    )
    # Position/quaternion validation above is deliberately part of this single
    # preflight even though only channel data crosses into the engine helper.
    _ = position
    return CameraFrameStateV1(
        _finite(frame.elapsed_seconds, "playback_elapsed"),
        bool(frame.complete),
        frame.filmback,
        *values,
        samples,
    )


def begin_camera_playback_native_application_v1(
    current_native_state: CameraNativeTransformStateV1,
    current_engine_state: CameraEngineStateSnapshotV1,
    capabilities: CameraEngineCapabilitySnapshotV1,
    drone_available: bool,
    existing_session: CameraPlaybackNativeApplicationSessionV1 | None = None,
) -> CameraPlaybackNativeApplicationSessionV1:
    """Capture actor/component and engine baselines once per playback session."""

    if drone_available is not True:
        raise CameraPlaybackNativeApplicationError("drone_camera_unavailable")
    validate_camera_native_transform_state_v1(current_native_state)
    # Validation may normalize a quaternion for comparison, but the captured
    # native Transform must remain a verbatim baseline for exact restoration.
    native = current_native_state
    try:
        engine = begin_camera_engine_application_v1(
            current_engine_state,
            capabilities,
            existing_session.engine_session if existing_session and existing_session.active else None,
        )
    except CameraEngineApplicationError as error:
        raise CameraPlaybackNativeApplicationError(
            "engine_capture_failed", error.code, error.unavailable_target_ids
        ) from error
    if existing_session is not None and existing_session.active:
        return existing_session
    return CameraPlaybackNativeApplicationSessionV1(native, native, engine, True, 0)


def plan_camera_playback_native_application_v1(
    session: CameraPlaybackNativeApplicationSessionV1,
    frame: CameraPlaybackFrameV1,
    playback_result_valid: bool,
    drone_available: bool,
) -> CameraPlaybackNativeApplicationPlanV1:
    """Complete pose and lens preflight before the first native write."""

    if not session.active or not session.engine_session.active:
        raise CameraPlaybackNativeApplicationError("native_application_session_inactive")
    if drone_available is not True:
        raise CameraPlaybackNativeApplicationError("drone_camera_unavailable")
    engine_frame = camera_engine_frame_from_playback_v1(frame, playback_result_valid)
    body = _quat(frame.body_world_rotation, "playback_body")
    relative = _quat(frame.gimbal_relative_rotation, "playback_relative")
    current = validate_camera_native_transform_state_v1(session.current_native_state)
    native = CameraNativeTransformStateV1(
        _vector(frame.position, "playback_position"),
        body,
        current.actor_scale,
        current.component_relative_position,
        relative,
        current.component_relative_scale,
    )
    try:
        engine_plan = plan_camera_engine_application_v1(session.engine_session, engine_frame)
    except CameraEngineApplicationError as error:
        raise CameraPlaybackNativeApplicationError(
            "engine_preflight_failed", error.code, error.unavailable_target_ids
        ) from error
    return CameraPlaybackNativeApplicationPlanV1(native, engine_plan)


def apply_camera_playback_native_frame_v1(
    session: CameraPlaybackNativeApplicationSessionV1,
    frame: CameraPlaybackFrameV1,
    playback_result_valid: bool,
    drone_available: bool,
) -> CameraPlaybackNativeApplicationSessionV1:
    """Apply one fully preflighted pose/lens frame as one logical transaction."""

    plan = plan_camera_playback_native_application_v1(
        session, frame, playback_result_valid, drone_available
    )
    engine_frame = camera_engine_frame_from_playback_v1(frame, playback_result_valid)
    try:
        engine = apply_camera_engine_frame_v1(session.engine_session, engine_frame)
    except CameraEngineApplicationError as error:  # defensive: plan already passed
        raise CameraPlaybackNativeApplicationError(
            "engine_apply_failed", error.code, error.unavailable_target_ids
        ) from error
    return CameraPlaybackNativeApplicationSessionV1(
        session.baseline_native_state,
        plan.native_state,
        engine,
        True,
        session.applied_frame_count + 1,
    )


def restore_camera_playback_native_application_v1(
    session: CameraPlaybackNativeApplicationSessionV1,
) -> CameraPlaybackNativeApplicationSessionV1:
    """Restore the exact pre-playback actor/component/lens baseline, idempotently."""

    if not session.active:
        return session
    return CameraPlaybackNativeApplicationSessionV1(
        session.baseline_native_state,
        session.baseline_native_state,
        restore_camera_engine_state_v1(session.engine_session),
        False,
        session.applied_frame_count,
    )
