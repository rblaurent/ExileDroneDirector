"""Deterministic viewer-local comfort composition for one evaluated frame.

This helper is downstream of authored body/gimbal evaluation, procedural
offsets, named looks, and camera-channel evaluation. It never rewrites any of
those sources; it publishes one local final pose/value frame for this viewer.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence

from camera_channel_assembly_reference import CHANNEL_POLICIES_V1
from orientation_reference import multiply, normalize, slerp


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
IDENTITY_QUATERNION: Quaternion = (0.0, 0.0, 0.0, 1.0)
QUATERNION_TOLERANCE = 1.0e-6
VECTOR_EPSILON = 1.0e-9
CHANNEL_IDS_V1 = tuple(policy.channel_id for policy in CHANNEL_POLICIES_V1)
COMFORT_WEIGHT_IDS_V1 = ("roll", "shake", "blur", "exposure_change", "chromatic_aberration")
_CHANNEL_INDEX = {channel_id: index for index, channel_id in enumerate(CHANNEL_IDS_V1)}


class CameraViewerComfortError(ValueError):
    """The local comfort request cannot publish a complete frame."""


@dataclass(frozen=True)
class CameraViewerComfortSettingsV1:
    enabled: bool = False
    roll_weight: float = 1.0
    shake_weight: float = 1.0
    blur_weight: float = 1.0
    exposure_change_weight: float = 1.0
    chromatic_aberration_weight: float = 1.0


@dataclass(frozen=True)
class CameraViewerComfortFrameV1:
    position: Vector3
    gimbal_rotation: Quaternion
    camera_channel_values: tuple[float, ...]
    effective_weights: tuple[float, ...]
    comfort_applied: bool


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise CameraViewerComfortError(f"{label}_not_numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraViewerComfortError(f"{label}_not_numeric") from error
    if not isfinite(result):
        raise CameraViewerComfortError(f"{label}_not_finite")
    return result


def _vector(value: object, label: str) -> Vector3:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise CameraViewerComfortError(f"{label}_shape")
    return tuple(_number(component, label) for component in value)  # type: ignore[return-value]


def _quaternion(value: object, label: str) -> Quaternion:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise CameraViewerComfortError(f"{label}_shape")
    result = tuple(_number(component, label) for component in value)
    magnitude = sqrt(sum(component * component for component in result))
    if abs(magnitude - 1.0) > QUATERNION_TOLERANCE:
        raise CameraViewerComfortError(f"{label}_not_normalized")
    return normalize(result)  # type: ignore[arg-type]


def _weight(value: object, label: str) -> float:
    result = _number(value, label)
    if result < 0.0 or result > 1.0:
        raise CameraViewerComfortError(f"{label}_outside_normalized_range")
    return result


def _rotate(quaternion: Quaternion, vector: Vector3) -> Vector3:
    rotated = multiply(multiply(quaternion, (vector[0], vector[1], vector[2], 0.0)),
                       (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3]))
    return (rotated[0], rotated[1], rotated[2])


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0])


def _length(value: Vector3) -> float:
    return sqrt(_dot(value, value))


def _scale(value: Vector3, factor: float) -> Vector3:
    return tuple(component * factor for component in value)  # type: ignore[return-value]


def _unit(value: Vector3, fallback: Vector3) -> Vector3:
    magnitude = _length(value)
    return _scale(value, 1.0 / magnitude) if magnitude > VECTOR_EPSILON else fallback


def _level_orientation(forward: Vector3, authored_up: Vector3) -> Quaternion:
    """Mirror MakeRotFromXZ with world-up and a deterministic vertical fallback."""

    x_axis = _unit(forward, (1.0, 0.0, 0.0))
    world_up = (0.0, 0.0, 1.0)
    y_axis = _cross(world_up, x_axis)
    if _length(y_axis) <= VECTOR_EPSILON:
        projection = _dot(authored_up, x_axis)
        projected_up = tuple(authored_up[index] - x_axis[index] * projection for index in range(3))
        if _length(projected_up) <= VECTOR_EPSILON:
            projected_up = (1.0, 0.0, 0.0)
        z_axis = _unit(projected_up, (1.0, 0.0, 0.0))
        y_axis = _unit(_cross(z_axis, x_axis), (0.0, 1.0, 0.0))
        z_axis = _unit(_cross(x_axis, y_axis), z_axis)
    else:
        y_axis = _unit(y_axis, (0.0, 1.0, 0.0))
        z_axis = _unit(_cross(x_axis, y_axis), world_up)

    m00, m01, m02 = x_axis[0], y_axis[0], z_axis[0]
    m10, m11, m12 = x_axis[1], y_axis[1], z_axis[1]
    m20, m21, m22 = x_axis[2], y_axis[2], z_axis[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        factor = sqrt(trace + 1.0) * 2.0
        result = ((m21 - m12) / factor, (m02 - m20) / factor, (m10 - m01) / factor, 0.25 * factor)
    elif m00 > m11 and m00 > m22:
        factor = sqrt(1.0 + m00 - m11 - m22) * 2.0
        result = (0.25 * factor, (m01 + m10) / factor, (m02 + m20) / factor, (m21 - m12) / factor)
    elif m11 > m22:
        factor = sqrt(1.0 + m11 - m00 - m22) * 2.0
        result = ((m01 + m10) / factor, 0.25 * factor, (m12 + m21) / factor, (m02 - m20) / factor)
    else:
        factor = sqrt(1.0 + m22 - m00 - m11) * 2.0
        result = ((m02 + m20) / factor, (m12 + m21) / factor, 0.25 * factor, (m10 - m01) / factor)
    return normalize(result)


def _validated_channels(values: Sequence[float]) -> tuple[float, ...]:
    source = tuple(values)
    if len(source) != len(CHANNEL_POLICIES_V1):
        raise CameraViewerComfortError("camera_channel_shape")
    result: list[float] = []
    for policy, value in zip(CHANNEL_POLICIES_V1, source):
        accepted = _number(value, policy.channel_id)
        if policy.minimum is not None and accepted < policy.minimum:
            raise CameraViewerComfortError(f"{policy.channel_id}_below_minimum")
        if policy.maximum is not None and accepted > policy.maximum:
            raise CameraViewerComfortError(f"{policy.channel_id}_above_maximum")
        result.append(accepted)
    return tuple(result)


def apply_camera_viewer_comfort_v1(
    frame_valid: bool,
    position: Vector3,
    gimbal_rotation: Quaternion,
    procedural_translation_offset: Vector3,
    procedural_rotation_offset: Quaternion,
    camera_channel_values: Sequence[float],
    settings: CameraViewerComfortSettingsV1,
) -> CameraViewerComfortFrameV1:
    """Publish one local, non-authoritative comfort-adjusted camera frame."""

    if frame_valid is not True:
        raise CameraViewerComfortError("input_frame_invalid")
    if not isinstance(settings, CameraViewerComfortSettingsV1) or not isinstance(settings.enabled, bool):
        raise CameraViewerComfortError("comfort_settings_shape")
    authored_position = _vector(position, "position")
    authored_gimbal = _quaternion(gimbal_rotation, "gimbal_rotation")
    shake_translation = _vector(procedural_translation_offset, "procedural_translation_offset")
    shake_rotation = _quaternion(procedural_rotation_offset, "procedural_rotation_offset")
    channels = list(_validated_channels(camera_channel_values))
    authored_weights = (
        _weight(settings.roll_weight, "roll_weight"),
        _weight(settings.shake_weight, "shake_weight"),
        _weight(settings.blur_weight, "blur_weight"),
        _weight(settings.exposure_change_weight, "exposure_change_weight"),
        _weight(settings.chromatic_aberration_weight, "chromatic_aberration_weight"),
    )
    effective = authored_weights if settings.enabled else (1.0,) * len(COMFORT_WEIGHT_IDS_V1)
    roll_weight, shake_weight, blur_weight, exposure_weight, chromatic_weight = effective

    final_position = tuple(authored_position[index] + shake_translation[index] * shake_weight for index in range(3))
    scaled_shake = slerp(IDENTITY_QUATERNION, shake_rotation, shake_weight)
    shaken_gimbal = normalize(multiply(authored_gimbal, scaled_shake))
    forward = _rotate(shaken_gimbal, (1.0, 0.0, 0.0))
    authored_up = _rotate(shaken_gimbal, (0.0, 0.0, 1.0))
    level = _level_orientation(forward, authored_up)
    final_gimbal = slerp(level, shaken_gimbal, roll_weight)

    channels[_CHANNEL_INDEX["focus_influence"]] *= blur_weight
    channels[_CHANNEL_INDEX["motion_blur_weight"]] *= blur_weight
    channels[_CHANNEL_INDEX["exposure_ev"]] *= exposure_weight
    channels[_CHANNEL_INDEX["chromatic_aberration_weight"]] *= chromatic_weight
    return CameraViewerComfortFrameV1(
        position=final_position,  # type: ignore[arg-type]
        gimbal_rotation=normalize(final_gimbal),
        camera_channel_values=tuple(channels),
        effective_weights=effective,
        comfort_applied=settings.enabled and any(weight < 1.0 for weight in effective),
    )
