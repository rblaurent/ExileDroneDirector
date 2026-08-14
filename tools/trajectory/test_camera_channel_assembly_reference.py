"""Executable contracts for the channel-owned camera assembly."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from camera_channel_assembly_reference import (
    CHANNEL_IDS_V1,
    AuthoredCameraChannelV1,
    CameraChannelAssemblyError,
    FilmbackSnapshotV1,
    compile_camera_channel_assembly_v1,
    evaluate_camera_channel_assembly_v1,
)
from camera_scalar_track_reference import CameraScalarKey


FILMBACK = FilmbackSnapshotV1("full_frame_36x24", 36.0, 24.0)


def channel(channel_id, left, right, *, domain="linear", mode="linear", duration=2.0):
    return AuthoredCameraChannelV1(
        channel_id,
        (CameraScalarKey(0.0, left, mode), CameraScalarKey(duration, right)),
        domain,
    )


class CameraChannelAssemblyContracts(unittest.TestCase):
    def test_sparse_input_becomes_complete_canonical_owned_bank(self):
        authored = (channel("focal_length_mm", 35.0, 70.0),)
        result = compile_camera_channel_assembly_v1(2.0, FILMBACK, authored)
        self.assertEqual(tuple(item.channel_id for item in result.channels), CHANNEL_IDS_V1)
        self.assertEqual(len(result.channels), 13)
        frame = evaluate_camera_channel_assembly_v1(result, 1.0)
        self.assertEqual(frame.focal_length_mm, 52.5)
        self.assertEqual(frame.aperture_fstop, 2.8)
        self.assertEqual(frame.focus_influence, 1.0)
        self.assertEqual(frame.motion_blur_weight, 0.0)
        self.assertIsNot(result.channels[0].track.key_times, authored[0].keys)

    def test_focus_authorship_remains_distinct_and_optical(self):
        authored = (
            channel("focus_distance_cm", 100.0, 400.0, domain="reciprocal"),
            channel("focus_influence", 0.2, 0.8),
        )
        result = compile_camera_channel_assembly_v1(2.0, FILMBACK, authored)
        frame = evaluate_camera_channel_assembly_v1(result, 1.0)
        self.assertAlmostEqual(frame.focus_distance_cm, 160.0)
        self.assertAlmostEqual(frame.focus_influence, 0.5)
        self.assertNotEqual(frame.focus_distance_cm, frame.focus_influence)

    def test_every_effect_is_independent_and_bounded(self):
        effect_ids = CHANNEL_IDS_V1[5:]
        authored = tuple(
            channel(channel_id, index / 20.0, (index + 4) / 20.0)
            for index, channel_id in enumerate(effect_ids)
        )
        result = compile_camera_channel_assembly_v1(2.0, FILMBACK, authored)
        frame = evaluate_camera_channel_assembly_v1(result, 1.0)
        values = tuple(getattr(frame, channel_id) for channel_id in effect_ids)
        self.assertEqual(len(set(values)), len(effect_ids))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values))

    def test_zero_duration_defaults_are_real_constant_tracks(self):
        result = compile_camera_channel_assembly_v1(0.0, FILMBACK, ())
        self.assertTrue(all(len(channel.track.key_times) == 1 for channel in result.channels))
        for query in (-10.0, 0.0, 10.0):
            frame = evaluate_camera_channel_assembly_v1(result, query)
            self.assertEqual(frame.time_seconds, 0.0)
            self.assertTrue(frame.complete)

    def test_invalid_filmback_channels_domains_and_ranges_fail_closed(self):
        cases = (
            (-1.0, FILMBACK, ()),
            (2.0, replace(FILMBACK, preset_id=""), ()),
            (2.0, replace(FILMBACK, sensor_width_mm=0.0), ()),
            (2.0, FILMBACK, (channel("unknown", 0.0, 1.0),)),
            (2.0, FILMBACK, (channel("focal_length_mm", 35.0, 50.0), channel("focal_length_mm", 50.0, 70.0))),
            (2.0, FILMBACK, (channel("aperture_fstop", 1.0, 2.0, domain="reciprocal"),)),
            (2.0, FILMBACK, (channel("focus_distance_cm", 0.0, 100.0, domain="reciprocal"),)),
            (2.0, FILMBACK, (channel("bloom_weight", -0.1, 0.5),)),
            (2.0, FILMBACK, (channel("exposure_ev", -21.0, 0.0),)),
        )
        for duration, filmback, channels in cases:
            with self.subTest(duration=duration, channels=channels), self.assertRaises(CameraChannelAssemblyError):
                compile_camera_channel_assembly_v1(duration, filmback, channels)

    def test_failed_recompile_cannot_mutate_previous_snapshot(self):
        accepted = compile_camera_channel_assembly_v1(
            2.0, FILMBACK, (channel("focal_length_mm", 24.0, 85.0),)
        )
        before = evaluate_camera_channel_assembly_v1(accepted, 1.0)
        with self.assertRaises(CameraChannelAssemblyError):
            compile_camera_channel_assembly_v1(
                2.0, FILMBACK, (channel("focal_length_mm", 0.0, 85.0),)
            )
        self.assertEqual(evaluate_camera_channel_assembly_v1(accepted, 1.0), before)

    def test_seeded_forward_reverse_evaluation_is_history_free(self):
        rng = random.Random(0xEDD600)
        authored = (
            channel("focal_length_mm", 18.0, 120.0, mode="cinematic", duration=4.0),
            channel("aperture_fstop", 1.4, 11.0, mode="smooth", duration=4.0),
            channel("focus_distance_cm", 80.0, 5000.0, domain="reciprocal", duration=4.0),
            *(channel(channel_id, rng.random(), rng.random(), duration=4.0) for channel_id in CHANNEL_IDS_V1[5:]),
        )
        result = compile_camera_channel_assembly_v1(4.0, FILMBACK, authored)
        queries = tuple(index / 8.0 for index in range(41))
        forward = {query: evaluate_camera_channel_assembly_v1(result, query) for query in queries}
        reverse = {query: evaluate_camera_channel_assembly_v1(result, query) for query in reversed(queries)}
        self.assertEqual(forward, reverse)
        self.assertTrue(all(math.isfinite(sample.value) for frame in forward.values() for _, sample in frame.samples))


if __name__ == "__main__":
    unittest.main(verbosity=2)

