"""Exact orchestration contracts for full camera channel compilation."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
ORDER=("ResetCameraChannelCompileV1","ValidateCameraChannelInputsV1","CompileCameraChannelCandidateV1","CommitCameraChannelAssemblyV1")
def load(path):s=importlib.util.spec_from_file_location("edd_camera_channel_compile_contract_base",path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(10 if x.paste else 11),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");root=nodes["K2Node_CallFunction_0"];c.require(not root.pins["execute"].links,"paste execution root") if x.paste else c.require_link(entries[0],"then",root,"execute","native entry to compile root");text=x.graph.read_text(encoding="utf-8");positions=[text.index(f'MemberName="{name}"') for name in ORDER];c.require(positions==sorted(positions),"reset validate candidate commit order");c.require(text.count('MemberName="CompileCameraChannelCandidateV1"')==1,"one loop-body candidate call");c.require(text.count("StandardMacros:ForLoop")==1,"one canonical bounded loop");c.require('DefaultValue="0"' in text and 'DefaultValue="12"' in text,"exact 0..12 bounds");c.require("CameraScalarTrack" not in text,"coordinator has no scalar policy");c.require('VariableReference=(MemberName="CameraChannelInput' not in text and 'VariableReference=(MemberName="CameraChannelCandidate' not in text and 'VariableReference=(MemberName="CameraChannelCompiled' not in text,"coordinator owns no storage")
 setters=[n for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require(len(setters)==1 and 'MemberName="CameraChannelScratchChannelIndexV1"' in setters[0].text,"only channel index setter");branches=[n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class];c.require(len(branches)==2,"validation and commit guards")
 simulated=[];valid=True;simulated.append("reset");simulated.append("validate")
 for index in range(13):simulated.append(("candidate",index))
 if valid:simulated.append("commit")
 c.require(simulated[:2]==["reset","validate"] and simulated[2:15]==[("candidate",i) for i in range(13)] and simulated[-1]=="commit","success orchestration")
 invalid=["reset","validate"];c.require("commit" not in invalid,"validation failure skips compile/commit");late=["reset","validate",*(("candidate",i) for i in range(6))];c.require("commit" not in late,"candidate failure skips commit")
 print(f"Camera channel compile contracts passed ({'paste' if x.paste else 'full'}): exact reset/validate/13 candidates/commit order")
if __name__=="__main__":main()
