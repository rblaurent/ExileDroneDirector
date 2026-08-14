"""Frozen Blueprint ABI contracts for camera engine application."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from camera_channel_assembly_reference import CHANNEL_IDS_V1
from camera_engine_application_reference import (
    NEUTRAL_TARGET_VALUES_V1,
    POST_PROCESS_OVERRIDE_TARGET_IDS_V1,
    REQUIRED_TARGET_IDS_V1,
    TARGET_IDS_V1,
)


SCHEMA_PATH = Path(__file__).with_name("camera_engine_application_blueprint_schema.json")


class CameraEngineApplicationBlueprintSchemaContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_targets_match_the_accepted_camera_frame_without_aliases(self):
        targets = self.schema["targets"]
        self.assertEqual(targets["count"], 15)
        self.assertEqual(tuple(targets["ids"]), TARGET_IDS_V1)
        self.assertEqual(tuple(targets["ids"][2:]), CHANNEL_IDS_V1)
        self.assertEqual(len(targets["ids"]), len(set(targets["ids"])))
        self.assertEqual(tuple(targets["neutralValues"]), NEUTRAL_TARGET_VALUES_V1)
        self.assertEqual(tuple(targets["requiredIds"]), REQUIRED_TARGET_IDS_V1)
        self.assertEqual(
            tuple(targets["postProcessOverrideIds"]),
            POST_PROCESS_OVERRIDE_TARGET_IDS_V1,
        )

    def test_state_layers_and_capability_identity_are_distinct(self):
        variables = self.schema["variables"]
        names = [item["name"] for item in variables]
        self.assertEqual(len(names), len(set(names)))
        for layer in ("Input", "Baseline", "Current"):
            self.assertIn(f"CameraApply{layer}TargetValuesV1", names)
        self.assertIn("CameraApplyBaselineOverrideFlagsV1", names)
        self.assertIn("CameraApplyCurrentOverrideFlagsV1", names)
        self.assertIn("CameraApplyCapabilityEngineVersionV1", names)
        self.assertIn("CameraApplyCapabilityManifestIdV1", names)
        self.assertIn("CameraApplyCapabilityAvailableV1", names)

    def test_function_order_separates_preflight_capture_apply_and_restore(self):
        functions = self.schema["functions"]
        self.assertEqual([item["stage"] for item in functions], list(range(6)))
        self.assertEqual([item["name"] for item in functions], [
            "ResetCameraEngineApplicationResultV1",
            "ValidateCameraEngineApplicationInputsV1",
            "CaptureCameraEngineStateV1",
            "ApplyCameraEngineFrameV1",
            "RestoreCameraEngineStateV1",
            "ApplyEvaluatedCameraChannelFrameV1",
        ])
        self.assertNotIn("RestoreCameraEngineStateV1", functions[-1]["uses"])
        self.assertTrue(functions[2]["engineReads"])
        self.assertTrue(functions[3]["engineWrites"])
        self.assertTrue(functions[4]["engineWrites"])

    def test_contract_requires_zero_write_rejection_and_exact_restoration(self):
        contracts = self.schema["invariants"]
        self.assertIn("before the first engine property write", contracts["atomicity"])
        self.assertIn("zero camera or post-process writes", contracts["atomicity"])
        self.assertIn("cannot replace the baseline", contracts["capture"])
        self.assertIn("exact baseline restoration", contracts["restore"])
        self.assertIn("override flags", contracts["overrides"])
        self.assertIn("Runtime reflection", contracts["capabilities"])

    def test_schema_keeps_authored_and_compiled_camera_banks_read_only(self):
        ownership = self.schema["invariants"]["ownership"]
        for layer in ("authored", "candidate", "compiled", "evaluated"):
            self.assertIn(layer, ownership)


if __name__ == "__main__":
    unittest.main(verbosity=2)
