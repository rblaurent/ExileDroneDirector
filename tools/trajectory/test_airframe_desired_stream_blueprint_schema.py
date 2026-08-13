import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/airframe_desired_stream_blueprint_schema.json").read_text(encoding="utf-8"))


class AirframeDesiredStreamBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_function_order_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(
            SCHEMA["limits"],
            {
                "minimumFixedStepSeconds": 1.0 / 240.0,
                "maximumFixedStepSeconds": 0.5,
                "maximumTotalSeconds": 3600.0,
                "maximumSampleCount": 65536,
            },
        )
        self.assertEqual(
            [entry["name"] for entry in SCHEMA["functions"]],
            [
                "ResetAirframeDesiredStreamV1",
                "ValidateAirframeDesiredStreamInputsV1",
                "BuildAirframeDesiredVelocitySamplesV1",
                "BuildAirframeDesiredAccelerationSamplesV1",
                "BuildAirframeDesiredJerkSamplesV1",
                "SampleAirframeDesiredVelocityAtTimeV1",
                "SolveAirframeDesiredPoseSamplesV1",
                "CommitAirframeDesiredStreamToPrebakeV1",
                "CompileAirframeDesiredStreamV1",
            ],
        )
        self.assertEqual([entry["stage"] for entry in SCHEMA["functions"]], list(range(9)))

    def test_source_streams_are_complete_distinct_and_blueprint_safe(self):
        variables = SCHEMA["variables"]
        names = [entry["name"] for entry in variables]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(variables), 28)
        self.assertTrue(all(entry["type"] in {"Boolean", "Integer", "Float", "Vector", "Quat"} for entry in variables))
        self.assertTrue(all(entry["container"] in {"None", "Array"} for entry in variables))
        inputs = [entry for entry in variables if entry["role"] == "input"]
        self.assertEqual(len(inputs), 15)
        self.assertEqual(sum(entry["container"] == "Array" for entry in inputs), 13)
        self.assertIn("AirframeDesiredStreamInputAuthoredBodyQuatsV1", names)
        self.assertIn("AirframeDesiredStreamInputAuthoredGimbalQuatsV1", names)
        self.assertNotEqual(
            names.index("AirframeDesiredStreamInputAuthoredBodyQuatsV1"),
            names.index("AirframeDesiredStreamInputAuthoredGimbalQuatsV1"),
        )
        expected_profile_arrays = {
            "AirframeDesiredStreamInputPathFollowWeightsV1",
            "AirframeDesiredStreamInputHorizonStabilizationWeightsV1",
            "AirframeDesiredStreamInputLookAheadSecondsV1",
            "AirframeDesiredStreamInputBankGainsV1",
            "AirframeDesiredStreamInputMaxBankDegreesV1",
            "AirframeDesiredStreamInputCameraUptiltDegreesV1",
            "AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1",
            "AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1",
            "AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1",
            "AirframeDesiredStreamInputMinimumTurnRadiiCmV1",
        }
        self.assertEqual({entry["name"] for entry in inputs if "Input" in entry["name"]} & expected_profile_arrays, expected_profile_arrays)

    def test_state_roles_and_downstream_ownership_are_explicit(self):
        by_role = {}
        for entry in SCHEMA["variables"]:
            by_role.setdefault(entry["role"], set()).add(entry["name"])
        self.assertEqual({key: len(value) for key, value in by_role.items()}, {
            "input": 15, "candidate": 9, "helperInput": 1, "helperResult": 2, "result": 1
        })
        self.assertEqual(by_role["result"], {"AirframeDesiredStreamCompileValidV1"})
        self.assertFalse(any(name.startswith("AirframePrebakeCompiled") for name in (entry["name"] for entry in SCHEMA["variables"])))
        reset, *_middle, commit, compile_stage = SCHEMA["functions"]
        self.assertEqual(reset["uses"], ["ResetAirframePrebakeCandidateV1"])
        self.assertEqual(commit["uses"], ["CompileAirframePrebakeV1"])
        self.assertEqual(
            compile_stage["uses"],
            [
                "ResetAirframeDesiredStreamV1",
                "ValidateAirframeDesiredStreamInputsV1",
                "BuildAirframeDesiredVelocitySamplesV1",
                "BuildAirframeDesiredAccelerationSamplesV1",
                "BuildAirframeDesiredJerkSamplesV1",
                "SolveAirframeDesiredPoseSamplesV1",
                "CommitAirframeDesiredStreamToPrebakeV1",
            ],
        )

    def test_contracts_freeze_partial_schedule_kinematics_and_atomicity(self):
        contracts = SCHEMA["contracts"]
        self.assertEqual(
            set(contracts),
            {"sourceBoundary", "schedule", "kinematics", "lookAhead", "authorship", "atomicity", "failure", "determinism"},
        )
        joined = " ".join(contracts.values()).lower()
        for phrase in (
            "exact terminal sample",
            "local quadratic lagrange derivative",
            "linearly interpolated",
            "body and gimbal source arrays remain distinct",
            "publishes stream validity last",
            "no partial authoritative motion",
            "no game-frame delta",
        ):
            self.assertIn(phrase, joined)

    def test_variable_names_do_not_collide_with_accepted_component_schemas(self):
        current = {entry["name"] for entry in SCHEMA["variables"]}
        for filename in (
            "position_route_blueprint_schema.json",
            "smoothed_flight_profile_blueprint_schema.json",
            "airframe_gimbal_blueprint_schema.json",
            "airframe_gimbal_prebake_blueprint_schema.json",
        ):
            other = json.loads((ROOT / "tools/trajectory" / filename).read_text(encoding="utf-8"))
            self.assertFalse(current & {entry["name"] for entry in other["variables"]}, filename)


if __name__ == "__main__":
    unittest.main(verbosity=2)
