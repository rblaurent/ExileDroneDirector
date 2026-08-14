"""Schema and ownership contracts for the camera DOF diagnostic helper."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


SCHEMA = json.loads((Path(__file__).with_name("camera_dof_diagnostics_blueprint_schema.json")).read_text(encoding="utf-8"))


class CameraDofDiagnosticSchemaContracts(unittest.TestCase):
    def test_asset_constants_and_function_order_are_frozen(self):
        self.assertEqual(SCHEMA["schema"], "edd.camera-dof-diagnostics.v1")
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["constants"], {
            "channelCount": 13,
            "focalLengthIndex": 0,
            "apertureIndex": 1,
            "focusDistanceIndex": 2,
            "circleOfConfusionDiagonalDivisor": 1500.0,
            "unboundedFarSentinelCm": 0.0,
        })
        self.assertEqual([item["name"] for item in SCHEMA["functions"]], [
            "ResetCameraDofDiagnosticsV1",
            "StageEvaluatedCameraDofFrameV1",
            "ComputeCameraDofDiagnosticsV1",
            "EvaluateCameraDofDiagnosticsV1",
        ])

    def test_variables_are_exact_scalar_diagnostic_ownership(self):
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 18)
        self.assertTrue(all(item["container"] == "None" for item in variables))
        self.assertTrue(all(item["type"] in {"Float", "Boolean", "String"} for item in variables))
        self.assertEqual(sum(item["role"] == "stage" for item in variables), 6)
        self.assertEqual(sum(item["role"] == "result" for item in variables), 12)
        self.assertEqual(variables[-1]["name"], "CameraDofResultValidV1")

    def test_stage_reads_only_the_complete_evaluated_camera_frame(self):
        stage = SCHEMA["functions"][1]
        self.assertEqual(stage["reads"], [
            "CameraChannelResultValidV1",
            "CameraChannelResultFilmbackSensorWidthMmV1",
            "CameraChannelResultFilmbackSensorHeightMmV1",
            "CameraChannelResultValuesV1",
        ])
        encoded = json.dumps(SCHEMA)
        for forbidden in ("CameraTransform", "CameraApply", "CameraFocusMarker", "Airframe", "Document"):
            self.assertNotIn(forbidden, encoded)

    def test_unbounded_far_and_atomicity_are_explicit(self):
        self.assertIn("FarUnbounded", json.dumps(SCHEMA["variables"]))
        self.assertIn("Infinity", SCHEMA["invariants"]["unbounded"])
        self.assertIn("validity last", SCHEMA["invariants"]["atomicity"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
