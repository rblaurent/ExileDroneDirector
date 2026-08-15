"""Exact ownership and executable contracts for bounded event result reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


DEFAULTS = {
    "EventPlanValidationValidV1": "false",
    "EventCrossingCollectionValidV1": "false",
    "EventSelectionValidV1": "false",
    "EventCandidateAlreadyExecutedV1": "false",
    "EventDispatchResultValidV1": "false",
    "EventDispatchAuthorizedV1": "false",
    "EventDispatchIndexV1": "-1",
    "EventDispatchCodeV1": "event_dispatch_unavailable",
}
PRESERVED = (
    "EventCueIdsV1", "EventCueTimesV1", "EventCueAdapterIdsV1",
    "EventCuePlanValidV1", "EventFlypathIdV1", "EventImmutableRevisionV1",
    "EventRequestedRevisionV1", "EventSessionIdV1", "EventSessionTokenV1",
    "EventRequesterIdV1", "EventPlaybackStartedV1", "EventScrubbingV1",
    "EventPreviousTimeV1", "EventCurrentTimeV1", "EventLoopIterationV1",
    "EventDirectionV1", "EventCrossedIndicesV1", "EventLedgerIdsV1",
    "EventLedgerLoopsV1", "EventLedgerDirectionsV1",
)
FORBIDDEN = (
    "CameraTransform", "CameraPlayback", "DroneCamera", "Repository",
    "FlypathDocument", "K2_SetActor", "FunctionName", "HUD", "UI",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_event_reset_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[name].body)
    return "" if match is None else match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (8 if args.paste else 9), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = sorted(
        (node for node in nodes.values() if "K2Node_VariableSet" in node.node_class),
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    contracts.require(len(setters) == 8, "exact setter count")
    contracts.require({member(node) for node in setters} == set(DEFAULTS), "exact reset ownership")
    if args.paste:
        contracts.require(not setters[0].pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", setters[0], "execute", "event reset entry")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", "exact reset chain")
    for node in setters:
        name = member(node)
        contracts.require(default(node, name) == DEFAULTS[name], f"{name} default")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "plan/query/ledger preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "external ownership forbidden")

    sentinels = {name: object() for name in PRESERVED}
    state = dict(sentinels)
    state.update(DEFAULTS)
    contracts.require(all(state[name] is sentinels[name] for name in PRESERVED), "preserved identity")
    contracts.require(state == {**sentinels, **DEFAULTS}, "reset changes exactly stage and result fields")
    print(
        f"Bounded event dispatch reset contracts passed "
        f"({'paste' if args.paste else 'full'}): plan, query, and ledger preserved"
    )


if __name__ == "__main__":
    main()
