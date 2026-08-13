"""Executable contracts for the explicit v2 document-to-source boundary."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from compiled_document_source_adapter_reference import (
    CompiledDocumentSegmentV2,
    CompiledDocumentSourceAdapterError,
    CompiledDocumentWaypointV2,
    CompiledTrajectoryDocumentV2,
    DiscontinuityThresholdsV2,
    compile_document_to_airframe_sources_v2,
)
from orientation_reference import normalize


def yaw(degrees: float):
    half = math.radians(degrees) * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


def pitch(degrees: float):
    half = math.radians(degrees) * 0.5
    return (0.0, math.sin(half), 0.0, math.cos(half))


def document(*, curves=("auto_cinematic", "auto_cinematic")):
    waypoints = (
        CompiledDocumentWaypointV2(4, (0.0, 0.0, 0.0), yaw(-12.0), pitch(7.0)),
        CompiledDocumentWaypointV2(9, (80.0, 0.0, 0.0), yaw(4.0), pitch(-3.0)),
        CompiledDocumentWaypointV2(20, (200.0, 0.0, 0.0), yaw(21.0), pitch(-14.0)),
    )
    segments = (
        CompiledDocumentSegmentV2(31, 4, 9, 0.8, curves[0], "linear", "cinematic_drone"),
        CompiledDocumentSegmentV2(32, 9, 20, 1.2, curves[1], "linear", "cinematic_drone"),
    )
    return CompiledTrajectoryDocumentV2(waypoints, segments, 2.0)


class CompiledDocumentSourceAdapterContracts(unittest.TestCase):
    def test_distinct_authorship_reaches_source_and_desired_without_aliasing(self):
        source = document()
        result = compile_document_to_airframe_sources_v2(source, 0.25)
        self.assertEqual(result.body_rotations, tuple(normalize(item.body_rotation) for item in source.waypoints))
        self.assertEqual(result.gimbal_rotations, tuple(normalize(item.gimbal_rotation) for item in source.waypoints))
        self.assertNotEqual(result.body_rotations, result.gimbal_rotations)
        self.assertNotEqual(result.sampled_sources.authored_body_rotations, result.sampled_sources.authored_gimbal_rotations)
        self.assertEqual(result.sampled_sources.sample_times[-1], 2.0)

    def test_v1_or_missing_orientation_channels_have_no_fallback(self):
        source = document()
        with self.assertRaisesRegex(CompiledDocumentSourceAdapterError, "schema version must be 2"):
            compile_document_to_airframe_sources_v2(replace(source, schema_version=1), 0.25)
        broken = replace(source.waypoints[1], body_rotation=())
        with self.assertRaisesRegex(CompiledDocumentSourceAdapterError, "four finite"):
            compile_document_to_airframe_sources_v2(replace(source, waypoints=(source.waypoints[0], broken, source.waypoints[2])), 0.25)
        broken = replace(source.waypoints[1], gimbal_rotation=(0.0, 0.0, 0.0, 0.0))
        with self.assertRaisesRegex(CompiledDocumentSourceAdapterError, "magnitude"):
            compile_document_to_airframe_sources_v2(replace(source, waypoints=(source.waypoints[0], broken, source.waypoints[2])), 0.25)

    def test_shape_ids_adjacency_duration_and_profile_are_fail_closed(self):
        source = document()
        cases = (
            replace(source, waypoints=source.waypoints[:1], segments=()),
            replace(source, segments=source.segments[:1]),
            replace(source, waypoints=(source.waypoints[0], replace(source.waypoints[1], waypoint_id=4), source.waypoints[2])),
            replace(source, segments=(replace(source.segments[0], to_waypoint_id=20), source.segments[1])),
            replace(source, segments=(replace(source.segments[0], duration_seconds=0.0), source.segments[1])),
            replace(source, duration_seconds=2.5),
            replace(source, default_flight_profile="not-a-profile"),
            replace(source, segments=(replace(source.segments[0], flight_profile_override="not-a-profile"), source.segments[1])),
        )
        for case in cases:
            with self.subTest(case=case), self.assertRaises(CompiledDocumentSourceAdapterError):
                compile_document_to_airframe_sources_v2(case, 0.25)

    def test_output_is_a_value_snapshot_and_input_order_is_irrelevant(self):
        source = document()
        first = compile_document_to_airframe_sources_v2(source, 0.2)
        second = compile_document_to_airframe_sources_v2(source, 0.2)
        self.assertEqual(first, second)
        mutable = [list(item.position) for item in source.waypoints]
        mutable[0][0] = 999.0
        self.assertEqual(first.positions[0], (0.0, 0.0, 0.0))

    def test_diagnostics_follow_adapter_and_do_not_change_motion(self):
        smooth = compile_document_to_airframe_sources_v2(document(), 0.25)
        sharp = compile_document_to_airframe_sources_v2(document(curves=("linear", "linear")), 0.25)
        self.assertEqual(len(smooth.diagnostics.joins), 1)
        self.assertEqual(len(sharp.diagnostics.joins), 1)
        self.assertEqual(sharp.diagnostics.joins[0].waypoint_id, 9)
        self.assertGreater(sharp.diagnostics.joins[0].authored_body_rate_jump_degrees_per_second, 0.0)
        self.assertGreaterEqual(sharp.diagnostics.discontinuity_count, 1)
        loose = compile_document_to_airframe_sources_v2(
            document(curves=("linear", "linear")),
            0.25,
            DiscontinuityThresholdsV2(1.0e9, 1.0e9, 1.0e9, 1.0, 1.0),
        )
        self.assertEqual(loose.diagnostics.discontinuity_count, 0)
        self.assertEqual(sharp.sampled_sources, loose.sampled_sources)

    def test_invalid_diagnostic_threshold_fails_without_mutating_document(self):
        source = document()
        before = repr(source)
        with self.assertRaisesRegex(CompiledDocumentSourceAdapterError, "cannot be negative"):
            compile_document_to_airframe_sources_v2(source, 0.25, DiscontinuityThresholdsV2(-1.0))
        self.assertEqual(repr(source), before)

    def test_seeded_forward_reverse_compilation_is_deterministic(self):
        cases = []
        for index in range(20):
            rng = random.Random(0xEDD400 + index)
            middle = (80.0, 0.0, 0.0)
            end = (200.0, 0.0, 0.0)
            mode = rng.choice(("linear", "auto_cinematic"))
            base = document(curves=(mode, mode))
            points = (
                replace(base.waypoints[0], body_rotation=yaw(rng.uniform(-25.0, 25.0)), gimbal_rotation=pitch(rng.uniform(-20.0, 20.0))),
                replace(base.waypoints[1], position=middle, body_rotation=yaw(rng.uniform(-25.0, 25.0)), gimbal_rotation=pitch(rng.uniform(-20.0, 20.0))),
                replace(base.waypoints[2], position=end, body_rotation=yaw(rng.uniform(-25.0, 25.0)), gimbal_rotation=pitch(rng.uniform(-20.0, 20.0))),
            )
            cases.append(replace(base, waypoints=points))
        forward = [compile_document_to_airframe_sources_v2(case, 0.2) for case in cases]
        reverse = [compile_document_to_airframe_sources_v2(case, 0.2) for case in reversed(cases)]
        self.assertEqual(forward, list(reversed(reverse)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
