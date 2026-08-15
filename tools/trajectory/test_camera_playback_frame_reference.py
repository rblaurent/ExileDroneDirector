from __future__ import annotations

import inspect
import math
import random
import unittest
from dataclasses import replace

from airframe_gimbal_prebake_reference import compile_airframe_gimbal_motion
from camera_channel_assembly_reference import (
    FilmbackSnapshotV1,
    compile_camera_channel_assembly_v1,
)
from camera_operator_override_reference import CameraOperatorPolicyV1, CameraOperatorStateV1
from camera_playback_frame_reference import (
    CameraPlaybackFrameError,
    evaluate_camera_playback_frame_v1,
)
from camera_viewer_comfort_reference import CameraViewerComfortSettingsV1
from carrier_frame_transport_reference import compile_carrier_frame_transport_v1
from cinematic_pose_reference import compile_cinematic_pose
from cinematic_reference import AuthoredSegment


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def axis_angle(axis, degrees):
    half = math.radians(degrees) * 0.5
    scale = math.sin(half)
    return tuple(component * scale for component in axis) + (math.cos(half),)


def multiply(left, right):
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def same_rotation(left, right, tolerance=1.0e-6):
    dot = abs(sum(a * b for a, b in zip(left, right)))
    return abs(1.0 - dot) <= tolerance


