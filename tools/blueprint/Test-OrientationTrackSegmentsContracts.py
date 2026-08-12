"""Exact graph contracts for orientation segment-control/start-time assembly."""
from __future__ import annotations
import argparse, importlib.util, sys
from pathlib import Path

def load(root):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"; spec = importlib.util.spec_from_file_location("edd_track_segments_contract", path); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args(); c = load(args.project_root); nodes = c.parse_graph(args.graph)
    expected = 36 if args.paste else 37; c.require(len(nodes) == expected, f"node count {len(nodes)}")
    entries = [n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class]; c.require(len(entries) == (0 if args.paste else 1), "entry count")
    def all_(member): return [n for n in nodes.values() if f'MemberName="{member}"' in n.text]
    def one(member): values = all_(member); c.require(len(values) == 1, f"one {member}: {len(values)}"); return values[0]
    starts = one("OrientationTrackCandidateSegmentStartsV1"); start_controls = one("OrientationTrackCandidateStartControlsV1"); end_controls = one("OrientationTrackCandidateEndControlsV1")
    clears = all_("Array_Clear"); c.require(len(clears) == 3, "three candidate clears")
    for target, pin in ((starts, "OrientationTrackCandidateSegmentStartsV1"), (start_controls, "OrientationTrackCandidateStartControlsV1"), (end_controls, "OrientationTrackCandidateEndControlsV1")):
        c.require(sum(c.linked(target, pin, clear, "TargetArray") for clear in clears) == 1, f"clear {pin}")
    total_nodes = all_("OrientationTrackCandidateTotalSecondsV1"); c.require(len(total_nodes) == 3, "total reset/get/commit")
    total_get = next(n for n in total_nodes if "K2Node_VariableGet" in n.node_class); total_sets = [n for n in total_nodes if "K2Node_VariableSet" in n.node_class]; c.require(len(total_sets) == 2, "two total setters"); c.require(any('DefaultValue="0.0"' in n.pins["OrientationTrackCandidateTotalSecondsV1"].body for n in total_sets), "total reset zero")
    stage = all_("OrientationTrackStageValidV1"); c.require(len(stage) == 2, "stage getter/reject"); stage_get = next(n for n in stage if "K2Node_VariableGet" in n.node_class); reject = next(n for n in stage if "K2Node_VariableSet" in n.node_class); c.require('DefaultValue="false"' in reject.pins["OrientationTrackStageValidV1"].body, "sticky reject")
    branches = [n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class]; c.require(len(branches) == 3, "outer inner result guards"); c.require(sum(c.linked(stage_get, "OrientationTrackStageValidV1", n, "Condition") for n in branches) == 2, "stage guards")
    loop = next(n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class); durations = one("OrientationTrackInputDurationsV1"); c.require_link(durations, "OrientationTrackInputDurationsV1", loop, "Array", "duration loop")
    aligned = one("OrientationTrackCandidateAlignedQuatsV1"); tangents = one("OrientationTrackCandidateTangentRatesV1"); items = [n for n in nodes.values() if "K2Node_GetArrayItem" in n.node_class]; c.require(len(items) == 4, "four segment reads"); c.require(sum(c.linked(aligned, "OrientationTrackCandidateAlignedQuatsV1", n, "Array") for n in items) == 2, "two quaternion reads"); c.require(sum(c.linked(tangents, "OrientationTrackCandidateTangentRatesV1", n, "Array") for n in items) == 2, "two tangent reads")
    for member in ("OrientationInputStartQuatV1", "OrientationInputEndQuatV1", "OrientationInputStartTangentRateVectorV1", "OrientationInputEndTangentRateVectorV1", "OrientationInputDurationV1"): c.require(len(all_(member)) == 1, f"staged {member}")
    call = one("BuildOrientationSegmentControlsV1"); c.require("bSelfContext=True" in call.text, "primitive self context")
    valid = one("OrientationResultValidV1"); result_guard = next(n for n in branches if c.linked(valid, "OrientationResultValidV1", n, "Condition")); c.require_link(result_guard, "else", reject, "execute", "reject path")
    result_start = one("OrientationResultStartControlQuatV1"); result_end = one("OrientationResultEndControlQuatV1"); adds = all_("Array_Add"); c.require(len(adds) == 3, "three appends")
    c.require(sum(c.linked(starts, "OrientationTrackCandidateSegmentStartsV1", n, "TargetArray") for n in adds) == 1, "start append target"); c.require(sum(c.linked(total_get, "OrientationTrackCandidateTotalSecondsV1", n, "NewItem") for n in adds) == 1, "cumulative start append")
    c.require(sum(c.linked(start_controls, "OrientationTrackCandidateStartControlsV1", n, "TargetArray") for n in adds) == 1, "start control append target"); c.require(sum(c.linked(result_start, "OrientationResultStartControlQuatV1", n, "NewItem") for n in adds) == 1, "start control result")
    c.require(sum(c.linked(end_controls, "OrientationTrackCandidateEndControlsV1", n, "TargetArray") for n in adds) == 1, "end control append target"); c.require(sum(c.linked(result_end, "OrientationResultEndControlQuatV1", n, "NewItem") for n in adds) == 1, "end control result")
    sum_node = one("Add_DoubleDouble"); c.require_link(total_get, "OrientationTrackCandidateTotalSecondsV1", sum_node, "A", "total accumulation"); c.require_link(loop, "Array Element", sum_node, "B", "duration accumulation"); commit = next(n for n in total_sets if c.linked(sum_node, "ReturnValue", n, "OrientationTrackCandidateTotalSecondsV1"))
    if args.paste: c.require(not clears[0].pins["execute"].links, "paste root")
    else: c.require(sum(c.linked(entries[0], "then", clear, "execute") for clear in clears) == 1, "entry seam")
    known = set(nodes); external = {target for n in nodes.values() for pin in n.pins.values() for target, _ in pin.links if target not in known}; c.require(not external, f"external {external}")
    print(f"Orientation track segment contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")

if __name__ == "__main__": main()
