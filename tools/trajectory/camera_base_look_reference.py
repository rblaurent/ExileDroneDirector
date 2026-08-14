"""Deterministic named base-look resolution and explicit channel composition.

Named looks are authoring conveniences, not hidden runtime policy.  Every look
expands to all thirteen canonical camera-channel values.  Sparse individually
authored values then replace only their matching channels, and the result keeps
both the base values and the authored-override mask visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from camera_channel_assembly_reference import CHANNEL_POLICIES_V1


class CameraBaseLookError(ValueError):
    """The requested look composition is not publishable."""


CHANNEL_IDS_V1 = tuple(policy.channel_id for policy in CHANNEL_POLICIES_V1)
CHANNEL_DEFAULTS_V1 = tuple(policy.default_value for policy in CHANNEL_POLICIES_V1)
DIRECTLY_UNAVAILABLE_CHANNELS_V1 = (
    "focus_influence",
    "color_grading_weight",
    "tint_weight",
    "sharpening_weight",
    "matte_weight",
)


@dataclass(frozen=True)
class CameraBaseLookPresetV1:
    preset_id: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class CameraBaseLookCompositionV1:
    preset_id: str
    channel_ids: tuple[str, ...]
    base_values: tuple[float, ...]
    values: tuple[float, ...]
    authored_override_mask: tuple[bool, ...]


def _look(preset_id: str, values: Sequence[float]) -> CameraBaseLookPresetV1:
    return CameraBaseLookPresetV1(preset_id, tuple(float(value) for value in values))


CAMERA_BASE_LOOK_PRESETS_V1 = (
    _look("raw", (35.0, 2.8, 1000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    _look("clean_cinematic", (50.0, 2.8, 1000.0, 1.0, 0.0, 0.10, 0.10, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0)),
    _look("epic_landscape", (28.0, 8.0, 100000.0, 1.0, 0.25, 0.15, 0.05, 0.0, 0.0, 0.10, 0.0, 0.0, 0.0)),
    _look("dreamy_shallow_focus", (85.0, 1.4, 500.0, 1.0, 0.50, 0.45, 0.20, 0.0, 0.0, 0.10, 0.05, 0.0, 0.0)),
    _look("dark_sorcery", (50.0, 2.0, 800.0, 1.0, -1.0, 0.35, 0.55, 0.0, 0.0, 0.10, 0.15, 0.0, 0.0)),
    _look("high_speed_fpv", (18.0, 5.6, 100000.0, 1.0, -0.20, 0.0, 0.10, 0.0, 0.0, 0.65, 0.10, 0.0, 0.0)),
    _look("vintage_lens", (50.0, 2.0, 700.0, 1.0, 0.10, 0.25, 0.45, 0.0, 0.0, 0.25, 0.30, 0.0, 0.0)),
    _look("documentary", (35.0, 4.0, 2000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0)),
)
CAMERA_BASE_LOOK_IDS_V1 = tuple(preset.preset_id for preset in CAMERA_BASE_LOOK_PRESETS_V1)
_PRESET_BY_ID = {preset.preset_id: preset for preset in CAMERA_BASE_LOOK_PRESETS_V1}
_POLICY_BY_ID = {policy.channel_id: policy for policy in CHANNEL_POLICIES_V1}


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise CameraBaseLookError(f"{field}_not_numeric")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraBaseLookError(f"{field}_not_numeric") from error
    if not isfinite(result):
        raise CameraBaseLookError(f"{field}_not_finite")
    return result


def _validate_channel_value(channel_id: str, value: object) -> float:
    accepted = _finite_number(value, channel_id)
    policy = _POLICY_BY_ID[channel_id]
    if policy.minimum is not None and accepted < policy.minimum:
        raise CameraBaseLookError(f"{channel_id}_below_minimum")
    if policy.maximum is not None and accepted > policy.maximum:
        raise CameraBaseLookError(f"{channel_id}_above_maximum")
    return accepted


def resolve_camera_base_look_v1(preset_id: str) -> CameraBaseLookPresetV1:
    if not isinstance(preset_id, str) or preset_id not in _PRESET_BY_ID:
        raise CameraBaseLookError("unsupported_camera_look")
    preset = _PRESET_BY_ID[preset_id]
    if len(preset.values) != len(CHANNEL_IDS_V1):
        raise CameraBaseLookError("camera_look_shape")
    values = tuple(
        _validate_channel_value(channel_id, value)
        for channel_id, value in zip(CHANNEL_IDS_V1, preset.values)
    )
    return CameraBaseLookPresetV1(preset.preset_id, values)


def compose_camera_base_look_v1(
    preset_id: str,
    authored_channel_ids: Sequence[str],
    authored_values: Sequence[float],
) -> CameraBaseLookCompositionV1:
    """Resolve a base look and apply sparse, explicit per-channel overrides."""

    preset = resolve_camera_base_look_v1(preset_id)
    ids = tuple(authored_channel_ids)
    source_values = tuple(authored_values)
    if len(ids) != len(source_values) or len(ids) > len(CHANNEL_IDS_V1):
        raise CameraBaseLookError("authored_camera_look_shape")

    overrides: dict[str, float] = {}
    for channel_id, value in zip(ids, source_values):
        if not isinstance(channel_id, str) or channel_id not in _POLICY_BY_ID:
            raise CameraBaseLookError("unsupported_authored_camera_channel")
        if channel_id in overrides:
            raise CameraBaseLookError("duplicate_authored_camera_channel")
        overrides[channel_id] = _validate_channel_value(channel_id, value)

    effective = tuple(
        overrides.get(channel_id, base_value)
        for channel_id, base_value in zip(CHANNEL_IDS_V1, preset.values)
    )
    mask = tuple(channel_id in overrides for channel_id in CHANNEL_IDS_V1)
    return CameraBaseLookCompositionV1(
        preset.preset_id,
        tuple(CHANNEL_IDS_V1),
        tuple(preset.values),
        effective,
        mask,
    )
