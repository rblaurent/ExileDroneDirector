"""Build a bounded, aligned dolly-zoom distance/focal candidate prefix."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "BuildCameraDollyZoomCandidatesV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_dolly_candidates_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def pin_kind(node, pin: str, kind: str, array=False):
    category, subcategory, obj = {"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[kind]
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args()
    scalar=load(args.project_root);bp=scalar.load_helpers(args.project_root);forms=scalar.load_templates(args.project_root,bp)
    capture=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");edit=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");playback=bp.read_blocks(args.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");reset=bp.read_blocks(args.project_root/"tools/blueprint/snippets/reset-camera-dolly-zoom-v1.eddgraph");loops=bp.read_blocks(args.project_root/"tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph");vectors=bp.read_blocks(args.project_root/"tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph");preview=bp.read_blocks(args.project_root/"tools/blueprint/templates/path-preview-segment-node-forms.eddgraph");speed=bp.read_blocks(args.project_root/"tools/blueprint/snippets/update-speed-controls.eddgraph")
    forms.update({"add":bp.find_block(capture,r'MemberName="Array_Add"'),"clear":bp.find_block(reset,r'MemberName="Array_Clear"'),"length":bp.find_block(edit,r'MemberName="Array_Length"'),"item":bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),"loop":bp.find_block(loops,r"StandardMacros:ForLoopWithBreak"),"break_vector":bp.find_block(vectors,r'MemberName="BreakVector"'),"distance":bp.find_block(preview,r'MemberName="Vector_Distance"'),"select":bp.find_block(speed,r'MemberName="SelectFloat"')})
    b=scalar.Builder(bp,forms,FUNCTION)
    def variable(node,name,kind,array=False):
        scalar.retarget_variable(node,name,"real" if kind=="int" else kind);pin_kind(node,name,kind,array)
        if "Output_Get" in node.pins:pin_kind(node,"Output_Get",kind,array)
    def get(name,kind,x,y,array=False):node=b.add(f"get_{name}_{len(b.nodes)}","get",x,y);variable(node,name,kind,array);return node
    def set_(name,kind,x,y,default=None):
        node=b.add(f"set_{name}_{len(b.nodes)}","set",x,y);variable(node,name,kind)
        if default is not None:scalar.set_default(node,name,default)
        return node
    def array_node(form,source,source_pin,kind,x,y):
        node=b.add(f"{form}_{len(b.nodes)}",form,x,y);target="Array" if form=="item" else "TargetArray";pin_kind(node,target,kind,True)
        if form=="item":pin_kind(node,"Output",kind)
        elif form=="length":pin_kind(node,"ReturnValue","int")
        elif form=="add":pin_kind(node,"NewItem",kind);pin_kind(node,"ReturnValue","int")
        bp.connect(source,source_pin,node,target);return node
    def item(source,source_pin,kind,index,index_pin,x,y):node=array_node("item",source,source_pin,kind,x,y);bp.connect(index,index_pin,node,"Dimension 1");return node
    def retarget(node,member,kinds):
        scalar.retarget_function(node,member)
        for pin,kind in kinds.items():pin_kind(node,pin,kind)
        return node
    def operation(member,left,left_pin,x,y,right=None,right_pin=None,default=None,kind="real"):
        node=b.add(f"op_{member}_{len(b.nodes)}","math",x,y);retarget(node,member,{"A":kind,"B":kind,"ReturnValue":kind});bp.connect(left,left_pin,node,"A")
        if right is not None:bp.connect(right,right_pin,node,"B")
        else:scalar.set_default(node,"B",default)
        return node
    def compare(member,left,left_pin,x,y,right=None,right_pin=None,default=None,kind="real"):
        node=b.add(f"cmp_{member}_{len(b.nodes)}","compare",x,y);retarget(node,member,{"A":kind,"B":kind,"ReturnValue":"bool"});bp.connect(left,left_pin,node,"A")
        if right is not None:bp.connect(right,right_pin,node,"B")
        else:scalar.set_default(node,"B",default)
        return node
    def boolean(member,left,right,x,y):return compare(member,left,"ReturnValue",x,y,right,"ReturnValue",kind="bool")
    def combine(items,x,y):
        current=items[0]
        for offset,node in enumerate(items[1:]):current=boolean("BooleanAND",current,node,x+offset*192,y)
        return current
    def distance(left,left_pin,right,right_pin,x,y):node=b.add(f"distance_{len(b.nodes)}","distance",x,y);bp.connect(left,left_pin,node,"V1");bp.connect(right,right_pin,node,"V2");return node
    def finite_vector(source,source_pin,x,y):
        node=b.add(f"break_vector_{len(b.nodes)}","break_vector",x,y);bp.connect(source,source_pin,node,"InVec");checks=[b.finite(node,axis,x+224,y+offset*160) for offset,axis in enumerate(("X","Y","Z"))];return combine(checks,x+672,y+160)

    inputs={
        "valid":get("CameraDollyValidationValidV1","bool",0,0),"times":get("CameraDollyInputTimesSecondsV1","real",0,160,True),"cameras":get("CameraDollyInputCameraPositionsV1","vector",0,320,True),"subject":get("CameraDollyInputSubjectPositionV1","vector",0,480),"reference":get("CameraDollyInputReferenceSampleIndexV1","int",0,640),"focal":get("CameraDollyInputReferenceFocalLengthMmV1","real",0,800),"distances":get("CameraDollyCandidateSubjectDistancesCmV1","real",0,960,True),"focals":get("CameraDollyCandidateFocalLengthsMmV1","real",0,1120,True),
    }
    count=array_node("length",inputs["times"],"CameraDollyInputTimesSecondsV1","real",256,160);last=operation("Subtract_IntInt",count,"ReturnValue",480,160,default="1",kind="int")
    reference_camera=item(inputs["cameras"],"CameraDollyInputCameraPositionsV1","vector",inputs["reference"],"CameraDollyInputReferenceSampleIndexV1",256,640)
    subject_finite=finite_vector(inputs["subject"],"CameraDollyInputSubjectPositionV1",480,960);reference_camera_finite=finite_vector(reference_camera,"Output",480,1440)
    reference_distance=distance(reference_camera,"Output",inputs["subject"],"CameraDollyInputSubjectPositionV1",1376,1280);reference_distance_finite=b.finite(reference_distance,"ReturnValue",1600,1280);reference_distance_min=compare("GreaterEqual_DoubleDouble",reference_distance,"ReturnValue",2048,1280,default="1.0");reference_ok=combine((subject_finite,reference_camera_finite,reference_distance_finite,reference_distance_min),2272,1440)
    invalidate=set_("CameraDollyCandidateValidV1","bool",256,2240,"false");failure=set_("CameraDollyFailureCodeV1","string",480,2240,"candidate_failed");clear_distances=array_node("clear",inputs["distances"],"CameraDollyCandidateSubjectDistancesCmV1","real",704,2240);clear_focals=array_node("clear",inputs["focals"],"CameraDollyCandidateFocalLengthsMmV1","real",928,2240);stage_guard=b.add("stage_guard","branch",1152,2240);reference_guard=b.add("reference_guard","branch",1376,2240)
    bp.connect(b.entry,"then",invalidate,"execute");bp.connect(invalidate,"then",failure,"execute");bp.connect(failure,"then",clear_distances,"execute");bp.connect(clear_distances,"then",clear_focals,"execute");bp.connect(clear_focals,"then",stage_guard,"execute");bp.connect(inputs["valid"],"CameraDollyValidationValidV1",stage_guard,"Condition");bp.connect(stage_guard,"then",reference_guard,"execute");bp.connect(reference_ok,"ReturnValue",reference_guard,"Condition")
    loop=b.add("sample_loop","loop",2720,2240);scalar.set_default(loop,"FirstIndex","0");bp.connect(last,"ReturnValue",loop,"LastIndex");bp.connect(reference_guard,"then",loop,"Execute")
    current=item(inputs["times"],"CameraDollyInputTimesSecondsV1","real",loop,"Index",2944,1760);is_first=compare("EqualEqual_IntInt",loop,"Index",3168,1760,default="0",kind="int");previous_raw=operation("Subtract_IntInt",loop,"Index",3392,1760,default="1",kind="int")
    # SelectInt: A=0 for the first sample, B=index-1 otherwise.
    select_index=b.add("previous_index","select",3616,1760);retarget(select_index,"SelectInt",{"A":"int","B":"int","ReturnValue":"int","bPickA":"bool"});scalar.set_default(select_index,"A","0");bp.connect(previous_raw,"ReturnValue",select_index,"B");bp.connect(is_first,"ReturnValue",select_index,"bPickA")
    previous=item(inputs["times"],"CameraDollyInputTimesSecondsV1","real",select_index,"ReturnValue",3840,1760);finite_time=b.finite(current,"Output",4064,1600);starts_zero=compare("EqualEqual_DoubleDouble",current,"Output",4512,1600,default="0.0");first_zero=boolean("BooleanAND",is_first,starts_zero,4736,1600);increasing=compare("Greater_DoubleDouble",current,"Output",4512,1760,previous,"Output");timeline_ok=boolean("BooleanOR",first_zero,increasing,4960,1680)
    camera=item(inputs["cameras"],"CameraDollyInputCameraPositionsV1","vector",loop,"Index",2944,2880);camera_finite=finite_vector(camera,"Output",3168,2720);sample_distance=distance(camera,"Output",inputs["subject"],"CameraDollyInputSubjectPositionV1",4064,3040);distance_finite=b.finite(sample_distance,"ReturnValue",4288,2880);distance_min=compare("GreaterEqual_DoubleDouble",sample_distance,"ReturnValue",4736,3040,default="1.0")
    focal_product=operation("Multiply_DoubleDouble",inputs["focal"],"CameraDollyInputReferenceFocalLengthMmV1",4288,3360,sample_distance,"ReturnValue");sample_focal=operation("Divide_DoubleDouble",focal_product,"ReturnValue",4512,3360,reference_distance,"ReturnValue");focal_finite=b.finite(sample_focal,"ReturnValue",4736,3360);focal_min=compare("GreaterEqual_DoubleDouble",sample_focal,"ReturnValue",5184,3360,default="1.0");focal_max=compare("LessEqual_DoubleDouble",sample_focal,"ReturnValue",5408,3360,default="1000.0")
    sample_ok=combine((finite_time,timeline_ok,camera_finite,distance_finite,distance_min,focal_finite,focal_min,focal_max),5632,2880);sample_guard=b.add("sample_guard","branch",6976,2240);bp.connect(loop,"LoopBody",sample_guard,"execute");bp.connect(sample_ok,"ReturnValue",sample_guard,"Condition")
    append_distance=array_node("add",inputs["distances"],"CameraDollyCandidateSubjectDistancesCmV1","real",7200,2160);bp.connect(sample_distance,"ReturnValue",append_distance,"NewItem");bp.connect(sample_guard,"then",append_distance,"execute")
    append_focal=array_node("add",inputs["focals"],"CameraDollyCandidateFocalLengthsMmV1","real",7424,2160);bp.connect(sample_focal,"ReturnValue",append_focal,"NewItem");bp.connect(append_distance,"then",append_focal,"execute");bp.connect(sample_guard,"else",loop,"Break")
    built_distances=array_node("length",inputs["distances"],"CameraDollyCandidateSubjectDistancesCmV1","real",7200,2560);built_focals=array_node("length",inputs["focals"],"CameraDollyCandidateFocalLengthsMmV1","real",7200,2720);distance_complete=compare("EqualEqual_IntInt",built_distances,"ReturnValue",7424,2560,count,"ReturnValue",kind="int");focal_complete=compare("EqualEqual_IntInt",built_focals,"ReturnValue",7424,2720,count,"ReturnValue",kind="int");complete=boolean("BooleanAND",distance_complete,focal_complete,7648,2640);complete_guard=b.add("complete_guard","branch",7872,2240);bp.connect(loop,"Completed",complete_guard,"execute");bp.connect(complete,"ReturnValue",complete_guard,"Condition");clear_failure=set_("CameraDollyFailureCodeV1","string",8096,2240,"");publish=set_("CameraDollyCandidateValidV1","bool",8320,2240,"true");bp.connect(complete_guard,"then",clear_failure,"execute");bp.connect(clear_failure,"then",publish,"execute")
    full="\n".join(node.text for node in b.nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
    if args.paste_output:args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:])+"\n",encoding="utf-8")


if __name__=="__main__":main()
