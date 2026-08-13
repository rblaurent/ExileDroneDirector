"""Explicit compiled-document boundary for the live airframe source sampler.

The persisted Python document already owns independent body and gimbal
quaternions, while the current Blueprint v1 waypoint struct owns only one
``CameraTransform`` rotation.  This module deliberately does not bridge that
lossy struct.  It freezes a normalized v2 trajectory-document boundary whose
two orientation channels are required, adjacency checked, and copied into the
accepted source-sampling compiler without synthesis or aliasing.

Discontinuity diagnostics are derived only after the adapter has compiled a
complete source transaction.  They are immutable warnings: a sharp authored
join remains observable without changing the accepted motion publication.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees, isfinite, sqrt
from typing import Sequence

from airframe_source_sampling_reference import (
    AirframeSourceSamplingError,
    SampledAirframeSources,
    sample_and_compile_airframe_sources,
)
from cinematic_reference import (
    AuthoredSegment,
    CompiledTrajectory,
    TrajectoryCompileError,
    compile_trajectory,
    evaluate_spatial_derivatives,
)
from flight_profile_reference import FlightProfileError, compile_flight_profiles
from orientation_reference import (
    CompiledOrientationTrack,
    OrientationCompileError,
    Quaternion,
    compile_orientation_track,
    logarithmic_delta,
    normalize,
)


DOCUMENT_SCHEMA_VERSION = 2
TRAJECTORY_ENGINE_VERSION = 1
MAX_WAYPOINTS = 512
Vector3 = tuple[float, float, float]


class CompiledDocumentSourceAdapterError(ValueError):
    """The normalized document cannot feed the source-sampling transaction."""


@dataclass(frozen=True)
class CompiledDocumentWaypointV2:
    waypoint_id: int
    position: Vector3
    body_rotation: Quaternion
    gimbal_rotation: Quaternion


@dataclass(frozen=True)
class CompiledDocumentSegmentV2:
    segment_id: int
    from_waypoint_id: int
    to_waypoint_id: int
    duration_seconds: float
    spatial_curve_type: str = "linear"
    time_profile: str = "linear"
    flight_profile_override: str = ""


@dataclass(frozen=True)
class CompiledTrajectoryDocumentV2:
    waypoints: tuple[CompiledDocumentWaypointV2, ...]
    segments: tuple[CompiledDocumentSegmentV2, ...]
    duration_seconds: float
    default_flight_profile: str = "cinematic_drone"
    schema_version: int = DOCUMENT_SCHEMA_VERSION
    trajectory_engine_version: int = TRAJECTORY_ENGINE_VERSION


@dataclass(frozen=True)
class DiscontinuityThresholdsV2:
    position_velocity_jump_cm_per_second: float = 1.0
    position_acceleration_jump_cm_per_second_squared: float = 1.0
    authored_angular_rate_jump_degrees_per_second: float = 1.0
    c0_position_gap_cm: float = 1.0e-6
    c0_rotation_gap_degrees: float = 1.0e-6


@dataclass(frozen=True)
class AirframeDocumentDiscontinuityV2:
    waypoint_id: int
    position_c0_gap_cm: float
    position_velocity_jump_cm_per_second: float
    position_acceleration_jump_cm_per_second_squared: float
    body_c0_gap_degrees: float
    gimbal_c0_gap_degrees: float
    authored_body_rate_jump_degrees_per_second: float
    authored_gimbal_rate_jump_degrees_per_second: float
    discontinuous: bool


@dataclass(frozen=True)
class AirframeDocumentDiscontinuityReportV2:
    joins: tuple[AirframeDocumentDiscontinuityV2, ...]
    discontinuity_count: int


@dataclass(frozen=True)
class AdaptedAirframeDocumentV2:
    waypoint_ids: tuple[int, ...]
    positions: tuple[Vector3, ...]
    body_rotations: tuple[Quaternion, ...]
    gimbal_rotations: tuple[Quaternion, ...]
    durations: tuple[float, ...]
    spatial_curve_types: tuple[str, ...]
    time_profiles: tuple[str, ...]
    default_flight_profile: str
    flight_profile_overrides: tuple[str, ...]
    fixed_step_seconds: float
    sampled_sources: SampledAirframeSources
    diagnostics: AirframeDocumentDiscontinuityReportV2


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise CompiledDocumentSourceAdapterError(f"{field} must be numeric, not boolean")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CompiledDocumentSourceAdapterError(f"{field} must be numeric") from error
    if not isfinite(result):
        raise CompiledDocumentSourceAdapterError(f"{field} must be finite")
    return result


def _vector(value: Sequence[float], field: str) -> Vector3:
    if len(value) != 3:
        raise CompiledDocumentSourceAdapterError(f"{field} must contain three components")
    return tuple(_finite_number(component, field) for component in value)  # type: ignore[return-value]


def _length(value: Vector3) -> float:
    return sqrt(sum(component * component for component in value))


def _sub(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _scale(value: Vector3, factor: float) -> Vector3:
    return tuple(component * factor for component in value)  # type: ignore[return-value]


def _rotation_gap_degrees(left: Quaternion, right: Quaternion) -> float:
    a, b = normalize(left), normalize(right)
    dot = abs(sum(x * y for x, y in zip(a, b)))
    return degrees(2.0 * acos(max(-1.0, min(1.0, dot))))


def _rate(rotations: tuple[Quaternion, ...], durations: tuple[float, ...], index: int) -> Vector3:
    return _scale(logarithmic_delta(rotations[index], rotations[index + 1]), 1.0 / durations[index])


def _validate_thresholds(value: DiscontinuityThresholdsV2) -> DiscontinuityThresholdsV2:
    fields = tuple(value.__dataclass_fields__)
    normalized = tuple(_finite_number(getattr(value, field), field) for field in fields)
    if any(item < 0.0 for item in normalized):
        raise CompiledDocumentSourceAdapterError("discontinuity thresholds cannot be negative")
    return DiscontinuityThresholdsV2(*normalized)


def _validate_document(document: CompiledTrajectoryDocumentV2) -> tuple[
    tuple[int, ...], tuple[Vector3, ...], tuple[Quaternion, ...], tuple[Quaternion, ...],
    tuple[float, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], str,
]:
    if document.schema_version != DOCUMENT_SCHEMA_VERSION:
        raise CompiledDocumentSourceAdapterError("compiled document schema version must be 2")
    if document.trajectory_engine_version != TRAJECTORY_ENGINE_VERSION:
        raise CompiledDocumentSourceAdapterError("unsupported trajectory engine version")
    if not 2 <= len(document.waypoints) <= MAX_WAYPOINTS:
        raise CompiledDocumentSourceAdapterError("waypoint count must be within 2..512")
    if len(document.segments) != len(document.waypoints) - 1:
        raise CompiledDocumentSourceAdapterError("segment count must equal waypoint count minus one")

    waypoint_ids = tuple(waypoint.waypoint_id for waypoint in document.waypoints)
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in waypoint_ids):
        raise CompiledDocumentSourceAdapterError("waypoint IDs must be positive integers")
    if len(set(waypoint_ids)) != len(waypoint_ids):
        raise CompiledDocumentSourceAdapterError("waypoint IDs must be unique")
    positions = tuple(_vector(waypoint.position, f"waypoint {index} position") for index, waypoint in enumerate(document.waypoints))
    try:
        body = tuple(normalize(waypoint.body_rotation) for waypoint in document.waypoints)
        gimbal = tuple(normalize(waypoint.gimbal_rotation) for waypoint in document.waypoints)
    except OrientationCompileError as error:
        raise CompiledDocumentSourceAdapterError(str(error)) from error

    segment_ids = tuple(segment.segment_id for segment in document.segments)
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in segment_ids):
        raise CompiledDocumentSourceAdapterError("segment IDs must be positive integers")
    if len(set(segment_ids)) != len(segment_ids):
        raise CompiledDocumentSourceAdapterError("segment IDs must be unique")
    durations = tuple(_finite_number(segment.duration_seconds, f"segment {index} duration") for index, segment in enumerate(document.segments))
    if any(value <= 0.0 for value in durations):
        raise CompiledDocumentSourceAdapterError("segment durations must be positive")
    for index, segment in enumerate(document.segments):
        expected = (waypoint_ids[index], waypoint_ids[index + 1])
        if (segment.from_waypoint_id, segment.to_waypoint_id) != expected:
            raise CompiledDocumentSourceAdapterError(f"segment {segment.segment_id} does not join adjacent waypoints")
    spatial = tuple(segment.spatial_curve_type for segment in document.segments)
    time_profiles = tuple(segment.time_profile for segment in document.segments)
    overrides = tuple(segment.flight_profile_override for segment in document.segments)
    if not isinstance(document.default_flight_profile, str):
        raise CompiledDocumentSourceAdapterError("default flight profile must be text")
    total = _finite_number(document.duration_seconds, "document duration")
    if total <= 0.0 or total != sum(durations):
        raise CompiledDocumentSourceAdapterError("document duration must exactly equal travel segment durations")
    return waypoint_ids, positions, body, gimbal, durations, spatial, time_profiles, overrides, document.default_flight_profile


def build_discontinuity_diagnostics_v2(
    document: CompiledTrajectoryDocumentV2,
    position: CompiledTrajectory,
    body: CompiledOrientationTrack,
    gimbal: CompiledOrientationTrack,
    thresholds: DiscontinuityThresholdsV2 = DiscontinuityThresholdsV2(),
) -> AirframeDocumentDiscontinuityReportV2:
    """Report C0/C1/C2 join pressure without mutating accepted publications."""

    limits = _validate_thresholds(thresholds)
    waypoint_ids = tuple(waypoint.waypoint_id for waypoint in document.waypoints)
    durations = tuple(segment.duration_seconds for segment in document.segments)
    joins = []
    for waypoint_index in range(1, len(document.waypoints) - 1):
        left_index, right_index = waypoint_index - 1, waypoint_index
        left, right = position.segments[left_index], position.segments[right_index]
        left_velocity, left_acceleration = evaluate_spatial_derivatives(left, 1.0)
        right_velocity, right_acceleration = evaluate_spatial_derivatives(right, 0.0)
        position_gap = _length(_sub(left.end, right.start))
        velocity_jump = _length(_sub(left_velocity, right_velocity))
        acceleration_jump = _length(_sub(left_acceleration, right_acceleration))
        body_gap = _rotation_gap_degrees(body.segments[left_index].end, body.segments[right_index].start)
        gimbal_gap = _rotation_gap_degrees(gimbal.segments[left_index].end, gimbal.segments[right_index].start)
        body_rate_jump = degrees(_length(_sub(
            _rate(body.waypoints, durations, left_index),
            _rate(body.waypoints, durations, right_index),
        )))
        gimbal_rate_jump = degrees(_length(_sub(
            _rate(gimbal.waypoints, durations, left_index),
            _rate(gimbal.waypoints, durations, right_index),
        )))
        values = (
            position_gap,
            velocity_jump,
            acceleration_jump,
            body_gap,
            gimbal_gap,
            body_rate_jump,
            gimbal_rate_jump,
        )
        if not all(isfinite(value) and value >= 0.0 for value in values):
            raise CompiledDocumentSourceAdapterError("discontinuity diagnostics must remain finite")
        discontinuous = (
            position_gap > limits.c0_position_gap_cm
            or velocity_jump > limits.position_velocity_jump_cm_per_second
            or acceleration_jump > limits.position_acceleration_jump_cm_per_second_squared
            or body_gap > limits.c0_rotation_gap_degrees
            or gimbal_gap > limits.c0_rotation_gap_degrees
            or body_rate_jump > limits.authored_angular_rate_jump_degrees_per_second
            or gimbal_rate_jump > limits.authored_angular_rate_jump_degrees_per_second
        )
        joins.append(AirframeDocumentDiscontinuityV2(
            waypoint_ids[waypoint_index], position_gap, velocity_jump,
            acceleration_jump, body_gap, gimbal_gap, body_rate_jump,
            gimbal_rate_jump, discontinuous,
        ))
    result = tuple(joins)
    return AirframeDocumentDiscontinuityReportV2(result, sum(item.discontinuous for item in result))


def compile_document_to_airframe_sources_v2(
    document: CompiledTrajectoryDocumentV2,
    fixed_step_seconds: float,
    thresholds: DiscontinuityThresholdsV2 = DiscontinuityThresholdsV2(),
) -> AdaptedAirframeDocumentV2:
    """Validate, stage, compile, and diagnose one explicit v2 document."""

    limits = _validate_thresholds(thresholds)
    (
        waypoint_ids, positions, body_rotations, gimbal_rotations, durations,
        spatial_curve_types, time_profiles, overrides, default_profile,
    ) = _validate_document(document)
    fixed_step = _finite_number(fixed_step_seconds, "fixed step")
    try:
        position = compile_trajectory(
            positions,
            tuple(AuthoredSegment(duration, spatial, timing) for duration, spatial, timing in zip(
                durations, spatial_curve_types, time_profiles
            )),
        )
        body = compile_orientation_track(body_rotations, durations)
        gimbal = compile_orientation_track(gimbal_rotations, durations)
        profiles = compile_flight_profiles(default_profile, overrides, len(durations))
        sampled = sample_and_compile_airframe_sources(position, body, gimbal, profiles, fixed_step)
        diagnostics = build_discontinuity_diagnostics_v2(document, position, body, gimbal, limits)
    except (
        TrajectoryCompileError,
        OrientationCompileError,
        FlightProfileError,
        AirframeSourceSamplingError,
        OverflowError,
        TypeError,
        ValueError,
    ) as error:
        if isinstance(error, CompiledDocumentSourceAdapterError):
            raise
        raise CompiledDocumentSourceAdapterError(str(error)) from error
    return AdaptedAirframeDocumentV2(
        waypoint_ids, positions, body_rotations, gimbal_rotations, durations,
        spatial_curve_types, time_profiles, default_profile, overrides,
        fixed_step, sampled, diagnostics,
    )
