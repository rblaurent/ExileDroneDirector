"""Channel-owned lens, focus, exposure, and bounded-effect compilation.

This is the engine-independent oracle for the camera-channel assembly boundary.
Every channel is compiled independently through the accepted scalar-track
engine, then copied into one immutable ordered snapshot.  Missing sparse
channels become explicit constant tracks; no channel aliases another channel's
keys or compiled storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

from camera_scalar_track_reference import (
    CameraScalarKey,
    CameraScalarSample,
    CameraScalarTrackError,
    CompiledCameraScalarTrack,
    compile_camera_scalar_track,
    evaluate_camera_scalar_track,
)


class CameraChannelAssemblyError(ValueError):
    """The authored camera-channel transaction is not publishable."""


@dataclass(frozen=True)
class CameraChannelPolicyV1:
    channel_id: str
    default_value: float
    minimum: float | None
    maximum: float | None
    clamp_output: bool
    permitted_domains: tuple[str, ...] = ("linear",)


@dataclass(frozen=True)
class AuthoredCameraChannelV1:
    channel_id: str
    keys: tuple[CameraScalarKey, ...]
    domain: str = "linear"


@dataclass(frozen=True)
class FilmbackSnapshotV1:
    preset_id: str
    sensor_width_mm: float
    sensor_height_mm: float


@dataclass(frozen=True)
class CompiledCameraChannelV1:
    channel_id: str
    track: CompiledCameraScalarTrack


@dataclass(frozen=True)
class CompiledCameraChannelAssemblyV1:
    duration_seconds: float
    filmback: FilmbackSnapshotV1
    channels: tuple[CompiledCameraChannelV1, ...]


@dataclass(frozen=True)
class CameraFrameStateV1:
    time_seconds: float
    complete: bool
    filmback: FilmbackSnapshotV1
    focal_length_mm: float
    aperture_fstop: float
    focus_distance_cm: float
    focus_influence: float
    exposure_ev: float
    bloom_weight: float
    vignette_weight: float
    color_grading_weight: float
    tint_weight: float
    motion_blur_weight: float
    chromatic_aberration_weight: float
    sharpening_weight: float
    matte_weight: float
    samples: tuple[tuple[str, CameraScalarSample], ...]


CHANNEL_POLICIES_V1 = (
    CameraChannelPolicyV1("focal_length_mm", 35.0, 1.0, 1000.0, False),
    CameraChannelPolicyV1("aperture_fstop", 2.8, 0.1, 64.0, False),
    CameraChannelPolicyV1("focus_distance_cm", 1000.0, 1.0, 1.0e9, False, ("linear", "reciprocal")),
    CameraChannelPolicyV1("focus_influence", 1.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("exposure_ev", 0.0, -20.0, 20.0, False),
    CameraChannelPolicyV1("bloom_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("vignette_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("color_grading_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("tint_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("motion_blur_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("chromatic_aberration_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("sharpening_weight", 0.0, 0.0, 1.0, True),
    CameraChannelPolicyV1("matte_weight", 0.0, 0.0, 1.0, True),
)
CHANNEL_IDS_V1 = tuple(policy.channel_id for policy in CHANNEL_POLICIES_V1)
_POLICY_BY_ID: Mapping[str, CameraChannelPolicyV1] = {
    policy.channel_id: policy for policy in CHANNEL_POLICIES_V1
}


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise CameraChannelAssemblyError(f"{field} must be numeric, not boolean")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraChannelAssemblyError(f"{field} must be numeric") from error
    if not isfinite(result):
        raise CameraChannelAssemblyError(f"{field} must be finite")
    return result


def _validate_filmback(value: FilmbackSnapshotV1) -> FilmbackSnapshotV1:
    if not isinstance(value.preset_id, str) or not value.preset_id.strip():
        raise CameraChannelAssemblyError("filmback preset ID must be non-empty text")
    width = _finite_number(value.sensor_width_mm, "filmback sensor width")
    height = _finite_number(value.sensor_height_mm, "filmback sensor height")
    if width <= 0.0 or height <= 0.0:
        raise CameraChannelAssemblyError("filmback dimensions must be positive")
    return FilmbackSnapshotV1(value.preset_id, width, height)


def _constant_keys(value: float, duration: float) -> tuple[CameraScalarKey, ...]:
    if duration == 0.0:
        return (CameraScalarKey(0.0, value),)
    return (
        CameraScalarKey(0.0, value, "linear"),
        CameraScalarKey(duration, value),
    )


def compile_camera_channel_assembly_v1(
    duration_seconds: float,
    filmback: FilmbackSnapshotV1,
    authored_channels: Sequence[AuthoredCameraChannelV1],
) -> CompiledCameraChannelAssemblyV1:
    """Compile one all-or-nothing ordered channel bank.

    The return object is created only after all thirteen channels compile.  The
    caller's authored key tuples are never retained as mutable shared storage.
    """

    duration = _finite_number(duration_seconds, "camera-channel duration")
    if duration < 0.0:
        raise CameraChannelAssemblyError("camera-channel duration cannot be negative")
    accepted_filmback = _validate_filmback(filmback)

    authored_by_id: dict[str, AuthoredCameraChannelV1] = {}
    for authored in authored_channels:
        if not isinstance(authored, AuthoredCameraChannelV1):
            raise CameraChannelAssemblyError("authored channels must use AuthoredCameraChannelV1")
        if authored.channel_id not in _POLICY_BY_ID:
            raise CameraChannelAssemblyError(f"unsupported camera channel: {authored.channel_id}")
        if authored.channel_id in authored_by_id:
            raise CameraChannelAssemblyError(f"duplicate camera channel: {authored.channel_id}")
        authored_by_id[authored.channel_id] = authored

    compiled: list[CompiledCameraChannelV1] = []
    try:
        for policy in CHANNEL_POLICIES_V1:
            authored = authored_by_id.get(policy.channel_id)
            keys = _constant_keys(policy.default_value, duration) if authored is None else tuple(authored.keys)
            domain = "linear" if authored is None else authored.domain
            if domain not in policy.permitted_domains:
                raise CameraChannelAssemblyError(
                    f"channel {policy.channel_id} does not permit domain {domain}"
                )
            track = compile_camera_scalar_track(
                keys,
                duration,
                domain=domain,
                minimum=policy.minimum,
                maximum=policy.maximum,
                clamp_output=policy.clamp_output,
            )
            compiled.append(CompiledCameraChannelV1(policy.channel_id, track))
    except CameraScalarTrackError as error:
        raise CameraChannelAssemblyError(str(error)) from error
    return CompiledCameraChannelAssemblyV1(duration, accepted_filmback, tuple(compiled))


def evaluate_camera_channel_assembly_v1(
    assembly: CompiledCameraChannelAssemblyV1,
    time_seconds: float,
) -> CameraFrameStateV1:
    """Evaluate every owned channel at the same absolute time."""

    query = _finite_number(time_seconds, "camera-channel query time")
    if tuple(channel.channel_id for channel in assembly.channels) != CHANNEL_IDS_V1:
        raise CameraChannelAssemblyError("compiled camera channels are not canonical and complete")
    samples = tuple(
        (channel.channel_id, evaluate_camera_scalar_track(channel.track, query))
        for channel in assembly.channels
    )
    values = {channel_id: sample.value for channel_id, sample in samples}
    completion = {sample.complete for _, sample in samples}
    if len(completion) != 1:
        raise CameraChannelAssemblyError("camera channels disagree on completion")
    clamped_time = min(max(query, 0.0), assembly.duration_seconds)
    return CameraFrameStateV1(
        clamped_time,
        completion.pop(),
        assembly.filmback,
        *(values[channel_id] for channel_id in CHANNEL_IDS_V1),
        samples,
    )

