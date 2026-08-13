"""Frozen composition oracle for one deterministic cinematic camera pose.

This layer deliberately owns no new interpolation math.  It composes the
accepted position-route and quaternion-orientation compilers on one authored
timeline, then publishes a pose only when both component evaluators agree on
segment, normalized local time, completion, and total duration.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from cinematic_reference import (
    AuthoredSegment,
    CompiledTrajectory,
    TrajectoryCompileError,
    Vector3,
    compile_trajectory,
    evaluate_position,
)
from orientation_reference import (
    CompiledOrientationTrack,
    OrientationCompileError,
    Quaternion,
    compile_orientation_track,
    evaluate_orientation,
)


class CinematicPoseError(ValueError):
    """The authored or compiled pose cannot be consumed atomically."""


@dataclass(frozen=True)
class CompiledCinematicPose:
    position: CompiledTrajectory
    orientation: CompiledOrientationTrack
    total_seconds: float


@dataclass(frozen=True)
class CinematicPoseEvaluation:
    complete: bool
    segment_index: int
    local_time_alpha: float
    distance_alpha: float
    curve_u: float
    position: Vector3
    rotation: Quaternion
    total_seconds: float


def _timeline(track: CompiledCinematicPose) -> tuple[tuple[float, float], ...]:
    position_segments = track.position.segments
    orientation_segments = track.orientation.segments
    if not position_segments or len(position_segments) != len(orientation_segments):
        raise CinematicPoseError("component segment cardinalities must be equal and nonempty")
    if not isfinite(track.total_seconds) or track.total_seconds <= 0.0:
        raise CinematicPoseError("pose total duration must be positive and finite")
    if (track.position.total_seconds != track.total_seconds or
            track.orientation.total_seconds != track.total_seconds):
        raise CinematicPoseError("component totals must equal the published pose total")
    timeline = tuple(
        (position.start_seconds, position.duration_seconds)
        for position in position_segments
    )
    for index, (position, orientation) in enumerate(zip(position_segments, orientation_segments)):
        if (not isfinite(position.start_seconds) or
                not isfinite(position.duration_seconds) or
                position.duration_seconds <= 0.0):
            raise CinematicPoseError(f"position segment {index} has an invalid timeline")
        if (position.start_seconds != orientation.start_seconds or
                position.duration_seconds != orientation.duration_seconds):
            raise CinematicPoseError(f"component timeline diverges at segment {index}")
        expected_start = 0.0 if index == 0 else sum(value[1] for value in timeline[:index])
        if position.start_seconds != expected_start:
            raise CinematicPoseError(f"segment {index} is not cumulative")
    if sum(duration for _start, duration in timeline) != track.total_seconds:
        raise CinematicPoseError("segment durations do not exhaust the pose total")
    return timeline


def compile_cinematic_pose(
    points: Sequence[Vector3],
    rotations: Sequence[Quaternion],
    authored_segments: Sequence[AuthoredSegment],
    *,
    arc_tolerance: float = 0.01,
    max_arc_depth: int = 12,
) -> CompiledCinematicPose:
    if len(points) != len(rotations):
        raise CinematicPoseError("position and orientation waypoint counts must match")
    durations = tuple(float(segment.duration_seconds) for segment in authored_segments)
    try:
        position = compile_trajectory(
            points,
            authored_segments,
            arc_tolerance=arc_tolerance,
            max_arc_depth=max_arc_depth,
        )
        orientation = compile_orientation_track(rotations, durations)
    except (TrajectoryCompileError, OrientationCompileError) as error:
        raise CinematicPoseError(str(error)) from error
    result = CompiledCinematicPose(position, orientation, position.total_seconds)
    _timeline(result)
    return result


def evaluate_cinematic_pose(
    track: CompiledCinematicPose, elapsed_seconds: float
) -> CinematicPoseEvaluation:
    _timeline(track)
    if not isfinite(elapsed_seconds):
        raise CinematicPoseError("elapsed pose time must be finite")
    try:
        position = evaluate_position(track.position, elapsed_seconds)
        orientation = evaluate_orientation(track.orientation, elapsed_seconds)
    except (TrajectoryCompileError, OrientationCompileError) as error:
        raise CinematicPoseError(str(error)) from error
    if not orientation.valid or orientation.rotation is None:
        raise CinematicPoseError("orientation evaluation failed")
    if (position.segment_index != orientation.segment_index or
            position.local_time_alpha != orientation.alpha or
            position.complete != orientation.complete or
            position.total_seconds != orientation.total_seconds or
            position.total_seconds != track.total_seconds):
        raise CinematicPoseError("component evaluators did not produce one atomic pose")
    return CinematicPoseEvaluation(
        position.complete,
        position.segment_index,
        position.local_time_alpha,
        position.distance_alpha,
        position.curve_u,
        position.position,
        orientation.rotation,
        track.total_seconds,
    )
