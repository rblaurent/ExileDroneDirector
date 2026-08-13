"""Freeze the Blueprint seam for atomic cinematic pose composition."""

from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/cinematic_pose_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
from cinematic_pose_reference import compile_cinematic_pose, evaluate_cinematic_pose  # noqa: E402
from cinematic_reference import AuthoredSegment  # noqa: E402
from orientation_reference import normalize  # noqa: E402


class CinematicPoseBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_supported_types_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual((SCHEMA["limits"]["minimumWaypoints"], SCHEMA["limits"]["maximumWaypoints"]), (2, 512))
        names = [value["name"] for value in SCHEMA["variables"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(value["type"] in {"Quat", "Vector", "Float", "Integer", "Boolean"} for value in SCHEMA["variables"]))
        self.assertTrue(all(value["container"] == "None" for value in SCHEMA["variables"]))

    def test_result_roles_are_disjoint_and_fail_closed(self):
        roles = {role: {value["name"] for value in SCHEMA["variables"] if value["role"] == role} for role in ("candidate", "result", "evaluationInput", "evaluationResult")}
        self.assertEqual(tuple(map(len, roles.values())), (1, 2, 1, 8))
        self.assertTrue(roles["candidate"].isdisjoint(roles["result"]))
        self.assertTrue(roles["result"].isdisjoint(roles["evaluationResult"]))
        defaults = {value["name"]: value.get("default") for value in SCHEMA["variables"]}
        self.assertFalse(defaults["CinematicPoseStageValidV1"])
        self.assertFalse(defaults["CinematicPoseCompileValidV1"])
        self.assertFalse(defaults["CinematicPoseResultValidV1"])
        self.assertEqual(defaults["CinematicPoseResultSegmentIndexV1"], -1)

    def test_stage_order_and_dependencies_are_exact(self):
        functions = SCHEMA["functions"]
        self.assertEqual([value["stage"] for value in functions], list(range(5)))
        by_name = {value["name"]: value for value in functions}
        self.assertEqual(
            by_name["CompileCinematicPoseV1"]["uses"],
            ["ResetCinematicPoseV1", "ValidateCinematicPoseInputsV1", "CompilePositionRouteV1", "CompileOrientationTrackV1", "CommitCompiledCinematicPoseV1"],
        )
        self.assertEqual(
            by_name["EvaluateCompiledCinematicPoseV1"]["uses"],
            ["EvaluateCompiledPositionRouteV1", "EvaluateCompiledOrientationTrackV1"],
        )

    def test_contracts_require_exact_atomic_absolute_time_composition(self):
        contracts = " ".join(SCHEMA["contracts"].values()).lower()
        for required in (
            "exact same duration array",
            "must agree exactly",
            "only commitcompiledcinematicposev1",
            "clears every combined result",
            "absolute elapsed",
            "never constitute a valid combined pose",
        ):
            self.assertIn(required, contracts)

    def test_seeded_oracle_tracks_obey_the_frozen_schema(self):
        rng = random.Random(0xEDD081)
        for _case in range(40):
            count = rng.randint(2, 10)
            points = tuple((rng.uniform(-1000, 1000), rng.uniform(-1000, 1000), rng.uniform(-1000, 1000)) for _ in range(count))
            rotations = tuple(normalize(tuple(rng.uniform(-1, 1) for _ in range(4))) for _ in range(count))
            segments = tuple(AuthoredSegment(rng.uniform(0.05, 5.0)) for _ in range(count - 1))
            compiled = compile_cinematic_pose(points, rotations, segments)
            for elapsed in (-1.0, 0.0, compiled.total_seconds * 0.37, compiled.total_seconds, compiled.total_seconds + 1.0):
                result = evaluate_cinematic_pose(compiled, elapsed)
                self.assertEqual(result.total_seconds, compiled.total_seconds)
                self.assertGreaterEqual(result.segment_index, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
