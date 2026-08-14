"""Policy-free orchestration contracts for named camera-look composition."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CALLS = (
    "ResetCameraLookCompositionV1",
    "ValidateCameraLookInputsV1",
    "BuildCameraLookBaseValuesV1",
    "ApplyCameraLookAuthoredOverridesV1",
    "CommitCameraLookCompositionV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_look_compose_contract", path)
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
    contracts.require(len(nodes) == (5 if args.paste else 6), f"node count {len(nodes)}")
    calls = [next(node for node in nodes.values() if member(node) == name) for name in CALLS]
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    if entries:
        contracts.require_link(entries[0], "then", calls[0], "execute", "reset first")
    else:
        contracts.require(not calls[0].pins["execute"].links, "paste root")
    for left, right in zip(calls, calls[1:]):
        contracts.require_link(left, "then", right, "execute", "exact ordered stage")
    contracts.require(not [node for node in nodes.values() if "K2Node_Variable" in node.node_class or "K2Node_IfThenElse" in node.node_class or "K2Node_MacroInstance" in node.node_class], "no hidden state or policy")
    contracts.require(not calls[-1].pins["then"].links, "commit terminal")
    contracts.require(tuple(member(node) for node in calls) == CALLS, "exact stage identity")
    print(f"Camera base-look compose contracts passed ({'paste' if args.paste else 'full'}): exact five-stage order")


if __name__ == "__main__":
    main()
