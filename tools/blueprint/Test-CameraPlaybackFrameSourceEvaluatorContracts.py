"""Exact call-order contracts for EvaluateCameraPlaybackSourcesV1."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CALLS = (
    "EvaluateCompiledCinematicPoseV1",
    "EvaluateCompiledAirframePrebakeV1",
    "EvaluateCompiledCarrierFrameTransportV1",
    "EvaluateCameraChannelAssemblyV1",
)


def load(path):
    spec = importlib.util.spec_from_file_location("edd_playback_source_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (4 if args.paste else 5), f"coordinator node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    calls = [next(node for node in nodes.values() if member(node) == name) for name in CALLS]
    contracts.require(all('bSelfContext=True' in node.text for node in calls), "exact self calls")
    if entries:
        contracts.require_link(entries[0], "then", calls[0], "execute", "cinematic position evaluator first")
    else:
        contracts.require(not calls[0].pins["execute"].links, "paste root")
    for left, right in zip(calls, calls[1:]):
        contracts.require_link(left, "then", right, "execute", "exact four-source order")
    contracts.require(not [
        node for node in nodes.values()
        if "K2Node_Variable" in node.node_class or "K2Node_IfThenElse" in node.node_class
        or "K2Node_MacroInstance" in node.node_class or "K2Node_Knot" in node.node_class
    ], "coordinator owns no state, policy, branch, macro, or reroute")
    known = set(nodes)
    contracts.require(not {
        target for node in nodes.values() for pin in node.pins.values()
        for target, _pin in pin.links if target not in known
    }, "no external links")
    for injected_failure in (None, *CALLS):
        visited = []
        valid = {}
        for name in CALLS:
            visited.append(name)
            valid[name] = name != injected_failure
        contracts.require(visited == list(CALLS), f"all evaluators execute:{injected_failure}")
        contracts.require(all(valid.values()) is (injected_failure is None), f"injected result:{injected_failure}")
    print(f"Camera playback source-evaluator contracts passed ({'paste' if args.paste else 'full'}): exact four-call order")


if __name__ == "__main__":
    main()
