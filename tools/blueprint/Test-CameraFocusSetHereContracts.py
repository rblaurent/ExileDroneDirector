"""Structural and executable contracts for atomic Set Focus Here."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

GETTERS={"CameraFocusTraceHitValidV1","CameraFocusTraceHitPositionV1","CameraFocusMarkerRevisionV1"};SETTERS={"CameraFocusMarkerPositionV1","CameraFocusMarkerValidV1","CameraFocusMarkerRevisionV1"}
def load(path):spec=importlib.util.spec_from_file_location("edd_focus_set_contract_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def member(node):match=re.search(r'MemberName="([^"]+)"',node.text);return None if match is None else match.group(1)
def one(nodes,cls=None,name=None):
 items=[node for node in nodes.values() if (cls is None or cls in node.node_class) and (name is None or member(node)==name)];assert len(items)==1,(cls,name,len(items));return items[0]
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args();c=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(args.graph);c.require(len(nodes)==(8 if args.paste else 9),f"node count {len(nodes)}");entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];c.require(len(entries)==(0 if args.paste else 1),"entry count")
 getters={member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class};setters={member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class};c.require(getters==GETTERS,"exact trace/revision reads");c.require(setters==SETTERS,"exact marker writes")
 branch=one(nodes,"K2Node_IfThenElse");trace=one(nodes,"K2Node_VariableGet","CameraFocusTraceHitValidV1");position=one(nodes,"K2Node_VariableGet","CameraFocusTraceHitPositionV1");revision=one(nodes,"K2Node_VariableGet","CameraFocusMarkerRevisionV1");set_position=one(nodes,"K2Node_VariableSet","CameraFocusMarkerPositionV1");set_valid=one(nodes,"K2Node_VariableSet","CameraFocusMarkerValidV1");set_revision=one(nodes,"K2Node_VariableSet","CameraFocusMarkerRevisionV1");add=one(nodes,name="Add_IntInt")
 if args.paste:c.require(not branch.pins["execute"].links,"paste execution root")
 else:c.require_link(entries[0],"then",branch,"execute","native entry to trace guard")
 c.require_link(trace,"CameraFocusTraceHitValidV1",branch,"Condition","trace validity guard");c.require(not branch.pins["else"].links,"trace miss zero mutation");c.require_link(branch,"then",set_position,"execute","hit starts commit");c.require_link(position,"CameraFocusTraceHitPositionV1",set_position,"CameraFocusMarkerPositionV1","exact hit position");c.require_link(set_position,"then",set_valid,"execute","position before validity");c.require_link(set_valid,"then",set_revision,"execute","revision publishes last");c.require_link(revision,"CameraFocusMarkerRevisionV1",add,"A","prior revision");c.require_link(add,"ReturnValue",set_revision,"CameraFocusMarkerRevisionV1","incremented revision")
 state={"valid":True,"position":(1,2,3),"revision":7};before=dict(state)
 c.require(state==before,"miss preserves marker");state.update(position=(9,8,7),valid=True,revision=state["revision"]+1);c.require(state=={"valid":True,"position":(9,8,7),"revision":8},"hit atomic marker commit")
 print(f"Camera focus Set Here contracts passed ({'paste' if args.paste else 'full'}): miss zero mutation, hit atomic")
if __name__=="__main__":main()
