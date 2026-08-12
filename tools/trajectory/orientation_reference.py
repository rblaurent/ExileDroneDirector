"""Deterministic quaternion-track compiler and absolute-time evaluator.

Version 1 uses a time-aware spherical cubic Bezier.  Each waypoint owns one
angular tangent rate, so adjacent segments share angular velocity even when
their durations differ.  Quaternion signs are canonicalized once at compile
time; runtime evaluation is history-free and never interpolates Euler angles.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan2, cos, isfinite, sin, sqrt
from typing import Sequence


Quaternion = tuple[float, float, float, float]
Vector3 = tuple[float, float, float]
EPSILON = 1.0e-12


class OrientationCompileError(ValueError):
    """Raised when an authored orientation track is not safe to compile."""


@dataclass(frozen=True)
class CompiledOrientationSegment:
    start_seconds: float
    duration_seconds: float
    start: Quaternion
    start_control: Quaternion
    end_control: Quaternion
    end: Quaternion


@dataclass(frozen=True)
class CompiledOrientationTrack:
    waypoints: tuple[Quaternion, ...]
    tangent_rates: tuple[Vector3, ...]
    segments: tuple[CompiledOrientationSegment, ...]
    total_seconds: float


@dataclass(frozen=True)
class OrientationEvaluation:
    valid: bool
    complete: bool
    segment_index: int
    alpha: float
    rotation: Quaternion | None
    total_seconds: float


def _dot(left: Quaternion, right: Quaternion) -> float:
    return sum(a * b for a, b in zip(left, right))


def _length(vector: Vector3) -> float:
    return sqrt(sum(component * component for component in vector))


def _scale(vector: Vector3, factor: float) -> Vector3:
    return tuple(component * factor for component in vector)  # type: ignore[return-value]


def _add(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def normalize(quaternion: Quaternion) -> Quaternion:
    if len(quaternion) != 4 or not all(isfinite(float(value)) for value in quaternion):
        raise OrientationCompileError("quaternion must contain four finite components")
    magnitude = sqrt(sum(float(value) * float(value) for value in quaternion))
    if magnitude <= EPSILON:
        raise OrientationCompileError("quaternion magnitude must be positive")
    return tuple(float(value) / magnitude for value in quaternion)  # type: ignore[return-value]


def _negate(quaternion: Quaternion) -> Quaternion:
    return tuple(-value for value in quaternion)  # type: ignore[return-value]


def multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw*rx + lx*rw + ly*rz - lz*ry,
        lw*ry - lx*rz + ly*rw + lz*rx,
        lw*rz + lx*ry - ly*rx + lz*rw,
        lw*rw - lx*rx - ly*ry - lz*rz,
    )


def inverse_unit(quaternion: Quaternion) -> Quaternion:
    x, y, z, w = quaternion
    return (-x, -y, -z, w)


def _log_unit(quaternion: Quaternion) -> Vector3:
    x, y, z, w = normalize(quaternion)
    vector_length = sqrt(x*x + y*y + z*z)
    if vector_length <= EPSILON:
        return (0.0, 0.0, 0.0)
    angle = atan2(vector_length, max(-1.0, min(1.0, w)))
    scale = angle / vector_length
    return (x*scale, y*scale, z*scale)


def _exp_vector(vector: Vector3) -> Quaternion:
    angle = _length(vector)
    if angle <= EPSILON:
        return normalize((vector[0], vector[1], vector[2], 1.0))
    scale = sin(angle) / angle
    return (vector[0]*scale, vector[1]*scale, vector[2]*scale, cos(angle))


def logarithmic_delta(start: Quaternion, end: Quaternion) -> Vector3:
    """Return the shortest rotation vector from start to end, in radians."""

    left, right = normalize(start), normalize(end)
    if _dot(left, right) < 0.0:
        right = _negate(right)
    # Quaternion logarithms encode half of the physical rotation angle.
    return _scale(_log_unit(multiply(inverse_unit(left), right)), 2.0)


def slerp(start: Quaternion, end: Quaternion, alpha: float) -> Quaternion:
    if not isfinite(alpha):
        raise OrientationCompileError("orientation alpha must be finite")
    left, right = normalize(start), normalize(end)
    dot = _dot(left, right)
    if dot < 0.0:
        right, dot = _negate(right), -dot
    dot = max(-1.0, min(1.0, dot))
    x = max(0.0, min(1.0, float(alpha)))
    if dot > 0.9995:
        return normalize(tuple(a + x*(b-a) for a, b in zip(left, right)))  # type: ignore[arg-type]
    angle = acos(dot)
    denominator = sin(angle)
    left_weight = sin((1.0-x)*angle) / denominator
    right_weight = sin(x*angle) / denominator
    return normalize(tuple(left_weight*a + right_weight*b for a, b in zip(left, right)))  # type: ignore[arg-type]


def _spherical_bezier(segment: CompiledOrientationSegment, alpha: float) -> Quaternion:
    x = max(0.0, min(1.0, float(alpha)))
    first = slerp(segment.start, segment.start_control, x)
    second = slerp(segment.start_control, segment.end_control, x)
    third = slerp(segment.end_control, segment.end, x)
    fourth = slerp(first, second, x)
    fifth = slerp(second, third, x)
    return slerp(fourth, fifth, x)


def _aligned_waypoints(values: Sequence[Quaternion]) -> tuple[Quaternion, ...]:
    aligned: list[Quaternion] = []
    for value in values:
        current = normalize(value)
        if aligned and _dot(aligned[-1], current) < 0.0:
            current = _negate(current)
        aligned.append(current)
    return tuple(aligned)


def _limited_tangent_rates(
    waypoints: tuple[Quaternion, ...], durations: tuple[float, ...]
) -> tuple[Vector3, ...]:
    forward = tuple(
        _scale(logarithmic_delta(left, right), 1.0/duration)
        for left, right, duration in zip(waypoints, waypoints[1:], durations)
    )
    rates: list[Vector3] = [forward[0]]
    for index in range(1, len(waypoints)-1):
        candidate = _scale(_add(forward[index-1], forward[index]), 0.5)
        magnitude = _length(candidate)
        # A control may travel at most the full adjacent shortest arc.  The
        # shared bound preserves one tangent rate on both sides of the join,
        # while preventing a short segment from acquiring a looping control.
        limit = 3.0 * min(_length(forward[index-1]), _length(forward[index]))
        if magnitude > limit and magnitude > EPSILON:
            candidate = _scale(candidate, limit/magnitude)
        rates.append(candidate)
    rates.append(forward[-1])
    return tuple(rates)


def compile_orientation_track(
    rotations: Sequence[Quaternion], durations: Sequence[float]
) -> CompiledOrientationTrack:
    if len(rotations) < 2:
        raise OrientationCompileError("at least two orientation waypoints are required")
    if len(durations) != len(rotations)-1:
        raise OrientationCompileError("duration count must equal waypoint count minus one")
    normalized_durations = tuple(float(value) for value in durations)
    if not all(isfinite(value) and value > 0.0 for value in normalized_durations):
        raise OrientationCompileError("orientation durations must be positive and finite")
    waypoints = _aligned_waypoints(rotations)
    tangent_rates = _limited_tangent_rates(waypoints, normalized_durations)
    segments: list[CompiledOrientationSegment] = []
    start_seconds = 0.0
    for index, duration in enumerate(normalized_durations):
        start, end = waypoints[index], waypoints[index+1]
        start_control = normalize(multiply(
            start, _exp_vector(_scale(tangent_rates[index], duration/6.0))
        ))
        end_control = normalize(multiply(
            end, _exp_vector(_scale(tangent_rates[index+1], -duration/6.0))
        ))
        segments.append(CompiledOrientationSegment(
            start_seconds, duration, start, start_control, end_control, end
        ))
        start_seconds += duration
    return CompiledOrientationTrack(waypoints, tangent_rates, tuple(segments), start_seconds)


def evaluate_orientation(
    track: CompiledOrientationTrack, elapsed_seconds: float
) -> OrientationEvaluation:
    if not track.segments:
        return OrientationEvaluation(False, False, -1, 0.0, None, 0.0)
    if not isfinite(elapsed_seconds):
        raise OrientationCompileError("elapsed orientation time must be finite")
    elapsed = max(0.0, float(elapsed_seconds))
    if elapsed >= track.total_seconds:
        return OrientationEvaluation(
            True, True, len(track.segments)-1, 1.0,
            track.waypoints[-1], track.total_seconds,
        )
    segment_index = 0
    for index, segment in enumerate(track.segments):
        if elapsed < segment.start_seconds + segment.duration_seconds:
            segment_index = index
            break
    segment = track.segments[segment_index]
    alpha = (elapsed-segment.start_seconds)/segment.duration_seconds
    rotation = segment.start if alpha <= 0.0 else _spherical_bezier(segment, alpha)
    return OrientationEvaluation(
        True, False, segment_index, alpha, rotation, track.total_seconds
    )
