"""Build the bounded iterative adaptive arc-table work-stack processor."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

FUNCTION="ProcessAdaptiveArcBuildV1"
WORK=(("TrajectoryArcBuildWorkU0V1","real"),("TrajectoryArcBuildWorkU1V1","real"),("TrajectoryArcBuildWorkP0V1","vector"),("TrajectoryArcBuildWorkP1V1","vector"),("TrajectoryArcBuildWorkDepthV1","int"))

def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_arc_process_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(n,p,v,array=False):
 c,s,o={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[v]
 def f(x):
  x=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{c}"',x,1);x=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{s}"',x,1);x=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f"PinType.PinSubCategoryObject={o}",x,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',x,1)
 n.mutate_pin(p,f)
def variable(s,n,name,v,array=False):
 s.retarget_variable(n,name,"vector" if v=="vector" else "real");kind(n,name,v,array)
 if "Output_Get" in n.pins:kind(n,"Output_Get",v)

def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();s=load(a.project_root);bp=s.load_helpers(a.project_root);forms=s.load_templates(a.project_root,bp);b=s.Builder(bp,forms,FUNCTION)
 edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");play=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");capture=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");probe=bp.read_blocks(a.project_root/"tools/blueprint/templates/adaptive-arc-process-node-forms.eddgraph");loop_probe=bp.read_blocks(a.project_root/"tools/blueprint/templates/adaptive-arc-forloop-node-form.eddgraph");clean=bp.read_blocks(a.project_root/"tools/blueprint/templates/conan-clean-frame-node-forms.eddgraph");repo=bp.read_blocks(a.project_root/"tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
 templ={"length":bp.find_block(edit,r'MemberName="Array_Length"'),"remove":bp.find_block(edit,r'MemberName="Array_Remove"'),"item":bp.find_block(play,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),"add":bp.find_block(capture,r'MemberName="Array_Add"'),"loop":bp.find_block(loop_probe,r"StandardMacros:ForLoop"),"vadd":bp.find_block(probe,r'MemberName="Add_VectorVector"'),"vdist":bp.find_block(probe,r'MemberName="Vector_Distance"'),"vmul":bp.find_block(bp.read_blocks(a.project_root/"tools/blueprint/snippets/apply-translation-input.eddgraph"),r'MemberName="Multiply_VectorVector"'),"select":bp.find_block(clean,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),"call":bp.find_block(repo,r'MemberName="ValidateRecordV1"')}
 def add(key,t,x,y):
  q=templ[t];m=bp.BLOCK_RE.match(q);c=m.group("class").rsplit(".",1)[-1];i=b.serial.get(c,0);b.serial[c]=i+1;n=bp.Node.clone(key,q,f"{c}_{i}",x,y);b.nodes.append(n);return n
 def get(name,v,x,y,array=False):n=b.get(name,"vector" if v=="vector" else "real",x,y);variable(s,n,name,v,array);return n
 def setv(name,v,x,y,default=None):n=b.set(name,"vector" if v=="vector" else "real",x,y,default);variable(s,n,name,v);return n
 def arrnode(t,v,x,y,key):n=add(key,t,x,y);kind(n,"TargetArray" if t!="item" else "Array",v,True);return n
 def math(member,l,lp,r,rp,x,y,v="real"):
  n=b.math(member,x,y);s.retarget_function(n,member);[kind(n,z,v) for z in ("A","B","ReturnValue")];bp.connect(l,lp,n,"A");bp.connect(r,rp,n,"B") if r else s.set_default(n,"B",rp);return n
 def compare(member,l,lp,r,rp,x,y,v):
  n=b.add(f"cmp_{len(b.nodes)}","compare",x,y);s.retarget_function(n,member);kind(n,"A",v);kind(n,"B",v);kind(n,"ReturnValue","bool");bp.connect(l,lp,n,"A");bp.connect(r,rp,n,"B") if r else s.set_default(n,"B",rp);return n
 def and_(l,r,x,y):return compare("BooleanAND",l,"ReturnValue",r,"ReturnValue",x,y,"bool")
 def or_(l,r,x,y):return compare("BooleanOR",l,"ReturnValue",r,"ReturnValue",x,y,"bool")
 def append(src,name,v,value,pin,x,y,key):n=arrnode("add",v,x,y,key);bp.connect(src,name,n,"TargetArray");bp.connect(value,pin,n,"NewItem");return n

 arrays={name:get(name,v,0,80+i*128,True) for i,(name,v) in enumerate(WORK)}
 cand_u=get("TrajectoryArcBuildCandidateUsV1","real",0,800,True);cand_p=get("TrajectoryArcBuildCandidatePositionsV1","vector",0,928,True);cand_d=get("TrajectoryArcBuildCandidateDistancesV1","real",0,1056,True)
 stage=get("TrajectoryArcBuildStageValidV1","bool",0,1216);stage_wrap=b.add("stage_wrap","compare",256,1120);s.retarget_function(stage_wrap,"BooleanAND");kind(stage_wrap,"A","bool");kind(stage_wrap,"B","bool");kind(stage_wrap,"ReturnValue","bool");bp.connect(stage,"TrajectoryArcBuildStageValidV1",stage_wrap,"A");s.set_default(stage_wrap,"B","true");maxops=get("TrajectoryArcBuildInputMaxOperationsV1","int",0,1344);last=math("Subtract_IntInt",maxops,"TrajectoryArcBuildInputMaxOperationsV1",None,"1",256,1344,"int")
 preflight_lengths=[]
 for i,(name,v) in enumerate(WORK):
  n=arrnode("length",v,512+i*224,1056,f"preflight_work_length_{i}");bp.connect(arrays[name],name,n,"TargetArray");preflight_lengths.append(n)
 for i,(source,name,v) in enumerate(((cand_u,"TrajectoryArcBuildCandidateUsV1","real"),(cand_p,"TrajectoryArcBuildCandidatePositionsV1","vector"),(cand_d,"TrajectoryArcBuildCandidateDistancesV1","real"))):
  n=arrnode("length",v,512+(i+5)*224,1056,f"preflight_candidate_length_{i}");bp.connect(source,name,n,"TargetArray");preflight_lengths.append(n)
 preflight=stage_wrap
 for i,n in enumerate(preflight_lengths):
  exact=compare("EqualEqual_IntInt",n,"ReturnValue",None,"1",512+i*224,1216,"int");preflight=and_(preflight,exact,512+i*224,1344)
 preflight_branch=b.add("preflight_branch","branch",2304,1536);bp.connect(b.entry,"then",preflight_branch,"execute");bp.connect(preflight,"ReturnValue",preflight_branch,"Condition");preflight_fail=setv("TrajectoryArcBuildStageValidV1","bool",2560,1792,"false");bp.connect(preflight_branch,"else",preflight_fail,"execute")
 loop=add("bounded_loop","loop",2560,1536);bp.connect(preflight_branch,"then",loop,"execute");bp.connect(last,"ReturnValue",loop,"LastIndex")
 length=arrnode("length","real",768,1792,"work_length");bp.connect(arrays[WORK[0][0]],WORK[0][0],length,"TargetArray");nonempty=compare("Greater_IntInt",length,"ReturnValue",None,"0",1024,1792,"int");active=and_(stage_wrap,nonempty,1280,1792);guard=b.add("active_guard","branch",1536,1536);bp.connect(loop,"LoopBody",guard,"execute");bp.connect(active,"ReturnValue",guard,"Condition");index=math("Subtract_IntInt",length,"ReturnValue",None,"1",1280,992,"int")
 current_names=("TrajectoryArcBuildCurrentU0V1","TrajectoryArcBuildCurrentU1V1","TrajectoryArcBuildCurrentP0V1","TrajectoryArcBuildCurrentP1V1","TrajectoryArcBuildCurrentDepthV1")
 setters=[]
 for i,((name,v),current) in enumerate(zip(WORK,current_names)):
  item=arrnode("item",v,1536+i*256,720,f"item_{i}");kind(item,"Output",v);bp.connect(arrays[name],name,item,"Array");bp.connect(index,"ReturnValue",item,"Dimension 1");st=setv(current,v,1792+i*256,1920);bp.connect(item,"Output",st,current);setters.append(st)
 bp.connect(guard,"then",setters[0],"execute")
 for l,r in zip(setters,setters[1:]):bp.connect(l,"then",r,"execute")
 # Length/index are pure and may be reevaluated between impure removes. Keep
 # U0, the length owner, intact until the other synchronized stacks consume
 # that last index; remove U0 last.
 removes=[]
 for order,i in enumerate((1,2,3,4,0)):
  name,v=WORK[i];n=arrnode("remove",v,3072+order*256,1536,f"remove_{i}");bp.connect(arrays[name],name,n,"TargetArray");bp.connect(index,"ReturnValue",n,"IndexToRemove");removes.append(n)
 bp.connect(setters[-1],"then",removes[0],"execute")
 for l,r in zip(removes,removes[1:]):bp.connect(l,"then",r,"execute")
 op=get("TrajectoryArcBuildOperationCountV1","int",3072,992);opplus=math("Add_IntInt",op,"TrajectoryArcBuildOperationCountV1",None,"1",3328,992,"int");setop=setv("TrajectoryArcBuildOperationCountV1","int",4352,1536);bp.connect(opplus,"ReturnValue",setop,"TrajectoryArcBuildOperationCountV1");bp.connect(removes[-1],"then",setop,"execute")
 u0=get(current_names[0],"real",3840,720);u1=get(current_names[1],"real",3840,848);usum=math("Add_DoubleDouble",u0,current_names[0],u1,current_names[1],4096,720);midcalc=math("Multiply_DoubleDouble",usum,"ReturnValue",None,"0.5",4352,720);setmidu=setv("TrajectoryArcBuildMidpointUV1","real",4608,1536);bp.connect(midcalc,"ReturnValue",setmidu,"TrajectoryArcBuildMidpointUV1");bp.connect(setop,"then",setmidu,"execute");stagealpha=setv("TrajectoryInputAlphaV1","real",4864,1536);bp.connect(midcalc,"ReturnValue",stagealpha,"TrajectoryInputAlphaV1");bp.connect(setmidu,"then",stagealpha,"execute")
 primitive=add("primitive","call",5120,1536);primitive.text=re.sub(r'FunctionReference=\([^\n]*\)','FunctionReference=(MemberName="EvaluateQuinticVectorV1",bSelfContext=True)',primitive.text,1);bp.connect(stagealpha,"then",primitive,"execute");pvalid=get("TrajectoryResultVectorValidV1","bool",5120,1216);pguard=b.add("primitive_guard","branch",5376,1536);bp.connect(primitive,"then",pguard,"execute");bp.connect(pvalid,"TrajectoryResultVectorValidV1",pguard,"Condition")
 p0=get(current_names[2],"vector",4608,720);p1=get(current_names[3],"vector",4608,848);vadd=add("linear_add","vadd",4864,720);bp.connect(p0,current_names[2],vadd,"A");bp.connect(p1,current_names[3],vadd,"B");vmul=add("linear_half","vmul",5120,720);s.set_default(vmul,"B","0.5");bp.connect(vadd,"ReturnValue",vmul,"A")
 presult=get("TrajectoryResultPositionVectorV1","vector",5376,720);linear=get("TrajectoryArcBuildInputLinearV1","bool",5376,848);select=add("midpoint_select","select",5632,720)
 for pin in ("Option 0","Option 1","ReturnValue"):kind(select,pin,"vector")
 kind(select,"Index","bool");bp.connect(presult,"TrajectoryResultPositionVectorV1",select,"Option 0");bp.connect(vmul,"ReturnValue",select,"Option 1");bp.connect(linear,"TrajectoryArcBuildInputLinearV1",select,"Index")
 setmidp=setv("TrajectoryArcBuildMidpointPositionV1","vector",5632,1536);bp.connect(select,"ReturnValue",setmidp,"TrajectoryArcBuildMidpointPositionV1");bp.connect(pguard,"then",setmidp,"execute");fail=setv("TrajectoryArcBuildStageValidV1","bool",5632,1792,"false");bp.connect(pguard,"else",fail,"execute")
 midp=get("TrajectoryArcBuildMidpointPositionV1","vector",5888,720);dch=add("chord","vdist",6144,720);bp.connect(p0,current_names[2],dch,"V1");bp.connect(p1,current_names[3],dch,"V2");dl=add("left_distance","vdist",6144,848);bp.connect(p0,current_names[2],dl,"V1");bp.connect(midp,"TrajectoryArcBuildMidpointPositionV1",dl,"V2");dr=add("right_distance","vdist",6144,976);bp.connect(midp,"TrajectoryArcBuildMidpointPositionV1",dr,"V1");bp.connect(p1,current_names[3],dr,"V2");poly=math("Add_DoubleDouble",dl,"ReturnValue",dr,"ReturnValue",6400,848);error=math("Subtract_DoubleDouble",poly,"ReturnValue",dch,"ReturnValue",6656,848);tol=get("TrajectoryArcBuildInputToleranceV1","real",6400,1104);errbig=compare("Greater_DoubleDouble",error,"ReturnValue",tol,"TrajectoryArcBuildInputToleranceV1",6912,848,"real");depth=get(current_names[4],"int",6400,1232);maxdepth=get("TrajectoryArcBuildInputMaxDepthV1","int",6400,1360);belowmax=compare("Less_IntInt",depth,current_names[4],maxdepth,"TrajectoryArcBuildInputMaxDepthV1",6656,1232,"int");belowfloor=compare("Less_IntInt",depth,current_names[4],None,"6",6656,1360,"int");reason=or_(belowfloor,errbig,7168,1072);refine=and_(belowmax,reason,7424,1072);branch=b.add("refine_branch","branch",5888,1536);bp.connect(setmidp,"then",branch,"execute");bp.connect(refine,"ReturnValue",branch,"Condition");nextdepth=math("Add_IntInt",depth,current_names[4],None,"1",6912,1232,"int")
 # Right interval first, then left, preserving recursive left-first pop order.
 pushes=[]
 specs=((WORK[0],midcalc,"ReturnValue"),(WORK[1],u1,current_names[1]),(WORK[2],midp,"TrajectoryArcBuildMidpointPositionV1"),(WORK[3],p1,current_names[3]),(WORK[4],nextdepth,"ReturnValue"),(WORK[0],u0,current_names[0]),(WORK[1],midcalc,"ReturnValue"),(WORK[2],p0,current_names[2]),(WORK[3],midp,"TrajectoryArcBuildMidpointPositionV1"),(WORK[4],nextdepth,"ReturnValue"))
 for i,((name,v),src,pin) in enumerate(specs):pushes.append(append(arrays[name],name,v,src,pin,7680+i*256,1536,f"push_{i}"))
 bp.connect(branch,"then",pushes[0],"execute")
 for l,r in zip(pushes,pushes[1:]):bp.connect(l,"then",r,"execute")
 oldlen=get("TrajectoryArcBuildCandidateLengthV1","real",7680,2096);newlen=math("Add_DoubleDouble",oldlen,"TrajectoryArcBuildCandidateLengthV1",dch,"ReturnValue",7936,2096);accept=(append(cand_u,"TrajectoryArcBuildCandidateUsV1","real",u1,current_names[1],7680,2304,"accept_u"),append(cand_p,"TrajectoryArcBuildCandidatePositionsV1","vector",p1,current_names[3],7936,2304,"accept_p"),append(cand_d,"TrajectoryArcBuildCandidateDistancesV1","real",newlen,"ReturnValue",8192,2304,"accept_d"),setv("TrajectoryArcBuildCandidateLengthV1","real",8448,2304))
 bp.connect(branch,"else",accept[0],"execute");bp.connect(newlen,"ReturnValue",accept[3],"TrajectoryArcBuildCandidateLengthV1")
 for l,r in zip(accept,accept[1:]):bp.connect(l,"then",r,"execute")
 final_len=arrnode("length","real",768,2752,"final_length");bp.connect(arrays[WORK[0][0]],WORK[0][0],final_len,"TargetArray");empty=compare("EqualEqual_IntInt",final_len,"ReturnValue",None,"0",1024,2752,"int");final_stage=get("TrajectoryArcBuildStageValidV1","bool",1024,2880);done_wrap=b.add("done_wrap","compare",1024,2944);s.retarget_function(done_wrap,"BooleanAND");kind(done_wrap,"A","bool");kind(done_wrap,"B","bool");kind(done_wrap,"ReturnValue","bool");bp.connect(final_stage,"TrajectoryArcBuildStageValidV1",done_wrap,"A");s.set_default(done_wrap,"B","true");done=and_(done_wrap,empty,1280,2752);setdone=setv("TrajectoryArcBuildStageValidV1","bool",1536,2752);bp.connect(done,"ReturnValue",setdone,"TrajectoryArcBuildStageValidV1");bp.connect(loop,"Completed",setdone,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
 if a.paste_output:
  body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
