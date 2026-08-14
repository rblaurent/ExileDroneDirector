"""Build history-free absolute-time camera scalar-track evaluation."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

FUNCTION = "EvaluateCameraScalarTrackV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_scalar_evaluate_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def pin_kind(node, pin: str, kind: str, array: bool = False):
    category, subcategory = {"bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double"), "string": ("string", "")}[kind]
    def mutate(line: str):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1)
        line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1)
        line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',"PinType.PinSubCategoryObject=None",line,1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args()
    scalar=load(args.project_root);bp=scalar.load_helpers(args.project_root);forms=scalar.load_templates(args.project_root,bp)
    sync=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback=bp.read_blocks(args.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph")
    activate=bp.read_blocks(args.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({"foreach":bp.find_block(sync,r"K2Node_MacroInstance"),"length":bp.find_block(edit,r'MemberName="Array_Length"'),"item":bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),"call":bp.find_block(activate,r'MemberName="SwitchToDroneView"')})
    b=scalar.Builder(bp,forms,FUNCTION)

    def add_form(key,form,x,y):
        match=bp.BLOCK_RE.match(forms[form]);cls=match.group("class").rsplit(".",1)[-1];index=b.serial.get(cls,0);b.serial[cls]=index+1
        node=bp.Node.clone(key,forms[form],f"{cls}_{index}",x,y);b.nodes.append(node);return node
    def variable(node,name,kind,array=False):
        scalar.retarget_variable(node,name,"real" if kind=="int" else kind);pin_kind(node,name,kind,array)
        if "Output_Get" in node.pins:pin_kind(node,"Output_Get",kind)
    def get(name,kind,x,y,array=False):node=b.add(f"get_{name}_{len(b.nodes)}","get",x,y);variable(node,name,kind,array);return node
    def set_(name,kind,x,y,default=None):
        node=b.add(f"set_{name}_{len(b.nodes)}","set",x,y);variable(node,name,kind)
        if default is not None:scalar.set_default(node,name,default)
        return node
    def length(source,pin,kind,x,y):
        node=add_form(f"length_{len(b.nodes)}","length",x,y);pin_kind(node,"TargetArray",kind,True);pin_kind(node,"ReturnValue","int");bp.connect(source,pin,node,"TargetArray");return node
    def item(source,pin,kind,index,index_pin,x,y):
        node=add_form(f"item_{len(b.nodes)}","item",x,y);pin_kind(node,"Array",kind,True);pin_kind(node,"Output",kind);pin_kind(node,"Dimension 1","int");bp.connect(source,pin,node,"Array")
        if index is None:scalar.set_default(node,"Dimension 1",index_pin)
        else:bp.connect(index,index_pin,node,"Dimension 1")
        return node
    def foreach(source,pin,kind,x,y):
        node=add_form(f"foreach_{len(b.nodes)}","foreach",x,y);pin_kind(node,"Array",kind,True);pin_kind(node,"Array Element",kind);pin_kind(node,"Array Index","int");bp.connect(source,pin,node,"Array");return node
    def operation(member,left,left_pin,x,y,right=None,right_pin=None,default=None,kind="real",result=None):
        output=result or kind;node=b.add(f"op_{member}_{len(b.nodes)}","compare" if output=="bool" else "math",x,y);scalar.retarget_function(node,member)
        input_kind="bool" if member in ("BooleanAND","BooleanOR") else kind;pin_kind(node,"A",input_kind);pin_kind(node,"B",input_kind);pin_kind(node,"ReturnValue",output);bp.connect(left,left_pin,node,"A")
        if right is None:scalar.set_default(node,"B",default)
        else:bp.connect(right,right_pin,node,"B")
        return node
    def call(member,x,y):
        node=add_form(f"call_{member}_{len(b.nodes)}","call",x,y);node.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{member}",bSelfContext=True)',node.text,1)
        node.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET}",line,1));return node

    reset=call("ResetCameraScalarTrackResultV1",1808,1440);bp.connect(b.entry,"then",reset,"execute")
    compile_valid=get("CameraScalarTrackCompileValidV1","bool",0,0);query=get("CameraScalarTrackQueryTimeV1","real",0,128);finite_query=b.finite(query,"CameraScalarTrackQueryTimeV1",256,128)
    guard_condition=operation("BooleanAND",compile_valid,"CameraScalarTrackCompileValidV1",704,64,finite_query,"ReturnValue",kind="bool",result="bool")
    guard=b.add("query_guard","branch",928,2400);bp.connect(reset,"then",guard,"execute");bp.connect(guard_condition,"ReturnValue",guard,"Condition")
    values=get("CameraScalarTrackCandidateDomainValuesV1","real",0,384,True);count=length(values,"CameraScalarTrackCandidateDomainValuesV1","real",256,384)
    single=operation("EqualEqual_IntInt",count,"ReturnValue",480,384,default="1",kind="int",result="bool")
    duration=get("CameraScalarTrackInputDurationV1","real",0,512);query_complete=operation("GreaterEqual_DoubleDouble",query,"CameraScalarTrackQueryTimeV1",480,512,duration,"CameraScalarTrackInputDurationV1",result="bool")
    complete=operation("BooleanOR",single,"ReturnValue",704,448,query_complete,"ReturnValue",kind="bool",result="bool")
    set_complete=set_("CameraScalarTrackResultCompleteV1","bool",1152,2400);single_branch=b.add("single_branch","branch",1376,2400)
    bp.connect(guard,"then",set_complete,"execute");bp.connect(complete,"ReturnValue",set_complete,"CameraScalarTrackResultCompleteV1");bp.connect(set_complete,"then",single_branch,"execute");bp.connect(single,"ReturnValue",single_branch,"Condition")
    first_value=item(values,"CameraScalarTrackCandidateDomainValuesV1","real",None,"0",704,704)
    constant_alpha=set_("CameraScalarTrackResultLocalAlphaV1","real",1600,2240,"1.0");constant_value=set_("CameraScalarTrackScratchDomainValueV1","real",1824,2240);constant_velocity=set_("CameraScalarTrackScratchDomainVelocityV1","real",2048,2240,"0.0");constant_acceleration=set_("CameraScalarTrackScratchDomainAccelerationV1","real",2272,2240,"0.0");constant_valid=set_("CameraScalarTrackScratchValidV1","bool",2496,2240,"true");constant_publish=call("PublishCameraScalarTrackSampleV1",2720,2240)
    bp.connect(single_branch,"then",constant_alpha,"execute");bp.connect(constant_alpha,"then",constant_value,"execute");bp.connect(first_value,"Output",constant_value,"CameraScalarTrackScratchDomainValueV1")
    for left,right in zip((constant_value,constant_velocity,constant_acceleration,constant_valid),(constant_velocity,constant_acceleration,constant_valid,constant_publish)):bp.connect(left,"then",right,"execute")
    modes=get("CameraScalarTrackCandidateInterpolationModesV1","string",0,832,True);last_index=operation("Subtract_IntInt",count,"ReturnValue",480,832,default="2",kind="int")
    set_last=set_("CameraScalarTrackScratchIndexV1","int",1600,2560);set_over=set_("CameraScalarTrackScratchValidV1","bool",1824,2560);loop=foreach(modes,"CameraScalarTrackCandidateInterpolationModesV1","string",2048,2560)
    bp.connect(single_branch,"else",set_last,"execute");bp.connect(last_index,"ReturnValue",set_last,"CameraScalarTrackScratchIndexV1");bp.connect(set_last,"then",set_over,"execute");bp.connect(query_complete,"ReturnValue",set_over,"CameraScalarTrackScratchValidV1");bp.connect(set_over,"then",loop,"Exec")
    selected=get("CameraScalarTrackScratchValidV1","bool",2048,1024);not_selected=operation("EqualEqual_BoolBool",selected,"CameraScalarTrackScratchValidV1",2272,1024,default="false",kind="bool",result="bool")
    next_index=operation("Add_IntInt",loop,"Array Index",2272,1152,default="1",kind="int");times=get("CameraScalarTrackCandidateKeyTimesV1","real",0,1152,True);right_time=item(times,"CameraScalarTrackCandidateKeyTimesV1","real",next_index,"ReturnValue",2496,1152)
    before_right=operation("LessEqual_DoubleDouble",query,"CameraScalarTrackQueryTimeV1",2720,1152,right_time,"Output",result="bool");choose=operation("BooleanAND",not_selected,"ReturnValue",2944,1088,before_right,"ReturnValue",kind="bool",result="bool")
    choose_branch=b.add("choose_branch","branch",3168,2560);choose_index=set_("CameraScalarTrackScratchIndexV1","int",3392,2560);choose_valid=set_("CameraScalarTrackScratchValidV1","bool",3616,2560,"true")
    bp.connect(loop,"LoopBody",choose_branch,"execute");bp.connect(choose,"ReturnValue",choose_branch,"Condition");bp.connect(choose_branch,"then",choose_index,"execute");bp.connect(loop,"Array Index",choose_index,"CameraScalarTrackScratchIndexV1");bp.connect(choose_index,"then",choose_valid,"execute")
    evaluate_segment=call("EvaluateCameraScalarTrackSegmentV1",3392,2880);bp.connect(loop,"Completed",evaluate_segment,"execute")
    full="\n".join(node.text for node in b.nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
    if args.paste_output:
        paste="\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:])+"\n";args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text(paste,encoding="utf-8")


if __name__=="__main__":main()
