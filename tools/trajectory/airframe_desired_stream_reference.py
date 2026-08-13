"""Deterministic sampled-kinematics to airframe/gimbal motion compiler.

This is the compositional boundary between absolute-time source sampling and
the accepted desired-pose/prebake primitives.  Source positions, authored body
and gimbal orientations, and smoothed profiles are already sampled on the exact
fixed-step schedule.  The compiler derives velocity, acceleration, and jerk
from that immutable schedule, samples look-ahead velocity by absolute time,
solves every desired pose, and only then invokes the accepted angular-rate
prebake transaction.

The split is intentional: the current document model owns distinct BodyRotation
and GimbalRotation tracks, while the older cinematic-pose adapter exposes only
one orientation result.  This boundary does not alias those tracks or invent a
second source of authorship.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from airframe_gimbal_prebake_reference import (
    AirframeGimbalPrebakeError,
    CompiledAirframeGimbalMotion,
    compile_airframe_gimbal_motion,
    fixed_sample_times,
)
from airframe_gimbal_reference import (
    AirframeGimbalError,
    AirframeGimbalEvaluation,
    AirframeGimbalProfile,
    Quaternion,
    Vector3,
    solve_airframe_gimbal,
)


class AirframeDesiredStreamError(ValueError):
    """The sampled source streams cannot be compiled atomically."""


@dataclass(frozen=True)
class CompiledAirframeDesiredStream:
    sample_times: tuple[float, ...]
    positions: tuple[Vector3, ...]
    velocities: tuple[Vector3, ...]
    accelerations: tuple[Vector3, ...]
    jerks: tuple[Vector3, ...]
    look_ahead_velocities: tuple[Vector3, ...]
    desired_body_rotations: tuple[Quaternion, ...]
    desired_gimbal_rotations: tuple[Quaternion, ...]
    maximum_angular_rates_degrees_per_second: tuple[float, ...]
    desired_pose_diagnostics: tuple[AirframeGimbalEvaluation, ...]
    motion: CompiledAirframeGimbalMotion


def _vector(value: object, label: str) -> Vector3:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise AirframeDesiredStreamError(f"{label} must contain three components")
    if any(isinstance(component, bool) for component in value):
        raise AirframeDesiredStreamError(f"{label} cannot contain booleans")
    try:
        result = tuple(float(component) for component in value)
    except (TypeError, ValueError) as error:
        raise AirframeDesiredStreamError(f"{label} must contain numeric components") from error
    if not all(isfinite(component) for component in result):
        raise AirframeDesiredStreamError(f"{label} must be finite")
    return result  # type: ignore[return-value]


def _derivative_weights(nodes: tuple[float, float, float], at: float) -> tuple[float, float, float]:
    """First-derivative weights for one local quadratic Lagrange stencil."""

    weights: list[float] = []
    for j, node_j in enumerate(nodes):
        denominator = 1.0
        for k, node_k in enumerate(nodes):
            if k != j:
                denominator *= node_j - node_k
        if denominator == 0.0 or not isfinite(denominator):
            raise AirframeDesiredStreamError("sample times must be finite and strictly increasing")
        numerator = 0.0
        for m in range(3):
            if m == j:
                continue
            product = 1.0
            for k, node_k in enumerate(nodes):
                if k != j and k != m:
                    product *= at - node_k
            numerator += product
        weight = numerator / denominator
        if not isfinite(weight):
            raise AirframeDesiredStreamError("derivative weight must remain finite")
        weights.append(weight)
    return tuple(weights)  # type: ignore[return-value]


def differentiate_sampled_vectors(
    values: Sequence[Vector3], sample_times: Sequence[float]
) -> tuple[Vector3, ...]:
    """Differentiate one vector track on the exact, possibly partial schedule.

    Two samples use their shared secant at both endpoints.  Three or more use a
    local quadratic: forward at the first sample, centered in the interior,
    and backward at the last.  Reapplying this same operator to velocity and
    acceleration makes all three derivative stages share one auditable rule.
    """

    if len(values) != len(sample_times) or len(values) < 2:
        raise AirframeDesiredStreamError("vector track and sample-time cardinalities must match and be at least two")
    vectors = tuple(_vector(value, f"sample {index}") for index, value in enumerate(values))
    if any(isinstance(value, bool) for value in sample_times):
        raise AirframeDesiredStreamError("sample times must be finite numeric values")
    try:
        times = tuple(float(value) for value in sample_times)
    except (TypeError, ValueError) as error:
        raise AirframeDesiredStreamError("sample times must be finite numeric values") from error
    if any(not isfinite(value) for value in times):
        raise AirframeDesiredStreamError("sample times must be finite numeric values")
    if any(right <= left for left, right in zip(times, times[1:])):
        raise AirframeDesiredStreamError("sample times must be strictly increasing")

    if len(vectors) == 2:
        inverse_delta = 1.0 / (times[1] - times[0])
        slope = tuple((vectors[1][axis] - vectors[0][axis]) * inverse_delta for axis in range(3))
        if not all(isfinite(component) for component in slope):
            raise AirframeDesiredStreamError("two-sample derivative must remain finite")
        return (slope, slope)  # type: ignore[return-value]

    derivatives: list[Vector3] = []
    last = len(vectors) - 1
    for index, at in enumerate(times):
        start = 0 if index == 0 else last - 2 if index == last else index - 1
        local_times = times[start : start + 3]
        weights = _derivative_weights(local_times, at)  # type: ignore[arg-type]
        value = tuple(
            sum(weights[offset] * vectors[start + offset][axis] for offset in range(3))
            for axis in range(3)
        )
        if not all(isfinite(component) for component in value):
            raise AirframeDesiredStreamError(f"derivative sample {index} must remain finite")
        derivatives.append(value)  # type: ignore[arg-type]
    return tuple(derivatives)


def sample_vector_track_linear(
    values: Sequence[Vector3], sample_times: Sequence[float], elapsed_seconds: float
) -> Vector3:
    """History-free linear sampling with endpoint clamping."""

    if len(values) != len(sample_times) or len(values) < 2:
        raise AirframeDesiredStreamError("sampled vector track has invalid cardinality")
    if isinstance(elapsed_seconds, bool):
        raise AirframeDesiredStreamError("sample time must be finite")
    try:
        elapsed = float(elapsed_seconds)
    except (TypeError, ValueError) as error:
        raise AirframeDesiredStreamError("sample time must be finite") from error
    if not isfinite(elapsed):
        raise AirframeDesiredStreamError("sample time must be finite")
    vectors = tuple(_vector(value, f"sample {index}") for index, value in enumerate(values))
    if any(isinstance(value, bool) for value in sample_times):
        raise AirframeDesiredStreamError("sample times must be finite and strictly increasing")
    try:
        times = tuple(float(value) for value in sample_times)
    except (TypeError, ValueError) as error:
        raise AirframeDesiredStreamError("sample times must be finite and strictly increasing") from error
    if any(not isfinite(value) for value in times) or any(right <= left for left, right in zip(times, times[1:])):
        raise AirframeDesiredStreamError("sample times must be finite and strictly increasing")
    if elapsed <= times[0]:
        return vectors[0]
    if elapsed >= times[-1]:
        return vectors[-1]
    left = bisect_right(times, elapsed) - 1
    alpha = (elapsed - times[left]) / (times[left + 1] - times[left])
    result = tuple(
        vectors[left][axis] + (vectors[left + 1][axis] - vectors[left][axis]) * alpha
        for axis in range(3)
    )
    if not all(isfinite(component) for component in result):
        raise AirframeDesiredStreamError("interpolated vector must remain finite")
    return result  # type: ignore[return-value]


def compile_airframe_desired_stream(
    positions: Sequence[Vector3],
    authored_body_rotations: Sequence[Quaternion],
    authored_gimbal_rotations: Sequence[Quaternion],
    profiles: Sequence[AirframeGimbalProfile],
    total_seconds: float,
    fixed_step_seconds: float,
) -> CompiledAirframeDesiredStream:
    """Compile one complete source-sample transaction or raise without output."""

    try:
        times = fixed_sample_times(total_seconds, fixed_step_seconds)
    except AirframeGimbalPrebakeError as error:
        raise AirframeDesiredStreamError(str(error)) from error
    count = len(times)
    streams = (positions, authored_body_rotations, authored_gimbal_rotations, profiles)
    if any(len(stream) != count for stream in streams):
        raise AirframeDesiredStreamError("all sampled source streams must match the exact fixed schedule")

    position_values = tuple(_vector(value, f"position {index}") for index, value in enumerate(positions))
    velocities = differentiate_sampled_vectors(position_values, times)
    accelerations = differentiate_sampled_vectors(velocities, times)
    jerks = differentiate_sampled_vectors(accelerations, times)

    look_ahead_velocities: list[Vector3] = []
    desired_body: list[Quaternion] = []
    desired_gimbal: list[Quaternion] = []
    maximum_rates: list[float] = []
    diagnostics: list[AirframeGimbalEvaluation] = []
    try:
        for index, (time, profile) in enumerate(zip(times, profiles)):
            if not isinstance(profile, AirframeGimbalProfile):
                raise AirframeDesiredStreamError(f"profile {index} must use the exact accepted record")
            look_ahead = sample_vector_track_linear(
                velocities, times, min(times[-1], time + float(profile.look_ahead_seconds))
            )
            result = solve_airframe_gimbal(
                velocities[index],
                look_ahead,
                accelerations[index],
                jerks[index],
                authored_body_rotations[index],
                authored_gimbal_rotations[index],
                profile,
            )
            look_ahead_velocities.append(look_ahead)
            desired_body.append(result.body_rotation)
            desired_gimbal.append(result.gimbal_rotation)
            maximum_rates.append(float(profile.max_angular_rate_degrees_per_second))
            diagnostics.append(result)
        motion = compile_airframe_gimbal_motion(
            desired_body,
            desired_gimbal,
            maximum_rates,
            total_seconds,
            fixed_step_seconds,
        )
    except (AirframeGimbalError, AirframeGimbalPrebakeError, OverflowError, ValueError) as error:
        if isinstance(error, AirframeDesiredStreamError):
            raise
        raise AirframeDesiredStreamError(str(error)) from error

    return CompiledAirframeDesiredStream(
        sample_times=times,
        positions=position_values,
        velocities=velocities,
        accelerations=accelerations,
        jerks=jerks,
        look_ahead_velocities=tuple(look_ahead_velocities),
        desired_body_rotations=tuple(desired_body),
        desired_gimbal_rotations=tuple(desired_gimbal),
        maximum_angular_rates_degrees_per_second=tuple(maximum_rates),
        desired_pose_diagnostics=tuple(diagnostics),
        motion=motion,
    )
