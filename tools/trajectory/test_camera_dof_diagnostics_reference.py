"""Executable contracts for focal-plane and approximate DOF diagnostics."""

from __future__ import annotations

import math
import random
import unittest

from camera_channel_assembly_reference import CHANNEL_IDS_V1, CHANNEL_POLICIES_V1
from camera_dof_diagnostics_reference import (
    CIRCLE_OF_CONFUSION_DIAGONAL_DIVISOR_V1,
    CameraDofDiagnosticError,
    evaluate_camera_dof_diagnostics_v1,
)


def frame(*, focal=50.0, aperture=2.8, focus=1000.0):
    values = [policy.default_value for policy in CHANNEL_POLICIES_V1]
    values[CHANNEL_IDS_V1.index("focal_length_mm")] = focal
    values[CHANNEL_IDS_V1.index("aperture_fstop")] = aperture
    values[CHANNEL_IDS_V1.index("focus_distance_cm")] = focus
    return values


class CameraDofDiagnosticContracts(unittest.TestCase):
    def test_full_frame_thin_lens_solution_and_plane_size_are_exact(self):
        result = evaluate_camera_dof_diagnostics_v1(True, 36.0, 24.0, frame())
        coc = math.hypot(36.0, 24.0) / CIRCLE_OF_CONFUSION_DIAGONAL_DIVISOR_V1
        hyperfocal_mm = 50.0 * 50.0 / (2.8 * coc) + 50.0
        near_mm = hyperfocal_mm * 10000.0 / (hyperfocal_mm + 9950.0)
        far_mm = hyperfocal_mm * 10000.0 / (hyperfocal_mm - 9950.0)
        self.assertAlmostEqual(result.circle_of_confusion_mm, coc)
        self.assertAlmostEqual(result.hyperfocal_distance_cm, hyperfocal_mm / 10.0)
        self.assertAlmostEqual(result.near_limit_cm, near_mm / 10.0)
        self.assertAlmostEqual(result.far_limit_cm, far_mm / 10.0)
        self.assertFalse(result.far_unbounded)
        self.assertAlmostEqual(result.focal_plane_width_cm, 720.0)
        self.assertAlmostEqual(result.focal_plane_height_cm, 480.0)

    def test_hyperfocal_boundary_uses_explicit_unbounded_far_state(self):
        coc = math.hypot(36.0, 24.0) / CIRCLE_OF_CONFUSION_DIAGONAL_DIVISOR_V1
        hyperfocal_mm = 35.0 * 35.0 / (8.0 * coc) + 35.0
        focus_cm = (hyperfocal_mm + 35.0) / 10.0
        result = evaluate_camera_dof_diagnostics_v1(True, 36.0, 24.0, frame(focal=35.0, aperture=8.0, focus=focus_cm))
        self.assertTrue(result.far_unbounded)
        self.assertEqual(result.far_limit_cm, 0.0)
        self.assertEqual(result.rear_depth_cm, 0.0)
        self.assertLess(result.near_limit_cm, result.focal_plane_distance_cm)

    def test_narrower_aperture_expands_the_bounded_depth_range(self):
        wide = evaluate_camera_dof_diagnostics_v1(True, 36.0, 24.0, frame(aperture=1.4, focus=500.0))
        narrow = evaluate_camera_dof_diagnostics_v1(True, 36.0, 24.0, frame(aperture=8.0, focus=500.0))
        self.assertGreater(narrow.front_depth_cm, wide.front_depth_cm)
        self.assertGreater(narrow.rear_depth_cm, wide.rear_depth_cm)

    def test_diagnostic_does_not_mutate_the_evaluated_frame(self):
        values = frame(focal=85.0, aperture=4.0, focus=2000.0)
        before = tuple(values)
        evaluate_camera_dof_diagnostics_v1(True, 36.0, 24.0, values)
        self.assertEqual(tuple(values), before)

    def test_invalid_frame_shapes_ranges_and_non_finite_values_fail_closed(self):
        cases = (
            (False, 36.0, 24.0, frame(), "camera_dof_frame_invalid"),
            (True, 36.0, 24.0, frame()[:-1], "camera_dof_frame_shape_invalid"),
            (True, 0.0, 24.0, frame(), "camera_dof_filmback_invalid"),
            (True, 36.0, 24.0, frame(focal=0.5), "camera_dof_focal_length_invalid"),
            (True, 36.0, 24.0, frame(aperture=0.0), "camera_dof_aperture_invalid"),
            (True, 36.0, 24.0, frame(focus=0.5), "camera_dof_focus_distance_invalid"),
            (True, 36.0, 24.0, frame(focal=1000.0, focus=50.0), "camera_dof_focus_not_beyond_focal_length"),
            (True, 36.0, 24.0, frame()[:-1] + [math.nan], "camera_dof_channel_matte_weight_invalid"),
        )
        for valid, width, height, values, code in cases:
            with self.subTest(code=code), self.assertRaises(CameraDofDiagnosticError) as raised:
                evaluate_camera_dof_diagnostics_v1(valid, width, height, values)
            self.assertEqual(raised.exception.code, code)

    def test_seeded_forward_and_reverse_evaluation_is_history_free(self):
        randomizer = random.Random(0xD0F2026)
        cases = []
        for _ in range(80):
            width = randomizer.uniform(10.0, 70.0)
            height = randomizer.uniform(8.0, 50.0)
            focal = randomizer.uniform(8.0, 300.0)
            aperture = randomizer.uniform(0.7, 22.0)
            focus = randomizer.uniform(focal / 10.0 + 1.0, 20000.0)
            cases.append((width, height, frame(focal=focal, aperture=aperture, focus=focus)))
        forward = [evaluate_camera_dof_diagnostics_v1(True, width, height, values) for width, height, values in cases]
        reverse = [evaluate_camera_dof_diagnostics_v1(True, width, height, values) for width, height, values in reversed(cases)]
        self.assertEqual(tuple(forward), tuple(reversed(reverse)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
