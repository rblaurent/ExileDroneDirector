"""Frozen Blueprint ABI contracts for the camera-channel assembly."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


SCHEMA_PATH = Path(__file__).with_name("camera_channel_assembly_blueprint_schema.json")


class CameraChannelAssemblyBlueprintSchemaContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_fixed_canonical_channels_and_policies_are_frozen(self):
        limits = self.schema["limits"]
        self.assertEqual(limits["channelCount"], 13)
        self.assertEqual(len(limits["channelIds"]), 13)
        self.assertEqual(limits["channelIds"][:5], [
            "focal_length_mm", "aperture_fstop", "focus_distance_cm",
            "focus_influence", "exposure_ev",
        ])
        self.assertEqual(limits["channelIds"][5:], [
            "bloom_weight", "vignette_weight", "color_grading_weight",
            "tint_weight", "motion_blur_weight", "chromatic_aberration_weight",
            "sharpening_weight", "matte_weight",
        ])
        self.assertIn("Only focus distance permits reciprocal", self.schema["contracts"]["policies"])

    def test_variable_names_are_unique_and_storage_layers_are_distinct(self):
        variables = self.schema["variables"]
        names = [item["name"] for item in variables]
        self.assertEqual(len(names), len(set(names)))
        for stem in ("KeyOffsets", "KeyCounts", "KeyTimes", "Domains"):
            self.assertIn(f"CameraChannelInput{stem}V1", names)
            self.assertIn(f"CameraChannelCandidate{stem}V1", names)
            self.assertIn(f"CameraChannelCompiled{stem}V1", names)
        self.assertIn("CameraChannelResultValuesV1", names)
        self.assertIn("CameraChannelResultVelocitiesV1", names)
        self.assertIn("CameraChannelResultAccelerationsV1", names)

    def test_graph_order_and_dependencies_are_exact(self):
        functions = self.schema["functions"]
        self.assertEqual([item["stage"] for item in functions], list(range(9)))
        self.assertEqual([item["name"] for item in functions], [
            "ResetCameraChannelCompileV1", "ValidateCameraChannelInputsV1",
            "CompileCameraChannelCandidateV1", "CommitCameraChannelAssemblyV1",
            "CompileCameraChannelAssemblyV1", "ResetCameraChannelResultV1",
            "StageCompiledCameraChannelV1", "PublishCameraChannelSampleV1",
            "EvaluateCameraChannelAssemblyV1",
        ])
        by_name = {item["name"]: item for item in functions}
        self.assertEqual(by_name["CompileCameraChannelCandidateV1"]["uses"], ["CompileCameraScalarTrackV1"])
        self.assertEqual(by_name["PublishCameraChannelSampleV1"]["uses"], ["EvaluateCameraScalarTrackV1"])
        self.assertNotIn("CompileCameraScalarTrackV1", by_name["EvaluateCameraChannelAssemblyV1"]["uses"])

    def test_contract_forbids_aliasing_and_per_frame_compilation(self):
        contracts = self.schema["contracts"]
        self.assertIn("disjoint offset/count slice", contracts["ownership"])
        self.assertIn("never alias", contracts["ownership"])
        self.assertIn("without compiling", contracts["evaluation"])
        self.assertIn("preserves the prior compiled bank", contracts["atomicity"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

