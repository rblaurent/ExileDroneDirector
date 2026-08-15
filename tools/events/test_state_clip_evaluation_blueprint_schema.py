from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "state_clip_evaluation_blueprint_schema.json").read_text(encoding="utf-8"))


class StateClipEvaluationBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_function_order_are_exact(self):
        self.assertEqual(SCHEMA["schema"], "edd.state-clip-evaluation.v1")
        self.assertEqual(SCHEMA["version"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"], {
            "maximumStateClips": 128,
            "maximumActiveStateClips": 32,
            "maximumDesiredStateBytes": 128,
            "maximumLeadSeconds": 30.0,
            "maximumTimeoutSeconds": 30.0,
        })
        self.assertEqual([item["name"] for item in SCHEMA["functions"]], [
            "ResetStateClipEvaluationV1",
            "ValidateStateClipPlanV1",
            "CollectActiveStateClipsV1",
            "CommitStateClipEvaluationV1",
            "EvaluateStateClipsAtTimeV1",
        ])
        self.assertEqual([item["stage"] for item in SCHEMA["functions"]], list(range(5)))

    def test_parallel_compiled_candidate_and_result_shapes_are_frozen(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 49)
        self.assertEqual(len({item["name"] for item in variables}), 49)
        compiled = [item for item in variables if item["role"] == "compiled"]
        candidates = [item for item in variables if item["role"] == "candidate"]
        results = [item for item in variables if item["role"] == "result"]
        self.assertEqual(len(compiled), 20)
        self.assertEqual(len(candidates), 9)
        self.assertEqual(len(results), 10)
        self.assertTrue(all(item["container"] == "Array" for item in compiled[:19]))
        self.assertTrue(all(item["container"] == "Array" for item in candidates))
        self.assertTrue(all(item["container"] == "Array" for item in results[:9]))
        by_name = {item["name"]: item for item in variables}
        self.assertEqual(by_name["StateClipPlanValidV1"]["role"], "compiled-authority")
        self.assertEqual(by_name["StateClipResultValidV1"]["role"], "result-authority")
        for name in ("StateClipValidationValidV1", "StateClipCollectionValidV1", "StateClipCommitValidV1"):
            self.assertEqual(by_name[name]["role"], "stage")

    def test_local_test_adapter_is_closed_preview_only_and_non_mutating(self):
        adapter = SCHEMA["localTestAdapter"]
        self.assertEqual(adapter["adapter"], "local.state_test")
        self.assertEqual(adapter["bindingType"], "local_channel")
        self.assertEqual(adapter["scope"], "local_cinematic")
        self.assertEqual(adapter["states"], ["off", "on", "accent"])
        self.assertFalse(adapter["mutatesWorld"])
        self.assertIn("explicit scrub request", adapter["preview"])

    def test_interval_preview_atomicity_and_downstream_seams_are_explicit(self):
        architecture = SCHEMA["architecture"]
        self.assertIn("start <= time < end", architecture["intervals"])
        self.assertIn("overlapping active intervals", architecture["intervals"])
        self.assertIn("history-free absolute-time", architecture["absoluteTime"])
        self.assertIn("forward/reverse query order", architecture["absoluteTime"])
        self.assertIn("never expand the active interval", architecture["leads"])
        self.assertIn("explicitly request", architecture["preview"])
        self.assertIn("publishes result authority last", architecture["atomicity"])
        self.assertIn("maximum of 32", architecture["ordering"])
        for value in ("Target resolution", "Event Anchors", "door state reads", "RPC execution", "leases"):
            self.assertIn(value, architecture["downstream"])

    def test_coordinator_and_forbidden_ownership_are_exact(self):
        self.assertEqual(SCHEMA["functions"][-1]["uses"], [
            "ResetStateClipEvaluationV1",
            "ValidateStateClipPlanV1",
            "CollectActiveStateClipsV1",
            "CommitStateClipEvaluationV1",
        ])
        forbidden = SCHEMA["architecture"]["forbidden"]
        for value in (
            "Transient actor pointers", "transform-only authority", "arbitrary classes",
            "reflection dispatch", "CameraTransform", "body/gimbal authorship",
            "repository mutation", "shared-world mutation", "polished UI", "cook",
            "deployment", "synchronized performance",
        ):
            self.assertIn(value, forbidden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
