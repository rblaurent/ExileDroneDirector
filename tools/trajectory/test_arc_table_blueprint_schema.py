"""Contracts for the staged Blueprint arc-table inversion boundary."""
from __future__ import annotations

import json
import unittest
from pathlib import Path


SCHEMA = json.loads((Path(__file__).with_name("arc_table_blueprint_schema.json")).read_text(encoding="utf-8"))


class ArcTableBlueprintSchemaContracts(unittest.TestCase):
    def test_surface_is_exact_and_versioned(self):
        self.assertEqual(SCHEMA["functions"], ["InvertArcLengthTableV1"])
        self.assertEqual(
            [item["name"] for item in SCHEMA["variables"]],
            [
                "TrajectoryArcInputUsV1", "TrajectoryArcInputDistancesV1",
                "TrajectoryArcInputLengthV1", "TrajectoryArcInputDistanceAlphaV1",
                "TrajectoryArcResultUV1", "TrajectoryArcResultValidV1",
                "TrajectoryArcScratchUpperIndexV1", "TrajectoryArcScratchValidV1",
            ],
        )

    def test_arrays_and_fail_closed_defaults_are_fixed(self):
        variables = {item["name"]: item for item in SCHEMA["variables"]}
        self.assertEqual(variables["TrajectoryArcInputUsV1"]["container"], "Array")
        self.assertEqual(variables["TrajectoryArcInputDistancesV1"]["container"], "Array")
        self.assertEqual(variables["TrajectoryArcScratchUpperIndexV1"]["default"], -1)
        self.assertFalse(variables["TrajectoryArcResultValidV1"]["default"])
        self.assertFalse(variables["TrajectoryArcScratchValidV1"]["default"])

    def test_only_proven_blueprint_kinds_are_used(self):
        self.assertEqual({item["type"] for item in SCHEMA["variables"]}, {"Float", "Boolean", "Integer"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
