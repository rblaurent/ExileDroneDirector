"""Structural and executable contracts for direction-correct Cue selection."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_selection_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def select(*, crossing_valid=True, crossed=(), cue_ids=(), repeat_policies=(),
           ledger_ids=(), ledger_loops=(), ledger_directions=(),
           loop_iteration=0, direction=1):
    result = {
        "selection_valid": False,
        "candidate_already_executed": False,
        "result_valid": False,
        "authorized": False,
        "index": -1,
        "code": "event_selection_invalid",
    }
    if not crossing_valid:
        return result
    if not (len(ledger_ids) == len(ledger_loops) == len(ledger_directions) <= 1024):
        return result
    if not crossed:
        result.update(selection_valid=True, code="no_event_crossing")
        return result
    for cue_index in crossed:
        result["candidate_already_executed"] = False
        cue_id = cue_ids[cue_index]
        repeat_policy = repeat_policies[cue_index]
        for ledger_id, ledger_loop, ledger_direction in zip(
            ledger_ids, ledger_loops, ledger_directions
        ):
            same_iteration = (
                ledger_loop == loop_iteration and ledger_direction == direction
            )
            repeated = ledger_id == cue_id and (
                repeat_policy != "every_loop" or same_iteration
            )
            if repeated:
                result["candidate_already_executed"] = True
        if not result["candidate_already_executed"] and (
            direction == -1 or result["index"] < 0
        ):
            result["index"] = cue_index
    result["selection_valid"] = True
    result["code"] = (
        "event_authorization_pending"
        if result["index"] >= 0
        else "event_already_executed"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (65 if args.paste else 66), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    contracts.require(member(root) == "EventSelectionValidV1", "selection execution root")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry fail-closes selection")
    contracts.require(text.count('MemberName="Array_Length"') == 4, "crossing plus aligned ledger lengths")
    contracts.require(text.count("StandardMacros:ForEachLoop") == 2, "crossing and nested ledger loops")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 4, "Cue and ledger indexed reads")
    contracts.require(text.count('MemberName="EqualEqual_StrStr"') == 2, "Cue ID and every-loop comparisons")
    contracts.require(text.count("KismetStringLibrary") == 2, "string comparisons use reflected owner")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 5, "exact preflight, crossing, ledger, selection, and final guards")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("EventSelectionValidV1") == 4, "fail-closed plus three terminal selection states")
    contracts.require(writes.count("EventCandidateAlreadyExecutedV1") == 3, "root, per-candidate reset, and match publication")
    contracts.require(writes.count("EventDispatchResultValidV1") == 1, "result authority invalidated")
    contracts.require(writes.count("EventDispatchAuthorizedV1") == 1, "authorization invalidated")
    contracts.require(writes.count("EventDispatchIndexV1") == 2, "index reset and selected candidate")
    contracts.require(writes.count("EventDispatchCodeV1") == 4, "invalid, empty, pending, and exhausted diagnostics")
    contracts.require(len(writes) == 15, "selection owns only stage, scratch, and result staging")
    for required in (
        "EventCrossingCollectionValidV1", "EventCrossedIndicesV1",
        "EventCueIdsV1", "EventCueRepeatPoliciesV1", "EventLedgerIdsV1",
        "EventLedgerLoopsV1", "EventLedgerDirectionsV1",
        "EventLoopIterationV1", "EventDirectionV1",
    ):
        contracts.require(required in text, f"required selection input {required}")
    for forbidden in (
        "EventCueAdapterIdsV1", "EventCueOperationIdsV1", "EventCueScopesV1",
        "EventCuePayloadsV1", "EventCueBindingIdsV1", "EventResolvedBindingIdsV1",
        "EventGrantedPermissionsV1", "EventRemainingRateBudgetV1",
        "CameraTransform", "DroneCamera", "Repository", "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden authorization/owner {forbidden}")

    rng = random.Random(0xEDD920)
    for case in range(100):
        count = rng.randint(1, 24)
        ids = tuple(f"cue-{index}" for index in range(count))
        policies = tuple(rng.choice(("once_per_session", "every_loop", "manual_reset")) for _ in ids)
        crossed = tuple(sorted(rng.sample(range(count), rng.randint(0, count))))
        loop_iteration = rng.randint(0, 5)
        ledger = []
        for cue_index in crossed:
            if rng.choice((False, True)):
                if policies[cue_index] == "every_loop" and rng.choice((False, True)):
                    ledger.append((ids[cue_index], loop_iteration + 1, 1))
                else:
                    ledger.append((ids[cue_index], loop_iteration, 1))
        ledger_ids = tuple(item[0] for item in ledger)
        ledger_loops = tuple(item[1] for item in ledger)
        ledger_directions = tuple(item[2] for item in ledger)
        for direction in (1, -1):
            observed = select(
                crossed=crossed, cue_ids=ids, repeat_policies=policies,
                ledger_ids=ledger_ids, ledger_loops=ledger_loops,
                ledger_directions=ledger_directions,
                loop_iteration=loop_iteration, direction=direction,
            )
            eligible = []
            for cue_index in crossed:
                already = any(
                    ledger_id == ids[cue_index] and (
                        policies[cue_index] != "every_loop"
                        or (ledger_loop == loop_iteration and ledger_direction == direction)
                    )
                    for ledger_id, ledger_loop, ledger_direction in ledger
                )
                if not already:
                    eligible.append(cue_index)
            expected_index = (-1 if not eligible else eligible[0 if direction == 1 else -1])
            contracts.require(observed["selection_valid"], f"seeded authority {case}/{direction}")
            contracts.require(observed["index"] == expected_index, f"seeded index {case}/{direction}")
            contracts.require(not observed["result_valid"] and not observed["authorized"], f"selection cannot authorize {case}")
    invalid = select(crossing_valid=False)
    contracts.require(not invalid["selection_valid"] and invalid["index"] == -1, "invalid crossing fail closed")
    malformed = select(crossed=(0,), cue_ids=("a",), repeat_policies=("once_per_session",), ledger_ids=("a",), ledger_loops=())
    contracts.require(not malformed["selection_valid"], "malformed ledger fail closed")
    empty = select(crossed=())
    contracts.require(empty["selection_valid"] and empty["code"] == "no_event_crossing", "empty crossing is typed no-op")
    print(
        f"Bounded event Cue selection contracts passed "
        f"({'paste' if args.paste else 'full'}): 200 direction/ledger queries plus failures"
    )


if __name__ == "__main__":
    main()