def fixture():
    cinematic_rotation = axis_angle((0.0, 0.0, 1.0), 90.0)
    pose = compile_cinematic_pose(
        ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0)),
        (cinematic_rotation, cinematic_rotation),
        (AuthoredSegment(1.0, "linear", "linear"),),
    )
    body = axis_angle((1.0, 0.0, 0.0), 20.0)
    gimbal = axis_angle((0.0, 1.0, 0.0), -30.0)
    airframe = compile_airframe_gimbal_motion(
        (body, body, body), (gimbal, gimbal, gimbal), (720.0, 720.0, 720.0), 1.0, 0.5
    )
    carrier = compile_carrier_frame_transport_v1(
        ((0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (100.0, 0.0, 0.0)), 1.0, 0.5
    )
    channels = compile_camera_channel_assembly_v1(
        1.0, FilmbackSnapshotV1("full_frame", 36.0, 24.0), ()
    )
    return pose, airframe, carrier, channels, cinematic_rotation, body, gimbal


def request(**overrides):
    pose, airframe, carrier, channels, _cinematic, _body, _gimbal = fixture()
    values = dict(
        cinematic_pose=pose,
        airframe_motion=airframe,
        carrier_frame=carrier,
        camera_channels=channels,
        elapsed_seconds=0.5,
        delta_seconds=1.0 / 60.0,
        requested_mode="directed",
        translation_input=(0.0, 0.0, 0.0),
        look_input=(0.0, 0.0, 0.0),
        recenter_requested=False,
        return_to_directed_requested=False,
        operator_policy=CameraOperatorPolicyV1(),
        previous_operator_state=CameraOperatorStateV1(initialized=True),
        procedural_translation_offset=(0.0, 0.0, 0.0),
        procedural_rotation_offset=IDENTITY,
        comfort_settings=CameraViewerComfortSettingsV1(),
    )
    values.update(overrides)
    return evaluate_camera_playback_frame_v1(**values)


class CameraPlaybackFrameReferenceTests(unittest.TestCase):
    def test_distinct_body_and_gimbal_survive_and_legacy_pose_rotation_is_ignored(self):
        _pose, _airframe, _carrier, _channels, cinematic, body, gimbal = fixture()
        frame = request()
        self.assertEqual(frame.position, (50.0, 0.0, 0.0))
        self.assertTrue(same_rotation(frame.body_world_rotation, body))
        self.assertTrue(same_rotation(frame.gimbal_world_rotation, gimbal))
        self.assertFalse(same_rotation(frame.body_world_rotation, cinematic))
        self.assertFalse(same_rotation(frame.gimbal_world_rotation, cinematic))
        self.assertFalse(same_rotation(frame.body_world_rotation, frame.gimbal_world_rotation))
        self.assertTrue(same_rotation(
            multiply(frame.body_world_rotation, frame.gimbal_relative_rotation),
            frame.gimbal_world_rotation,
        ))
        source = inspect.getsource(evaluate_camera_playback_frame_v1)
        self.assertNotIn("pose.rotation", source)
        self.assertNotIn("CameraTransform", source)

    def test_carrier_freecam_uses_independent_carrier_only_for_translation(self):
        frame = request(
            requested_mode="carrier_freecam",
            translation_input=(1.0, 0.0, 0.0),
            delta_seconds=0.1,
            operator_policy=CameraOperatorPolicyV1(
                translation_frame="carrier",
                maximum_translation_speed_cm_s=100.0,
                translation_acceleration_cm_s2=100.0,
            ),
        )
        self.assertGreater(frame.position[0], 50.0)
        self.assertEqual(frame.position[1:], (0.0, 0.0))
        self.assertEqual(frame.operator_mode, "carrier_freecam")
        self.assertTrue(frame.operator_override_active)

    def test_comfort_is_after_operator_and_channels(self):
        frame = request(
            procedural_translation_offset=(10.0, -6.0, 4.0),
            procedural_rotation_offset=axis_angle((1.0, 0.0, 0.0), 40.0),
            comfort_settings=CameraViewerComfortSettingsV1(
                enabled=True,
                roll_weight=0.0,
                shake_weight=0.0,
                blur_weight=0.0,
                exposure_change_weight=0.0,
                chromatic_aberration_weight=0.0,
            ),
        )
        self.assertEqual(frame.position, (50.0, 0.0, 0.0))
        self.assertEqual(frame.comfort_effective_weights, (0.0, 0.0, 0.0, 0.0, 0.0))
        self.assertEqual(frame.camera_channel_values[3], 0.0)
        self.assertEqual(frame.camera_channel_values[9], 0.0)
        self.assertTrue(frame.comfort_applied)

    def test_absolute_boundaries_have_one_completion_decision(self):
        for elapsed, complete in ((-2.0, False), (0.0, False), (0.25, False), (1.0, True), (2.0, True)):
            with self.subTest(elapsed=elapsed):
                frame = request(elapsed_seconds=elapsed)
                self.assertEqual(frame.complete, complete)
                self.assertEqual(frame.elapsed_seconds, elapsed)

    def test_timeline_source_operator_and_comfort_fail_closed(self):
        _pose, _airframe, carrier, channels, *_ = fixture()
        failures = (
            ("elapsed_seconds_invalid", dict(elapsed_seconds=math.nan)),
            ("timeline_mismatch", dict(camera_channels=replace(channels, duration_seconds=2.0))),
            ("source_invalid", dict(carrier_frame=replace(carrier, rotations=()))),
            ("operator_invalid", dict(delta_seconds=0.0)),
            ("comfort_invalid", dict(comfort_settings=CameraViewerComfortSettingsV1(enabled=True, roll_weight=2.0))),
        )
        for code, overrides in failures:
            with self.subTest(code=code), self.assertRaises(CameraPlaybackFrameError) as raised:
                request(**overrides)
            self.assertEqual(raised.exception.code, code)

    def test_seeded_forward_reverse_queries_are_deterministic(self):
        rng = random.Random(0xEDD9F)
        queries = [rng.uniform(-0.5, 1.5) for _ in range(40)]
        forward = [request(elapsed_seconds=value) for value in queries]
        reverse = [request(elapsed_seconds=value) for value in reversed(queries)]
        self.assertEqual(forward, list(reversed(reverse)))

    def test_compiled_sources_are_immutable(self):
        pose, airframe, carrier, channels, *_ = fixture()
        before = (pose, airframe, carrier, channels)
        request()
        self.assertEqual(before, (pose, airframe, carrier, channels))


if __name__ == "__main__":
    unittest.main(verbosity=2)
