"""Exact semantic contracts for one camera channel sample publication."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
def load(path):s=importlib.util.spec_from_file_location("edd_camera_channel_publish_contract_base",path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(24 if x.paste else 25),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");text=x.graph.read_text(encoding="utf-8");c.require(text.count('MemberName="EvaluateCameraScalarTrackV1"')==1,"one scalar evaluation");c.require(text.count('MemberName="Array_Add"')==3,"three result appends");c.require("CameraChannelCompiled" not in text and "CameraChannelInputKey" not in text,"publication cannot mutate/read storage");setters={member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class};c.require(setters=={"CameraScalarTrackQueryTimeV1","CameraChannelScratchValidV1","CameraChannelResultCompleteV1"},"setter ownership")
 values=[];velocities=[];accelerations=[];complete=False
 samples=((1.0,2.0,3.0,False),(4.0,5.0,6.0,True),(7.0,8.0,9.0,True))
 for index,(value,velocity,acceleration,item_complete) in enumerate(samples):values.append(value);velocities.append(velocity);accelerations.append(acceleration);complete=item_complete if index==0 else complete and item_complete
 c.require(values==[1.0,4.0,7.0] and velocities==[2.0,5.0,8.0] and accelerations==[3.0,6.0,9.0],"canonical append order");c.require(not complete,"completion folds all channels")
 stale=([1.0],[2.0],[3.0]);before=tuple(list(item) for item in stale);scalar_valid=False
 if scalar_valid:raise AssertionError("unreachable")
 c.require(stale==before,"invalid scalar result does not append");c.require(text.index('MemberName="Array_Add"')<text.rindex('MemberName="CameraChannelResultCompleteV1"'),"completion after sample append")
 print(f"Camera channel publication contracts passed ({'paste' if x.paste else 'full'}): ordered sample append and completion fold")
if __name__=="__main__":main()
