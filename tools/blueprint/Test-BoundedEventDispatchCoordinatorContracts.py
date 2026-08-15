"""Exact ordered contracts for DispatchBoundedPlaybackEventsV1."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CALLS = (
    "ResetBoundedEventDispatchResultV1",
    "ValidateBoundedEventPlanV1",
    "CollectCrossedCuesV1",
    "SelectEligibleCrossedCueV1",
    "AuthorizeSelectedCueV1",
)


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_dispatch_coordinator_contract_base", path)
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
    contracts.require(len(nodes) == (5 if args.paste else 6), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    calls = [next(node for node in nodes.values() if member(node) == name) for name in CALLS]
    contracts.require(all("bSelfContext=True" in node.text for node in calls), "exact self calls")
    if entries:
        contracts.require_link(entries[0], "then", calls[0], "execute", "fresh reset first")
    else:
        contracts.require(not calls[0].pins["execute"].links, "paste execution root")
    for left, right in zip(calls, calls[1:]):
        contracts.require_link(left, "then", right, "execute", "exact dispatcher order")
    contracts.require(
        not [
            node for node in nodes.values()
            if "K2Node_Variable" in node.node_class
            or "K2Node_IfThenElse" in node.node_class
            or "K2Node_MacroInstance" in node.node_class
        ],
        "coordinator owns no state, branch, or loop",
    )
    known = set(nodes)
    contracts.require(
        not {
            target for node in nodes.values() for pin in node.pins.values()
            for target, _ in pin.links if target not in known
        },
        "no external graph link",
    )
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute")
    text = args.graph.read_text(encoding="utf-8")
    for forbidden in (
        "CommitCueExecutionLedgerV1", "ResetManualCueLedgerEntryV1",
        "EventAdapterExecution", "EventLedger", "EventCue", "CameraTransform",
        "DroneCamera", "Repository", "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden coordinator policy/owner {forbidden}")

    for failure in (None, *CALLS[1:]):
        state = {
            "calls": [], "plan": False, "crossing": False,
            "selection": False, "result": False, "authorized": False,
        }
        for name in CALLS:
            state["calls"].append(name)
            if name == CALLS[0]:
                state.update(plan=False, crossing=False, selection=False, result=False, authorized=False)
            elif name == "ValidateBoundedEventPlanV1":
                state["plan"] = failure != name
            elif name == "CollectCrossedCuesV1":
                state["crossing"] = state["plan"] and failure != name
            elif name == "SelectEligibleCrossedCueV1":
                state["selection"] = state["crossing"] and failure != name
            elif name == "AuthorizeSelectedCueV1":
                state["result"] = state["selection"]
                state["authorized"] = state["selection"] and failure != name
        contracts.require(state["calls"] == list(CALLS), f"all calls execute {failure}")
        if failure is None:
            contracts.require(state["result"] and state["authorized"], "successful decision publication")
        else:
            contracts.require(not state["authorized"], f"failure remains unauthorized {failure}")
    print(
        f"Bounded event dispatch coordinator contracts passed "
        f"({'paste' if args.paste else 'full'}): exact five-call decision-only order"
    )


if __name__ == "__main__":
    main()
