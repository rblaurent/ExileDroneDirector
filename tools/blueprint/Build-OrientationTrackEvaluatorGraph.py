"""Build scrub-safe absolute-time evaluation of a compiled orientation track."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "EvaluateCompiledOrientationTrackV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'

def load(root):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_orientation_eval_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def kind(node,pin,value,array=False):
    category,subcategory,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[value]
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)

def variable(scalar,node,name,value,array=False):
    scalar.retarget_variable(node,name,"vector" if value in ("quat","vector") else ("real" if value=="int" else value));kind(node,name,value,array)
    if "Output_Get" in node.pins:kind(node,"Output_Get",value)

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
    sync=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph");edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");playback=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");repository=bp.read_blocks(a.project_root/"tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    foreach_form=bp.find_block(sync,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance");length_form=bp.find_block(edit,r'MemberName="Array_Length"');item_form=bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem");call_form=bp.find_block(repository,r'MemberName="ValidateRecordV1"')
    def add(key,form,x,y):
        m=bp.BLOCK_RE.match(form);cls=m.group("class").rsplit(".",1)[-1];i=b.serial.get(cls,0);b.serial[cls]=i+1;node=bp.Node.clone(key,form,f"{cls}_{i}",x,y);b.nodes.append(node);return node
    def base(value):return "vector" if value in ("quat","vector") else ("real" if value=="int" else value)
    def get(name,value,x,y,array=False):node=b.get(name,base(value),x,y);variable(scalar,node,name,value,array);return node
    def setv(name,value,x,y,default=None):node=b.set(name,base(value),x,y,default);variable(scalar,node,name,value);return node
    def item(source,pin,value,index,index_pin,x,y,key):node=add(key,item_form,x,y);kind(node,"Array",value,True);kind(node,"Output",value);bp.connect(source,pin,node,"Array");bp.connect(index,index_pin,node,"Dimension 1");return node
    def length(source,pin,value,x,y,key):node=add(key,length_form,x,y);kind(node,"TargetArray",value,True);bp.connect(source,pin,node,"TargetArray");return node
    def compare(member,left,left_pin,right,right_pin,x,y,value):
        node=b.add(f"cmp_{len(b.nodes)}","compare",x,y);scalar.retarget_function(node,member)
        for pin in ("A","B"):kind(node,pin,value)
        kind(node,"ReturnValue","bool");bp.connect(left,left_pin,node,"A")
        if right is None:scalar.set_default(node,"B",right_pin)
        else:bp.connect(right,right_pin,node,"B")
        return node
    def and_(left,right,x,y):return compare("BooleanAND",left,"ReturnValue",right,"ReturnValue",x,y,"bool")
    def math(member,left,left_pin,right,right_pin,x,y,value="real"):
        node=b.math(member,x,y);scalar.retarget_function(node,member)
        for pin in ("A","B","ReturnValue"):kind(node,pin,value)
        bp.connect(left,left_pin,node,"A")
        if right is None:scalar.set_default(node,"B",right_pin)
        else:bp.connect(right,right_pin,node,"B")
        return node

    reset=[setv("OrientationTrackResultSegmentIndexV1","int",256,1800,"-1"),setv("OrientationTrackResultAlphaV1","real",512,1800,"0.0"),setv("OrientationTrackResultQuatV1","quat",768,1800,"0, 0, 0, 1"),setv("OrientationTrackResultCompleteV1","bool",1024,1800,"false"),setv("OrientationTrackResultValidV1","bool",1280,1800,"false")]
    # A prior primitive result must never remain observable after a failed
    # track evaluation.  Reset the primitive's transactional boundary too.
    reset.extend((setv("TrajectoryResultOrientationQuatV1","quat",1536,1800,"0, 0, 0, 1"),setv("TrajectoryResultOrientationValidV1","bool",1792,1800,"false")))
    bp.connect(b.entry,"then",reset[0],"execute")
    for left,right in zip(reset,reset[1:]):bp.connect(left,"then",right,"execute")
    elapsed=get("OrientationTrackInputElapsedSecondsV1","real",0,80);elapsed_finite=b.finite(elapsed,"OrientationTrackInputElapsedSecondsV1",256,80);compile_valid=get("OrientationTrackCompileValidV1","bool",0,320);compile_wrap=b.add("compile_wrap","compare",512,320);scalar.retarget_function(compile_wrap,"BooleanAND");[kind(compile_wrap,p,"bool") for p in ("A","B","ReturnValue")];bp.connect(compile_valid,"OrientationTrackCompileValidV1",compile_wrap,"A");scalar.set_default(compile_wrap,"B","true")
    durations=get("OrientationTrackCompiledDurationsV1","real",0,560,True);starts=get("OrientationTrackCompiledSegmentStartsV1","real",0,720,True);start_controls=get("OrientationTrackCompiledStartControlsV1","quat",0,880,True);end_controls=get("OrientationTrackCompiledEndControlsV1","quat",0,1040,True);aligned=get("OrientationTrackCompiledAlignedQuatsV1","quat",0,1200,True);tangents=get("OrientationTrackCompiledTangentRatesV1","vector",0,1360,True);total=get("OrientationTrackCompiledTotalSecondsV1","real",0,1520)
    specs=((durations,"OrientationTrackCompiledDurationsV1","real"),(starts,"OrientationTrackCompiledSegmentStartsV1","real"),(start_controls,"OrientationTrackCompiledStartControlsV1","quat"),(end_controls,"OrientationTrackCompiledEndControlsV1","quat"),(aligned,"OrientationTrackCompiledAlignedQuatsV1","quat"),(tangents,"OrientationTrackCompiledTangentRatesV1","vector"))
    lens=[length(*spec,512+i*224,560,f"len_{i}") for i,spec in enumerate(specs)]
    d_positive=compare("Greater_IntInt",lens[0],"ReturnValue",None,"0",512,1520,"int");plus_one=math("Add_IntInt",lens[0],"ReturnValue",None,"1",736,1520,"int")
    guards=[elapsed_finite,compile_wrap,d_positive,compare("EqualEqual_IntInt",lens[1],"ReturnValue",lens[0],"ReturnValue",960,1520,"int"),compare("EqualEqual_IntInt",lens[2],"ReturnValue",lens[0],"ReturnValue",1184,1520,"int"),compare("EqualEqual_IntInt",lens[3],"ReturnValue",lens[0],"ReturnValue",1408,1520,"int"),compare("EqualEqual_IntInt",lens[4],"ReturnValue",plus_one,"ReturnValue",1632,1520,"int"),compare("EqualEqual_IntInt",lens[5],"ReturnValue",plus_one,"ReturnValue",1856,1520,"int"),b.finite(total,"OrientationTrackCompiledTotalSecondsV1",2080,1520),compare("Greater_DoubleDouble",total,"OrientationTrackCompiledTotalSecondsV1",None,"0.0",2304,1520,"real")]
    combined=guards[0]
    for i,guard in enumerate(guards[1:]):combined=and_(combined,guard,2528+i*208,1520)
    outer=b.add("outer","branch",4608,1800);bp.connect(reset[-1],"then",outer,"execute");bp.connect(combined,"ReturnValue",outer,"Condition")
    complete_cmp=compare("GreaterEqual_DoubleDouble",elapsed,"OrientationTrackInputElapsedSecondsV1",total,"OrientationTrackCompiledTotalSecondsV1",4832,1520,"real");complete_branch=b.add("complete_branch","branch",4832,1800);bp.connect(outer,"then",complete_branch,"execute");bp.connect(complete_cmp,"ReturnValue",complete_branch,"Condition")
    last_segment=math("Subtract_IntInt",lens[0],"ReturnValue",None,"1",5056,1120,"int");end_quat=item(aligned,"OrientationTrackCompiledAlignedQuatsV1","quat",lens[0],"ReturnValue",5280,1120,"end_quat")
    complete_chain=[setv("OrientationTrackResultSegmentIndexV1","int",5056,1800),setv("OrientationTrackResultAlphaV1","real",5312,1800,"1.0"),setv("OrientationTrackResultQuatV1","quat",5568,1800),setv("OrientationTrackResultCompleteV1","bool",5824,1800,"true"),setv("OrientationTrackResultValidV1","bool",6080,1800,"true")]
    bp.connect(complete_branch,"then",complete_chain[0],"execute");bp.connect(last_segment,"ReturnValue",complete_chain[0],"OrientationTrackResultSegmentIndexV1");bp.connect(end_quat,"Output",complete_chain[2],"OrientationTrackResultQuatV1")
    for left,right in zip(complete_chain,complete_chain[1:]):bp.connect(left,"then",right,"execute")
    loop=add("loop",foreach_form,5056,2320);kind(loop,"Array","real",True);kind(loop,"Array Element","real");bp.connect(durations,"OrientationTrackCompiledDurationsV1",loop,"Array");bp.connect(complete_branch,"else",loop,"Exec")
    start=item(starts,"OrientationTrackCompiledSegmentStartsV1","real",loop,"Array Index",5312,2160,"start");end=math("Add_DoubleDouble",start,"Output",loop,"Array Element",5568,2160);before_end=compare("Less_DoubleDouble",elapsed,"OrientationTrackInputElapsedSecondsV1",end,"ReturnValue",5824,2160,"real");result_index=get("OrientationTrackResultSegmentIndexV1","int",5312,2560);unset=compare("EqualEqual_IntInt",result_index,"OrientationTrackResultSegmentIndexV1",None,"-1",5568,2560,"int");choose=and_(before_end,unset,6080,2320);choose_branch=b.add("choose_branch","branch",6336,2320);bp.connect(loop,"LoopBody",choose_branch,"execute");bp.connect(choose,"ReturnValue",choose_branch,"Condition");store_index=setv("OrientationTrackResultSegmentIndexV1","int",6592,2320);bp.connect(choose_branch,"then",store_index,"execute");bp.connect(loop,"Array Index",store_index,"OrientationTrackResultSegmentIndexV1")
    selected=get("OrientationTrackResultSegmentIndexV1","int",6336,2800);found=compare("GreaterEqual_IntInt",selected,"OrientationTrackResultSegmentIndexV1",None,"0",6592,2800,"int");found_branch=b.add("found_branch","branch",6848,2480);bp.connect(loop,"Completed",found_branch,"execute");bp.connect(found,"ReturnValue",found_branch,"Condition")
    selected_start=item(starts,"OrientationTrackCompiledSegmentStartsV1","real",selected,"OrientationTrackResultSegmentIndexV1",6848,2960,"selected_start");selected_duration=item(durations,"OrientationTrackCompiledDurationsV1","real",selected,"OrientationTrackResultSegmentIndexV1",6848,3120,"selected_duration");q0=item(aligned,"OrientationTrackCompiledAlignedQuatsV1","quat",selected,"OrientationTrackResultSegmentIndexV1",6848,3280,"q0");c0=item(start_controls,"OrientationTrackCompiledStartControlsV1","quat",selected,"OrientationTrackResultSegmentIndexV1",6848,3440,"c0");c1=item(end_controls,"OrientationTrackCompiledEndControlsV1","quat",selected,"OrientationTrackResultSegmentIndexV1",6848,3600,"c1");next_index=math("Add_IntInt",selected,"OrientationTrackResultSegmentIndexV1",None,"1",7104,3760,"int");q1=item(aligned,"OrientationTrackCompiledAlignedQuatsV1","quat",next_index,"ReturnValue",7360,3760,"q1")
    duration_finite=b.finite(selected_duration,"Output",7104,2960);duration_positive=compare("Greater_DoubleDouble",selected_duration,"Output",None,"0.0",7104,3200,"real");duration_valid=and_(duration_finite,duration_positive,7360,3040);duration_branch=b.add("duration_branch","branch",7616,2480);bp.connect(found_branch,"then",duration_branch,"execute");bp.connect(duration_valid,"ReturnValue",duration_branch,"Condition")
    clamped=b.add("clamped_elapsed","clamp",7616,3360);scalar.set_default(clamped,"Min","0.0");bp.connect(elapsed,"OrientationTrackInputElapsedSecondsV1",clamped,"Value");bp.connect(total,"OrientationTrackCompiledTotalSecondsV1",clamped,"Max");relative=math("Subtract_DoubleDouble",clamped,"ReturnValue",selected_start,"Output",7872,3360);alpha=math("Divide_DoubleDouble",relative,"ReturnValue",selected_duration,"Output",8128,3360)
    staged=[]
    for name,value,source,pin in (("TrajectoryInputAlphaV1","real",alpha,"ReturnValue"),("TrajectoryInputOrientationStartQuatV1","quat",q0,"Output"),("TrajectoryInputOrientationStartControlQuatV1","quat",c0,"Output"),("TrajectoryInputOrientationEndControlQuatV1","quat",c1,"Output"),("TrajectoryInputOrientationEndQuatV1","quat",q1,"Output")):
        node=setv(name,value,7872+len(staged)*256,2480);bp.connect(source,pin,node,name);staged.append(node)
    bp.connect(duration_branch,"then",staged[0],"execute")
    for left,right in zip(staged,staged[1:]):bp.connect(left,"then",right,"execute")
    primitive=add("primitive",call_form,9152,2480);primitive.text=re.sub(r'FunctionReference=\([^\n]*\)','FunctionReference=(MemberName="EvaluateSphericalBezierQuaternionV1",bSelfContext=True)',primitive.text,1);primitive.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET_CLASS}",line,1));bp.connect(staged[-1],"then",primitive,"execute")
    primitive_valid=get("TrajectoryResultOrientationValidV1","bool",9408,2240);primitive_guard=b.add("primitive_guard","branch",9664,2480);bp.connect(primitive,"then",primitive_guard,"execute");bp.connect(primitive_valid,"TrajectoryResultOrientationValidV1",primitive_guard,"Condition");primitive_quat=get("TrajectoryResultOrientationQuatV1","quat",9664,2240)
    accept=[setv("OrientationTrackResultAlphaV1","real",9920,2480),setv("OrientationTrackResultQuatV1","quat",10176,2480),setv("OrientationTrackResultCompleteV1","bool",10432,2480,"false"),setv("OrientationTrackResultValidV1","bool",10688,2480,"true")];bp.connect(primitive_guard,"then",accept[0],"execute");bp.connect(alpha,"ReturnValue",accept[0],"OrientationTrackResultAlphaV1");bp.connect(primitive_quat,"TrajectoryResultOrientationQuatV1",accept[1],"OrientationTrackResultQuatV1")
    for left,right in zip(accept,accept[1:]):bp.connect(left,"then",right,"execute")
    failure_roots=(found_branch,"else",duration_branch,"else",primitive_guard,"else")
    for i in range(0,len(failure_roots),2):
        chain=[setv("OrientationTrackResultSegmentIndexV1","int",7872+i*192,4160+i*80,"-1"),setv("OrientationTrackResultAlphaV1","real",8128+i*192,4160+i*80,"0.0"),setv("OrientationTrackResultQuatV1","quat",8384+i*192,4160+i*80,"0, 0, 0, 1"),setv("OrientationTrackResultCompleteV1","bool",8640+i*192,4160+i*80,"false"),setv("OrientationTrackResultValidV1","bool",8896+i*192,4160+i*80,"false")];bp.connect(failure_roots[i],failure_roots[i+1],chain[0],"execute")
        for left,right in zip(chain,chain[1:]):bp.connect(left,"then",right,"execute")
    full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
