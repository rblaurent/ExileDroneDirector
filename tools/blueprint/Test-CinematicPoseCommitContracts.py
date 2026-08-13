"""Exact atomic-publication contracts for compiled cinematic pose timelines."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


RESET_DEFAULTS = {
    "CinematicPoseCompiledTotalSecondsV1": "0.0",
    "CinematicPoseCompileValidV1": "false",
    "CinematicPoseResultSegmentIndexV1": "-1",
    "CinematicPoseResultLocalTimeAlphaV1": "0.0",
    "CinematicPoseResultDistanceAlphaV1": "0.0",
    "CinematicPoseResultCurveUV1": "0.0",
    "CinematicPoseResultCompleteV1": "false",
    "CinematicPoseResultValidV1": "false",
}
COMPONENTS = (
    "PositionRouteCompileValidV1",
    "OrientationTrackCompileValidV1",
    "PositionRouteCompiledTotalSecondsV1",
    "OrientationTrackCompiledTotalSecondsV1",
    "PositionRouteCompiledDurationsV1",
    "OrientationTrackCompiledDurationsV1",
    "PositionRouteCompiledSegmentStartsV1",
    "OrientationTrackCompiledSegmentStartsV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_commit_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return None if match is None else match.group(1)


def members(nodes, name, node_class=None):
    return [
        node
        for node in nodes.values()
        if f'MemberName="{name}"' in node.text and (node_class is None or node_class in node.node_class)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (56 if args.paste else 57), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")

    reset_chain = []
    reset_names = (
        "CinematicPoseCompiledTotalSecondsV1",
        "CinematicPoseCompileValidV1",
        "CinematicPoseResultSegmentIndexV1",
        "CinematicPoseResultLocalTimeAlphaV1",
        "CinematicPoseResultDistanceAlphaV1",
        "CinematicPoseResultCurveUV1",
        "CinematicPoseResultPositionV1",
        "CinematicPoseResultQuatV1",
        "CinematicPoseResultCompleteV1",
        "CinematicPoseResultValidV1",
    )
    for name in reset_names:
        setters = members(nodes, name, "K2Node_VariableSet")
        reset = next((node for node in setters if default(node, name) != "true"), None)
        contracts.require(reset is not None, f"reset setter {name}")
        if name in RESET_DEFAULTS:
            contracts.require(default(reset, name) == RESET_DEFAULTS[name], f"reset default {name}")
        reset_chain.append(reset)
    if args.paste:
        contracts.require(not reset_chain[0].pins["execute"].links, "paste root exposed")
    else:
        contracts.require_link(entries[0], "then", reset_chain[0], "execute", "entry to first reset")
    for left, right in zip(reset_chain, reset_chain[1:]):
        contracts.require_link(left, "then", right, "execute", "complete ordered reset")

    for name in COMPONENTS:
        contracts.require(len(members(nodes, name, "K2Node_VariableGet")) == 1, f"one component read {name}")
        contracts.require(not members(nodes, name, "K2Node_VariableSet"), f"component publication must remain immutable: {name}")
    stage_getters = members(nodes, "CinematicPoseStageValidV1", "K2Node_VariableGet")
    stage_setters = members(nodes, "CinematicPoseStageValidV1", "K2Node_VariableSet")
    contracts.require(len(stage_getters) == 2, "preflight and final stage reads")
    contracts.require(len(stage_setters) == 2 and all(default(node, "CinematicPoseStageValidV1") == "false" for node in stage_setters), "sticky failure-only stage writes")

    lengths = [node for node in nodes.values() if 'MemberName="Array_Length"' in node.text]
    contracts.require(len(lengths) == 4, "four component timeline lengths")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 1, "one full timeline walk")
    loop = loops[0]
    position_durations = members(nodes, "PositionRouteCompiledDurationsV1", "K2Node_VariableGet")[0]
    contracts.require_link(position_durations, "PositionRouteCompiledDurationsV1", loop, "Array", "position durations drive validation")
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    contracts.require(len(items) == 3, "orientation duration and both start reads")
    contracts.require(all(contracts.linked(loop, "Array Index", node, "Dimension 1") for node in items), "all cross-track reads use same segment index")
    real_equals = [node for node in nodes.values() if 'MemberName="EqualEqual_DoubleDouble"' in node.text]
    contracts.require(len(real_equals) == 3, "total duration and start equalities")
    contracts.require(any(contracts.linked(loop, "Array Element", node, "A") for node in real_equals), "per-segment duration equality")
    position_total = members(nodes, "PositionRouteCompiledTotalSecondsV1", "K2Node_VariableGet")[0]
    orientation_total = members(nodes, "OrientationTrackCompiledTotalSecondsV1", "K2Node_VariableGet")[0]
    contracts.require(any(contracts.linked(position_total, "PositionRouteCompiledTotalSecondsV1", node, "A") and contracts.linked(orientation_total, "OrientationTrackCompiledTotalSecondsV1", node, "B") for node in real_equals), "exact total equality")

    publish_total = next(
        node
        for node in members(nodes, "CinematicPoseCompiledTotalSecondsV1", "K2Node_VariableSet")
        if node is not reset_chain[0]
    )
    publish_valid = next(
        node
        for node in members(nodes, "CinematicPoseCompileValidV1", "K2Node_VariableSet")
        if default(node, "CinematicPoseCompileValidV1") == "true"
    )
    contracts.require_link(position_total, "PositionRouteCompiledTotalSecondsV1", publish_total, "CinematicPoseCompiledTotalSecondsV1", "published total source")
    contracts.require_link(publish_total, "then", publish_valid, "execute", "validity must publish last")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 3, "preflight item and final branches")
    contracts.require(any(contracts.linked(loop, "Completed", node, "execute") and contracts.linked(node, "then", publish_total, "execute") for node in branches), "publication only after complete walk")

    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Cinematic pose commit contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
