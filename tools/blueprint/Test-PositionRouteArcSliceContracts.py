"""Exact executable topology contracts for one compiled position-route arc slice."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_position_arc_slice_contract", path)
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
    c.require(len(nodes) == (67 if args.paste else 68), f"exact node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")

    def all_(member: str):
        return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]

    def one(member: str):
        found = all_(member)
        c.require(len(found) == 1, f"one {member}: {len(found)}")
        return found[0]

    def authored_default(node, pin: str) -> str | None:
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', node.pins[pin].body)
        return match.group(1) if match else None

    out_us = one("TrajectoryArcInputUsV1")
    out_distances = one("TrajectoryArcInputDistancesV1")
    clears = all_("Array_Clear")
    c.require(len(clears) == 2, "two destination clears")
    clear_us = next(node for node in clears if c.linked(out_us, "TrajectoryArcInputUsV1", node, "TargetArray"))
    clear_distances = next(node for node in clears if c.linked(out_distances, "TrajectoryArcInputDistancesV1", node, "TargetArray"))
    c.require_link(clear_us, "then", clear_distances, "execute", "destination reset order")

    for name, zero in (
        ("TrajectoryArcInputLengthV1", "0.0"),
        ("TrajectoryArcInputDistanceAlphaV1", "0.0"),
        ("TrajectoryArcResultUV1", "0.0"),
        ("TrajectoryArcResultValidV1", "false"),
    ):
        setters = [node for node in all_(name) if "K2Node_VariableSet" in node.node_class]
        c.require(any(authored_default(node, name) == zero for node in setters), f"fail-closed reset {name}")

    index = one("PositionRouteResultSegmentIndexV1")
    compile_valid = one("PositionRouteCompileValidV1")
    distance_alpha = one("PositionRouteResultDistanceAlphaV1")
    sources = {
        "starts": one("PositionRouteCompiledArcSampleStartsV1"),
        "counts": one("PositionRouteCompiledArcSampleCountsV1"),
        "us": one("PositionRouteCompiledArcUsV1"),
        "distances": one("PositionRouteCompiledArcDistancesV1"),
        "lengths": one("PositionRouteCompiledSegmentLengthsV1"),
    }
    lengths = all_("Array_Length")
    c.require(len(lengths) == 5, "five source cardinalities")
    source_pins = {
        "starts": "PositionRouteCompiledArcSampleStartsV1",
        "counts": "PositionRouteCompiledArcSampleCountsV1",
        "us": "PositionRouteCompiledArcUsV1",
        "distances": "PositionRouteCompiledArcDistancesV1",
        "lengths": "PositionRouteCompiledSegmentLengthsV1",
    }
    length_by_source = {
        key: next(node for node in lengths if c.linked(source, source_pins[key], node, "TargetArray"))
        for key, source in sources.items()
    }
    equal_int = all_("EqualEqual_IntInt")
    c.require(len(equal_int) == 3, "metadata and flat-array cardinality equality checks")
    c.require(any(c.linked(length_by_source["counts"], "ReturnValue", node, "A") and c.linked(length_by_source["starts"], "ReturnValue", node, "B") for node in equal_int), "count/start cardinality")
    c.require(any(c.linked(length_by_source["lengths"], "ReturnValue", node, "A") and c.linked(length_by_source["starts"], "ReturnValue", node, "B") for node in equal_int), "length/start cardinality")
    c.require(any(c.linked(length_by_source["us"], "ReturnValue", node, "A") and c.linked(length_by_source["distances"], "ReturnValue", node, "B") for node in equal_int), "flat-array cardinality")

    c.require(len(all_("GreaterEqual_IntInt")) == 3, "nonnegative index/start and minimum count")
    c.require(len(all_("Less_IntInt")) == 1, "selected index upper bound")
    c.require(len(all_("LessEqual_IntInt")) == 1, "flat slice end bound")
    c.require(len(all_("GreaterEqual_DoubleDouble")) == 4, "finite/lower bounds for alpha and length")
    c.require(len(all_("LessEqual_DoubleDouble")) == 3, "finite/upper bounds for alpha and length")
    c.require(len(all_("BooleanAND")) == 15, "complete preflight and selected-slice conjunctions")
    c.require(len(all_("Add_IntInt")) == 1, "flat loop index")
    c.require(len(all_("Subtract_IntInt")) == 2, "overflow-safe remaining count and inclusive loop end")

    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    adds = all_("Array_Add")
    c.require(len(branches) == 2, "preflight and selected-slice guards")
    c.require(len(loops) == 1, "one bounded copy loop")
    c.require(len(items) == 5, "start, count, length, u, and distance reads")
    c.require(len(adds) == 2, "one u and one distance append")
    loop = loops[0]
    start_item = next(node for node in items if c.linked(sources["starts"], "PositionRouteCompiledArcSampleStartsV1", node, "Array"))
    count_item = next(node for node in items if c.linked(sources["counts"], "PositionRouteCompiledArcSampleCountsV1", node, "Array"))
    segment_length_item = next(node for node in items if c.linked(sources["lengths"], "PositionRouteCompiledSegmentLengthsV1", node, "Array"))
    for selected in (start_item, count_item, segment_length_item):
        c.require_link(index, "PositionRouteResultSegmentIndexV1", selected, "Dimension 1", "selected segment metadata index")
    flat_u_item = next(node for node in items if c.linked(sources["us"], "PositionRouteCompiledArcUsV1", node, "Array"))
    flat_distance_item = next(node for node in items if c.linked(sources["distances"], "PositionRouteCompiledArcDistancesV1", node, "Array"))
    flat_index = next(node for node in all_("Add_IntInt") if c.linked(loop, "Index", node, "B"))
    c.require_link(start_item, "Output", flat_index, "A", "flat index begins at selected start")
    c.require_link(flat_index, "ReturnValue", flat_u_item, "Dimension 1", "u flat index")
    c.require_link(flat_index, "ReturnValue", flat_distance_item, "Dimension 1", "distance flat index")
    add_us = next(node for node in adds if c.linked(out_us, "TrajectoryArcInputUsV1", node, "TargetArray"))
    add_distances = next(node for node in adds if c.linked(out_distances, "TrajectoryArcInputDistancesV1", node, "TargetArray"))
    c.require_link(loop, "LoopBody", add_us, "execute", "bounded copy body")
    c.require_link(flat_u_item, "Output", add_us, "NewItem", "append selected u")
    c.require_link(add_us, "then", add_distances, "execute", "parallel append order")
    c.require_link(flat_distance_item, "Output", add_distances, "NewItem", "append selected distance")

    result_valid = [node for node in all_("TrajectoryArcResultValidV1") if "K2Node_VariableSet" in node.node_class]
    accept = next(node for node in result_valid if authored_default(node, "TrajectoryArcResultValidV1") == "true")
    store_length = next(node for node in all_("TrajectoryArcInputLengthV1") if "K2Node_VariableSet" in node.node_class and c.linked(loop, "Completed", node, "execute"))
    store_alpha = next(node for node in all_("TrajectoryArcInputDistanceAlphaV1") if "K2Node_VariableSet" in node.node_class and c.linked(store_length, "then", node, "execute"))
    c.require_link(segment_length_item, "Output", store_length, "TrajectoryArcInputLengthV1", "stage selected segment length")
    c.require_link(distance_alpha, "PositionRouteResultDistanceAlphaV1", store_alpha, "TrajectoryArcInputDistanceAlphaV1", "stage selected distance alpha")
    c.require_link(store_alpha, "then", accept, "execute", "validity is final staging write")
    c.require(not accept.pins["then"].links, "staging terminates at validity")

    if args.paste:
        c.require(not clear_us.pins["execute"].links, "paste root intentionally has no native entry seam")
    else:
        c.require_link(entries[0], "then", clear_us, "execute", "entry starts fail-closed reset")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Position route arc-slice contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
