"""Freeze the staged Blueprint seam for multi-segment position routes."""
from __future__ import annotations
import json, random, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
S=json.loads((ROOT/"tools/trajectory/position_route_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0,str(ROOT/"tools"/"trajectory"))
from cinematic_reference import AuthoredSegment,compile_trajectory,evaluate_position

class PositionRouteBlueprintSchemaContracts(unittest.TestCase):
    def test_identity_limits_and_supported_types_are_explicit(self):
        self.assertEqual(S["schemaVersion"],1);self.assertEqual(S["asset"],"Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(S["limits"]["minimumWaypoints"],2);self.assertEqual(S["limits"]["maximumWaypoints"],512)
        self.assertEqual((S["limits"]["minimumArcDepth"],S["limits"]["maximumArcDepth"]),(1,12))
        self.assertEqual((S["limits"]["minimumArcOperations"],S["limits"]["maximumArcOperations"]),(1,8191))
        variables=S["variables"];names=[v["name"] for v in variables];self.assertEqual(len(names),len(set(names)))
        self.assertTrue(all(v["type"] in {"Vector","Float","Integer","Boolean","String"} for v in variables))
        self.assertTrue(all(v["container"] in {"None","Array"} for v in variables))
    def test_candidate_compiled_and_evaluation_channels_are_disjoint(self):
        by_role={role:{v["name"] for v in S["variables"] if v["role"]==role} for role in ("input","candidate","result","evaluationInput","evaluationResult")}
        for index,left in enumerate(by_role.values()):
            for right in list(by_role.values())[index+1:]:self.assertTrue(left.isdisjoint(right))
        self.assertEqual(len(by_role["candidate"]),11);self.assertEqual(len(by_role["result"]),14);self.assertEqual(len(by_role["evaluationResult"]),7)
    def test_flat_arc_layout_and_stage_dependencies_are_exact(self):
        names={v["name"] for v in S["variables"]}
        for prefix in ("Candidate","Compiled"):
            for suffix in ("ArcSampleStartsV1","ArcSampleCountsV1","ArcUsV1","ArcDistancesV1"):
                self.assertIn(f"PositionRoute{prefix}{suffix}",names)
        functions=S["functions"];self.assertEqual([f["stage"] for f in functions],list(range(8)))
        by_name={f["name"]:f for f in functions}
        self.assertEqual(by_name["BuildPositionRouteSegmentsV1"]["uses"],["BuildAdaptiveArcTableV1"])
        self.assertEqual(by_name["EvaluateCompiledPositionRouteV1"]["uses"],["EvaluateTimeProfileV1","StagePositionRouteArcSliceV1","InvertArcLengthTableV1","EvaluateQuinticVectorV1"])
    def test_contracts_require_atomic_absolute_time_and_flat_slices(self):
        contracts=" ".join(S["contracts"].values()).lower()
        for required in ("only commitcompiledpositionroutev1","contiguous slice","clears every","absolute elapsed","never integrates"):
            self.assertIn(required,contracts)
    def test_flattened_oracle_tables_round_trip_segment_boundaries(self):
        rng=random.Random(0xEDD071)
        for _ in range(50):
            points=[];current=[0.,0.,0.]
            for _point in range(rng.randint(2,10)):
                current=[value+rng.uniform(-250,250) for value in current];points.append(tuple(current))
            authored=tuple(AuthoredSegment(rng.uniform(.05,8),"linear" if i%4==0 else "auto_cinematic",("linear","smoothstep","smootherstep","cinematic_s_curve","accelerate_through","brake_into")[i%6]) for i in range(len(points)-1))
            compiled=compile_trajectory(tuple(points),authored,arc_tolerance=.01,max_arc_depth=12)
            starts=[];counts=[];us=[];distances=[]
            for segment in compiled.segments:
                starts.append(len(us));counts.append(len(segment.arc_table));us.extend(sample.u for sample in segment.arc_table);distances.extend(sample.distance for sample in segment.arc_table)
            self.assertEqual(starts,[sum(counts[:i]) for i in range(len(counts))])
            for i,segment in enumerate(compiled.segments):
                begin=starts[i];end=begin+counts[i];self.assertEqual(tuple(us[begin:end]),tuple(s.u for s in segment.arc_table));self.assertEqual(tuple(distances[begin:end]),tuple(s.distance for s in segment.arc_table))
            query=compiled.total_seconds*rng.random();self.assertEqual(evaluate_position(compiled,query),evaluate_position(compiled,query))

if __name__=="__main__":unittest.main(verbosity=2)
