"""Exact orchestration contract for complete smoothed-profile evaluation."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


STAGES = (
    "ResetSmoothedFlightProfileV1",
    "StageSmoothedFlightProfileSamplesV1",
    "PublishSmoothedFlightProfileV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_smoothed_profile_evaluate_contract_base", path)
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
    c = load(args.project_root)
    nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (3 if args.paste else 4), f"evaluate node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")
    calls = []
    for name in STAGES:
        found = [node for node in nodes.values() if f'MemberName="{name}"' in node.text]
        c.require(len(found) == 1 and "bSelfContext=True" in found[0].text, f"one self call {name}")
        calls.append(found[0])
    for left, right in zip(calls, calls[1:]):
        c.require_link(left, "then", right, "execute", "reset-stage-publish order")
    if args.paste:
        c.require(not calls[0].pins["execute"].links, "paste reset root")
    else:
        c.require_link(entries[0], "then", calls[0], "execute", "entry reset seam")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knots forbidden")
    c.require(not any("K2Node_Variable" in node.node_class for node in nodes.values()), "orchestrator owns no state")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Smoothed flight-profile evaluate contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
