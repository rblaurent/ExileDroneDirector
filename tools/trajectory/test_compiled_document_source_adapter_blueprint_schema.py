"""Schema contracts for the lossless v2 document-to-source adapter."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/compiled_document_source_adapter_blueprint_schema.json").read_text(encoding="utf-8"))


class CompiledDocumentSourceAdapterBlueprintSchemaContracts(unittest.TestCase):
    def test_boundary_is_explicitly_v2_and_forbids_single_rotation_fallback(self):
        architecture = SCHEMA["architecture"]
        self.assertEqual(SCHEMA["schemaVersion"], 2)
        self.assertIn("Parallel typed v2 arrays", architecture["boundary"])
        self.assertIn("CameraTransform", architecture["legacyMismatch"])
        self.assertIn("forbidden", architecture["legacyMismatch"])
        self.assertIn("bodyRotation", architecture["migration"])
        self.assertIn("gimbalRotation", architecture["migration"])

    def test_inputs_preserve_two_complete_authorship_channels(self):
        variables = {item["name"]: item for item in SCHEMA["variables"]}
        expected = {
            "AirframeDocumentInputWaypointBodyQuatsV2": ("Quat", "Array"),
            "AirframeDocumentInputWaypointGimbalQuatsV2": ("Quat", "Array"),
            "AirframeDocumentInputWaypointPositionsV2": ("Vector", "Array"),
            "AirframeDocumentInputWaypointIdsV2": ("Integer", "Array"),
        }
        for name, pair in expected.items():
            self.assertEqual((variables[name]["type"], variables[name]["container"]), pair)
        self.assertNotEqual(expected["AirframeDocumentInputWaypointBodyQuatsV2"], ("Transform", "Array"))
        self.assertFalse(any("CameraTransform" in item["name"] for item in variables.values()))

    def test_segment_shape_and_accepted_output_mapping_are_complete(self):
        variables = {item["name"] for item in SCHEMA["variables"]}
        segment_inputs = {
            "AirframeDocumentInputSegmentIdsV2",
            "AirframeDocumentInputSegmentFromWaypointIdsV2",
            "AirframeDocumentInputSegmentToWaypointIdsV2",
            "AirframeDocumentInputSegmentDurationsV2",
            "AirframeDocumentInputSegmentSpatialCurveTypesV2",
            "AirframeDocumentInputSegmentTimeProfilesV2",
            "AirframeDocumentInputSegmentFlightProfileOverridesV2",
        }
        self.assertTrue(segment_inputs <= variables)
        self.assertEqual(len(SCHEMA["existingOutputs"]), 9)
        self.assertIn("AirframeSourceInputBodyWaypointQuatsV1", SCHEMA["existingOutputs"])
        self.assertIn("AirframeSourceInputGimbalWaypointQuatsV1", SCHEMA["existingOutputs"])

    def test_functions_freeze_adapter_then_diagnostics_order(self):
        functions = SCHEMA["functions"]
        self.assertEqual([item["stage"] for item in functions], list(range(5)))
        self.assertEqual(
            [item["name"] for item in functions],
            [
                "ResetAirframeDocumentSourceAdapterV2",
                "ValidateAirframeDocumentSourceAdapterV2",
                "CommitAirframeDocumentSourceAdapterV2",
                "BuildAirframeDocumentDiscontinuityDiagnosticsV2",
                "CompileAirframeDocumentSourceAdapterV2",
            ],
        )
        self.assertEqual(functions[-1]["uses"], [item["name"] for item in functions[:-1]])

    def test_diagnostics_are_separate_non_authoritative_state(self):
        variables = SCHEMA["variables"]
        diagnostic = [item for item in variables if item["role"].startswith("diagnostic")]
        self.assertEqual(len(diagnostic), 11)
        self.assertIn("never mutate", SCHEMA["architecture"]["diagnostics"])
        self.assertIn("cannot modify adapter/source/desired/prebake", SCHEMA["contracts"]["diagnostics"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
