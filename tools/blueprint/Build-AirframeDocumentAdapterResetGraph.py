"""Build fail-closed reset for the v2 compiled-document source adapter."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="ResetAirframeDocumentSourceAdapterV2"
ARRAYS=(
 ("AirframeDocumentDiagnosticWaypointIdsV2","int"),
 ("AirframeDocumentDiagnosticPositionVelocityJumpsV2","real"),
 ("AirframeDocumentDiagnosticPositionAccelerationJumpsV2","real"),
 ("AirframeDocumentDiagnosticBodyAngularRateJumpsV2","real"),
 ("AirframeDocumentDiagnosticGimbalAngularRateJumpsV2","real"),
 ("AirframeDocumentDiagnosticDiscontinuousFlagsV2","bool"),
)
SCALARS=(("AirframeDocumentAdapterStageValidV2","bool","false"),("AirframeDocumentAdapterCompileValidV2","bool","false"),("AirframeDocumentAdapterFailureCodeV2","string","") ,("AirframeDocumentDiagnosticCountV2","int","0"),("AirframeDocumentDiagnosticsValidV2","bool","false"))
def load(root):
 p=root/"tools/blueprint/Build-OrientationTrackResetGraph.py";s=importlib.util.spec_from_file_location("edd_document_adapter_reset_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def string_variable(node,old,new):
 node.text=re.sub(rf'VariableReference=\(MemberName="{re.escape(old)}"[^)]*\)',f'VariableReference=(MemberName="{new}",bSelfContext=True)',node.text,1);node.text=node.text.replace(f'PinName="{old}"',f'PinName="{new}"');node.pins[new]=node.pins.pop(old)
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"','PinType.PinCategory="string"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"','PinType.PinSubCategory=""',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")','PinType.PinSubCategoryObject=None',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)','PinType.ContainerType=None',line,1)
 node.mutate_pin(new,mutate)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();reset=load(x.project_root);bp=reset.load(x.project_root);bp.TARGET_GRAPH=FUNCTION
 capture=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");sync=bp.read_blocks(x.project_root/"tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph");start=bp.read_blocks(x.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph");calls=bp.read_blocks(x.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph")
 entry=bp.Node.clone("entry",bp.find_block(capture,r"K2Node_FunctionEntry"),"K2Node_FunctionEntry_0",0,0);entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1)
 call=bp.Node.clone("source_reset",bp.find_block(calls,r'MemberName="SwitchToDroneView"'),"K2Node_CallFunction_0",256,0);call.text=re.sub(r"FunctionReference=\([^)]*\)",'FunctionReference=(MemberName="ResetAirframeSourceSamplingV1",bSelfContext=True)',call.text,1)
 array_form=bp.find_block(sync,r'MemberName="DraftWaypointIds"');clear_form=bp.find_block(sync,r'MemberName="Array_Clear"');setter_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"');nodes=[entry,call];chain=[call]
 for i,(name,kind) in enumerate(ARRAYS):
  g=bp.Node.clone(f"get_{i}",array_form,f"K2Node_VariableGet_{i}",640+i*416,256);reset.variable(g,"DraftWaypointIds",name,kind,True);c=bp.Node.clone(f"clear_{i}",clear_form,f"K2Node_CallArrayFunction_{i}",640+i*416,0);reset.pin_kind(c,"TargetArray",kind,True);bp.connect(g,name,c,"TargetArray");nodes.extend((g,c));chain.append(c)
 for i,(name,kind,value) in enumerate(SCALARS):
  n=bp.Node.clone(f"set_{i}",setter_form,f"K2Node_VariableSet_{i}",640+(len(ARRAYS)+i)*416,0);string_variable(n,"PlaybackActive",name) if kind=="string" else reset.variable(n,"PlaybackActive",name,kind);reset.default(n,name,value);nodes.append(n);chain.append(n)
 bp.connect(entry,"then",call,"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(chain,chain[1:])]
 full="\n".join(n.text for n in nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
