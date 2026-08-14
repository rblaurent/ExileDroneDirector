"""Build the fail-closed, compiled-snapshot-preserving focus reset."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

FUNCTION="ResetCameraFocusCompileV1"


def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
 parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args()
 camera=load(args.project_root/"tools/blueprint/Build-CameraChannelCompileResetGraph.py","edd_focus_reset_camera");reset=camera.load(args.project_root);bp=reset.load(args.project_root);bp.TARGET_GRAPH=FUNCTION
 capture=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");sync=bp.read_blocks(args.project_root/"tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph");start=bp.read_blocks(args.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph")
 entry=bp.Node.clone("entry",bp.find_block(capture,r"K2Node_FunctionEntry"),"K2Node_FunctionEntry_0",0,0);entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1)
 array_form=bp.find_block(sync,r'MemberName="DraftWaypointIds"');clear_form=bp.find_block(sync,r'MemberName="Array_Clear"');setter_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"')
 getter=bp.Node.clone("candidate",array_form,"K2Node_VariableGet_0",256,256);reset.variable(getter,"DraftWaypointIds","CameraFocusCandidateDistancesCmV1","real",True)
 clear=bp.Node.clone("clear",clear_form,"K2Node_CallArrayFunction_0",256,0);reset.pin_kind(clear,"TargetArray","real",True);bp.connect(getter,"CameraFocusCandidateDistancesCmV1",clear,"TargetArray")
 nodes=[entry,getter,clear];chain=[clear]
 for index,(name,kind,value) in enumerate((("CameraFocusCandidateValidV1","bool","false"),("CameraFocusCompileValidV1","bool","false"),("CameraFocusFailureCodeV1","string",""))):
  node=bp.Node.clone(f"set_{index}",setter_form,f"K2Node_VariableSet_{index}",672+index*416,0)
  camera.string_variable(node,"PlaybackActive",name) if kind=="string" else reset.variable(node,"PlaybackActive",name,kind)
  reset.default(node,name,value);nodes.append(node);chain.append(node)
 bp.connect(entry,"then",clear,"execute")
 for left,right in zip(chain,chain[1:]):bp.connect(left,"then",right,"execute")
 full="\n".join(node.text for node in nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
 if args.paste_output:
  paste="\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in nodes[1:])+"\n";args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text(paste,encoding="utf-8")


if __name__=="__main__":main()
