"""Executable contracts for the common authored camera scalar track."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from camera_scalar_track_reference import (
    CameraScalarKey,
    CameraScalarTrackError,
    compile_camera_scalar_track,
    evaluate_camera_scalar_track,
)


class CameraScalarTrackContracts(unittest.TestCase):
    def assertClose(self, actual, expected, tolerance=1.0e-9):
        self.assertLessEqual(abs(actual - expected), tolerance)

    def test_constant_track_and_absolute_time_clamping(self):
        track = compile_camera_scalar_track((CameraScalarKey(0.0, 35.0),), 0.0, minimum=1.0)
        for query in (-100.0, 0.0, 100.0):
            sample = evaluate_camera_scalar_track(track, query)
            self.assertEqual((sample.value, sample.velocity, sample.acceleration), (35.0, 0.0, 0.0))
            self.assertEqual(sample.segment_index, -1)
            self.assertTrue(sample.complete)

    def test_curve_presets_have_exact_values_and_boundary_derivatives(self):
        for mode, midpoint, continuous_order in (
            ("linear", 5.0, 0),
            ("smooth", 5.0, 1),
            ("cinematic", 5.0, 2),
        ):
            track = compile_camera_scalar_track((CameraScalarKey(0.0, 0.0, mode), CameraScalarKey(2.0, 10.0)), 2.0)
            self.assertClose(evaluate_camera_scalar_track(track, 1.0).value, midpoint)
            left = evaluate_camera_scalar_track(track, 0.0)
            right = evaluate_camera_scalar_track(track, 2.0)
            if continuous_order >= 1:
                self.assertClose(left.velocity, 0.0)
                self.assertClose(right.velocity, 0.0)
            if continuous_order >= 2:
                self.assertClose(left.acceleration, 0.0)
                self.assertClose(right.acceleration, 0.0)

    def test_hold_is_explicitly_discontinuous(self):
        track = compile_camera_scalar_track((CameraScalarKey(0.0, 2.0, "hold"), CameraScalarKey(1.0, 8.0)), 1.0)
        self.assertEqual(evaluate_camera_scalar_track(track, 0.999).value, 2.0)
        self.assertEqual(evaluate_camera_scalar_track(track, 1.0).value, 8.0)
        self.assertEqual(evaluate_camera_scalar_track(track, 1.001).value, 8.0)

    def test_hermite_uses_authored_domain_tangents(self):
        keys = (
            CameraScalarKey(0.0, 0.0, "hermite", leave_tangent=4.0),
            CameraScalarKey(2.0, 10.0, arrive_tangent=4.0),
        )
        track = compile_camera_scalar_track(keys, 2.0)
        self.assertClose(evaluate_camera_scalar_track(track, 0.0).velocity, 4.0)
        self.assertClose(evaluate_camera_scalar_track(track, 2.0).velocity, 4.0)
        self.assertClose(evaluate_camera_scalar_track(track, 1.0).value, 5.0)

    def test_reciprocal_focus_interpolation_is_optical_not_linear_distance(self):
        track = compile_camera_scalar_track(
            (CameraScalarKey(0.0, 100.0, "linear"), CameraScalarKey(2.0, 400.0)),
            2.0,
            domain="reciprocal",
            minimum=1.0,
        )
        midpoint = evaluate_camera_scalar_track(track, 1.0)
        self.assertClose(midpoint.value, 160.0)
        self.assertNotEqual(midpoint.value, 250.0)
        self.assertTrue(math.isfinite(midpoint.velocity) and math.isfinite(midpoint.acceleration))

    def test_bounded_effect_output_clamps_overshoot_without_mutating_keys(self):
        keys = (
            CameraScalarKey(0.0, 0.2, "hermite", leave_tangent=4.0),
            CameraScalarKey(1.0, 0.8, arrive_tangent=-4.0),
        )
        track = compile_camera_scalar_track(keys, 1.0, minimum=0.0, maximum=1.0, clamp_output=True)
        sample = evaluate_camera_scalar_track(track, 0.5)
        self.assertGreaterEqual(sample.value, 0.0)
        self.assertLessEqual(sample.value, 1.0)
        self.assertEqual(tuple(key.value for key in keys), (0.2, 0.8))

    def test_invalid_shapes_domains_ranges_and_hidden_tangents_fail_closed(self):
        valid = (CameraScalarKey(0.0, 1.0, "linear"), CameraScalarKey(1.0, 2.0))
        cases = (
            ((), 0.0, {}),
            ((CameraScalarKey(1.0, 1.0),), 1.0, {}),
            ((CameraScalarKey(0.0, 1.0),), 1.0, {}),
            ((valid[0], replace(valid[1], time_seconds=0.0)), 0.0, {}),
            ((replace(valid[0], interpolation_out="bad"), valid[1]), 1.0, {}),
            ((replace(valid[0], leave_tangent=1.0), valid[1]), 1.0, {}),
            ((replace(valid[0], arrive_tangent=1.0), valid[1]), 1.0, {}),
            ((valid[0], replace(valid[1], leave_tangent=1.0)), 1.0, {}),
            (valid, 1.0, {"domain": "bad"}),
            ((CameraScalarKey(0.0, 0.0),), 0.0, {"domain": "reciprocal"}),
            (valid, 1.0, {"minimum": 3.0}),
            (valid, 1.0, {"minimum": 3.0, "maximum": 2.0}),
        )
        for keys, duration, kwargs in cases:
            with self.subTest(keys=keys, kwargs=kwargs), self.assertRaises(CameraScalarTrackError):
                compile_camera_scalar_track(keys, duration, **kwargs)
        with self.assertRaises(CameraScalarTrackError):
            evaluate_camera_scalar_track(compile_camera_scalar_track(valid, 1.0), math.nan)

    def test_seeded_forward_reverse_queries_are_history_free(self):
        for seed in range(40):
            rng = random.Random(0xEDD500 + seed)
            values = [rng.uniform(18.0, 120.0) for _ in range(5)]
            modes = [rng.choice(("linear", "smooth", "cinematic")) for _ in range(4)]
            keys = tuple(CameraScalarKey(float(index), value, modes[index] if index < 4 else "cinematic") for index, value in enumerate(values))
            track = compile_camera_scalar_track(keys, 4.0, minimum=1.0)
            queries = [index / 8.0 for index in range(33)]
            forward = {query: evaluate_camera_scalar_track(track, query) for query in queries}
            reverse = {query: evaluate_camera_scalar_track(track, query) for query in reversed(queries)}
            self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main(verbosity=2)
