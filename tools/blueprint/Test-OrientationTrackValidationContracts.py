"""Exact executable contracts for orientation-track input validation."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path=root/"tools/blueprint/Test-WaypointCaptureContracts.py"
    spec=importlib.util.spec_from_file_location("edd_orientation_validation_contract_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def one_member(nodes, member):
    return next(node for node in nodes.values() if f'MemberName="{member}"' in node.text)


def default(node,pin,value):
    match=re.search(r'(?:^|,)DefaultValue="([^"]*)"',node.pins[pin].body)
    return match is not None and match.group(1)==value


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args()
    c=load(a.project_root);nodes=c.parse_graph(a.graph);c.require(len(nodes)==(28 if a.paste else 29),f"node count {len(nodes)}")
    entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    quats=one_member(nodes,"OrientationTrackInputWaypointQuatsV1");durations=one_member(nodes,"OrientationTrackInputDurationsV1")
    lengths=[n for n in nodes.values() if 'MemberName="Array_Length"' in n.text];c.require(len(lengths)==2,"two exact lengths")
    qlen=next(n for n in lengths if c.linked(quats,"OrientationTrackInputWaypointQuatsV1",n,"TargetArray"))
    dlen=next(n for n in lengths if c.linked(durations,"OrientationTrackInputDurationsV1",n,"TargetArray"))
    lower=one_member(nodes,"GreaterEqual_IntInt");upper=one_member(nodes,"LessEqual_IntInt");subtract=one_member(nodes,"Subtract_IntInt");shape=one_member(nodes,"EqualEqual_IntInt")
    c.require(default(lower,"B","2"),"minimum changed");c.require(default(upper,"B","512"),"maximum changed");c.require(default(subtract,"B","1"),"shape subtract changed")
    c.require_link(qlen,"ReturnValue",lower,"A","minimum must use waypoint length");c.require_link(qlen,"ReturnValue",upper,"A","maximum must use waypoint length")
    c.require_link(qlen,"ReturnValue",subtract,"A","subtract must use waypoint length");c.require_link(dlen,"ReturnValue",shape,"A","shape must use duration length");c.require_link(subtract,"ReturnValue",shape,"B","shape must equal waypoint minus one")
    loops=[n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class];c.require(len(loops)==2,"two foreach loops")
    qloop=next(n for n in loops if c.linked(quats,"OrientationTrackInputWaypointQuatsV1",n,"Array"));dloop=next(n for n in loops if c.linked(durations,"OrientationTrackInputDurationsV1",n,"Array"))
    qfinite=one_member(nodes,"Quat_IsFinite");qsize=one_member(nodes,"Quat_Size")
    c.require_link(qloop,"Array Element",qfinite,"Q","quat finite must inspect each item");c.require_link(qloop,"Array Element",qsize,"Q","quat norm must inspect each item")
    greater=[n for n in nodes.values() if 'MemberName="Greater_DoubleDouble"' in n.text];c.require(len(greater)==2,"two real positivity predicates")
    qnonzero=next(n for n in greater if default(n,"B","1e-12"));dpositive=next(n for n in greater if default(n,"B","0.0"))
    c.require_link(qsize,"ReturnValue",qnonzero,"A","quat norm threshold disconnected")
    c.require(c.linked(dloop,"Array Element",dpositive,"A"),"duration positivity disconnected")
    finite_bounds=[n for n in nodes.values() if 'MemberName="GreaterEqual_DoubleDouble"' in n.text or 'MemberName="LessEqual_DoubleDouble"' in n.text]
    c.require(len(finite_bounds)==2 and all(c.linked(dloop,"Array Element",n,"A") for n in finite_bounds),"duration finite bounds disconnected")
    stage_sets=[n for n in nodes.values() if 'MemberName="OrientationTrackStageValidV1"' in n.text]
    c.require(len(stage_sets)==4,"stage must have reset accept and two rejects")
    defaults=[re.search(r'DefaultValue="([^"]*)"',n.pins["OrientationTrackStageValidV1"].body).group(1) for n in stage_sets]
    c.require(defaults.count("true")==1 and defaults.count("false")==3,"stage validity writes changed")
    if a.paste:
        reset=next(n for n in stage_sets if not n.pins["execute"].links);c.require(reset is not None,"paste root not exposed")
    else:
        reset=next(n for n in stage_sets if c.linked(entries[0],"then",n,"execute"));c.require(reset is not None,"entry reset missing")
    known=set(nodes);external={target for n in nodes.values() for pin in n.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external links {external}")
    print(f"Orientation track validation contracts passed ({'paste' if a.paste else 'full'}): {len(nodes)} nodes")


if __name__=="__main__":main()
