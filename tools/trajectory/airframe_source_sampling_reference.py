"""Absolute-time source sampling for the accepted desired-airframe compiler.

This is the narrow bridge between already compiled cinematic source tracks and
``compile_airframe_desired_stream``.  Position, authored body orientation,
authored gimbal orientation, and smoothed flight profiles are evaluated on one
exact fixed schedule.  Nothing is published until every evaluator agrees on
the same segment-local timeline and the downstream desired/prebake transaction
succeeds.

The separate orientation tracks are intentional.  A camera rotation is not a
substitute for both drone-body authorship and gimbal authorship.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from airframe_desired_stream_reference import (
    AirframeDesiredStreamError,
    CompiledAirframeDesiredStream,
    compile_airframe_desired_stream,
)
from airframe_gimbal_prebake_reference import AirframeGimbalPrebakeError, fixed_sample_times
from airframe_gimbal_reference import AirframeGimbalProfile
from cinematic_reference import (
    CompiledTrajectory,
    PositionEvaluation,
    TrajectoryCompileError,
    evaluate_position,
)
from flight_profile_reference import CompiledFlightProfiles
from orientation_reference import (
    CompiledOrientationTrack,
    OrientationCompileError,
    Quaternion,
    evaluate_orientation,
)
from smoothed_flight_profile_reference import (
    PARAMETER_FIELDS,
    SmoothedFlightProfileError,
    evaluate_smoothed_flight_profile,
)


class AirframeSourceSamplingError(ValueError):
    """The compiled source tracks cannot form one atomic desired stream."""


@dataclass(frozen=True)
class SampledAirframeSources:
    sample_times: tuple[float, ...]
    positions: tuple[tuple[float, float, float], ...]
    authored_body_rotations: tuple[Quaternion, ...]
    authored_gimbal_rotations: tuple[Quaternion, ...]
    profiles: tuple[AirframeGimbalProfile, ...]
    desired_stream: CompiledAirframeDesiredStream


def _timeline(
    position: CompiledTrajectory,
    body: CompiledOrientationTrack,
    gimbal: CompiledOrientationTrack,
    profiles: CompiledFlightProfiles,
) -> tuple[float, int]:
    segment_count = len(position.segments)
    if segment_count < 1:
        raise AirframeSourceSamplingError("position source must contain at least one segment")
    if len(body.segments) != segment_count or len(gimbal.segments) != segment_count:
        raise AirframeSourceSamplingError("position, body, and gimbal segment counts must match")
    if profiles.segment_count != segment_count or len(profiles.profiles) != segment_count:
        raise AirframeSourceSamplingError("flight-profile segment count must match source tracks")
    total = float(position.total_seconds)
    if not isfinite(total) or total <= 0.0:
        raise AirframeSourceSamplingError("source total duration must be positive and finite")
    if float(body.total_seconds) != total or float(gimbal.total_seconds) != total:
        raise AirframeSourceSamplingError("position, body, and gimbal totals must match exactly")
    for index, (position_segment, body_segment, gimbal_segment) in enumerate(
        zip(position.segments, body.segments, gimbal.segments)
    ):
        expected = (float(position_segment.start_seconds), float(position_segment.duration_seconds))
        if not all(isfinite(value) for value in expected) or expected[1] <= 0.0:
            raise AirframeSourceSamplingError(f"position segment {index} has an invalid timeline")
        if expected != (float(body_segment.start_seconds), float(body_segment.duration_seconds)):
            raise AirframeSourceSamplingError(f"body timeline diverges at segment {index}")
        if expected != (float(gimbal_segment.start_seconds), float(gimbal_segment.duration_seconds)):
            raise AirframeSourceSamplingError(f"gimbal timeline diverges at segment {index}")
    return total, segment_count


def _require_agreement(
    position: PositionEvaluation,
    body,
    gimbal,
    total: float,
    sample_index: int,
) -> None:
    if not body.valid or body.rotation is None or not gimbal.valid or gimbal.rotation is None:
        raise AirframeSourceSamplingError(f"orientation evaluation failed at sample {sample_index}")
    if not (
        position.segment_index == body.segment_index == gimbal.segment_index
        and position.local_time_alpha == body.alpha == gimbal.alpha
        and position.complete == body.complete == gimbal.complete
        and position.total_seconds == body.total_seconds == gimbal.total_seconds == total
    ):
        raise AirframeSourceSamplingError(f"source evaluators diverged at sample {sample_index}")


def sample_and_compile_airframe_sources(
    position: CompiledTrajectory,
    body: CompiledOrientationTrack,
    gimbal: CompiledOrientationTrack,
    profiles: CompiledFlightProfiles,
    fixed_step_seconds: float,
) -> SampledAirframeSources:
    """Sample all accepted sources and compile one desired/prebake transaction."""

    if isinstance(fixed_step_seconds, bool):
        raise AirframeSourceSamplingError("fixed step must be numeric, not boolean")
    try:
        fixed_step = float(fixed_step_seconds)
    except (TypeError, ValueError, OverflowError) as error:
        raise AirframeSourceSamplingError("fixed step must be numeric") from error
    if not isfinite(fixed_step):
        raise AirframeSourceSamplingError("fixed step must be finite")

    total, _segment_count = _timeline(position, body, gimbal, profiles)
    try:
        sample_times = fixed_sample_times(total, fixed_step)
    except AirframeGimbalPrebakeError as error:
        raise AirframeSourceSamplingError(str(error)) from error

    sampled_positions = []
    sampled_body = []
    sampled_gimbal = []
    sampled_profiles = []
    try:
        for sample_index, elapsed in enumerate(sample_times):
            position_value = evaluate_position(position, elapsed)
            body_value = evaluate_orientation(body, elapsed)
            gimbal_value = evaluate_orientation(gimbal, elapsed)
            _require_agreement(position_value, body_value, gimbal_value, total, sample_index)
            profile_value = evaluate_smoothed_flight_profile(
                profiles, position_value.segment_index, position_value.local_time_alpha
            )
            parameters = profile_value.parameters
            profile = AirframeGimbalProfile(
                *(float(getattr(parameters, field)) for field in PARAMETER_FIELDS)
            )
            sampled_positions.append(position_value.position)
            sampled_body.append(body_value.rotation)
            sampled_gimbal.append(gimbal_value.rotation)
            sampled_profiles.append(profile)

        desired = compile_airframe_desired_stream(
            sampled_positions,
            sampled_body,
            sampled_gimbal,
            sampled_profiles,
            total,
            fixed_step,
        )
    except (
        TrajectoryCompileError,
        OrientationCompileError,
        SmoothedFlightProfileError,
        AirframeDesiredStreamError,
        OverflowError,
        TypeError,
        ValueError,
    ) as error:
        if isinstance(error, AirframeSourceSamplingError):
            raise
        raise AirframeSourceSamplingError(str(error)) from error

    return SampledAirframeSources(
        tuple(sample_times),
        tuple(sampled_positions),
        tuple(sampled_body),
        tuple(sampled_gimbal),
        tuple(sampled_profiles),
        desired,
    )
