from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from camera_channel_assembly_reference import CHANNEL_IDS_V1, FilmbackSnapshotV1
from camera_engine_application_reference import (
    NEUTRAL_TARGET_VALUES_V1,
    TARGET_IDS_V1,
    CameraEngineCapabilitySnapshotV1,
    CameraEngineNativeStructSnapshotV1,
    CameraEngineStateSnapshotV1,
)
from camera_operator_override_reference import CameraOperatorStateV1
from camera_playback_frame_reference import CameraPlaybackFrameV1
from camera_playback_native_application_reference import (
    CameraNativeTransformStateV1,
    CameraPlaybackNativeApplicationError,
    apply_camera_playback_native_frame_v1,
    begin_camera_playback_native_application_v1,
    camera_engine_frame_from_playback_v1,
    plan_camera_playback_native_application_v1,
    restore_camera_playback_native_application_v1,
)


def axis_quat(axis: tuple[float, float, float], degrees: float):
    half = math.radians(degrees) * 0.5
    sine = math.sin(half)
    return axis[0] * sine, axis[1] * sine, axis[2] * sine, math.cos(half)


def multiply(left, right):
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


BODY = axis_quat((0.0, 0.0, 1.0), 45.0)
GIMBAL = axis_quat((0.0, 1.0, 0.0), 30.0)
RELATIVE = multiply((-BODY[0], -BODY[1], -BODY[2], BODY[3]), GIMBAL)


def capabilities(*unavailable: str):
    unavailable_set = set(unavailable)
    return CameraEngineCapabilitySnapshotV1(
        "5.6.1-enhanced",
        "enhanced-5.6.1-camera-v1",
        TARGET_IDS_V1,
        tuple(target_id not in unavailable_set for target_id in TARGET_IDS_V1),
    )


def engine_state(focal_length: float = 50.0):
    values = list(NEUTRAL_TARGET_VALUES_V1)
    values[TARGET_IDS_V1.index("focal_length_mm")] = focal_length
    return CameraEngineStateSnapshotV1(
        "viewer_baseline",
        tuple(values),
        CameraEngineNativeStructSnapshotV1(
            (("OpaqueFilmback", 7), ("SensorHeight", values[1]), ("SensorWidth", values[0])),
            (("ManualFocusDistance", values[4]), ("OpaqueFocus", "tracking")),
            (("AutoExposureBias", 0.0), ("OpaqueToneCurve", (0.25, 0.75))),
        ),
    )


def native_state(seed: float = 0.0):
    return CameraNativeTransformStateV1(
        (10.0 + seed, 20.0, 30.0),
        axis_quat((1.0, 0.0, 0.0), 5.0),
        (1.0, 1.25, 0.75),
        (2.0, 3.0, 4.0),
        axis_quat((0.0, 0.0, 1.0), -8.0),
        (0.9, 1.1, 1.0),
    )


def playback_frame(
    *,
    elapsed: float = 0.5,
    position=(100.0, 200.0, 300.0),
    body=BODY,
    gimbal=GIMBAL,
    relative=RELATIVE,
    channel_values=None,
):
    values = tuple(channel_values or NEUTRAL_TARGET_VALUES_V1[2:])
    return CameraPlaybackFrameV1(
        elapsed,
        elapsed >= 1.0,
        position,
        body,
        gimbal,
        relative,
        FilmbackSnapshotV1("playback_full_frame", 36.0, 24.0),
        values,
        CameraOperatorStateV1(True, "directed"),
        "directed",
        False,
        False,
        False,
        (1.0, 1.0, 1.0, 1.0, 1.0),
        False,
    )


