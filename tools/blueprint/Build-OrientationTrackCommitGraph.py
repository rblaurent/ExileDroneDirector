"""Build atomic publication of a fully assembled orientation track candidate."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "CommitCompiledOrientationTrackV1"

def load(root):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_track_commit_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def kind(node,pin,value,array=False):
    category,subcategory,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[value]
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)

def variable(scalar,node,name,value,array=False):
    scalar.retarget_variable(node,name,"vector" if value in ("quat","vector") else ("real" if value == "int" else value));kind(node,name,value,array)
    if "Output_Get" in node.pins:kind(node,"Output_Get",value)

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
    sync=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph");edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");playback=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");reset=bp.read_blocks(a.project_root/"tools/blueprint/snippets/reset-orientation-track-candidate-v1.eddgraph")
    foreach_form=bp.find_block(sync,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance");length_form=bp.find_block(edit,r'MemberName="Array_Length"');item_form=bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem");clear_form=bp.find_block(reset,r'MemberName="Array_Clear"')
    def add(key,form,x,y):
        m=bp.BLOCK_RE.match(form);cls=m.group("class").rsplit(".",1)[-1];i=b.serial.get(cls,0);b.serial[cls]=i+1;node=bp.Node.clone(key,form,f"{cls}_{i}",x,y);b.nodes.append(node);return node
    def base_kind(value): return "vector" if value in ("quat", "vector") else ("real" if value == "int" else value)
    def get(name,value,x,y,array=False):node=b.get(name,base_kind(value),x,y);variable(scalar,node,name,value,array);return node
    def setv(name,value,x,y,default=None,array=False):node=b.set(name,base_kind(value),x,y,default);variable(scalar,node,name,value,array);return node
    def length(source,pin,value,x,y,key):node=add(key,length_form,x,y);kind(node,"TargetArray",value,True);bp.connect(source,pin,node,"TargetArray");return node
    def compare(member,left,left_pin,right,right_pin,x,y,value):
        node=b.add(f"cmp_{len(b.nodes)}","compare",x,y);scalar.retarget_function(node,member)
        for pin in ("A","B"):kind(node,pin,value)
        kind(node,"ReturnValue","bool");bp.connect(left,left_pin,node,"A");
        if right is None:scalar.set_default(node,"B",right_pin)
        else:bp.connect(right,right_pin,node,"B")
        return node
    def and_(left,right,x,y):return compare("BooleanAND",left,"ReturnValue",right,"ReturnValue",x,y,"bool")

    compiled=(
        ("OrientationTrackCompiledAlignedQuatsV1","quat"),("OrientationTrackCompiledDurationsV1","real"),("OrientationTrackCompiledTangentRatesV1","vector"),("OrientationTrackCompiledSegmentStartsV1","real"),("OrientationTrackCompiledStartControlsV1","quat"),("OrientationTrackCompiledEndControlsV1","quat"),
    )
    reset_chain=[]; compiled_gets={}
    for i,(name,value) in enumerate(compiled):
        source=get(name,value,0,i*160,True);compiled_gets[name]=source;clear=add("clear_"+name,clear_form,256+i*256,1800);kind(clear,"TargetArray",value,True);bp.connect(source,name,clear,"TargetArray");reset_chain.append(clear)
    for name,value,default in (("OrientationTrackCompiledTotalSecondsV1","real","0.0"),("OrientationTrackCompileValidV1","bool","false"),("OrientationTrackResultSegmentIndexV1","int","-1"),("OrientationTrackResultAlphaV1","real","0.0"),("OrientationTrackResultQuatV1","quat","0, 0, 0, 1"),("OrientationTrackResultCompleteV1","bool","false"),("OrientationTrackResultValidV1","bool","false")):
        reset_chain.append(setv(name,value,256+len(reset_chain)*256,1800,default))
    bp.connect(b.entry,"then",reset_chain[0],"execute")
    for left,right in zip(reset_chain,reset_chain[1:]):bp.connect(left,"then",right,"execute")

    candidate_specs=(("OrientationTrackCandidateAlignedQuatsV1","quat"),("OrientationTrackInputDurationsV1","real"),("OrientationTrackCandidateTangentRatesV1","vector"),("OrientationTrackCandidateSegmentStartsV1","real"),("OrientationTrackCandidateStartControlsV1","quat"),("OrientationTrackCandidateEndControlsV1","quat"))
    candidates={name:get(name,value,0,2200+i*160,True) for i,(name,value) in enumerate(candidate_specs)}
    lengths={name:length(candidates[name],name,value,512+i*224,2200,f"len_{i}") for i,(name,value) in enumerate(candidate_specs)}
    qlen=lengths["OrientationTrackCandidateAlignedQuatsV1"];dlen=lengths["OrientationTrackInputDurationsV1"];tlen=lengths["OrientationTrackCandidateTangentRatesV1"];slen=lengths["OrientationTrackCandidateSegmentStartsV1"];sclen=lengths["OrientationTrackCandidateStartControlsV1"];eclen=lengths["OrientationTrackCandidateEndControlsV1"]
    qmin=compare("GreaterEqual_IntInt",qlen,"ReturnValue",None,"2",512,3200,"int")
    minus=b.math("Subtract_IntInt",736,3200);scalar.retarget_function(minus,"Subtract_IntInt");[kind(minus,pin,"int") for pin in ("A","B","ReturnValue")];scalar.set_default(minus,"B","1");bp.connect(qlen,"ReturnValue",minus,"A")
    conditions=[qmin,compare("EqualEqual_IntInt",dlen,"ReturnValue",minus,"ReturnValue",960,3200,"int"),compare("EqualEqual_IntInt",tlen,"ReturnValue",qlen,"ReturnValue",1184,3200,"int"),compare("EqualEqual_IntInt",slen,"ReturnValue",dlen,"ReturnValue",1408,3200,"int"),compare("EqualEqual_IntInt",sclen,"ReturnValue",dlen,"ReturnValue",1632,3200,"int"),compare("EqualEqual_IntInt",eclen,"ReturnValue",dlen,"ReturnValue",1856,3200,"int")]
    candidate_total=get("OrientationTrackCandidateTotalSecondsV1","real",2080,2400);total_finite=b.finite(candidate_total,"OrientationTrackCandidateTotalSecondsV1",2080,2880);total_positive=compare("Greater_DoubleDouble",candidate_total,"OrientationTrackCandidateTotalSecondsV1",None,"0.0",2304,3040,"real");conditions.extend((total_finite,total_positive))
    stage=get("OrientationTrackStageValidV1","bool",2528,2880);stage_wrap=b.add("stage_wrap","compare",2528,3200);scalar.retarget_function(stage_wrap,"BooleanAND");kind(stage_wrap,"A","bool");kind(stage_wrap,"B","bool");kind(stage_wrap,"ReturnValue","bool");bp.connect(stage,"OrientationTrackStageValidV1",stage_wrap,"A");scalar.set_default(stage_wrap,"B","true");conditions.append(stage_wrap)
    combined=conditions[0]
    for i,condition in enumerate(conditions[1:]):combined=and_(combined,condition,2752+i*224,3200)
    outer=b.add("outer","branch",4768,1800);bp.connect(reset_chain[-1],"then",outer,"execute");bp.connect(combined,"ReturnValue",outer,"Condition")
    outer_reject=setv("OrientationTrackStageValidV1","bool",4992,2040,"false");bp.connect(outer,"else",outer_reject,"execute")

    loop=add("loop",foreach_form,4992,2480);kind(loop,"Array","real",True);kind(loop,"Array Element","real");bp.connect(candidates["OrientationTrackInputDurationsV1"],"OrientationTrackInputDurationsV1",loop,"Array");bp.connect(outer,"then",loop,"Exec")
    start_item=add("start_item",item_form,5248,2320);kind(start_item,"Array","real",True);kind(start_item,"Output","real");bp.connect(candidates["OrientationTrackCandidateSegmentStartsV1"],"OrientationTrackCandidateSegmentStartsV1",start_item,"Array");bp.connect(loop,"Array Index",start_item,"Dimension 1")
    accumulator=get("OrientationTrackCompiledTotalSecondsV1","real",5248,2800);start_equal=compare("EqualEqual_DoubleDouble",start_item,"Output",accumulator,"OrientationTrackCompiledTotalSecondsV1",5504,2320,"real");duration_finite=b.finite(loop,"Array Element",5504,2560);duration_positive=compare("Greater_DoubleDouble",loop,"Array Element",None,"0.0",5504,2800,"real")
    stage_loop=b.add("stage_loop","compare",5504,3040);scalar.retarget_function(stage_loop,"BooleanAND");kind(stage_loop,"A","bool");kind(stage_loop,"B","bool");kind(stage_loop,"ReturnValue","bool");bp.connect(stage,"OrientationTrackStageValidV1",stage_loop,"A");scalar.set_default(stage_loop,"B","true")
    item_valid=and_(and_(start_equal,duration_finite,5760,2400),and_(duration_positive,stage_loop,5760,2880),6016,2640)
    item_guard=b.add("item_guard","branch",6272,2480);bp.connect(loop,"LoopBody",item_guard,"execute");bp.connect(item_valid,"ReturnValue",item_guard,"Condition")
    sum_total=b.math("Add_DoubleDouble",6528,2320);scalar.retarget_function(sum_total,"Add_DoubleDouble");[kind(sum_total,pin,"real") for pin in ("A","B","ReturnValue")];bp.connect(accumulator,"OrientationTrackCompiledTotalSecondsV1",sum_total,"A");bp.connect(loop,"Array Element",sum_total,"B")
    advance=setv("OrientationTrackCompiledTotalSecondsV1","real",6784,2480);bp.connect(item_guard,"then",advance,"execute");bp.connect(sum_total,"ReturnValue",advance,"OrientationTrackCompiledTotalSecondsV1")
    item_reject=setv("OrientationTrackStageValidV1","bool",6528,2800,"false");bp.connect(item_guard,"else",item_reject,"execute")
    total_equal=compare("EqualEqual_DoubleDouble",accumulator,"OrientationTrackCompiledTotalSecondsV1",candidate_total,"OrientationTrackCandidateTotalSecondsV1",6528,3200,"real");final_stage=b.add("final_stage","compare",6528,3440);scalar.retarget_function(final_stage,"BooleanAND");kind(final_stage,"A","bool");kind(final_stage,"B","bool");kind(final_stage,"ReturnValue","bool");bp.connect(stage,"OrientationTrackStageValidV1",final_stage,"A");scalar.set_default(final_stage,"B","true");final_valid=and_(total_equal,final_stage,6784,3280)
    final_guard=b.add("final_guard","branch",7040,2480);bp.connect(loop,"Completed",final_guard,"execute");bp.connect(final_valid,"ReturnValue",final_guard,"Condition")
    publish=[]
    for i,((source_name,value),(target_name,_)) in enumerate(zip(candidate_specs,compiled)):
        node=setv(target_name,value,7296+i*256,2320,array=True);bp.connect(candidates[source_name],source_name,node,target_name);publish.append(node)
    bp.connect(final_guard,"then",publish[0],"execute")
    for left,right in zip(publish,publish[1:]):bp.connect(left,"then",right,"execute")
    accept=setv("OrientationTrackCompileValidV1","bool",7296+len(publish)*256,2320,"true");bp.connect(publish[-1],"then",accept,"execute")
    fail_total=setv("OrientationTrackCompiledTotalSecondsV1","real",7296,2800,"0.0");fail_stage=setv("OrientationTrackStageValidV1","bool",7552,2800,"false");bp.connect(final_guard,"else",fail_total,"execute");bp.connect(fail_total,"then",fail_stage,"execute")
    full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
