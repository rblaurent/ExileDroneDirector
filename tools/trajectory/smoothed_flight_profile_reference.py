"""Deterministic C2 interpolation between compiled segment flight profiles.

Each segment owns its exact canonical preset at its midpoint. Adjacent presets
meet at their shared waypoint as a 50/50 numeric blend. A quintic smootherstep
on either half of the segment makes value, first derivative, and second
derivative agree at both the segment midpoint and every inter-segment boundary.

This slice owns parameter smoothing only. It does not derive airframe or gimbal
transforms and it never mutates the accepted compiled profile publication.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from flight_profile_reference import (
    CompiledFlightProfiles,
    FlightProfile,
    FlightProfileError,
    evaluate_flight_profile,
)


class SmoothedFlightProfileError(ValueError):
    """A compiled profile transition cannot be evaluated safely."""


@dataclass(frozen=True)
class FlightProfileParameters:
    path_follow_weight: float
    horizon_stabilization_weight: float
    look_ahead_seconds: float
    bank_gain: float
    max_bank_degrees: float
    camera_uptilt_degrees: float
    max_angular_rate_degrees_per_second: float
    max_acceleration_cm_per_second_squared: float
    max_jerk_cm_per_second_cubed: float
    minimum_turn_radius_cm: float


@dataclass(frozen=True)
class SmoothedFlightProfileEvaluation:
    segment_index: int
    local_time_alpha: float
    current_profile_id: str
    neighbor_profile_id: str
    neighbor_weight: float
    parameters: FlightProfileParameters


PARAMETER_FIELDS = tuple(FlightProfileParameters.__dataclass_fields__)


def _parameters(profile: FlightProfile) -> FlightProfileParameters:
    return FlightProfileParameters(*(float(getattr(profile, name)) for name in PARAMETER_FIELDS))


def _smootherstep(value: float) -> float:
    x = max(0.0, min(1.0, value))
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def _blend(
    current: FlightProfileParameters,
    neighbor: FlightProfileParameters,
    neighbor_weight: float,
) -> FlightProfileParameters:
    return FlightProfileParameters(*(
        (1.0 - neighbor_weight) * getattr(current, name)
        + neighbor_weight * getattr(neighbor, name)
        for name in PARAMETER_FIELDS
    ))


def _validate_parameters(parameters: FlightProfileParameters) -> None:
    values = tuple(float(getattr(parameters, name)) for name in PARAMETER_FIELDS)
    if not all(isfinite(value) for value in values):
        raise SmoothedFlightProfileError("smoothed profile parameters must be finite")
    if not 0.0 <= parameters.path_follow_weight <= 1.0:
        raise SmoothedFlightProfileError("path-follow weight left its convex domain")
    if not 0.0 <= parameters.horizon_stabilization_weight <= 1.0:
        raise SmoothedFlightProfileError("horizon stabilization left its convex domain")
    if not 0.0 <= parameters.look_ahead_seconds <= 5.0:
        raise SmoothedFlightProfileError("look-ahead left its convex domain")
    if not 0.0 <= parameters.bank_gain <= 2.0:
        raise SmoothedFlightProfileError("bank gain left its convex domain")
    if not 0.0 <= parameters.max_bank_degrees <= 85.0:
        raise SmoothedFlightProfileError("maximum bank left its convex domain")
    if not -45.0 <= parameters.camera_uptilt_degrees <= 45.0:
        raise SmoothedFlightProfileError("camera uptilt left its convex domain")
    if not 0.0 < parameters.max_angular_rate_degrees_per_second <= 720.0:
        raise SmoothedFlightProfileError("angular-rate limit left its convex domain")
    if not 0.0 < parameters.max_acceleration_cm_per_second_squared <= 10000.0:
        raise SmoothedFlightProfileError("acceleration limit left its convex domain")
    if not 0.0 < parameters.max_jerk_cm_per_second_cubed <= 50000.0:
        raise SmoothedFlightProfileError("jerk limit left its convex domain")
    if not 0.0 < parameters.minimum_turn_radius_cm <= 100000.0:
        raise SmoothedFlightProfileError("turn-radius limit left its convex domain")


def evaluate_smoothed_flight_profile(
    compiled: CompiledFlightProfiles,
    segment_index: int,
    local_time_alpha: float,
) -> SmoothedFlightProfileEvaluation:
    """Evaluate one history-free C2 profile transition at a segment-local time."""

    if isinstance(segment_index, bool) or not isinstance(segment_index, int):
        raise SmoothedFlightProfileError("segment index must be an integer")
    if isinstance(local_time_alpha, bool):
        raise SmoothedFlightProfileError("local-time alpha must be a finite scalar")
    try:
        alpha = float(local_time_alpha)
    except (TypeError, ValueError) as error:
        raise SmoothedFlightProfileError("local-time alpha must be a finite scalar") from error
    if not isfinite(alpha) or not 0.0 <= alpha <= 1.0:
        raise SmoothedFlightProfileError("local-time alpha must stay within [0, 1]")

    try:
        current = evaluate_flight_profile(compiled, segment_index).profile
    except FlightProfileError as error:
        raise SmoothedFlightProfileError(str(error)) from error

    if alpha <= 0.5:
        neighbor_index = max(0, segment_index - 1)
        neighbor_weight = 0.5 * (1.0 - _smootherstep(alpha * 2.0))
    else:
        neighbor_index = min(compiled.segment_count - 1, segment_index + 1)
        neighbor_weight = 0.5 * _smootherstep(alpha * 2.0 - 1.0)

    try:
        neighbor = evaluate_flight_profile(compiled, neighbor_index).profile
    except FlightProfileError as error:
        raise SmoothedFlightProfileError(str(error)) from error

    if (neighbor_index == segment_index or neighbor.profile_id == current.profile_id
            or neighbor_weight == 0.0):
        neighbor = current
        neighbor_weight = 0.0

    parameters = _blend(_parameters(current), _parameters(neighbor), neighbor_weight)
    _validate_parameters(parameters)
    return SmoothedFlightProfileEvaluation(
        segment_index,
        alpha,
        current.profile_id,
        neighbor.profile_id,
        neighbor_weight,
        parameters,
    )
