"""Build bounded extraction of one compiled route's flat arc-table slice."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="StagePositionRouteArcSliceV1"
def load(root):
    p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_position_arc_slice_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(node,pin,value,array=False):
    cat,sub={"bool":("bool",""),"int":("int",""),"real":("real","double")}[value]
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{cat}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{sub}"',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin,mutate)
def variable(scalar,node,name,value,array=False):
    scalar.retarget_variable(node,name,"real" if value=="int" else value);kind(node,name,value,array)
    if "Output_Get" in node.pins:kind(node,"Output_Get",value)
def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
    edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");play=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");capture=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");reset=bp.read_blocks(a.project_root/"tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph");loops=bp.read_blocks(a.project_root/"tools/blueprint/templates/adaptive-arc-forloop-node-form.eddgraph")
    template={"length":bp.find_block(edit,r'MemberName="Array_Length"'),"item":bp.find_block(play,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),"add":bp.find_block(capture,r'MemberName="Array_Add"'),"clear":bp.find_block(reset,r'MemberName="Array_Clear"'),"loop":bp.find_block(loops,r"StandardMacros:ForLoop")}
    def add(key,form,x,y):
        raw=template[form];m=bp.BLOCK_RE.match(raw);cls=m.group("class").rsplit(".",1)[-1];i=b.serial.get(cls,0);b.serial[cls]=i+1;n=bp.Node.clone(key,raw,f"{cls}_{i}",x,y);b.nodes.append(n);return n
    def get(name,value,x,y,array=False):n=b.get(name,"real" if value=="int" else value,x,y);variable(scalar,n,name,value,array);return n
    def setv(name,value,x,y,default=None):n=b.set(name,"real" if value=="int" else value,x,y,default);variable(scalar,n,name,value);return n
    def length(src,pin,value,x,y,key):n=add(key,"length",x,y);kind(n,"TargetArray",value,True);bp.connect(src,pin,n,"TargetArray");return n
    def item(src,pin,value,index,indexpin,x,y,key):n=add(key,"item",x,y);kind(n,"Array",value,True);kind(n,"Output",value);bp.connect(src,pin,n,"Array");bp.connect(index,indexpin,n,"Dimension 1");return n
    def arrayop(form,src,pin,value,x,y,key,new=None,newpin=None):
        n=add(key,form,x,y);kind(n,"TargetArray",value,True);bp.connect(src,pin,n,"TargetArray")
        if form=="add":kind(n,"NewItem",value);kind(n,"ReturnValue","int");bp.connect(new,newpin,n,"NewItem")
        return n
    def cmp(member,left,leftpin,right,rightpin,x,y,value):
        n=b.add(f"cmp_{len(b.nodes)}","compare",x,y);scalar.retarget_function(n,member)
        for pin in ("A","B"):kind(n,pin,value)
        kind(n,"ReturnValue","bool");bp.connect(left,leftpin,n,"A")
        if right is None:scalar.set_default(n,"B",rightpin)
        else:bp.connect(right,rightpin,n,"B")
        return n
    def math(member,left,leftpin,right,rightpin,x,y,value="int"):
        n=b.math(member,x,y);scalar.retarget_function(n,member)
        for pin in ("A","B","ReturnValue"):kind(n,pin,value)
        bp.connect(left,leftpin,n,"A")
        if right is None:scalar.set_default(n,"B",rightpin)
        else:bp.connect(right,rightpin,n,"B")
        return n
    def and_(left,right,x,y):return cmp("BooleanAND",left,"ReturnValue",right,"ReturnValue",x,y,"bool")

    out_us=get("TrajectoryArcInputUsV1","real",0,80,True);out_ds=get("TrajectoryArcInputDistancesV1","real",0,240,True)
    clears=(arrayop("clear",out_us,"TrajectoryArcInputUsV1","real",256,1760,"clear_us"),arrayop("clear",out_ds,"TrajectoryArcInputDistancesV1","real",512,1760,"clear_ds"),setv("TrajectoryArcInputLengthV1","real",768,1760,"0.0"),setv("TrajectoryArcInputDistanceAlphaV1","real",1024,1760,"0.0"),setv("TrajectoryArcResultUV1","real",1280,1760,"0.0"),setv("TrajectoryArcResultValidV1","bool",1536,1760,"false"))
    bp.connect(b.entry,"then",clears[0],"execute")
    for l,r in zip(clears,clears[1:]):bp.connect(l,"then",r,"execute")
    index=get("PositionRouteResultSegmentIndexV1","int",0,480);valid=get("PositionRouteCompileValidV1","bool",0,640);starts=get("PositionRouteCompiledArcSampleStartsV1","int",0,800,True);counts=get("PositionRouteCompiledArcSampleCountsV1","int",0,960,True);flat_us=get("PositionRouteCompiledArcUsV1","real",0,1120,True);flat_ds=get("PositionRouteCompiledArcDistancesV1","real",0,1280,True);lengths=get("PositionRouteCompiledSegmentLengthsV1","real",0,1440,True);distance_alpha=get("PositionRouteResultDistanceAlphaV1","real",0,1600)
    starts_len=length(starts,"PositionRouteCompiledArcSampleStartsV1","int",256,800,"starts_len");counts_len=length(counts,"PositionRouteCompiledArcSampleCountsV1","int",256,960,"counts_len");us_len=length(flat_us,"PositionRouteCompiledArcUsV1","real",256,1120,"us_len");ds_len=length(flat_ds,"PositionRouteCompiledArcDistancesV1","real",256,1280,"ds_len");lengths_len=length(lengths,"PositionRouteCompiledSegmentLengthsV1","real",256,1440,"lengths_len")
    conditions=[cmp("GreaterEqual_IntInt",index,"PositionRouteResultSegmentIndexV1",None,"0",512,480,"int"),cmp("Less_IntInt",index,"PositionRouteResultSegmentIndexV1",starts_len,"ReturnValue",736,480,"int"),cmp("EqualEqual_IntInt",counts_len,"ReturnValue",starts_len,"ReturnValue",512,800,"int"),cmp("EqualEqual_IntInt",lengths_len,"ReturnValue",starts_len,"ReturnValue",736,800,"int"),cmp("EqualEqual_IntInt",us_len,"ReturnValue",ds_len,"ReturnValue",960,800,"int"),b.finite(distance_alpha,"PositionRouteResultDistanceAlphaV1",1184,800),cmp("GreaterEqual_DoubleDouble",distance_alpha,"PositionRouteResultDistanceAlphaV1",None,"0.0",1408,800,"real"),cmp("LessEqual_DoubleDouble",distance_alpha,"PositionRouteResultDistanceAlphaV1",None,"1.0",1632,800,"real")]
    wrap=b.add("valid_wrap","compare",1840,800);scalar.retarget_function(wrap,"BooleanAND");[kind(wrap,p,"bool") for p in ("A","B","ReturnValue")];bp.connect(valid,"PositionRouteCompileValidV1",wrap,"A");scalar.set_default(wrap,"B","true");conditions.insert(0,wrap)
    ready=conditions[0]
    for i,c in enumerate(conditions[1:]):ready=and_(ready,c,2064+i*208,800)
    branch=b.add("ready_branch","branch",3728,1760);bp.connect(clears[-1],"then",branch,"execute");bp.connect(ready,"ReturnValue",branch,"Condition")
    start=item(starts,"PositionRouteCompiledArcSampleStartsV1","int",index,"PositionRouteResultSegmentIndexV1",2880,480,"start");count=item(counts,"PositionRouteCompiledArcSampleCountsV1","int",index,"PositionRouteResultSegmentIndexV1",2880,640,"count");length=item(lengths,"PositionRouteCompiledSegmentLengthsV1","real",index,"PositionRouteResultSegmentIndexV1",2880,800,"length");remaining=math("Subtract_IntInt",us_len,"ReturnValue",start,"Output",3136,560);count_ok=cmp("GreaterEqual_IntInt",count,"Output",None,"2",3392,480,"int");start_ok=cmp("GreaterEqual_IntInt",start,"Output",None,"0",3392,640,"int");end_ok=cmp("LessEqual_IntInt",count,"Output",remaining,"ReturnValue",3392,800,"int");length_finite=b.finite(length,"Output",3392,960);length_ok=cmp("GreaterEqual_DoubleDouble",length,"Output",None,"0.0",3616,960,"real");bounds=count_ok
    for i,c in enumerate((start_ok,end_ok,length_finite,length_ok)):bounds=and_(bounds,c,3840+i*208,800)
    bounds_branch=b.add("bounds_branch","branch",4672,1760);bp.connect(branch,"then",bounds_branch,"execute");bp.connect(bounds,"ReturnValue",bounds_branch,"Condition")
    last=math("Subtract_IntInt",count,"Output",None,"1",4672,640);loop=add("slice_loop","loop",4928,1760);scalar.set_default(loop,"FirstIndex","0");bp.connect(last,"ReturnValue",loop,"LastIndex");bp.connect(bounds_branch,"then",loop,"execute");flat_index=math("Add_IntInt",start,"Output",loop,"Index",5184,800);u=item(flat_us,"PositionRouteCompiledArcUsV1","real",flat_index,"ReturnValue",5440,720,"u");d=item(flat_ds,"PositionRouteCompiledArcDistancesV1","real",flat_index,"ReturnValue",5440,880,"d");add_u=arrayop("add",out_us,"TrajectoryArcInputUsV1","real",5696,1760,"add_u",u,"Output");add_d=arrayop("add",out_ds,"TrajectoryArcInputDistancesV1","real",5952,1760,"add_d",d,"Output");bp.connect(loop,"LoopBody",add_u,"execute");bp.connect(add_u,"then",add_d,"execute")
    store_len=setv("TrajectoryArcInputLengthV1","real",6208,1760);store_alpha=setv("TrajectoryArcInputDistanceAlphaV1","real",6464,1760);store_valid=setv("TrajectoryArcResultValidV1","bool",6720,1760,"true");bp.connect(loop,"Completed",store_len,"execute");bp.connect(length,"Output",store_len,"TrajectoryArcInputLengthV1");bp.connect(store_len,"then",store_alpha,"execute");bp.connect(distance_alpha,"PositionRouteResultDistanceAlphaV1",store_alpha,"TrajectoryArcInputDistanceAlphaV1");bp.connect(store_alpha,"then",store_valid,"execute")
    full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