class CameraPlaybackNativeApplicationContracts(unittest.TestCase):
    def test_distinct_body_and_relative_gimbal_map_to_different_native_owners(self):
        baseline_native = native_state()
        session = begin_camera_playback_native_application_v1(
            baseline_native, engine_state(), capabilities(), True
        )
        frame = playback_frame()
        applied = apply_camera_playback_native_frame_v1(session, frame, True, True)
        self.assertEqual(applied.current_native_state.actor_position, frame.position)
        self.assertEqual(applied.current_native_state.actor_world_rotation, BODY)
        self.assertEqual(applied.current_native_state.component_relative_rotation, RELATIVE)
        self.assertNotEqual(BODY, RELATIVE)
        self.assertEqual(
            applied.current_native_state.component_relative_position,
            baseline_native.component_relative_position,
        )
        self.assertEqual(applied.current_native_state.actor_scale, baseline_native.actor_scale)
        self.assertEqual(
            applied.current_native_state.component_relative_scale,
            baseline_native.component_relative_scale,
        )
        self.assertEqual(applied.engine_session.current.target_values, NEUTRAL_TARGET_VALUES_V1)

    def test_final_comfort_channels_are_value_copied_in_canonical_order(self):
        values = tuple(
            40.0 if channel_id == "focal_length_mm" else neutral
            for channel_id, neutral in zip(CHANNEL_IDS_V1, NEUTRAL_TARGET_VALUES_V1[2:])
        )
        frame = playback_frame(channel_values=values)
        engine_frame = camera_engine_frame_from_playback_v1(frame, True)
        self.assertEqual(tuple(getattr(engine_frame, name) for name in CHANNEL_IDS_V1), values)
        self.assertEqual(tuple(name for name, _sample in engine_frame.samples), CHANNEL_IDS_V1)
        self.assertTrue(all(sample.value == value for (_name, sample), value in zip(engine_frame.samples, values)))

    def test_complete_preflight_rejects_pose_corruption_without_mutation(self):
        session = begin_camera_playback_native_application_v1(
            native_state(), engine_state(), capabilities(), True
        )
        corrupt = replace(playback_frame(), gimbal_relative_rotation=(0.0, 0.0, 0.0, 1.0))
        before = session
        with self.assertRaises(CameraPlaybackNativeApplicationError) as caught:
            apply_camera_playback_native_frame_v1(session, corrupt, True, True)
        self.assertEqual(caught.exception.code, "playback_pose_reconstruction_failed")
        self.assertEqual(session, before)

    def test_invalid_authority_shape_and_nonfinite_values_fail_closed(self):
        valid = playback_frame()
        failures = (
            (valid, False, "playback_frame_invalid"),
            (replace(valid, camera_channel_values=valid.camera_channel_values[:-1]), True, "playback_channel_shape_invalid"),
            (replace(valid, position=(math.nan, 0.0, 0.0)), True, "playback_position_invalid"),
            (replace(valid, body_world_rotation=(0.0, 0.0, 0.0, 2.0)), True, "playback_body_invalid"),
        )
        for frame, authority, code in failures:
            with self.subTest(code=code), self.assertRaises(CameraPlaybackNativeApplicationError) as caught:
                camera_engine_frame_from_playback_v1(frame, authority)
            self.assertEqual(caught.exception.code, code)

    def test_unavailable_non_neutral_lens_target_rejects_before_pose_application(self):
        session = begin_camera_playback_native_application_v1(
            native_state(), engine_state(), capabilities("matte_weight"), True
        )
        values = list(NEUTRAL_TARGET_VALUES_V1[2:])
        values[CHANNEL_IDS_V1.index("matte_weight")] = 0.75
        before = session
        with self.assertRaises(CameraPlaybackNativeApplicationError) as caught:
            plan_camera_playback_native_application_v1(
                session, playback_frame(channel_values=values), True, True
            )
        self.assertEqual(caught.exception.code, "engine_preflight_failed")
        self.assertEqual(caught.exception.detail, "requested_target_unavailable")
        self.assertEqual(caught.exception.unavailable_target_ids, ("matte_weight",))
        self.assertEqual(session, before)

    def test_repeated_begin_preserves_both_baselines_and_manifest(self):
        first = begin_camera_playback_native_application_v1(
            native_state(), engine_state(47.0), capabilities(), True
        )
        applied = apply_camera_playback_native_frame_v1(first, playback_frame(), True, True)
        repeated = begin_camera_playback_native_application_v1(
            native_state(999.0), engine_state(999.0), capabilities(), True, applied
        )
        self.assertIs(repeated, applied)
        self.assertEqual(repeated.baseline_native_state, native_state())
        changed = replace(capabilities(), manifest_id="different")
        with self.assertRaises(CameraPlaybackNativeApplicationError) as caught:
            begin_camera_playback_native_application_v1(
                native_state(999.0), engine_state(999.0), changed, True, applied
            )
        self.assertEqual(caught.exception.code, "engine_capture_failed")
        self.assertEqual(caught.exception.detail, "capabilities_changed_during_session")

    def test_restore_is_exact_and_idempotent_for_pose_and_engine_state(self):
        baseline_native = native_state()
        baseline_engine = engine_state(58.0)
        session = begin_camera_playback_native_application_v1(
            baseline_native, baseline_engine, capabilities(), True
        )
        applied = apply_camera_playback_native_frame_v1(session, playback_frame(), True, True)
        restored = restore_camera_playback_native_application_v1(applied)
        self.assertFalse(restored.active)
        self.assertFalse(restored.engine_session.active)
        self.assertEqual(restored.current_native_state, baseline_native)
        self.assertEqual(restored.engine_session.current, baseline_engine)
        self.assertEqual(restored.applied_frame_count, 1)
        self.assertEqual(restore_camera_playback_native_application_v1(restored), restored)

    def test_seeded_forward_reverse_application_is_history_free(self):
        rng = random.Random(0xEDD820)
        frames = tuple(
            playback_frame(
                elapsed=index / 10.0,
                position=(rng.uniform(-500.0, 500.0), float(index), -float(index)),
            )
            for index in range(11)
        )
        expected = {
            frame.elapsed_seconds: (frame.position, frame.body_world_rotation, frame.gimbal_relative_rotation)
            for frame in frames
        }
        for order in (frames, tuple(reversed(frames))):
            session = begin_camera_playback_native_application_v1(
                native_state(), engine_state(), capabilities(), True
            )
            observed = {}
            for frame in order:
                session = apply_camera_playback_native_frame_v1(session, frame, True, True)
                state = session.current_native_state
                observed[frame.elapsed_seconds] = (
                    state.actor_position,
                    state.actor_world_rotation,
                    state.component_relative_rotation,
                )
            self.assertEqual(observed, expected)
            self.assertEqual(session.applied_frame_count, len(frames))


if __name__ == "__main__":
    unittest.main(verbosity=2)
