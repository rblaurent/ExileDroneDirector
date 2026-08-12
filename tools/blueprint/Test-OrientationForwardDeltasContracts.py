"""Exact structural contracts for adjacent-key orientation log deltas."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_forward_delta_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load(args.project_root)
    nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (19 if args.paste else 20), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")

    def one(member: str):
        matches = [node for node in nodes.values() if f'MemberName="{member}"' in node.text]
        c.require(len(matches) == 1, f"one {member}: {len(matches)}")
        return matches[0]

    candidate = one("OrientationTrackCandidateForwardDeltasV1")
    aligned = one("OrientationTrackCandidateAlignedQuatsV1")
    durations = one("OrientationTrackInputDurationsV1")
    stage_nodes = [node for node in nodes.values() if 'MemberName="OrientationTrackStageValidV1"' in node.text]
    c.require(len(stage_nodes) == 2, "one stage getter and one rejecting setter")
    stage_get = next(node for node in stage_nodes if "K2Node_VariableGet" in node.node_class)
    reject = next(node for node in stage_nodes if "K2Node_VariableSet" in node.node_class)
    c.require('DefaultValue="false"' in reject.pins["OrientationTrackStageValidV1"].body, "rejection must write false")

    clear = one("Array_Clear")
    loop = next(node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class)
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(items) == 2, "two aligned-key reads")
    plus_one = one("Add_IntInt")
    set_start = one("OrientationInputStartQuatV1")
    set_end = one("OrientationInputEndQuatV1")
    primitive = one("ComputeOrientationLogDeltaV1")
    primitive_valid = one("OrientationResultValidV1")
    result = one("OrientationResultDeltaVectorV1")
    append = one("Array_Add")

    c.require_link(candidate, "OrientationTrackCandidateForwardDeltasV1", clear, "TargetArray", "candidate reset")
    c.require_link(durations, "OrientationTrackInputDurationsV1", loop, "Array", "one iteration per segment")
    c.require_link(loop, "Array Index", plus_one, "A", "end offset source")
    c.require('DefaultValue="1"' in plus_one.pins["B"].body, "end offset")
    start_item = next(node for node in items if c.linked(loop, "Array Index", node, "Dimension 1"))
    end_item = next(node for node in items if c.linked(plus_one, "ReturnValue", node, "Dimension 1"))
    for item in items:
        c.require_link(aligned, "OrientationTrackCandidateAlignedQuatsV1", item, "Array", "aligned read")
    c.require_link(start_item, "Output", set_start, "OrientationInputStartQuatV1", "primitive start")
    c.require_link(end_item, "Output", set_end, "OrientationInputEndQuatV1", "primitive end")
    c.require_link(set_start, "then", set_end, "execute", "atomic primitive staging")
    c.require_link(set_end, "then", primitive, "execute", "primitive invocation")

    guards = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(guards) == 3, "outer, per-iteration, and primitive-result guards")
    stage_guards = [node for node in guards if c.linked(stage_get, "OrientationTrackStageValidV1", node, "Condition")]
    c.require(len(stage_guards) == 2, "stage must gate entry and every iteration")
    outer = next(node for node in stage_guards if c.linked(node, "then", loop, "Exec"))
    inner = next(node for node in stage_guards if c.linked(loop, "LoopBody", node, "execute"))
    c.require_link(inner, "then", set_start, "execute", "valid iteration route")
    result_guard = next(node for node in guards if c.linked(primitive_valid, "OrientationResultValidV1", node, "Condition"))
    c.require_link(result_guard, "then", append, "execute", "valid delta append")
    c.require_link(result_guard, "else", reject, "execute", "primitive failure is sticky")
    c.require_link(candidate, "OrientationTrackCandidateForwardDeltasV1", append, "TargetArray", "append target")
    c.require_link(result, "OrientationResultDeltaVectorV1", append, "NewItem", "append value")

    c.require('PinType.ContainerType=Array' in candidate.pins["OrientationTrackCandidateForwardDeltasV1"].body, "vector output array")
    c.require("/Script/CoreUObject.Vector" in append.pins["NewItem"].body, "vector append type")
    c.require("/Script/CoreUObject.Quat" in start_item.pins["Output"].body, "start quat type")
    c.require("/Script/CoreUObject.Quat" in end_item.pins["Output"].body, "end quat type")
    c.require('bSelfContext=True' in primitive.text, "primitive self context")
    if args.paste:
        c.require(not clear.pins["execute"].links, "paste root")
    else:
        c.require_link(entries[0], "then", clear, "execute", "entry seam")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Orientation forward-delta contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
