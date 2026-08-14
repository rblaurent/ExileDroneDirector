from __future__ import annotations

import json
import unittest
from pathlib import Path

from camera_base_look_reference import CHANNEL_IDS_V1
from camera_viewer_comfort_reference import COMFORT_WEIGHT_IDS_V1


SCHEMA = json.loads((Path(__file__).with_name("camera_viewer_comfort_blueprint_schema.json")).read_text(encoding="utf-8"))


class CameraViewerComfortBlueprintSchemaContracts(unittest.TestCase):
    def test_asset_channels_and_weights_are_frozen(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(tuple(SCHEMA["limits"]["channelIds"]), CHANNEL_IDS_V1)
        self.assertEqual(tuple(SCHEMA["limits"]["comfortWeightIds"]), COMFORT_WEIGHT_IDS_V1)
        self.assertEqual(SCHEMA["limits"]["channelCount"], 13)
        self.assertEqual(tuple(SCHEMA["limits"]["comfortSensitiveChannelIds"]),
                         ("focus_influence", "exposure_ev", "motion_blur_weight", "chromatic_aberration_weight"))

    def test_variables_are_typed_unique_and_comfort_owned(self):
        variables = SCHEMA["variables"]
        names = tuple(variable["name"] for variable in variables)
        self.assertEqual(len(names), 28)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name.startswith("CameraComfort") for name in names))
        self.assertTrue(all(variable["type"] in {"Boolean", "Vector", "Quat", "Float", "String", "Integer"} for variable in variables))
        roles = {role: {variable["name"] for variable in variables if variable["role"] == role}
                 for role in {variable["role"] for variable in variables}}
        for left in roles:
            for right in roles:
                if left != right:
                    self.assertTrue(roles[left].isdisjoint(roles[right]))

    def test_functions_freeze_the_transaction_order(self):
        functions = SCHEMA["functions"]
        self.assertEqual(tuple(function["name"] for function in functions), (
            "ResetCameraViewerComfortV1", "ValidateCameraViewerComfortInputsV1",
            "BuildCameraViewerComfortMotionV1", "BuildCameraViewerComfortChannelsV1",
            "CommitCameraViewerComfortV1", "ApplyCameraViewerComfortV1",
        ))
        self.assertEqual(tuple(function["stage"] for function in functions), tuple(range(6)))
        self.assertEqual(tuple(functions[-1]["uses"]), tuple(function["name"] for function in functions[:-1]))

    def test_locality_and_distinct_authorship_are_explicit(self):
        architecture = SCHEMA["architecture"]
        self.assertIn("transient and local", architecture["locality"])
        for forbidden in ("Flypath document", "repository record", "published revision", "server state", "authored track"):
            self.assertIn(forbidden, architecture["locality"])
        self.assertIn("already distinct evaluated gimbal quaternion", architecture["authorship"])
        self.assertIn("never accepts, manufactures, aliases, or writes a body track", architecture["authorship"])
        self.assertIn("local final-view result only", architecture["authorship"])
        self.assertIn("Airframe", SCHEMA["contracts"]["ownership"])
        self.assertIn("authored/compiled gimbal", SCHEMA["contracts"]["ownership"])

    def test_disabled_failure_and_atomic_result_contracts_are_visible(self):
        contracts = SCHEMA["contracts"]
        self.assertIn("still validates every source and preference", contracts["disabled"])
        self.assertIn("[1,1,1,1,1]", contracts["disabled"])
        self.assertIn("prior local result pose", contracts["failure"])
        self.assertIn("publishing result validity false", contracts["failure"])
        self.assertIn("publishes validity last", SCHEMA["architecture"]["atomicity"])
        result_names = {variable["name"] for variable in SCHEMA["variables"] if variable["role"] == "result"}
        self.assertEqual(result_names, {
            "CameraComfortResultPositionV1", "CameraComfortResultGimbalQuatV1",
            "CameraComfortResultChannelValuesV1", "CameraComfortResultEffectiveWeightsV1",
            "CameraComfortResultAppliedV1", "CameraComfortResultValidV1", "CameraComfortFailureCodeV1",
        })


if __name__ == "__main__":
    unittest.main(verbosity=2)
