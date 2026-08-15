from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "bounded_event_adapter_blueprint_schema.json").read_text(encoding="utf-8"))


class BoundedEventAdapterBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_function_order_are_exact(self):
        self.assertEqual(SCHEMA["schema"], "edd.bounded-event-adapter.v1")
        self.assertEqual(SCHEMA["version"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"], {
            "maximumCues": 256,
            "maximumPayloadBytes": 1024,
            "maximumLedgerEntries": 1024,
            "maximumCrossingsPerFrame": 32,
        })
        self.assertEqual(
            [function["name"] for function in SCHEMA["functions"]],
            [
                "ResetBoundedEventDispatchResultV1",
                "ValidateBoundedEventPlanV1",
                "CollectCrossedCuesV1",
                "SelectEligibleCrossedCueV1",
                "AuthorizeSelectedCueV1",
                "CommitCueExecutionLedgerV1",
                "ResetManualCueLedgerEntryV1",
                "DispatchBoundedPlaybackEventsV1",
            ],
        )
        self.assertEqual([function["stage"] for function in SCHEMA["functions"]], list(range(8)))

    def test_parallel_compiled_arrays_and_authority_are_frozen(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 48)
        self.assertEqual(len({item["name"] for item in variables}), 48)
        compiled = [item for item in variables if item["role"] == "compiled"]
        self.assertEqual(len(compiled), 16)
        self.assertTrue(all(item["container"] == "Array" and item["default"] == [] for item in compiled))
        by_name = {item["name"]: item for item in variables}
        self.assertEqual(by_name["EventCuePlanValidV1"]["role"], "compiled-authority")
        self.assertEqual(by_name["EventDispatchResultValidV1"]["role"], "result-authority")
        self.assertEqual(by_name["EventDispatchIndexV1"]["default"], -1)
        self.assertFalse(by_name["EventServerWorldEnabledV1"]["default"])
        self.assertFalse(by_name["EventServerRevisionApprovedV1"]["default"])
        self.assertEqual(by_name["EventPlanValidationValidV1"]["role"], "stage")
        self.assertEqual(by_name["EventCrossingCollectionValidV1"]["role"], "stage")
        self.assertEqual(by_name["EventSelectionValidV1"]["role"], "stage")
        self.assertEqual(by_name["EventCandidateAlreadyExecutedV1"]["role"], "scratch")
        for name in (
            "EventResolvedBindingIdsV1",
            "EventResolvedBindingDistancesV1",
            "EventGrantedPermissionsV1",
        ):
            self.assertEqual(by_name[name]["role"], "authorization")
            self.assertEqual(by_name[name]["container"], "Array")

    def test_manifest_is_closed_bounded_and_safe_by_default(self):
        manifest = SCHEMA["manifest"]
        self.assertEqual(len(manifest), 5)
        keys = {(item["adapter"], item["version"], item["operation"]) for item in manifest}
        self.assertEqual(len(keys), 5)
        self.assertFalse(any(item["scope"] == "local_cinematic" and item["mutatesWorld"] for item in manifest))
        server = [item for item in manifest if item["scope"] == "server_world"]
        self.assertEqual(len(server), 1)
        self.assertFalse(server[0]["enabledByDefault"])
        self.assertNotIn("synchronized_performance", {item["scope"] for item in manifest})

    def test_crossing_scrub_identity_authorization_and_ledger_are_explicit(self):
        architecture = SCHEMA["architecture"]
        self.assertIn("previous < cue <= current", architecture["crossing"])
        self.assertIn("current <= cue < previous", architecture["crossing"])
        self.assertIn("exact no-dispatch", architecture["scrubbing"])
        self.assertIn("immutable published revision", architecture["identity"])
        self.assertIn("post-clone binding", architecture["authorization"])
        self.assertIn("positive rate budget", architecture["authorization"])
        self.assertIn("before EventCuePlanValidV1 is published", architecture["payload"])
        self.assertIn("treats the compiled payload as opaque", architecture["payload"])
        self.assertIn("server adapter must revalidate", architecture["payload"])
        self.assertIn("Only adapter success commits", architecture["ledger"])

    def test_coordinator_and_forbidden_ownership_are_exact(self):
        coordinator = SCHEMA["functions"][-1]
        self.assertEqual(coordinator["uses"], [
            "ResetBoundedEventDispatchResultV1",
            "ValidateBoundedEventPlanV1",
            "CollectCrossedCuesV1",
            "SelectEligibleCrossedCueV1",
            "AuthorizeSelectedCueV1",
        ])
        forbidden = SCHEMA["architecture"]["forbidden"]
        for value in (
            "Arbitrary actor pointers", "class names", "function names",
            "CameraTransform", "body/gimbal authorship", "native camera mutation",
            "repository mutation", "polished UI", "cooking", "deployment",
            "synchronized performance",
        ):
            self.assertIn(value, forbidden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
