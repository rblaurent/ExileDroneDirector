"""Deterministic position/timing oracle for trajectory-engine version 1.

The cooked mod remains Blueprint-only.  This engine-independent module freezes
the math and failure semantics that the modular Blueprint compiler/evaluator
must reproduce: linear or quintic auto-cinematic space, deterministic adaptive
arc-length tables, monotonic time profiles, and absolute-time scrubbing.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence


Vector3 = tuple[float, float, float]
SUPPORTED_SPATIAL_CURVES = frozenset(("linear", "auto_cinematic"))
SUPPORTED_TIME_PROFILES = frozenset((
    "linear", "smoothstep", "smootherstep", "cinematic_s_curve",
    "accelerate_through", "brake_into",
))


class TrajectoryCompileError(ValueError):
    """Authored position/timing data cannot compile safely."""


@dataclass(frozen=True)
class AuthoredSegment:
    duration_seconds: float
    spatial_curve_type: str = "auto_cinematic"
    time_profile: str = "cinematic_s_curve"


@dataclass(frozen=True)
class ArcSample:
    u: float
    distance: float


@dataclass(frozen=True)
class CompiledSegment:
    start_seconds: float
    duration_seconds: float
    spatial_curve_type: str
    time_profile: str
    start: Vector3
    end: Vector3
    start_velocity_u: Vector3
    end_velocity_u: Vector3
    start_acceleration_u: Vector3
    end_acceleration_u: Vector3
    arc_table: tuple[ArcSample, ...]
    length: float


@dataclass(frozen=True)
class CompiledTrajectory:
    segments: tuple[CompiledSegment, ...]
    total_seconds: float
    total_distance: float


@dataclass(frozen=True)
class PositionEvaluation:
    complete: bool
    segment_index: int
    local_time_alpha: float
    distance_alpha: float
    curve_u: float
    position: Vector3
    total_seconds: float


def _finite_vector(value: Vector3) -> bool:
    return len(value) == 3 and all(isfinite(float(component)) for component in value)


def _add(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def _sub(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _mul(value: Vector3, scalar: float) -> Vector3:
    return tuple(component * scalar for component in value)  # type: ignore[return-value]


def _length(value: Vector3) -> float:
    return sqrt(sum(component * component for component in value))


def _distance(left: Vector3, right: Vector3) -> float:
    return _length(_sub(right, left))


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right))


def _normalize(value: Vector3) -> Vector3:
    magnitude = _length(value)
    if magnitude <= 1.0e-12:
        return (0.0, 0.0, 0.0)
    return _mul(value, 1.0 / magnitude)


def evaluate_time_profile(name: str, alpha: float) -> float:
    """Map normalized segment time to monotonic normalized distance."""

    if name not in SUPPORTED_TIME_PROFILES:
        raise TrajectoryCompileError(f"unsupported time profile {name!r}")
    if not isfinite(alpha):
        raise TrajectoryCompileError("time-profile alpha must be finite")
    x = max(0.0, min(1.0, float(alpha)))
    if name == "linear":
        return x
    if name == "smoothstep":
        return x * x * (3.0 - 2.0 * x)
    if name == "smootherstep":
        return x**3 * (x * (x * 6.0 - 15.0) + 10.0)
    if name == "cinematic_s_curve":
        # Seventh-order smoothstep: zero velocity, acceleration, and jerk at
        # both ends.  It is closed form, monotonic, and scrub deterministic.
        return 35.0 * x**4 - 84.0 * x**5 + 70.0 * x**6 - 20.0 * x**7
    if name == "accelerate_through":
        return x * x
    return 1.0 - (1.0 - x) ** 2  # brake_into


def _quintic_basis(u: float) -> tuple[float, ...]:
    u2, u3 = u * u, u * u * u
    u4, u5 = u3 * u, u3 * u * u
    return (
        1.0 - 10.0*u3 + 15.0*u4 - 6.0*u5,
        u - 6.0*u3 + 8.0*u4 - 3.0*u5,
        0.5*(u2 - 3.0*u3 + 3.0*u4 - u5),
        10.0*u3 - 15.0*u4 + 6.0*u5,
        -4.0*u3 + 7.0*u4 - 3.0*u5,
        0.5*(u3 - 2.0*u4 + u5),
    )


def _quintic_basis_d1(u: float) -> tuple[float, ...]:
    u2, u3, u4 = u*u, u*u*u, u*u*u*u
    return (
        -30.0*u2 + 60.0*u3 - 30.0*u4,
        1.0 - 18.0*u2 + 32.0*u3 - 15.0*u4,
        u - 4.5*u2 + 6.0*u3 - 2.5*u4,
        30.0*u2 - 60.0*u3 + 30.0*u4,
        -12.0*u2 + 28.0*u3 - 15.0*u4,
        1.5*u2 - 4.0*u3 + 2.5*u4,
    )


def _quintic_basis_d2(u: float) -> tuple[float, ...]:
    u2, u3 = u*u, u*u*u
    return (
        -60.0*u + 180.0*u2 - 120.0*u3,
        -36.0*u + 96.0*u2 - 60.0*u3,
        1.0 - 9.0*u + 18.0*u2 - 10.0*u3,
        60.0*u - 180.0*u2 + 120.0*u3,
        -24.0*u + 84.0*u2 - 60.0*u3,
        3.0*u - 12.0*u2 + 10.0*u3,
    )


def _blend(segment: CompiledSegment, basis: tuple[float, ...]) -> Vector3:
    channels = (
        segment.start, segment.start_velocity_u, segment.start_acceleration_u,
        segment.end, segment.end_velocity_u, segment.end_acceleration_u,
    )
    return tuple(
        sum(weight * channel[axis] for weight, channel in zip(basis, channels))
        for axis in range(3)
    )  # type: ignore[return-value]


def evaluate_spatial(segment: CompiledSegment, u: float) -> Vector3:
    if not isfinite(u):
        raise TrajectoryCompileError("curve parameter must be finite")
    x = max(0.0, min(1.0, float(u)))
    if segment.spatial_curve_type == "linear":
        return _add(segment.start, _mul(_sub(segment.end, segment.start), x))
    return _blend(segment, _quintic_basis(x))


def evaluate_spatial_derivatives(segment: CompiledSegment, u: float) -> tuple[Vector3, Vector3]:
    """Return first/second spatial derivatives with respect to real seconds."""

    if segment.spatial_curve_type == "linear":
        return (_mul(_sub(segment.end, segment.start), 1.0 / segment.duration_seconds), (0.0, 0.0, 0.0))
    first_u = _blend(segment, _quintic_basis_d1(max(0.0, min(1.0, u))))
    second_u = _blend(segment, _quintic_basis_d2(max(0.0, min(1.0, u))))
    return (_mul(first_u, 1.0 / segment.duration_seconds),
            _mul(second_u, 1.0 / (segment.duration_seconds ** 2)))


def _auto_velocities(points: Sequence[Vector3], segments: Sequence[AuthoredSegment]) -> list[Vector3]:
    velocities: list[Vector3] = [(0.0, 0.0, 0.0) for _ in points]
    for index in range(1, len(points) - 1):
        if (segments[index - 1].spatial_curve_type != "auto_cinematic" or
                segments[index].spatial_curve_type != "auto_cinematic"):
            continue
        incoming = _sub(points[index], points[index - 1])
        outgoing = _sub(points[index + 1], points[index])
        incoming_time = segments[index - 1].duration_seconds
        outgoing_time = segments[index].duration_seconds
        # Component-wise monotonic limiting is deliberately conservative.  A
        # derivative survives only when both adjacent secants move that axis in
        # the same direction.  This prevents the quintic from dipping below a
        # flat-to-rising corner (or overshooting a rising-to-flat corner) while
        # retaining one shared velocity and zero acceleration for C2 joins.
        components = []
        for left_delta, right_delta in zip(incoming, outgoing):
            left_rate = left_delta / incoming_time
            right_rate = right_delta / outgoing_time
            if left_rate * right_rate <= 0.0:
                components.append(0.0)
            else:
                sign = 1.0 if left_rate > 0.0 else -1.0
                components.append(sign * min(abs(left_rate), abs(right_rate)))
        velocities[index] = tuple(components)  # type: ignore[assignment]
    return velocities


def _arc_table(segment: CompiledSegment, tolerance: float, max_depth: int) -> tuple[ArcSample, ...]:
    points: list[tuple[float, Vector3]] = [(0.0, segment.start)]
    minimum_depth = min(6, max_depth)

    def subdivide(u0: float, p0: Vector3, u1: float, p1: Vector3, depth: int) -> None:
        midpoint_u = (u0 + u1) * 0.5
        midpoint = evaluate_spatial(segment, midpoint_u)
        chord = _distance(p0, p1)
        polyline = _distance(p0, midpoint) + _distance(midpoint, p1)
        # A spatially straight quintic can still be strongly nonlinear in u;
        # chord error alone would retain only its endpoints and make distance
        # inversion wrong.  A small fixed floor samples parameter speed, then
        # geometric error drives any additional adaptive subdivision.
        if depth < max_depth and (depth < minimum_depth or polyline - chord > tolerance):
            subdivide(u0, p0, midpoint_u, midpoint, depth + 1)
            subdivide(midpoint_u, midpoint, u1, p1, depth + 1)
        else:
            points.append((u1, p1))

    subdivide(0.0, segment.start, 1.0, segment.end, 0)
    result = [ArcSample(0.0, 0.0)]
    cumulative = 0.0
    for (previous_u, previous), (u, position) in zip(points, points[1:]):
        del previous_u
        cumulative += _distance(previous, position)
        result.append(ArcSample(u, cumulative))
    return tuple(result)


def compile_trajectory(
    points: Sequence[Vector3],
    authored_segments: Sequence[AuthoredSegment],
    *,
    arc_tolerance: float = 0.01,
    max_arc_depth: int = 12,
) -> CompiledTrajectory:
    if len(points) < 2:
        raise TrajectoryCompileError("at least two waypoints are required")
    if len(authored_segments) != len(points) - 1:
        raise TrajectoryCompileError("segment count must equal waypoint count minus one")
    if not all(_finite_vector(point) for point in points):
        raise TrajectoryCompileError("waypoint positions must be finite vectors")
    if not isfinite(arc_tolerance) or arc_tolerance <= 0.0:
        raise TrajectoryCompileError("arc tolerance must be positive and finite")
    if not isinstance(max_arc_depth, int) or not 1 <= max_arc_depth <= 20:
        raise TrajectoryCompileError("max arc depth must be in 1..20")
    for segment in authored_segments:
        if not isfinite(segment.duration_seconds) or segment.duration_seconds <= 0.0:
            raise TrajectoryCompileError("segment duration must be positive and finite")
        if segment.spatial_curve_type not in SUPPORTED_SPATIAL_CURVES:
            raise TrajectoryCompileError(f"unsupported spatial curve {segment.spatial_curve_type!r}")
        if segment.time_profile not in SUPPORTED_TIME_PROFILES:
            raise TrajectoryCompileError(f"unsupported time profile {segment.time_profile!r}")

    velocities = _auto_velocities(points, authored_segments)
    compiled: list[CompiledSegment] = []
    start_seconds = 0.0
    for index, authored in enumerate(authored_segments):
        duration = float(authored.duration_seconds)
        if authored.spatial_curve_type == "linear":
            start_velocity_u = end_velocity_u = (0.0, 0.0, 0.0)
        else:
            start_velocity_u = _mul(velocities[index], duration)
            end_velocity_u = _mul(velocities[index + 1], duration)
        provisional = CompiledSegment(
            start_seconds, duration, authored.spatial_curve_type, authored.time_profile,
            points[index], points[index + 1], start_velocity_u, end_velocity_u,
            (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (), 0.0,
        )
        table = _arc_table(provisional, arc_tolerance, max_arc_depth)
        compiled.append(CompiledSegment(
            **{**provisional.__dict__, "arc_table": table, "length": table[-1].distance}
        ))
        start_seconds += duration
    return CompiledTrajectory(tuple(compiled), start_seconds, sum(segment.length for segment in compiled))


def invert_arc_table(
    us: Sequence[float], distances: Sequence[float], length: float,
    distance_alpha: float,
) -> float:
    """Validate and invert one published cumulative arc table."""

    if not isfinite(distance_alpha):
        raise TrajectoryCompileError("distance alpha must be finite")
    if not isfinite(length) or length < 0.0:
        raise TrajectoryCompileError("arc length must be finite and nonnegative")
    normalized_us = tuple(float(value) for value in us)
    normalized_distances = tuple(float(value) for value in distances)
    if len(normalized_us) < 2 or len(normalized_us) != len(normalized_distances):
        raise TrajectoryCompileError("arc arrays must have equal cardinality of at least two")
    if not all(isfinite(value) for value in normalized_us + normalized_distances):
        raise TrajectoryCompileError("arc samples must be finite")
    if normalized_us[0] != 0.0 or normalized_distances[0] != 0.0:
        raise TrajectoryCompileError("arc table must start at zero")
    if normalized_us[-1] != 1.0 or normalized_distances[-1] != float(length):
        raise TrajectoryCompileError("arc table endpoint must match total length")
    if any(left >= right for left, right in zip(normalized_us, normalized_us[1:])):
        raise TrajectoryCompileError("arc parameters must be strictly increasing")
    if any(left > right for left, right in zip(normalized_distances, normalized_distances[1:])):
        raise TrajectoryCompileError("arc distances must be nondecreasing")

    clamped_alpha = max(0.0, min(1.0, float(distance_alpha)))
    target = clamped_alpha * float(length)
    if length <= 1.0e-12:
        return clamped_alpha
    upper = min(max(1, bisect_left(normalized_distances, target)), len(normalized_distances) - 1)
    left_u, right_u = normalized_us[upper - 1], normalized_us[upper]
    left_distance, right_distance = normalized_distances[upper - 1], normalized_distances[upper]
    span = right_distance - left_distance
    if span <= 1.0e-12:
        return left_u
    alpha = (target - left_distance) / span
    return left_u + (right_u - left_u) * alpha


def invert_arc_length(segment: CompiledSegment, distance_alpha: float) -> float:
    return invert_arc_table(
        tuple(sample.u for sample in segment.arc_table),
        tuple(sample.distance for sample in segment.arc_table),
        segment.length,
        distance_alpha,
    )


def evaluate_position(compiled: CompiledTrajectory, elapsed_seconds: float) -> PositionEvaluation:
    if not compiled.segments:
        raise TrajectoryCompileError("compiled trajectory has no segments")
    if not isfinite(elapsed_seconds):
        raise TrajectoryCompileError("elapsed time must be finite")
    elapsed = max(0.0, float(elapsed_seconds))
    if elapsed >= compiled.total_seconds:
        final_index = len(compiled.segments) - 1
        final = compiled.segments[final_index]
        return PositionEvaluation(True, final_index, 1.0, 1.0, 1.0, final.end, compiled.total_seconds)
    index = len(compiled.segments) - 1
    for candidate, segment in enumerate(compiled.segments):
        if elapsed < segment.start_seconds + segment.duration_seconds:
            index = candidate
            break
    segment = compiled.segments[index]
    local = (elapsed - segment.start_seconds) / segment.duration_seconds
    distance_alpha = evaluate_time_profile(segment.time_profile, local)
    u = invert_arc_length(segment, distance_alpha)
    return PositionEvaluation(False, index, local, distance_alpha, u,
                              evaluate_spatial(segment, u), compiled.total_seconds)
