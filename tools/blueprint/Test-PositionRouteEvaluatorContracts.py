"""Exact structural contracts for compiled absolute-time position evaluation."""
from __future__ import annotations
import argparse, importlib.util, sys
from pathlib import Path

RESULTS=("PositionRouteResultSegmentIndexV1","PositionRouteResultLocalTimeAlphaV1","PositionRouteResultDistanceAlphaV1","PositionRouteResultCurveUV1","PositionRouteResultPositionV1","PositionRouteResultCompleteV1","PositionRouteResultValidV1")

def load(root):
    path=root/"tools/blueprint/Test-WaypointCaptureContracts.py";spec=importlib.util.spec_from_file_location("edd_position_eval_contract",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);nodes=c.parse_graph(a.graph);c.require(len(nodes)==(236 if a.paste else 237),f"node count {len(nodes)}")
    entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    def all_(member):return [n for n in nodes.values() if f'MemberName="{member}"' in n.text]
    def one(member):values=all_(member);c.require(len(values)==1,f"one {member}:{len(values)}");return values[0]
    def setters(name):return [n for n in all_(name) if "VariableSet" in n.node_class]
    def authored(node,pin):
        body=node.pins[pin].body
        marker='DefaultValue="'
        return body.split(marker,1)[1].split('"',1)[0] if marker in body else None

    expected_counts=(10,10,10,11,11,11,11)
    c.require(tuple(len(setters(name)) for name in RESULTS)==expected_counts,"result write counts")
    defaults=("-1","0.0","0.0","0.0",None,"false","false")
    resets=[]
    for name,default in zip(RESULTS,defaults):
        candidates=[n for n in setters(name) if default is None or authored(n,name)==default];c.require(candidates,f"reset {name}");resets.append(candidates[0])
    if a.paste:c.require(not resets[0].pins["execute"].links,"paste reset root")
    else:c.require(c.linked(entries[0],"then",resets[0],"execute"),"entry reset seam")
    for left,right in zip(resets,resets[1:]):c.require(c.linked(left,"then",right,"execute"),"result reset order")
    primitive_resets=[]
    for name in ("TrajectoryResultValidV1","TrajectoryArcResultValidV1","TrajectoryResultVectorValidV1"):
        values=[n for n in setters(name) if authored(n,name)=="false"];c.require(len(values)==8,f"entry plus seven failure primitive resets {name}");primitive_resets.append(values)
    initial=[n for n in primitive_resets[0] if c.linked(resets[-1],"then",n,"execute")];c.require(len(initial)==1,"primitive reset begins after public reset")
    initial_arc=[n for n in primitive_resets[1] if c.linked(initial[0],"then",n,"execute")];c.require(len(initial_arc)==1,"initial arc reset order")
    initial_vector=[n for n in primitive_resets[2] if c.linked(initial_arc[0],"then",n,"execute")];c.require(len(initial_vector)==1,"initial vector reset order")
    primitive_reset_chain=(initial[0],initial_arc[0],initial_vector[0])

    arrays=("PositionRouteCompiledWaypointPositionsV1","PositionRouteCompiledDurationsV1","PositionRouteCompiledSpatialCurveTypesV1","PositionRouteCompiledTimeProfilesV1","PositionRouteCompiledWaypointVelocitiesV1","PositionRouteCompiledSegmentStartsV1","PositionRouteCompiledArcSampleStartsV1","PositionRouteCompiledArcSampleCountsV1","PositionRouteCompiledArcUsV1","PositionRouteCompiledArcDistancesV1","PositionRouteCompiledSegmentLengthsV1")
    for name in arrays:c.require(len([n for n in all_(name) if "VariableGet" in n.node_class])==1,f"one array source {name}")
    c.require(len(all_("Array_Length"))==11,"all compiled cardinalities measured")
    c.require(len([n for n in nodes.values() if "K2Node_GetArrayItem" in n.node_class])==10,"ten bounded selected reads")
    c.require(len([n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class])==1,"one bounded segment scan")
    c.require(len(all_("EvaluateTimeProfileV1"))==1,"one time-profile call")
    clamps=[n for n in nodes.values() if "K2Node_CallFunction" in n.node_class and 'MemberName="FClamp"' in n.text]
    c.require(len(clamps)==2,"elapsed and profiled-distance clamps")
    distance_source=one("TrajectoryResultValueV1");distance_setters=setters("PositionRouteResultDistanceAlphaV1")
    distance_clamp=[n for n in clamps if c.linked(distance_source,"TrajectoryResultValueV1",n,"Value")]
    c.require(len(distance_clamp)==1,"profiled distance feeds clamp")
    c.require(any(c.linked(distance_clamp[0],"ReturnValue",n,"PositionRouteResultDistanceAlphaV1") for n in distance_setters),"clamped distance is published")
    c.require(len(all_("StagePositionRouteArcSliceV1"))==1,"one slice adapter call")
    c.require(len(all_("InvertArcLengthTableV1"))==1,"one inversion call")
    c.require(len(all_("EvaluateQuinticVectorV1"))==1,"one nonlinear vector call")
    for name in ("TrajectoryInputProfileV1","TrajectoryInputStartPositionVectorV1","TrajectoryInputStartVelocityUVectorV1","TrajectoryInputStartAccelerationUVectorV1","TrajectoryInputEndPositionVectorV1","TrajectoryInputEndVelocityUVectorV1","TrajectoryInputEndAccelerationUVectorV1"):
        c.require(len(setters(name))==1,f"one staged primitive input {name}")
    c.require(len(setters("TrajectoryInputAlphaV1"))==2,"time and spatial alpha staged separately")

    c.require(len(all_("Add_IntInt"))==2 and len(all_("Subtract_IntInt"))==1,"bounded index arithmetic")
    c.require(len(all_("Add_DoubleDouble"))==1 and len(all_("Subtract_DoubleDouble"))==1 and len(all_("Divide_DoubleDouble"))==1,"absolute-time arithmetic")
    c.require(len(all_("Subtract_VectorVector"))==1 and len(all_("Add_VectorVector"))==1 and len(all_("Multiply_VectorVector"))==3,"linear interpolation and time-domain tangent scaling")
    c.require(len(all_("EqualEqual_StrStr"))==2,"only supported spatial modes")
    branches=[n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class];c.require(len(branches)==12,"preflight/complete/scan/select/helper/spatial guards")
    scan_writes=setters("TrajectoryArcScratchValidV1");c.require(len(scan_writes)==2,"sticky duration scan writes")
    c.require(sorted(authored(n,"TrajectoryArcScratchValidV1") for n in scan_writes)==["false","true"],"duration scan initializes true and only invalidates")

    # Every failure after provisional selection ends in a full seven-field clear.
    fail_segment=[n for n in setters(RESULTS[0]) if authored(n,RESULTS[0])=="-1"]
    c.require(len(fail_segment)==8,"entry plus seven post-selection fail roots")
    for first in fail_segment:
        current=first
        for name in RESULTS[1:]:
            candidates=[n for n in setters(name) if c.linked(current,"then",n,"execute")];c.require(len(candidates)==1,f"failure/reset chain {current.name}->{name}");current=candidates[0]
        for name,values in zip(("TrajectoryResultValidV1","TrajectoryArcResultValidV1","TrajectoryResultVectorValidV1"),primitive_resets):
            candidates=[n for n in values if c.linked(current,"then",n,"execute")];c.require(len(candidates)==1,f"failure primitive clear {current.name}->{name}");current=candidates[0]
    # Exactly two active accepts and one terminal accept set validity true.
    true_valid=[n for n in setters("PositionRouteResultValidV1") if authored(n,"PositionRouteResultValidV1")=="true"]
    c.require(len(true_valid)==3,"terminal, linear, nonlinear acceptance")
    known=set(nodes);external={target for n in nodes.values() for pin in n.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external links {external}")
    print(f"Position route evaluator contracts passed ({'paste' if a.paste else 'full'}): {len(nodes)} nodes")

if __name__=="__main__":main()
