from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/airframe_source_sampling_blueprint_schema.json").read_text(encoding="utf-8"))


class AirframeSourceSamplingBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_order_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"], {
            "minimumWaypoints": 2,
            "maximumWaypoints": 512,
            "minimumFixedStepSeconds": 1.0 / 240.0,
            "maximumFixedStepSeconds": 0.5,
            "maximumTotalSeconds": 3600.0,
            "maximumSampleCount": 65536,
        })
        self.assertEqual([item["name"] for item in SCHEMA["functions"]], [
            "ResetAirframeSourceSamplingV1",
            "ValidateAirframeSourceSamplingInputsV1",
            "CompileAirframeSourcePositionProfilesV1",
            "BuildAirframeSourcePositionBodyProfileSamplesV1",
            "BuildAirframeSourceGimbalSamplesV1",
            "CommitAirframeSourceSamplesToDesiredV1",
            "CompileAirframeSourceSamplingV1",
        ])
        self.assertEqual([item["stage"] for item in SCHEMA["functions"]], list(range(7)))

    def test_variables_freeze_distinct_authorship_and_complete_candidates(self):
        variables = SCHEMA["variables"]
        names = [item["name"] for item in variables]
        self.assertEqual(len(variables), 22)
        self.assertEqual(len(names), len(set(names)))
        by_role = {}
        for item in variables:
            by_role.setdefault(item["role"], []).append(item)
        self.assertEqual({role: len(items) for role, items in by_role.items()}, {
            "input": 3, "candidate": 13, "scratch": 5, "result": 1,
        })
        authored = {item["name"] for item in by_role["input"] if item["container"] == "Array"}
        self.assertEqual(authored, {
            "AirframeSourceInputBodyWaypointQuatsV1",
            "AirframeSourceInputGimbalWaypointQuatsV1",
        })
        candidates = by_role["candidate"]
        self.assertEqual(sum(item["type"] == "Vector" for item in candidates), 1)
        self.assertEqual(sum(item["type"] == "Quat" for item in candidates), 2)
        self.assertEqual(sum(item["type"] == "Float" for item in candidates), 10)
        self.assertTrue(all(item["container"] == "Array" for item in candidates))

    def test_existing_component_inputs_and_calls_are_explicit(self):
        self.assertEqual(set(SCHEMA["existingInputs"]), {
            "PositionRouteInputWaypointPositionsV1",
            "PositionRouteInputDurationsV1",
            "PositionRouteInputSpatialCurveTypesV1",
            "PositionRouteInputTimeProfilesV1",
            "PositionRouteInputArcToleranceV1",
            "PositionRouteInputMaxArcDepthV1",
            "PositionRouteInputMaxArcOperationsV1",
            "FlightProfileInputDefaultIdV1",
            "FlightProfileInputSegmentOverrideIdsV1",
        })
        by_name = {item["name"]: item for item in SCHEMA["functions"]}
        self.assertEqual(by_name["ResetAirframeSourceSamplingV1"]["uses"], ["ResetAirframeDesiredStreamV1"])
        self.assertEqual(by_name["BuildAirframeSourcePositionBodyProfileSamplesV1"]["uses"].count("CompileOrientationTrackV1"), 1)
        self.assertEqual(by_name["BuildAirframeSourceGimbalSamplesV1"]["uses"].count("CompileOrientationTrackV1"), 1)
        self.assertEqual(by_name["CommitAirframeSourceSamplesToDesiredV1"]["uses"], ["CompileAirframeDesiredStreamV1"])

    def test_contracts_freeze_atomic_sequential_sampling(self):
        contracts = SCHEMA["contracts"]
        self.assertEqual(set(contracts), {
            "authorship", "timeline", "schedule", "sequentialOrientationCache",
            "profiles", "atomicity", "failure", "determinism",
        })
        joined = " ".join(contracts.values()).lower()
        for phrase in (
            "distinct required inputs",
            "exact terminal schedule agreement",
            "ceil(total / step) + 1",
            "first loaded with body authorship",
            "all ten bounded channels atomically",
            "publishes source validity last",
            "no partial authoritative motion",
            "no game-frame delta",
        ):
            self.assertIn(phrase, joined)

    def test_names_do_not_collide_with_accepted_schemas(self):
        current = {item["name"] for item in SCHEMA["variables"]}
        for filename in (
            "position_route_blueprint_schema.json",
            "orientation_blueprint_schema.json",
            "flight_profile_blueprint_schema.json",
            "smoothed_flight_profile_blueprint_schema.json",
            "airframe_desired_stream_blueprint_schema.json",
        ):
            other = json.loads((ROOT / "tools/trajectory" / filename).read_text(encoding="utf-8"))
            self.assertFalse(current & {item["name"] for item in other["variables"]}, filename)


if __name__ == "__main__":
    unittest.main(verbosity=2)
