"""Exact graph, ownership, and execution contracts for State Clip reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = (
    "StateClipCandidateIdsV1",
    "StateClipCandidateBindingIdsV1",
    "StateClipCandidateAdapterIdsV1",
    "StateClipCandidateAdapterVersionsV1",
    "StateClipCandidateDesiredStatesV1",
    "StateClipCandidateScopesV1",
    "StateClipCandidateRestorePoliciesV1",
    "StateClipCandidatePreviewAllowedV1",
    "StateClipCandidateCodesV1",
)
SCALARS = (
    "StateClipValidationValidV1",
    "StateClipCollectionValidV1",
    "StateClipCommitValidV1",
    "StateClipCandidateValidV1",
    "StateClipCurrentActiveV1",
    "StateClipResultValidV1",
)
PRESERVED = (
    "StateClipIdsV1", "StateClipStartTimesV1", "StateClipEndTimesV1",
    "StateClipDesiredStatesV1", "StateClipEnterLeadSecondsV1",
    "StateClipExitLeadSecondsV1", "StateClipScopesV1",
    "StateClipRestorePoliciesV1", "StateClipConflictPoliciesV1",
    "StateClipFailurePoliciesV1", "StateClipTimeoutSecondsV1",
    "StateClipPreviewPoliciesV1", "StateClipBindingIdsV1",
    "StateClipBindingTypesV1", "StateClipBindingRegionsV1",
    "StateClipBindingAdapterIdsV1", "StateClipBindingAdapterVersionsV1",
    "StateClipBindingEnabledV1", "StateClipBindingReauthorizedV1",
    "StateClipPlanDurationV1", "StateClipPlanValidV1",
    "StateClipQueryTimeV1", "StateClipQueryScrubbingV1",
    "StateClipLocalPreviewRequestedV1", "StateClipResultIdsV1",
    "StateClipResultBindingIdsV1", "StateClipResultAdapterIdsV1",
    "StateClipResultAdapterVersionsV1", "StateClipResultDesiredStatesV1",
    "StateClipResultScopesV1", "StateClipResultRestorePoliciesV1",
    "StateClipResultPreviewAllowedV1", "StateClipResultCodesV1",
    "StateClipResultTimeV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_state_clip_reset_contract_base", path)
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
    contracts.require(len(nodes) == (24 if args.paste else 25), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = [node for node in nodes.values() if member(node) == "Array_Clear"]
    contracts.require(len(clears) == 9, "candidate clear count")
    root = nodes["K2Node_CallArrayFunction_0"]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to first clear")
    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in getters} == set(ARRAYS), "candidate clear ownership")
    contracts.require({member(node) for node in setters} == set(SCALARS), "scalar reset ownership")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "plan/query/result snapshot mutation")

    state = {name: ["poison"] for name in ARRAYS}
    state.update({name: True for name in SCALARS})
    state.update({name: [name] for name in PRESERVED})
    before = {name: state[name] for name in PRESERVED}
    for name in ARRAYS:
        state[name] = []
    for name in SCALARS:
        state[name] = False
    contracts.require(all(state[name] == [] for name in ARRAYS), "candidate arrays not cleared")
    contracts.require(not any(state[name] for name in SCALARS), "stage/result authority not invalidated")
    contracts.require(all(state[name] == before[name] for name in PRESERVED), "preserved state changed")
    print(
        f"State Clip evaluation reset contracts passed ({'paste' if args.paste else 'full'}): "
        f"{len(nodes)} nodes"
    )


if __name__ == "__main__":
    main()
