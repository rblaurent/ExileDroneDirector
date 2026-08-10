"""Pure oracle for rebuilding the first authored waypoint struct array.

The Blueprint ``SyncDraftWaypointsV1`` function must match these all-or-nothing
semantics.  It validates every legacy channel before producing a new ordered
value snapshot; callers replace the old typed array only after this succeeds.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Any, Sequence


class WaypointBridgeError(ValueError):
    """Legacy waypoint channels cannot form a valid typed snapshot."""


@dataclass(frozen=True)
class WaypointBridgeV1:
    waypoint_id: int
    camera_transform: Any
    focal_length: float
    aperture: float
    manual_focus_distance: float
    hold_seconds: float


def rebuild_waypoints_v1(
    ids: Sequence[int],
    transforms: Sequence[Any],
    focal_lengths: Sequence[float],
    apertures: Sequence[float],
    focus_distances: Sequence[float],
    hold_seconds: Sequence[float],
) -> tuple[WaypointBridgeV1, ...]:
    """Return an ordered value snapshot or fail before constructing any item."""

    channels = {
        "ids": ids,
        "transforms": transforms,
        "focal_lengths": focal_lengths,
        "apertures": apertures,
        "focus_distances": focus_distances,
        "hold_seconds": hold_seconds,
    }
    lengths = {name: len(values) for name, values in channels.items()}
    if len(set(lengths.values())) != 1:
        raise WaypointBridgeError(f"legacy waypoint channels are not lockstep: {lengths}")
    if any(waypoint_id <= 0 for waypoint_id in ids) or len(set(ids)) != len(ids):
        raise WaypointBridgeError("waypoint IDs must be positive and unique")

    scalar_channels = {
        "focal_lengths": focal_lengths,
        "apertures": apertures,
        "focus_distances": focus_distances,
        "hold_seconds": hold_seconds,
    }
    for name, values in scalar_channels.items():
        if not all(isfinite(float(value)) for value in values):
            raise WaypointBridgeError(f"{name} contains a non-finite value")
    if any(value <= 0.0 for value in focal_lengths) or any(value <= 0.0 for value in apertures):
        raise WaypointBridgeError("focal lengths and apertures must be positive")
    if any(value < 0.0 for value in focus_distances) or any(value < 0.0 for value in hold_seconds):
        raise WaypointBridgeError("focus distances and holds cannot be negative")

    return tuple(
        WaypointBridgeV1(
            waypoint_id=ids[index],
            camera_transform=deepcopy(transforms[index]),
            focal_length=float(focal_lengths[index]),
            aperture=float(apertures[index]),
            manual_focus_distance=float(focus_distances[index]),
            hold_seconds=float(hold_seconds[index]),
        )
        for index in range(len(ids))
    )

