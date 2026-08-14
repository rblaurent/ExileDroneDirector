"""Build atomic Set Focus Here marker commit from a normalized trace hit."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

FUNCTION="SetCameraFocusHereV1"
def load(path,name):spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args();reset=load(args.project_root/"tools/blueprint/Build-OrientationTrackResetGraph.py","edd_focus_set_here_base");bp=reset.load(args.project_root);bp.TARGET_GRAPH=FUNCTION
 capture=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");sync=bp.read_blocks(args.project_root/"tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph");start=bp.read_blocks(args.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph")
 entry=bp.Node.clone("entry",bp.find_block(capture,r"K2Node_FunctionEntry"),"K2Node_FunctionEntry_0",0,0);entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1)
 getter_form=bp.find_block(sync,r'MemberName="DraftWaypointIds"');setter_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"');branch=bp.Node.clone("guard",bp.find_block(start,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_IfThenElse"),"K2Node_IfThenElse_0",512,0);add=bp.Node.clone("increment",bp.find_block(capture,r'MemberName="Add_IntInt"'),"K2Node_CallFunction_0",768,384);reset.default(add,"B","1")
 def getter(name,kind,index,x,y):node=bp.Node.clone(name,getter_form,f"K2Node_VariableGet_{index}",x,y);reset.variable(node,"DraftWaypointIds",name,kind);return node
 def setter(name,kind,index,x,y,default=None):node=bp.Node.clone(name,setter_form,f"K2Node_VariableSet_{index}",x,y);reset.variable(node,"PlaybackActive",name,kind);reset.default(node,name,default) if default is not None else None;return node
 trace_valid=getter("CameraFocusTraceHitValidV1","bool",0,256,256);trace_position=getter("CameraFocusTraceHitPositionV1","vector",1,512,256);revision=getter("CameraFocusMarkerRevisionV1","int",2,512,384);set_position=setter("CameraFocusMarkerPositionV1","vector",0,768,0);set_valid=setter("CameraFocusMarkerValidV1","bool",1,1024,0,"true");set_revision=setter("CameraFocusMarkerRevisionV1","int",2,1280,0)
 bp.connect(entry,"then",branch,"execute");bp.connect(trace_valid,"CameraFocusTraceHitValidV1",branch,"Condition");bp.connect(branch,"then",set_position,"execute");bp.connect(trace_position,"CameraFocusTraceHitPositionV1",set_position,"CameraFocusMarkerPositionV1");bp.connect(set_position,"then",set_valid,"execute");bp.connect(set_valid,"then",set_revision,"execute");bp.connect(revision,"CameraFocusMarkerRevisionV1",add,"A");bp.connect(add,"ReturnValue",set_revision,"CameraFocusMarkerRevisionV1")
 nodes=[entry,trace_valid,branch,trace_position,revision,add,set_position,set_valid,set_revision];full="\n".join(node.text for node in nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
 if args.paste_output:args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
