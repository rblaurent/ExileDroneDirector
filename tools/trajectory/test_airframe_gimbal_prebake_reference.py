import math
import random
import unittest
from dataclasses import replace

from airframe_gimbal_prebake_reference import (
    AirframeGimbalPrebakeError,
    MAXIMUM_SAMPLE_COUNT,
    apply_airframe_angular_rate_limit,
    compile_airframe_gimbal_motion,
    evaluate_airframe_gimbal_motion,
    fixed_sample_times,
)


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def axis_angle(axis, degrees):
    half = math.radians(degrees) * 0.5
    sine = math.sin(half)
    return (axis[0] * sine, axis[1] * sine, axis[2] * sine, math.cos(half))


def same_rotation(left, right, tolerance=1.0e-9):
    return abs(sum(a * b for a, b in zip(left, right))) >= 1.0 - tolerance


class AirframeGimbalPrebakeContracts(unittest.TestCase):
    def compile(self, bodies=None, gimbals=None, rates=None, total=1.0, step=0.25):
        count = len(fixed_sample_times(total, step))
        return compile_airframe_gimbal_motion(
            bodies or [IDENTITY] * count,
            gimbals or [IDENTITY] * count,
            rates or [90.0] * count,
            total,
            step,
        )

    def test_schedule_uses_integer_steps_and_one_exact_terminal_sample(self):
        self.assertEqual(fixed_sample_times(1.0, 0.25), (0.0, 0.25, 0.5, 0.75, 1.0))
        self.assertEqual(fixed_sample_times(1.0, 0.3), (0.0, 0.3, 0.6, 0.8999999999999999, 1.0))

    def test_schedule_rejects_invalid_domains_and_sample_overflow(self):
        for total, step in ((0.0, 0.1), (-1.0, 0.1), (3600.001, 0.1), (1.0, 0.0),
                            (1.0, 1.0 / 241.0), (1.0, 0.501), (math.nan, 0.1), (1.0, math.inf),
                            (True, 0.1), (1.0, False)):
            with self.subTest(total=total, step=step), self.assertRaises(AirframeGimbalPrebakeError):
                fixed_sample_times(total, step)
        with self.assertRaises(AirframeGimbalPrebakeError):
            fixed_sample_times(3600.0, 1.0 / 240.0)

    def test_cardinality_is_exact_for_all_three_input_streams(self):
        count = len(fixed_sample_times(1.0, 0.25))
        good = [IDENTITY] * count
        rates = [90.0] * count
        for bodies, gimbals, limits in ((good[:-1], good, rates), (good, good[:-1], rates), (good, good, rates[:-1])):
            with self.assertRaises(AirframeGimbalPrebakeError):
                compile_airframe_gimbal_motion(bodies, gimbals, limits, 1.0, 0.25)

    def test_quaternions_must_be_finite_normalized_and_nonboolean(self):
        count = len(fixed_sample_times(1.0, 0.25))
        for bad in ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 2.0),
                    (math.nan, 0.0, 0.0, 1.0), (True, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0)):
            bodies = [IDENTITY] * count
            bodies[2] = bad
            with self.subTest(bad=bad), self.assertRaises(AirframeGimbalPrebakeError):
                self.compile(bodies=bodies)
        accepted = [IDENTITY] * count
        accepted[2] = (0.0, 0.0, 0.0, 1.000001)
        self.compile(bodies=accepted)
        rejected = [IDENTITY] * count
        rejected[2] = (0.0, 0.0, 0.0, 1.0000011)
        with self.assertRaises(AirframeGimbalPrebakeError):
            self.compile(bodies=rejected)

    def test_angular_rates_must_be_finite_numeric_and_bounded(self):
        count = len(fixed_sample_times(1.0, 0.25))
        for bad in (0.0, -1.0, 720.001, math.nan, math.inf, True):
            rates = [90.0] * count
            rates[2] = bad
            with self.subTest(bad=bad), self.assertRaises(AirframeGimbalPrebakeError):
                self.compile(rates=rates)

    def test_atomic_rate_limit_public_contract_validates_and_limits(self):
        limited = apply_airframe_angular_rate_limit(
            IDENTITY, axis_angle((0, 0, 1), 90.0), 0.25, 120.0
        )
        self.assertTrue(limited.rate_limited)
        self.assertAlmostEqual(limited.angular_rate_degrees_per_second, 120.0, places=8)
        exact = apply_airframe_angular_rate_limit(
            IDENTITY, axis_angle((1, 0, 0), 30.0), 0.25, 120.0
        )
        self.assertFalse(exact.rate_limited)
        self.assertAlmostEqual(exact.angular_rate_degrees_per_second, 120.0, places=8)
        for previous, desired, delta, rate in (
            ((0.0, 0.0, 0.0, 0.0), IDENTITY, 0.25, 120.0),
            (IDENTITY, (math.nan, 0.0, 0.0, 1.0), 0.25, 120.0),
            (IDENTITY, IDENTITY, 0.0, 120.0),
            (IDENTITY, IDENTITY, 0.501, 120.0),
            (IDENTITY, IDENTITY, 0.25, 0.0),
            (IDENTITY, IDENTITY, 0.25, 720.001),
        ):
            with self.subTest(previous=previous, desired=desired, delta=delta, rate=rate):
                with self.assertRaises(AirframeGimbalPrebakeError):
                    apply_airframe_angular_rate_limit(previous, desired, delta, rate)

    def test_atomic_rate_limit_target_antipodes_and_half_turn_ties_are_byte_identical(self):
        for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            target = axis_angle(axis, 180.0)
            inverse = tuple(-value for value in target)
            left = apply_airframe_angular_rate_limit(IDENTITY, target, 0.25, 90.0)
            right = apply_airframe_angular_rate_limit(IDENTITY, inverse, 0.25, 90.0)
            self.assertEqual(left, right)

    def test_atomic_rate_limit_preserves_authoritative_previous_hemisphere(self):
        previous = tuple(-value for value in axis_angle((1, 0, 0), 120.0))
        result = apply_airframe_angular_rate_limit(previous, axis_angle((0, 1, 0), 80.0), 0.1, 30.0)
        self.assertGreaterEqual(sum(a * b for a, b in zip(previous, result.rotation)), 0.0)

    def test_below_limit_tracks_desired_samples_exactly(self):
        bodies = [axis_angle((0, 0, 1), angle) for angle in (0, 10, 20, 30, 40)]
        gimbals = [axis_angle((0, 1, 0), angle) for angle in (0, -5, -10, -15, -20)]
        result = self.compile(bodies=bodies, gimbals=gimbals, rates=[180.0] * 5)
        self.assertTrue(all(same_rotation(a, b) for a, b in zip(result.body_rotations, bodies)))
        self.assertTrue(all(same_rotation(a, b) for a, b in zip(result.gimbal_rotations, gimbals)))
        self.assertEqual(result.body_rate_limited, (False,) * 5)
        self.assertEqual(result.gimbal_rate_limited, (False,) * 5)

    def test_body_and_gimbal_are_limited_independently(self):
        bodies = [IDENTITY, axis_angle((0, 0, 1), 90)] + [axis_angle((0, 0, 1), 90)] * 3
        gimbals = [IDENTITY, axis_angle((0, 1, 0), 10)] + [axis_angle((0, 1, 0), 10)] * 3
        result = self.compile(bodies=bodies, gimbals=gimbals, rates=[120.0] * 5)
        self.assertAlmostEqual(result.body_angular_rates_degrees_per_second[1], 120.0, places=8)
        self.assertAlmostEqual(result.gimbal_angular_rates_degrees_per_second[1], 40.0, places=8)
        self.assertTrue(result.body_rate_limited[1])
        self.assertFalse(result.gimbal_rate_limited[1])

    def test_each_interval_uses_the_stricter_endpoint_limit(self):
        targets = [IDENTITY, axis_angle((1, 0, 0), 90)] + [axis_angle((1, 0, 0), 90)] * 3
        result = self.compile(bodies=targets, rates=[200.0, 40.0, 200.0, 200.0, 200.0])
        self.assertAlmostEqual(result.body_angular_rates_degrees_per_second[1], 40.0, places=8)

    def test_exact_rate_boundary_is_not_reported_as_limited(self):
        targets = [IDENTITY, axis_angle((1, 0, 0), 30)] + [axis_angle((1, 0, 0), 30)] * 3
        result = self.compile(bodies=targets, rates=[120.0] * 5)
        self.assertAlmostEqual(result.body_angular_rates_degrees_per_second[1], 120.0, places=8)
        self.assertFalse(result.body_rate_limited[1])

    def test_antipodal_inputs_and_exact_half_turn_ties_are_deterministic(self):
        positive = [IDENTITY, axis_angle((1, 0, 0), 180)] + [axis_angle((1, 0, 0), 180)] * 3
        negative = [tuple(-v for v in value) for value in positive]
        left = self.compile(bodies=positive, gimbals=negative, rates=[90.0] * 5)
        right = self.compile(bodies=negative, gimbals=positive, rates=[90.0] * 5)
        self.assertEqual(left.body_rotations, right.body_rotations)
        self.assertEqual(left.gimbal_rotations, right.gimbal_rotations)

    def test_repeated_target_converges_monotonically_without_overshoot(self):
        count = len(fixed_sample_times(1.0, 0.25))
        target = axis_angle((0, 0, 1), 90)
        result = self.compile(bodies=[IDENTITY] + [target] * (count - 1), rates=[60.0] * count)
        remaining = [2 * math.degrees(math.acos(min(1.0, abs(sum(a*b for a, b in zip(value, target)))))) for value in result.body_rotations]
        self.assertTrue(all(a >= b for a, b in zip(remaining, remaining[1:])))
        self.assertTrue(all(abs(sum(v*v for v in value) - 1.0) < 1.0e-12 for value in result.body_rotations))

    def test_profile_rate_changes_produce_distinct_motion_character(self):
        targets = [IDENTITY] + [axis_angle((0, 0, 1), 180)] * 4
        cinematic = self.compile(bodies=targets, rates=[45.0] * 5)
        fpv = self.compile(bodies=targets, rates=[360.0] * 5)
        self.assertGreater(cinematic.body_rate_limited.count(True), fpv.body_rate_limited.count(True))
        self.assertFalse(same_rotation(cinematic.body_rotations[-1], fpv.body_rotations[-1]))

    def test_absolute_time_evaluation_is_clamped_and_history_independent(self):
        bodies = [axis_angle((0, 0, 1), angle) for angle in (0, 20, 40, 60, 80)]
        track = self.compile(bodies=bodies, rates=[360.0] * 5)
        start = evaluate_airframe_gimbal_motion(track, -10.0)
        end = evaluate_airframe_gimbal_motion(track, 10.0)
        self.assertTrue(start.valid and not start.complete and start.segment_index == 0 and start.alpha == 0.0)
        self.assertTrue(end.valid and end.complete and end.segment_index == 3 and end.alpha == 1.0)
        queries = (0.11, 0.87, 0.26, 0.74, 0.5)
        forward = {value: evaluate_airframe_gimbal_motion(track, value) for value in queries}
        reverse = {value: evaluate_airframe_gimbal_motion(track, value) for value in reversed(queries)}
        self.assertEqual(forward, reverse)

    def test_terminal_partial_interval_uses_its_real_duration(self):
        count = len(fixed_sample_times(1.0, 0.3))
        targets = [IDENTITY] * (count - 1) + [axis_angle((0, 0, 1), 20)]
        result = self.compile(bodies=targets, rates=[100.0] * count, total=1.0, step=0.3)
        self.assertAlmostEqual(result.body_angular_rates_degrees_per_second[-1], 100.0, places=7)
        self.assertTrue(result.body_rate_limited[-1])
        evaluation = evaluate_airframe_gimbal_motion(result, 0.95)
        self.assertEqual(evaluation.segment_index, count - 2)
        self.assertAlmostEqual(evaluation.alpha, 0.5, places=12)

    def test_seeded_streams_never_exceed_rate_and_are_invocation_order_independent(self):
        rng = random.Random(0xEDD_F17E)
        cases = []
        for _ in range(100):
            total = rng.uniform(0.05, 2.0)
            step = rng.choice((1/120, 1/60, 1/30, 0.1))
            count = len(fixed_sample_times(total, step))
            bodies = [axis_angle((rng.random(), rng.random(), rng.random()), rng.uniform(-180, 180)) for _ in range(count)]
            # Normalize arbitrary axes used by the fixture helper.
            normalized = []
            for value in bodies:
                magnitude = math.sqrt(sum(v*v for v in value))
                normalized.append(tuple(v/magnitude for v in value))
            gimbals = [tuple(-v for v in value) if rng.random() < 0.5 else value for value in normalized]
            rates = [rng.uniform(1.0, 720.0) for _ in range(count)]
            cases.append((normalized, gimbals, rates, total, step))
        forward = [compile_airframe_gimbal_motion(*case) for case in cases]
        reverse = [compile_airframe_gimbal_motion(*case) for case in reversed(cases)]
        self.assertEqual(forward, list(reversed(reverse)))
        for result, case in zip(forward, cases):
            limits = case[2]
            for index in range(1, len(limits)):
                limit = min(limits[index - 1], limits[index])
                self.assertLessEqual(result.body_angular_rates_degrees_per_second[index], limit + 1e-7)
                self.assertLessEqual(result.gimbal_angular_rates_degrees_per_second[index], limit + 1e-7)

    def test_corrupt_compiled_tracks_fail_closed_at_evaluation(self):
        track = self.compile()
        corruptions = (
            replace(track, gimbal_rotations=track.gimbal_rotations[:-1]),
            replace(track, body_rotations=track.body_rotations[:-1]),
            replace(track, body_angular_rates_degrees_per_second=(1.0,) + track.body_angular_rates_degrees_per_second[1:]),
            replace(track, body_angular_rates_degrees_per_second=track.body_angular_rates_degrees_per_second[:2] + (1.0,) + track.body_angular_rates_degrees_per_second[3:]),
            replace(track, body_rate_limited=(1,) + track.body_rate_limited[1:]),
            replace(track, fixed_step_seconds=0.0),
            replace(track, total_seconds=math.nan),
        )
        for corrupt in corruptions:
            result = evaluate_airframe_gimbal_motion(corrupt, 0.5)
            self.assertEqual((result.valid, result.complete, result.segment_index, result.body_rotation), (False, False, -1, None))
        with self.assertRaises(AirframeGimbalPrebakeError):
            evaluate_airframe_gimbal_motion(track, math.nan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
