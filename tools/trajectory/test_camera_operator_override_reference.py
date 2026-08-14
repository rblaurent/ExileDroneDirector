from __future__ import annotations

import inspect
import math
import random
import unittest

from camera_operator_override_reference import *
from orientation_reference import normalize


def axis_angle(axis, degrees):
    half = math.radians(degrees) * 0.5
    factor = math.sin(half)
    return normalize((axis[0] * factor, axis[1] * factor, axis[2] * factor, math.cos(half)))


def request(state=CameraOperatorStateV1(), **overrides):
    values = {
        "source_valid": True,
        "requested_mode": "directed",
        "authored_position": (100.0, 200.0, 300.0),
        "authored_body_rotation": axis_angle((1.0, 0.0, 0.0), 12.0),
        "authored_gimbal_rotation": axis_angle((0.0, 1.0, 0.0), -18.0),
        "carrier_frame_rotation": IDENTITY_QUATERNION,
        "translation_input": (0.0, 0.0, 0.0),
        "look_input": (0.0, 0.0, 0.0),
        "delta_seconds": 1.0 / 60.0,
        "recenter_requested": False,
        "return_to_directed_requested": False,
        "policy": CameraOperatorPolicyV1(),
        "previous_state": state,
    }
    values.update(overrides)
    return apply_camera_operator_override_v1(**values)


