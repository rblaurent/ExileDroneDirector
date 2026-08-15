"""Deterministic composition of one complete directed-camera playback frame.

This boundary evaluates the already-compiled position, airframe/gimbal,
carrier-frame, and camera-channel tracks at one absolute time.  It then applies
viewer-local operator input and comfort policy without ever treating the
legacy cinematic-pose rotation as body or gimbal authorship.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence

from airframe_gimbal_prebake_reference import (
    AirframeGimbalPrebakeError,
    CompiledAirframeGimbalMotion,
    evaluate_airframe_gimbal_motion,
)
from camera_channel_assembly_reference import (
    CHANNEL_IDS_V1,
    CameraChannelAssemblyError,
    CompiledCameraChannelAssemblyV1,
    FilmbackSnapshotV1,
    evaluate_camera_channel_assembly_v1,
)
from camera_operator_override_reference import (
    CameraOperatorOverrideError,
    CameraOperatorPolicyV1,
    CameraOperatorStateV1,
    apply_camera_operator_override_v1,
)
from camera_viewer_comfort_reference import (
    CameraViewerComfortError,
    CameraViewerComfortSettingsV1,
    apply_camera_viewer_comfort_v1,
)
from carrier_frame_transport_reference import (
    CarrierFrameTransportError,
    CompiledCarrierFrameTransportV1,
    evaluate_carrier_frame_transport_v1,
)
from cinematic_pose_reference import (
    CinematicPoseError,
    CompiledCinematicPose,
    evaluate_cinematic_pose,
)


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


class CameraPlaybackFrameError(ValueError):
    """The complete playback frame could not be published."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CameraPlaybackFrameV1:
    elapsed_seconds: float
    complete: bool
    position: Vector3
    body_world_rotation: Quaternion
    gimbal_world_rotation: Quaternion
    gimbal_relative_rotation: Quaternion
    filmback: FilmbackSnapshotV1
    camera_channel_values: tuple[float, ...]
    operator_state: CameraOperatorStateV1
    operator_mode: str
    operator_override_active: bool
    operator_transition_active: bool
    operator_tether_applied: bool
    comfort_effective_weights: tuple[float, ...]
    comfort_applied: bool


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise CameraPlaybackFrameError(f"{label}_invalid")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraPlaybackFrameError(f"{label}_invalid") from error
    if not isfinite(result):
        raise CameraPlaybackFrameError(f"{label}_invalid")
    return result


def _unit_quaternion(value: Sequence[float], label: str) -> Quaternion:
    if len(value) != 4:
        raise CameraPlaybackFrameError(f"{label}_invalid")
    result = tuple(_finite_number(component, label) for component in value)
    magnitude = sqrt(sum(component * component for component in result))
    if abs(magnitude - 1.0) > 1.0e-6:
        raise CameraPlaybackFrameError(f"{label}_invalid")
    return tuple(component / magnitude for component in result)  # type: ignore[return-value]


def _multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return _unit_quaternion((
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    ), "composed_gimbal")


def _inverse(value: Quaternion) -> Quaternion:
    x, y, z, w = _unit_quaternion(value, "body_rotation")
    return (-x, -y, -z, w)


def _channel_values(frame: object) -> tuple[float, ...]:
    return tuple(float(getattr(frame, channel_id)) for channel_id in CHANNEL_IDS_V1)


