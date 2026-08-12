"""Exact structural contracts for absolute-time compiled orientation evaluation."""
from __future__ import annotations
import argparse, importlib.util, sys
from pathlib import Path

def load(root):
    p=root/"tools/blueprint/Test-WaypointCaptureContracts.py";s=importlib.util.spec_from_file_location("edd_orientation_eval_contract",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);n=c.parse_graph(a.graph);c.require(len(n)==(112 if a.paste else 113),f"node count {len(n)}")
    entries=[x for x in n.values() if "K2Node_FunctionEntry" in x.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    def all_(member):return [x for x in n.values() if f'MemberName="{member}"' in x.text]
    def one(member):values=all_(member);c.require(len(values)==1,f"one {member}:{len(values)}");return values[0]
    # Reset-before-guard is the stale-result boundary.
    results=("OrientationTrackResultSegmentIndexV1","OrientationTrackResultAlphaV1","OrientationTrackResultQuatV1","OrientationTrackResultCompleteV1","OrientationTrackResultValidV1")
    setters={name:[x for x in all_(name) if "VariableSet" in x.node_class] for name in results}
    c.require([len(setters[x]) for x in results]==[6,6,6,6,6],"reset, active/complete success, and three fail-closed writes")
    resets=[]
    defaults=("-1","0.0",None,"false","false")
    for name,default in zip(results,defaults):
        matches=[x for x in setters[name] if default is None or f'DefaultValue="{default}"' in x.pins[name].body];c.require(matches,f"reset {name}");resets.append(matches[0])
    if a.paste:c.require(not resets[0].pins["execute"].links,"paste root")
    else:c.require(c.linked(entries[0],"then",resets[0],"execute"),"entry reset seam")
    for left,right in zip(resets,resets[1:]):c.require(c.linked(left,"then",right,"execute"),"reset chain")
    # Complete compiled shape and finite elapsed/total gates.
    arrays=("OrientationTrackCompiledDurationsV1","OrientationTrackCompiledSegmentStartsV1","OrientationTrackCompiledStartControlsV1","OrientationTrackCompiledEndControlsV1","OrientationTrackCompiledAlignedQuatsV1","OrientationTrackCompiledTangentRatesV1")
    for name in arrays:c.require(len(all_(name))==1,f"one array source {name}")
    c.require(len(all_("Array_Length"))==6,"six array lengths");c.require(len(all_("EqualEqual_IntInt"))==6,"cardinality and selection equalities");c.require(len(all_("BooleanAND"))==15,"all guard conjunctions")
    c.require(len(all_("Greater_IntInt"))==1,"nonempty durations");c.require(len(all_("GreaterEqual_IntInt"))==1,"found index")
    c.require(len(all_("GreaterEqual_DoubleDouble"))==4,"finite lowers plus completion");c.require(len(all_("LessEqual_DoubleDouble"))==3,"finite uppers");c.require(len(all_("Greater_DoubleDouble"))==2,"positive total and selected duration");c.require(len(all_("Less_DoubleDouble"))==1,"first containing segment")
    c.require(len(all_("Add_IntInt"))==2 and len(all_("Subtract_IntInt"))==1,"index arithmetic");c.require(len(all_("Add_DoubleDouble"))==1 and len(all_("Subtract_DoubleDouble"))==1 and len(all_("Divide_DoubleDouble"))==1,"absolute-time alpha arithmetic")
    loops=[x for x in n.values() if "K2Node_MacroInstance" in x.node_class];c.require(len(loops)==1,"one bounded duration scan");items=[x for x in n.values() if "K2Node_GetArrayItem" in x.node_class];c.require(len(items)==8,"eight exact array reads")
    primitive=one("EvaluateSphericalBezierQuaternionV1");c.require('bSelfContext=True' in primitive.text,"self primitive")
    for name in ("TrajectoryInputAlphaV1","TrajectoryInputOrientationStartQuatV1","TrajectoryInputOrientationStartControlQuatV1","TrajectoryInputOrientationEndControlQuatV1","TrajectoryInputOrientationEndQuatV1"):c.require(len(all_(name))==1,f"primitive input {name}")
    c.require(len(all_("TrajectoryResultOrientationValidV1"))==2,"primitive validity reset/get")
    c.require(len(all_("TrajectoryResultOrientationQuatV1"))==2,"primitive quat reset/get")
    branches=[x for x in n.values() if "K2Node_IfThenElse" in x.node_class];c.require(len(branches)==6,"outer complete choose found duration primitive guards")
    known=set(n);external={target for x in n.values() for pin in x.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external links {external}")
    print(f"Orientation track evaluator contracts passed ({'paste' if a.paste else 'full'}): {len(n)} nodes")
if __name__=="__main__":main()
