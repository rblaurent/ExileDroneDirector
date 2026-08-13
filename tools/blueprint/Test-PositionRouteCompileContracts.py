"""Exact ordering contract for the end-to-end position-route compiler."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


STAGES = (
    "ResetPositionRouteCandidateV1",
    "ValidatePositionRouteInputsV1",
    "ComputePositionRouteVelocitiesV1",
    "BuildPositionRouteSegmentsV1",
    "CommitCompiledPositionRouteV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_position_compile_contract", path)
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
    contracts.require(len(nodes) == (5 if args.paste else 6), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")

    calls = []
    for name in STAGES:
        found = [node for node in nodes.values() if f'MemberName="{name}"' in node.text]
        contracts.require(len(found) == 1, f"one call {name}")
        contracts.require("bSelfContext=True" in found[0].text, f"self call {name}")
        calls.append(found[0])
    for left, right in zip(calls, calls[1:]):
        contracts.require_link(left, "then", right, "execute", f"ordered {left.name} -> {right.name}")
    if args.paste:
        contracts.require(not calls[0].pins["execute"].links, "paste root")
    else:
        contracts.require_link(entries[0], "then", calls[0], "execute", "entry reset seam")

    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _pin in pin.links
        if target not in known
    }
    contracts.require(not external, f"external {external}")
    print(f"position route compile contracts passed: {args.graph} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