def evaluate_camera_playback_frame_v1(
    cinematic_pose: CompiledCinematicPose,
    airframe_motion: CompiledAirframeGimbalMotion,
    carrier_frame: CompiledCarrierFrameTransportV1,
    camera_channels: CompiledCameraChannelAssemblyV1,
    elapsed_seconds: float,
    delta_seconds: float,
    requested_mode: str,
    translation_input: Vector3,
    look_input: Vector3,
    recenter_requested: bool,
    return_to_directed_requested: bool,
    operator_policy: CameraOperatorPolicyV1,
    previous_operator_state: CameraOperatorStateV1,
    procedural_translation_offset: Vector3,
    procedural_rotation_offset: Quaternion,
    comfort_settings: CameraViewerComfortSettingsV1,
) -> CameraPlaybackFrameV1:
    """Evaluate and atomically compose one local camera frame.

    The cinematic orientation is intentionally evaluated only as part of its
    accepted pose transaction.  It is never used as body or gimbal authorship.
    """

    elapsed = _finite_number(elapsed_seconds, "elapsed_seconds")
    delta = _finite_number(delta_seconds, "delta_seconds")
    totals = (
        cinematic_pose.total_seconds,
        airframe_motion.total_seconds,
        carrier_frame.total_seconds,
        camera_channels.duration_seconds,
    )
    if any(not isfinite(float(value)) or float(value) <= 0.0 for value in totals):
        raise CameraPlaybackFrameError("timeline_invalid")
    if len(set(float(value) for value in totals)) != 1:
        raise CameraPlaybackFrameError("timeline_mismatch")

    try:
        pose = evaluate_cinematic_pose(cinematic_pose, elapsed)
        airframe = evaluate_airframe_gimbal_motion(airframe_motion, elapsed)
        carrier = evaluate_carrier_frame_transport_v1(carrier_frame, elapsed)
        channels = evaluate_camera_channel_assembly_v1(camera_channels, elapsed)
    except (
        AirframeGimbalPrebakeError,
        CameraChannelAssemblyError,
        CarrierFrameTransportError,
        CinematicPoseError,
        TypeError,
        ValueError,
    ) as error:
        raise CameraPlaybackFrameError("source_evaluation_failed") from error
    if (not airframe.valid or airframe.body_rotation is None or
            airframe.gimbal_rotation is None or not carrier.valid or
            carrier.rotation is None):
        raise CameraPlaybackFrameError("source_invalid")
    completion = (pose.complete, airframe.complete, carrier.complete, channels.complete)
    if len(set(completion)) != 1:
        raise CameraPlaybackFrameError("completion_mismatch")

    try:
        operator = apply_camera_operator_override_v1(
            True,
            requested_mode,
            pose.position,
            airframe.body_rotation,
            airframe.gimbal_rotation,
            carrier.rotation,
            translation_input,
            look_input,
            delta,
            recenter_requested,
            return_to_directed_requested,
            operator_policy,
            previous_operator_state,
        )
    except CameraOperatorOverrideError as error:
        raise CameraPlaybackFrameError("operator_invalid") from error

    try:
        comfort = apply_camera_viewer_comfort_v1(
            True,
            operator.position,
            operator.gimbal_rotation,
            procedural_translation_offset,
            procedural_rotation_offset,
            _channel_values(channels),
            comfort_settings,
        )
    except CameraViewerComfortError as error:
        raise CameraPlaybackFrameError("comfort_invalid") from error

    body = _unit_quaternion(operator.body_rotation, "body_rotation")
    gimbal_world = _unit_quaternion(comfort.gimbal_rotation, "gimbal_rotation")
    gimbal_relative = _multiply(_inverse(body), gimbal_world)
    if any(abs(a - b) > 1.0e-6 for a, b in zip(_multiply(body, gimbal_relative), gimbal_world)):
        raise CameraPlaybackFrameError("final_pose_invalid")
    return CameraPlaybackFrameV1(
        elapsed_seconds=elapsed,
        complete=completion[0],
        position=comfort.position,
        body_world_rotation=body,
        gimbal_world_rotation=gimbal_world,
        gimbal_relative_rotation=gimbal_relative,
        filmback=channels.filmback,
        camera_channel_values=comfort.camera_channel_values,
        operator_state=operator.state,
        operator_mode=operator.state.mode,
        operator_override_active=operator.override_active,
        operator_transition_active=operator.transition_active,
        operator_tether_applied=operator.tether_applied,
        comfort_effective_weights=comfort.effective_weights,
        comfort_applied=comfort.comfort_applied,
    )
