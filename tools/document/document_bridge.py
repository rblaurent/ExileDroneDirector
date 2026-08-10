"""Transactional oracle for the Blueprint version-1 Flypath document bridge.

``SyncDraftDocumentV1`` must produce the same pair of value snapshots.  It
reconciles adjacent waypoint pairs with existing authored segments, preserving
segment identity and edits whenever the exact adjacency survives.  New
adjacencies receive monotonically increasing IDs.  No caller-owned value is
mutated; invalid input raises before a replacement snapshot is returned.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from waypoint_bridge import WaypointBridgeV1


SCHEMA_VERSION = 1
TRAJECTORY_ENGINE_VERSION = 1
DEFAULT_SEGMENT_DURATION_SECONDS = 3.0
DEFAULT_FLIGHT_PROFILE = "cinematic_drone"
MAX_BLUEPRINT_INTEGER = 2_147_483_647


class DocumentBridgeError(ValueError):
    """Typed waypoint/segment state cannot form a safe Flypath snapshot."""


@dataclass(frozen=True)
class SegmentBridgeV1:
    segment_id: int
    from_waypoint_id: int
    to_waypoint_id: int
    duration_seconds: float = DEFAULT_SEGMENT_DURATION_SECONDS
    spatial_curve_type: str = "linear"
    time_profile: str = "linear"


@dataclass(frozen=True)
class FlypathDocumentBridgeV1:
    schema_version: int = SCHEMA_VERSION
    trajectory_engine_version: int = TRAJECTORY_ENGINE_VERSION
    revision_number: int = 0
    region_id: str = ""
    duration_seconds: float = 0.0
    default_flight_profile: str = DEFAULT_FLIGHT_PROFILE
    waypoints: tuple[WaypointBridgeV1, ...] = ()
    segments: tuple[SegmentBridgeV1, ...] = ()
    content_hash: str = ""


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DocumentBridgeError(f"{field} must be non-empty text")


def _validate_waypoints(waypoints: Sequence[WaypointBridgeV1]) -> None:
    ids = [waypoint.waypoint_id for waypoint in waypoints]
    if any(waypoint_id <= 0 for waypoint_id in ids) or len(ids) != len(set(ids)):
        raise DocumentBridgeError("waypoint IDs must be positive and unique")
    for index, waypoint in enumerate(waypoints):
        scalars = (
            waypoint.focal_length,
            waypoint.aperture,
            waypoint.manual_focus_distance,
            waypoint.hold_seconds,
        )
        if not all(isfinite(float(value)) for value in scalars):
            raise DocumentBridgeError(f"waypoint {index} contains a non-finite scalar")
        if waypoint.focal_length <= 0.0 or waypoint.aperture <= 0.0:
            raise DocumentBridgeError("focal length and aperture must be positive")
        if waypoint.manual_focus_distance < 0.0 or waypoint.hold_seconds < 0.0:
            raise DocumentBridgeError("focus distance and hold cannot be negative")


def _is_reusable(segment: SegmentBridgeV1) -> bool:
    return (
        0 < segment.segment_id <= MAX_BLUEPRINT_INTEGER
        and isfinite(float(segment.duration_seconds))
        and segment.duration_seconds > 0.0
        and isinstance(segment.spatial_curve_type, str)
        and bool(segment.spatial_curve_type.strip())
        and isinstance(segment.time_profile, str)
        and bool(segment.time_profile.strip())
    )


def _next_available_id(candidate: int, used_ids: set[int]) -> int:
    while candidate in used_ids and candidate <= MAX_BLUEPRINT_INTEGER:
        candidate += 1
    if candidate > MAX_BLUEPRINT_INTEGER:
        raise DocumentBridgeError("segment ID space is exhausted")
    return candidate


def sync_draft_document_v1(
    waypoints: Sequence[WaypointBridgeV1],
    prior_segments: Sequence[SegmentBridgeV1] = (),
    prior_document: FlypathDocumentBridgeV1 | None = None,
    *,
    default_segment_duration_seconds: float = DEFAULT_SEGMENT_DURATION_SECONDS,
) -> tuple[tuple[SegmentBridgeV1, ...], FlypathDocumentBridgeV1]:
    """Return reconciled segments and a matching document value snapshot."""

    _validate_waypoints(waypoints)
    if not isfinite(float(default_segment_duration_seconds)):
        raise DocumentBridgeError("default segment duration must be finite")
    if default_segment_duration_seconds <= 0.0:
        raise DocumentBridgeError("default segment duration must be positive")

    metadata = prior_document or FlypathDocumentBridgeV1()
    if metadata.schema_version != SCHEMA_VERSION:
        raise DocumentBridgeError("unsupported schema version")
    if metadata.trajectory_engine_version != TRAJECTORY_ENGINE_VERSION:
        raise DocumentBridgeError("unsupported trajectory engine version")
    if metadata.revision_number < 0:
        raise DocumentBridgeError("revision number cannot be negative")
    if not isinstance(metadata.region_id, str):
        raise DocumentBridgeError("region ID must be text")
    _require_text(metadata.default_flight_profile, "default flight profile")

    reusable = [segment for segment in prior_segments if _is_reusable(segment)]
    highest_prior_id = max((segment.segment_id for segment in reusable), default=0)
    next_id = highest_prior_id + 1
    used_ids: set[int] = set()
    reconciled: list[SegmentBridgeV1] = []

    for left, right in zip(waypoints, waypoints[1:]):
        match = next(
            (
                segment
                for segment in reusable
                if segment.from_waypoint_id == left.waypoint_id
                and segment.to_waypoint_id == right.waypoint_id
                and segment.segment_id not in used_ids
            ),
            None,
        )
        if match is None:
            next_id = _next_available_id(next_id, used_ids)
            match = SegmentBridgeV1(
                segment_id=next_id,
                from_waypoint_id=left.waypoint_id,
                to_waypoint_id=right.waypoint_id,
                duration_seconds=float(default_segment_duration_seconds),
            )
            next_id += 1
        used_ids.add(match.segment_id)
        reconciled.append(deepcopy(match))

    total_duration = sum(float(waypoint.hold_seconds) for waypoint in waypoints)
    total_duration += sum(segment.duration_seconds for segment in reconciled)
    if not isfinite(total_duration):
        raise DocumentBridgeError("calculated duration is not finite")

    waypoint_snapshot = tuple(deepcopy(tuple(waypoints)))
    segment_snapshot = tuple(reconciled)
    document = FlypathDocumentBridgeV1(
        schema_version=SCHEMA_VERSION,
        trajectory_engine_version=TRAJECTORY_ENGINE_VERSION,
        revision_number=metadata.revision_number,
        region_id=metadata.region_id,
        duration_seconds=total_duration,
        default_flight_profile=metadata.default_flight_profile,
        waypoints=waypoint_snapshot,
        segments=segment_snapshot,
        content_hash="",
    )
    return segment_snapshot, document
