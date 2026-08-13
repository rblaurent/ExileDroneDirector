"""Build atomic source-sample handoff into the accepted desired-stream compiler."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="CommitAirframeSourceSamplesToDesiredV1"
TARGET='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
ARRAYS=(
 ("AirframeSourceCandidatePositionsV1","vector","AirframeDesiredStreamInputPositionsV1"),
 ("AirframeSourceCandidateBodyQuatsV1","quat","AirframeDesiredStreamInputAuthoredBodyQuatsV1"),
 ("AirframeSourceCandidateGimbalQuatsV1","quat","AirframeDesiredStreamInputAuthoredGimbalQuatsV1"),
 ("AirframeSourceCandidatePathFollowWeightsV1","real","AirframeDesiredStreamInputPathFollowWeightsV1"),
 ("AirframeSourceCandidateHorizonStabilizationWeightsV1","real","AirframeDesiredStreamInputHorizonStabilizationWeightsV1"),
 ("AirframeSourceCandidateLookAheadSecondsV1","real","AirframeDesiredStreamInputLookAheadSecondsV1"),
 ("AirframeSourceCandidateBankGainsV1","real","AirframeDesiredStreamInputBankGainsV1"),
 ("AirframeSourceCandidateMaxBankDegreesV1","real","AirframeDesiredStreamInputMaxBankDegreesV1"),
 ("AirframeSourceCandidateCameraUptiltDegreesV1","real","AirframeDesiredStreamInputCameraUptiltDegreesV1"),
 ("AirframeSourceCandidateMaxAngularRatesDegreesPerSecondV1","real","AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1"),
 ("AirframeSourceCandidateMaxAccelerationsCmPerSecondSquaredV1","real","AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1"),
 ("AirframeSourceCandidateMaxJerksCmPerSecondCubedV1","real","AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1"),
 ("AirframeSourceCandidateMinimumTurnRadiiCmV1","real","AirframeDesiredStreamInputMinimumTurnRadiiCmV1"),
)
def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_source_commit_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(n,p,k,array=False):
 c,sc,o={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),"quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"')}[k]
 def f(l):
  l=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{c}"',l,1);l=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{sc}"',l,1);l=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f"PinType.PinSubCategoryObject={o}",l,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',l,1)
 n.mutate_pin(p,f)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();s=load(x.project_root);bp=s.load_helpers(x.project_root);forms=s.load_templates(x.project_root,bp)
 edit=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");calls=bp.read_blocks(x.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");forms.update({"length":bp.find_block(edit,r'MemberName="Array_Length"'),"self_call":bp.find_block(calls,r'MemberName="SwitchToDroneView"')});b=s.Builder(bp,forms,FUNCTION)
 def var(n,name,k,array=False):
  s.retarget_variable(n,name,"vector" if k=="quat" else ("real" if k=="int" else k));kind(n,name,k,array)
  if "Output_Get" in n.pins:kind(n,"Output_Get",k,array)
 def get(name,k,X,Y,array=False):n=b.add(f"get_{name}_{len(b.nodes)}","get",X,Y);var(n,name,k,array);return n
 def set_(name,k,X,Y,value=None,array=False):
  n=b.add(f"set_{name}_{len(b.nodes)}","set",X,Y);var(n,name,k,array)
  if value is not None:s.set_default(n,name,value)
  return n
 def length(src,p,k,X,Y):n=b.add(f"length_{len(b.nodes)}","length",X,Y);kind(n,"TargetArray",k,True);kind(n,"ReturnValue","int");bp.connect(src,p,n,"TargetArray");return n
 def cmp(member,l,lp,X,Y,r=None,rp=None,default=None,k="int"):
  n=b.add(f"cmp_{member}_{len(b.nodes)}","compare",X,Y);s.retarget_function(n,member);kind(n,"A",k);kind(n,"B",k);kind(n,"ReturnValue","bool");bp.connect(l,lp,n,"A");bp.connect(r,rp,n,"B") if r else s.set_default(n,"B",default);return n
 def and_all(values,X,Y):
  cur,pin=values[0]
  for i,(other,op) in enumerate(values[1:]):cur=cmp("BooleanAND",cur,pin,X+i*224,Y,other,op,k="bool");pin="ReturnValue"
  return cur
 def call(name,X,Y):
  n=b.add(f"call_{name}","self_call",X,Y);n.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);n.mutate_pin("self",lambda l:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET}",l,1));return n
 invalidate=set_("AirframeSourceCompileValidV1","bool",256,3200,"false");bp.connect(b.entry,"then",invalidate,"execute")
 getters=[];lengths=[]
 for i,(name,k,_target) in enumerate(ARRAYS):
  g=get(name,k,0,i*144,True);getters.append(g);lengths.append(length(g,name,k,320,i*144))
 count=lengths[0];stage=get("AirframeSourceStageValidV1","bool",0,2032);expected=get("AirframeSourceExpectedSampleCountV1","int",0,2192)
 guards=[(stage,"AirframeSourceStageValidV1"),(cmp("GreaterEqual_IntInt",count,"ReturnValue",640,0,default="2"),"ReturnValue"),(cmp("LessEqual_IntInt",count,"ReturnValue",640,144,default="65536"),"ReturnValue"),(cmp("EqualEqual_IntInt",count,"ReturnValue",640,288,expected,"AirframeSourceExpectedSampleCountV1"),"ReturnValue")]
 for i,L in enumerate(lengths[1:]):guards.append((cmp("EqualEqual_IntInt",L,"ReturnValue",640,432+i*144,count,"ReturnValue"),"ReturnValue"))
 valid=and_all(guards,992,2880);pre=b.add("preflight","branch",4608,3200);bp.connect(invalidate,"then",pre,"execute");bp.connect(valid,"ReturnValue",pre,"Condition")
 publications=[]
 for (source,k,target),g in zip(ARRAYS,getters):
  n=set_(target,k,4864+len(publications)*256,3200,array=True);bp.connect(g,source,n,target);publications.append(n)
 total=get("AirframeSourceTotalSecondsV1","real",0,2352);step=get("AirframeSourceInputFixedStepSecondsV1","real",0,2512)
 set_total=set_("AirframeDesiredStreamInputTotalSecondsV1","real",8192,3200);set_step=set_("AirframeDesiredStreamInputFixedStepSecondsV1","real",8448,3200);bp.connect(total,"AirframeSourceTotalSecondsV1",set_total,"AirframeDesiredStreamInputTotalSecondsV1");bp.connect(step,"AirframeSourceInputFixedStepSecondsV1",set_step,"AirframeDesiredStreamInputFixedStepSecondsV1")
 chain=[*publications,set_total,set_step];bp.connect(pre,"then",chain[0],"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(chain,chain[1:])]
 compile_call=call("CompileAirframeDesiredStreamV1",8704,3200);bp.connect(chain[-1],"then",compile_call,"execute")
 desired=get("AirframeDesiredStreamCompileValidV1","bool",8704,2720);prebake=get("AirframePrebakeCompileValidV1","bool",8704,2880);down=cmp("BooleanAND",desired,"AirframeDesiredStreamCompileValidV1",8960,2800,prebake,"AirframePrebakeCompileValidV1",k="bool")
 down_guard=b.add("downstream_guard","branch",9216,3200);bp.connect(compile_call,"then",down_guard,"execute");bp.connect(down,"ReturnValue",down_guard,"Condition");publish=set_("AirframeSourceCompileValidV1","bool",9472,3200,"true");bp.connect(down_guard,"then",publish,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:
  body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
