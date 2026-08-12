"""Exact structural and semantic contracts for arc-table inversion."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load(root):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_arc_table_contract", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args(); c = load(args.project_root); nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (97 if args.paste else 98), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")
    def all_(member): return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]
    def setters(member): return [node for node in all_(member) if "VariableSet" in node.node_class]

    reset_names = (
        "TrajectoryArcResultUV1", "TrajectoryArcResultValidV1",
        "TrajectoryArcScratchUpperIndexV1", "TrajectoryArcScratchValidV1",
    )
    reset_defaults = ("0.0", "false", "-1", "true")
    reset = []
    for name, default in zip(reset_names, reset_defaults):
        matches = [node for node in setters(name) if f'DefaultValue="{default}"' in node.pins[name].body]
        c.require(matches, f"reset {name}"); reset.append(matches[0])
    if args.paste: c.require(not reset[0].pins["execute"].links, "paste root")
    else: c.require(c.linked(entries[0], "then", reset[0], "execute"), "native entry seam")
    for left, right in zip(reset, reset[1:]): c.require(c.linked(left, "then", right, "execute"), "reset chain")

    for name in ("TrajectoryArcInputUsV1", "TrajectoryArcInputDistancesV1"):
        c.require(len(all_(name)) == 1, f"one array source {name}")
    c.require(len(all_("Array_Length")) == 2, "two array lengths")
    c.require(len([node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]) == 1, "one bounded scan")
    c.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 11, "eleven exact reads")
    c.require(len(all_("GreaterEqual_DoubleDouble")) == 6, "finite lower, nonnegative, target, found")
    c.require(len(all_("LessEqual_DoubleDouble")) == 7, "finite upper, monotonic, zero/plateau")
    c.require(len(all_("Less_DoubleDouble")) == 1, "strict u ordering")
    c.require(len(all_("GreaterEqual_IntInt")) == 2, "shape and found index")
    c.require(len(all_("Greater_IntInt")) == 1, "skip first loop item")
    c.require(len(all_("EqualEqual_IntInt")) == 2, "cardinality and first-upper stickiness")
    c.require(len(all_("EqualEqual_DoubleDouble")) == 4, "four endpoint equalities")
    c.require(len(all_("BooleanAND")) == 18, "complete sticky conjunction chain")
    c.require(len(all_("BooleanOR")) == 1, "zero length or found")
    c.require(len(all_("Subtract_IntInt")) == 3, "last/previous/left indexes")
    c.require(len(all_("Subtract_DoubleDouble")) == 3, "span/relative/u span")
    c.require(len(all_("Multiply_DoubleDouble")) == 2, "target and scaled u")
    c.require(len(all_("Divide_DoubleDouble")) == 1 and len(all_("Add_DoubleDouble")) == 1, "interpolation arithmetic")
    c.require(len([node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]) == 8, "all validation and result branches")
    c.require(len(setters("TrajectoryArcResultUV1")) == 4, "reset, zero, plateau, interpolated result")
    c.require(len(setters("TrajectoryArcResultValidV1")) == 4, "reset plus three success families")
    c.require(len(setters("TrajectoryArcScratchValidV1")) == 4, "reset plus shape/endpoint/item failures")
    c.require(len(setters("TrajectoryArcScratchUpperIndexV1")) == 2, "reset and first upper selection")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Arc table inversion contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__": main()
