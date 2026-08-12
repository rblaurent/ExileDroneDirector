"""Exact semantic contracts for the orientation-track reset transaction."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = (
    "OrientationTrackCandidateAlignedQuatsV1", "OrientationTrackCandidateForwardDeltasV1",
    "OrientationTrackCandidateTangentRatesV1", "OrientationTrackCandidateSegmentStartsV1",
    "OrientationTrackCandidateStartControlsV1", "OrientationTrackCandidateEndControlsV1",
    "OrientationTrackCompiledAlignedQuatsV1", "OrientationTrackCompiledDurationsV1",
    "OrientationTrackCompiledTangentRatesV1", "OrientationTrackCompiledSegmentStartsV1",
    "OrientationTrackCompiledStartControlsV1", "OrientationTrackCompiledEndControlsV1",
)
SCALARS = (
    ("OrientationTrackCandidateTotalSecondsV1", "0.0"),
    ("OrientationTrackStageValidV1", "false"),
    ("OrientationTrackCompiledTotalSecondsV1", "0.0"),
    ("OrientationTrackCompileValidV1", "false"),
    ("OrientationTrackResultSegmentIndexV1", "-1"),
    ("OrientationTrackResultAlphaV1", "0.0"),
    ("OrientationTrackResultQuatV1", None),
    ("OrientationTrackResultCompleteV1", "false"),
    ("OrientationTrackResultValidV1", "false"),
)


def load(root: Path):
    path=root/"tools/blueprint/Test-WaypointCaptureContracts.py"
    spec=importlib.util.spec_from_file_location("edd_orientation_reset_contract_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args()
    c=load(a.project_root);nodes=c.parse_graph(a.graph)
    c.require(len(nodes)==(34 if not a.paste else 33),f"reset node count {len(nodes)}")
    entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class]
    c.require(len(entries)==(0 if a.paste else 1),"reset entry count")
    clears=[]
    for name in ARRAYS:
        getter=c.one(nodes,f'MemberName="{name}"')
        clear=next((node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text and any(target==getter.name for pin in node.pins.values() for target,_ in pin.links)),None)
        c.require(clear is not None,f"{name} clear missing")
        c.require_link(getter,name,clear,"TargetArray",f"{name} must be cleared")
        clears.append(clear)
    setters=[]
    for name,value in SCALARS:
        setter=c.one(nodes,f'MemberName="{name}"')
        line=setter.pins[name].body
        if value is None:
            explicit=re.search(r'(?:^|,)DefaultValue="([^"]*)"',line)
            c.require(explicit and explicit.group(1) in ('0, 0, 0, 1','(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)'),"quat reset changed")
        else:c.require(f'DefaultValue="{value}"' in line,f"{name} reset changed")
        setters.append(setter)
    chain=[*clears,*setters]
    if a.paste:c.require(not chain[0].pins["execute"].links,"paste root must be exposed")
    else:c.require_link(entries[0],"then",chain[0],"execute","entry must reach first clear")
    for left,right in zip(chain,chain[1:]):c.require_link(left,"then",right,"execute","reset order changed")
    known=set(nodes)
    external={target for node in nodes.values() for pin in node.pins.values() for target,_ in pin.links if target not in known}
    c.require(not external,f"external links {external}")
    print(f"Orientation track reset contracts passed ({'paste' if a.paste else 'full'}): {len(nodes)} nodes")


if __name__=="__main__":main()
