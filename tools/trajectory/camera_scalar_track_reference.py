"""Deterministic common scalar-track oracle for authored camera channels.

The track is absolute-time and history-free. It supports physical linear units
(millimetres, f-stops, EV, weights) and reciprocal-distance focus interpolation.
Curve presets make their continuity explicit; clamping is an output policy and
never rewrites authored keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


MAX_KEYS = 512
MODES = ("hold", "linear", "smooth", "cinematic", "hermite")
DOMAINS = ("linear", "reciprocal")


class CameraScalarTrackError(ValueError):
    """Authored scalar-track data cannot produce a deterministic track."""


@dataclass(frozen=True)
class CameraScalarKey:
    time_seconds: float
    value: float
    interpolation_out: str = "cinematic"
    arrive_tangent: float = 0.0
    leave_tangent: float = 0.0


@dataclass(frozen=True)
class CompiledCameraScalarTrack:
    key_times: tuple[float, ...]
    domain_values: tuple[float, ...]
    interpolation_modes: tuple[str, ...]
    arrive_tangents: tuple[float, ...]
    leave_tangents: tuple[float, ...]
    duration_seconds: float
    domain: str
    has_minimum: bool
    minimum: float
    has_maximum: bool
    maximum: float
    clamp_output: bool


@dataclass(frozen=True)
class CameraScalarSample:
    value: float
    velocity: float
    acceleration: float
    segment_index: int
    local_alpha: float
    complete: bool


def _number(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise CameraScalarTrackError(f"{name} must be numeric, not boolean")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraScalarTrackError(f"{name} must be numeric") from error
    if not isfinite(result):
        raise CameraScalarTrackError(f"{name} must be finite")
    return result


def _to_domain(value: float, domain: str) -> float:
    if domain == "linear":
        return value
    if value <= 0.0:
        raise CameraScalarTrackError("reciprocal-domain values must be positive")
    return 1.0 / value


def compile_camera_scalar_track(
    keys: Iterable[CameraScalarKey],
    duration_seconds: float,
    *,
    domain: str = "linear",
    minimum: float | None = None,
    maximum: float | None = None,
    clamp_output: bool = False,
) -> CompiledCameraScalarTrack:
    """Validate and snapshot one scalar channel for absolute-time evaluation."""

    source = tuple(keys)
    if not 1 <= len(source) <= MAX_KEYS:
        raise CameraScalarTrackError("key count must be within 1..512")
    if domain not in DOMAINS:
        raise CameraScalarTrackError(f"unsupported scalar domain: {domain}")
    duration = _number(duration_seconds, "duration")
    if duration < 0.0:
        raise CameraScalarTrackError("duration cannot be negative")

    times = tuple(_number(key.time_seconds, f"key {index} time") for index, key in enumerate(source))
    values = tuple(_number(key.value, f"key {index} value") for index, key in enumerate(source))
    arrives = tuple(_number(key.arrive_tangent, f"key {index} arrive tangent") for index, key in enumerate(source))
    leaves = tuple(_number(key.leave_tangent, f"key {index} leave tangent") for index, key in enumerate(source))
    if times[0] != 0.0:
        raise CameraScalarTrackError("first key time must be zero")
    if any(right <= left for left, right in zip(times, times[1:])):
        raise CameraScalarTrackError("key times must be strictly increasing")
    if times[-1] != duration:
        raise CameraScalarTrackError("last key time must exactly equal duration")
    if len(source) > 1 and duration <= 0.0:
        raise CameraScalarTrackError("multi-key duration must be positive")

    modes = tuple(key.interpolation_out for key in source[:-1])
    if any(mode not in MODES for mode in modes):
        raise CameraScalarTrackError("unsupported interpolation mode")
    for index, mode in enumerate(modes):
        if mode != "hermite" and (leaves[index] != 0.0 or arrives[index + 1] != 0.0):
            raise CameraScalarTrackError("non-hermite segments cannot hide authored tangents")

    has_minimum = minimum is not None
    has_maximum = maximum is not None
    low = _number(minimum, "minimum") if has_minimum else 0.0
    high = _number(maximum, "maximum") if has_maximum else 0.0
    if has_minimum and has_maximum and low > high:
        raise CameraScalarTrackError("minimum cannot exceed maximum")
    if has_minimum and any(value < low for value in values):
        raise CameraScalarTrackError("authored value is below minimum")
    if has_maximum and any(value > high for value in values):
        raise CameraScalarTrackError("authored value is above maximum")
    domain_values = tuple(_to_domain(value, domain) for value in values)

    return CompiledCameraScalarTrack(
        times,
        domain_values,
        modes,
        arrives,
        leaves,
        duration,
        domain,
        has_minimum,
        low,
        has_maximum,
        high,
        bool(clamp_output),
    )


def _basis(mode: str, alpha: float, duration: float, left_tangent: float, right_tangent: float):
    """Return domain value weights and first/second time derivatives."""

    u = alpha
    if mode == "hold":
        return (1.0 if u >= 1.0 else 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if mode == "linear":
        return (u, 1.0 / duration, 0.0, 0.0, 0.0, 0.0)
    if mode == "smooth":
        return (3.0 * u * u - 2.0 * u * u * u, (6.0 * u - 6.0 * u * u) / duration, (6.0 - 12.0 * u) / (duration * duration), 0.0, 0.0, 0.0)
    if mode == "cinematic":
        blend = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
        first = (30.0 * u**2 - 60.0 * u**3 + 30.0 * u**4) / duration
        second = (60.0 * u - 180.0 * u**2 + 120.0 * u**3) / (duration * duration)
        return (blend, first, second, 0.0, 0.0, 0.0)
    # Cubic Hermite: value = h00*a + h10*dt*m0 + h01*b + h11*dt*m1.
    h01 = -2.0 * u**3 + 3.0 * u**2
    dh01 = (-6.0 * u**2 + 6.0 * u) / duration
    d2h01 = (-12.0 * u + 6.0) / (duration * duration)
    h10 = u**3 - 2.0 * u**2 + u
    h11 = u**3 - u**2
    dh10 = (3.0 * u**2 - 4.0 * u + 1.0) / duration
    dh11 = (3.0 * u**2 - 2.0 * u) / duration
    d2h10 = (6.0 * u - 4.0) / (duration * duration)
    d2h11 = (6.0 * u - 2.0) / (duration * duration)
    return h01, dh01, d2h01, duration * left_tangent * h10 + duration * right_tangent * h11, left_tangent * duration * dh10 + right_tangent * duration * dh11, left_tangent * duration * d2h10 + right_tangent * duration * d2h11


def evaluate_camera_scalar_track(track: CompiledCameraScalarTrack, time_seconds: float) -> CameraScalarSample:
    """Evaluate value and physical first/second derivatives at absolute time."""

    query = _number(time_seconds, "query time")
    clamped_time = min(max(query, 0.0), track.duration_seconds)
    if len(track.key_times) == 1:
        domain_value = track.domain_values[0]
        domain_velocity = domain_acceleration = 0.0
        segment_index, alpha = -1, 1.0
    else:
        segment_index = len(track.interpolation_modes) - 1
        for index, right in enumerate(track.key_times[1:]):
            if clamped_time <= right:
                segment_index = index
                break
        left_time = track.key_times[segment_index]
        right_time = track.key_times[segment_index + 1]
        span = right_time - left_time
        alpha = (clamped_time - left_time) / span
        left = track.domain_values[segment_index]
        right = track.domain_values[segment_index + 1]
        mode = track.interpolation_modes[segment_index]
        blend, first, second, tangent_value, tangent_first, tangent_second = _basis(
            mode,
            alpha,
            span,
            track.leave_tangents[segment_index],
            track.arrive_tangents[segment_index + 1],
        )
        domain_value = left + (right - left) * blend + tangent_value
        domain_velocity = (right - left) * first + tangent_first
        domain_acceleration = (right - left) * second + tangent_second

    if track.domain == "reciprocal":
        if domain_value <= 0.0:
            raise CameraScalarTrackError("reciprocal interpolation crossed a non-positive optical value")
        value = 1.0 / domain_value
        velocity = -domain_velocity / (domain_value * domain_value)
        acceleration = 2.0 * domain_velocity * domain_velocity / (domain_value**3) - domain_acceleration / (domain_value * domain_value)
    else:
        value, velocity, acceleration = domain_value, domain_velocity, domain_acceleration

    unclamped = value
    if track.clamp_output:
        if track.has_minimum:
            value = max(value, track.minimum)
        if track.has_maximum:
            value = min(value, track.maximum)
        if value != unclamped:
            velocity = acceleration = 0.0
    return CameraScalarSample(value, velocity, acceleration, segment_index, alpha, clamped_time >= track.duration_seconds)
