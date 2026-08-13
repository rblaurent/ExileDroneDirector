"""Exact executable topology contracts for atomic position-route publication."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_position_commit_contract", path)
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
    c.require(len(nodes) == (181 if args.paste else 182), f"exact node count {len(nodes)}")
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

    mappings = (
        ("PositionRouteInputWaypointPositionsV1", "PositionRouteCompiledWaypointPositionsV1"),
        ("PositionRouteInputDurationsV1", "PositionRouteCompiledDurationsV1"),
        ("PositionRouteInputSpatialCurveTypesV1", "PositionRouteCompiledSpatialCurveTypesV1"),
        ("PositionRouteInputTimeProfilesV1", "PositionRouteCompiledTimeProfilesV1"),
        ("PositionRouteCandidateWaypointVelocitiesV1", "PositionRouteCompiledWaypointVelocitiesV1"),
        ("PositionRouteCandidateSegmentStartsV1", "PositionRouteCompiledSegmentStartsV1"),
        ("PositionRouteCandidateArcSampleStartsV1", "PositionRouteCompiledArcSampleStartsV1"),
        ("PositionRouteCandidateArcSampleCountsV1", "PositionRouteCompiledArcSampleCountsV1"),
        ("PositionRouteCandidateArcUsV1", "PositionRouteCompiledArcUsV1"),
        ("PositionRouteCandidateArcDistancesV1", "PositionRouteCompiledArcDistancesV1"),
        ("PositionRouteCandidateSegmentLengthsV1", "PositionRouteCompiledSegmentLengthsV1"),
    )
    clears = all_("Array_Clear")
    c.require(len(clears) == 11, "eleven compiled-array clears")
    sources = {}
    compiled_getters = {}
    compiled_setters = {}
    for source_name, target_name in mappings:
        sources[source_name] = one(source_name)
        target_nodes = all_(target_name)
        c.require(len(target_nodes) == 2, f"compiled get/publish {target_name}")
        getter = next(node for node in target_nodes if "K2Node_VariableGet" in node.node_class)
        setter = next(node for node in target_nodes if "K2Node_VariableSet" in node.node_class)
        c.require(sum(c.linked(getter, target_name, clear, "TargetArray") for clear in clears) == 1, f"clear {target_name}")
        c.require_link(sources[source_name], source_name, setter, target_name, f"publish {source_name}->{target_name}")
        compiled_getters[target_name] = getter
        compiled_setters[target_name] = setter

    c.require(len(all_("Array_Length")) == 11, "eleven source cardinalities")
    point_length = next(node for node in all_("Array_Length") if c.linked(sources["PositionRouteInputWaypointPositionsV1"], "PositionRouteInputWaypointPositionsV1", node, "TargetArray"))
    duration_length = next(node for node in all_("Array_Length") if c.linked(sources["PositionRouteInputDurationsV1"], "PositionRouteInputDurationsV1", node, "TargetArray"))
    flat_u_length = next(node for node in all_("Array_Length") if c.linked(sources["PositionRouteCandidateArcUsV1"], "PositionRouteCandidateArcUsV1", node, "TargetArray"))
    flat_distance_length = next(node for node in all_("Array_Length") if c.linked(sources["PositionRouteCandidateArcDistancesV1"], "PositionRouteCandidateArcDistancesV1", node, "TargetArray"))
    c.require(len(all_("Subtract_IntInt")) == 2, "segment-count and endpoint-index subtraction")
    segment_count = next(node for node in all_("Subtract_IntInt") if c.linked(point_length, "ReturnValue", node, "A"))
    c.require('DefaultValue="1"' in segment_count.pins["B"].body, "segment count is points minus one")
    c.require(any(c.linked(duration_length, "ReturnValue", node, "A") and c.linked(segment_count, "ReturnValue", node, "B") for node in all_("EqualEqual_IntInt")), "duration cardinality")
    c.require(any(c.linked(flat_u_length, "ReturnValue", node, "A") and c.linked(flat_distance_length, "ReturnValue", node, "B") for node in all_("EqualEqual_IntInt")), "flat table cardinality")
    c.require(len(all_("GreaterEqual_IntInt")) == 3, "minimum points, operations, and samples")
    c.require(len(all_("LessEqual_IntInt")) == 2, "maximum points and operation budget")
    c.require(len(all_("Multiply_IntInt")) == 1, "bounded aggregate operation budget")

    total_seconds_nodes = all_("PositionRouteCompiledTotalSecondsV1")
    total_distance_nodes = all_("PositionRouteCompiledTotalDistanceV1")
    c.require(len(total_seconds_nodes) == 4, "seconds reset/get/advance/fail")
    c.require(len(total_distance_nodes) == 4, "distance reset/get/advance/fail")
    seconds_get = next(node for node in total_seconds_nodes if "K2Node_VariableGet" in node.node_class)
    distance_get = next(node for node in total_distance_nodes if "K2Node_VariableGet" in node.node_class)
    compile_valid = all_("PositionRouteCompileValidV1")
    c.require(len(compile_valid) == 2, "compile validity reset and accept")
    reset_valid = next(node for node in compile_valid if authored_default(node, "PositionRouteCompileValidV1") == "false")
    accept_valid = next(node for node in compile_valid if authored_default(node, "PositionRouteCompileValidV1") == "true")
    for name in (
        "PositionRouteResultLocalTimeAlphaV1",
        "PositionRouteResultDistanceAlphaV1",
        "PositionRouteResultCurveUV1",
        "PositionRouteResultPositionV1",
        "PositionRouteResultCompleteV1",
        "PositionRouteResultValidV1",
    ):
        c.require(len(all_(name)) == 1, f"evaluation reset {name}")
    sample_nodes = all_("PositionRouteResultSegmentIndexV1")
    c.require(len(sample_nodes) == 7, "sample accumulator lifecycle")
    sample_get = next(node for node in sample_nodes if "K2Node_VariableGet" in node.node_class)
    sample_setters = [node for node in sample_nodes if "K2Node_VariableSet" in node.node_class]
    c.require(sum(authored_default(node, "PositionRouteResultSegmentIndexV1") == "-1" and not node.pins["PositionRouteResultSegmentIndexV1"].links for node in sample_setters) == 4, "result index reset on entry, preflight rejection, success, and final failure")
    c.require(sum(authored_default(node, "PositionRouteResultSegmentIndexV1") == "0" and not node.pins["PositionRouteResultSegmentIndexV1"].links for node in sample_setters) == 1, "zero sample accumulator init")

    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    c.require(len(loops) == 1, "one bounded segment loop")
    loop = loops[0]
    c.require_link(sources["PositionRouteInputDurationsV1"], "PositionRouteInputDurationsV1", loop, "Array", "duration loop")
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(items) == 8, "four segment metadata and four endpoint reads")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 4, "outer, bounds, endpoint, and final guards")
    stage_nodes = all_("PositionRouteStageValidV1")
    c.require(len(stage_nodes) == 5, "stage getter and four fail-closed writes")
    stage_get = next(node for node in stage_nodes if "K2Node_VariableGet" in node.node_class)
    c.require(all(authored_default(node, "PositionRouteStageValidV1") == "false" for node in stage_nodes if "K2Node_VariableSet" in node.node_class), "every stage write rejects")

    arc_start_item = next(node for node in items if c.linked(sources["PositionRouteCandidateArcSampleStartsV1"], "PositionRouteCandidateArcSampleStartsV1", node, "Array"))
    arc_count_item = next(node for node in items if c.linked(sources["PositionRouteCandidateArcSampleCountsV1"], "PositionRouteCandidateArcSampleCountsV1", node, "Array"))
    length_item = next(node for node in items if c.linked(sources["PositionRouteCandidateSegmentLengthsV1"], "PositionRouteCandidateSegmentLengthsV1", node, "Array"))
    c.require(any(c.linked(arc_start_item, "Output", node, "A") and c.linked(sample_get, "PositionRouteResultSegmentIndexV1", node, "B") for node in all_("EqualEqual_IntInt")), "contiguous arc start equals accumulator")
    c.require(any(c.linked(arc_count_item, "Output", node, "A") and 'DefaultValue="2"' in node.pins["B"].body for node in all_("GreaterEqual_IntInt")), "positive two-endpoint sample count")
    c.require(len(all_("Less_IntInt")) == 1, "endpoint index bounded by flat table")
    c.require(len(all_("EqualEqual_DoubleDouble")) == 7, "start, totals, and four arc endpoint equalities")
    c.require(len(all_("Greater_DoubleDouble")) == 2, "positive total and duration")
    c.require(len(all_("GreaterEqual_DoubleDouble")) == 6, "four finite lower bounds plus nonnegative total and segment distance")
    c.require(len(all_("LessEqual_DoubleDouble")) == 4, "four finite upper bounds")
    c.require(len(all_("Add_DoubleDouble")) == 2, "time and distance accumulators")
    c.require(len(all_("Add_IntInt")) == 2, "endpoint and sample accumulators")
    c.require(len(all_("BooleanAND")) == 38, "complete preflight, finite, per-segment, endpoint, and final conjunctions")

    final_guard = next(node for node in branches if any(c.linked(node, "then", setter, "execute") for setter in sample_setters if authored_default(setter, "PositionRouteResultSegmentIndexV1") == "-1"))
    success_reset = next(node for node in sample_nodes if "K2Node_VariableSet" in node.node_class and c.linked(final_guard, "then", node, "execute"))
    publish = [compiled_setters[target_name] for _source_name, target_name in mappings]
    c.require_link(success_reset, "then", publish[0], "execute", "validated publication starts after result reset")
    for left, right in zip(publish, publish[1:]):
        c.require_link(left, "then", right, "execute", f"atomic publication chain {left.name}->{right.name}")
    c.require_link(publish[-1], "then", accept_valid, "execute", "validity is final publication write")
    c.require(not accept_valid.pins["then"].links, "publication terminates at validity")

    fail_seconds = next(node for node in total_seconds_nodes if "K2Node_VariableSet" in node.node_class and 'DefaultValue="0.0"' in node.pins["PositionRouteCompiledTotalSecondsV1"].body and c.linked(final_guard, "else", node, "execute"))
    fail_distance = next(node for node in total_distance_nodes if "K2Node_VariableSet" in node.node_class and c.linked(fail_seconds, "then", node, "execute"))
    fail_sample = next(node for node in sample_nodes if "K2Node_VariableSet" in node.node_class and c.linked(fail_distance, "then", node, "execute"))
    fail_stage = next(node for node in stage_nodes if "K2Node_VariableSet" in node.node_class and c.linked(fail_sample, "then", node, "execute"))
    c.require(authored_default(fail_stage, "PositionRouteStageValidV1") == "false", "final failure remains sticky")

    if args.paste:
        c.require(not clears[0].pins["execute"].links, "paste root intentionally has no native entry seam")
    else:
        c.require_link(entries[0], "then", clears[0], "execute", "entry begins compiled/evaluation reset")
    c.require(any(c.linked(reset_valid, "then", node, "execute") for node in sample_nodes if "K2Node_VariableSet" in node.node_class), "reset chain reaches sample accumulator lifecycle")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Position route commit contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
