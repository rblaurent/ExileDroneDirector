"""Structural and executable contracts for BuildCarrierFrameTangentsV1."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CarrierFrameInputPositionsV1", "CarrierFrameCandidateTangentsV1",
    "CarrierFrameScratchValidV1", "CarrierFrameScratchIndexV1", "CarrierFrameScratchForwardV1",
}
WRITES = {"CarrierFrameScratchValidV1", "CarrierFrameScratchIndexV1", "CarrierFrameScratchForwardV1", "CarrierFrameFailureCodeV1"}
FORBIDDEN = (
    "AirframeDesired", "AuthoredBody", "AuthoredGimbal", "CameraTransform",
    "CarrierFrameCandidateQuats", "CarrierFrameCompiled", "CarrierFrameResult",
    "CameraOperator", "PlaybackTime", "Event", "Repository", "Server",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_tangent_contract_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def default(node, pin_name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body); return "" if match is None else match.group(1)


def subtract(left, right): return tuple(a - b for a, b in zip(left, right))
def length(value): return math.sqrt(sum(component * component for component in value))
def normalize(value):
    magnitude = length(value); return tuple(component / magnitude for component in value)


def sample_tangent(positions, index):
    count = len(positions); candidates = []
    if 0 < index < count - 1: candidates.append(subtract(positions[index + 1], positions[index - 1]))
    if index < count - 1: candidates.append(subtract(positions[index + 1], positions[index]))
    if index > 0: candidates.append(subtract(positions[index], positions[index - 1]))
    for distance in range(2, count):
        if index + distance < count: candidates.append(subtract(positions[index + distance], positions[index]))
        if index - distance >= 0: candidates.append(subtract(positions[index], positions[index - distance]))
    for candidate in candidates:
        if length(candidate) > 1.0e-9: return normalize(candidate)
    raise ValueError("tangent_missing")


def execute(positions, validation_valid=True):
    candidates = []
    if not validation_valid: return candidates, False, ""
    for index in range(len(positions)):
        try: candidates.append(sample_tangent(positions, index))
        except ValueError: return candidates, False, "tangent_missing"
    if len(candidates) != len(positions): return candidates, False, "tangent_build_failed"
    return candidates, True, ""


def close_vector(left, right, tolerance=1.0e-12): return all(abs(a-b) <= tolerance for a,b in zip(left,right))


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args()
    contracts=load(args.project_root);nodes=contracts.parse_graph(args.graph)
    contracts.require(len(nodes)==(71 if args.paste else 72),f"tangent node count {len(nodes)}")
    entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries)==(0 if args.paste else 1),"tangent entry count")
    getters=[node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setters=[node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in getters}==READS,"exact tangent reads")
    contracts.require({member(node) for node in setters}==WRITES,"exact tangent writes")
    contracts.require(sum("K2Node_MacroInstance" in node.node_class for node in nodes.values())==2,"outer and distance loops")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values())==5,"central/current/forward/backward items")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values())==10,"exact tangent phase guards")
    functions=[member(node) for node in nodes.values()]
    for name,expected in {"Array_Clear":1,"Array_Length":2,"Array_Add":1,"Subtract_VectorVector":3,"VSize":3,"MakeVector":3,"Divide_VectorVector":3}.items():
        contracts.require(functions.count(name)==expected,f"{name} count {functions.count(name)}")
    text=args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN),"authored/external ownership forbidden")
    for token in ('DefaultValue="1e-9"','DefaultValue="tangent_missing"','DefaultValue="tangent_build_failed"','DefaultValue="1"'):
        contracts.require(token in text,f"frozen tangent token missing:{token}")
    clear=next(node for node in nodes.values() if member(node)=="Array_Clear")
    target=next(node for node in getters if member(node)=="CarrierFrameCandidateTangentsV1")
    contracts.require_link(target,"CarrierFrameCandidateTangentsV1",clear,"TargetArray","candidate tangents clear")
    if args.paste: contracts.require(not clear.pins["execute"].links,"paste root")
    else: contracts.require_link(entries[0],"then",clear,"execute","entry clears owned candidate")
    appends=[node for node in nodes.values() if member(node)=="Array_Add"]
    contracts.require(len(appends)==1,"single tangent append site")
    scratch_forward=next(node for node in getters if member(node)=="CarrierFrameScratchForwardV1")
    contracts.require_link(scratch_forward,"CarrierFrameScratchForwardV1",appends[0],"NewItem","append frozen normalized tangent")
    publishers=[node for node in setters if member(node)=="CarrierFrameScratchValidV1" and default(node,"CarrierFrameScratchValidV1")=="true"]
    final_publish=publishers[-1]
    contracts.require(not final_publish.pins["then"].links,"success publishes terminal validity")

    cases=[
        ((0.,0.,0.),(1.,0.,0.),(2.,0.,0.)),
        ((0.,0.,0.),(0.,0.,0.),(0.,0.,2.)),
        ((0.,0.,0.),(1.,0.,0.),(1.,0.,0.),(1.,0.,0.),(0.,0.,0.)),
        ((0.,0.,0.),(1.,0.,0.),(2.,1.,0.),(3.,2.,1.)),
    ]
    randomizer=random.Random(0x7A66E17)
    for _index in range(100):
        points=[(0.0,0.0,0.0)]
        for sample in range(1,randomizer.randint(2,80)):
            if sample%11==0: points.append(points[-1])
            else: points.append(tuple(value+randomizer.uniform(-5.0,5.0) for value in points[-1]))
        cases.append(tuple(points))
    forward=[]
    for index,positions in enumerate(cases):
        before=tuple(positions);tangents,valid,failure=execute(positions)
        contracts.require(valid and failure=="" and len(tangents)==len(positions),f"valid tangent case {index}")
        expected=[sample_tangent(positions,sample) for sample in range(len(positions))]
        contracts.require(all(close_vector(a,b) for a,b in zip(tangents,expected)),f"reference priority {index}")
        contracts.require(all(abs(length(value)-1.0)<=1e-12 for value in tangents),f"unit tangents {index}")
        contracts.require(tuple(positions)==before,f"immutable positions {index}");forward.append(tangents)
    reverse=[execute(positions)[0] for positions in reversed(cases)]
    contracts.require(all(all(close_vector(a,b) for a,b in zip(left,right)) for left,right in zip(forward,reversed(reverse))),"query-order determinism")
    preserved,valid,failure=execute(cases[0],False)
    contracts.require(preserved==[] and valid is False and failure=="","false validation no-op after owned clear")
    prefix,valid,failure=execute(((1.,2.,3.),(1.,2.,3.),(1.,2.,3.)),True)
    contracts.require(prefix==[] and valid is False and failure=="tangent_missing","unexpected stationary path fails closed")
    print(f"Carrier-frame tangent contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} forward/reverse paths")


if __name__=="__main__": main()
