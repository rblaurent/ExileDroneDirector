"""Build the fail-closed reset for the reusable camera scalar-track engine."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="ResetCameraScalarTrackCompileV1"
ARRAYS=(("CameraScalarTrackCandidateKeyTimesV1","real"),("CameraScalarTrackCandidateDomainValuesV1","real"),("CameraScalarTrackCandidateInterpolationModesV1","string"),("CameraScalarTrackCandidateArriveTangentsV1","real"),("CameraScalarTrackCandidateLeaveTangentsV1","real"))
SCALARS=(("CameraScalarTrackCompileValidV1","bool","false"),("CameraScalarTrackFailureCodeV1","string",""),("CameraScalarTrackResultValueV1","real","0.0"),("CameraScalarTrackResultVelocityV1","real","0.0"),("CameraScalarTrackResultAccelerationV1","real","0.0"),("CameraScalarTrackResultSegmentIndexV1","int","-1"),("CameraScalarTrackResultLocalAlphaV1","real","0.0"),("CameraScalarTrackResultCompleteV1","bool","false"),("CameraScalarTrackResultValidV1","bool","false"),("CameraScalarTrackScratchIndexV1","int","0"),("CameraScalarTrackScratchValidV1","bool","false"),("CameraScalarTrackScratchDomainValueV1","real","0.0"),("CameraScalarTrackScratchDomainVelocityV1","real","0.0"),("CameraScalarTrackScratchDomainAccelerationV1","real","0.0"))
def load(root):
 p=root/"tools/blueprint/Build-OrientationTrackResetGraph.py";s=importlib.util.spec_from_file_location("edd_camera_scalar_reset_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def string_variable(node,old,new,array=False):
 node.text=re.sub(rf'VariableReference=\(MemberName="{re.escape(old)}"[^)]*\)',f'VariableReference=(MemberName="{new}",bSelfContext=True)',node.text,1);node.text=node.text.replace(f'PinName="{old}"',f'PinName="{new}"');node.pins[new]=node.pins.pop(old)
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"','PinType.PinCategory="string"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"','PinType.PinSubCategory=""',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")','PinType.PinSubCategoryObject=None',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(new,mutate)
def string_pin(node,name,array=False):
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"','PinType.PinCategory="string"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"','PinType.PinSubCategory=""',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")','PinType.PinSubCategoryObject=None',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(name,mutate)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();reset=load(x.project_root);bp=reset.load(x.project_root);bp.TARGET_GRAPH=FUNCTION
 capture=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");sync=bp.read_blocks(x.project_root/"tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph");start=bp.read_blocks(x.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph")
 entry=bp.Node.clone("entry",bp.find_block(capture,r"K2Node_FunctionEntry"),"K2Node_FunctionEntry_0",0,0);entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1)
 array_form=bp.find_block(sync,r'MemberName="DraftWaypointIds"');clear_form=bp.find_block(sync,r'MemberName="Array_Clear"');setter_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"');nodes=[entry];chain=[]
 for i,(name,kind) in enumerate(ARRAYS):
  g=bp.Node.clone(f"get_{i}",array_form,f"K2Node_VariableGet_{i}",256+i*416,256);string_variable(g,"DraftWaypointIds",name,True) if kind=="string" else reset.variable(g,"DraftWaypointIds",name,kind,True);c=bp.Node.clone(f"clear_{i}",clear_form,f"K2Node_CallArrayFunction_{i}",256+i*416,0);string_pin(c,"TargetArray",True) if kind=="string" else reset.pin_kind(c,"TargetArray",kind,True);bp.connect(g,name,c,"TargetArray");nodes.extend((g,c));chain.append(c)
 for i,(name,kind,value) in enumerate(SCALARS):
  n=bp.Node.clone(f"set_{i}",setter_form,f"K2Node_VariableSet_{i}",256+(len(ARRAYS)+i)*416,0);string_variable(n,"PlaybackActive",name) if kind=="string" else reset.variable(n,"PlaybackActive",name,kind);reset.default(n,name,value);nodes.append(n);chain.append(n)
 bp.connect(entry,"then",chain[0],"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(chain,chain[1:])]
 full="\n".join(n.text for n in nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
