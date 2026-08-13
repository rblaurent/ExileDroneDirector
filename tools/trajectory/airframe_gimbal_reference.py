"""Deterministic instantaneous airframe and gimbal desired-pose solver.

The solver is deliberately stateless.  Its velocity, look-ahead velocity,
acceleration, and jerk inputs are sampled from the accepted absolute-time
trajectory.  A later fixed-step compiler owns angular-rate limiting; this
primitive owns only the desired pose and the per-sample physical gates.

Coordinates follow the Unreal convention used by the mod: local X is forward,
local Y is right, and local Z is up.  Positive camera uptilt raises local X.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, isfinite, radians, sin, sqrt

from orientation_reference import multiply, normalize, slerp


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
EPSILON = 1.0e-9
QUATERNION_TOLERANCE = 1.0e-6
GRAVITY_CM_PER_SECOND_SQUARED = 980.665
STRAIGHT_TURN_RADIUS_CM = 0.0


class AirframeGimbalError(ValueError):
    """The requested desired pose is unsafe or structurally invalid."""


@dataclass(frozen=True)
class AirframeGimbalProfile:
    path_follow_weight: float
    horizon_stabilization_weight: float
    look_ahead_seconds: float
    bank_gain: float
    max_bank_degrees: float
    camera_uptilt_degrees: float
    max_angular_rate_degrees_per_second: float
    max_acceleration_cm_per_second_squared: float
    max_jerk_cm_per_second_cubed: float
    minimum_turn_radius_cm: float


@dataclass(frozen=True)
class AirframeGimbalEvaluation:
    body_rotation: Quaternion
    gimbal_rotation: Quaternion
    path_rotation: Quaternion
    speed_cm_per_second: float
    lateral_acceleration_cm_per_second_squared: float
    turn_radius_cm: float
    bank_degrees: float


def _vector(value: object, label: str) -> Vector3:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise AirframeGimbalError(f"{label} must contain three components")
    if any(isinstance(component, bool) for component in value):
        raise AirframeGimbalError(f"{label} must contain numeric components, not booleans")
    result = tuple(float(component) for component in value)
    if not all(isfinite(component) for component in result):
        raise AirframeGimbalError(f"{label} must be finite")
    return result  # type: ignore[return-value]


def _quaternion(value: object, label: str) -> Quaternion:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise AirframeGimbalError(f"{label} must contain four components")
    if any(isinstance(component, bool) for component in value):
        raise AirframeGimbalError(f"{label} must contain numeric components, not booleans")
    result = tuple(float(component) for component in value)
    if not all(isfinite(component) for component in result):
        raise AirframeGimbalError(f"{label} must be finite")
    magnitude = sqrt(sum(component * component for component in result))
    if abs(magnitude - 1.0) > QUATERNION_TOLERANCE:
        raise AirframeGimbalError(f"{label} must be normalized")
    return normalize(result)  # type: ignore[arg-type]


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _length(vector: Vector3) -> float:
    return hypot(*vector)


def _scale(vector: Vector3, factor: float) -> Vector3:
    return tuple(component * factor for component in vector)  # type: ignore[return-value]


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _unit(vector: Vector3, fallback: Vector3) -> Vector3:
    magnitude = _length(vector)
    return _scale(vector, 1.0 / magnitude) if magnitude > EPSILON else fallback


def _rotate(quaternion: Quaternion, vector: Vector3) -> Vector3:
    rotated = multiply(multiply(quaternion, (vector[0], vector[1], vector[2], 0.0)),
                       (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3]))
    return (rotated[0], rotated[1], rotated[2])


def _axis_angle(axis: Vector3, angle_radians: float) -> Quaternion:
    direction = _unit(axis, (1.0, 0.0, 0.0))
    half = 0.5 * angle_radians
    scale = sin(half)
    return normalize((direction[0] * scale, direction[1] * scale, direction[2] * scale, cos(half)))


def _basis_quaternion(forward: Vector3, authored_up: Vector3) -> Quaternion:
    x_axis = _unit(forward, (1.0, 0.0, 0.0))
    world_up = (0.0, 0.0, 1.0)
    right = _cross(world_up, x_axis)
    if _length(right) <= EPSILON:
        projected_up = _subtract(authored_up, _scale(x_axis, _dot(authored_up, x_axis)))
        if _length(projected_up) <= EPSILON:
            projected_up = (0.0, 1.0, 0.0)
        z_axis = _unit(projected_up, (0.0, 1.0, 0.0))
        y_axis = _unit(_cross(z_axis, x_axis), (1.0, 0.0, 0.0))
        z_axis = _unit(_cross(x_axis, y_axis), z_axis)
    else:
        y_axis = _unit(right, (0.0, 1.0, 0.0))
        z_axis = _unit(_cross(x_axis, y_axis), world_up)

    # Rotation matrix columns are local X/Y/Z expressed in world space.
    m00, m01, m02 = x_axis[0], y_axis[0], z_axis[0]
    m10, m11, m12 = x_axis[1], y_axis[1], z_axis[1]
    m20, m21, m22 = x_axis[2], y_axis[2], z_axis[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        factor = sqrt(trace + 1.0) * 2.0
        quaternion = ((m21 - m12) / factor, (m02 - m20) / factor,
                      (m10 - m01) / factor, 0.25 * factor)
    elif m00 > m11 and m00 > m22:
        factor = sqrt(1.0 + m00 - m11 - m22) * 2.0
        quaternion = (0.25 * factor, (m01 + m10) / factor,
                      (m02 + m20) / factor, (m21 - m12) / factor)
    elif m11 > m22:
        factor = sqrt(1.0 + m11 - m00 - m22) * 2.0
        quaternion = ((m01 + m10) / factor, 0.25 * factor,
                      (m12 + m21) / factor, (m02 - m20) / factor)
    else:
        factor = sqrt(1.0 + m22 - m00 - m11) * 2.0
        quaternion = ((m02 + m20) / factor, (m12 + m21) / factor,
                      0.25 * factor, (m10 - m01) / factor)
    return normalize(quaternion)


def _validate_profile(profile: AirframeGimbalProfile) -> None:
    if any(
        isinstance(getattr(profile, field_name), bool)
        for field_name in AirframeGimbalProfile.__dataclass_fields__
    ):
        raise AirframeGimbalError("airframe/gimbal profile cannot contain booleans")
    values = tuple(
        float(getattr(profile, field_name))
        for field_name in AirframeGimbalProfile.__dataclass_fields__
    )
    if not all(isfinite(value) for value in values):
        raise AirframeGimbalError("airframe/gimbal profile must be finite")
    if not 0.0 <= profile.path_follow_weight <= 1.0:
        raise AirframeGimbalError("path-follow weight must be normalized")
    if not 0.0 <= profile.horizon_stabilization_weight <= 1.0:
        raise AirframeGimbalError("horizon stabilization must be normalized")
    if not 0.0 <= profile.look_ahead_seconds <= 5.0:
        raise AirframeGimbalError("look-ahead is outside 0..5 seconds")
    if not 0.0 <= profile.bank_gain <= 2.0:
        raise AirframeGimbalError("bank gain is outside 0..2")
    if not 0.0 <= profile.max_bank_degrees <= 85.0:
        raise AirframeGimbalError("maximum bank is outside 0..85 degrees")
    if not -45.0 <= profile.camera_uptilt_degrees <= 45.0:
        raise AirframeGimbalError("camera uptilt is outside -45..45 degrees")
    if not 0.0 < profile.max_angular_rate_degrees_per_second <= 720.0:
        raise AirframeGimbalError("maximum angular rate is invalid")
    if not 0.0 < profile.max_acceleration_cm_per_second_squared <= 10000.0:
        raise AirframeGimbalError("maximum acceleration is invalid")
    if not 0.0 < profile.max_jerk_cm_per_second_cubed <= 50000.0:
        raise AirframeGimbalError("maximum jerk is invalid")
    if not 0.0 < profile.minimum_turn_radius_cm <= 100000.0:
        raise AirframeGimbalError("minimum turn radius is invalid")


def solve_airframe_gimbal(
    current_velocity: Vector3,
    look_ahead_velocity: Vector3,
    acceleration: Vector3,
    jerk: Vector3,
    authored_body_rotation: Quaternion,
    authored_gimbal_rotation: Quaternion,
    profile: AirframeGimbalProfile,
) -> AirframeGimbalEvaluation:
    """Return one history-free desired body/gimbal sample.

    The caller must sample ``look_ahead_velocity`` at absolute time
    ``t + profile.look_ahead_seconds`` (clamped to the route endpoint).
    """

    current = _vector(current_velocity, "current velocity")
    look_ahead = _vector(look_ahead_velocity, "look-ahead velocity")
    accel = _vector(acceleration, "acceleration")
    jerk_vector = _vector(jerk, "jerk")
    authored_body = _quaternion(authored_body_rotation, "authored body rotation")
    authored_gimbal = _quaternion(authored_gimbal_rotation, "authored gimbal rotation")
    if not isinstance(profile, AirframeGimbalProfile):
        raise AirframeGimbalError("profile must use the exact airframe/gimbal record")
    _validate_profile(profile)

    acceleration_magnitude = _length(accel)
    jerk_magnitude = _length(jerk_vector)
    tolerance = 1.0e-9
    if acceleration_magnitude > profile.max_acceleration_cm_per_second_squared + tolerance:
        raise AirframeGimbalError("trajectory acceleration exceeds the profile limit")
    if jerk_magnitude > profile.max_jerk_cm_per_second_cubed + tolerance:
        raise AirframeGimbalError("trajectory jerk exceeds the profile limit")

    authored_forward = _unit(_rotate(authored_body, (1.0, 0.0, 0.0)), (1.0, 0.0, 0.0))
    authored_up = _unit(_rotate(authored_body, (0.0, 0.0, 1.0)), (0.0, 0.0, 1.0))
    current_forward = _unit(current, authored_forward)
    predicted_forward = _unit(look_ahead, current_forward)
    path_rotation = _basis_quaternion(predicted_forward, authored_up)

    speed = _length(current)
    forward_acceleration = _scale(current_forward, _dot(accel, current_forward))
    lateral_vector = _subtract(accel, forward_acceleration)
    lateral_magnitude = _length(lateral_vector)
    has_finite_turn = lateral_magnitude > EPSILON and speed > EPSILON
    turn_radius = speed * speed / lateral_magnitude if has_finite_turn else STRAIGHT_TURN_RADIUS_CM
    if not all(isfinite(value) for value in (speed, lateral_magnitude, turn_radius)):
        raise AirframeGimbalError("airframe/gimbal diagnostics must remain finite")
    if has_finite_turn and turn_radius + tolerance < profile.minimum_turn_radius_cm:
        raise AirframeGimbalError("trajectory turn radius is below the profile limit")

    path_right = _unit(_rotate(path_rotation, (0.0, 1.0, 0.0)), (0.0, 1.0, 0.0))
    signed_right_acceleration = _dot(accel, path_right)
    unclamped_bank = -degrees(atan2(signed_right_acceleration, GRAVITY_CM_PER_SECOND_SQUARED)) * profile.bank_gain
    bank = max(-profile.max_bank_degrees, min(profile.max_bank_degrees, unclamped_bank))
    banked_path = normalize(multiply(path_rotation, _axis_angle((1.0, 0.0, 0.0), radians(bank))))
    body = slerp(authored_body, banked_path, profile.path_follow_weight)

    uptilt = _axis_angle((0.0, -1.0, 0.0), radians(profile.camera_uptilt_degrees))
    body_locked_gimbal = normalize(multiply(body, uptilt))
    gimbal = slerp(body_locked_gimbal, authored_gimbal, profile.horizon_stabilization_weight)
    return AirframeGimbalEvaluation(
        body_rotation=normalize(body),
        gimbal_rotation=normalize(gimbal),
        path_rotation=path_rotation,
        speed_cm_per_second=speed,
        lateral_acceleration_cm_per_second_squared=lateral_magnitude,
        turn_radius_cm=turn_radius,
        bank_degrees=bank,
    )
