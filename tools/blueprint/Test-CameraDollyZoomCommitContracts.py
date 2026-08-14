"""Atomic publication contracts for the complete dolly-zoom result."""
from __future__ import annotations
import argparse, importlib.util, random, re, sys
from copy import deepcopy
from pathlib import Path

READS={"CameraDollyCandidateValidV1","CameraDollyInputTimesSecondsV1","CameraDollyCandidateSubjectDistancesCmV1","CameraDollyCandidateFocalLengthsMmV1","CameraDollyInputReferenceSampleIndexV1"}
WRITES={"CameraDollyCompiledTimesSecondsV1","CameraDollyCompiledSubjectDistancesCmV1","CameraDollyCompiledFocalLengthsMmV1","CameraDollyCompiledReferenceDistanceCmV1","CameraDollyCompileValidV1","CameraDollyFailureCodeV1"}
FORBIDDEN=("CameraDollyInputCameraPositionsV1","CameraDollyInputSubjectPositionV1","CameraDollyInputReferenceFocalLengthMmV1","CameraApply","Airframe","Gimbal","Rotation","Transform","Document","Playback")


def load(path):spec=importlib.util.spec_from_file_location("edd_camera_dolly_commit_contract_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def member(node):match=re.search(r'MemberName="([^"]+)"',node.text);return None if match is None else match.group(1)
def commit(candidate_valid,times,distances,focals,reference_index,prior):
    result=deepcopy(prior);result["valid"]=False;result["failure"]="commit_failed";ready=candidate_valid and 2<=len(times)<=65536 and len(times)==len(distances)==len(focals) and isinstance(reference_index,int) and not isinstance(reference_index,bool) and 0<=reference_index<len(times)
    if ready:result.update(times=list(times),distances=list(distances),focals=list(focals),reference_distance=distances[reference_index],failure="",valid=True)
    return result
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args();c=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(args.graph);c.require(len(nodes)==(30 if args.paste else 31),f"node count {len(nodes)}");entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];c.require(len(entries)==(0 if args.paste else 1),"entry count")
    getters={member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class};setters=[node for node in nodes.values() if "K2Node_VariableSet" in node.node_class];c.require(getters==READS,"exact commit reads");c.require({member(node) for node in setters}==WRITES,"exact commit writes");c.require(sum(member(node)=="CameraDollyCompileValidV1" for node in setters)==2,"validity invalidated then published");c.require(sum(member(node)=="CameraDollyFailureCodeV1" for node in setters)==2,"failure staged then cleared")
    for name in ("CameraDollyCompiledTimesSecondsV1","CameraDollyCompiledSubjectDistancesCmV1","CameraDollyCompiledFocalLengthsMmV1"):
        node=next(node for node in setters if member(node)==name);c.require("PinType.ContainerType=Array" in node.pins[name].body,f"{name} whole-array publication")
    text=args.graph.read_text(encoding="utf-8");c.require(not any(value in text for value in FORBIDDEN),"commit boundary isolation");c.require(sum(member(node)=="Array_Length" for node in nodes.values())==3,"three exact cardinalities");c.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values())==1,"one reference-distance lookup")
    invalidator=next(node for node in setters if member(node)=="CameraDollyCompileValidV1" and 'DefaultValue="true"' not in node.text);publisher=next(node for node in setters if member(node)=="CameraDollyCompileValidV1" and 'DefaultValue="true"' in node.text);c.require(not publisher.pins["then"].links,"validity last")
    if args.paste:c.require(not invalidator.pins["execute"].links,"paste root unlinked")
    else:c.require_link(entries[0],"then",invalidator,"execute","entry invalidates first")
    rng=random.Random(0xD0117D);prior={"times":[0.0,9.0],"distances":[9.0,9.0],"focals":[35.0,35.0],"reference_distance":9.0,"valid":True,"failure":"old"}
    for _ in range(80):
        count=rng.randint(2,128);times=[index*.125 for index in range(count)];distances=[rng.uniform(1,100000) for _ in range(count)];focals=[rng.uniform(1,1000) for _ in range(count)];index=rng.randrange(count);before=(deepcopy(times),deepcopy(distances),deepcopy(focals));result=commit(True,times,distances,focals,index,prior);c.require(result=={"times":times,"distances":distances,"focals":focals,"reference_distance":distances[index],"valid":True,"failure":""},"exact atomic publication");c.require((times,distances,focals)==before and result["times"] is not times and result["distances"] is not distances and result["focals"] is not focals,"value snapshot")
    good=([0.0,.1,.2],[100.0,110.0,120.0],[35.0,38.5,42.0]);failures=((False,*good,0),(True,[0.0],good[1][:1],good[2][:1],0),(True,list(range(65537)),list(range(65537)),list(range(65537)),0),(True,good[0],good[1][:-1],good[2],0),(True,good[0],good[1],good[2][:-1],0),(True,*good,-1),(True,*good,3),(True,*good,True))
    for case in failures:
        result=commit(*case,prior);c.require(all(result[key]==prior[key] for key in ("times","distances","focals","reference_distance")),"failure preserves compiled snapshot");c.require(not result["valid"] and result["failure"]=="commit_failed","failure invalidates result")
    print(f"Camera dolly commit contracts passed ({'paste' if args.paste else 'full'}): 80 snapshots, {len(failures)} failures")
if __name__=="__main__":main()
