import math
import random
import unittest
from dataclasses import replace

from airframe_desired_stream_reference import (
    AirframeDesiredStreamError,
    compile_airframe_desired_stream,
    differentiate_sampled_vectors,
    sample_vector_track_linear,
)
from airframe_gimbal_prebake_reference import fixed_sample_times
from airframe_gimbal_reference import AirframeGimbalProfile


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def profile(**changes):
    base = AirframeGimbalProfile(
        path_follow_weight=1.0,
        horizon_stabilization_weight=0.5,
        look_ahead_seconds=0.0,
        bank_gain=0.0,
        max_bank_degrees=45.0,
        camera_uptilt_degrees=0.0,
        max_angular_rate_degrees_per_second=180.0,
        max_acceleration_cm_per_second_squared=10000.0,
        max_jerk_cm_per_second_cubed=50000.0,
        minimum_turn_radius_cm=1.0,
    )
    return replace(base, **changes)


class AirframeDesiredStreamContracts(unittest.TestCase):
    def compile(self, positions=None, profiles=None, bodies=None, gimbals=None, total=1.0, step=0.25):
        times = fixed_sample_times(total, step)
        count = len(times)
        source_positions = positions or [(100.0 * time, 0.0, 0.0) for time in times]
        return compile_airframe_desired_stream(
            source_positions,
            bodies or [IDENTITY] * count,
            gimbals or [IDENTITY] * count,
            profiles or [profile()] * count,
            total,
            step,
        )

    def test_two_sample_line_has_exact_constant_kinematics(self):
        compiled = self.compile(total=0.1, step=0.5)
        self.assertEqual(compiled.sample_times, (0.0, 0.1))
        self.assertEqual(compiled.velocities, ((100.0, 0.0, 0.0),) * 2)
        self.assertEqual(compiled.accelerations, ((0.0, 0.0, 0.0),) * 2)
        self.assertEqual(compiled.jerks, ((0.0, 0.0, 0.0),) * 2)
        self.assertEqual(len(compiled.motion.body_rotations), 2)

    def test_quadratic_kinematics_are_exact_on_partial_terminal_schedule(self):
        times = fixed_sample_times(1.0, 0.3)
        positions = [(2.0 * time * time + 3.0 * time + 5.0, 0.0, 0.0) for time in times]
        compiled = self.compile(positions=positions, total=1.0, step=0.3)
        for time, velocity, acceleration, jerk in zip(
            times, compiled.velocities, compiled.accelerations, compiled.jerks
        ):
            self.assertAlmostEqual(velocity[0], 4.0 * time + 3.0, places=10)
            self.assertAlmostEqual(acceleration[0], 4.0, places=9)
            self.assertAlmostEqual(jerk[0], 0.0, places=8)

    def test_look_ahead_velocity_is_absolute_linear_and_endpoint_clamped(self):
        times = (0.0, 0.4, 1.0)
        values = ((0.0, 0.0, 0.0), (4.0, 8.0, 0.0), (10.0, 20.0, 0.0))
        self.assertEqual(sample_vector_track_linear(values, times, -1.0), values[0])
        self.assertEqual(sample_vector_track_linear(values, times, 2.0), values[-1])
        interpolated = sample_vector_track_linear(values, times, 0.7)
        self.assertAlmostEqual(interpolated[0], 7.0, places=12)
        self.assertAlmostEqual(interpolated[1], 14.0, places=12)
        self.assertEqual(interpolated[2], 0.0)

        schedule = fixed_sample_times(1.0, 0.25)
        positions = [(100.0 * time * time, 0.0, 0.0) for time in schedule]
        profiles = [profile(look_ahead_seconds=0.375)] * len(schedule)
        compiled = self.compile(positions=positions, profiles=profiles)
        self.assertEqual(compiled.look_ahead_velocities[-1], compiled.velocities[-1])
        expected = sample_vector_track_linear(compiled.velocities, schedule, 0.375)
        self.assertEqual(compiled.look_ahead_velocities[0], expected)

    def test_exact_schedule_cardinality_is_required_for_every_source(self):
        times = fixed_sample_times(1.0, 0.25)
        count = len(times)
        positions = [(time, 0.0, 0.0) for time in times]
        good_quats = [IDENTITY] * count
        good_profiles = [profile()] * count
        cases = (
            (positions[:-1], good_quats, good_quats, good_profiles),
            (positions, good_quats[:-1], good_quats, good_profiles),
            (positions, good_quats, good_quats[:-1], good_profiles),
            (positions, good_quats, good_quats, good_profiles[:-1]),
        )
        for streams in cases:
            with self.subTest(lengths=tuple(map(len, streams))), self.assertRaises(AirframeDesiredStreamError):
                compile_airframe_desired_stream(*streams, 1.0, 0.25)

    def test_derivative_boundary_rejects_shape_time_and_nonfinite_values(self):
        valid = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        cases = (
            (valid[:1], (0.0,)),
            (valid, (0.0,)),
            (valid, (0.0, 0.0)),
            (valid, (0.0, math.nan)),
            (valid, (0.0, True)),
            (valid, (0.0, object())),
            (((0.0, 0.0, 0.0), (math.inf, 0.0, 0.0)), (0.0, 1.0)),
            (((0.0, 0.0, 0.0), (object(), 0.0, 0.0)), (0.0, 1.0)),
        )
        for values, times in cases:
            with self.subTest(values=values, times=times), self.assertRaises(AirframeDesiredStreamError):
                differentiate_sampled_vectors(values, times)

    def test_invalid_quaternion_profile_and_physical_motion_fail_transactionally(self):
        times = fixed_sample_times(1.0, 0.25)
        count = len(times)
        bad_bodies = [IDENTITY] * count
        bad_bodies[2] = (0.0, 0.0, 0.0, 0.0)
        with self.assertRaises(AirframeDesiredStreamError):
            self.compile(bodies=bad_bodies)
        bad_profiles = [profile()] * count
        bad_profiles[1] = profile(max_angular_rate_degrees_per_second=0.0)
        with self.assertRaises(AirframeDesiredStreamError):
            self.compile(profiles=bad_profiles)
        violent = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1000.0, 0.0, 0.0),
                   (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        with self.assertRaises(AirframeDesiredStreamError):
            self.compile(positions=violent, profiles=[profile(max_acceleration_cm_per_second_squared=1.0)] * count)

    def test_angular_rate_profiles_flow_into_the_accepted_prebake(self):
        times = fixed_sample_times(1.0, 0.25)
        positions = [(0.0, 100.0 * time, 0.0) for time in times]
        rates = [30.0, 60.0, 90.0, 120.0, 150.0]
        compiled = self.compile(positions=positions, profiles=[profile(max_angular_rate_degrees_per_second=value) for value in rates])
        self.assertEqual(compiled.maximum_angular_rates_degrees_per_second, tuple(rates))
        self.assertEqual(compiled.motion.fixed_step_seconds, 0.25)
        self.assertEqual(compiled.motion.total_seconds, 1.0)
        self.assertTrue(all(value <= max(rates) for value in compiled.motion.body_angular_rates_degrees_per_second))

    def test_seeded_compilation_is_order_independent_and_finite(self):
        rng = random.Random(0xEDD57EA)
        cases = []
        for _ in range(80):
            step = rng.choice((0.05, 0.1, 0.2, 0.3))
            total = rng.uniform(step * 1.1, min(2.0, step * 8.7))
            times = fixed_sample_times(total, step)
            vx = rng.uniform(20.0, 200.0)
            vy = rng.uniform(-50.0, 50.0)
            ax = rng.uniform(-5.0, 5.0)
            positions = [(vx * time + 0.5 * ax * time * time, vy * time, 0.0) for time in times]
            profiles = [profile(look_ahead_seconds=rng.uniform(0.0, 0.5), bank_gain=rng.uniform(0.0, 1.0)) for _ in times]
            cases.append((positions, profiles, total, step))
        forward = [self.compile(positions=positions, profiles=profiles, total=total, step=step) for positions, profiles, total, step in cases]
        reverse = [self.compile(positions=positions, profiles=profiles, total=total, step=step) for positions, profiles, total, step in reversed(cases)]
        self.assertEqual(forward, list(reversed(reverse)))
        for compiled in forward:
            numeric_vectors = compiled.velocities + compiled.accelerations + compiled.jerks + compiled.look_ahead_velocities
            self.assertTrue(all(math.isfinite(component) for vector in numeric_vectors for component in vector))


if __name__ == "__main__":
    unittest.main(verbosity=2)
