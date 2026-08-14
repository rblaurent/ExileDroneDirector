"""Atomically publish one complete private dolly-zoom result snapshot."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="CommitCameraDollyZoomV1"


def load(root):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_camera_dolly_commit_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def pin_kind(node,pin,kind,array=False):
    category,subcategory={"bool":("bool",""),"int":("int",""),"real":("real","double"),"string":("string","")}[kind]
    def mutate(line):line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',"PinType.PinSubCategoryObject=None",line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args();scalar=load(args.project_root);bp=scalar.load_helpers(args.project_root);forms=scalar.load_templates(args.project_root,bp);edit=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");playback=bp.read_blocks(args.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");forms["length"]=bp.find_block(edit,r'MemberName="Array_Length"');forms["item"]=bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem");b=scalar.Builder(bp,forms,FUNCTION)
    def variable(node,name,kind,array=False):
        scalar.retarget_variable(node,name,"real" if kind=="int" else kind);pin_kind(node,name,kind,array)
        if "Output_Get" in node.pins:pin_kind(node,"Output_Get",kind,array)
    def get(name,kind,x,y,array=False):node=b.add(f"get_{name}_{len(b.nodes)}","get",x,y);variable(node,name,kind,array);return node
    def set_(name,kind,x,y,default=None,array=False):
        node=b.add(f"set_{name}_{len(b.nodes)}","set",x,y);variable(node,name,kind,array)
        if default is not None:scalar.set_default(node,name,default)
        return node
    def length(source,pin,x,y):node=b.add(f"length_{len(b.nodes)}","length",x,y);pin_kind(node,"TargetArray","real",True);pin_kind(node,"ReturnValue","int");bp.connect(source,pin,node,"TargetArray");return node
    def compare(member,left,left_pin,x,y,right=None,right_pin=None,default=None,kind="int"):
        node=b.add(f"compare_{member}_{len(b.nodes)}","compare",x,y);scalar.retarget_function(node,member);pin_kind(node,"A",kind);pin_kind(node,"B",kind);pin_kind(node,"ReturnValue","bool");bp.connect(left,left_pin,node,"A")
        if right is None:scalar.set_default(node,"B",default)
        else:bp.connect(right,right_pin,node,"B")
        return node
    def boolean(left,right,x,y):return compare("BooleanAND",left,"ReturnValue",x,y,right,"ReturnValue",kind="bool")
    def combine(items,x,y):
        current=items[0]
        for offset,item in enumerate(items[1:]):current=boolean(current,item,x+offset*192,y)
        return current
    candidate_valid=get("CameraDollyCandidateValidV1","bool",0,0);times=get("CameraDollyInputTimesSecondsV1","real",0,160,True);distances=get("CameraDollyCandidateSubjectDistancesCmV1","real",0,320,True);focals=get("CameraDollyCandidateFocalLengthsMmV1","real",0,480,True);reference=get("CameraDollyInputReferenceSampleIndexV1","int",0,640)
    time_count=length(times,"CameraDollyInputTimesSecondsV1",256,160);distance_count=length(distances,"CameraDollyCandidateSubjectDistancesCmV1",256,320);focal_count=length(focals,"CameraDollyCandidateFocalLengthsMmV1",256,480)
    conditions=(compare("EqualEqual_IntInt",time_count,"ReturnValue",480,160,distance_count,"ReturnValue"),compare("EqualEqual_IntInt",time_count,"ReturnValue",480,320,focal_count,"ReturnValue"),compare("GreaterEqual_IntInt",time_count,"ReturnValue",480,480,default="2"),compare("LessEqual_IntInt",time_count,"ReturnValue",480,640,default="65536"),compare("GreaterEqual_IntInt",reference,"CameraDollyInputReferenceSampleIndexV1",704,640,default="0"),compare("Less_IntInt",reference,"CameraDollyInputReferenceSampleIndexV1",928,640,time_count,"ReturnValue"))
    shape=combine(conditions,704,960);ready=compare("BooleanAND",candidate_valid,"CameraDollyCandidateValidV1",1664,960,shape,"ReturnValue",kind="bool")
    reference_distance=b.add("reference_distance","item",1888,480);pin_kind(reference_distance,"Array","real",True);pin_kind(reference_distance,"Output","real");bp.connect(distances,"CameraDollyCandidateSubjectDistancesCmV1",reference_distance,"Array");bp.connect(reference,"CameraDollyInputReferenceSampleIndexV1",reference_distance,"Dimension 1")
    invalidate=set_("CameraDollyCompileValidV1","bool",256,1440,"false");failure=set_("CameraDollyFailureCodeV1","string",480,1440,"commit_failed");guard=b.add("commit_guard","branch",1888,1440);bp.connect(b.entry,"then",invalidate,"execute");bp.connect(invalidate,"then",failure,"execute");bp.connect(failure,"then",guard,"execute");bp.connect(ready,"ReturnValue",guard,"Condition")
    publish_times=set_("CameraDollyCompiledTimesSecondsV1","real",2112,1440,array=True);publish_distances=set_("CameraDollyCompiledSubjectDistancesCmV1","real",2336,1440,array=True);publish_focals=set_("CameraDollyCompiledFocalLengthsMmV1","real",2560,1440,array=True);publish_reference=set_("CameraDollyCompiledReferenceDistanceCmV1","real",2784,1440);clear_failure=set_("CameraDollyFailureCodeV1","string",3008,1440,"");publish_valid=set_("CameraDollyCompileValidV1","bool",3232,1440,"true")
    bp.connect(guard,"then",publish_times,"execute");bp.connect(times,"CameraDollyInputTimesSecondsV1",publish_times,"CameraDollyCompiledTimesSecondsV1");bp.connect(publish_times,"then",publish_distances,"execute");bp.connect(distances,"CameraDollyCandidateSubjectDistancesCmV1",publish_distances,"CameraDollyCompiledSubjectDistancesCmV1");bp.connect(publish_distances,"then",publish_focals,"execute");bp.connect(focals,"CameraDollyCandidateFocalLengthsMmV1",publish_focals,"CameraDollyCompiledFocalLengthsMmV1");bp.connect(publish_focals,"then",publish_reference,"execute");bp.connect(reference_distance,"Output",publish_reference,"CameraDollyCompiledReferenceDistanceCmV1");bp.connect(publish_reference,"then",clear_failure,"execute");bp.connect(clear_failure,"then",publish_valid,"execute")
    full="\n".join(node.text for node in b.nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
    if args.paste_output:args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:])+"\n",encoding="utf-8")


if __name__=="__main__":main()
