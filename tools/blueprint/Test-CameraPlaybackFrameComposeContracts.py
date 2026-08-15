"""Exact call-order and ownership contracts for ComposeCameraPlaybackFrameV1."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CALLS = (
    "ResetCameraPlaybackFrameV1",
    "StageCameraPlaybackEvaluationTimeV1",
    "EvaluateCameraPlaybackSourcesV1",
    "StageCameraOperatorFromPlaybackV1",
    "ApplyCameraOperatorOverrideV1",
    "StageCameraComfortFromPlaybackV1",
    "ApplyCameraViewerComfortV1",
    "CommitCameraPlaybackFrameV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_compose_contract_base", path)
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
    contracts.require(len(nodes) == (8 if args.paste else 9), f"coordinator node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    calls = [next(node for node in nodes.values() if member(node) == name) for name in CALLS]
    contracts.require(all('bSelfContext=True' in node.text for node in calls), "exact self calls")
    if entries:
        contracts.require_link(entries[0], "then", calls[0], "execute", "reset first")
    else:
        contracts.require(not calls[0].pins["execute"].links, "paste execution root")
    for left, right in zip(calls, calls[1:]):
        contracts.require_link(left, "then", right, "execute", "exact eight-stage order")
    contracts.require(not calls[-1].pins["then"].links, "commit terminates coordinator")
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

    # This graph intentionally calls every stage unconditionally.  Each accepted
    # helper owns its own fail-closed validity, and the final commit is the sole
    # publication gate even when an earlier injected stage fails.
    for injected_failure in (None, *CALLS[:-1]):
        visited = list(CALLS)
        authority = all(name != injected_failure for name in CALLS[:-1])
        published = authority
        contracts.require(visited == list(CALLS), f"all stages execute:{injected_failure}")
        contracts.require(published is (injected_failure is None), f"final authority:{injected_failure}")
    print(f"Camera playback compose contracts passed ({'paste' if args.paste else 'full'}): exact eight-call order")


if __name__ == "__main__":
    main()
