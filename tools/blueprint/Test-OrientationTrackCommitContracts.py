"""Exact structural contracts for atomic compiled-orientation publication."""
from __future__ import annotations
import argparse, importlib.util, sys
from pathlib import Path

def load(root):
    p=root/"tools/blueprint/Test-WaypointCaptureContracts.py";s=importlib.util.spec_from_file_location("edd_track_commit_contract",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);n=c.parse_graph(a.graph);c.require(len(n)==(84 if a.paste else 85),f"node count {len(n)}")
    entries=[x for x in n.values() if "K2Node_FunctionEntry" in x.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    def all_(member):return [x for x in n.values() if f'MemberName="{member}"' in x.text]
    def one(member):values=all_(member);c.require(len(values)==1,f"one {member}:{len(values)}");return values[0]
    compiled=("OrientationTrackCompiledAlignedQuatsV1","OrientationTrackCompiledDurationsV1","OrientationTrackCompiledTangentRatesV1","OrientationTrackCompiledSegmentStartsV1","OrientationTrackCompiledStartControlsV1","OrientationTrackCompiledEndControlsV1")
    candidate=("OrientationTrackCandidateAlignedQuatsV1","OrientationTrackInputDurationsV1","OrientationTrackCandidateTangentRatesV1","OrientationTrackCandidateSegmentStartsV1","OrientationTrackCandidateStartControlsV1","OrientationTrackCandidateEndControlsV1")
    clears=all_("Array_Clear");c.require(len(clears)==6,"six compiled clears")
    for name in compiled:
        nodes=all_(name);c.require(len(nodes)==2,f"compiled get/publish {name}");get=next(x for x in nodes if "VariableGet" in x.node_class);c.require(sum(c.linked(get,name,clear,"TargetArray") for clear in clears)==1,f"clear {name}")
    for name in candidate:c.require(len(all_(name))==1,f"candidate source {name}")
    c.require(len(all_("Array_Length"))==6,"six cardinality lengths");c.require(len(all_("EqualEqual_IntInt"))==5,"five cardinality equalities");c.require(len(all_("GreaterEqual_IntInt"))==1,"minimum keys")
    c.require(len(all_("Greater_DoubleDouble"))==2,"positive total and duration");c.require(len(all_("EqualEqual_DoubleDouble"))==2,"exact start and final total");c.require(len(all_("Add_DoubleDouble"))==1,"duration accumulator")
    stage=all_("OrientationTrackStageValidV1");c.require(len(stage)==4,"stage get plus three fail setters");c.require(all('DefaultValue="false"' in x.pins["OrientationTrackStageValidV1"].body for x in stage if "VariableSet" in x.node_class),"all stage failures false")
    compile_valid=all_("OrientationTrackCompileValidV1");c.require(len(compile_valid)==2,"compile validity reset/accept");c.require(any('DefaultValue="false"' in x.pins["OrientationTrackCompileValidV1"].body for x in compile_valid),"valid reset");c.require(any('DefaultValue="true"' in x.pins["OrientationTrackCompileValidV1"].body for x in compile_valid),"valid final accept")
    for name in ("OrientationTrackResultSegmentIndexV1","OrientationTrackResultAlphaV1","OrientationTrackResultQuatV1","OrientationTrackResultCompleteV1","OrientationTrackResultValidV1"):c.require(len(all_(name))==1,f"evaluation reset {name}")
    loops=[x for x in n.values() if "K2Node_MacroInstance" in x.node_class];c.require(len(loops)==1,"one duration verification loop");branches=[x for x in n.values() if "K2Node_IfThenElse" in x.node_class];c.require(len(branches)==3,"outer item final guards")
    boolean_ands=all_("BooleanAND");c.require(len(boolean_ands)==17,"complete outer, loop, and final boolean chains")
    # Publication setters must copy all six candidate arrays and execute only after final guard.
    publish=[]
    for source_name,target_name in zip(candidate,compiled):
        source=one(source_name);target=next(x for x in all_(target_name) if "VariableSet" in x.node_class and c.linked(source,source_name,x,target_name));publish.append(target)
    c.require(len(publish)==6,"six publication setters")
    if a.paste:c.require(not clears[0].pins["execute"].links,"paste root")
    else:c.require(sum(c.linked(entries[0],"then",clear,"execute") for clear in clears)==1,"entry reset seam")
    known=set(n);external={target for x in n.values() for pin in x.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external {external}")
    print(f"Orientation track commit contracts passed ({'paste' if a.paste else 'full'}): {len(n)} nodes")
if __name__=="__main__":main()
