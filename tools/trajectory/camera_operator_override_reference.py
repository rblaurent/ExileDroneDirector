"""Deterministic client-local Directed/Free Look/Carrier Freecam composition.

The adapter consumes already distinct authored position, body, and gimbal
results plus an independently transported carrier frame.  It never feeds its
ephemeral offsets back into authored tracks, playback time, events, or server
authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, isfinite, radians, sin, sqrt

from orientation_reference import multiply, normalize


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
IDENTITY_QUATERNION: Quaternion = (0.0, 0.0, 0.0, 1.0)
MODES_V1 = ("directed", "free_look", "carrier_freecam")
TRANSLATION_FRAMES_V1 = ("world", "carrier")
QUATERNION_TOLERANCE = 1.0e-6
VECTOR_EPSILON = 1.0e-9
SETTLE_POSITION_CM = 1.0e-4
SETTLE_LINEAR_SPEED_CM_S = 1.0e-4
SETTLE_ANGLE_DEGREES = 1.0e-5
SETTLE_ANGULAR_SPEED_DEG_S = 1.0e-4
MAX_DELTA_SECONDS = 0.5
MAX_TETHER_CM = 100000.0


class CameraOperatorOverrideError(ValueError):
    """The local operator request cannot publish a complete final-view pose."""


@dataclass(frozen=True)
class CameraOperatorPolicyV1:
    translation_frame: str = "world"
    maximum_translation_speed_cm_s: float = 1200.0
    translation_acceleration_cm_s2: float = 2400.0
    recenter_translation_speed_cm_s: float = 800.0
    maximum_angular_speed_deg_s: float = 120.0
    angular_acceleration_deg_s2: float = 360.0
    recenter_angular_speed_deg_s: float = 90.0
    tether_enabled: bool = True
    tether_distance_cm: float = 3000.0


@dataclass(frozen=True)
class CameraOperatorStateV1:
    initialized: bool = False
    mode: str = "directed"
    recenter_active: bool = False
    translation_offset_cm: Vector3 = (0.0, 0.0, 0.0)
    translation_velocity_cm_s: Vector3 = (0.0, 0.0, 0.0)
    look_offset: Quaternion = IDENTITY_QUATERNION
    angular_velocity_deg_s: Vector3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class CameraOperatorFrameV1:
    position: Vector3
    body_rotation: Quaternion
    gimbal_rotation: Quaternion
    state: CameraOperatorStateV1
    override_active: bool
    transition_active: bool
    tether_applied: bool


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise CameraOperatorOverrideError(f"{label}_not_numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraOperatorOverrideError(f"{label}_not_numeric") from error
    if not isfinite(result):
        raise CameraOperatorOverrideError(f"{label}_not_finite")
    return result


def _positive(value: object, label: str) -> float:
    result = _number(value, label)
    if result <= 0.0:
        raise CameraOperatorOverrideError(f"{label}_not_positive")
    return result


def _vector(value: object, label: str) -> Vector3:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise CameraOperatorOverrideError(f"{label}_shape")
    return tuple(_number(component, label) for component in value)  # type: ignore[return-value]


def _quaternion(value: object, label: str) -> Quaternion:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise CameraOperatorOverrideError(f"{label}_shape")
    result = tuple(_number(component, label) for component in value)
    magnitude = sqrt(sum(component * component for component in result))
    if abs(magnitude - 1.0) > QUATERNION_TOLERANCE:
        raise CameraOperatorOverrideError(f"{label}_not_normalized")
    return result  # type: ignore[return-value]


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise CameraOperatorOverrideError(f"{label}_not_boolean")
    return value


def _add(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _scale(value: Vector3, factor: float) -> Vector3:
    return tuple(component * factor for component in value)  # type: ignore[return-value]


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right))


def _length(value: Vector3) -> float:
    return sqrt(_dot(value, value))


def _bounded_direction(value: Vector3) -> Vector3:
    magnitude = _length(value)
    return _scale(value, 1.0 / magnitude) if magnitude > 1.0 else value


def _input_vector(value: object, label: str) -> Vector3:
    result = _vector(value, label)
    if any(abs(component) > 1.0 for component in result):
        raise CameraOperatorOverrideError(f"{label}_outside_normalized_range")
    return _bounded_direction(result)


def _move_towards(current: Vector3, target: Vector3, maximum_delta: float) -> Vector3:
    difference = _subtract(target, current)
    distance = _length(difference)
    if distance <= maximum_delta:
        return target
    return _add(current, _scale(difference, maximum_delta / distance))


def _rotate(quaternion: Quaternion, vector: Vector3) -> Vector3:
    unit = normalize(quaternion)
    conjugate = (-unit[0], -unit[1], -unit[2], unit[3])
    rotated = multiply(multiply(unit, (vector[0], vector[1], vector[2], 0.0)), conjugate)
    return (rotated[0], rotated[1], rotated[2])


def _axis_angle(quaternion: Quaternion) -> tuple[Vector3, float]:
    unit = normalize(quaternion)
    if unit[3] < 0.0:
        unit = tuple(-component for component in unit)  # type: ignore[assignment]
    half_angle = acos(max(-1.0, min(1.0, unit[3])))
    sine = sin(half_angle)
    if sine <= VECTOR_EPSILON:
        return (1.0, 0.0, 0.0), 0.0
    return (unit[0] / sine, unit[1] / sine, unit[2] / sine), half_angle * 2.0 * 180.0 / 3.141592653589793


def _delta_quaternion(rotation_degrees: Vector3) -> Quaternion:
    angle = _length(rotation_degrees)
    if angle <= VECTOR_EPSILON:
        return IDENTITY_QUATERNION
    axis = _scale(rotation_degrees, 1.0 / angle)
    half = radians(angle) * 0.5
    factor = sin(half)
    return (axis[0] * factor, axis[1] * factor, axis[2] * factor, cos(half))


def _validated_policy(policy: CameraOperatorPolicyV1) -> CameraOperatorPolicyV1:
    if not isinstance(policy, CameraOperatorPolicyV1):
        raise CameraOperatorOverrideError("policy_shape")
    if policy.translation_frame not in TRANSLATION_FRAMES_V1:
        raise CameraOperatorOverrideError("translation_frame_unknown")
    maximum_translation_speed = _positive(policy.maximum_translation_speed_cm_s, "maximum_translation_speed")
    translation_acceleration = _positive(policy.translation_acceleration_cm_s2, "translation_acceleration")
    recenter_translation_speed = _positive(policy.recenter_translation_speed_cm_s, "recenter_translation_speed")
    maximum_angular_speed = _positive(policy.maximum_angular_speed_deg_s, "maximum_angular_speed")
    angular_acceleration = _positive(policy.angular_acceleration_deg_s2, "angular_acceleration")
    recenter_angular_speed = _positive(policy.recenter_angular_speed_deg_s, "recenter_angular_speed")
    tether_enabled = _boolean(policy.tether_enabled, "tether_enabled")
    tether_distance = _positive(policy.tether_distance_cm, "tether_distance")
    if tether_distance > MAX_TETHER_CM:
        raise CameraOperatorOverrideError("tether_distance_above_hard_limit")
    return CameraOperatorPolicyV1(
        policy.translation_frame, maximum_translation_speed, translation_acceleration,
        recenter_translation_speed, maximum_angular_speed, angular_acceleration,
        recenter_angular_speed, tether_enabled, tether_distance,
    )


def _validated_state(state: CameraOperatorStateV1) -> CameraOperatorStateV1:
    if not isinstance(state, CameraOperatorStateV1):
        raise CameraOperatorOverrideError("state_shape")
    initialized = _boolean(state.initialized, "state_initialized")
    if state.mode not in MODES_V1:
        raise CameraOperatorOverrideError("state_mode_unknown")
    result = CameraOperatorStateV1(
        initialized,
        state.mode,
        _boolean(state.recenter_active, "state_recenter_active"),
        _vector(state.translation_offset_cm, "state_translation_offset"),
        _vector(state.translation_velocity_cm_s, "state_translation_velocity"),
        _quaternion(state.look_offset, "state_look_offset"),
        _vector(state.angular_velocity_deg_s, "state_angular_velocity"),
    )
    if not initialized and result != CameraOperatorStateV1():
        raise CameraOperatorOverrideError("uninitialized_state_not_canonical")
    return result


def _translation_step(
    state: CameraOperatorStateV1,
    mode: str,
    translation_input: Vector3,
    carrier_frame_rotation: Quaternion,
    delta_seconds: float,
    policy: CameraOperatorPolicyV1,
    recenter: bool,
) -> tuple[Vector3, Vector3, bool]:
    interactive = mode == "carrier_freecam" and not recenter
    if interactive:
        direction = _bounded_direction(translation_input)
        if policy.translation_frame == "carrier":
            direction = _rotate(carrier_frame_rotation, direction)
        desired_velocity = _scale(direction, policy.maximum_translation_speed_cm_s)
    else:
        offset_length = _length(state.translation_offset_cm)
        desired_velocity = ((0.0, 0.0, 0.0) if offset_length <= SETTLE_POSITION_CM else
                            _scale(state.translation_offset_cm,
                                   -min(policy.recenter_translation_speed_cm_s,
                                        offset_length / delta_seconds) / offset_length))
    velocity = _move_towards(
        state.translation_velocity_cm_s,
        desired_velocity,
        policy.translation_acceleration_cm_s2 * delta_seconds,
    )
    offset = _add(state.translation_offset_cm, _scale(velocity, delta_seconds))
    if not interactive and _dot(state.translation_offset_cm, offset) <= 0.0:
        offset = (0.0, 0.0, 0.0)
        velocity = (0.0, 0.0, 0.0)
    tether_applied = False
    if policy.tether_enabled and _length(offset) > policy.tether_distance_cm:
        normal = _scale(offset, 1.0 / _length(offset))
        offset = _scale(normal, policy.tether_distance_cm)
        outward_speed = _dot(velocity, normal)
        if outward_speed > 0.0:
            velocity = _subtract(velocity, _scale(normal, outward_speed))
        tether_applied = True
    if _length(offset) <= SETTLE_POSITION_CM and _length(velocity) <= SETTLE_LINEAR_SPEED_CM_S:
        offset = (0.0, 0.0, 0.0)
        velocity = (0.0, 0.0, 0.0)
    return offset, velocity, tether_applied


def _look_step(
    state: CameraOperatorStateV1,
    mode: str,
    look_input: Vector3,
    delta_seconds: float,
    policy: CameraOperatorPolicyV1,
    recenter: bool,
) -> tuple[Quaternion, Vector3]:
    interactive = mode in ("free_look", "carrier_freecam") and not recenter
    if interactive:
        desired_velocity = _scale(_bounded_direction(look_input), policy.maximum_angular_speed_deg_s)
    else:
        axis, angle = _axis_angle(state.look_offset)
        desired_velocity = ((0.0, 0.0, 0.0) if angle <= SETTLE_ANGLE_DEGREES else
                            _scale(axis, -min(policy.recenter_angular_speed_deg_s, angle / delta_seconds)))
    velocity = _move_towards(
        state.angular_velocity_deg_s,
        desired_velocity,
        policy.angular_acceleration_deg_s2 * delta_seconds,
    )
    look = normalize(multiply(state.look_offset, _delta_quaternion(_scale(velocity, delta_seconds))))
    new_angle = _axis_angle(look)[1]
    if new_angle <= SETTLE_ANGLE_DEGREES and _length(velocity) <= SETTLE_ANGULAR_SPEED_DEG_S:
        look = IDENTITY_QUATERNION
        velocity = (0.0, 0.0, 0.0)
    return look, velocity


def apply_camera_operator_override_v1(
    source_valid: bool,
    requested_mode: str,
    authored_position: Vector3,
    authored_body_rotation: Quaternion,
    authored_gimbal_rotation: Quaternion,
    carrier_frame_rotation: Quaternion,
    translation_input: Vector3,
    look_input: Vector3,
    delta_seconds: float,
    recenter_requested: bool,
    return_to_directed_requested: bool,
    policy: CameraOperatorPolicyV1,
    previous_state: CameraOperatorStateV1,
) -> CameraOperatorFrameV1:
    """Advance one local operator step without touching authored or authoritative state."""

    if source_valid is not True:
        raise CameraOperatorOverrideError("source_invalid")
    if requested_mode not in MODES_V1:
        raise CameraOperatorOverrideError("requested_mode_unknown")
    position = _vector(authored_position, "authored_position")
    body = _quaternion(authored_body_rotation, "authored_body_rotation")
    gimbal = _quaternion(authored_gimbal_rotation, "authored_gimbal_rotation")
    carrier = _quaternion(carrier_frame_rotation, "carrier_frame_rotation")
    translation = _input_vector(translation_input, "translation_input")
    look_input_value = _input_vector(look_input, "look_input")
    delta = _positive(delta_seconds, "delta_seconds")
    if delta > MAX_DELTA_SECONDS:
        raise CameraOperatorOverrideError("delta_seconds_above_limit")
    recenter = _boolean(recenter_requested, "recenter_requested")
    return_to_directed = _boolean(return_to_directed_requested, "return_to_directed_requested")
    accepted_policy = _validated_policy(policy)
    state = _validated_state(previous_state)
    mode = "directed" if return_to_directed else requested_mode

    if not state.initialized:
        next_state = CameraOperatorStateV1(True, mode)
        return CameraOperatorFrameV1(position, body, gimbal, next_state,
                                     mode != "directed", False, False)

    operator_input_active = (_length(look_input_value) > VECTOR_EPSILON or
                             (mode == "carrier_freecam" and _length(translation) > VECTOR_EPSILON))
    recenter_active = mode != "directed" and (recenter or (state.recenter_active and not operator_input_active))
    decay = recenter_active or mode == "directed"
    translation_offset, translation_velocity, tether_applied = _translation_step(
        state, mode, translation, carrier, delta, accepted_policy,
        recenter_active or mode != "carrier_freecam",
    )
    look_offset, angular_velocity = _look_step(
        state, mode, look_input_value, delta, accepted_policy, decay,
    )
    settled_translation = translation_offset == (0.0, 0.0, 0.0) and translation_velocity == (0.0, 0.0, 0.0)
    settled_look = look_offset == IDENTITY_QUATERNION and angular_velocity == (0.0, 0.0, 0.0)
    next_recenter_active = recenter_active and not (settled_translation and settled_look)
    next_state = CameraOperatorStateV1(
        True, mode, next_recenter_active, translation_offset, translation_velocity, look_offset, angular_velocity,
    )
    if mode == "directed" or recenter_active:
        transition_active = not (settled_translation and settled_look)
    elif mode == "free_look":
        transition_active = not settled_translation
    else:
        transition_active = False
    final_position = _add(position, translation_offset)
    final_gimbal = gimbal if look_offset == IDENTITY_QUATERNION else normalize(multiply(gimbal, look_offset))
    override_active = mode != "directed" or not (settled_translation and settled_look)
    return CameraOperatorFrameV1(
        final_position, body, final_gimbal, next_state,
        override_active, transition_active, tether_applied,
    )
