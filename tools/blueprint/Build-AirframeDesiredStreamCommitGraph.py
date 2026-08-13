"""Build atomic desired-stream handoff into the accepted prebake compiler."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="CommitAirframeDesiredStreamToPrebakeV1"
TARGET_CLASS='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
CANDIDATES=(("AirframeDesiredStreamCandidateLookAheadVelocitiesV1","vector",None),("AirframeDesiredStreamCandidateBodyQuatsV1","quat","AirframePrebakeInputDesiredBodyQuatsV1"),("AirframeDesiredStreamCandidateGimbalQuatsV1","quat","AirframePrebakeInputDesiredGimbalQuatsV1"),("AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1","real","AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"))

def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_desired_commit_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(n,p,k,array=False):
 c,sc,o={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),"quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"')}[k]
 def f(l):
  l=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{c}"',l,1);l=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{sc}"',l,1);l=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f"PinType.PinSubCategoryObject={o}",l,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',l,1)
 n.mutate_pin(p,f)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();s=load(x.project_root);bp=s.load_helpers(x.project_root);forms=s.load_templates(x.project_root,bp)
 edit=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");calls=bp.read_blocks(x.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");forms.update({"length":bp.find_block(edit,r'MemberName="Array_Length"'),"self_call":bp.find_block(calls,r'MemberName="SwitchToDroneView"')});b=s.Builder(bp,forms,FUNCTION)
 def var(n,name,k,array=False): s.retarget_variable(n,name,"vector" if k=="quat" else ("real" if k=="int" else k));kind(n,name,k,array);kind(n,"Output_Get",k) if "Output_Get" in n.pins else None
 def get(name,k,X,Y,array=False): n=b.add(f"get_{name}_{len(b.nodes)}","get",X,Y);var(n,name,k,array);return n
 def set_(name,k,X,Y,value=None,array=False): n=b.add(f"set_{name}_{len(b.nodes)}","set",X,Y);var(n,name,k,array);s.set_default(n,name,value) if value is not None else None;return n
 def length(src,p,k,X,Y): n=b.add(f"length_{len(b.nodes)}","length",X,Y);kind(n,"TargetArray",k,True);bp.connect(src,p,n,"TargetArray");return n
 def compare(member,l,lp,r,rp,k,X,Y): n=b.add(f"cmp_{len(b.nodes)}","compare",X,Y);s.retarget_function(n,member);kind(n,"A",k);kind(n,"B",k);kind(n,"ReturnValue","bool");bp.connect(l,lp,n,"A");bp.connect(r,rp,n,"B") if r else s.set_default(n,"B",rp);return n
 def and_(l,lp,r,rp,X,Y): return compare("BooleanAND",l,lp,r,rp,"bool",X,Y)
 def call(name,X,Y):
  n=b.add(f"call_{name}","self_call",X,Y);n.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);n.mutate_pin("self",lambda l:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET_CLASS}",l,1));return n
 reset=set_("AirframeDesiredStreamCompileValidV1","bool",256,2400,"false");bp.connect(b.entry,"then",reset,"execute")
 getters=[];lengths=[]
 for i,(name,k,_target) in enumerate(CANDIDATES): g=get(name,k,0,i*192,True);getters.append(g);lengths.append(length(g,name,k,320,i*192))
 count=lengths[1];stage=get("AirframeDesiredStreamStageValidV1","bool",0,896);idx=get("AirframeDesiredStreamStageIndexV1","int",0,1056)
 minimum=compare("GreaterEqual_IntInt",count,"ReturnValue",None,"2","int",640,192);maximum=compare("LessEqual_IntInt",count,"ReturnValue",None,"65536","int",640,320)
 minus=b.math("Subtract_DoubleDouble",640,1056);s.retarget_function(minus,"Subtract_IntInt");[kind(minus,p,"int") for p in ("A","B","ReturnValue")];bp.connect(count,"ReturnValue",minus,"A");s.set_default(minus,"B","1")
 terminal=compare("EqualEqual_IntInt",idx,"AirframeDesiredStreamStageIndexV1",minus,"ReturnValue","int",896,1056)
 guards=[(stage,"AirframeDesiredStreamStageValidV1"),(minimum,"ReturnValue"),(maximum,"ReturnValue"),(terminal,"ReturnValue")]
 for i,L in enumerate(lengths):
  if L is count: continue
  eq=compare("EqualEqual_IntInt",L,"ReturnValue",count,"ReturnValue","int",640,512+i*128);guards.append((eq,"ReturnValue"))
 current,pin=guards[0]
 for i,(g,gp) in enumerate(guards[1:]): current=and_(current,pin,g,gp,1216+i*224,1056);pin="ReturnValue"
 pre=b.add("preflight","branch",2752,2400);bp.connect(reset,"then",pre,"execute");bp.connect(current,pin,pre,"Condition")
 publications=[]
 for i,((source,k,target),g) in enumerate(zip(CANDIDATES,getters)):
  if target is None: continue
  n=set_(target,k,3008+len(publications)*288,2400,array=True);bp.connect(g,source,n,target);publications.append(n)
 total=get("AirframeDesiredStreamInputTotalSecondsV1","real",0,1280);step=get("AirframeDesiredStreamInputFixedStepSecondsV1","real",0,1440)
 set_total=set_("AirframePrebakeInputTotalSecondsV1","real",3872,2400);set_step=set_("AirframePrebakeInputFixedStepSecondsV1","real",4128,2400);bp.connect(total,"AirframeDesiredStreamInputTotalSecondsV1",set_total,"AirframePrebakeInputTotalSecondsV1");bp.connect(step,"AirframeDesiredStreamInputFixedStepSecondsV1",set_step,"AirframePrebakeInputFixedStepSecondsV1")
 chain=[*publications,set_total,set_step];bp.connect(pre,"then",chain[0],"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(chain,chain[1:])]
 compile_call=call("CompileAirframePrebakeV1",4384,2400);bp.connect(chain[-1],"then",compile_call,"execute");down=get("AirframePrebakeCompileValidV1","bool",4384,2080);guard=b.add("downstream_guard","branch",4640,2400);bp.connect(compile_call,"then",guard,"execute");bp.connect(down,"AirframePrebakeCompileValidV1",guard,"Condition");publish=set_("AirframeDesiredStreamCompileValidV1","bool",4896,2400,"true");bp.connect(guard,"then",publish,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:
  body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
