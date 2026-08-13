from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/airframe_gimbal_blueprint_schema.json").read_text(encoding="utf-8"))


class AirframeGimbalBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_asset_limits_and_function_order_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"], {
            "finiteScalarBound": 1.7976931348623157e308,
            "gravityCmPerSecondSquared": 980.665,
            "quaternionUnitTolerance": 0.000001,
            "vectorEpsilon": 0.000000001,
        })
        self.assertEqual(
            [function["name"] for function in SCHEMA["functions"]],
            ["ResetAirframeGimbalV1", "ValidateAirframeGimbalInputsV1", "SolveAirframeGimbalV1"],
        )
        self.assertEqual([function["stage"] for function in SCHEMA["functions"]], [0, 1, 2])

    def test_variables_are_complete_unique_and_blueprint_safe(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 25)
        names = [variable["name"] for variable in variables]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual({variable["type"] for variable in variables}, {"Vector", "Quat", "Float", "Boolean"})
        self.assertTrue(all(variable["container"] == "None" for variable in variables))
        self.assertEqual([name for name in names if name.startswith("AirframeGimbalInput")], names[:16])
        self.assertEqual(names[16], "AirframeGimbalStageValidV1")
        self.assertEqual(names[-1], "AirframeGimbalResultValidV1")

    def test_all_smoothed_profile_channels_cross_the_boundary_once(self):
        profile_suffixes = (
            "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
            "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
            "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
            "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
        )
        names = {variable["name"] for variable in SCHEMA["variables"]}
        self.assertEqual(
            {f"AirframeGimbalInput{suffix}V1" for suffix in profile_suffixes},
            {name for name in names if name.startswith("AirframeGimbalInput") and name not in {
                "AirframeGimbalInputCurrentVelocityV1", "AirframeGimbalInputLookAheadVelocityV1",
                "AirframeGimbalInputAccelerationV1", "AirframeGimbalInputJerkV1",
                "AirframeGimbalInputAuthoredBodyQuatV1", "AirframeGimbalInputAuthoredGimbalQuatV1",
            }},
        )

    def test_state_roles_and_defaults_are_fail_closed(self):
        by_role = {}
        for variable in SCHEMA["variables"]:
            by_role.setdefault(variable["role"], []).append(variable)
        self.assertEqual(set(by_role), {"input", "candidate", "result"})
        self.assertEqual([item["name"] for item in by_role["candidate"]], ["AirframeGimbalStageValidV1"])
        self.assertFalse(by_role["candidate"][0]["default"])
        results = by_role["result"]
        self.assertEqual(len(results), 8)
        self.assertFalse(results[-1]["default"])
        self.assertTrue(all(item["default"] == [0.0, 0.0, 0.0, 1.0] for item in results[:3]))
        self.assertTrue(all(item["default"] == 0.0 for item in results[3:-1]))

    def test_contracts_freeze_history_independence_limits_and_atomicity(self):
        contracts = SCHEMA["contracts"]
        self.assertEqual(set(contracts), {
            "sampling", "desiredPose", "body", "gimbal", "physicalGates", "atomicity", "failure",
        })
        self.assertIn("absolute-time", contracts["sampling"])
        self.assertIn("history-free", contracts["desiredPose"])
        self.assertIn("fixed-step", contracts["desiredPose"])
        self.assertIn("PathFollowWeight", contracts["body"])
        self.assertIn("HorizonStabilizationWeight", contracts["gimbal"])
        self.assertIn("turn radius", contracts["physicalGates"])
        self.assertIn("TurnRadiusCm is zero", contracts["physicalGates"])
        self.assertIn("validity publishes last", contracts["atomicity"])
        self.assertIn("never mutates an input", contracts["failure"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
