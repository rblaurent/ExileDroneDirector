"""Deterministic per-segment flight-profile compilation and lookup.

This slice owns profile identity and bounded parameters only.  It deliberately
does not derive an airframe, gimbal, or procedural motion yet.  Those solvers
consume this immutable publication instead of branching on loosely authored
strings at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import Sequence


class FlightProfileError(ValueError):
    """Authored or compiled flight-profile data is unsafe to consume."""


@dataclass(frozen=True)
class FlightProfile:
    profile_id: str
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
class CompiledFlightProfiles:
    segment_count: int
    profiles: tuple[FlightProfile, ...]


@dataclass(frozen=True)
class FlightProfileEvaluation:
    segment_index: int
    profile: FlightProfile


PROFILE_ORDER = (
    "cinematic_drone",
    "hybrid",
    "fpv_cinewhoop",
    "fpv_freestyle",
    "fpv_long_range",
)


PROFILES = {
    "cinematic_drone": FlightProfile(
        "cinematic_drone", 0.35, 1.0, 0.75, 0.12, 8.0, 0.0,
        45.0, 350.0, 700.0, 500.0,
    ),
    "hybrid": FlightProfile(
        "hybrid", 0.65, 0.70, 0.45, 0.55, 25.0, 4.0,
        120.0, 900.0, 1800.0, 250.0,
    ),
    "fpv_cinewhoop": FlightProfile(
        "fpv_cinewhoop", 0.85, 0.35, 0.25, 0.85, 40.0, 10.0,
        180.0, 1500.0, 3000.0, 120.0,
    ),
    "fpv_freestyle": FlightProfile(
        "fpv_freestyle", 1.0, 0.05, 0.12, 1.25, 70.0, 20.0,
        360.0, 3500.0, 7000.0, 60.0,
    ),
    "fpv_long_range": FlightProfile(
        "fpv_long_range", 0.90, 0.25, 0.50, 0.70, 45.0, 8.0,
        120.0, 1000.0, 1800.0, 300.0,
    ),
}


def _require_profile_id(value: object, *, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise FlightProfileError("flight-profile identifiers must be strings")
    if value != value.strip():
        raise FlightProfileError("flight-profile identifiers must be canonical and trimmed")
    if allow_empty and value == "":
        return value
    if value not in PROFILES:
        raise FlightProfileError(f"unknown flight profile: {value!r}")
    return value


def _validate_profile(profile: FlightProfile) -> None:
    canonical_id = _require_profile_id(profile.profile_id, allow_empty=False)
    values = (
        profile.path_follow_weight,
        profile.horizon_stabilization_weight,
        profile.look_ahead_seconds,
        profile.bank_gain,
        profile.max_bank_degrees,
        profile.camera_uptilt_degrees,
        profile.max_angular_rate_degrees_per_second,
        profile.max_acceleration_cm_per_second_squared,
        profile.max_jerk_cm_per_second_cubed,
        profile.minimum_turn_radius_cm,
    )
    if not all(isfinite(float(value)) for value in values):
        raise FlightProfileError("flight-profile parameters must be finite")
    if not 0.0 <= profile.path_follow_weight <= 1.0:
        raise FlightProfileError("path-follow weight must be normalized")
    if not 0.0 <= profile.horizon_stabilization_weight <= 1.0:
        raise FlightProfileError("horizon stabilization weight must be normalized")
    if not 0.0 <= profile.look_ahead_seconds <= 5.0:
        raise FlightProfileError("look-ahead must be within the compiled safety bound")
    if not 0.0 <= profile.bank_gain <= 2.0:
        raise FlightProfileError("bank gain must be within the compiled safety bound")
    if not 0.0 <= profile.max_bank_degrees <= 85.0:
        raise FlightProfileError("maximum bank must stay below inversion")
    if not -45.0 <= profile.camera_uptilt_degrees <= 45.0:
        raise FlightProfileError("camera uptilt is outside the supported range")
    if not 0.0 < profile.max_angular_rate_degrees_per_second <= 720.0:
        raise FlightProfileError("angular-rate limit is invalid")
    if not 0.0 < profile.max_acceleration_cm_per_second_squared <= 10000.0:
        raise FlightProfileError("acceleration limit is invalid")
    if not 0.0 < profile.max_jerk_cm_per_second_cubed <= 50000.0:
        raise FlightProfileError("jerk limit is invalid")
    if not 0.0 < profile.minimum_turn_radius_cm <= 100000.0:
        raise FlightProfileError("turn-radius limit is invalid")
    if profile != PROFILES[canonical_id]:
        raise FlightProfileError("compiled profile parameters differ from the canonical preset")


def compile_flight_profiles(
    default_profile_id: str,
    segment_override_ids: Sequence[str],
    segment_count: int,
) -> CompiledFlightProfiles:
    if isinstance(segment_count, bool) or not isinstance(segment_count, int):
        raise FlightProfileError("segment count must be an integer")
    if not 1 <= segment_count <= 511:
        raise FlightProfileError("segment count must be within 1..511")
    default_id = _require_profile_id(default_profile_id, allow_empty=False)
    if len(segment_override_ids) != segment_count:
        raise FlightProfileError("override count must equal segment count")
    resolved: list[FlightProfile] = []
    for override in segment_override_ids:
        override_id = _require_profile_id(override, allow_empty=True)
        resolved.append(PROFILES[override_id or default_id])
    result = CompiledFlightProfiles(segment_count, tuple(resolved))
    _validate_compiled(result)
    return result


def _validate_compiled(compiled: CompiledFlightProfiles) -> None:
    if isinstance(compiled.segment_count, bool) or not isinstance(compiled.segment_count, int):
        raise FlightProfileError("compiled segment count must be an integer")
    if not 1 <= compiled.segment_count <= 511:
        raise FlightProfileError("compiled segment count is outside 1..511")
    if len(compiled.profiles) != compiled.segment_count:
        raise FlightProfileError("compiled profile cardinality differs from segment count")
    for profile in compiled.profiles:
        if not isinstance(profile, FlightProfile):
            raise FlightProfileError("compiled profiles must use the exact profile record")
        _validate_profile(profile)


def evaluate_flight_profile(
    compiled: CompiledFlightProfiles,
    segment_index: int,
) -> FlightProfileEvaluation:
    _validate_compiled(compiled)
    if isinstance(segment_index, bool) or not isinstance(segment_index, int):
        raise FlightProfileError("segment index must be an integer")
    if not 0 <= segment_index < compiled.segment_count:
        raise FlightProfileError("segment index is outside the compiled publication")
    return FlightProfileEvaluation(segment_index, compiled.profiles[segment_index])


def corrupt_parameter(profile: FlightProfile, field: str, value: float) -> FlightProfile:
    """Test helper: construct an immutable malformed publication explicitly."""

    return replace(profile, **{field: value})
