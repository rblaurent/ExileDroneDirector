"""Build the fail-closed candidate/result reset for position-route assembly."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

FUNCTION="ResetPositionRouteCandidateV1";TARGET="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
ARRAYS=(
 ("PositionRouteCandidateWaypointVelocitiesV1","vector"),("PositionRouteCandidateSegmentStartsV1","real"),("PositionRouteCandidateArcSampleStartsV1","int"),("PositionRouteCandidateArcSampleCountsV1","int"),("PositionRouteCandidateArcUsV1","real"),("PositionRouteCandidateArcDistancesV1","real"),("PositionRouteCandidateSegmentLengthsV1","real"),
 ("PositionRouteCompiledWaypointPositionsV1","vector"),("PositionRouteCompiledDurationsV1","real"),("PositionRouteCompiledSpatialCurveTypesV1","string"),("PositionRouteCompiledTimeProfilesV1","string"),("PositionRouteCompiledWaypointVelocitiesV1","vector"),("PositionRouteCompiledSegmentStartsV1","real"),("PositionRouteCompiledArcSampleStartsV1","int"),("PositionRouteCompiledArcSampleCountsV1","int"),("PositionRouteCompiledArcUsV1","real"),("PositionRouteCompiledArcDistancesV1","real"),("PositionRouteCompiledSegmentLengthsV1","real"),
)
SCALARS=(("PositionRouteCandidateTotalSecondsV1","real","0.0"),("PositionRouteCandidateTotalDistanceV1","real","0.0"),("PositionRouteCandidateOperationCountV1","int","0"),("PositionRouteStageValidV1","bool","false"),("PositionRouteCompiledTotalSecondsV1","real","0.0"),("PositionRouteCompiledTotalDistanceV1","real","0.0"),("PositionRouteCompileValidV1","bool","false"),("PositionRouteResultSegmentIndexV1","int","-1"),("PositionRouteResultLocalTimeAlphaV1","real","0.0"),("PositionRouteResultDistanceAlphaV1","real","0.0"),("PositionRouteResultCurveUV1","real","0.0"),("PositionRouteResultPositionV1","vector","0, 0, 0"),("PositionRouteResultCompleteV1","bool","false"),("PositionRouteResultValidV1","bool","false"))

def load(root):
 p=root/"tools/blueprint/Build-OrientationTrackResetGraph.py";s=importlib.util.spec_from_file_location("edd_position_reset_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def pin_kind(node,pin_name,kind,array=False):
 category,subcategory,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[kind]
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(pin_name,mutate)
def variable(node,old,new,kind,array=False):
 node.text=re.sub(rf'VariableReference=\(MemberName="{old}"[^)]*\)',f'VariableReference=(MemberName="{new}",bSelfContext=True)',node.text,1);node.text=node.text.replace(f'PinName="{old}"',f'PinName="{new}"');node.pins[new]=node.pins.pop(old);pin_kind(node,new,kind,array)
 if "Output_Get" in node.pins:pin_kind(node,"Output_Get",kind)
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();base=load(a.project_root);bp=base.load(a.project_root);bp.TARGET_ASSET=TARGET;bp.TARGET_GRAPH=FUNCTION
 capture=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");sync=bp.read_blocks(a.project_root/"tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph");start=bp.read_blocks(a.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph")
 entry_form=bp.find_block(capture,r"K2Node_FunctionEntry");array_form=bp.find_block(sync,r'MemberName="DraftWaypointIds"');clear_form=bp.find_block(sync,r'MemberName="Array_Clear"');setter_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"')
 nodes=[];entry=bp.Node.clone("entry",entry_form,"K2Node_FunctionEntry_0",0,0);entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1);nodes.append(entry);chain=[]
 for i,(name,kind) in enumerate(ARRAYS):
  getter=bp.Node.clone(f"get{i}",array_form,f"K2Node_VariableGet_{i}",256+i*416,256);variable(getter,"DraftWaypointIds",name,kind,True);nodes.append(getter)
  clear=bp.Node.clone(f"clear{i}",clear_form,f"K2Node_CallArrayFunction_{i}",256+i*416,0);pin_kind(clear,"TargetArray",kind,True);nodes.append(clear);bp.connect(getter,name,clear,"TargetArray");chain.append(clear)
 for i,(name,kind,value) in enumerate(SCALARS):
  setter=bp.Node.clone(f"set{i}",setter_form,f"K2Node_VariableSet_{i}",256+(len(ARRAYS)+i)*416,0);variable(setter,"PlaybackActive",name,kind);base.default(setter,name,value);nodes.append(setter);chain.append(setter)
 bp.connect(entry,"then",chain[0],"execute")
 for left,right in zip(chain,chain[1:]):bp.connect(left,"then",right,"execute")
 full="\n".join(n.text for n in nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
 if a.paste_output:
  body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
