from __future__ import annotations

import inspect
import math
import random
import unittest

from camera_base_look_reference import CHANNEL_IDS_V1, compose_camera_base_look_v1
from camera_viewer_comfort_reference import *
from orientation_reference import normalize


def axis_angle(axis, degrees):
    half = math.radians(degrees) * 0.5
    scale = math.sin(half)
    return normalize((axis[0] * scale, axis[1] * scale, axis[2] * scale, math.cos(half)))


def frame(settings=CameraViewerComfortSettingsV1(), **overrides):
    arguments = {
        "frame_valid": True,
        "position": (100.0, 200.0, 300.0),
        "gimbal_rotation": IDENTITY_QUATERNION,
        "procedural_translation_offset": (2.0, -4.0, 6.0),
        "procedural_rotation_offset": IDENTITY_QUATERNION,
        "camera_channel_values": compose_camera_base_look_v1("high_speed_fpv", (), ()).values,
        "settings": settings,
    }
    arguments.update(overrides)
    return apply_camera_viewer_comfort_v1(**arguments)


class CameraViewerComfortReferenceContracts(unittest.TestCase):
    def assert_quat_close(self, left, right, places=10):
        if sum(a * b for a, b in zip(left, right)) < 0.0:
            right = tuple(-value for value in right)
        for actual, expected in zip(left, right):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_disabled_is_exact_authored_behavior(self):
        source = compose_camera_base_look_v1("high_speed_fpv", (), ()).values
        result = frame(camera_channel_values=source)
        self.assertEqual(result.position, (102.0, 196.0, 306.0))
        self.assert_quat_close(result.gimbal_rotation, IDENTITY_QUATERNION)
        self.assertEqual(result.camera_channel_values, source)
        self.assertEqual(result.effective_weights, (1.0,) * 5)
        self.assertFalse(result.comfort_applied)

    def test_zero_weights_remove_owned_motion_and_effects(self):
        settings = CameraViewerComfortSettingsV1(True, 0.0, 0.0, 0.0, 0.0, 0.0)
        source = list(compose_camera_base_look_v1("high_speed_fpv", (), ()).values)
        source[CHANNEL_IDS_V1.index("focus_influence")] = 0.75
        source[CHANNEL_IDS_V1.index("exposure_ev")] = 4.0
        source[CHANNEL_IDS_V1.index("motion_blur_weight")] = 0.8
        source[CHANNEL_IDS_V1.index("chromatic_aberration_weight")] = 0.7
        result = frame(settings, gimbal_rotation=axis_angle((1.0, 0.0, 0.0), 40.0), camera_channel_values=source)
        self.assertEqual(result.position, (100.0, 200.0, 300.0))
        self.assert_quat_close(result.gimbal_rotation, IDENTITY_QUATERNION)
        for channel_id in ("focus_influence", "exposure_ev", "motion_blur_weight", "chromatic_aberration_weight"):
            self.assertEqual(result.camera_channel_values[CHANNEL_IDS_V1.index(channel_id)], 0.0)
        self.assertEqual(result.camera_channel_values[CHANNEL_IDS_V1.index("focal_length_mm")], source[0])
        self.assertTrue(result.comfort_applied)

    def test_continuous_weights_scale_only_owned_outputs(self):
        settings = CameraViewerComfortSettingsV1(True, 1.0, 0.25, 0.5, 0.25, 0.75)
        source = list(compose_camera_base_look_v1("vintage_lens", (), ()).values)
        source[CHANNEL_IDS_V1.index("focus_influence")] = 0.8
        result = frame(settings, camera_channel_values=source)
        self.assertEqual(result.position, (100.5, 199.0, 301.5))
        self.assertEqual(result.camera_channel_values[CHANNEL_IDS_V1.index("focus_influence")], 0.4)
        self.assertEqual(result.camera_channel_values[CHANNEL_IDS_V1.index("exposure_ev")], 0.025)
        self.assertAlmostEqual(result.camera_channel_values[CHANNEL_IDS_V1.index("chromatic_aberration_weight")], 0.225)
        untouched = set(CHANNEL_IDS_V1) - {"focus_influence", "motion_blur_weight", "exposure_ev", "chromatic_aberration_weight"}
        for channel_id in untouched:
            index = CHANNEL_IDS_V1.index(channel_id)
            self.assertEqual(result.camera_channel_values[index], source[index])

    def test_inputs_are_value_snapshots_and_never_mutated(self):
        position = [1.0, 2.0, 3.0]
        offset = [4.0, 5.0, 6.0]
        channels = list(compose_camera_base_look_v1("raw", (), ()).values)
        before = (tuple(position), tuple(offset), tuple(channels))
        result = frame(CameraViewerComfortSettingsV1(True, 0.5, 0.5, 0.5, 0.5, 0.5), position=position, procedural_translation_offset=offset, camera_channel_values=channels)
        self.assertEqual((tuple(position), tuple(offset), tuple(channels)), before)
        position[0] = offset[0] = channels[0] = -1.0
        self.assertEqual(result.position, (3.0, 4.5, 6.0))
        self.assertEqual(result.camera_channel_values[0], 35.0)

    def test_body_authorship_is_not_an_input_or_output(self):
        parameters = tuple(inspect.signature(apply_camera_viewer_comfort_v1).parameters)
        self.assertNotIn("body_rotation", parameters)
        self.assertEqual(tuple(CameraViewerComfortFrameV1.__dataclass_fields__),
                         ("position", "gimbal_rotation", "camera_channel_values", "effective_weights", "comfort_applied"))

    def test_vertical_forward_has_a_deterministic_finite_fallback(self):
        result = frame(CameraViewerComfortSettingsV1(True, 0.0, 1.0, 1.0, 1.0, 1.0),
                       gimbal_rotation=axis_angle((0.0, -1.0, 0.0), 90.0))
        self.assertTrue(all(math.isfinite(value) for value in result.gimbal_rotation))
        self.assertAlmostEqual(sum(value * value for value in result.gimbal_rotation), 1.0, places=10)

    def test_invalid_requests_fail_before_publication(self):
        valid = compose_camera_base_look_v1("raw", (), ()).values
        failures = (
            {"frame_valid": False},
            {"position": (0.0, 0.0)},
            {"procedural_translation_offset": (0.0, math.nan, 0.0)},
            {"gimbal_rotation": (0.0, 0.0, 0.0, 2.0)},
            {"procedural_rotation_offset": (0.0, 0.0, 0.0)},
            {"camera_channel_values": valid[:-1]},
            {"camera_channel_values": tuple(math.inf if index == 0 else value for index, value in enumerate(valid))},
            {"settings": CameraViewerComfortSettingsV1(True, -0.01, 1.0, 1.0, 1.0, 1.0)},
            {"settings": CameraViewerComfortSettingsV1(True, 1.0, 1.01, 1.0, 1.0, 1.0)},
            {"settings": CameraViewerComfortSettingsV1(True, 1.0, 1.0, math.nan, 1.0, 1.0)},
        )
        for overrides in failures:
            with self.subTest(overrides=overrides), self.assertRaises(CameraViewerComfortError):
                frame(**overrides)

    def test_disabled_policy_still_rejects_poisoned_preferences(self):
        with self.assertRaises(CameraViewerComfortError):
            frame(CameraViewerComfortSettingsV1(False, 2.0, 1.0, 1.0, 1.0, 1.0))

    def test_seeded_forward_reverse_execution_is_history_free(self):
        randomizer = random.Random(0xEDD10C0)
        cases = []
        for _ in range(80):
            settings = CameraViewerComfortSettingsV1(randomizer.choice((True, False)), *(randomizer.random() for _ in range(5)))
            cases.append({
                "settings": settings,
                "position": tuple(randomizer.uniform(-10000.0, 10000.0) for _ in range(3)),
                "procedural_translation_offset": tuple(randomizer.uniform(-20.0, 20.0) for _ in range(3)),
                "gimbal_rotation": axis_angle((1.0, 0.0, 0.0), randomizer.uniform(-80.0, 80.0)),
                "procedural_rotation_offset": axis_angle((0.0, 0.0, 1.0), randomizer.uniform(-10.0, 10.0)),
            })
        forward = tuple(frame(**case) for case in cases)
        reverse = tuple(reversed(tuple(frame(**case) for case in reversed(cases))))
        self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main(verbosity=2)
