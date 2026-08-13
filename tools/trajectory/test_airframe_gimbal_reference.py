from __future__ import annotations

import math
import random
import unittest

from airframe_gimbal_reference import (
    AirframeGimbalError,
    AirframeGimbalProfile,
    solve_airframe_gimbal,
)
from flight_profile_reference import PROFILES


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def profile(name: str) -> AirframeGimbalProfile:
    source = PROFILES[name]
    return AirframeGimbalProfile(**{
        field: getattr(source, field)
        for field in AirframeGimbalProfile.__dataclass_fields__
    })


def unit_quaternion(value) -> bool:
    return math.isclose(sum(component * component for component in value), 1.0, abs_tol=1.0e-10)


def same_rotation(left, right, tolerance=1.0e-9) -> bool:
    return abs(sum(a * b for a, b in zip(left, right))) >= 1.0 - tolerance


def rotate(quaternion, vector):
    x, y, z, w = quaternion
    vx, vy, vz = vector
    # Unit-quaternion vector rotation, expanded to avoid sharing solver helpers.
    tx, ty, tz = 2.0 * (y * vz - z * vy), 2.0 * (z * vx - x * vz), 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


class AirframeGimbalContracts(unittest.TestCase):
    def solve(self, selected="hybrid", **overrides):
        arguments = dict(
            current_velocity=(1000.0, 0.0, 0.0),
            look_ahead_velocity=(900.0, 300.0, 0.0),
            acceleration=(0.0, 300.0, 0.0),
            jerk=(0.0, 0.0, 0.0),
            authored_body_rotation=IDENTITY,
            authored_gimbal_rotation=IDENTITY,
            profile=profile(selected),
        )
        arguments.update(overrides)
        return solve_airframe_gimbal(**arguments)

    def test_body_lock_and_full_stabilization_endpoints_are_exact(self):
        base = profile("hybrid")
        body_authored = AirframeGimbalProfile(**{**base.__dict__, "path_follow_weight": 0.0, "horizon_stabilization_weight": 0.0, "camera_uptilt_degrees": 0.0})
        body_locked = self.solve(profile=body_authored, acceleration=(0.0, 0.0, 0.0), look_ahead_velocity=(1000.0, 0.0, 0.0))
        self.assertTrue(same_rotation(body_locked.body_rotation, IDENTITY))
        self.assertTrue(same_rotation(body_locked.gimbal_rotation, IDENTITY))
        stabilized_profile = AirframeGimbalProfile(**{**body_authored.__dict__, "horizon_stabilization_weight": 1.0})
        quarter_turn = (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
        stabilized = self.solve(profile=stabilized_profile, authored_gimbal_rotation=quarter_turn, acceleration=(0.0, 0.0, 0.0), look_ahead_velocity=(1000.0, 0.0, 0.0))
        self.assertTrue(same_rotation(stabilized.gimbal_rotation, quarter_turn))

    def test_identical_motion_has_distinct_cinematic_hybrid_and_fpv_character(self):
        cinematic = self.solve("cinematic_drone")
        hybrid = self.solve("hybrid")
        fpv = self.solve("fpv_freestyle")
        self.assertLess(abs(cinematic.bank_degrees), abs(hybrid.bank_degrees))
        self.assertLess(abs(hybrid.bank_degrees), abs(fpv.bank_degrees))
        self.assertFalse(same_rotation(cinematic.body_rotation, hybrid.body_rotation, 1.0e-5))
        self.assertFalse(same_rotation(hybrid.gimbal_rotation, fpv.gimbal_rotation, 1.0e-5))

    def test_path_forward_uses_look_ahead_then_current_then_authored_fallback(self):
        anticipated = self.solve(look_ahead_velocity=(0.0, 1000.0, 0.0), acceleration=(0.0, 0.0, 0.0))
        current = self.solve(look_ahead_velocity=(0.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
        authored = self.solve(current_velocity=(0.0, 0.0, 0.0), look_ahead_velocity=(0.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
        for actual, expected in (
            (rotate(anticipated.path_rotation, (1.0, 0.0, 0.0)), (0.0, 1.0, 0.0)),
            (rotate(current.path_rotation, (1.0, 0.0, 0.0)), (1.0, 0.0, 0.0)),
            (rotate(authored.path_rotation, (1.0, 0.0, 0.0)), (1.0, 0.0, 0.0)),
        ):
            self.assertTrue(all(math.isclose(a, b, abs_tol=1.0e-9) for a, b in zip(actual, expected)))

    def test_bank_is_signed_and_clamped(self):
        base = profile("fpv_freestyle")
        permissive = AirframeGimbalProfile(**{**base.__dict__, "minimum_turn_radius_cm": 1.0})
        right = self.solve(profile=permissive, acceleration=(0.0, 3500.0, 0.0))
        left = self.solve(profile=permissive, acceleration=(0.0, -3500.0, 0.0))
        self.assertEqual(right.bank_degrees, -base.max_bank_degrees)
        self.assertEqual(left.bank_degrees, base.max_bank_degrees)

    def test_positive_uptilt_raises_body_locked_camera_forward(self):
        base = profile("fpv_freestyle")
        locked = AirframeGimbalProfile(**{**base.__dict__, "path_follow_weight": 0.0, "horizon_stabilization_weight": 0.0})
        result = self.solve(profile=locked, acceleration=(0.0, 0.0, 0.0), look_ahead_velocity=(1000.0, 0.0, 0.0))
        x, y, z, w = result.gimbal_rotation
        forward_z = 2.0 * (x * z - w * y)
        self.assertGreater(forward_z, 0.0)

    def test_stationary_vertical_and_straight_paths_publish_finite_diagnostics(self):
        stationary = self.solve(current_velocity=(0.0, 0.0, 0.0), look_ahead_velocity=(0.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
        vertical = self.solve(current_velocity=(0.0, 0.0, 100.0), look_ahead_velocity=(0.0, 0.0, 100.0), acceleration=(0.0, 0.0, 0.0))
        straight = self.solve(current_velocity=(1000.0, 0.0, 0.0), look_ahead_velocity=(1000.0, 0.0, 0.0), acceleration=(10.0, 0.0, 0.0))
        for result in (stationary, vertical, straight):
            self.assertTrue(unit_quaternion(result.body_rotation))
            self.assertTrue(unit_quaternion(result.gimbal_rotation))
            self.assertTrue(unit_quaternion(result.path_rotation))
            self.assertTrue(all(math.isfinite(value) for value in (
                result.speed_cm_per_second,
                result.lateral_acceleration_cm_per_second_squared,
                result.turn_radius_cm,
                result.bank_degrees,
            )))
            self.assertEqual(result.turn_radius_cm, 0.0)

    def test_profile_physical_limits_reject_before_pose_publication(self):
        accepted = self.solve(
            acceleration=(0.0, 900.0, 0.0),
            jerk=(1800.0, 0.0, 0.0),
            current_velocity=(math.sqrt(250.0 * 900.0), 0.0, 0.0),
            selected="hybrid",
        )
        self.assertTrue(math.isclose(accepted.turn_radius_cm, 250.0, abs_tol=1.0e-9))
        with self.assertRaises(AirframeGimbalError):
            self.solve(acceleration=(0.0, 901.0, 0.0), selected="hybrid")
        with self.assertRaises(AirframeGimbalError):
            self.solve(jerk=(1801.0, 0.0, 0.0), selected="hybrid", acceleration=(0.0, 0.0, 0.0))
        with self.assertRaises(AirframeGimbalError):
            self.solve(current_velocity=(100.0, 0.0, 0.0), acceleration=(0.0, 100.0, 0.0), selected="hybrid")

    def test_invalid_vectors_quaternions_and_profiles_fail_closed(self):
        invalid_cases = (
            {"current_velocity": (math.nan, 0.0, 0.0)},
            {"current_velocity": (True, 0.0, 0.0)},
            {"look_ahead_velocity": (math.inf, 0.0, 0.0)},
            {"jerk": (False, 0.0, 0.0)},
            {"authored_body_rotation": (0.0, 0.0, 0.0, 2.0)},
            {"authored_body_rotation": (False, 0.0, 0.0, 1.0)},
            {"authored_gimbal_rotation": (0.0, 0.0, 0.0, 0.0)},
            {"profile": AirframeGimbalProfile(**{**profile("hybrid").__dict__, "bank_gain": math.nan})},
            {"profile": AirframeGimbalProfile(**{**profile("hybrid").__dict__, "bank_gain": True})},
            {"profile": AirframeGimbalProfile(**{**profile("hybrid").__dict__, "horizon_stabilization_weight": 1.01})},
            {"profile": object()},
        )
        for case in invalid_cases:
            with self.subTest(case=case), self.assertRaises(AirframeGimbalError):
                self.solve(**case)

    def test_overflow_capable_motion_fails_instead_of_publishing_nonfinite_diagnostics(self):
        with self.assertRaises(AirframeGimbalError):
            self.solve(current_velocity=(1.0e308, 1.0e308, 0.0), acceleration=(-1.0, 1.0, 0.0))

    def test_quaternion_signs_do_not_change_the_physical_result(self):
        positive = self.solve()
        negative = self.solve(authored_body_rotation=tuple(-value for value in IDENTITY), authored_gimbal_rotation=tuple(-value for value in IDENTITY))
        self.assertTrue(same_rotation(positive.body_rotation, negative.body_rotation))
        self.assertTrue(same_rotation(positive.gimbal_rotation, negative.gimbal_rotation))

    def test_seeded_samples_are_deterministic_normalized_and_history_free(self):
        rng = random.Random(0xEDD_A1)
        cases = []
        for _ in range(1000):
            speed = rng.uniform(0.0, 2500.0)
            lateral = rng.uniform(-200.0, 200.0)
            selected = rng.choice(tuple(PROFILES))
            minimum_radius = PROFILES[selected].minimum_turn_radius_cm
            if abs(lateral) > 1.0e-9 and speed * speed / abs(lateral) < minimum_radius:
                lateral = 0.0
            cases.append((selected, (speed, 0.0, 0.0), (speed, rng.uniform(-500.0, 500.0), rng.uniform(-200.0, 200.0)), (0.0, lateral, 0.0)))
        forward = [self.solve(name, current_velocity=current, look_ahead_velocity=look, acceleration=accel) for name, current, look, accel in cases]
        reverse = [self.solve(name, current_velocity=current, look_ahead_velocity=look, acceleration=accel) for name, current, look, accel in reversed(cases)]
        self.assertEqual(forward, list(reversed(reverse)))
        for result in forward:
            self.assertTrue(unit_quaternion(result.body_rotation))
            self.assertTrue(unit_quaternion(result.gimbal_rotation))
            self.assertTrue(-85.0 <= result.bank_degrees <= 85.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