class CameraOperatorOverrideReferenceContracts(unittest.TestCase):
    def assert_quat_close(self, left, right, places=9):
        if sum(a * b for a, b in zip(left, right)) < 0.0:
            right = tuple(-component for component in right)
        for actual, expected in zip(left, right):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_first_step_is_exact_authored_pose_in_every_mode(self):
        for mode in MODES_V1:
            with self.subTest(mode=mode):
                result = request(requested_mode=mode, translation_input=(1.0, 0.0, 0.0), look_input=(0.0, 0.0, 1.0))
                self.assertEqual(result.position, (100.0, 200.0, 300.0))
                self.assertEqual(result.body_rotation, axis_angle((1.0, 0.0, 0.0), 12.0))
                self.assertEqual(result.gimbal_rotation, axis_angle((0.0, 1.0, 0.0), -18.0))
                self.assertEqual(result.state.mode, mode)
                self.assertEqual(result.state.translation_offset_cm, (0.0, 0.0, 0.0))
                self.assertEqual(result.state.look_offset, IDENTITY_QUATERNION)
                self.assertFalse(result.transition_active)

    def test_directed_settled_pose_preserves_distinct_body_and_gimbal_exactly(self):
        body = (0.0, 0.0, 0.0, 1.0)
        gimbal = axis_angle((0.0, 0.0, 1.0), 35.0)
        initialized = CameraOperatorStateV1(initialized=True)
        result = request(initialized, authored_body_rotation=body, authored_gimbal_rotation=gimbal)
        self.assertEqual(result.body_rotation, body)
        self.assertEqual(result.gimbal_rotation, gimbal)
        self.assertNotEqual(result.body_rotation, result.gimbal_rotation)
        self.assertFalse(result.override_active)
        self.assertFalse(result.transition_active)

    def test_free_look_changes_only_final_view_gimbal(self):
        result = request(requested_mode="free_look")
        for _ in range(20):
            result = request(result.state, requested_mode="free_look", look_input=(0.0, 0.0, 1.0))
        self.assertEqual(result.position, (100.0, 200.0, 300.0))
        self.assertEqual(result.body_rotation, axis_angle((1.0, 0.0, 0.0), 12.0))
        self.assertNotEqual(result.gimbal_rotation, axis_angle((0.0, 1.0, 0.0), -18.0))
        self.assertEqual(result.state.translation_offset_cm, (0.0, 0.0, 0.0))
        self.assertTrue(result.override_active)

    def test_world_and_carrier_translation_use_only_the_declared_frame(self):
        carrier = axis_angle((0.0, 0.0, 1.0), 90.0)
        world_policy = CameraOperatorPolicyV1(translation_frame="world")
        carrier_policy = CameraOperatorPolicyV1(translation_frame="carrier")
        world = request(requested_mode="carrier_freecam", carrier_frame_rotation=carrier, policy=world_policy)
        local = request(requested_mode="carrier_freecam", carrier_frame_rotation=carrier, policy=carrier_policy)
        for _ in range(10):
            world = request(world.state, requested_mode="carrier_freecam", carrier_frame_rotation=carrier,
                            authored_body_rotation=axis_angle((1.0, 0.0, 0.0), 70.0),
                            authored_gimbal_rotation=axis_angle((0.0, 1.0, 0.0), -65.0),
                            translation_input=(1.0, 0.0, 0.0), policy=world_policy)
            local = request(local.state, requested_mode="carrier_freecam", carrier_frame_rotation=carrier,
                            authored_body_rotation=axis_angle((1.0, 0.0, 0.0), 70.0),
                            authored_gimbal_rotation=axis_angle((0.0, 1.0, 0.0), -65.0),
                            translation_input=(1.0, 0.0, 0.0), policy=carrier_policy)
        self.assertGreater(world.state.translation_offset_cm[0], 0.0)
        self.assertAlmostEqual(world.state.translation_offset_cm[1], 0.0, places=8)
        self.assertGreater(local.state.translation_offset_cm[1], 0.0)
        self.assertAlmostEqual(local.state.translation_offset_cm[0], 0.0, places=8)

    def test_soft_tether_bounds_only_local_translation(self):
        policy = CameraOperatorPolicyV1(maximum_translation_speed_cm_s=1000.0,
                                        translation_acceleration_cm_s2=10000.0,
                                        tether_distance_cm=10.0)
        result = request(requested_mode="carrier_freecam", policy=policy)
        tether_seen = False
        for _ in range(20):
            result = request(result.state, requested_mode="carrier_freecam", translation_input=(1.0, 0.0, 0.0),
                             delta_seconds=0.1, policy=policy)
            tether_seen |= result.tether_applied
            self.assertLessEqual(math.dist(result.state.translation_offset_cm, (0.0, 0.0, 0.0)), 10.0 + 1e-9)
        self.assertTrue(tether_seen)
        self.assertEqual(result.body_rotation, axis_angle((1.0, 0.0, 0.0), 12.0))
        self.assertEqual(result.position[0], 110.0)

    def test_switch_from_carrier_to_free_look_decays_without_position_snap(self):
        policy = CameraOperatorPolicyV1(maximum_translation_speed_cm_s=300.0,
                                        translation_acceleration_cm_s2=600.0,
                                        recenter_translation_speed_cm_s=200.0)
        result = request(requested_mode="carrier_freecam", policy=policy)
        for _ in range(30):
            result = request(result.state, requested_mode="carrier_freecam", translation_input=(1.0, 0.0, 0.0),
                             delta_seconds=0.05, policy=policy)
        prior_offset = result.state.translation_offset_cm[0]
        first_free = request(result.state, requested_mode="free_look", delta_seconds=0.05, policy=policy)
        self.assertGreater(first_free.state.translation_offset_cm[0], 0.0)
        self.assertLessEqual(abs(first_free.state.translation_offset_cm[0] - prior_offset),
                             policy.maximum_translation_speed_cm_s * 0.05 + 1e-9)
        self.assertTrue(first_free.transition_active)
        result = first_free
        for _ in range(500):
            result = request(result.state, requested_mode="free_look", delta_seconds=0.05, policy=policy)
            if result.state.translation_offset_cm == (0.0, 0.0, 0.0):
                break
        self.assertEqual(result.state.translation_offset_cm, (0.0, 0.0, 0.0))
        self.assertEqual(result.position, (100.0, 200.0, 300.0))

    def test_return_to_directed_blends_then_settles_exactly(self):
        result = request(requested_mode="carrier_freecam")
        for _ in range(45):
            result = request(result.state, requested_mode="carrier_freecam",
                             translation_input=(0.4, -0.2, 0.1), look_input=(0.2, 0.6, -0.1))
        first = request(result.state, requested_mode="carrier_freecam", return_to_directed_requested=True)
        self.assertEqual(first.state.mode, "directed")
        self.assertTrue(first.transition_active)
        self.assertNotEqual(first.position, (100.0, 200.0, 300.0))
        result = first
        for _ in range(1000):
            result = request(result.state, requested_mode="directed")
            if not result.override_active:
                break
        self.assertFalse(result.override_active)
        self.assertFalse(result.transition_active)
        self.assertEqual(result.position, (100.0, 200.0, 300.0))
        self.assertEqual(result.gimbal_rotation, axis_angle((0.0, 1.0, 0.0), -18.0))
        self.assertEqual(result.body_rotation, axis_angle((1.0, 0.0, 0.0), 12.0))

    def test_velocity_and_acceleration_are_bounded(self):
        policy = CameraOperatorPolicyV1(maximum_translation_speed_cm_s=200.0,
                                        translation_acceleration_cm_s2=50.0,
                                        maximum_angular_speed_deg_s=90.0,
                                        angular_acceleration_deg_s2=30.0)
        result = request(requested_mode="carrier_freecam", policy=policy)
        prior_linear = result.state.translation_velocity_cm_s
        prior_angular = result.state.angular_velocity_deg_s
        for _ in range(100):
            result = request(result.state, requested_mode="carrier_freecam", translation_input=(1.0, 1.0, 1.0),
                             look_input=(1.0, -1.0, 1.0), delta_seconds=0.02, policy=policy)
            linear_delta = math.dist(prior_linear, result.state.translation_velocity_cm_s)
            angular_delta = math.dist(prior_angular, result.state.angular_velocity_deg_s)
            self.assertLessEqual(linear_delta, policy.translation_acceleration_cm_s2 * 0.02 + 1e-9)
            self.assertLessEqual(angular_delta, policy.angular_acceleration_deg_s2 * 0.02 + 1e-9)
            self.assertLessEqual(math.dist(result.state.translation_velocity_cm_s, (0.0, 0.0, 0.0)),
                                 policy.maximum_translation_speed_cm_s + 1e-9)
            self.assertLessEqual(math.dist(result.state.angular_velocity_deg_s, (0.0, 0.0, 0.0)),
                                 policy.maximum_angular_speed_deg_s + 1e-9)
            prior_linear = result.state.translation_velocity_cm_s
            prior_angular = result.state.angular_velocity_deg_s

    def test_recenter_does_not_change_mode_or_authoritative_inputs(self):
        result = request(requested_mode="free_look")
        for _ in range(20):
            result = request(result.state, requested_mode="free_look", look_input=(0.0, 1.0, 0.0))
        recentered = request(result.state, requested_mode="free_look", recenter_requested=True)
        self.assertEqual(recentered.state.mode, "free_look")
        self.assertEqual(recentered.body_rotation, axis_angle((1.0, 0.0, 0.0), 12.0))
        self.assertTrue(recentered.transition_active)
        self.assertTrue(recentered.state.recenter_active)
        result = recentered
        for _ in range(1000):
            result = request(result.state, requested_mode="free_look")
            if not result.state.recenter_active:
                break
        self.assertFalse(result.state.recenter_active)
        self.assertEqual(result.state.look_offset, IDENTITY_QUATERNION)
        resumed = request(result.state, requested_mode="free_look", look_input=(0.0,1.0,0.0))
        self.assertFalse(resumed.state.recenter_active)

    def test_seeded_sequence_is_deterministic_and_input_snapshots_are_immutable(self):
        rng = random.Random(0xEDD0F5E7)
        sequence = [
            (rng.choice(MODES_V1), tuple(rng.uniform(-1.0, 1.0) for _ in range(3)),
             tuple(rng.uniform(-1.0, 1.0) for _ in range(3)), rng.choice((False, False, True)))
            for _ in range(160)
        ]
        def execute():
            state = CameraOperatorStateV1()
            frames = []
            for mode, translation, look, recenter in sequence:
                frame = request(state, requested_mode=mode, translation_input=translation,
                                look_input=look, recenter_requested=recenter)
                state = frame.state
                frames.append(frame)
            return tuple(frames)
        self.assertEqual(execute(), execute())

    def test_invalid_requests_fail_before_publication(self):
        invalid = (
            {"source_valid": False},
            {"requested_mode": "orbit"},
            {"authored_position": (0.0, 1.0)},
            {"authored_body_rotation": (0.0, 0.0, 0.0, 2.0)},
            {"authored_gimbal_rotation": (0.0, math.nan, 0.0, 1.0)},
            {"carrier_frame_rotation": (0.0, 0.0, 0.0)},
            {"translation_input": (1.01, 0.0, 0.0)},
            {"look_input": (0.0, math.inf, 0.0)},
            {"delta_seconds": 0.0},
            {"delta_seconds": MAX_DELTA_SECONDS + 0.001},
            {"recenter_requested": 1},
            {"policy": CameraOperatorPolicyV1(translation_frame="body")},
            {"policy": CameraOperatorPolicyV1(tether_distance_cm=MAX_TETHER_CM + 1.0)},
            {"previous_state": CameraOperatorStateV1(mode="bad")},
            {"previous_state": CameraOperatorStateV1(translation_offset_cm=(1.0,0.0,0.0))},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(CameraOperatorOverrideError):
                request(**overrides)

    def test_no_playback_event_repository_or_camera_transform_alias_exists(self):
        parameters = tuple(inspect.signature(apply_camera_operator_override_v1).parameters)
        for forbidden in ("playback_time", "event_time", "camera_transform", "repository", "flypath"):
            self.assertNotIn(forbidden, parameters)
        self.assertEqual(tuple(CameraOperatorFrameV1.__dataclass_fields__), (
            "position", "body_rotation", "gimbal_rotation", "state",
            "override_active", "transition_active", "tether_applied",
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
