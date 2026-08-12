"""Exact executable topology contracts for adaptive arc-table publication."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_arc_commit_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    expected = 94 if args.paste else 95
    contracts.require(len(nodes) == expected, f"exact {expected}-node commit graph")

    def all_(member):
        return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]

    def setters(member):
        return [node for node in all_(member) if "K2Node_VariableSet" in node.node_class]

    def getters(member):
        return [node for node in all_(member) if "K2Node_VariableGet" in node.node_class]

    def one(member):
        matches = all_(member)
        contracts.require(len(matches) == 1, f"one {member}")
        return matches[0]

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = all_("Array_Clear")
    contracts.require(len(clears) == 2, "only the two published arrays are cleared")
    reset_length = next(node for node in setters("TrajectoryArcBuiltLengthV1") if 'DefaultValue="0.0"' in node.pins["TrajectoryArcBuiltLengthV1"].body)
    reset_valid = next(node for node in setters("TrajectoryArcBuildValidV1") if 'DefaultValue="false"' in node.pins["TrajectoryArcBuildValidV1"].body)
    contracts.require(len(getters("TrajectoryArcBuiltUsV1")) == 1, "one published-u getter")
    contracts.require(len(getters("TrajectoryArcBuiltDistancesV1")) == 1, "one published-distance getter")
    built_us = getters("TrajectoryArcBuiltUsV1")[0]
    built_distances = getters("TrajectoryArcBuiltDistancesV1")[0]
    clear_us = next(node for node in clears if contracts.linked(built_us, "TrajectoryArcBuiltUsV1", node, "TargetArray"))
    clear_distances = next(node for node in clears if contracts.linked(built_distances, "TrajectoryArcBuiltDistancesV1", node, "TargetArray"))
    if args.paste:
        contracts.require(not clear_us.pins["execute"].links, "paste root intentionally has no entry")
    else:
        contracts.require(contracts.linked(entries[0], "then", clear_us, "execute"), "native entry clears publication first")
    contracts.require(contracts.linked(clear_us, "then", clear_distances, "execute"), "clear published arrays in order")
    contracts.require(contracts.linked(clear_distances, "then", reset_length, "execute"), "clear published length after arrays")
    contracts.require(contracts.linked(reset_length, "then", reset_valid, "execute"), "clear public validity before validation")

    contracts.require(len(all_("Array_Length")) == 8, "five work and three candidate lengths")
    contracts.require(len([node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]) == 1, "one bounded candidate scan")
    contracts.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 7, "four endpoint and three ordered-item reads")
    contracts.require(len(all_("EqualEqual_IntInt")) == 7, "five empty work and two cardinality comparisons")
    contracts.require(len(all_("GreaterEqual_IntInt")) == 1, "minimum table size")
    contracts.require(len(all_("Greater_IntInt")) == 1, "skip first scan item")
    contracts.require(len(all_("EqualEqual_DoubleDouble")) == 4, "exact candidate endpoints")
    contracts.require(len(all_("Less_DoubleDouble")) == 1, "strict u ordering")
    contracts.require(len(all_("LessEqual_DoubleDouble")) == 4, "finite upper bounds and nondecreasing distances")
    contracts.require(len(all_("GreaterEqual_DoubleDouble")) == 4, "finite lower bounds and nonnegative length")
    contracts.require(len(all_("Subtract_IntInt")) == 2, "last and previous indexes")
    contracts.require(len(all_("BooleanAND")) == 23, "complete sticky validation conjunctions")
    contracts.require(len([node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]) == 5, "shape, endpoints, item gate, item validation, and final gates")

    stage_sets = setters("TrajectoryArcBuildStageValidV1")
    contracts.require(len(stage_sets) == 4, "shape, endpoint, item, and final rejection")
    for node in stage_sets:
        contracts.require('DefaultValue="false"' in node.pins["TrajectoryArcBuildStageValidV1"].body, f"{node.name} is sticky false")

    contracts.require(len(getters("TrajectoryArcBuildCandidateUsV1")) == 1, "one candidate-u source")
    contracts.require(len(getters("TrajectoryArcBuildCandidateDistancesV1")) == 1, "one candidate-distance source")
    contracts.require(len(getters("TrajectoryArcBuildCandidateLengthV1")) == 1, "one candidate-length source")
    candidate_us = getters("TrajectoryArcBuildCandidateUsV1")[0]
    candidate_distances = getters("TrajectoryArcBuildCandidateDistancesV1")[0]
    candidate_length = getters("TrajectoryArcBuildCandidateLengthV1")[0]
    published_us = setters("TrajectoryArcBuiltUsV1")
    published_distances = setters("TrajectoryArcBuiltDistancesV1")
    published_lengths = setters("TrajectoryArcBuiltLengthV1")
    published_valid = setters("TrajectoryArcBuildValidV1")
    contracts.require(len(published_us) == 1 and len(published_distances) == 1, "one atomic array publication each")
    contracts.require(len(published_lengths) == 2 and len(published_valid) == 2, "one reset and one publication each")
    contracts.require(contracts.linked(candidate_us, "TrajectoryArcBuildCandidateUsV1", published_us[0], "TrajectoryArcBuiltUsV1"), "publish candidate us by value")
    contracts.require(contracts.linked(candidate_distances, "TrajectoryArcBuildCandidateDistancesV1", published_distances[0], "TrajectoryArcBuiltDistancesV1"), "publish candidate distances by value")
    publish_length = next(node for node in published_lengths if node is not reset_length)
    publish_valid = next(node for node in published_valid if node is not reset_valid)
    contracts.require(contracts.linked(candidate_length, "TrajectoryArcBuildCandidateLengthV1", publish_length, "TrajectoryArcBuiltLengthV1"), "publish exact candidate length")
    contracts.require('DefaultValue="true"' in publish_valid.pins["TrajectoryArcBuildValidV1"].body, "validity becomes true only at transaction end")
    contracts.require(contracts.linked(published_us[0], "then", published_distances[0], "execute"), "publication array order")
    contracts.require(contracts.linked(published_distances[0], "then", publish_length, "execute"), "publication length order")
    contracts.require(contracts.linked(publish_length, "then", publish_valid, "execute"), "validity is final publication write")

    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"no dangling or external links: {external}")
    print(f"adaptive arc commit contracts passed: {args.graph} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
