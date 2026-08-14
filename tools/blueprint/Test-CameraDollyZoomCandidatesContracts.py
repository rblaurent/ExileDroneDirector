"""Structural and executable contracts for dolly-zoom candidate construction."""
from __future__ import annotations
import argparse, importlib.util, math, random, re, sys
from pathlib import Path

READS = {"CameraDollyValidationValidV1", "CameraDollyInputTimesSecondsV1", "CameraDollyInputCameraPositionsV1", "CameraDollyInputSubjectPositionV1", "CameraDollyInputReferenceSampleIndexV1", "CameraDollyInputReferenceFocalLengthMmV1", "CameraDollyCandidateSubjectDistancesCmV1", "CameraDollyCandidateFocalLengthsMmV1"}
WRITES = {"CameraDollyCandidateValidV1", "CameraDollyFailureCodeV1"}
FORBIDDEN = ("CameraDollyCompiled", "CameraDollyCompileValid", "CameraApply", "AirframeBody", "Gimbal", "Rotation", "Transform", "Document", "Playback")


def load(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def member(node):
    match=re.search(r'MemberName="([^"]+)"',node.text);return None if match is None else match.group(1)


def finite_vector(value):
    return len(value)==3 and all(math.isfinite(component) for component in value)


def build(times,positions,subject,reference_index,reference_focal,validation=True):
    distances=[];focals=[]
    if not validation:return distances,focals,False,"candidate_failed"
    reference_camera=positions[reference_index]
    if not finite_vector(subject) or not finite_vector(reference_camera):return distances,focals,False,"candidate_failed"
    reference_distance=math.dist(reference_camera,subject)
    if not math.isfinite(reference_distance) or reference_distance<1.0:return distances,focals,False,"candidate_failed"
    for index,(time,camera) in enumerate(zip(times,positions)):
        if not math.isfinite(time) or (index==0 and time!=0.0) or (index>0 and time<=times[index-1]) or not finite_vector(camera):break
        distance=math.dist(camera,subject)
        focal=reference_focal*distance/reference_distance
        if not math.isfinite(distance) or distance<1.0 or not math.isfinite(focal) or not 1.0<=focal<=1000.0:break
        distances.append(distance);focals.append(focal)
    valid=len(distances)==len(times) and len(focals)==len(times)
    return distances,focals,valid,"" if valid else "candidate_failed"


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args()
    c=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_dolly_candidate_contract_base");reference=load(args.project_root/"tools/trajectory/camera_dolly_zoom_reference.py","edd_dolly_candidate_reference");nodes=c.parse_graph(args.graph)
    c.require(len(nodes)==(105 if args.paste else 106),f"node count {len(nodes)}");entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];c.require(len(entries)==(0 if args.paste else 1),"entry count")
    getters={member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class};setters={member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class};c.require(getters==READS,"exact candidate reads");c.require(setters==WRITES,"exact candidate scalar writes")
    text=args.graph.read_text(encoding="utf-8");c.require(not any(value in text for value in FORBIDDEN),"compiled, engine, motion, orientation, document, and playback state forbidden");c.require(text.count("ForLoopWithBreak")==1,"one bounded loop");c.require(text.count('MemberName="Array_Clear"')==2,"two candidate clears");c.require(text.count('MemberName="Array_Add"')==2,"two aligned appends");c.require(text.count('MemberName="Array_Length"')==3,"input and two candidate lengths");c.require(text.count('MemberName="Vector_Distance"')==2,"reference and sample distance only");c.require(text.count('MemberName="BreakVector"')==3,"subject, reference camera, and sample camera finite checks")
    invalidators=[node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node)=="CameraDollyCandidateValidV1" and 'DefaultValue="true"' not in node.text];c.require(len(invalidators)==1,"candidate invalidated once")
    if not args.paste:c.require(any(any(link[0]==entries[0].name for link in node.pins["execute"].links) for node in invalidators),"native entry invalidates first")
    rng=random.Random(0xD0117C);valid=[]
    for _ in range(80):
        count=rng.randint(2,32);step=rng.uniform(.02,.2);times=tuple(index*step for index in range(count));subject=(10000.0,3000.0,1200.0);positions=tuple((rng.uniform(-500,500),rng.uniform(-500,500),rng.uniform(-500,500)) for _ in range(count));index=rng.randrange(count);focal=rng.uniform(20.0,120.0);valid.append((times,positions,subject,index,focal))
    for case in valid:
        expected=reference.compile_camera_dolly_zoom_v1(*case);distances,focals,accepted,failure=build(*case);c.require(accepted and failure=="","valid candidate publication");c.require(tuple(distances)==expected.subject_distances_cm and tuple(focals)==expected.focal_lengths_mm,"independent oracle match")
    base=((0.0,1.0,2.0),((0.0,0.0,0.0),(100.0,0.0,0.0),(200.0,0.0,0.0)),(1000.0,0.0,0.0),0,35.0)
    failures=(((*base,False),0),((base[0],base[1],(math.nan,0,0),base[3],base[4],True),0),((base[0],((math.inf,0,0),*base[1][1:]),base[2],base[3],base[4],True),0),(((0.0,1.0),((0,0,0),(10,0,0)),(0,0,0),0,35.0,True),0),(((1.0,2.0,3.0),*base[1:],True),0),(((0.0,1.0,1.0),*base[1:],True),2),(((0.0,math.nan,2.0),*base[1:],True),1),((base[0],(base[1][0],(math.nan,0,0),base[1][2]),base[2],base[3],base[4],True),1),(((0.0,1.0),((1000,0,0),(999.5,0,0)),(1000,0,0),1,35.0,True),0),(((0.0,1.0),((1,0,0),(1001,0,0)),(0,0,0),0,1000.0,True),1),(((0.0,1.0),((1000,0,0),(1,0,0)),(0,0,0),0,1.0,True),1))
    for case,prefix in failures:
        distances,focals,accepted,failure=build(*case);c.require(not accepted and failure=="candidate_failed" and len(distances)==prefix and len(focals)==prefix,"bounded aligned failure prefix")
    reverse=valid[0];forward_result=build(*reverse);reverse_case=(reverse[0],tuple(reversed(reverse[1])),reverse[2],len(reverse[1])-1-reverse[3],reverse[4]);reverse_result=build(*reverse_case);c.require(reverse_result[0]==list(reversed(forward_result[0])) and reverse_result[1]==list(reversed(forward_result[1])),"history-free spatial reversal")
    print(f"Camera dolly candidate contracts passed ({'paste' if args.paste else 'full'}): {len(valid)} reference cases, {len(failures)} failures")


if __name__=="__main__":main()
