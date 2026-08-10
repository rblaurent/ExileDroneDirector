"""Deterministic geometry contract for the first visible path-preview slice."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Rotator:
    pitch: float
    yaw: float
    roll: float = 0.0


@dataclass(frozen=True)
class InstanceTransform:
    location: Vector3
    rotation: Rotator
    scale: Vector3


@dataclass(frozen=True)
class LinearPreview:
    markers: tuple[InstanceTransform, ...]
    segments: tuple[InstanceTransform, ...]


def _require_finite(value: float, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _vector(value: Iterable[float], label: str) -> Vector3:
    values = tuple(value)
    if len(values) != 3:
        raise ValueError(f"{label} must have exactly three components")
    return Vector3(*(_require_finite(item, label) for item in values))


def build_linear_preview(
    waypoint_locations: Iterable[Iterable[float]],
    *,
    marker_scale: float = 0.20,
    line_thickness_scale: float = 0.03,
    source_cube_extent: float = 100.0,
    zero_length_epsilon: float = 0.001,
) -> LinearPreview:
    """Project ordered waypoints into world-space marker and segment instances.

    The Engine basic sphere and cube meshes are 100 Unreal units across. Segment
    cubes point along local +X, are centered at the adjacency midpoint, and scale
    along X by world length / 100. Degenerate adjacencies keep both markers but
    intentionally emit no invisible/unstable segment instance.
    """

    marker = _require_finite(marker_scale, "marker_scale")
    thickness = _require_finite(line_thickness_scale, "line_thickness_scale")
    extent = _require_finite(source_cube_extent, "source_cube_extent")
    epsilon = _require_finite(zero_length_epsilon, "zero_length_epsilon")
    if marker <= 0.0:
        raise ValueError("marker_scale must be positive")
    if thickness <= 0.0:
        raise ValueError("line_thickness_scale must be positive")
    if extent <= 0.0:
        raise ValueError("source_cube_extent must be positive")
    if epsilon < 0.0:
        raise ValueError("zero_length_epsilon must be non-negative")

    points = tuple(_vector(value, f"waypoint[{index}]") for index, value in enumerate(waypoint_locations))
    markers = tuple(
        InstanceTransform(point, Rotator(0.0, 0.0), Vector3(marker, marker, marker))
        for point in points
    )
    segments: list[InstanceTransform] = []
    for start, end in zip(points, points[1:]):
        dx = end.x - start.x
        dy = end.y - start.y
        dz = end.z - start.z
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length <= epsilon:
            continue
        horizontal = math.sqrt(dx * dx + dy * dy)
        rotation = Rotator(
            math.degrees(math.atan2(dz, horizontal)),
            math.degrees(math.atan2(dy, dx)),
        )
        segments.append(
            InstanceTransform(
                Vector3(
                    (start.x + end.x) * 0.5,
                    (start.y + end.y) * 0.5,
                    (start.z + end.z) * 0.5,
                ),
                rotation,
                Vector3(length / extent, thickness, thickness),
            )
        )
    return LinearPreview(markers, tuple(segments))
