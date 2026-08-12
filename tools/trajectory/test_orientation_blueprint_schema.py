"""Freeze the staged Blueprint seam for multi-key orientation compilation."""

from __future__ import annotations

import json
import math
import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/orientation_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
from orientation_reference import compile_orientation_track, evaluate_orientation, logarithmic_delta, normalize  # noqa: E402


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def axis_angle(axis, degrees):
    magnitude = math.sqrt(sum(value * value for value in axis))
    half = math.radians(degrees) * 0.5
    scale = math.sin(half) / magnitude
    return normalize((axis[0] * scale, axis[1] * scale, axis[2] * scale, math.cos(half)))


class OrientationBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_and_limits_are_explicit(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"]["minimumWaypoints"], 2)
        self.assertEqual(SCHEMA["limits"]["maximumWaypoints"], 512)
        self.assertEqual(SCHEMA["limits"]["minimumQuaternionNorm"], 1e-12)
        self.assertGreater(SCHEMA["limits"]["finiteScalarBound"], 1e300)

    def test_variable_names_are_unique_and_use_supported_blueprint_types(self):
        variables = SCHEMA["variables"]
        names = [value["name"] for value in variables]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(value["type"] in {"Quat", "Vector", "Float", "Integer", "Boolean"} for value in variables))
        self.assertTrue(all(value["container"] in {"None", "Array"} for value in variables))

    def test_candidate_and_compiled_channels_are_not_aliased(self):
        variables = SCHEMA["variables"]
        candidates = {value["name"] for value in variables if value["role"] == "candidate"}
        results = {value["name"] for value in variables if value["role"] == "result"}
        self.assertTrue(candidates)
        self.assertTrue(results)
        self.assertTrue(candidates.isdisjoint(results))
        self.assertEqual(len([name for name in candidates if name.endswith("QuatsV1") or "Controls" in name]), 3)

    def test_stage_order_and_primitive_dependencies_are_exact(self):
        functions = SCHEMA["functions"]
        self.assertEqual([value["stage"] for value in functions], list(range(9)))
        by_name = {value["name"]: value for value in functions}
        self.assertEqual(by_name["ComputeOrientationForwardDeltasV1"]["uses"], ["ComputeOrientationLogDeltaV1"])
        self.assertEqual(by_name["ComputeOrientationTrackTangentRatesV1"]["uses"], ["ComputeOrientationTangentRateV1"])
        self.assertEqual(by_name["BuildOrientationTrackSegmentsV1"]["uses"], ["BuildOrientationSegmentControlsV1"])
        self.assertEqual(by_name["EvaluateCompiledOrientationTrackV1"]["uses"], ["EvaluateSphericalBezierQuaternionV1"])

    def test_contracts_require_atomic_absolute_time_behavior(self):
        contracts = " ".join(SCHEMA["contracts"].values()).lower()
        for required in ("only commitcompiledorientationtrackv1", "clears every", "absolute elapsed", "never integrates"):
            self.assertIn(required, contracts)

    def test_staged_channel_cardinality_and_time_match_the_frozen_oracle(self):
        rng = random.Random(0xEDD060)
        for _case in range(100):
            rotations = [IDENTITY]
            durations = []
            for _ in range(rng.randint(1, 15)):
                rotations.append(axis_angle(tuple(rng.uniform(-1.0, 1.0) for _ in range(3)), rng.uniform(-179.0, 179.0)))
                durations.append(10 ** rng.uniform(-2.0, 1.5))
            track = compile_orientation_track(tuple(rotations), tuple(durations))
            self.assertEqual(len(track.waypoints), len(rotations))
            self.assertEqual(len(track.tangent_rates), len(rotations))
            self.assertEqual(len(track.segments), len(durations))
            self.assertAlmostEqual(track.total_seconds, sum(durations), places=12)
            self.assertEqual([segment.start_seconds for segment in track.segments], [sum(durations[:index]) for index in range(len(durations))])

    def test_repeated_direct_queries_are_history_independent(self):
        track = compile_orientation_track(
            (IDENTITY, axis_angle((0, 0, 1), 80), axis_angle((0, 1, 1), 155)),
            (0.75, 4.25),
        )
        queries = (4.9, 0.0, 0.75, 2.125, 100.0, -2.0, 2.125)
        first = [evaluate_orientation(track, value) for value in queries]
        second = [evaluate_orientation(track, value) for value in reversed(queries)]
        self.assertEqual(first[-1], second[-4])

    def test_join_controls_share_the_same_time_domain_angular_rate(self):
        track = compile_orientation_track(
            (IDENTITY, axis_angle((0, 0, 1), 35), axis_angle((1, 1, 0), 145)),
            (0.2, 7.5),
        )
        join = track.segments[0].end
        incoming = tuple(value * 6.0 / track.segments[0].duration_seconds for value in logarithmic_delta(track.segments[0].end_control, join))
        outgoing = tuple(value * 6.0 / track.segments[1].duration_seconds for value in logarithmic_delta(join, track.segments[1].start_control))
        self.assertLess(math.sqrt(sum((left - right) ** 2 for left, right in zip(incoming, outgoing))), 1e-10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
