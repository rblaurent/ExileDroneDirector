"""Structural and executable contracts for success-only Cue ledger commit."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


SUCCESS_CODES = frozenset(("executed", "state_satisfied"))


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_ledger_commit_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def commit(*, authorization_valid=True, authorized=True, selection_valid=True,
           receipt_valid=True, execution_succeeded=True, execution_code="executed",
           dispatch_index=0, cue_ids=("cue",), loop_iteration=0, direction=1,
           ledger_ids=(), ledger_loops=(), ledger_directions=(),
           candidate_ids=("poison",), candidate_loops=(99,), candidate_directions=(-1,)):
    result = {
        "commit_valid": False,
        "candidate_already_executed": False,
        "code": "event_ledger_commit_unavailable",
        "ledger_ids": ledger_ids,
        "ledger_loops": ledger_loops,
        "ledger_directions": ledger_directions,
        "candidate_ids": candidate_ids,
        "candidate_loops": candidate_loops,
        "candidate_directions": candidate_directions,
    }
    if not (authorization_valid and authorized and selection_valid):
        result["code"] = "event_authorization_invalid"
        return result
    if not receipt_valid:
        result["code"] = "event_execution_receipt_invalid"
        return result
    if not execution_succeeded:
        result["code"] = "event_adapter_execution_failed"
        return result
    if execution_code not in SUCCESS_CODES:
        result["code"] = "event_adapter_success_code_invalid"
        return result
    if dispatch_index < 0 or dispatch_index >= len(cue_ids):
        result["code"] = "event_selection_index_invalid"
        return result
    cue_id = cue_ids[dispatch_index]
    if not cue_id:
        result["code"] = "event_identity_invalid"
        return result
    if loop_iteration < 0 or direction not in (-1, 1):
        result["code"] = "event_playback_context_invalid"
        return result
    if not len(ledger_ids) == len(ledger_loops) == len(ledger_directions):
        result["code"] = "event_ledger_invalid"
        return result
    key = (cue_id, loop_iteration, direction)
    if key in tuple(zip(ledger_ids, ledger_loops, ledger_directions)):
        result.update(
            commit_valid=True,
            candidate_already_executed=True,
            code="event_ledger_already_committed",
        )
        return result
    if len(ledger_ids) >= 1024:
        result["code"] = "event_ledger_full"
        return result
    staged_ids = (*ledger_ids, cue_id)
    staged_loops = (*ledger_loops, loop_iteration)
    staged_directions = (*ledger_directions, direction)
    result.update(
        commit_valid=True,
        code="event_ledger_committed",
        ledger_ids=staged_ids,
        ledger_loops=staged_loops,
        ledger_directions=staged_directions,
        candidate_ids=staged_ids,
        candidate_loops=staged_loops,
        candidate_directions=staged_directions,
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
    contracts.require(len(nodes) == (92 if args.paste else 93), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    contracts.require(member(root) == "EventLedgerCommitValidV1", "ledger authority fail-closes first")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry fail-closes ledger commit")
    contracts.require(text.count('MemberName="Array_Length"') == 4, "Cue plus three ledger lengths")
    contracts.require(text.count("StandardMacros:ForEachLoop") == 1, "one duplicate scan")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 3, "Cue and aligned ledger reads")
    contracts.require(text.count('MemberName="Array_Add"') == 3, "three candidate-only appends")
    contracts.require(text.count('MemberName="Array_Clear"') == 0, "authoritative arrays are never cleared")
    contracts.require(text.count('MemberName="Array_Remove"') == 0, "commit never removes ledger entries")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 12, "exact typed guard chain")
    contracts.require(text.count('MemberName="EqualEqual_StrStr"') == 3, "two success codes plus duplicate ID")
    contracts.require(text.count('MemberName="NotEqual_StrStr"') == 1, "nonempty selected Cue identity")
    contracts.require(text.count("KismetStringLibrary") == 4, "all string comparisons use reflected owner")

    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("EventLedgerCommitValidV1") == 3, "fail-close, duplicate, and new commit authority")
    contracts.require(writes.count("EventCandidateAlreadyExecutedV1") == 2, "duplicate scratch reset/publication")
    for name in (
        "EventLedgerCandidateIdsV1", "EventLedgerCandidateLoopsV1",
        "EventLedgerCandidateDirectionsV1", "EventLedgerIdsV1",
        "EventLedgerLoopsV1", "EventLedgerDirectionsV1",
    ):
        contracts.require(writes.count(name) == 1, f"single atomic staging/publication write {name}")
    codes = (
        "event_ledger_commit_unavailable", "event_authorization_invalid",
        "event_execution_receipt_invalid", "event_adapter_execution_failed",
        "event_adapter_success_code_invalid", "event_selection_index_invalid",
        "event_identity_invalid", "event_playback_context_invalid",
        "event_ledger_invalid", "event_ledger_already_committed",
        "event_ledger_full", "event_ledger_candidate_invalid",
        "event_ledger_committed",
    )
    for code in codes:
        contracts.require(f'DefaultValue="{code}"' in text, f"typed result {code}")
    for required in (
        "EventDispatchResultValidV1", "EventDispatchAuthorizedV1",
        "EventSelectionValidV1", "EventAdapterExecutionResultValidV1",
        "EventAdapterExecutionSucceededV1", "EventAdapterExecutionCodeV1",
        "EventDispatchIndexV1", "EventCueIdsV1", "EventLoopIterationV1",
        "EventDirectionV1", "EventLedgerIdsV1", "EventLedgerLoopsV1",
        "EventLedgerDirectionsV1",
    ):
        contracts.require(required in text, f"required commit input {required}")
    for forbidden in (
        "EventCueRepeatPoliciesV1", "EventCuePayloadsV1", "EventCueAdapterIdsV1",
        "EventResolvedBindingIdsV1", "EventGrantedPermissionsV1",
        "CameraTransform", "DroneCamera", "Repository", "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden policy/owner {forbidden}")

    failure_cases = (
        ({"authorization_valid": False}, "event_authorization_invalid"),
        ({"authorized": False}, "event_authorization_invalid"),
        ({"selection_valid": False}, "event_authorization_invalid"),
        ({"receipt_valid": False}, "event_execution_receipt_invalid"),
        ({"execution_succeeded": False}, "event_adapter_execution_failed"),
        ({"execution_code": "adapter_failed"}, "event_adapter_success_code_invalid"),
        ({"dispatch_index": -1}, "event_selection_index_invalid"),
        ({"dispatch_index": 1}, "event_selection_index_invalid"),
        ({"cue_ids": ("",)}, "event_identity_invalid"),
        ({"loop_iteration": -1}, "event_playback_context_invalid"),
        ({"direction": 0}, "event_playback_context_invalid"),
        ({"ledger_ids": ("a",), "ledger_loops": (), "ledger_directions": ()}, "event_ledger_invalid"),
        ({"ledger_ids": tuple(f"c-{i}" for i in range(1024)),
          "ledger_loops": tuple(0 for _ in range(1024)),
          "ledger_directions": tuple(1 for _ in range(1024))}, "event_ledger_full"),
    )
    for overrides, expected_code in failure_cases:
        prior_ids = overrides.get("ledger_ids", ("prior",))
        prior_loops = overrides.get("ledger_loops", (7,))
        prior_directions = overrides.get("ledger_directions", (-1,))
        if expected_code == "event_ledger_full":
            prior_loops = overrides["ledger_loops"]
            prior_directions = overrides["ledger_directions"]
        observed = commit(
            ledger_ids=prior_ids, ledger_loops=prior_loops,
            ledger_directions=prior_directions, **{
                key: value for key, value in overrides.items()
                if key not in ("ledger_ids", "ledger_loops", "ledger_directions")
            },
        )
        contracts.require(not observed["commit_valid"], f"failure authority {expected_code}")
        contracts.require(observed["code"] == expected_code, f"failure code {expected_code}")
        contracts.require(observed["ledger_ids"] is prior_ids, f"failure ID identity {expected_code}")
        contracts.require(observed["ledger_loops"] is prior_loops, f"failure loop identity {expected_code}")
        contracts.require(observed["ledger_directions"] is prior_directions, f"failure direction identity {expected_code}")

    for code in SUCCESS_CODES:
        observed = commit(execution_code=code, cue_ids=("accepted",), loop_iteration=3, direction=-1)
        contracts.require(observed["commit_valid"] and observed["code"] == "event_ledger_committed", f"success {code}")
        contracts.require(
            tuple(zip(observed["ledger_ids"], observed["ledger_loops"], observed["ledger_directions"]))
            == (("accepted", 3, -1),), f"exact key {code}",
        )

    prior_ids = ("cue",)
    prior_loops = (2,)
    prior_directions = (-1,)
    duplicate = commit(
        loop_iteration=2, direction=-1, ledger_ids=prior_ids,
        ledger_loops=prior_loops, ledger_directions=prior_directions,
    )
    contracts.require(duplicate["commit_valid"] and duplicate["candidate_already_executed"], "duplicate idempotent success")
    contracts.require(duplicate["code"] == "event_ledger_already_committed", "duplicate typed code")
    contracts.require(duplicate["ledger_ids"] is prior_ids, "duplicate preserves authoritative identity")

    rng = random.Random(0xEDD930)
    for case in range(100):
        count = rng.randint(0, 40)
        triples = tuple((f"cue-{i}", rng.randint(0, 5), rng.choice((-1, 1))) for i in range(count))
        event_id = f"new-{case}"
        loop_iteration = rng.randint(0, 5)
        direction = rng.choice((-1, 1))
        observed = commit(
            execution_code=rng.choice(tuple(SUCCESS_CODES)), cue_ids=(event_id,),
            loop_iteration=loop_iteration, direction=direction,
            ledger_ids=tuple(item[0] for item in triples),
            ledger_loops=tuple(item[1] for item in triples),
            ledger_directions=tuple(item[2] for item in triples),
        )
        result_triples = tuple(zip(
            observed["ledger_ids"], observed["ledger_loops"], observed["ledger_directions"]
        ))
        contracts.require(observed["commit_valid"], f"seeded authority {case}")
        contracts.require(result_triples == (*triples, (event_id, loop_iteration, direction)), f"seeded append {case}")
        contracts.require(len(observed["candidate_ids"]) == len(triples) + 1, f"seeded candidate alignment {case}")

    print(
        f"Bounded event ledger commit contracts passed "
        f"({'paste' if args.paste else 'full'}): success-only atomic publication and typed failures"
    )


if __name__ == "__main__":
    main()
