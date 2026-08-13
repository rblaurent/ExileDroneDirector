from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/airframe_gimbal_prebake_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
from airframe_gimbal_prebake_reference import (  # noqa: E402
    MAXIMUM_ANGULAR_RATE_DEGREES_PER_SECOND,
    MAXIMUM_FIXED_STEP_SECONDS,
    MAXIMUM_SAMPLE_COUNT,
    MAXIMUM_TOTAL_SECONDS,
    MINIMUM_FIXED_STEP_SECONDS,
    UNIT_TOLERANCE,
)


class AirframeGimbalPrebakeBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_stage_order_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"], {
            "minimumFixedStepSeconds": MINIMUM_FIXED_STEP_SECONDS,
            "maximumFixedStepSeconds": MAXIMUM_FIXED_STEP_SECONDS,
            "maximumTotalSeconds": MAXIMUM_TOTAL_SECONDS,
            "maximumSampleCount": MAXIMUM_SAMPLE_COUNT,
            "maximumAngularRateDegreesPerSecond": MAXIMUM_ANGULAR_RATE_DEGREES_PER_SECOND,
            "quaternionUnitTolerance": UNIT_TOLERANCE,
        })
        functions = SCHEMA["functions"]
        self.assertEqual([function["stage"] for function in functions], list(range(7)))
        self.assertEqual([function["name"] for function in functions], [
            "ResetAirframePrebakeCandidateV1",
            "ValidateAirframePrebakeInputsV1",
            "ApplyAirframeAngularRateLimitV1",
            "BuildAirframePrebakeSamplesV1",
            "CommitCompiledAirframePrebakeV1",
            "CompileAirframePrebakeV1",
            "EvaluateCompiledAirframePrebakeV1",
        ])

    def test_variables_are_unique_blueprint_safe_and_role_partitioned(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 40)
        names = [variable["name"] for variable in variables]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual({variable["type"] for variable in variables}, {"Quat", "Float", "Boolean", "Integer"})
        self.assertEqual({variable["container"] for variable in variables}, {"Array", "None"})
        roles = {role: [variable for variable in variables if variable["role"] == role]
                 for role in ("input", "candidate", "result", "scratch", "evaluationInput", "evaluationResult")}
        self.assertEqual(tuple(len(roles[role]) for role in roles), (5, 8, 9, 11, 1, 6))
        self.assertEqual(sum(len(values) for values in roles.values()), len(variables))

    def test_candidate_and_compiled_payloads_are_one_to_one(self):
        names = {variable["name"] for variable in SCHEMA["variables"]}
        channels = (
            "BodyQuats", "GimbalQuats", "BodyAngularRatesDegreesPerSecond",
            "GimbalAngularRatesDegreesPerSecond", "BodyRateLimited", "GimbalRateLimited",
        )
        for channel in channels:
            self.assertIn(f"AirframePrebakeCandidate{channel}V1", names)
            self.assertIn(f"AirframePrebakeCompiled{channel}V1", names)
        self.assertEqual(
            {variable["type"] for variable in SCHEMA["variables"] if "RateLimited" in variable["name"]},
            {"Boolean"},
        )

    def test_defaults_are_fail_closed_and_first_step_is_explicit(self):
        defaults = {variable["name"]: variable.get("default") for variable in SCHEMA["variables"]}
        self.assertAlmostEqual(defaults["AirframePrebakeInputFixedStepSecondsV1"], 1.0 / 60.0)
        self.assertFalse(defaults["AirframePrebakeStageValidV1"])
        self.assertFalse(defaults["AirframePrebakeCompileValidV1"])
        self.assertFalse(defaults["AirframePrebakeResultValidV1"])
        self.assertEqual(defaults["AirframePrebakeResultSegmentIndexV1"], -1)
        self.assertEqual(defaults["AirframePrebakeResultBodyQuatV1"], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(defaults["AirframePrebakeResultGimbalQuatV1"], [0.0, 0.0, 0.0, 1.0])

    def test_function_dependencies_keep_rate_limiting_inside_compile(self):
        by_name = {function["name"]: function for function in SCHEMA["functions"]}
        self.assertEqual(by_name["BuildAirframePrebakeSamplesV1"]["uses"], ["ApplyAirframeAngularRateLimitV1"])
        self.assertNotIn("uses", by_name["EvaluateCompiledAirframePrebakeV1"])
        scratch = [variable for variable in SCHEMA["variables"] if variable["role"] == "scratch"]
        self.assertEqual(len(scratch), 11)
        self.assertEqual(scratch[-4]["name"], "AirframePrebakeScratchResultQuatV1")
        self.assertEqual(scratch[-1]["name"], "AirframePrebakeScratchResultValidV1")

    def test_contracts_freeze_schedule_rate_atomicity_and_absolute_time(self):
        self.assertEqual(set(SCHEMA["contracts"]), {
            "schedule", "rateLimit", "shotBoundary", "sign", "helper", "atomicity", "failure", "evaluation",
        })
        contracts = " ".join(SCHEMA["contracts"].values()).lower()
        for required in (
            "ceil(totalseconds / fixedstepseconds) + 1",
            "min(rate[i-1], rate[i])",
            "first desired body and gimbal samples seed the shot exactly",
            "180-degree ties",
            "resets its four result fields before every call",
            "validity is published last",
            "clears all compiled and evaluation results",
            "absolute elapsed seconds",
            "never integrates game-frame delta",
        ):
            self.assertIn(required, contracts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
