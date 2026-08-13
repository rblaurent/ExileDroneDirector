from __future__ import annotations

import random
import unittest
from dataclasses import replace
from math import cos, radians, sin

from airframe_source_sampling_reference import (
    AirframeSourceSamplingError,
    sample_and_compile_airframe_sources,
)
from cinematic_reference import AuthoredSegment, compile_trajectory
from flight_profile_reference import PROFILE_ORDER, compile_flight_profiles
from orientation_reference import compile_orientation_track


def yaw(degrees):
    half = radians(degrees) * 0.5
    return 0.0, 0.0, sin(half), cos(half)


def pitch(degrees):
    half = radians(degrees) * 0.5
    return 0.0, sin(half), 0.0, cos(half)


def fixture(points, durations, *, overrides=(), body=None, gimbal=None):
    segments = tuple(
        AuthoredSegment(duration, "linear", "linear") for duration in durations
    )
    position = compile_trajectory(points, segments)
    body_values = body or tuple(yaw(index * 8.0) for index in range(len(points)))
    gimbal_values = gimbal or tuple(pitch(index * -5.0) for index in range(len(points)))
    body_track = compile_orientation_track(body_values, durations)
    gimbal_track = compile_orientation_track(gimbal_values, durations)
    profile_track = compile_flight_profiles(
        "cinematic_drone", overrides or ("",) * len(durations), len(durations)
    )
    return position, body_track, gimbal_track, profile_track


class AirframeSourceSamplingReferenceTests(unittest.TestCase):
    def test_two_sample_source_preserves_distinct_authorship(self):
        case = fixture(((0.0, 0.0, 0.0), (20.0, 0.0, 0.0)), (1.0,))
        result = sample_and_compile_airframe_sources(*case, 0.5)
        self.assertEqual(result.sample_times, (0.0, 0.5, 1.0))
        self.assertEqual(result.positions[0], (0.0, 0.0, 0.0))
        self.assertEqual(result.positions[-1], (20.0, 0.0, 0.0))
        self.assertNotEqual(result.authored_body_rotations[-1], result.authored_gimbal_rotations[-1])
        self.assertEqual(result.desired_stream.sample_times, result.sample_times)

    def test_partial_terminal_schedule_and_profile_smoothing(self):
        points = ((0.0, 0.0, 0.0), (20.0, 3.0, 0.0), (45.0, 8.0, 1.0))
        case = fixture(points, (0.4, 0.6), overrides=("hybrid", "fpv_cinewhoop"))
        result = sample_and_compile_airframe_sources(*case, 0.3)
        self.assertEqual(result.sample_times, (0.0, 0.3, 0.6, 0.8999999999999999, 1.0))
        self.assertEqual(result.profiles[0].path_follow_weight, 0.65)
        self.assertGreater(result.profiles[2].path_follow_weight, 0.65)
        self.assertLess(result.profiles[2].path_follow_weight, 0.85)

    def test_all_profiles_are_reachable_on_one_timeline(self):
        # Constant-speed straight flight keeps every physical profile inside its
        # acceleration, jerk, and turn-radius envelope.  This test is about
        # profile reachability and smoothing, not expected physical rejection.
        points = tuple((float(index * 20), 0.0, 0.0) for index in range(6))
        case = fixture(points, (0.5,) * 5, overrides=PROFILE_ORDER)
        result = sample_and_compile_airframe_sources(*case, 0.25)
        observed = {round(value.path_follow_weight, 6) for value in result.profiles}
        for expected in (0.35, 0.65, 0.85, 1.0, 0.9):
            self.assertIn(expected, observed)

    def test_timeline_and_shape_divergence_fail_before_publication(self):
        case = fixture(((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)), (0.5, 0.5))
        with self.assertRaises(AirframeSourceSamplingError):
            sample_and_compile_airframe_sources(case[0], replace(case[1], total_seconds=2.0), case[2], case[3], 0.1)
        with self.assertRaises(AirframeSourceSamplingError):
            sample_and_compile_airframe_sources(case[0], case[1], case[2], compile_flight_profiles("hybrid", ("",), 1), 0.1)
        broken_segments = (replace(case[2].segments[0], duration_seconds=0.4),) + case[2].segments[1:]
        with self.assertRaises(AirframeSourceSamplingError):
            sample_and_compile_airframe_sources(case[0], case[1], replace(case[2], segments=broken_segments), case[3], 0.1)

    def test_invalid_schedule_and_downstream_physical_failure_propagate(self):
        case = fixture(((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)), (1.0,))
        for step in (0.0, 0.001, float("nan"), float("inf"), True, None, "nope"):
            with self.subTest(step=step), self.assertRaises(AirframeSourceSamplingError):
                sample_and_compile_airframe_sources(*case, step)
        violent = fixture(
            ((0.0, 0.0, 0.0), (100000.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (0.05, 0.05),
        )
        with self.assertRaises(AirframeSourceSamplingError):
            sample_and_compile_airframe_sources(*violent, 0.05)

    def test_seeded_order_independence_and_source_immutability(self):
        cases = []
        for seed in range(40):
            rng = random.Random(0xEDD5000 + seed)
            count = rng.randint(2, 7)
            durations = tuple(rng.choice((0.2, 0.3, 0.5)) for _ in range(count - 1))
            # Diverse origins, directions, speeds, durations, profiles, and
            # schedules, but a constant velocity in each case.  Random lateral
            # noise would intentionally violate jerk/radius gates and would
            # turn this determinism test into a rejection test.
            origin = (rng.uniform(-100.0, 100.0), rng.uniform(-100.0, 100.0), rng.uniform(-20.0, 20.0))
            direction = (rng.uniform(0.7, 1.0), rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.1))
            speed = rng.uniform(20.0, 80.0)
            elapsed = 0.0
            points = [origin]
            for duration in durations:
                elapsed += duration
                points.append(tuple(origin[axis] + direction[axis] * speed * elapsed for axis in range(3)))
            overrides = tuple(PROFILE_ORDER[(seed + index) % len(PROFILE_ORDER)] for index in range(count - 1))
            cases.append((fixture(tuple(points), durations, overrides=overrides), rng.choice((0.1, 0.2))))
        snapshots = tuple(repr(case) for case, _step in cases)
        forward = [sample_and_compile_airframe_sources(*case, step) for case, step in cases]
        reverse = [sample_and_compile_airframe_sources(*case, step) for case, step in reversed(cases)]
        self.assertEqual(forward, list(reversed(reverse)))
        self.assertEqual(snapshots, tuple(repr(case) for case, _step in cases))


if __name__ == "__main__":
    unittest.main(verbosity=2)
