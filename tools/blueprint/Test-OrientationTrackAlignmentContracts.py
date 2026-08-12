"""Exact executable contracts for multi-key quaternion alignment."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path


def load(root):
    path=root/"tools/blueprint/Test-WaypointCaptureContracts.py";spec=importlib.util.spec_from_file_location("edd_align_contract_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args()
    c=load(a.project_root);n=c.parse_graph(a.graph);c.require(len(n)==(14 if a.paste else 15),f"node count {len(n)}")
    entries=[x for x in n.values() if "K2Node_FunctionEntry" in x.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
    def one(member):return next(x for x in n.values() if f'MemberName="{member}"' in x.text)
    candidate=one("OrientationTrackCandidateAlignedQuatsV1");inputs=one("OrientationTrackInputWaypointQuatsV1");stage=one("OrientationTrackStageValidV1")
    clear=one("Array_Clear");loop=next(x for x in n.values() if "K2Node_MacroInstance" in x.node_class);norm=one("Quat_Normalized");slerp=one("Quat_Slerp")
    adds=[x for x in n.values() if 'MemberName="Array_Add"' in x.text];c.require(len(adds)==2,"two append paths")
    item=next(x for x in n.values() if "K2Node_GetArrayItem" in x.node_class);subtract=one("Subtract_IntInt");equal=one("EqualEqual_IntInt")
    c.require_link(candidate,"OrientationTrackCandidateAlignedQuatsV1",clear,"TargetArray","candidate reset")
    c.require_link(inputs,"OrientationTrackInputWaypointQuatsV1",loop,"Array","input loop")
    c.require_link(loop,"Array Element",norm,"Q","every input normalized")
    c.require_link(loop,"Array Index",equal,"A","first predicate index");c.require('DefaultValue="0"' in equal.pins["B"].body,"first predicate default")
    c.require_link(loop,"Array Index",subtract,"A","prior index source");c.require('DefaultValue="1"' in subtract.pins["B"].body,"prior offset")
    c.require_link(candidate,"OrientationTrackCandidateAlignedQuatsV1",item,"Array","previous comes from candidate");c.require_link(subtract,"ReturnValue",item,"Dimension 1","previous index")
    c.require_link(item,"Output",slerp,"A","alignment anchor");c.require_link(norm,"ReturnValue",slerp,"B","alignment candidate");c.require('DefaultValue="1.0"' in slerp.pins["Alpha"].body,"alignment alpha")
    first=next(x for x in adds if c.linked(norm,"ReturnValue",x,"NewItem"));rest=next(x for x in adds if c.linked(slerp,"ReturnValue",x,"NewItem"))
    for add in adds:c.require_link(candidate,"OrientationTrackCandidateAlignedQuatsV1",add,"TargetArray","append target")
    branch=next(x for x in n.values() if "K2Node_IfThenElse" in x.node_class and c.linked(equal,"ReturnValue",x,"Condition"))
    c.require_link(branch,"then",first,"execute","first append route");c.require_link(branch,"else",rest,"execute","subsequent append route")
    guard=next(x for x in n.values() if "K2Node_IfThenElse" in x.node_class and c.linked(stage,"OrientationTrackStageValidV1",x,"Condition"));c.require_link(guard,"then",loop,"Exec","invalid stage must not loop")
    if a.paste:c.require(not clear.pins["execute"].links,"paste root")
    else:c.require_link(entries[0],"then",clear,"execute","entry seam")
    known=set(n);external={target for x in n.values() for pin in x.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external {external}")
    print(f"Orientation track alignment contracts passed ({'paste' if a.paste else 'full'}): {len(n)} nodes")


if __name__=="__main__":main()
