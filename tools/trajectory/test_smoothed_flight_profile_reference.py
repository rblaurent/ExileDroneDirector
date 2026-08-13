"""Executable contracts for C2 compiled flight-profile transitions."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from flight_profile_reference import (
    CompiledFlightProfiles,
    PROFILE_ORDER,
    PROFILES,
    compile_flight_profiles,
)
from smoothed_flight_profile_reference import (
    PARAMETER_FIELDS,
    SmoothedFlightProfileError,
    evaluate_smoothed_flight_profile,
)


class SmoothedFlightProfileContracts(unittest.TestCase):
    def setUp(self):
        self.compiled = compile_flight_profiles(
            "cinematic_drone",
            ("", "hybrid", "fpv_freestyle", "fpv_long_range"),
            4,
        )

    def test_single_segment_and_identical_neighbors_remain_exact(self):
        single = compile_flight_profiles("hybrid", ("",), 1)
        repeated = compile_flight_profiles("hybrid", ("", "", ""), 3)
        for compiled, indices in ((single, (0,)), (repeated, (0, 1, 2))):
            for index in indices:
                for alpha in (0.0, 0.1, 0.5, 0.9, 1.0):
                    result = evaluate_smoothed_flight_profile(compiled, index, alpha)
                    self.assertEqual(result.current_profile_id, "hybrid")
                    self.assertEqual(result.neighbor_profile_id, "hybrid")
                    self.assertEqual(result.neighbor_weight, 0.0)
                    for field in PARAMETER_FIELDS:
                        self.assertEqual(getattr(result.parameters, field), getattr(PROFILES["hybrid"], field))

    def test_each_segment_owns_its_exact_preset_at_midpoint(self):
        for index, expected in enumerate(("cinematic_drone", "hybrid", "fpv_freestyle", "fpv_long_range")):
            result = evaluate_smoothed_flight_profile(self.compiled, index, 0.5)
            self.assertEqual(result.current_profile_id, expected)
            self.assertEqual(result.neighbor_profile_id, expected)
            self.assertEqual(result.neighbor_weight, 0.0)
            for field in PARAMETER_FIELDS:
                self.assertEqual(getattr(result.parameters, field), getattr(PROFILES[expected], field))

    def test_track_endpoints_remain_exact_and_evaluation_never_mutates_publication(self):
        original = self.compiled
        first = evaluate_smoothed_flight_profile(self.compiled, 0, 0.0)
        last = evaluate_smoothed_flight_profile(self.compiled, 3, 1.0)
        self.assertEqual(first.current_profile_id, "cinematic_drone")
        self.assertEqual(first.neighbor_weight, 0.0)
        self.assertEqual(last.current_profile_id, "fpv_long_range")
        self.assertEqual(last.neighbor_weight, 0.0)
        for field in PARAMETER_FIELDS:
            self.assertEqual(getattr(first.parameters, field), getattr(PROFILES["cinematic_drone"], field))
            self.assertEqual(getattr(last.parameters, field), getattr(PROFILES["fpv_long_range"], field))
        self.assertIs(self.compiled, original)
        self.assertEqual(self.compiled, original)

    def test_adjacent_segments_share_the_exact_same_boundary_value(self):
        for left_index in range(self.compiled.segment_count - 1):
            left = evaluate_smoothed_flight_profile(self.compiled, left_index, 1.0)
            right = evaluate_smoothed_flight_profile(self.compiled, left_index + 1, 0.0)
            for field in PARAMETER_FIELDS:
                expected = 0.5 * (
                    getattr(PROFILES[left.current_profile_id], field)
                    + getattr(PROFILES[right.current_profile_id], field)
                )
                self.assertEqual(getattr(left.parameters, field), expected)
                self.assertEqual(getattr(right.parameters, field), expected)

    def test_transition_has_zero_first_and_second_derivative_at_boundaries(self):
        field = "max_jerk_cm_per_second_cubed"
        left_duration, right_duration = 0.37, 4.9
        def value(offset: float) -> float:
            if offset <= 0.0:
                result = evaluate_smoothed_flight_profile(
                    self.compiled, 1, 1.0 + offset / left_duration
                )
            else:
                result = evaluate_smoothed_flight_profile(
                    self.compiled, 2, offset / right_duration
                )
            return getattr(result.parameters, field)

        def derivatives(step: float) -> tuple[float, float, float, float, float]:
            samples = {offset: value(offset) for offset in (-2*step, -step, 0.0, step, 2*step)}
            return (
                (samples[0.0] - samples[-step]) / step,
                (samples[step] - samples[0.0]) / step,
                (samples[0.0] - 2*samples[-step] + samples[-2*step]) / (step*step),
                (samples[2*step] - 2*samples[step] + samples[0.0]) / (step*step),
                max(abs(samples[0.0]), 1.0),
            )

        coarse = derivatives(1.0e-4)
        left_d1, right_d1, left_d2, right_d2, scale = derivatives(1.0e-5)
        self.assertLess(abs(left_d1) / scale, 1.0e-7)
        self.assertLess(abs(right_d1) / scale, 1.0e-7)
        self.assertLess(abs(left_d2) / scale, 0.1)
        self.assertLess(abs(right_d2) / scale, 0.1)
        self.assertLess(abs(left_d2), abs(coarse[2]) * 0.2)
        self.assertLess(abs(right_d2), abs(coarse[3]) * 0.2)

    def test_midpoint_is_c2_and_does_not_cross_to_the_other_neighbor(self):
        center = evaluate_smoothed_flight_profile(self.compiled, 1, 0.5)
        left = evaluate_smoothed_flight_profile(self.compiled, 1, 0.5 - 1.0e-6)
        right = evaluate_smoothed_flight_profile(self.compiled, 1, 0.5 + 1.0e-6)
        self.assertEqual(center.neighbor_weight, 0.0)
        self.assertEqual(left.neighbor_profile_id, "cinematic_drone")
        self.assertEqual(right.neighbor_profile_id, "fpv_freestyle")
        for field in PARAMETER_FIELDS:
            expected = getattr(PROFILES["hybrid"], field)
            self.assertAlmostEqual(getattr(left.parameters, field), expected, places=12)
            self.assertEqual(getattr(center.parameters, field), expected)
            self.assertAlmostEqual(getattr(right.parameters, field), expected, places=12)

    def test_every_blended_parameter_remains_inside_its_neighbor_convex_hull(self):
        for index in range(self.compiled.segment_count):
            for step in range(101):
                result = evaluate_smoothed_flight_profile(self.compiled, index, step / 100.0)
                current = PROFILES[result.current_profile_id]
                neighbor = PROFILES[result.neighbor_profile_id]
                self.assertGreaterEqual(result.neighbor_weight, 0.0)
                self.assertLessEqual(result.neighbor_weight, 0.5)
                for field in PARAMETER_FIELDS:
                    value = getattr(result.parameters, field)
                    low, high = sorted((getattr(current, field), getattr(neighbor, field)))
                    self.assertGreaterEqual(value, low)
                    self.assertLessEqual(value, high)

    def test_direct_scrubbing_is_history_independent(self):
        queries = ((3, 1.0), (0, 0.0), (2, 0.125), (1, 0.5), (2, 0.125), (1, 0.999))
        forward = {query: evaluate_smoothed_flight_profile(self.compiled, *query) for query in queries}
        reverse = {query: evaluate_smoothed_flight_profile(self.compiled, *query) for query in reversed(queries)}
        self.assertEqual(forward, reverse)

    def test_invalid_inputs_and_corrupt_publications_fail_closed(self):
        bad_inputs = ((-1, 0.5), (4, 0.5), (True, 0.5), (0, -0.001), (0, 1.001), (0, math.nan), (0, math.inf), (0, True), (0, "bad"))
        for index, alpha in bad_inputs:
            with self.subTest(index=index, alpha=alpha), self.assertRaises(SmoothedFlightProfileError):
                evaluate_smoothed_flight_profile(self.compiled, index, alpha)

        corrupt_profile = replace(PROFILES["hybrid"], bank_gain=math.nan)
        corruptions = (
            replace(self.compiled, segment_count=True),
            replace(self.compiled, segment_count=5),
            replace(self.compiled, profiles=self.compiled.profiles[:-1]),
            CompiledFlightProfiles(4, (self.compiled.profiles[0], corrupt_profile, *self.compiled.profiles[2:])),
        )
        for compiled in corruptions:
            with self.subTest(compiled=compiled), self.assertRaises(SmoothedFlightProfileError):
                evaluate_smoothed_flight_profile(compiled, 0, 0.5)

    def test_seeded_ceiling_tracks_are_deterministic_finite_and_bounded(self):
        rng = random.Random(0xEDD082)
        overrides = tuple(rng.choice(PROFILE_ORDER) for _ in range(511))
        compiled = compile_flight_profiles("cinematic_drone", overrides, 511)
        queries = [(rng.randrange(511), rng.random()) for _ in range(1000)]
        first = [evaluate_smoothed_flight_profile(compiled, *query) for query in queries]
        second = [evaluate_smoothed_flight_profile(compiled, *query) for query in reversed(queries)]
        self.assertEqual(first, list(reversed(second)))
        for result in first:
            self.assertTrue(all(math.isfinite(getattr(result.parameters, field)) for field in PARAMETER_FIELDS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
