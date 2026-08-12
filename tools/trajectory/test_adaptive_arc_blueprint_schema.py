from __future__ import annotations
import json, unittest
from pathlib import Path

S=json.loads((Path(__file__).with_name("adaptive_arc_blueprint_schema.json")).read_text(encoding="utf-8"))

class AdaptiveArcSchemaContracts(unittest.TestCase):
    def test_limits_are_bounded_for_blueprint_v1(self):
        self.assertEqual(S["limits"],{
            "minimumDepth":1,"maximumDepth":12,"minimumOperations":1,
            "maximumOperations":8191,"minimumToleranceExclusive":0.0,
        })
    def test_transaction_roles_and_defaults_are_explicit(self):
        variables={v["name"]:v for v in S["variables"]}
        self.assertEqual(len(variables),32)
        self.assertEqual(sum(v["role"]=="input" for v in variables.values()),10)
        self.assertEqual(sum(v["role"]=="work" for v in variables.values()),5)
        self.assertEqual(sum(v["role"]=="scratch" for v in variables.values()),8)
        self.assertEqual(sum(v["role"]=="candidate" for v in variables.values()),5)
        self.assertEqual(sum(v["role"]=="result" for v in variables.values()),4)
        self.assertEqual(variables["TrajectoryArcBuildInputToleranceV1"]["default"],.01)
        self.assertEqual(variables["TrajectoryArcBuildInputMaxDepthV1"]["default"],12)
        self.assertEqual(variables["TrajectoryArcBuildInputMaxOperationsV1"]["default"],8191)
        self.assertFalse(variables["TrajectoryArcBuildValidV1"]["default"])
        self.assertEqual(variables["TrajectoryArcBuildWorkP0V1"]["container"],"Array")
        self.assertEqual(variables["TrajectoryArcBuildCandidatePositionsV1"]["type"],"Vector")
    def test_ordered_modular_surface_is_fixed(self):
        self.assertEqual([f["name"] for f in S["functions"]],[
            "ResetAdaptiveArcBuildV1","ValidateAdaptiveArcBuildInputsV1",
            "InitializeAdaptiveArcBuildV1","ProcessAdaptiveArcBuildV1",
            "CommitAdaptiveArcBuildV1","BuildAdaptiveArcTableV1",
        ])
        self.assertEqual(S["functions"][1]["uses"],["EvaluateQuinticVectorV1"])
        self.assertEqual(S["functions"][3]["uses"],["EvaluateQuinticVectorV1"])
        self.assertIn("Only CommitAdaptiveArcBuildV1",S["contracts"]["atomicity"])
        self.assertIn("right then left",S["contracts"]["ordering"])

if __name__ == "__main__": unittest.main(verbosity=2)
