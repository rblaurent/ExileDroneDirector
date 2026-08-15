"""Twist-minimizing carrier-frame compilation and absolute-time evaluation.

The carrier frame is derived only from the accepted sampled path positions.  It
is a third orientation track: authored body and gimbal rotations are deliberately
absent.  A deterministic parallel-transport construction avoids Frenet-frame
roll at straight segments, inflections, holds, and vertical motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, ceil, cos, isfinite, sin, sqrt
from typing import Sequence


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
WORLD_UP: Vector3 = (0.0, 0.0, 1.0)
MINIMUM_FIXED_STEP_SECONDS = 1.0 / 240.0
MAXIMUM_FIXED_STEP_SECONDS = 0.5
MAXIMUM_TOTAL_SECONDS = 3600.0
MAXIMUM_SAMPLE_COUNT = 65536
VECTOR_EPSILON = 1.0e-9
UNIT_TOLERANCE = 1.0e-6
ORTHOGONAL_TOLERANCE = 1.0e-6


class CarrierFrameTransportError(ValueError):
    """Sampled path motion cannot produce a valid independent carrier frame."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CompiledCarrierFrameTransportV1:
    positions: tuple[Vector3, ...]
    tangents: tuple[Vector3, ...]
    rotations: tuple[Quaternion, ...]
    fixed_step_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class CarrierFrameEvaluationV1:
    valid: bool
    complete: bool
    segment_index: int
    alpha: float
    rotation: Quaternion | None
    total_seconds: float


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise CarrierFrameTransportError(f"{label}_not_numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CarrierFrameTransportError(f"{label}_not_numeric") from error
    if not isfinite(result):
        raise CarrierFrameTransportError(f"{label}_not_finite")
    return result


def _vector(value: object, label: str) -> Vector3:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise CarrierFrameTransportError(f"{label}_shape")
    return tuple(_number(component, label) for component in value)  # type: ignore[return-value]


def _add(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _scale(value: Vector3, factor: float) -> Vector3:
    return tuple(component * factor for component in value)  # type: ignore[return-value]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _length(value: Sequence[float]) -> float:
    return sqrt(_dot(value, value))


def _normalize_vector(value: Vector3, label: str) -> Vector3:
    magnitude = _length(value)
    if magnitude <= VECTOR_EPSILON:
        raise CarrierFrameTransportError(f"{label}_degenerate")
    return _scale(value, 1.0 / magnitude)


def _normalize_quaternion(value: Quaternion) -> Quaternion:
    magnitude = _length(value)
    if magnitude <= VECTOR_EPSILON:
        raise CarrierFrameTransportError("quaternion_degenerate")
    return tuple(component / magnitude for component in value)  # type: ignore[return-value]


def _canonical_quaternion(value: Quaternion) -> Quaternion:
    result = _normalize_quaternion(value)
    ordered = (result[3], result[0], result[1], result[2])
    first = next((component for component in ordered if component != 0.0), 0.0)
    return tuple(-component for component in result) if first < 0.0 else result  # type: ignore[return-value]


def _multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def _rotate(rotation: Quaternion, value: Vector3) -> Vector3:
    unit = _normalize_quaternion(rotation)
    conjugate = (-unit[0], -unit[1], -unit[2], unit[3])
    result = _multiply(_multiply(unit, (value[0], value[1], value[2], 0.0)), conjugate)
    return result[0], result[1], result[2]


def _axis_angle(axis: Vector3, angle: float) -> Quaternion:
    unit = _normalize_vector(axis, "transport_axis")
    half = angle * 0.5
    factor = sin(half)
    return _normalize_quaternion((unit[0] * factor, unit[1] * factor, unit[2] * factor, cos(half)))


def _shortest_arc(left: Vector3, right: Vector3, antiparallel_axis: Vector3) -> Quaternion:
    cosine = max(-1.0, min(1.0, _dot(left, right)))
    if cosine >= 1.0 - VECTOR_EPSILON:
        return (0.0, 0.0, 0.0, 1.0)
    if cosine <= -1.0 + VECTOR_EPSILON:
        return _axis_angle(antiparallel_axis, 3.141592653589793)
    return _axis_angle(_cross(left, right), acos(cosine))


def _basis_quaternion(forward: Vector3, right: Vector3, up: Vector3) -> Quaternion:
    # Matrix columns are Unreal's local X/Y/Z axes expressed in world space.
    m00, m01, m02 = forward[0], right[0], up[0]
    m10, m11, m12 = forward[1], right[1], up[1]
    m20, m21, m22 = forward[2], right[2], up[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        scale = sqrt(trace + 1.0) * 2.0
        result = ((m21 - m12) / scale, (m02 - m20) / scale, (m10 - m01) / scale, 0.25 * scale)
    elif m00 > m11 and m00 > m22:
        scale = sqrt(1.0 + m00 - m11 - m22) * 2.0
        result = (0.25 * scale, (m01 + m10) / scale, (m02 + m20) / scale, (m21 - m12) / scale)
    elif m11 > m22:
        scale = sqrt(1.0 + m11 - m00 - m22) * 2.0
        result = ((m01 + m10) / scale, 0.25 * scale, (m12 + m21) / scale, (m02 - m20) / scale)
    else:
        scale = sqrt(1.0 + m22 - m00 - m11) * 2.0
        result = ((m02 + m20) / scale, (m12 + m21) / scale, 0.25 * scale, (m10 - m01) / scale)
    return _canonical_quaternion(result)


def _initial_axes(forward: Vector3) -> tuple[Vector3, Vector3]:
    up_hint = WORLD_UP
    if abs(_dot(forward, up_hint)) >= 1.0 - ORTHOGONAL_TOLERANCE:
        alternatives = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        up_hint = min(alternatives, key=lambda value: (abs(_dot(forward, value)), value))
    right = _normalize_vector(_cross(up_hint, forward), "initial_right")
    up = _normalize_vector(_cross(forward, right), "initial_up")
    return right, up


def fixed_sample_times_v1(total_seconds: object, fixed_step_seconds: object) -> tuple[float, ...]:
    total = _number(total_seconds, "total_seconds")
    step = _number(fixed_step_seconds, "fixed_step_seconds")
    if not 0.0 < total <= MAXIMUM_TOTAL_SECONDS:
        raise CarrierFrameTransportError("total_seconds_out_of_range")
    if not MINIMUM_FIXED_STEP_SECONDS <= step <= MAXIMUM_FIXED_STEP_SECONDS:
        raise CarrierFrameTransportError("fixed_step_seconds_out_of_range")
    intervals = int(ceil(total / step))
    if intervals + 1 > MAXIMUM_SAMPLE_COUNT:
        raise CarrierFrameTransportError("sample_count_above_limit")
    return tuple(index * step for index in range(intervals)) + (total,)


def _sample_tangent(positions: tuple[Vector3, ...], index: int) -> Vector3:
    count = len(positions)
    candidates: list[Vector3] = []
    if 0 < index < count - 1:
        candidates.append(_subtract(positions[index + 1], positions[index - 1]))
    if index < count - 1:
        candidates.append(_subtract(positions[index + 1], positions[index]))
    if index > 0:
        candidates.append(_subtract(positions[index], positions[index - 1]))
    for distance in range(2, count):
        if index + distance < count:
            candidates.append(_subtract(positions[index + distance], positions[index]))
        if index - distance >= 0:
            candidates.append(_subtract(positions[index], positions[index - distance]))
    for candidate in candidates:
        if _length(candidate) > VECTOR_EPSILON:
            return _normalize_vector(candidate, f"tangent_{index}")
    raise CarrierFrameTransportError("path_has_no_direction")


def compile_carrier_frame_transport_v1(
    positions: Sequence[Vector3], total_seconds: object, fixed_step_seconds: object
) -> CompiledCarrierFrameTransportV1:
    if not isinstance(positions, (tuple, list)):
        raise CarrierFrameTransportError("positions_shape")
    accepted_positions = tuple(_vector(value, f"position_{index}") for index, value in enumerate(positions))
    times = fixed_sample_times_v1(total_seconds, fixed_step_seconds)
    if len(accepted_positions) != len(times):
        raise CarrierFrameTransportError("positions_schedule_mismatch")
    tangents = tuple(_sample_tangent(accepted_positions, index) for index in range(len(accepted_positions)))

    right, up = _initial_axes(tangents[0])
    rotations = [_basis_quaternion(tangents[0], right, up)]
    previous_forward = tangents[0]
    for index, forward in enumerate(tangents[1:], start=1):
        delta = _shortest_arc(previous_forward, forward, up)
        transported_up = _rotate(delta, up)
        projected_up = _subtract(transported_up, _scale(forward, _dot(transported_up, forward)))
        if _length(projected_up) <= VECTOR_EPSILON:
            projected_up = _cross(forward, right)
        up = _normalize_vector(projected_up, f"transported_up_{index}")
        right = _normalize_vector(_cross(up, forward), f"transported_right_{index}")
        up = _normalize_vector(_cross(forward, right), f"orthogonal_up_{index}")
        rotation = _basis_quaternion(forward, right, up)
        if _dot(rotations[-1], rotation) < 0.0:
            rotation = tuple(-component for component in rotation)  # type: ignore[assignment]
        rotations.append(rotation)
        previous_forward = forward
    return CompiledCarrierFrameTransportV1(
        accepted_positions, tangents, tuple(rotations), float(fixed_step_seconds), float(total_seconds)
    )


def _track_valid(track: object) -> bool:
    if not isinstance(track, CompiledCarrierFrameTransportV1):
        return False
    count = len(track.positions)
    if count < 2 or len(track.tangents) != count or len(track.rotations) != count:
        return False
    try:
        if len(fixed_sample_times_v1(track.total_seconds, track.fixed_step_seconds)) != count:
            return False
        for index, (tangent, rotation) in enumerate(zip(track.tangents, track.rotations)):
            if abs(_length(tangent) - 1.0) > UNIT_TOLERANCE or abs(_length(rotation) - 1.0) > UNIT_TOLERANCE:
                return False
            if index and _dot(track.rotations[index - 1], rotation) < -UNIT_TOLERANCE:
                return False
            forward = _rotate(rotation, (1.0, 0.0, 0.0))
            if _length(_subtract(forward, tangent)) > ORTHOGONAL_TOLERANCE:
                return False
        return all(all(isfinite(component) for component in position) for position in track.positions)
    except (CarrierFrameTransportError, TypeError, ValueError):
        return False


def _slerp(left: Quaternion, right: Quaternion, alpha: float) -> Quaternion:
    cosine = _dot(left, right)
    aligned = right
    if cosine < 0.0:
        aligned = tuple(-component for component in right)  # type: ignore[assignment]
        cosine = -cosine
    cosine = max(-1.0, min(1.0, cosine))
    if cosine > 0.9995:
        return _normalize_quaternion(tuple(a + alpha * (b - a) for a, b in zip(left, aligned)))  # type: ignore[arg-type]
    angle = acos(cosine)
    denominator = sin(angle)
    return _normalize_quaternion(tuple(
        (sin((1.0 - alpha) * angle) * a + sin(alpha * angle) * b) / denominator
        for a, b in zip(left, aligned)
    ))  # type: ignore[arg-type]


def evaluate_carrier_frame_transport_v1(
    track: CompiledCarrierFrameTransportV1, elapsed_seconds: object
) -> CarrierFrameEvaluationV1:
    if not _track_valid(track):
        return CarrierFrameEvaluationV1(False, False, -1, 0.0, None, 0.0)
    elapsed = _number(elapsed_seconds, "elapsed_seconds")
    if elapsed <= 0.0:
        return CarrierFrameEvaluationV1(True, False, 0, 0.0, track.rotations[0], track.total_seconds)
    if elapsed >= track.total_seconds:
        return CarrierFrameEvaluationV1(True, True, len(track.rotations) - 2, 1.0, track.rotations[-1], track.total_seconds)
    index = min(int(elapsed / track.fixed_step_seconds), len(track.rotations) - 2)
    start = index * track.fixed_step_seconds
    end = min(start + track.fixed_step_seconds, track.total_seconds)
    alpha = (elapsed - start) / (end - start)
    return CarrierFrameEvaluationV1(
        True, False, index, alpha, _slerp(track.rotations[index], track.rotations[index + 1], alpha), track.total_seconds
    )

