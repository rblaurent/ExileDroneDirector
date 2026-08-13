"""Freeze the Blueprint seam for per-segment flight-profile compilation."""

from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/flight_profile_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
from flight_profile_reference import PROFILE_ORDER, compile_flight_profiles, evaluate_flight_profile  # noqa: E402


class FlightProfileBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_supported_types_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual((SCHEMA["limits"]["minimumSegments"], SCHEMA["limits"]["maximumSegments"]), (1, 511))
        self.assertEqual(tuple(SCHEMA["limits"]["profileIds"]), PROFILE_ORDER)
        variables = SCHEMA["variables"]
        names = [value["name"] for value in variables]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(value["type"] in {"String", "Float", "Integer", "Boolean"} for value in variables))
        self.assertTrue(all(value["container"] in {"None", "Array"} for value in variables))
        self.assertEqual(len(variables), 53)

    def test_parameter_channels_are_exact_disjoint_and_complete(self):
        self.assertEqual(len(SCHEMA["parameterChannels"]), 10)
        variables = SCHEMA["variables"]
        roles = {role: {value["name"] for value in variables if value["role"] == role} for role in ("candidate", "result", "evaluationResult")}
        self.assertTrue(roles["candidate"].isdisjoint(roles["result"]))
        self.assertTrue(roles["result"].isdisjoint(roles["evaluationResult"]))
        self.assertEqual(len([name for name in roles["candidate"] if "Candidate" in name]), 11)
        self.assertEqual(len([name for name in roles["result"] if "Compiled" in name]), 11)
        self.assertEqual(len([name for name in roles["evaluationResult"] if "Result" in name]), 12)
        for channel in SCHEMA["parameterChannels"]:
            self.assertIn(channel["candidate"], roles["candidate"])
            self.assertIn(channel["compiled"], roles["result"])
            self.assertIn(channel["result"], roles["evaluationResult"])
        resolver_input = {value["name"] for value in variables if value["role"] == "resolverInput"}
        resolver_result = {value["name"] for value in variables if value["role"] == "resolverResult"}
        self.assertEqual(resolver_input, {"FlightProfileResolveInputIdV1"})
        self.assertEqual(len(resolver_result), 12)
        self.assertTrue(resolver_input.isdisjoint(resolver_result | roles["candidate"] | roles["result"]))
        self.assertTrue(resolver_result.isdisjoint(roles["candidate"] | roles["result"] | roles["evaluationResult"]))

    def test_stage_order_and_dependencies_are_exact(self):
        functions = SCHEMA["functions"]
        self.assertEqual([value["stage"] for value in functions], list(range(7)))
        by_name = {value["name"]: value for value in functions}
        self.assertEqual(by_name["BuildFlightProfileCandidatesV1"]["uses"], ["ResolveFlightProfilePresetV1"])
        self.assertEqual(
            by_name["CompileFlightProfilesV1"]["uses"],
            ["ResetFlightProfileStateV1", "ValidateFlightProfileInputsV1", "BuildFlightProfileCandidatesV1", "CommitCompiledFlightProfilesV1"],
        )

    def test_contracts_require_atomic_fail_closed_resolution(self):
        contracts = " ".join(SCHEMA["contracts"].values()).lower()
        for required in (
            "five exact canonical profile ids",
            "every override is validated",
            "every candidate array",
            "only commitcompiledflightprofilesv1",
            "immutable canonical preset",
            "never falls back",
            "leaves validity false",
        ):
            self.assertIn(required, contracts)

    def test_seeded_oracle_publications_obey_the_frozen_schema(self):
        rng = random.Random(0xEDD092)
        for _case in range(100):
            count = rng.randint(1, 64)
            default_id = rng.choice(PROFILE_ORDER)
            overrides = tuple("" if rng.random() < 0.4 else rng.choice(PROFILE_ORDER) for _ in range(count))
            compiled = compile_flight_profiles(default_id, overrides, count)
            self.assertEqual(len(compiled.profiles), count)
            for index in range(count):
                result = evaluate_flight_profile(compiled, index)
                self.assertEqual(result.segment_index, index)
                self.assertIn(result.profile.profile_id, PROFILE_ORDER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
