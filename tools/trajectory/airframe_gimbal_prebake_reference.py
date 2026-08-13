"""Deterministic fixed-step airframe/gimbal angular-rate prebake.

The desired-pose solver is deliberately history-free.  This compiler is the
stateful layer above it: it consumes an already sampled desired-pose stream,
limits body and gimbal rotation independently, and publishes immutable samples
that can be evaluated by absolute time at any game frame rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, ceil, degrees, isfinite
from typing import Sequence

from orientation_reference import Quaternion, normalize, slerp


EPSILON = 1.0e-12
UNIT_TOLERANCE = 1.0e-6
MINIMUM_FIXED_STEP_SECONDS = 1.0 / 240.0
MAXIMUM_FIXED_STEP_SECONDS = 0.5
MAXIMUM_TOTAL_SECONDS = 3600.0
MAXIMUM_SAMPLE_COUNT = 65536
MAXIMUM_ANGULAR_RATE_DEGREES_PER_SECOND = 720.0


class AirframeGimbalPrebakeError(ValueError):
    """Raised when a fixed-step motion stream is unsafe to compile."""


@dataclass(frozen=True)
class CompiledAirframeGimbalMotion:
    body_rotations: tuple[Quaternion, ...]
    gimbal_rotations: tuple[Quaternion, ...]
    body_angular_rates_degrees_per_second: tuple[float, ...]
    gimbal_angular_rates_degrees_per_second: tuple[float, ...]
    body_rate_limited: tuple[bool, ...]
    gimbal_rate_limited: tuple[bool, ...]
    fixed_step_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class AirframeGimbalMotionEvaluation:
    valid: bool
    complete: bool
    segment_index: int
    alpha: float
    body_rotation: Quaternion | None
    gimbal_rotation: Quaternion | None
    total_seconds: float


def _number(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise AirframeGimbalPrebakeError(f"{label} cannot be a boolean")
    result = float(value)
    if not isfinite(result):
        raise AirframeGimbalPrebakeError(f"{label} must be finite")
    return result


def _dot(left: Quaternion, right: Quaternion) -> float:
    return sum(a * b for a, b in zip(left, right))


def _negate(value: Quaternion) -> Quaternion:
    return tuple(-component for component in value)  # type: ignore[return-value]


def _canonical_sign(value: Quaternion) -> Quaternion:
    """Choose one representative, including a deterministic 180-degree tie."""

    normalized = normalize(value)
    # Prefer a nonnegative scalar hemisphere.  At w == 0, use vector
    # lexicographic order so q and -q still compile byte-identically.
    ordered = (normalized[3], normalized[0], normalized[1], normalized[2])
    first = next((component for component in ordered if abs(component) > EPSILON), 0.0)
    return _negate(normalized) if first < 0.0 else normalized


def _strict_unit(value: Quaternion, label: str) -> Quaternion:
    if len(value) != 4:
        raise AirframeGimbalPrebakeError(f"{label} must have four components")
    if any(isinstance(component, bool) for component in value):
        raise AirframeGimbalPrebakeError(f"{label} cannot contain booleans")
    components = tuple(float(component) for component in value)
    if not all(isfinite(component) for component in components):
        raise AirframeGimbalPrebakeError(f"{label} must be finite")
    magnitude_squared = sum(component * component for component in components)
    if abs(magnitude_squared - 1.0) > UNIT_TOLERANCE:
        raise AirframeGimbalPrebakeError(f"{label} must be normalized")
    return _canonical_sign(components)  # type: ignore[arg-type]


def fixed_sample_times(total_seconds: float, fixed_step_seconds: float) -> tuple[float, ...]:
    """Return zero, integer fixed steps, and one exact terminal sample."""

    total = _number(total_seconds, "total seconds")
    step = _number(fixed_step_seconds, "fixed step seconds")
    if not 0.0 < total <= MAXIMUM_TOTAL_SECONDS:
        raise AirframeGimbalPrebakeError("total seconds is outside the supported range")
    if not MINIMUM_FIXED_STEP_SECONDS <= step <= MAXIMUM_FIXED_STEP_SECONDS:
        raise AirframeGimbalPrebakeError("fixed step seconds is outside the supported range")
    interval_count = int(ceil(total / step))
    sample_count = interval_count + 1
    if sample_count > MAXIMUM_SAMPLE_COUNT:
        raise AirframeGimbalPrebakeError("fixed-step sample ceiling exceeded")
    values = [index * step for index in range(interval_count)]
    values.append(total)
    return tuple(values)


def _angle_degrees(start: Quaternion, end: Quaternion) -> float:
    dot = max(-1.0, min(1.0, abs(_dot(normalize(start), normalize(end)))))
    return degrees(2.0 * acos(dot))


def _limit_one(
    previous: Quaternion,
    desired: Quaternion,
    delta_seconds: float,
    maximum_rate: float,
) -> tuple[Quaternion, float, bool]:
    target = _canonical_sign(desired)
    dot = _dot(previous, target)
    if dot < -EPSILON:
        target = _negate(target)
        dot = -dot
    # Exact 180-degree ties retain target's canonical sign, making q/-q input
    # equivalent without assigning meaning to an arbitrary serialized sign.
    dot = max(0.0, min(1.0, dot))
    angle = degrees(2.0 * acos(dot))
    allowed = maximum_rate * delta_seconds
    limited = angle > allowed + 1.0e-9
    alpha = allowed / angle if limited and angle > EPSILON else 1.0
    result = _canonical_sign(slerp(previous, target, alpha))
    # Keep the serialized sequence sign-continuous after global canonicalization.
    if _dot(previous, result) < 0.0:
        result = _negate(result)
    applied_rate = _angle_degrees(previous, result) / delta_seconds
    return result, applied_rate, limited


def compile_airframe_gimbal_motion(
    desired_body_rotations: Sequence[Quaternion],
    desired_gimbal_rotations: Sequence[Quaternion],
    maximum_angular_rates_degrees_per_second: Sequence[float],
    total_seconds: float,
    fixed_step_seconds: float,
) -> CompiledAirframeGimbalMotion:
    times = fixed_sample_times(total_seconds, fixed_step_seconds)
    expected = len(times)
    if len(desired_body_rotations) != expected:
        raise AirframeGimbalPrebakeError("body sample count does not match the fixed schedule")
    if len(desired_gimbal_rotations) != expected:
        raise AirframeGimbalPrebakeError("gimbal sample count does not match the fixed schedule")
    if len(maximum_angular_rates_degrees_per_second) != expected:
        raise AirframeGimbalPrebakeError("angular-rate count does not match the fixed schedule")

    bodies = tuple(_strict_unit(value, f"body sample {index}") for index, value in enumerate(desired_body_rotations))
    gimbals = tuple(_strict_unit(value, f"gimbal sample {index}") for index, value in enumerate(desired_gimbal_rotations))
    rates = tuple(_number(value, f"angular rate {index}") for index, value in enumerate(maximum_angular_rates_degrees_per_second))
    if not all(0.0 < value <= MAXIMUM_ANGULAR_RATE_DEGREES_PER_SECOND for value in rates):
        raise AirframeGimbalPrebakeError("angular rate is outside the supported range")

    compiled_bodies = [bodies[0]]
    compiled_gimbals = [gimbals[0]]
    body_rates = [0.0]
    gimbal_rates = [0.0]
    body_limited = [False]
    gimbal_limited = [False]

    for index in range(1, expected):
        delta = times[index] - times[index - 1]
        # Using the stricter endpoint limit prevents a step from violating
        # either side of a smoothly changing profile boundary.
        limit = min(rates[index - 1], rates[index])
        body, body_rate, did_limit_body = _limit_one(
            compiled_bodies[-1], bodies[index], delta, limit
        )
        gimbal, gimbal_rate, did_limit_gimbal = _limit_one(
            compiled_gimbals[-1], gimbals[index], delta, limit
        )
        if body_rate > limit + 1.0e-7 or gimbal_rate > limit + 1.0e-7:
            raise AirframeGimbalPrebakeError("compiled angular rate exceeded its limit")
        compiled_bodies.append(body)
        compiled_gimbals.append(gimbal)
        body_rates.append(body_rate)
        gimbal_rates.append(gimbal_rate)
        body_limited.append(did_limit_body)
        gimbal_limited.append(did_limit_gimbal)

    return CompiledAirframeGimbalMotion(
        tuple(compiled_bodies), tuple(compiled_gimbals), tuple(body_rates), tuple(gimbal_rates),
        tuple(body_limited), tuple(gimbal_limited), float(fixed_step_seconds), float(total_seconds)
    )


def _track_valid(track: CompiledAirframeGimbalMotion) -> bool:
    count = len(track.body_rotations)
    if count < 2 or count > MAXIMUM_SAMPLE_COUNT:
        return False
    arrays = (
        track.gimbal_rotations,
        track.body_angular_rates_degrees_per_second,
        track.gimbal_angular_rates_degrees_per_second,
        track.body_rate_limited,
        track.gimbal_rate_limited,
    )
    if any(len(values) != count for values in arrays):
        return False
    try:
        times = fixed_sample_times(track.total_seconds, track.fixed_step_seconds)
        if len(times) != count:
            return False
        for index, value in enumerate(track.body_rotations):
            _strict_unit(value, f"compiled body {index}")
        for index, value in enumerate(track.gimbal_rotations):
            _strict_unit(value, f"compiled gimbal {index}")
        numeric = track.body_angular_rates_degrees_per_second + track.gimbal_angular_rates_degrees_per_second
        if not all(isfinite(value) and 0.0 <= value <= MAXIMUM_ANGULAR_RATE_DEGREES_PER_SECOND + 1.0e-7 for value in numeric):
            return False
        if track.body_angular_rates_degrees_per_second[0] != 0.0 or track.gimbal_angular_rates_degrees_per_second[0] != 0.0:
            return False
        if track.body_rate_limited[0] is not False or track.gimbal_rate_limited[0] is not False:
            return False
        if not all(type(value) is bool for value in track.body_rate_limited + track.gimbal_rate_limited):
            return False
        for index in range(1, count):
            delta = times[index] - times[index - 1]
            actual_body_rate = _angle_degrees(track.body_rotations[index - 1], track.body_rotations[index]) / delta
            actual_gimbal_rate = _angle_degrees(track.gimbal_rotations[index - 1], track.gimbal_rotations[index]) / delta
            if abs(actual_body_rate - track.body_angular_rates_degrees_per_second[index]) > 1.0e-7:
                return False
            if abs(actual_gimbal_rate - track.gimbal_angular_rates_degrees_per_second[index]) > 1.0e-7:
                return False
    except (AirframeGimbalPrebakeError, TypeError, ValueError):
        return False
    return True


def evaluate_airframe_gimbal_motion(
    track: CompiledAirframeGimbalMotion,
    elapsed_seconds: float,
) -> AirframeGimbalMotionEvaluation:
    if not _track_valid(track):
        return AirframeGimbalMotionEvaluation(False, False, -1, 0.0, None, None, 0.0)
    elapsed = _number(elapsed_seconds, "elapsed seconds")
    if elapsed <= 0.0:
        return AirframeGimbalMotionEvaluation(
            True, False, 0, 0.0, track.body_rotations[0], track.gimbal_rotations[0], track.total_seconds
        )
    if elapsed >= track.total_seconds:
        return AirframeGimbalMotionEvaluation(
            True, True, len(track.body_rotations) - 2, 1.0,
            track.body_rotations[-1], track.gimbal_rotations[-1], track.total_seconds
        )
    segment_index = min(int(elapsed / track.fixed_step_seconds), len(track.body_rotations) - 2)
    start_seconds = segment_index * track.fixed_step_seconds
    segment_end = min(start_seconds + track.fixed_step_seconds, track.total_seconds)
    alpha = (elapsed - start_seconds) / (segment_end - start_seconds)
    return AirframeGimbalMotionEvaluation(
        True, False, segment_index, alpha,
        slerp(track.body_rotations[segment_index], track.body_rotations[segment_index + 1], alpha),
        slerp(track.gimbal_rotations[segment_index], track.gimbal_rotations[segment_index + 1], alpha),
        track.total_seconds,
    )
