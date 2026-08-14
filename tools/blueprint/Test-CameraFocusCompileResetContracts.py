"""Exact ownership and execution contracts for focus compile reset."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

ARRAY="CameraFocusCandidateDistancesCmV1";SCALARS=("CameraFocusCandidateValidV1","CameraFocusCompileValidV1","CameraFocusFailureCodeV1")
PRESERVED=("CameraFocusInputModeV1","CameraFocusInputDomainV1","CameraFocusInputFixedStepSecondsV1","CameraFocusInputTimesSecondsV1","CameraFocusInputCameraPositionsV1","CameraFocusInputManualDistancesCmV1","CameraFocusInputTargetPositionsV1","CameraFocusInputRackTargetAV1","CameraFocusInputRackTargetBV1","CameraFocusInputRackBlendWeightsV1","CameraFocusInputSmoothingResponseSecondsV1","CameraFocusTraceHitValidV1","CameraFocusTraceHitPositionV1","CameraFocusMarkerValidV1","CameraFocusMarkerPositionV1","CameraFocusMarkerRevisionV1","CameraFocusCompiledTimesSecondsV1","CameraFocusCompiledDistancesCmV1","CameraFocusCompiledModeV1","CameraFocusCompiledDomainV1")
def load(path):spec=importlib.util.spec_from_file_location("edd_focus_reset_contract_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def member(node):
 match=re.search(r'MemberName="([^"]+)"',node.text);return None if match is None else match.group(1)
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args();contracts=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=contracts.parse_graph(args.graph)
 contracts.require(len(nodes)==(5 if args.paste else 6),f"node count {len(nodes)}");entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];contracts.require(len(entries)==(0 if args.paste else 1),"entry count");root=nodes["K2Node_CallArrayFunction_0"]
 if args.paste:contracts.require(not root.pins["execute"].links,"paste execution root")
 else:contracts.require_link(entries[0],"then",root,"execute","native entry to focus reset root")
 getters={member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class};setters={member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class};contracts.require(getters=={ARRAY},"exact candidate array");contracts.require(setters==set(SCALARS),"exact result scalars")
 text=args.graph.read_text(encoding="utf-8");contracts.require(not any(name in text for name in PRESERVED),"inputs, trace, marker, and accepted compiled snapshot preserved")
 state={ARRAY:[1.0,2.0],**{name:"poison" for name in SCALARS},**{name:object() for name in PRESERVED}};before={name:state[name] for name in PRESERVED};state[ARRAY]=[];state.update(CameraFocusCandidateValidV1=False,CameraFocusCompileValidV1=False,CameraFocusFailureCodeV1="");contracts.require(state[ARRAY]==[] and not state["CameraFocusCandidateValidV1"] and not state["CameraFocusCompileValidV1"] and state["CameraFocusFailureCodeV1"]=="","fail-closed reset");contracts.require(all(state[name] is before[name] for name in PRESERVED),"preserved object identity")
 print(f"Camera focus reset contracts passed ({'paste' if args.paste else 'full'}): compiled snapshot preserved")
if __name__=="__main__":main()
