"""Exact ordering contract for the end-to-end orientation track compiler."""
from __future__ import annotations
import argparse,importlib.util,sys
from pathlib import Path

STAGES=("ResetOrientationTrackCandidateV1","ValidateOrientationTrackInputsV1","AlignOrientationWaypointsV1","ComputeOrientationForwardDeltasV1","ComputeOrientationTrackTangentRatesV1","BuildOrientationTrackSegmentsV1","CommitCompiledOrientationTrackV1")
def load(root):
    p=root/"tools/blueprint/Test-WaypointCaptureContracts.py";s=importlib.util.spec_from_file_location("edd_compile_contract",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);n=c.parse_graph(a.graph);c.require(len(n)==(7 if a.paste else 8),f"node count {len(n)}")
    entries=[x for x in n.values() if "K2Node_FunctionEntry" in x.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    calls=[]
    for name in STAGES:
        found=[x for x in n.values() if f'MemberName="{name}"' in x.text];c.require(len(found)==1,f"one call {name}");calls.append(found[0]);c.require('bSelfContext=True' in found[0].text,f"self call {name}")
    for left,right in zip(calls,calls[1:]):c.require_link(left,"then",right,"execute",f"ordered {left.name} -> {right.name}")
    if a.paste:c.require(not calls[0].pins["execute"].links,"paste root")
    else:c.require_link(entries[0],"then",calls[0],"execute","entry reset seam")
    known=set(n);external={target for x in n.values() for pin in x.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external {external}")
    print(f"Orientation track compile contracts passed ({'paste' if a.paste else 'full'}): {len(n)} nodes")
if __name__=="__main__":main()
