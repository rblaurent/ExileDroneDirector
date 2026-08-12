"""Build deterministic normalization and shortest-arc alignment of orientation keys."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="AlignOrientationWaypointsV1"


def load(root):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_orientation_align_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def kind(node,pin,quat=False,array=False):
    category="struct" if quat else "int";obj='"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"' if quat else "None"
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1)
        line=re.sub(r'PinType.PinSubCategory="[^"]*"','PinType.PinSubCategory=""',line,1)
        line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)


def variable(scalar,node,name,quat=True,array=True):
    scalar.retarget_variable(node,name,"vector" if quat else "int");kind(node,name,quat,array)
    if "Output_Get" in node.pins:kind(node,"Output_Get",quat,False)


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args()
    scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
    sync=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    capture=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph")
    qforms=bp.read_blocks(a.project_root/"tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    foreach_form=bp.find_block(sync,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance");add_form=bp.find_block(capture,r'MemberName="Array_Add"');getitem_form=bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")
    clear_form=bp.find_block(bp.read_blocks(a.project_root/"tools/blueprint/snippets/reset-orientation-track-candidate-v1.eddgraph"),r'MemberName="Array_Clear"')
    qnorm_form=bp.find_block(qforms,r'MemberName="Quat_Normalized"');slerp_form=bp.find_block(qforms,r'MemberName="Quat_Slerp"')
    def add(key,form,x,y):
        match=bp.BLOCK_RE.match(form);cls=match.group("class").rsplit(".",1)[-1];idx=b.serial.get(cls,0);b.serial[cls]=idx+1
        node=bp.Node.clone(key,form,f"{cls}_{idx}",x,y);b.nodes.append(node);return node
    candidate=b.get("OrientationTrackCandidateAlignedQuatsV1","vector",0,560);variable(scalar,candidate,"OrientationTrackCandidateAlignedQuatsV1")
    clear=add("clear",clear_form,256,1280);kind(clear,"TargetArray",True,True);bp.connect(candidate,"OrientationTrackCandidateAlignedQuatsV1",clear,"TargetArray");bp.connect(b.entry,"then",clear,"execute")
    stage=b.get("OrientationTrackStageValidV1","bool",256,1120);guard=b.add("guard","branch",512,1280);bp.connect(clear,"then",guard,"execute");bp.connect(stage,"OrientationTrackStageValidV1",guard,"Condition")
    inputs=b.get("OrientationTrackInputWaypointQuatsV1","vector",768,160);variable(scalar,inputs,"OrientationTrackInputWaypointQuatsV1")
    loop=add("loop",foreach_form,1024,448);kind(loop,"Array",True,True);kind(loop,"Array Element",True);bp.connect(inputs,"OrientationTrackInputWaypointQuatsV1",loop,"Array");bp.connect(guard,"then",loop,"Exec")
    normalized=add("normalized",qnorm_form,1296,320);bp.connect(loop,"Array Element",normalized,"Q")
    first_compare=b.add("first_compare","compare",1296,640);scalar.retarget_function(first_compare,"EqualEqual_IntInt")
    for pin in ("A","B"):kind(first_compare,pin,False);kind(first_compare,"ReturnValue",False);scalar.set_default(first_compare,"B","0");bp.connect(loop,"Array Index",first_compare,"A")
    branch=b.add("first_branch","branch",1536,816);bp.connect(loop,"LoopBody",branch,"execute");bp.connect(first_compare,"ReturnValue",branch,"Condition")
    add_first=add("add_first",add_form,1792,640);kind(add_first,"TargetArray",True,True);kind(add_first,"NewItem",True);bp.connect(candidate,"OrientationTrackCandidateAlignedQuatsV1",add_first,"TargetArray");bp.connect(normalized,"ReturnValue",add_first,"NewItem");bp.connect(branch,"then",add_first,"execute")
    subtract=b.math("Subtract_DoubleDouble",1536,1120);scalar.retarget_function(subtract,"Subtract_IntInt")
    for pin in ("A","B","ReturnValue"):kind(subtract,pin,False)
    scalar.set_default(subtract,"B","1");bp.connect(loop,"Array Index",subtract,"A")
    previous=add("previous",getitem_form,1792,1120);kind(previous,"Array",True,True);kind(previous,"Output",True);bp.connect(candidate,"OrientationTrackCandidateAlignedQuatsV1",previous,"Array");bp.connect(subtract,"ReturnValue",previous,"Dimension 1")
    aligned=add("aligned",slerp_form,2048,960);scalar.set_default(aligned,"Alpha","1.0");bp.connect(previous,"Output",aligned,"A");bp.connect(normalized,"ReturnValue",aligned,"B")
    add_rest=add("add_rest",add_form,2304,1120);kind(add_rest,"TargetArray",True,True);kind(add_rest,"NewItem",True);bp.connect(candidate,"OrientationTrackCandidateAlignedQuatsV1",add_rest,"TargetArray");bp.connect(aligned,"ReturnValue",add_rest,"NewItem");bp.connect(branch,"else",add_rest,"execute")
    full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")


if __name__=="__main__":main()
