"""Build deterministic endpoint/interior orientation tangent-rate assembly."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "ComputeOrientationTrackTangentRatesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_track_tangent_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def kind(node,pin,value,array=False):
    category,subcategory,obj={
        "bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),
        "quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[value]
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1)
        line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1)
        line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)


def variable(scalar,node,name,value,array=False):
    scalar.retarget_variable(node,name,"vector" if value in ("quat","vector") else value);kind(node,name,value,array)
    if "Output_Get" in node.pins:kind(node,"Output_Get",value)


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args()
    scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
    sync=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    capture=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset=bp.read_blocks(a.project_root/"tools/blueprint/snippets/reset-orientation-track-candidate-v1.eddgraph")
    repository=bp.read_blocks(a.project_root/"tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    foreach_form=bp.find_block(sync,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance");add_form=bp.find_block(capture,r'MemberName="Array_Add"')
    length_form=bp.find_block(edit,r'MemberName="Array_Length"');getitem_form=bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")
    clear_form=bp.find_block(reset,r'MemberName="Array_Clear"');call_form=bp.find_block(repository,r'MemberName="ValidateRecordV1"')
    def add(key,form,x,y):
        m=bp.BLOCK_RE.match(form);cls=m.group("class").rsplit(".",1)[-1];i=b.serial.get(cls,0);b.serial[cls]=i+1
        node=bp.Node.clone(key,form,f"{cls}_{i}",x,y);b.nodes.append(node);return node
    def get_array(name,value,x,y):
        node=b.get(name,"vector" if value=="vector" else "real",x,y);variable(scalar,node,name,value,True);return node
    def item(source,name,value,index,index_pin,x,y,key):
        node=add(key,getitem_form,x,y);kind(node,"Array",value,True);kind(node,"Output",value);bp.connect(source,name,node,"Array");bp.connect(index,index_pin,node,"Dimension 1");return node
    def arithmetic(member,x,y,bvalue):
        node=b.math(member,x,y);scalar.retarget_function(node,member)
        for pin in ("A","B","ReturnValue"):kind(node,pin,"int")
        scalar.set_default(node,"B",bvalue);return node
    def self_call(x,y,key):
        node=add(key,call_form,x,y);node.text=re.sub(r'FunctionReference=\([^\n]*\)','FunctionReference=(MemberName="ComputeOrientationTangentRateV1",bSelfContext=True)',node.text,1)
        node.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET_CLASS}",line,1));return node

    candidate=get_array("OrientationTrackCandidateTangentRatesV1","vector",0,800);clear=add("clear",clear_form,256,1600);kind(clear,"TargetArray","vector",True);bp.connect(candidate,"OrientationTrackCandidateTangentRatesV1",clear,"TargetArray");bp.connect(b.entry,"then",clear,"execute")
    stage=b.get("OrientationTrackStageValidV1","bool",256,1280);outer=b.add("outer","branch",512,1600);bp.connect(clear,"then",outer,"execute");bp.connect(stage,"OrientationTrackStageValidV1",outer,"Condition")
    aligned=get_array("OrientationTrackCandidateAlignedQuatsV1","quat",768,160);loop=add("loop",foreach_form,1024,480);kind(loop,"Array","quat",True);kind(loop,"Array Element","quat");bp.connect(aligned,"OrientationTrackCandidateAlignedQuatsV1",loop,"Array");bp.connect(outer,"then",loop,"Exec")
    inner=b.add("inner","branch",1296,960);bp.connect(loop,"LoopBody",inner,"execute");bp.connect(stage,"OrientationTrackStageValidV1",inner,"Condition")
    length=add("length",length_form,1024,160);kind(length,"TargetArray","quat",True);bp.connect(aligned,"OrientationTrackCandidateAlignedQuatsV1",length,"TargetArray")
    last_index=arithmetic("Subtract_IntInt",1296,160,"1");bp.connect(length,"ReturnValue",last_index,"A")
    first_cmp=b.add("first_cmp","compare",1552,640);scalar.retarget_function(first_cmp,"EqualEqual_IntInt")
    for pin in ("A","B"):kind(first_cmp,pin,"int")
    kind(first_cmp,"ReturnValue","bool");scalar.set_default(first_cmp,"B","0");bp.connect(loop,"Array Index",first_cmp,"A")
    first_branch=b.add("first_branch","branch",1808,960);bp.connect(inner,"then",first_branch,"execute");bp.connect(first_cmp,"ReturnValue",first_branch,"Condition")
    last_cmp=b.add("last_cmp","compare",1808,1152);scalar.retarget_function(last_cmp,"EqualEqual_IntInt")
    for pin in ("A","B"):kind(last_cmp,pin,"int")
    kind(last_cmp,"ReturnValue","bool");bp.connect(loop,"Array Index",last_cmp,"A");bp.connect(last_index,"ReturnValue",last_cmp,"B")
    last_branch=b.add("last_branch","branch",2064,1120);bp.connect(first_branch,"else",last_branch,"execute");bp.connect(last_cmp,"ReturnValue",last_branch,"Condition")
    deltas=get_array("OrientationTrackCandidateForwardDeltasV1","vector",768,800);durations=get_array("OrientationTrackInputDurationsV1","real",768,1040)
    zero=arithmetic("Subtract_IntInt",2048,160,"0");scalar.set_default(zero,"A","0")
    prior=arithmetic("Subtract_IntInt",2048,320,"1");bp.connect(loop,"Array Index",prior,"A")

    def path(label,exec_source,exec_pin,prev_index,prev_pin,next_index,next_pin,x,y):
        pd=item(deltas,"OrientationTrackCandidateForwardDeltasV1","vector",prev_index,prev_pin,x,y,label+"_pd")
        nd=item(deltas,"OrientationTrackCandidateForwardDeltasV1","vector",next_index,next_pin,x,y+160,label+"_nd")
        pt=item(durations,"OrientationTrackInputDurationsV1","real",prev_index,prev_pin,x,y+320,label+"_pt")
        nt=item(durations,"OrientationTrackInputDurationsV1","real",next_index,next_pin,x,y+480,label+"_nt")
        setters=[]
        for name,value,source,pin in (
            ("OrientationInputPreviousDeltaVectorV1","vector",pd,"Output"),("OrientationInputNextDeltaVectorV1","vector",nd,"Output"),
            ("OrientationInputPreviousDurationV1","real",pt,"Output"),("OrientationInputNextDurationV1","real",nt,"Output")):
            node=b.set(name,"vector" if value=="vector" else "real",x+320,y+720+len(setters)*144);variable(scalar,node,name,value);bp.connect(source,pin,node,name);setters.append(node)
        bp.connect(exec_source,exec_pin,setters[0],"execute")
        for left,right in zip(setters,setters[1:]):bp.connect(left,"then",right,"execute")
        call=self_call(x+640,y+1152,label+"_call");bp.connect(setters[-1],"then",call,"execute")
        valid=b.get("OrientationResultValidV1","bool",x+896,y+1008);guard=b.add(label+"_guard","branch",x+1152,y+1152);bp.connect(call,"then",guard,"execute");bp.connect(valid,"OrientationResultValidV1",guard,"Condition")
        result=b.get("OrientationResultTangentRateVectorV1","vector",x+1152,y+960);append=add(label+"_append",add_form,x+1408,y+1040);kind(append,"TargetArray","vector",True);kind(append,"NewItem","vector");bp.connect(candidate,"OrientationTrackCandidateTangentRatesV1",append,"TargetArray");bp.connect(result,"OrientationResultTangentRateVectorV1",append,"NewItem");bp.connect(guard,"then",append,"execute")
        reject=b.set("OrientationTrackStageValidV1","bool",x+1408,y+1328,"false");bp.connect(guard,"else",reject,"execute")

    path("first",first_branch,"then",zero,"ReturnValue",zero,"ReturnValue",2320,0)
    path("last",last_branch,"then",prior,"ReturnValue",prior,"ReturnValue",2320,2200)
    path("middle",last_branch,"else",prior,"ReturnValue",loop,"Array Index",2320,4400)
    full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")

if __name__=="__main__":main()
