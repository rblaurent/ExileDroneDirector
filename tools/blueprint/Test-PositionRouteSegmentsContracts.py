"""Exact topology contracts for candidate position-segment assembly."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_position_segments_contract", path)
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
    c.require(len(nodes) == (77 if args.paste else 78), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")

    def all_(member: str):
        return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]

    def one(member: str):
        found = all_(member)
        c.require(len(found) == 1, f"one {member}: {len(found)}")
        return found[0]

    candidate_arrays = (
        ("PositionRouteCandidateSegmentStartsV1", "real"),
        ("PositionRouteCandidateArcSampleStartsV1", "int"),
        ("PositionRouteCandidateArcSampleCountsV1", "int"),
        ("PositionRouteCandidateArcUsV1", "real"),
        ("PositionRouteCandidateArcDistancesV1", "real"),
        ("PositionRouteCandidateSegmentLengthsV1", "real"),
    )
    candidates = {name: one(name) for name, _kind in candidate_arrays}
    clears = all_("Array_Clear")
    c.require(len(clears) == 6, "six candidate clears")
    for name, _kind in candidate_arrays:
        c.require(sum(c.linked(candidates[name], name, clear, "TargetArray") for clear in clears) == 1, f"clear {name}")

    scalar_nodes = {}
    for name in (
        "PositionRouteCandidateTotalSecondsV1",
        "PositionRouteCandidateTotalDistanceV1",
        "PositionRouteCandidateOperationCountV1",
    ):
        found = all_(name)
        c.require(len(found) == 3, f"reset/get/commit {name}")
        getters = [node for node in found if "K2Node_VariableGet" in node.node_class]
        setters = [node for node in found if "K2Node_VariableSet" in node.node_class]
        c.require(len(getters) == 1 and len(setters) == 2, f"scalar node kinds {name}")
        resets = [node for node in setters if not node.pins[name].links]
        c.require(len(resets) == 1, f"zero reset {name}")
        c.require('DefaultValue="0"' in resets[0].pins[name].body or 'DefaultValue="0.0"' in resets[0].pins[name].body, f"zero default {name}")
        scalar_nodes[name] = (getters[0], resets[0], next(node for node in setters if node is not resets[0]))

    stage_nodes = all_("PositionRouteStageValidV1")
    c.require(len(stage_nodes) == 2, "stage getter/reject")
    stage = next(node for node in stage_nodes if "K2Node_VariableGet" in node.node_class)
    reject = next(node for node in stage_nodes if "K2Node_VariableSet" in node.node_class)
    c.require('DefaultValue="false"' in reject.pins["PositionRouteStageValidV1"].body, "sticky reject false")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 3, "outer inner primitive guards")
    stage_guards = [node for node in branches if c.linked(stage, "PositionRouteStageValidV1", node, "Condition")]
    c.require(len(stage_guards) == 1, "per-segment sticky guard")

    positions = one("PositionRouteInputWaypointPositionsV1")
    velocities = one("PositionRouteCandidateWaypointVelocitiesV1")
    all_lengths = all_("Array_Length")
    c.require(len(all_lengths) == 4, "input cardinalities plus flat offset/count")
    position_count = next(node for node in all_lengths if c.linked(positions, "PositionRouteInputWaypointPositionsV1", node, "TargetArray"))
    velocity_count = next(node for node in all_lengths if c.linked(velocities, "PositionRouteCandidateWaypointVelocitiesV1", node, "TargetArray"))
    counts_match = one("EqualEqual_IntInt")
    c.require_link(position_count, "ReturnValue", counts_match, "A", "position cardinality")
    c.require_link(velocity_count, "ReturnValue", counts_match, "B", "velocity cardinality")
    ready = one("BooleanAND")
    c.require_link(stage, "PositionRouteStageValidV1", ready, "A", "prior stage readiness")
    c.require_link(counts_match, "ReturnValue", ready, "B", "velocity cardinality readiness")
    outer = next(node for node in branches if c.linked(ready, "ReturnValue", node, "Condition"))
    c.require_link(outer, "else", reject, "execute", "invalid readiness rejects")

    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    c.require(len(loops) == 3, "segment/u/distance loops")
    durations = one("PositionRouteInputDurationsV1")
    segment_loop = next(node for node in loops if c.linked(durations, "PositionRouteInputDurationsV1", node, "Array"))
    c.require_link(segment_loop, "LoopBody", stage_guards[0], "execute", "per-segment sticky guard")

    curves = one("PositionRouteInputSpatialCurveTypesV1")
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(items) == 5, "two positions, two velocities, one curve")
    c.require(sum(c.linked(positions, "PositionRouteInputWaypointPositionsV1", node, "Array") for node in items) == 2, "position reads")
    c.require(sum(c.linked(velocities, "PositionRouteCandidateWaypointVelocitiesV1", node, "Array") for node in items) == 2, "velocity reads")
    c.require(sum(c.linked(curves, "PositionRouteInputSpatialCurveTypesV1", node, "Array") for node in items) == 1, "curve read")
    int_adds = all_("Add_IntInt")
    c.require(len(int_adds) == 2, "index increment and operation sum")
    plus_one = next(node for node in int_adds if c.linked(segment_loop, "Array Index", node, "A"))
    c.require('DefaultValue="1"' in plus_one.pins["B"].body, "next waypoint index")

    equal_linear = one("EqualEqual_StrStr")
    c.require('DefaultValue="linear"' in equal_linear.pins["B"].body, "linear discriminator")
    make_duration = one("MakeVector")
    for axis in "XYZ":
        c.require_link(segment_loop, "Array Element", make_duration, axis, f"duration vector {axis}")
    vector_multipliers = all_("Multiply_VectorVector")
    c.require(len(vector_multipliers) == 2, "two time-to-u velocity conversions")
    c.require(sum(c.linked(make_duration, "ReturnValue", node, "B") for node in vector_multipliers) == 2, "duration scales both velocities")

    staged_names = (
        "TrajectoryArcBuildInputStartPositionV1",
        "TrajectoryArcBuildInputEndPositionV1",
        "TrajectoryArcBuildInputStartVelocityUV1",
        "TrajectoryArcBuildInputEndVelocityUV1",
        "TrajectoryArcBuildInputStartAccelerationUV1",
        "TrajectoryArcBuildInputEndAccelerationUV1",
        "TrajectoryArcBuildInputLinearV1",
        "TrajectoryArcBuildInputToleranceV1",
        "TrajectoryArcBuildInputMaxDepthV1",
        "TrajectoryArcBuildInputMaxOperationsV1",
    )
    staged = [one(name) for name in staged_names]
    for left, right in zip(staged, staged[1:]):
        c.require_link(left, "then", right, "execute", f"ordered staging {left.name}->{right.name}")
    c.require_link(stage_guards[0], "then", staged[0], "execute", "valid segment starts staging")
    primitive = one("BuildAdaptiveArcTableV1")
    c.require("bSelfContext=True" in primitive.text, "adaptive primitive self context")
    c.require_link(staged[-1], "then", primitive, "execute", "staging invokes primitive")
    arc_valid = one("TrajectoryArcBuildValidV1")
    result_guard = next(node for node in branches if c.linked(arc_valid, "TrajectoryArcBuildValidV1", node, "Condition"))
    c.require_link(primitive, "then", result_guard, "execute", "primitive result guard")
    c.require_link(result_guard, "else", reject, "execute", "primitive failure is sticky")

    adds = all_("Array_Add")
    c.require(len(adds) == 6, "six candidate appends")
    built_us = one("TrajectoryArcBuiltUsV1")
    built_distances = one("TrajectoryArcBuiltDistancesV1")
    built_length = one("TrajectoryArcBuiltLengthV1")
    flat_start = next(node for node in all_lengths if c.linked(candidates["PositionRouteCandidateArcUsV1"], "PositionRouteCandidateArcUsV1", node, "TargetArray"))
    sample_count = next(node for node in all_lengths if c.linked(built_us, "TrajectoryArcBuiltUsV1", node, "TargetArray"))

    def target_add(name: str):
        found = [node for node in adds if c.linked(candidates[name], name, node, "TargetArray")]
        c.require(len(found) == 1, f"one append to {name}")
        return found[0]

    add_segment_start = target_add("PositionRouteCandidateSegmentStartsV1")
    add_arc_start = target_add("PositionRouteCandidateArcSampleStartsV1")
    add_arc_count = target_add("PositionRouteCandidateArcSampleCountsV1")
    add_u = target_add("PositionRouteCandidateArcUsV1")
    add_distance = target_add("PositionRouteCandidateArcDistancesV1")
    add_length = target_add("PositionRouteCandidateSegmentLengthsV1")
    seconds_get, _seconds_reset, seconds_commit = scalar_nodes["PositionRouteCandidateTotalSecondsV1"]
    c.require_link(result_guard, "then", add_segment_start, "execute", "successful primitive begins publication")
    c.require_link(seconds_get, "PositionRouteCandidateTotalSecondsV1", add_segment_start, "NewItem", "cumulative segment start")
    c.require_link(add_segment_start, "then", add_arc_start, "execute", "segment then arc start")
    c.require_link(flat_start, "ReturnValue", add_arc_start, "NewItem", "flat offset captured before append")
    c.require_link(add_arc_start, "then", add_arc_count, "execute", "arc start then count")
    c.require_link(sample_count, "ReturnValue", add_arc_count, "NewItem", "published sample count")

    u_loop = next(node for node in loops if c.linked(built_us, "TrajectoryArcBuiltUsV1", node, "Array"))
    distance_loop = next(node for node in loops if c.linked(built_distances, "TrajectoryArcBuiltDistancesV1", node, "Array"))
    c.require_link(add_arc_count, "then", u_loop, "Exec", "copy u table after metadata")
    c.require_link(u_loop, "LoopBody", add_u, "execute", "append every u")
    c.require_link(u_loop, "Array Element", add_u, "NewItem", "u element")
    c.require_link(u_loop, "Completed", distance_loop, "Exec", "distance copy after u copy")
    c.require_link(distance_loop, "LoopBody", add_distance, "execute", "append every distance")
    c.require_link(distance_loop, "Array Element", add_distance, "NewItem", "distance element")
    c.require_link(distance_loop, "Completed", add_length, "execute", "metadata completion after flat tables")
    c.require_link(built_length, "TrajectoryArcBuiltLengthV1", add_length, "NewItem", "segment length")

    double_adds = all_("Add_DoubleDouble")
    c.require(len(double_adds) == 2, "seconds and distance sums")
    seconds_sum = next(node for node in double_adds if c.linked(seconds_get, "PositionRouteCandidateTotalSecondsV1", node, "A"))
    distance_get, _distance_reset, distance_commit = scalar_nodes["PositionRouteCandidateTotalDistanceV1"]
    distance_sum = next(node for node in double_adds if c.linked(distance_get, "PositionRouteCandidateTotalDistanceV1", node, "A"))
    operations_get, _operations_reset, operations_commit = scalar_nodes["PositionRouteCandidateOperationCountV1"]
    operation_sum = next(node for node in int_adds if node is not plus_one)
    built_operations = one("TrajectoryArcBuildOperationCountV1")
    c.require_link(segment_loop, "Array Element", seconds_sum, "B", "duration accumulation")
    c.require_link(built_length, "TrajectoryArcBuiltLengthV1", distance_sum, "B", "distance accumulation")
    c.require_link(operations_get, "PositionRouteCandidateOperationCountV1", operation_sum, "A", "operation accumulation")
    c.require_link(built_operations, "TrajectoryArcBuildOperationCountV1", operation_sum, "B", "primitive operation count")
    c.require_link(seconds_sum, "ReturnValue", seconds_commit, "PositionRouteCandidateTotalSecondsV1", "commit seconds")
    c.require_link(distance_sum, "ReturnValue", distance_commit, "PositionRouteCandidateTotalDistanceV1", "commit distance")
    c.require_link(operation_sum, "ReturnValue", operations_commit, "PositionRouteCandidateOperationCountV1", "commit operations")
    c.require_link(add_length, "then", seconds_commit, "execute", "totals after complete segment")
    c.require_link(seconds_commit, "then", distance_commit, "execute", "ordered totals")
    c.require_link(distance_commit, "then", operations_commit, "execute", "ordered operation total")

    if args.paste:
        c.require(not clears[0].pins["execute"].links, "paste root")
    else:
        c.require_link(entries[0], "then", clears[0], "execute", "entry-to-clear seam")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Position route segment contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
