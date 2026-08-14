"""Engine-neutral dolly-zoom authoring helper.

The helper derives a focal-length track from an already authored camera-position
schedule and one fixed world subject.  It never changes position or either
orientation track.  Constant framing assumes the separately authored gimbal
keeps the optical axis on the selected subject.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import dist, isfinite
from typing import Sequence


MAXIMUM_SAMPLES_V1 = 65_536
MINIMUM_SUBJECT_DISTANCE_CM_V1 = 1.0
MINIMUM_FOCAL_LENGTH_MM_V1 = 1.0
MAXIMUM_FOCAL_LENGTH_MM_V1 = 1000.0


class CameraDollyZoomError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CameraDollyZoomV1:
    times_seconds: tuple[float, ...]
    subject_distances_cm: tuple[float, ...]
    focal_lengths_mm: tuple[float, ...]
    reference_sample_index: int
    reference_distance_cm: float
    reference_focal_length_mm: float


def _finite(value: object, code: str) -> float:
    if isinstance(value, bool):
        raise CameraDollyZoomError(code)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CameraDollyZoomError(code) from error
    if not isfinite(result):
        raise CameraDollyZoomError(code)
    return result


def _vector(value: object, code: str) -> tuple[float, float, float]:
    try:
        values = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise CameraDollyZoomError(code) from error
    if len(values) != 3:
        raise CameraDollyZoomError(code)
    return tuple(_finite(component, code) for component in values)  # type: ignore[return-value]


def compile_camera_dolly_zoom_v1(
    times_seconds: Sequence[object],
    camera_positions: Sequence[object],
    subject_position: object,
    reference_sample_index: object,
    reference_focal_length_mm: object,
) -> CameraDollyZoomV1:
    """Derive a whole focal track or reject without partial publication."""

    count = len(times_seconds)
    if not 2 <= count <= MAXIMUM_SAMPLES_V1 or len(camera_positions) != count:
        raise CameraDollyZoomError("camera_dolly_shape_invalid")
    times = tuple(_finite(value, "camera_dolly_time_invalid") for value in times_seconds)
    if times[0] != 0.0 or any(right <= left for left, right in zip(times, times[1:])):
        raise CameraDollyZoomError("camera_dolly_timeline_invalid")
    positions = tuple(_vector(value, "camera_dolly_camera_position_invalid") for value in camera_positions)
    subject = _vector(subject_position, "camera_dolly_subject_position_invalid")
    if isinstance(reference_sample_index, bool) or not isinstance(reference_sample_index, int):
        raise CameraDollyZoomError("camera_dolly_reference_index_invalid")
    if not 0 <= reference_sample_index < count:
        raise CameraDollyZoomError("camera_dolly_reference_index_invalid")
    focal = _finite(reference_focal_length_mm, "camera_dolly_reference_focal_invalid")
    if not MINIMUM_FOCAL_LENGTH_MM_V1 <= focal <= MAXIMUM_FOCAL_LENGTH_MM_V1:
        raise CameraDollyZoomError("camera_dolly_reference_focal_invalid")

    distances = tuple(dist(position, subject) for position in positions)
    if any(not isfinite(value) or value < MINIMUM_SUBJECT_DISTANCE_CM_V1 for value in distances):
        raise CameraDollyZoomError("camera_dolly_subject_distance_invalid")
    reference_distance = distances[reference_sample_index]
    focal_lengths = tuple(focal * value / reference_distance for value in distances)
    if any(
        not isfinite(value) or not MINIMUM_FOCAL_LENGTH_MM_V1 <= value <= MAXIMUM_FOCAL_LENGTH_MM_V1
        for value in focal_lengths
    ):
        raise CameraDollyZoomError("camera_dolly_derived_focal_invalid")
    return CameraDollyZoomV1(
        times,
        distances,
        focal_lengths,
        reference_sample_index,
        reference_distance,
        focal,
    )
