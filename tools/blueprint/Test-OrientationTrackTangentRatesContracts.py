"""Exact contracts for endpoint/interior orientation tangent-rate assembly."""
from __future__ import annotations
import argparse,importlib.util,sys
from pathlib import Path

def load(root):
    p=root/"tools/blueprint/Test-WaypointCaptureContracts.py";s=importlib.util.spec_from_file_location("edd_track_tangent_contract",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);n=c.parse_graph(a.graph)
    c.require(len(n)==(59 if a.paste else 60),f"node count {len(n)}");entries=[x for x in n.values() if "K2Node_FunctionEntry" in x.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    def all_(member):return [x for x in n.values() if f'MemberName="{member}"' in x.text]
    def one(member):
        values=all_(member);c.require(len(values)==1,f"one {member}: {len(values)}");return values[0]
    candidate=one("OrientationTrackCandidateTangentRatesV1");aligned=one("OrientationTrackCandidateAlignedQuatsV1");deltas=one("OrientationTrackCandidateForwardDeltasV1");durations=one("OrientationTrackInputDurationsV1")
    clear=one("Array_Clear");loop=next(x for x in n.values() if "K2Node_MacroInstance" in x.node_class);length=one("Array_Length");calls=all_("ComputeOrientationTangentRateV1");c.require(len(calls)==3,"three primitive call paths")
    adds=all_("Array_Add");c.require(len(adds)==3,"three append paths");stage=all_("OrientationTrackStageValidV1");c.require(len(stage)==4,"one stage getter plus three rejecting setters")
    stage_get=next(x for x in stage if "K2Node_VariableGet" in x.node_class);rejects=[x for x in stage if "K2Node_VariableSet" in x.node_class];c.require(all('DefaultValue="false"' in x.pins["OrientationTrackStageValidV1"].body for x in rejects),"sticky rejects")
    c.require_link(candidate,"OrientationTrackCandidateTangentRatesV1",clear,"TargetArray","candidate clear");c.require_link(aligned,"OrientationTrackCandidateAlignedQuatsV1",loop,"Array","waypoint loop");c.require_link(aligned,"OrientationTrackCandidateAlignedQuatsV1",length,"TargetArray","last index length")
    guards=[x for x in n.values() if "K2Node_IfThenElse" in x.node_class];c.require(len(guards)==7,"outer inner first last and three result guards");c.require(sum(c.linked(stage_get,"OrientationTrackStageValidV1",x,"Condition") for x in guards)==2,"stage entry and iteration guards")
    c.require(len(all_("OrientationInputPreviousDeltaVectorV1"))==3,"previous delta setters");c.require(len(all_("OrientationInputNextDeltaVectorV1"))==3,"next delta setters");c.require(len(all_("OrientationInputPreviousDurationV1"))==3,"previous duration setters");c.require(len(all_("OrientationInputNextDurationV1"))==3,"next duration setters")
    items=[x for x in n.values() if "K2Node_GetArrayItem" in x.node_class];c.require(len(items)==12,"four staged reads per path")
    c.require(sum(c.linked(deltas,"OrientationTrackCandidateForwardDeltasV1",x,"Array") for x in items)==6,"six delta reads");c.require(sum(c.linked(durations,"OrientationTrackInputDurationsV1",x,"Array") for x in items)==6,"six duration reads")
    result_valid=all_("OrientationResultValidV1");results=all_("OrientationResultTangentRateVectorV1");c.require(len(result_valid)==3 and len(results)==3,"three primitive result reads")
    for add in adds:c.require_link(candidate,"OrientationTrackCandidateTangentRatesV1",add,"TargetArray","append target")
    c.require(sum(c.linked(x,"OrientationResultTangentRateVectorV1",add,"NewItem") for x in results for add in adds)==3,"one result per append")
    c.require(all('bSelfContext=True' in x.text for x in calls),"primitive self context")
    if a.paste:c.require(not clear.pins["execute"].links,"paste root")
    else:c.require_link(entries[0],"then",clear,"execute","entry seam")
    known=set(n);external={t for x in n.values() for pin in x.pins.values() for t,_ in pin.links if t not in known};c.require(not external,f"external {external}")
    print(f"Orientation track tangent-rate contracts passed ({'paste' if a.paste else 'full'}): {len(n)} nodes")
if __name__=="__main__":main()
