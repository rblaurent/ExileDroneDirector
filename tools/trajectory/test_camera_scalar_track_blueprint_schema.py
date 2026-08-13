"""Freeze the Blueprint-safe common camera scalar-track ABI."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


SCHEMA = json.loads((Path(__file__).with_name("camera_scalar_track_blueprint_schema.json")).read_text(encoding="utf-8"))


class CameraScalarTrackBlueprintSchemaContracts(unittest.TestCase):
    def test_asset_limits_domains_and_presets_are_exact(self):
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["limits"], {
            "minimumKeys": 1,
            "maximumKeys": 512,
            "domains": ["linear", "reciprocal"],
            "interpolationModes": ["hold", "linear", "smooth", "cinematic", "hermite"],
        })

    def test_variable_order_types_and_ownership_are_fixed(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 32)
        self.assertEqual([item["name"] for item in variables[:12]], [
            "CameraScalarTrackInputDurationV1", "CameraScalarTrackInputKeyTimesV1",
            "CameraScalarTrackInputKeyValuesV1", "CameraScalarTrackInputInterpolationModesV1",
            "CameraScalarTrackInputArriveTangentsV1", "CameraScalarTrackInputLeaveTangentsV1",
            "CameraScalarTrackInputDomainV1", "CameraScalarTrackInputHasMinimumV1",
            "CameraScalarTrackInputMinimumV1", "CameraScalarTrackInputHasMaximumV1",
            "CameraScalarTrackInputMaximumV1", "CameraScalarTrackInputClampOutputV1",
        ])
        allowed = {"Float", "Integer", "Boolean", "String"}
        self.assertTrue(all(item["type"] in allowed for item in variables))
        self.assertTrue(all(item["container"] in {"None", "Array"} for item in variables))
        self.assertEqual(sum(item["role"] == "candidate" for item in variables), 5)
        self.assertEqual(sum(item["role"] == "query" for item in variables), 1)

    def test_functions_and_orchestration_are_exact(self):
        functions = SCHEMA["functions"]
        self.assertEqual([item["stage"] for item in functions], list(range(9)))
        self.assertEqual([item["name"] for item in functions], [
            "ResetCameraScalarTrackCompileV1", "ValidateCameraScalarTrackInputsV1",
            "BuildCameraScalarTrackCandidatesV1", "CommitCameraScalarTrackV1",
            "CompileCameraScalarTrackV1", "ResetCameraScalarTrackResultV1",
            "PublishCameraScalarTrackSampleV1", "EvaluateCameraScalarTrackSegmentV1",
            "EvaluateCameraScalarTrackV1",
        ])
        self.assertEqual(functions[4]["uses"], [
            "ResetCameraScalarTrackCompileV1", "ValidateCameraScalarTrackInputsV1",
            "BuildCameraScalarTrackCandidatesV1", "CommitCameraScalarTrackV1",
        ])
        self.assertEqual(functions[7]["uses"], [
            "EvaluateTimeProfileV1", "EvaluateQuinticScalarV1", "PublishCameraScalarTrackSampleV1",
        ])
        self.assertEqual(functions[8]["uses"], [
            "ResetCameraScalarTrackResultV1", "EvaluateCameraScalarTrackSegmentV1",
            "PublishCameraScalarTrackSampleV1",
        ])

    def test_optical_domain_and_bounds_are_explicit(self):
        architecture = SCHEMA["architecture"]
        self.assertIn("inverse-centimetre", architecture["domains"])
        self.assertIn("zero derivatives", architecture["bounds"])
        self.assertIn("no per-frame recompilation", architecture["ownership"])
        contracts = SCHEMA["contracts"]
        self.assertIn("strictly positive", contracts["domain"])
        self.assertIn("finite-representable", contracts["domain"])
        self.assertIn("silently hiding", contracts["tangents"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
