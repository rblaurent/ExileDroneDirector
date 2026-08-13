"""Build fail-closed compiled flight-profile validation and indexed evaluation."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="EvaluateCompiledFlightProfileV1"
TARGET_CLASS='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
CHANNELS=(("Ids","string","Id"),("PathFollowWeights","real","PathFollowWeight"),("HorizonStabilizationWeights","real","HorizonStabilizationWeight"),("LookAheadSeconds","real","LookAheadSeconds"),("BankGains","real","BankGain"),("MaxBankDegrees","real","MaxBankDegrees"),("CameraUptiltDegrees","real","CameraUptiltDegrees"),("MaxAngularRatesDegreesPerSecond","real","MaxAngularRateDegreesPerSecond"),("MaxAccelerationsCmPerSecondSquared","real","MaxAccelerationCmPerSecondSquared"),("MaxJerksCmPerSecondCubed","real","MaxJerkCmPerSecondCubed"),("MinimumTurnRadiiCm","real","MinimumTurnRadiusCm"))
BOUNDS=(("0.0","1.0",True),("0.0","1.0",True),("0.0","5.0",True),("0.0","2.0",True),("0.0","85.0",True),("-45.0","45.0",True),("0.0","720.0",False),("0.0","10000.0",False),("0.0","50000.0",False),("0.0","100000.0",False))

def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_flight_profile_evaluator_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def pk(n,p,k,a=False):
 c,s={"bool":("bool",""),"int":("int",""),"real":("real","double"),"string":("string","")}[k]
 def f(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{c}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{s}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")','PinType.PinSubCategoryObject=None',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if a else "None"}',line,1)
 n.mutate_pin(p,f)

def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args()
 s=load(a.project_root);bp=s.load_helpers(a.project_root);forms=s.load_templates(a.project_root,bp);sync=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph");edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");play=bp.read_blocks(a.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");repo=bp.read_blocks(a.project_root/"tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph");forms.update({"foreach":bp.find_block(sync,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),"length":bp.find_block(edit,r'MemberName="Array_Length"'),"item":bp.find_block(play,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),"call":bp.find_block(repo,r'MemberName="ValidateRecordV1"')});b=s.Builder(bp,forms,FUNCTION)
 def var(n,name,k,arr=False):
  s.retarget_variable(n,name,"real" if k=="int" else k);pk(n,name,k,arr)
  if "Output_Get" in n.pins:pk(n,"Output_Get",k)
 def get(name,k,x,y,arr=False):n=b.add(f"g{len(b.nodes)}","get",x,y);var(n,name,k,arr);return n
 def setv(name,k,x,y,d=None):
  n=b.add(f"s{len(b.nodes)}","set",x,y);var(n,name,k)
  if d is not None:s.set_default(n,name,d)
  return n
 def length(src,pin,k,x,y):n=b.add(f"l{len(b.nodes)}","length",x,y);pk(n,"TargetArray",k,True);bp.connect(src,pin,n,"TargetArray");return n
 def item(src,pin,k,idx,ip,x,y):n=b.add(f"i{len(b.nodes)}","item",x,y);pk(n,"Array",k,True);pk(n,"Output",k);bp.connect(src,pin,n,"Array");bp.connect(idx,ip,n,"Dimension 1");return n
 def cmp(member,l,lp,r,rp,k,x,y):
  n=b.add(f"c{len(b.nodes)}","compare",x,y);s.retarget_function(n,member)
  # Retarget both the function reference and the hidden self/Target pin. A
  # partial retarget survives a warm compile but warns during cold rebuild.
  if member=="EqualEqual_StrStr":n.text=n.text.replace("/Script/Engine.KismetMathLibrary","/Script/Engine.KismetStringLibrary")
  for p0 in ("A","B"):pk(n,p0,k)
  pk(n,"ReturnValue","bool");bp.connect(l,lp,n,"A")
  if r is None:s.set_default(n,"B",rp)
  else:bp.connect(r,rp,n,"B")
  return n
 def ands(gs,x,y):
  n,p0=gs[0]
  for j,(g,gp) in enumerate(gs[1:]):n=cmp("BooleanAND",n,p0,g,gp,"bool",x+j*224,y);p0="ReturnValue"
  return n,p0
 def call(name,x,y):
  n=b.add(f"call{name}","call",x,y);n.text=re.sub(r'FunctionReference=\([^\n]*\)',f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);n.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET_CLASS}",line,1));return n

 reset_specs=(("FlightProfileEvaluationStageValidV1","bool","false"),("FlightProfileResultIdV1","string",""),("FlightProfileResultPathFollowWeightV1","real","0.0"),("FlightProfileResultHorizonStabilizationWeightV1","real","0.0"),("FlightProfileResultLookAheadSecondsV1","real","0.0"),("FlightProfileResultBankGainV1","real","0.0"),("FlightProfileResultMaxBankDegreesV1","real","0.0"),("FlightProfileResultCameraUptiltDegreesV1","real","0.0"),("FlightProfileResultMaxAngularRateDegreesPerSecondV1","real","0.0"),("FlightProfileResultMaxAccelerationCmPerSecondSquaredV1","real","0.0"),("FlightProfileResultMaxJerkCmPerSecondCubedV1","real","0.0"),("FlightProfileResultMinimumTurnRadiusCmV1","real","0.0"),("FlightProfileResultValidV1","bool","false"))
 resets=[setv(n,k,256+j*320,2304,d) for j,(n,k,d) in enumerate(reset_specs)];bp.connect(b.entry,"then",resets[0],"execute")
 for l,r in zip(resets,resets[1:]):bp.connect(l,"then",r,"execute")
 compiled=[];lens=[]
 for j,(suf,k,_rs) in enumerate(CHANNELS):
  name=f"FlightProfileCompiled{suf}V1";g=get(name,k,0,j*160,True);compiled.append(g);lens.append(length(g,name,k,320,j*160))
 valid=get("FlightProfileCompileValidV1","bool",0,1840);index=get("FlightProfileInputSegmentIndexV1","int",0,2000);count=lens[0]
 guards=[(valid,"FlightProfileCompileValidV1"),(cmp("GreaterEqual_IntInt",count,"ReturnValue",None,"1","int",576,1760),"ReturnValue"),(cmp("LessEqual_IntInt",count,"ReturnValue",None,"511","int",576,1920),"ReturnValue"),(cmp("GreaterEqual_IntInt",index,"FlightProfileInputSegmentIndexV1",None,"0","int",576,2080),"ReturnValue"),(cmp("Less_IntInt",index,"FlightProfileInputSegmentIndexV1",count,"ReturnValue","int",576,2240),"ReturnValue")]
 for ln in lens[1:]:guards.append((cmp("EqualEqual_IntInt",ln,"ReturnValue",count,"ReturnValue","int",832,len(guards)*144),"ReturnValue"))
 ready,rp=ands(guards,1088,1760);pre=b.add("pre","branch",4448,2304);bp.connect(resets[-1],"then",pre,"execute");bp.connect(ready,rp,pre,"Condition")
 stage_true=setv("FlightProfileEvaluationStageValidV1","bool",4704,2304,"true");bp.connect(pre,"then",stage_true,"execute")
 loop=b.add("loop","foreach",4960,1840);pk(loop,"Array","string",True);pk(loop,"Array Element","string");bp.connect(compiled[0],"FlightProfileCompiledIdsV1",loop,"Array");bp.connect(stage_true,"then",loop,"Exec")
 rid=setv("FlightProfileResolveInputIdV1","string",5216,2304);bp.connect(loop,"Array Element",rid,"FlightProfileResolveInputIdV1");bp.connect(loop,"LoopBody",rid,"execute");resolver=call("ResolveFlightProfilePresetV1",5472,2304);bp.connect(rid,"then",resolver,"execute")
 rv=get("FlightProfileResolveResultValidV1","bool",5728,1760);r_id=get("FlightProfileResolveResultIdV1","string",5728,1920);eqid=cmp("EqualEqual_StrStr",r_id,"FlightProfileResolveResultIdV1",loop,"Array Element","string",5984,1920);igs=[(rv,"FlightProfileResolveResultValidV1"),(eqid,"ReturnValue")]
 for j,((suf,k,rs),cg) in enumerate(zip(CHANNELS[1:],compiled[1:])):
  cn=f"FlightProfileCompiled{suf}V1";rn=f"FlightProfileResolveResult{rs}V1";it=item(cg,cn,k,loop,"Array Index",5728,j*144);rg=get(rn,k,5984,j*144);igs.append((cmp("EqualEqual_DoubleDouble",it,"Output",rg,rn,"real",6240,j*144),"ReturnValue"))
  lower,upper,inclusive=BOUNDS[j];igs.append((cmp("GreaterEqual_DoubleDouble" if inclusive else "Greater_DoubleDouble",it,"Output",None,lower,"real",6464,j*144),"ReturnValue"));igs.append((cmp("LessEqual_DoubleDouble",it,"Output",None,upper,"real",6688,j*144),"ReturnValue"))
 integrity,ip=ands(igs,6912,1760);ib=b.add("integrity","branch",14016,2304);bp.connect(resolver,"then",ib,"execute");bp.connect(integrity,ip,ib,"Condition");fail=setv("FlightProfileEvaluationStageValidV1","bool",14272,2688,"false");bp.connect(pre,"else",fail,"execute");bp.connect(ib,"else",fail,"execute")
 stage=get("FlightProfileEvaluationStageValidV1","bool",14272,1920);final=b.add("final","branch",14528,2304);bp.connect(loop,"Completed",final,"execute");bp.connect(stage,"FlightProfileEvaluationStageValidV1",final,"Condition")
 pubs=[]
 for j,((suf,k,rs),cg) in enumerate(zip(CHANNELS,compiled)):
  cn=f"FlightProfileCompiled{suf}V1";out=item(cg,cn,k,index,"FlightProfileInputSegmentIndexV1",14784,j*144);rn=f"FlightProfileResult{rs}V1";sv=setv(rn,k,15040+j*288,2304);bp.connect(out,"Output",sv,rn);pubs.append(sv)
 bp.connect(final,"then",pubs[0],"execute")
 for l,r in zip(pubs,pubs[1:]):bp.connect(l,"then",r,"execute")
 done=setv("FlightProfileResultValidV1","bool",18240,2304,"true");bp.connect(pubs[-1],"then",done,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
 if a.paste_output:
  body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
