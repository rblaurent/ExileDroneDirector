"""Engine-neutral focal-plane and approximate depth-of-field diagnostics.

The accepted camera-channel evaluator owns lens/focus authorship.  This module
is a read-only diagnostic boundary over one complete evaluated frame.  It uses
the standard thin-lens depth-of-field approximation and publishes an explicit
unbounded-far flag instead of encoding infinity in a Blueprint float.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Sequence

from camera_channel_assembly_reference import CHANNEL_IDS_V1


CHANNEL_COUNT_V1 = len(CHANNEL_IDS_V1)
FOCAL_LENGTH_INDEX_V1 = CHANNEL_IDS_V1.index("focal_length_mm")
APERTURE_INDEX_V1 = CHANNEL_IDS_V1.index("aperture_fstop")
FOCUS_DISTANCE_INDEX_V1 = CHANNEL_IDS_V1.index("focus_distance_cm")
CIRCLE_OF_CONFUSION_DIAGONAL_DIVISOR_V1 = 1500.0


class CameraDofDiagnosticError(ValueError):
    """The evaluated frame cannot produce a truthful DOF diagnostic."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CameraDofDiagnosticsV1:
    circle_of_confusion_mm: float
    hyperfocal_distance_cm: float
    focal_plane_distance_cm: float
    near_limit_cm: float
    far_limit_cm: float
    far_unbounded: bool
    front_depth_cm: float
    rear_depth_cm: float
    focal_plane_width_cm: float
    focal_plane_height_cm: float


def _finite(value: object, code: str) -> float:
    if isinstance(value, bool):
        raise CameraDofDiagnosticError(code)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraDofDiagnosticError(code) from error
    if not isfinite(result):
        raise CameraDofDiagnosticError(code)
    return result


def evaluate_camera_dof_diagnostics_v1(
    frame_valid: bool,
    filmback_sensor_width_mm: object,
    filmback_sensor_height_mm: object,
    channel_values: Sequence[object],
) -> CameraDofDiagnosticsV1:
    """Evaluate one immutable camera frame into bounded diagnostic values."""

    if frame_valid is not True:
        raise CameraDofDiagnosticError("camera_dof_frame_invalid")
    if len(channel_values) != CHANNEL_COUNT_V1:
        raise CameraDofDiagnosticError("camera_dof_frame_shape_invalid")

    values = tuple(
        _finite(value, f"camera_dof_channel_{CHANNEL_IDS_V1[index]}_invalid")
        for index, value in enumerate(channel_values)
    )
    sensor_width_mm = _finite(filmback_sensor_width_mm, "camera_dof_filmback_invalid")
    sensor_height_mm = _finite(filmback_sensor_height_mm, "camera_dof_filmback_invalid")
    if sensor_width_mm <= 0.0 or sensor_height_mm <= 0.0:
        raise CameraDofDiagnosticError("camera_dof_filmback_invalid")

    focal_length_mm = values[FOCAL_LENGTH_INDEX_V1]
    aperture_fstop = values[APERTURE_INDEX_V1]
    focus_distance_cm = values[FOCUS_DISTANCE_INDEX_V1]
    if not 1.0 <= focal_length_mm <= 1000.0:
        raise CameraDofDiagnosticError("camera_dof_focal_length_invalid")
    if not 0.1 <= aperture_fstop <= 64.0:
        raise CameraDofDiagnosticError("camera_dof_aperture_invalid")
    if not 1.0 <= focus_distance_cm <= 1.0e9:
        raise CameraDofDiagnosticError("camera_dof_focus_distance_invalid")

    focus_distance_mm = focus_distance_cm * 10.0
    if focus_distance_mm <= focal_length_mm:
        raise CameraDofDiagnosticError("camera_dof_focus_not_beyond_focal_length")

    circle_of_confusion_mm = hypot(sensor_width_mm, sensor_height_mm) / CIRCLE_OF_CONFUSION_DIAGONAL_DIVISOR_V1
    hyperfocal_mm = focal_length_mm * focal_length_mm / (aperture_fstop * circle_of_confusion_mm) + focal_length_mm
    near_denominator = hyperfocal_mm + (focus_distance_mm - focal_length_mm)
    near_limit_mm = hyperfocal_mm * focus_distance_mm / near_denominator

    far_unbounded = focus_distance_mm >= hyperfocal_mm + focal_length_mm
    if far_unbounded:
        far_limit_cm = 0.0
        rear_depth_cm = 0.0
    else:
        far_denominator = hyperfocal_mm - (focus_distance_mm - focal_length_mm)
        far_limit_cm = (hyperfocal_mm * focus_distance_mm / far_denominator) / 10.0
        rear_depth_cm = far_limit_cm - focus_distance_cm

    near_limit_cm = near_limit_mm / 10.0
    result = CameraDofDiagnosticsV1(
        circle_of_confusion_mm=circle_of_confusion_mm,
        hyperfocal_distance_cm=hyperfocal_mm / 10.0,
        focal_plane_distance_cm=focus_distance_cm,
        near_limit_cm=near_limit_cm,
        far_limit_cm=far_limit_cm,
        far_unbounded=far_unbounded,
        front_depth_cm=focus_distance_cm - near_limit_cm,
        rear_depth_cm=rear_depth_cm,
        focal_plane_width_cm=focus_distance_cm * sensor_width_mm / focal_length_mm,
        focal_plane_height_cm=focus_distance_cm * sensor_height_mm / focal_length_mm,
    )
    if not all(
        isfinite(value)
        for value in (
            result.circle_of_confusion_mm,
            result.hyperfocal_distance_cm,
            result.focal_plane_distance_cm,
            result.near_limit_cm,
            result.far_limit_cm,
            result.front_depth_cm,
            result.rear_depth_cm,
            result.focal_plane_width_cm,
            result.focal_plane_height_cm,
        )
    ):
        raise CameraDofDiagnosticError("camera_dof_result_non_finite")
    return result
