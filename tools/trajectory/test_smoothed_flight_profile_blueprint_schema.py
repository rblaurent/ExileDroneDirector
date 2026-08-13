"""Freeze the Blueprint seam for C2 flight-profile transitions."""

from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/smoothed_flight_profile_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
from flight_profile_reference import PROFILE_ORDER, compile_flight_profiles  # noqa: E402
from smoothed_flight_profile_reference import (  # noqa: E402
    PARAMETER_FIELDS,
    evaluate_smoothed_flight_profile,
)


class SmoothedFlightProfileBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_supported_types_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual((SCHEMA["limits"]["minimumSegments"], SCHEMA["limits"]["maximumSegments"]), (1, 511))
        self.assertEqual(SCHEMA["limits"]["localTimeAlpha"], [0.0, 1.0])
        self.assertEqual(SCHEMA["limits"]["maximumNeighborWeight"], 0.5)
        names = [value["name"] for value in SCHEMA["variables"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(value["type"] in {"String", "Float", "Integer", "Boolean"} for value in SCHEMA["variables"]))
        self.assertTrue(all(value["container"] == "None" for value in SCHEMA["variables"]))

    def test_parameter_channels_are_complete_and_one_to_one(self):
        expected = [
            "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
            "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
            "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
            "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
        ]
        self.assertEqual(SCHEMA["parameterFields"], expected)
        self.assertEqual(
            tuple("".join(part.capitalize() for part in field.split("_")) for field in PARAMETER_FIELDS),
            tuple(expected),
        )
        names = {value["name"] for value in SCHEMA["variables"]}
        for field in expected:
            self.assertIn(f"SmoothedFlightProfileCurrent{field}V1", names)
            self.assertIn(f"SmoothedFlightProfileNeighbor{field}V1", names)
            self.assertIn(f"SmoothedFlightProfileResult{field}V1", names)

    def test_state_roles_are_disjoint_and_fail_closed(self):
        roles = {
            role: {value["name"] for value in SCHEMA["variables"] if value["role"] == role}
            for role in ("input", "scratch", "result")
        }
        self.assertEqual(tuple(map(len, roles.values())), (2, 24, 14))
        self.assertTrue(roles["input"].isdisjoint(roles["scratch"]))
        self.assertTrue(roles["scratch"].isdisjoint(roles["result"]))
        defaults = {value["name"]: value.get("default") for value in SCHEMA["variables"]}
        self.assertEqual(defaults["SmoothedFlightProfileInputSegmentIndexV1"], -1)
        self.assertFalse(defaults["SmoothedFlightProfileStageValidV1"])
        self.assertFalse(defaults["SmoothedFlightProfileResultValidV1"])

    def test_stage_order_and_dependencies_are_exact(self):
        functions = SCHEMA["functions"]
        self.assertEqual([value["stage"] for value in functions], list(range(4)))
        by_name = {value["name"]: value for value in functions}
        self.assertEqual(
            by_name["StageSmoothedFlightProfileSamplesV1"]["uses"],
            ["EvaluateCompiledFlightProfileV1"],
        )
        self.assertEqual(
            by_name["EvaluateSmoothedFlightProfileV1"]["uses"],
            ["ResetSmoothedFlightProfileV1", "StageSmoothedFlightProfileSamplesV1", "PublishSmoothedFlightProfileV1"],
        )

    def test_contracts_require_c2_atomic_history_free_blending(self):
        contracts = " ".join(SCHEMA["contracts"].values()).lower()
        for required in (
            "exactly 1..511",
            "exact 50/50 boundary",
            "first and second derivatives zero",
            "restored to the requested current segment",
            "convex hull",
            "writes result validity last",
            "history-independent",
        ):
            self.assertIn(required, contracts)

    def test_seeded_oracle_outputs_obey_the_frozen_seam(self):
        rng = random.Random(0xEDD083)
        for _case in range(80):
            count = rng.randint(1, 64)
            overrides = tuple(rng.choice(PROFILE_ORDER) for _ in range(count))
            compiled = compile_flight_profiles(rng.choice(PROFILE_ORDER), overrides, count)
            for _query in range(40):
                result = evaluate_smoothed_flight_profile(compiled, rng.randrange(count), rng.random())
                self.assertIn(result.current_profile_id, PROFILE_ORDER)
                self.assertIn(result.neighbor_profile_id, PROFILE_ORDER)
                self.assertGreaterEqual(result.neighbor_weight, 0.0)
                self.assertLessEqual(result.neighbor_weight, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
