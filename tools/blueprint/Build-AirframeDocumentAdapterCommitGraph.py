"""Build atomic v2 document handoff into the accepted source sampler."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="CommitAirframeDocumentSourceAdapterV2"
TARGET='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
MAPPINGS=(("AirframeDocumentInputWaypointPositionsV2","vector","PositionRouteInputWaypointPositionsV1"),("AirframeDocumentInputSegmentDurationsV2","real","PositionRouteInputDurationsV1"),("AirframeDocumentInputSegmentSpatialCurveTypesV2","string","PositionRouteInputSpatialCurveTypesV1"),("AirframeDocumentInputSegmentTimeProfilesV2","string","PositionRouteInputTimeProfilesV1"),("AirframeDocumentInputDefaultFlightProfileV2","string","FlightProfileInputDefaultIdV1"),("AirframeDocumentInputSegmentFlightProfileOverridesV2","string","FlightProfileInputSegmentOverrideIdsV1"),("AirframeDocumentInputWaypointBodyQuatsV2","quat","AirframeSourceInputBodyWaypointQuatsV1"),("AirframeDocumentInputWaypointGimbalQuatsV2","quat","AirframeSourceInputGimbalWaypointQuatsV1"),("AirframeDocumentInputFixedStepSecondsV2","real","AirframeSourceInputFixedStepSecondsV1"))
def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_document_adapter_commit_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(n,p,k,array=False):
 c,sc,o={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),"quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"')}[k]
 def f(l):
  l=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{c}"',l,1);l=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{sc}"',l,1);l=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f"PinType.PinSubCategoryObject={o}",l,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',l,1)
 n.mutate_pin(p,f)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();s=load(x.project_root);bp=s.load_helpers(x.project_root);forms=s.load_templates(x.project_root,bp);raw=bp.read_blocks(x.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");forms["self_call"]=bp.find_block(raw,r'MemberName="SwitchToDroneView"');b=s.Builder(bp,forms,FUNCTION)
 def var(n,name,k,array=False):s.retarget_variable(n,name,"vector" if k=="quat" else ("real" if k=="int" else k));kind(n,name,k,array);"Output_Get" in n.pins and kind(n,"Output_Get",k,array)
 def get(name,k,X,Y,array=False):n=b.add(f"get_{name}","get",X,Y);var(n,name,k,array);return n
 def setv(name,k,X,Y,value=None,array=False):n=b.add(f"set_{name}","set",X,Y);var(n,name,k,array);value is not None and s.set_default(n,name,value);return n
 def call(name,X,Y):
  n=b.add(f"call_{name}","self_call",X,Y);n.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);n.mutate_pin("self",lambda l:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET}",l,1));return n
 def and_(l,lp,r,rp,X,Y):n=b.add(f"and_{len(b.nodes)}","compare",X,Y);s.retarget_function(n,"BooleanAND");[kind(n,p,"bool") for p in ("A","B","ReturnValue")];bp.connect(l,lp,n,"A");bp.connect(r,rp,n,"B");return n
 invalidate=setv("AirframeDocumentAdapterCompileValidV2","bool",256,1600,"false");bp.connect(b.entry,"then",invalidate,"execute");stage=get("AirframeDocumentAdapterStageValidV2","bool",0,1600);guard=b.add("stage_guard","branch",512,1600);bp.connect(invalidate,"then",guard,"execute");bp.connect(stage,"AirframeDocumentAdapterStageValidV2",guard,"Condition")
 pubs=[]
 for i,(source,k,target) in enumerate(MAPPINGS):
  array=k in ("vector","quat") or source.startswith("AirframeDocumentInputSegment") and source not in ("AirframeDocumentInputDefaultFlightProfileV2",);g=get(source,k,0,i*144,array);n=setv(target,k,768+i*288,1600,array=array);bp.connect(g,source,n,target);pubs.append(n)
 bp.connect(guard,"then",pubs[0],"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(pubs,pubs[1:])];compile_call=call("CompileAirframeSourceSamplingV1",3552,1600);bp.connect(pubs[-1],"then",compile_call,"execute")
 source=get("AirframeSourceCompileValidV1","bool",3552,1120);desired=get("AirframeDesiredStreamCompileValidV1","bool",3552,1264);prebake=get("AirframePrebakeCompileValidV1","bool",3552,1408);both=and_(source,"AirframeSourceCompileValidV1",desired,"AirframeDesiredStreamCompileValidV1",3808,1200);all_=and_(both,"ReturnValue",prebake,"AirframePrebakeCompileValidV1",4032,1280);down=b.add("downstream_guard","branch",4288,1600);bp.connect(compile_call,"then",down,"execute");bp.connect(all_,"ReturnValue",down,"Condition");publish=setv("AirframeDocumentAdapterCompileValidV2","bool",4544,1600,"true");bp.connect(down,"then",publish,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
