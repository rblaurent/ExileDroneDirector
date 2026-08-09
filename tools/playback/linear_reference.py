"""Pure reference evaluator for the first Blueprint linear-playback slice.

This module is deliberately engine-independent.  The live Blueprint must match
these absolute-time semantics before richer trajectory profiles are introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, floor, sin, sqrt
from typing import Sequence


Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class Transform:
    position: Vector3
    rotation: Quaternion


@dataclass(frozen=True)
class Evaluation:
    valid: bool
    complete: bool
    segment_index: int
    alpha: float
    transform: Transform | None
    total_seconds: float


def _normalize(quaternion: Quaternion) -> Quaternion:
    magnitude = sqrt(sum(component * component for component in quaternion))
    if magnitude <= 1.0e-12:
        raise ValueError("A playback waypoint cannot contain a zero quaternion")
    return tuple(component / magnitude for component in quaternion)  # type: ignore[return-value]


def _slerp(start: Quaternion, end: Quaternion, alpha: float) -> Quaternion:
    left = _normalize(start)
    right = _normalize(end)
    dot = sum(a * b for a, b in zip(left, right))
    if dot < 0.0:
        right = tuple(-component for component in right)  # type: ignore[assignment]
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _normalize(
            tuple(a + alpha * (b - a) for a, b in zip(left, right))  # type: ignore[arg-type]
        )
    angle = acos(dot)
    denominator = sin(angle)
    start_weight = sin((1.0 - alpha) * angle) / denominator
    end_weight = sin(alpha * angle) / denominator
    return tuple(  # type: ignore[return-value]
        start_weight * a + end_weight * b for a, b in zip(left, right)
    )


def evaluate_linear(
    waypoints: Sequence[Transform],
    seconds_per_segment: float,
    elapsed_seconds: float,
) -> Evaluation:
    """Evaluate equal-duration segments from absolute elapsed playback time."""

    if len(waypoints) < 2 or seconds_per_segment <= 0.0:
        return Evaluation(False, False, -1, 0.0, None, 0.0)

    segment_count = len(waypoints) - 1
    total_seconds = segment_count * seconds_per_segment
    elapsed = max(0.0, elapsed_seconds)
    if elapsed >= total_seconds:
        return Evaluation(
            True,
            True,
            segment_count - 1,
            1.0,
            waypoints[-1],
            total_seconds,
        )

    segment_time = elapsed / seconds_per_segment
    segment_index = min(floor(segment_time), segment_count - 1)
    alpha = segment_time - segment_index
    start = waypoints[segment_index]
    end = waypoints[segment_index + 1]
    position = tuple(
        a + alpha * (b - a) for a, b in zip(start.position, end.position)
    )
    return Evaluation(
        True,
        False,
        segment_index,
        alpha,
        Transform(position, _slerp(start.rotation, end.rotation, alpha)),
        total_seconds,
    )
