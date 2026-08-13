"""Executable contracts for distinct gimbal source sampling."""

from __future__ import annotations

import argparse
import copy
import math
import random
import sys
from pathlib import Path


def pitch(degrees):
    half = math.radians(degrees) * 0.5
    return 0.0, math.sin(half), 0.0, math.cos(half)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    contract = __import__("importlib.util").util.spec_from_file_location("edd_source_gimbal_base", args.project_root / "tools/blueprint/Test-AirframeSourcePositionBodyProfileSamplesContracts.py")
    base = __import__("importlib.util").util.module_from_spec(contract); sys.modules[contract.name] = base; contract.loader.exec_module(base)
    contracts = base.load_module(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_source_gimbal_parse_base")
    trajectory = str(args.project_root / "tools/trajectory")
    if trajectory not in sys.path: sys.path.insert(0, trajectory)
    modules = {
        "cinematic": base.load_module(args.project_root / "tools/trajectory/cinematic_reference.py", "edd_source_gimbal_cinematic"),
        "orientation": base.load_module(args.project_root / "tools/trajectory/orientation_reference.py", "orientation_reference"),
        "profiles": base.load_module(args.project_root / "tools/trajectory/flight_profile_reference.py", "flight_profile_reference"),
        "smoothed": base.load_module(args.project_root / "tools/trajectory/smoothed_flight_profile_reference.py", "smoothed_flight_profile_reference"),
        "prebake": base.load_module(args.project_root / "tools/trajectory/airframe_gimbal_prebake_reference.py", "airframe_gimbal_prebake_reference"),
    }
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (79 if args.paste else 80), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = [node for node in nodes.values() if base.member(node) == "Array_Clear"]
    adds = [node for node in nodes.values() if base.member(node) == "Array_Add"]
    contracts.require(len(clears) == len(adds) == 1, "one gimbal clear and append")
    macros = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(macros) == 2 and sum("Array" in node.pins for node in macros) == 1 and sum("FirstIndex" in node.pins for node in macros) == 1, "timeline and sample loops")
    for name in ("CompileOrientationTrackV1", "EvaluateCompiledPositionRouteV1", "EvaluateCompiledOrientationTrackV1"):
        found = [node for node in nodes.values() if base.member(node) == name]
        contracts.require(len(found) == 1 and "bSelfContext=True" in found[0].text, f"one self call {name}")
    contracts.require(not [node for node in nodes.values() if base.member(node) == "EvaluateSmoothedFlightProfileV1"], "gimbal never resamples profiles")
    contracts.require(len([node for node in nodes.values() if base.member(node) == "FMin"]) == 1, "terminal elapsed clamp")
    contracts.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 3, "three timeline reads")
    stage_sets = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and base.member(node) == base.STAGE]
    contracts.require(len(stage_sets) == 3 and all(base.explicit_default(node, base.STAGE) == "false" for node in stage_sets), "three sticky rejection writes")
    protected = {name for name, _kind in base.OUTPUTS}
    contracts.require(not [node for node in nodes.values() if base.member(node) in protected], "body/profile candidates remain graph-immutable")
    gimbal_members = [node for node in nodes.values() if base.member(node) == "AirframeSourceCandidateGimbalQuatsV1"]
    contracts.require(len(gimbal_members) == 1, "one gimbal getter shared by clear and append")
    known = set(nodes); external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}"); contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute forbidden")

    directed = [((1.0,),0.25,None),((1.0,),0.3,None),((0.4,0.6),0.2,("hybrid","fpv_cinewhoop")),((0.5,)*5,0.25,tuple(modules["profiles"].PROFILE_ORDER))]
    cases=[]; rng=random.Random(0xEDD5407)
    for seed,(durations,step,overrides) in enumerate(directed): cases.append((durations,step,overrides,seed))
    for seed in range(40):
        count=rng.randint(2,7); durations=tuple(rng.choice((0.2,0.3,0.5)) for _ in range(count-1)); overrides=tuple(modules["profiles"].PROFILE_ORDER[(seed+i)%5] for i in range(count-1)); cases.append((durations,rng.choice((0.1,0.2)),overrides,seed+20))
    forward=[]
    for index,(durations,step,overrides,seed) in enumerate(cases):
        state,position,body,profiles,times=base.make_case(modules,durations,step,overrides,seed)
        completed=base.expected(modules,position,body,profiles,times)
        for name,_kind in base.OUTPUTS: state[name]=copy.deepcopy(completed[name])
        authored=tuple(pitch(seed*0.5-i*7.0) for i in range(len(durations)+1)); gimbal=modules["orientation"].compile_orientation_track(authored,tuple(durations))
        state["AirframeSourceInputGimbalWaypointQuatsV1"]=list(authored); state["AirframeSourceCandidateGimbalQuatsV1"]=["poison"]
        wanted=[modules["orientation"].evaluate_orientation(gimbal,t).rotation for t in times]
        protected_snapshot={name:copy.deepcopy(state[name]) for name,_kind in base.OUTPUTS}
        result=base.Interpreter(nodes,state,modules).run()
        contracts.require(result[base.STAGE] is True and result[base.INDEX] == len(times)-1, f"valid terminal state {index}")
        contracts.require(base.close_nested(result["AirframeSourceCandidateGimbalQuatsV1"],wanted), f"valid gimbal {index}")
        contracts.require({name:result[name] for name in protected_snapshot} == protected_snapshot, f"protected source mutation {index}")
        forward.append(tuple(result["AirframeSourceCandidateGimbalQuatsV1"]))
        poisoned=copy.deepcopy(state); poisoned["AirframeSourceCandidateGimbalQuatsV1"]=list(reversed(wanted))+["stale"]
        repeat=base.Interpreter(nodes,poisoned,modules).run(); contracts.require(base.close_nested(repeat["AirframeSourceCandidateGimbalQuatsV1"],wanted), f"poison repeat {index}")
    reverse=[]
    for durations,step,overrides,seed in reversed(cases):
        state,position,body,profiles,times=base.make_case(modules,durations,step,overrides,seed); completed=base.expected(modules,position,body,profiles,times)
        for name,_kind in base.OUTPUTS: state[name]=copy.deepcopy(completed[name])
        authored=tuple(pitch(seed*0.5-i*7.0) for i in range(len(durations)+1)); state["AirframeSourceInputGimbalWaypointQuatsV1"]=list(authored); state["AirframeSourceCandidateGimbalQuatsV1"]=["poison"]
        reverse.append(tuple(base.Interpreter(nodes,state,modules).run()["AirframeSourceCandidateGimbalQuatsV1"]))
    contracts.require(forward == list(reversed(reverse)), "forward/reverse independence")

    durations,step,overrides,seed=((0.4,0.6),0.2,("hybrid","fpv_cinewhoop"),99)
    state,position,body,profiles,times=base.make_case(modules,durations,step,overrides,seed); completed=base.expected(modules,position,body,profiles,times)
    for name,_kind in base.OUTPUTS: state[name]=copy.deepcopy(completed[name])
    state["AirframeSourceInputGimbalWaypointQuatsV1"]=[pitch(-i*7.0) for i in range(3)]; state["AirframeSourceCandidateGimbalQuatsV1"]=["poison"]
    protected_snapshot={name:copy.deepcopy(state[name]) for name,_kind in base.OUTPUTS}
    for label,failures,prefix in (("position",{"position":2},2),("orientation",{"orientation":3},3),("agreement",{"agreement":2},2)):
        result=base.Interpreter(nodes,state,modules,failures).run(); contracts.require(result[base.STAGE] is False and len(result["AirframeSourceCandidateGimbalQuatsV1"]) == prefix, f"{label} prefix"); contracts.require({name:result[name] for name in protected_snapshot} == protected_snapshot, f"{label} protected mutation")
    compile_failure=base.Interpreter(nodes,state,modules,{"compile":True}).run(); contracts.require(compile_failure[base.STAGE] is False and not compile_failure["AirframeSourceCandidateGimbalQuatsV1"], "compile rejection")
    for index,mutation in enumerate(({"OrientationTrackCompiledTotalSecondsV1":9.0},{"OrientationTrackCompiledDurationsV1":[0.3,0.7]},{"OrientationTrackCompiledSegmentStartsV1":[0.0,0.5]},{"OrientationTrackCompiledDurationsV1":[1.0]})):
        result=base.Interpreter(nodes,state,modules,timeline_mutation=mutation).run(); contracts.require(result[base.STAGE] is False and not result["AirframeSourceCandidateGimbalQuatsV1"], f"timeline rejection {index}")
    guarded=copy.deepcopy(state); guarded[base.STAGE]=False; guarded["AirframeSourceInputGimbalWaypointQuatsV1"]=object(); result=base.Interpreter(nodes,guarded,modules).run()
    contracts.require(result[base.STAGE] is False and not result["AirframeSourceCandidateGimbalQuatsV1"] and {name:result[name] for name in protected_snapshot} == protected_snapshot, "false-stage clear-only guard")
    print(f"Airframe source gimbal contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} valid, poisoned repeats, protected body/profile state, helper/timeline failures")


if __name__ == "__main__": main()
