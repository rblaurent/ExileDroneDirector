"""Executable contracts for deterministic dolly-zoom authoring."""

from __future__ import annotations

import math
import random
import unittest
from dataclasses import FrozenInstanceError

from camera_dolly_zoom_reference import CameraDollyZoomError, compile_camera_dolly_zoom_v1


class CameraDollyZoomContracts(unittest.TestCase):
    def test_constant_framing_ratio_and_reference_are_exact(self) -> None:
        result = compile_camera_dolly_zoom_v1(
            (0.0, 1.0, 2.0),
            ((0.0, 0.0, 0.0), (0.0, 500.0, 0.0), (0.0, 1000.0, 0.0)),
            (0.0, 2000.0, 0.0),
            1,
            50.0,
        )
        self.assertEqual(result.subject_distances_cm, (2000.0, 1500.0, 1000.0))
        self.assertEqual(result.focal_lengths_mm, (200.0 / 3.0, 50.0, 100.0 / 3.0))
        ratios = tuple(focal / distance for focal, distance in zip(result.focal_lengths_mm, result.subject_distances_cm))
        self.assertTrue(all(math.isclose(value, ratios[0], rel_tol=1e-14) for value in ratios))

    def test_motion_and_orientation_authorship_are_not_outputs(self) -> None:
        result = compile_camera_dolly_zoom_v1((0, 1), ((0, 0, 0), (100, 0, 0)), (1000, 0, 0), 0, 35)
        self.assertEqual(set(result.__dataclass_fields__), {"times_seconds", "subject_distances_cm", "focal_lengths_mm", "reference_sample_index", "reference_distance_cm", "reference_focal_length_mm"})
        with self.assertRaises(FrozenInstanceError):
            result.reference_distance_cm = 7.0  # type: ignore[misc]

    def test_inputs_are_value_snapshotted(self) -> None:
        times = [0.0, 1.0]; positions = [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]]; subject = [1000.0, 0.0, 0.0]
        result = compile_camera_dolly_zoom_v1(times, positions, subject, 0, 35.0)
        times[1] = 9.0; positions[0][0] = 9.0; subject[0] = 9.0
        self.assertEqual(result.times_seconds, (0.0, 1.0))
        self.assertEqual(result.subject_distances_cm, (1000.0, 900.0))

    def test_failures_are_typed_and_whole_track(self) -> None:
        base = ((0.0, 1.0), ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0)), (1000.0, 0.0, 0.0), 0, 35.0)
        failures = (
            ((0.0,), base[1], base[2], 0, 35.0),
            (base[0], base[1][:1], base[2], 0, 35.0),
            ((0.0, 0.0), base[1], base[2], 0, 35.0),
            ((1.0, 2.0), base[1], base[2], 0, 35.0),
            ((0.0, math.nan), base[1], base[2], 0, 35.0),
            (base[0], ((math.inf, 0, 0), base[1][1]), base[2], 0, 35.0),
            (base[0], base[1], (math.nan, 0, 0), 0, 35.0),
            (base[0], base[1], base[2], True, 35.0),
            (base[0], base[1], base[2], 2, 35.0),
            (base[0], base[1], base[2], 0, 0.9),
            (base[0], ((1000, 0, 0), base[1][1]), base[2], 1, 35.0),
            (base[0], ((0, 0, 0), (-1, 0, 0)), base[2], 0, 1000.0),
        )
        for case in failures:
            with self.subTest(case=case), self.assertRaises(CameraDollyZoomError):
                compile_camera_dolly_zoom_v1(*case)

    def test_seeded_forward_and_reverse_spatial_routes_are_history_free(self) -> None:
        rng = random.Random(0xD0117)
        for _ in range(80):
            count = rng.randint(2, 24); times = tuple(float(i) * 0.125 for i in range(count)); subject = (10000.0, 3000.0, 1200.0)
            positions = tuple((rng.uniform(-500, 500), rng.uniform(-500, 500), rng.uniform(-500, 500)) for _ in range(count))
            reference = rng.randrange(count); focal = rng.uniform(20.0, 120.0)
            forward = compile_camera_dolly_zoom_v1(times, positions, subject, reference, focal)
            reverse_positions = tuple(reversed(positions)); reverse_reference = count - 1 - reference
            reverse = compile_camera_dolly_zoom_v1(times, reverse_positions, subject, reverse_reference, focal)
            self.assertEqual(reverse.subject_distances_cm, tuple(reversed(forward.subject_distances_cm)))
            self.assertEqual(reverse.focal_lengths_mm, tuple(reversed(forward.focal_lengths_mm)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
