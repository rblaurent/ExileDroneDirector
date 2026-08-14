"""Executable contracts for camera-frame engine application and restoration."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from camera_channel_assembly_reference import (
    CHANNEL_IDS_V1,
    AuthoredCameraChannelV1,
    FilmbackSnapshotV1,
    compile_camera_channel_assembly_v1,
    evaluate_camera_channel_assembly_v1,
)
from camera_engine_application_reference import (
    NEUTRAL_TARGET_VALUES_V1,
    POST_PROCESS_OVERRIDE_TARGET_IDS_V1,
    REQUIRED_TARGET_IDS_V1,
    TARGET_COUNT_V1,
    TARGET_IDS_V1,
    CameraEngineApplicationError,
    CameraEngineCapabilitySnapshotV1,
    CameraEngineStateSnapshotV1,
    apply_camera_engine_frame_v1,
    begin_camera_engine_application_v1,
    camera_frame_target_values_v1,
    restore_camera_engine_state_v1,
)
from camera_scalar_track_reference import CameraScalarKey


def capabilities(*unavailable: str) -> CameraEngineCapabilitySnapshotV1:
    unavailable_set = set(unavailable)
    return CameraEngineCapabilitySnapshotV1(
        "5.6.1-enhanced",
        "enhanced-5.6.1-camera-v1",
        TARGET_IDS_V1,
        tuple(target_id not in unavailable_set for target_id in TARGET_IDS_V1),
    )


def state(*, value_delta: dict[str, float] | None = None, overrides: tuple[str, ...] = ()):
    values = list(NEUTRAL_TARGET_VALUES_V1)
    for target_id, value in (value_delta or {}).items():
        values[TARGET_IDS_V1.index(target_id)] = value
    override_set = set(overrides)
    return CameraEngineStateSnapshotV1(
        "viewer_baseline",
        tuple(values),
        tuple(target_id in override_set for target_id in TARGET_IDS_V1),
    )


def channel(channel_id: str, left: float, right: float, duration: float = 2.0):
    return AuthoredCameraChannelV1(
        channel_id,
        (CameraScalarKey(0.0, left, "linear"), CameraScalarKey(duration, right)),
    )


def frame(query: float = 1.0, authored=()):
    compiled = compile_camera_channel_assembly_v1(
        2.0,
        FilmbackSnapshotV1("authored_full_frame", 36.0, 24.0),
        authored,
    )
    return evaluate_camera_channel_assembly_v1(compiled, query)


class CameraEngineApplicationContracts(unittest.TestCase):
    def test_complete_supported_frame_applies_canonical_values_and_overrides(self):
        authored = tuple(
            channel(channel_id, index / 20.0, (index + 2) / 20.0)
            for index, channel_id in enumerate(CHANNEL_IDS_V1[5:])
        )
        wanted = frame(authored=authored)
        baseline = state(value_delta={"focal_length_mm": 50.0})
        session = begin_camera_engine_application_v1(baseline, capabilities())
        applied = apply_camera_engine_frame_v1(session, wanted)
        self.assertEqual(applied.current.target_values, camera_frame_target_values_v1(wanted))
        self.assertEqual(applied.current.filmback_preset_id, "authored_full_frame")
        self.assertEqual(applied.applied_frame_count, 1)
        for target_id in POST_PROCESS_OVERRIDE_TARGET_IDS_V1:
            self.assertTrue(applied.current.override_enabled[TARGET_IDS_V1.index(target_id)])
        self.assertEqual(session.current, baseline)
        self.assertEqual(session.baseline, baseline)

    def test_unavailable_optional_target_is_safe_only_when_already_neutral(self):
        manifest = capabilities("matte_weight", "sharpening_weight")
        session = begin_camera_engine_application_v1(state(), manifest)
        applied = apply_camera_engine_frame_v1(session, frame())
        self.assertEqual(applied.last_unavailable_target_ids, ("sharpening_weight", "matte_weight"))
        for target_id in applied.last_unavailable_target_ids:
            index = TARGET_IDS_V1.index(target_id)
            self.assertEqual(applied.current.target_values[index], NEUTRAL_TARGET_VALUES_V1[index])
            self.assertFalse(applied.current.override_enabled[index])

        active_frame = frame(authored=(channel("matte_weight", 0.2, 0.8),))
        before = applied
        with self.assertRaises(CameraEngineApplicationError) as caught:
            apply_camera_engine_frame_v1(applied, active_frame)
        self.assertEqual(caught.exception.code, "requested_target_unavailable")
        self.assertEqual(caught.exception.unavailable_target_ids, ("matte_weight",))
        self.assertEqual(applied, before)

        contaminated = begin_camera_engine_application_v1(
            state(value_delta={"sharpening_weight": 0.3}), manifest
        )
        with self.assertRaises(CameraEngineApplicationError):
            apply_camera_engine_frame_v1(contaminated, frame())

    def test_required_capability_failure_prevents_session_capture(self):
        for target_id in REQUIRED_TARGET_IDS_V1:
            with self.subTest(target_id=target_id), self.assertRaises(CameraEngineApplicationError) as caught:
                begin_camera_engine_application_v1(state(), capabilities(target_id))
            self.assertEqual(caught.exception.code, "required_target_unavailable")
            self.assertEqual(caught.exception.unavailable_target_ids, (target_id,))

    def test_repeated_begin_preserves_original_baseline_and_freezes_manifest(self):
        original = state(value_delta={"focal_length_mm": 47.0})
        session = begin_camera_engine_application_v1(original, capabilities())
        applied = apply_camera_engine_frame_v1(
            session,
            frame(authored=(channel("focal_length_mm", 20.0, 80.0),)),
        )
        replacement = state(value_delta={"focal_length_mm": 999.0})
        repeated = begin_camera_engine_application_v1(replacement, capabilities(), applied)
        self.assertIs(repeated, applied)
        self.assertEqual(repeated.baseline, original)
        changed = replace(capabilities(), manifest_id="different")
        with self.assertRaises(CameraEngineApplicationError) as caught:
            begin_camera_engine_application_v1(replacement, changed, applied)
        self.assertEqual(caught.exception.code, "capabilities_changed_during_session")

    def test_invalid_manifests_states_and_frames_fail_before_mutation(self):
        bad_manifests = (
            replace(capabilities(), engine_version=""),
            replace(capabilities(), manifest_id=""),
            replace(capabilities(), target_ids=tuple(reversed(TARGET_IDS_V1))),
            replace(capabilities(), available=(True,) * (TARGET_COUNT_V1 - 1)),
        )
        for manifest in bad_manifests:
            with self.subTest(manifest=manifest), self.assertRaises(CameraEngineApplicationError):
                begin_camera_engine_application_v1(state(), manifest)

        with self.assertRaises(CameraEngineApplicationError):
            begin_camera_engine_application_v1(
                replace(state(), target_values=(math.nan,) + state().target_values[1:]),
                capabilities(),
            )

        session = begin_camera_engine_application_v1(state(), capabilities())
        valid_frame = frame()
        poisoned_sample = replace(valid_frame.samples[0][1], value=999.0)
        poisoned_frame = replace(
            valid_frame,
            samples=((valid_frame.samples[0][0], poisoned_sample), *valid_frame.samples[1:]),
        )
        before = session
        with self.assertRaises(CameraEngineApplicationError) as caught:
            apply_camera_engine_frame_v1(session, poisoned_frame)
        self.assertEqual(caught.exception.code, "frame_sample_value_mismatch")
        self.assertEqual(session, before)

    def test_restore_is_exact_and_idempotent_including_override_flags(self):
        baseline = state(
            value_delta={"exposure_ev": -1.25, "bloom_weight": 0.4},
            overrides=("exposure_ev", "bloom_weight"),
        )
        session = begin_camera_engine_application_v1(baseline, capabilities())
        applied = apply_camera_engine_frame_v1(
            session,
            frame(authored=(channel("exposure_ev", 1.0, 3.0), channel("bloom_weight", 0.0, 1.0))),
        )
        restored = restore_camera_engine_state_v1(applied)
        self.assertFalse(restored.active)
        self.assertEqual(restored.current, baseline)
        self.assertEqual(restored.baseline, baseline)
        self.assertEqual(restored.applied_frame_count, 1)
        self.assertEqual(restore_camera_engine_state_v1(restored), restored)

    def test_seeded_forward_reverse_application_is_history_free(self):
        rng = random.Random(0xEDD710)
        authored = tuple(
            channel(channel_id, rng.random() * 0.4, 0.6 + rng.random() * 0.4, 2.0)
            for channel_id in CHANNEL_IDS_V1[5:]
        )
        compiled = compile_camera_channel_assembly_v1(
            2.0,
            FilmbackSnapshotV1("seeded", 32.0, 18.0),
            authored,
        )
        queries = tuple(index / 10.0 for index in range(21))
        expected = {
            query: camera_frame_target_values_v1(evaluate_camera_channel_assembly_v1(compiled, query))
            for query in queries
        }
        for order in (queries, tuple(reversed(queries))):
            session = begin_camera_engine_application_v1(state(), capabilities())
            observed = {}
            for query in order:
                session = apply_camera_engine_frame_v1(
                    session,
                    evaluate_camera_channel_assembly_v1(compiled, query),
                )
                observed[query] = session.current.target_values
            self.assertEqual(observed, expected)
            self.assertEqual(restore_camera_engine_state_v1(session).current, state())


if __name__ == "__main__":
    unittest.main(verbosity=2)
