"""Frozen Blueprint ownership contract for dolly-zoom authoring."""
import json
import unittest
from pathlib import Path


SCHEMA = json.loads(Path(__file__).with_name("camera_dolly_zoom_blueprint_schema.json").read_text(encoding="utf-8"))


class CameraDollyZoomSchemaContracts(unittest.TestCase):
    def test_asset_constants_and_function_order_are_exact(self) -> None:
        self.assertEqual(SCHEMA["asset"], "Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(SCHEMA["constants"], {"minimumSamples":2,"maximumSamples":65536,"minimumSubjectDistanceCm":1.0,"minimumFocalLengthMm":1.0,"maximumFocalLengthMm":1000.0})
        self.assertEqual([value["name"] for value in SCHEMA["functions"]], ["ResetCameraDollyZoomV1","ValidateCameraDollyZoomInputsV1","BuildCameraDollyZoomCandidatesV1","CommitCameraDollyZoomV1","CompileCameraDollyZoomV1"])

    def test_variables_are_exact_and_disjoint(self) -> None:
        values = SCHEMA["variables"]
        self.assertEqual(len(values), 15)
        self.assertEqual(len({value["name"] for value in values}), 15)
        self.assertEqual({value["role"] for value in values}, {"input", "validation", "candidate", "compiled", "result"})
        self.assertTrue(all(value["container"] in {"None", "Array"} for value in values))

    def test_authorship_and_atomicity_forbid_aliases(self) -> None:
        text = " ".join(SCHEMA["invariants"].values()).lower()
        for token in ("does not author orientation", "cannot write position", "body", "gimbal", "compiled camera-channel", "preserving the prior compiled", "validity last"):
            self.assertIn(token, text)
        self.assertIn("clamping is forbidden", text)

    def test_only_focal_authoring_results_are_published(self) -> None:
        names = {value["name"] for value in SCHEMA["variables"]}
        self.assertIn("CameraDollyCompiledFocalLengthsMmV1", names)
        self.assertFalse(any("Rotation" in name or "Transform" in name or "Body" in name or "Gimbal" in name for name in names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
