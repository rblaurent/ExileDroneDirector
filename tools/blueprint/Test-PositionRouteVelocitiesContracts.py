"""Exact topology contracts for position-route waypoint velocity assembly."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_position_velocity_contract", path)
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

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")
    expected_count = 82 if args.paste else 83
    c.require(len(nodes) == expected_count, f"node count {len(nodes)} != {expected_count}")

    def calls(member: str):
        return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]

    def one(member: str):
        values = calls(member)
        c.require(len(values) == 1, f"one {member}: {len(values)}")
        return values[0]

    positions = one("PositionRouteInputWaypointPositionsV1")
    durations = one("PositionRouteInputDurationsV1")
    curves = one("PositionRouteInputSpatialCurveTypesV1")
    candidate = one("PositionRouteCandidateWaypointVelocitiesV1")
    stage = one("PositionRouteStageValidV1")
    clear = one("Array_Clear")
    loop = next(node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class)
    length = one("Array_Length")
    adds = calls("Array_Add")
    c.require(len(adds) == 3, "endpoint, mixed-mode, and computed append paths")
    c.require_link(candidate, "PositionRouteCandidateWaypointVelocitiesV1", clear, "TargetArray", "stale candidate clear")
    c.require_link(positions, "PositionRouteInputWaypointPositionsV1", loop, "Array", "waypoint loop")
    c.require_link(positions, "PositionRouteInputWaypointPositionsV1", length, "TargetArray", "waypoint length")
    for add in adds:
        c.require_link(candidate, "PositionRouteCandidateWaypointVelocitiesV1", add, "TargetArray", "append target")

    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 4, "outer, per-iteration, endpoint, and curve-mode branches")
    c.require(sum(c.linked(stage, "PositionRouteStageValidV1", branch, "Condition") for branch in branches) == 2, "stage precondition gates")
    comparisons = {member: calls(member) for member in (
        "EqualEqual_IntInt", "EqualEqual_StrStr", "BooleanOR", "BooleanAND",
        "Greater_DoubleDouble", "Less_DoubleDouble", "LessEqual_DoubleDouble", "GreaterEqual_DoubleDouble",
    )}
    c.require(len(comparisons["EqualEqual_IntInt"]) == 2, "endpoint comparisons")
    c.require(len(comparisons["EqualEqual_StrStr"]) == 2, "adjacent curve comparisons")
    c.require(all(re.search(r'DefaultValue="auto_cinematic"', node.pins["B"].body) for node in comparisons["EqualEqual_StrStr"]), "curve mode constants")
    c.require(len(comparisons["BooleanOR"]) == 1, "endpoint union")
    c.require(len(comparisons["BooleanAND"]) == 7, "curve and component sign conjunctions")
    c.require(len(comparisons["Greater_DoubleDouble"]) == 6, "positive rate predicates")
    c.require(len(comparisons["Less_DoubleDouble"]) == 6, "negative rate predicates")
    c.require(len(comparisons["LessEqual_DoubleDouble"]) == 3, "positive per-axis minima")
    c.require(len(comparisons["GreaterEqual_DoubleDouble"]) == 3, "negative per-axis maxima")
    c.require(len(calls("Subtract_DoubleDouble")) == 6, "incoming/outgoing component deltas")
    c.require(len(calls("Divide_DoubleDouble")) == 6, "time-normalized component secants")
    c.require(len(calls("SelectFloat")) == 12, "four monotone selections per axis")
    c.require(len(calls("BreakVector")) == 3 and len(calls("MakeVector")) == 1, "vector reconstruction topology")

    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(items) == 6, "two positions, durations, and curves")
    c.require(sum(c.linked(positions, "PositionRouteInputWaypointPositionsV1", item, "Array") for item in items) == 2, "position reads")
    c.require(sum(c.linked(durations, "PositionRouteInputDurationsV1", item, "Array") for item in items) == 2, "duration reads")
    c.require(sum(c.linked(curves, "PositionRouteInputSpatialCurveTypesV1", item, "Array") for item in items) == 2, "curve reads")
    c.require(len(calls("PositionRouteStageValidV1")) == 1, "velocity stage never rewrites validation verdict")
    if args.paste:
        c.require(not clear.pins["execute"].links, "paste clear root")
    else:
        c.require_link(entries[0], "then", clear, "execute", "entry-to-clear seam")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Position route velocity contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
