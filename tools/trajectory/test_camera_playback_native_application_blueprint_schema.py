from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "camera_playback_native_application_blueprint_schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class CameraPlaybackNativeApplicationBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_dependencies_and_function_order_are_exact(self):
        self.assertEqual(SCHEMA["schema"], "edd.camera-playback-native-application.v1")
        self.assertEqual(SCHEMA["version"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["dependencies"]["playback"], "edd.camera-playback-frame.v1")
        self.assertEqual(SCHEMA["dependencies"]["engineApplication"], "edd.camera-engine-application.v1")
        self.assertEqual(SCHEMA["dependencies"]["cameraComponent"], "DroneCamera")
        self.assertEqual(
            [function["name"] for function in SCHEMA["functions"]],
            [
                "ResetCameraPlaybackNativeApplicationResultV1",
                "StageCameraPlaybackNativeApplicationInputsV1",
                "ValidateCameraPlaybackNativeApplicationInputsV1",
                "CaptureCameraPlaybackNativeStateV1",
                "ApplyCameraPlaybackNativeFrameV1",
                "RestoreCameraPlaybackNativeStateV1",
                "ApplyComposedCameraPlaybackFrameV1",
            ],
        )
        self.assertEqual([function["stage"] for function in SCHEMA["functions"]], list(range(7)))

    def test_variable_shape_and_defaults_are_frozen(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 13)
        self.assertEqual(len({variable["name"] for variable in variables}), 13)
        self.assertEqual(
            [variable["name"] for variable in variables[:5]],
            [
                "CameraPlaybackNativeInputPositionV1",
                "CameraPlaybackNativeInputBodyWorldQuatV1",
                "CameraPlaybackNativeInputGimbalWorldQuatV1",
                "CameraPlaybackNativeInputGimbalRelativeQuatV1",
                "CameraPlaybackNativeInputValidV1",
            ],
        )
        by_name = {variable["name"]: variable for variable in variables}
        self.assertEqual(by_name["CameraPlaybackNativeInputPositionV1"]["type"], "Vector")
        for name in (
            "CameraPlaybackNativeInputBodyWorldQuatV1",
            "CameraPlaybackNativeInputGimbalWorldQuatV1",
            "CameraPlaybackNativeInputGimbalRelativeQuatV1",
        ):
            self.assertEqual(by_name[name]["type"], "Quat")
            self.assertEqual(by_name[name]["default"], [0.0, 0.0, 0.0, 1.0])
        for name in (
            "CameraPlaybackNativeBaselineActorTransformV1",
            "CameraPlaybackNativeBaselineComponentRelativeTransformV1",
        ):
            self.assertEqual(by_name[name]["type"], "Transform")
            self.assertEqual(by_name[name]["default"]["scale"], [1.0, 1.0, 1.0])
        self.assertTrue(all(variable["container"] == "None" for variable in variables))

    def test_body_gimbal_and_world_validation_have_distinct_native_roles(self):
        architecture = SCHEMA["architecture"]
        authorship = architecture["authorship"]
        self.assertIn("BodyWorldQuatV1 is the drone actor world rotation", authorship)
        self.assertIn("GimbalRelativeQuatV1 alone is the Cine Camera component relative rotation", authorship)
        self.assertIn("GimbalWorldQuatV1 is retained only to prove", authorship)
        native = SCHEMA["contracts"]["nativeOwnership"]
        self.assertIn("actor setter receives position plus body", native)
        self.assertIn("component setter receives only the derived relative gimbal", native)

    def test_engine_application_is_reused_without_aliasing_channel_results(self):
        functions = {function["name"]: function for function in SCHEMA["functions"]}
        self.assertEqual(
            functions["ValidateCameraPlaybackNativeApplicationInputsV1"]["uses"],
            ["ValidateCameraEngineApplicationInputsV1"],
        )
        self.assertEqual(
            functions["CaptureCameraPlaybackNativeStateV1"]["uses"],
            ["CaptureCameraEngineStateV1"],
        )
        self.assertEqual(
            functions["ApplyCameraPlaybackNativeFrameV1"]["uses"],
            ["ApplyCameraEngineFrameV1"],
        )
        self.assertEqual(
            functions["RestoreCameraPlaybackNativeStateV1"]["uses"],
            ["RestoreCameraEngineStateV1"],
        )
        self.assertEqual(
            functions["ApplyComposedCameraPlaybackFrameV1"]["uses"],
            [
                "ResetCameraPlaybackNativeApplicationResultV1",
                "ResetCameraEngineApplicationResultV1",
                "StageCameraPlaybackNativeApplicationInputsV1",
                "ValidateCameraPlaybackNativeApplicationInputsV1",
                "CaptureCameraPlaybackNativeStateV1",
                "ApplyCameraPlaybackNativeFrameV1",
            ],
        )
        self.assertIn("CameraApplyInput*", SCHEMA["architecture"]["lens"])
        self.assertNotIn("CameraChannelResult", SCHEMA["architecture"]["lens"])

    def test_preflight_capture_restore_and_failure_contracts_are_explicit(self):
        architecture = SCHEMA["architecture"]
        self.assertIn("before the first actor, component, lens", architecture["preflight"])
        self.assertIn("captured once", architecture["capture"])
        self.assertIn("Repeated capture cannot replace", architecture["capture"])
        self.assertIn("exact actor/component transforms", architecture["restore"])
        self.assertIn("Repeated restore is a no-op", architecture["restore"])
        self.assertIn("zero native writes", architecture["failure"])
        self.assertIn("publishes CameraPlaybackNativeResultValidV1 last", SCHEMA["contracts"]["transaction"])
        self.assertIn("resets both native and engine result authority", SCHEMA["contracts"]["transaction"])

    def test_forbidden_legacy_and_unrelated_ownership_is_explicit(self):
        forbidden = SCHEMA["architecture"]["forbidden"]
        for value in (
            "CinematicPoseResultQuatV1",
            "CameraTransform rotation",
            "CarrierFrameResultQuatV1",
            "persistence",
            "server state",
            "HUD",
            "UI",
            "input dispatch",
        ):
            self.assertIn(value, forbidden)
        self.assertIn("Body and gimbal can never share", forbidden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
