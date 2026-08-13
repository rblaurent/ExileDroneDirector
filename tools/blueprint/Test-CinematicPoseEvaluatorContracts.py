"""Exact atomic absolute-time contracts for compiled cinematic pose evaluation."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


RESULT_FIELDS = (
    "CinematicPoseResultSegmentIndexV1",
    "CinematicPoseResultLocalTimeAlphaV1",
    "CinematicPoseResultDistanceAlphaV1",
    "CinematicPoseResultCurveUV1",
    "CinematicPoseResultPositionV1",
    "CinematicPoseResultQuatV1",
    "CinematicPoseResultCompleteV1",
    "CinematicPoseResultValidV1",
)
RESET_DEFAULTS = ("-1", "0.0", "0.0", "0.0", None, None, "false", "false")
COMPONENT_READS = (
    "PositionRouteResultValidV1",
    "OrientationTrackResultValidV1",
    "PositionRouteResultSegmentIndexV1",
    "OrientationTrackResultSegmentIndexV1",
    "PositionRouteResultLocalTimeAlphaV1",
    "OrientationTrackResultAlphaV1",
    "PositionRouteResultCompleteV1",
    "OrientationTrackResultCompleteV1",
    "PositionRouteResultDistanceAlphaV1",
    "PositionRouteResultCurveUV1",
    "PositionRouteResultPositionV1",
    "OrientationTrackResultQuatV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_evaluator_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return None if match is None else match.group(1)


def members(nodes, name, node_class=None):
    return [node for node in nodes.values() if f'MemberName="{name}"' in node.text and (node_class is None or node_class in node.node_class)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (64 if args.paste else 65), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")

    field_setters = {name: members(nodes, name, "K2Node_VariableSet") for name in RESULT_FIELDS}
    contracts.require(all(len(value) == 2 for value in field_setters.values()), "exact reset and publication setters")
    first_candidates = field_setters[RESULT_FIELDS[0]]
    if args.paste:
        reset_first = next(node for node in first_candidates if not node.pins["execute"].links)
    else:
        reset_first = next(node for node in first_candidates if contracts.linked(entries[0], "then", node, "execute"))
    reset_chain = [reset_first]
    for name in RESULT_FIELDS[1:]:
        reset_chain.append(next(node for node in field_setters[name] if contracts.linked(reset_chain[-1], "then", node, "execute")))
    for node, name, expected in zip(reset_chain, RESULT_FIELDS, RESET_DEFAULTS):
        actual = default(node, name)
        if name == "CinematicPoseResultPositionV1":
            contracts.require(actual in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"), "position reset")
        elif name == "CinematicPoseResultQuatV1":
            contracts.require(actual in ("0, 0, 0, 1", "(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)"), "quat reset")
        else:
            contracts.require(actual == expected, f"reset default {name}: {actual!r}")

    publications = [next(node for node in field_setters[name] if node not in reset_chain) for name in RESULT_FIELDS]
    for left, right in zip(publications, publications[1:]):
        contracts.require_link(left, "then", right, "execute", "atomic publication order")
    contracts.require(default(publications[-1], "CinematicPoseResultValidV1") == "true", "combined validity publishes true last")

    calls = {}
    for name in ("EvaluateCompiledPositionRouteV1", "EvaluateCompiledOrientationTrackV1"):
        found = members(nodes, name, "K2Node_CallFunction")
        contracts.require(len(found) == 1 and "bSelfContext=True" in found[0].text, f"one self call {name}")
        calls[name] = found[0]
    contracts.require_link(calls["EvaluateCompiledPositionRouteV1"], "then", calls["EvaluateCompiledOrientationTrackV1"], "execute", "position then orientation evaluation")
    position_elapsed = members(nodes, "PositionRouteInputElapsedSecondsV1", "K2Node_VariableSet")
    orientation_elapsed = members(nodes, "OrientationTrackInputElapsedSecondsV1", "K2Node_VariableSet")
    contracts.require(len(position_elapsed) == len(orientation_elapsed) == 1, "one elapsed staging write per component")
    elapsed = members(nodes, "CinematicPoseInputElapsedSecondsV1", "K2Node_VariableGet")[0]
    contracts.require_link(elapsed, "CinematicPoseInputElapsedSecondsV1", position_elapsed[0], "PositionRouteInputElapsedSecondsV1", "position elapsed source")
    contracts.require_link(elapsed, "CinematicPoseInputElapsedSecondsV1", orientation_elapsed[0], "OrientationTrackInputElapsedSecondsV1", "orientation elapsed source")
    contracts.require_link(orientation_elapsed[0], "then", calls["EvaluateCompiledPositionRouteV1"], "execute", "staging before evaluation")

    for name in COMPONENT_READS:
        contracts.require(len(members(nodes, name, "K2Node_VariableGet")) == 1, f"one component result read {name}")
        contracts.require(not members(nodes, name, "K2Node_VariableSet"), f"no direct component result mutation {name}")
    contracts.require(len(members(nodes, "EqualEqual_IntInt", "K2Node_CallFunction")) == 1, "segment equality")
    contracts.require(len(members(nodes, "EqualEqual_BoolBool", "K2Node_CallFunction")) == 1, "completion equality")
    real_equals = members(nodes, "EqualEqual_DoubleDouble", "K2Node_CallFunction")
    contracts.require(len(real_equals) == 3, "two total equalities and local alpha equality")

    source_names = (
        "PositionRouteResultSegmentIndexV1",
        "PositionRouteResultLocalTimeAlphaV1",
        "PositionRouteResultDistanceAlphaV1",
        "PositionRouteResultCurveUV1",
        "PositionRouteResultPositionV1",
        "OrientationTrackResultQuatV1",
        "PositionRouteResultCompleteV1",
    )
    for source_name, result_name, publication in zip(source_names, RESULT_FIELDS, publications):
        source = members(nodes, source_name, "K2Node_VariableGet")[0]
        contracts.require_link(source, source_name, publication, result_name, f"published {result_name} source")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 2, "outer and result commit branches")
    contracts.require(any(contracts.linked(calls["EvaluateCompiledOrientationTrackV1"], "then", node, "execute") and contracts.linked(node, "then", publications[0], "execute") for node in branches), "publication only after both calls and agreement")

    compile_valid = members(nodes, "CinematicPoseCompileValidV1", "K2Node_VariableGet")
    contracts.require(len(compile_valid) == 1, "combined compile validity guard")
    for name in ("PositionRouteCompileValidV1", "OrientationTrackCompileValidV1", "CinematicPoseCompiledTotalSecondsV1", "PositionRouteCompiledTotalSecondsV1", "OrientationTrackCompiledTotalSecondsV1"):
        contracts.require(len(members(nodes, name, "K2Node_VariableGet")) == 1, f"preflight read {name}")
    finite_bounds = [node for node in nodes.values() if 'MemberName="GreaterEqual_DoubleDouble"' in node.text or 'MemberName="LessEqual_DoubleDouble"' in node.text]
    contracts.require(len(finite_bounds) == 4, "finite elapsed and combined-total bounds")

    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Cinematic pose evaluator contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
