from __future__ import annotations

import json
import unittest
from pathlib import Path

from camera_base_look_reference import (
    CAMERA_BASE_LOOK_IDS_V1,
    CHANNEL_IDS_V1,
    DIRECTLY_UNAVAILABLE_CHANNELS_V1,
)


SCHEMA = json.loads(
    (Path(__file__).with_name("camera_base_look_blueprint_schema.json")).read_text(encoding="utf-8")
)


class CameraBaseLookBlueprintSchemaContracts(unittest.TestCase):
    def test_asset_limits_and_catalog_are_frozen(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(tuple(SCHEMA["limits"]["presetIds"]), CAMERA_BASE_LOOK_IDS_V1)
        self.assertEqual(tuple(SCHEMA["limits"]["channelIds"]), CHANNEL_IDS_V1)
        self.assertEqual(tuple(SCHEMA["limits"]["directlyUnavailableChannels"]), DIRECTLY_UNAVAILABLE_CHANNELS_V1)
        self.assertEqual(SCHEMA["limits"]["channelCount"], 13)
        self.assertEqual(SCHEMA["limits"]["maximumAuthoredOverrides"], 13)

    def test_variables_are_unique_typed_and_role_separated(self):
        variables = SCHEMA["variables"]
        names = [variable["name"] for variable in variables]
        self.assertEqual(len(names), 17)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name.startswith("CameraLook") for name in names))
        self.assertTrue(all(variable["type"] in {"String", "Float", "Boolean", "Integer"} for variable in variables))
        roles = {role: {variable["name"] for variable in variables if variable["role"] == role} for role in {variable["role"] for variable in variables}}
        self.assertTrue(roles["input"].isdisjoint(roles["candidate"] | roles["result"] | roles["scratch"]))
        self.assertIn("CameraLookValidationValidV1", roles["validation"])

    def test_functions_freeze_the_transaction_order(self):
        functions = SCHEMA["functions"]
        self.assertEqual(
            tuple(function["name"] for function in functions),
            (
                "ResetCameraLookCompositionV1",
                "ValidateCameraLookInputsV1",
                "BuildCameraLookBaseValuesV1",
                "ApplyCameraLookAuthoredOverridesV1",
                "CommitCameraLookCompositionV1",
                "ComposeCameraLookV1",
            ),
        )
        self.assertEqual(tuple(function["stage"] for function in functions), tuple(range(6)))
        self.assertEqual(tuple(functions[-1]["uses"]), tuple(function["name"] for function in functions[:-1]))

    def test_ownership_preserves_accepted_channels_and_local_comfort_boundary(self):
        ownership = SCHEMA["architecture"]["ownership"]
        self.assertIn("cannot mutate CameraChannel", ownership)
        self.assertIn("body", ownership)
        self.assertIn("gimbal", ownership)
        self.assertIn("local comfort", ownership)
        self.assertIn("never modified or aliased", SCHEMA["contracts"]["integration"])
        self.assertIn("transient local layer", SCHEMA["contracts"]["comfort"])
        self.assertIn("No comfort preference", SCHEMA["contracts"]["comfort"])

    def test_atomic_publication_keeps_values_visible(self):
        architecture = SCHEMA["architecture"]
        self.assertIn("complete base values", architecture["visibility"])
        self.assertIn("complete effective values", architecture["visibility"])
        self.assertIn("publishes validity last", architecture["atomicity"])
        result_names = {variable["name"] for variable in SCHEMA["variables"] if variable["role"] == "result"}
        self.assertEqual(
            result_names,
            {
                "CameraLookResultPresetIdV1", "CameraLookResultChannelIdsV1",
                "CameraLookResultBaseValuesV1", "CameraLookResultValuesV1",
                "CameraLookResultOverrideMaskV1", "CameraLookResultValidV1",
                "CameraLookFailureCodeV1",
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
