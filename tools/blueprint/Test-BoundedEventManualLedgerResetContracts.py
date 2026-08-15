"""Structural and executable contracts for manual Cue ledger re-arming."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_manual_reset_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def reset(*, plan_valid=True, request_id="manual", cue_ids=("manual",),
          repeat_policies=("manual_reset",), ledger_ids=(), ledger_loops=(),
          ledger_directions=(), candidate_ids=("poison",),
          candidate_loops=(99,), candidate_directions=(-1,)):
    result = {
        "result_valid": False,
        "commit_valid": False,
        "cue_found": False,
        "removed_any": False,
        "candidate_valid": True,
        "code": "event_manual_reset_unavailable",
        "ledger_ids": ledger_ids,
        "ledger_loops": ledger_loops,
        "ledger_directions": ledger_directions,
        "candidate_ids": candidate_ids,
        "candidate_loops": candidate_loops,
        "candidate_directions": candidate_directions,
    }
    if not request_id:
        result["code"] = "event_manual_reset_request_invalid"
        return result
    if not plan_valid:
        result["code"] = "event_manual_reset_plan_invalid"
        return result
    if not (1 <= len(cue_ids) <= 256 and len(cue_ids) == len(repeat_policies)):
        result["code"] = "event_manual_reset_plan_invalid"
        return result
    result["cue_found"] = any(
        cue_id == request_id and policy == "manual_reset"
        for cue_id, policy in zip(cue_ids, repeat_policies)
    )
    if not result["cue_found"]:
        result["code"] = "event_manual_reset_policy_invalid"
        return result
    if not (
        len(ledger_ids) == len(ledger_loops) == len(ledger_directions)
        and len(ledger_ids) <= 1024
    ):
        result["code"] = "event_manual_reset_ledger_invalid"
        return result
    retained = tuple(
        entry for entry in zip(ledger_ids, ledger_loops, ledger_directions)
        if entry[0] != request_id
    )
    result["removed_any"] = len(retained) != len(ledger_ids)
    staged_ids = tuple(entry[0] for entry in retained)
    staged_loops = tuple(entry[1] for entry in retained)
    staged_directions = tuple(entry[2] for entry in retained)
    result.update(
        result_valid=True,
        code=(
            "event_manual_reset_completed"
            if result["removed_any"] else "event_manual_reset_already_armed"
        ),
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
    contracts.require(len(nodes) == (87 if args.paste else 88), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    contracts.require(member(root) == "EventManualResetResultValidV1", "manual authority fail-closes first")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry fail-closes manual reset")
    contracts.require(text.count('MemberName="Array_Length"') == 8, "Cue, ledger, and candidate lengths")
    contracts.require(text.count("StandardMacros:ForEachLoop") == 2, "policy scan and ledger rebuild")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 3, "policy plus aligned ledger reads")
    contracts.require(text.count('MemberName="Array_Clear"') == 3, "three private candidate clears")
    contracts.require(text.count('MemberName="Array_Add"') == 3, "three private retained-entry appends")
    contracts.require(text.count('MemberName="Array_Remove"') == 0, "authoritative arrays are never edited in place")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 10, "exact policy/rebuild guard chain")
    contracts.require(text.count('MemberName="EqualEqual_StrStr"') == 3, "policy ID, manual policy, and removal ID")
    contracts.require(text.count('MemberName="NotEqual_StrStr"') == 1, "nonempty reset request")
    contracts.require(text.count("KismetStringLibrary") == 4, "all strings use reflected owner")

    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("EventManualResetResultValidV1") == 2, "fail-close and terminal authority")
    contracts.require(writes.count("EventLedgerCommitValidV1") == 1, "prior adapter commit authority invalidated")
    contracts.require(writes.count("EventManualResetCueFoundV1") == 2, "policy scratch reset and mark")
    contracts.require(writes.count("EventManualResetRemovedAnyV1") == 2, "removal scratch reset and mark")
    contracts.require(writes.count("EventManualResetCandidateValidV1") == 2, "candidate scratch true then fail-close")
    for name in ("EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1"):
        contracts.require(writes.count(name) == 1, f"single authoritative publication {name}")
    codes = (
        "event_manual_reset_unavailable", "event_manual_reset_request_invalid",
        "event_manual_reset_plan_invalid", "event_manual_reset_policy_invalid",
        "event_manual_reset_ledger_invalid", "event_manual_reset_candidate_invalid",
        "event_manual_reset_completed", "event_manual_reset_already_armed",
    )
    for code in codes:
        contracts.require(f'DefaultValue="{code}"' in text, f"typed result {code}")
    for required in (
        "EventManualResetCueIdV1", "EventCuePlanValidV1", "EventCueIdsV1",
        "EventCueRepeatPoliciesV1", "EventLedgerCandidateIdsV1",
        "EventLedgerCandidateLoopsV1", "EventLedgerCandidateDirectionsV1",
        "EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1",
    ):
        contracts.require(required in text, f"required manual-reset field {required}")
    for forbidden in (
        "EventAdapterExecution", "EventDispatchAuthorizedV1", "EventCuePayloadsV1",
        "EventCueOperationIdsV1", "EventResolvedBindingIdsV1",
        "CameraTransform", "DroneCamera", "Repository", "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden execution/owner {forbidden}")

    failures = (
        ({"request_id": ""}, "event_manual_reset_request_invalid"),
        ({"plan_valid": False}, "event_manual_reset_plan_invalid"),
        ({"cue_ids": (), "repeat_policies": ()}, "event_manual_reset_plan_invalid"),
        ({"cue_ids": ("manual",), "repeat_policies": ()}, "event_manual_reset_plan_invalid"),
        ({"cue_ids": ("once",), "repeat_policies": ("once_per_session",)}, "event_manual_reset_policy_invalid"),
        ({"cue_ids": ("manual",), "repeat_policies": ("every_loop",)}, "event_manual_reset_policy_invalid"),
        ({"cue_ids": ("other",), "repeat_policies": ("manual_reset",)}, "event_manual_reset_policy_invalid"),
        ({"ledger_ids": ("manual",), "ledger_loops": (), "ledger_directions": ()}, "event_manual_reset_ledger_invalid"),
        ({"ledger_ids": tuple("x" for _ in range(1025)),
          "ledger_loops": tuple(0 for _ in range(1025)),
          "ledger_directions": tuple(1 for _ in range(1025))}, "event_manual_reset_ledger_invalid"),
    )
    for overrides, code in failures:
        prior_ids = overrides.get("ledger_ids", ("prior",))
        prior_loops = overrides.get("ledger_loops", (7,))
        prior_directions = overrides.get("ledger_directions", (-1,))
        observed = reset(
            ledger_ids=prior_ids, ledger_loops=prior_loops,
            ledger_directions=prior_directions, **{
                key: value for key, value in overrides.items()
                if key not in ("ledger_ids", "ledger_loops", "ledger_directions")
            },
        )
        contracts.require(not observed["result_valid"] and observed["code"] == code, f"failure {code}")
        contracts.require(observed["ledger_ids"] is prior_ids, f"failure ID identity {code}")
        contracts.require(observed["ledger_loops"] is prior_loops, f"failure loop identity {code}")
        contracts.require(observed["ledger_directions"] is prior_directions, f"failure direction identity {code}")

    prior = (("manual", 0, 1), ("other", 0, 1), ("manual", 4, -1))
    completed = reset(
        ledger_ids=tuple(item[0] for item in prior),
        ledger_loops=tuple(item[1] for item in prior),
        ledger_directions=tuple(item[2] for item in prior),
    )
    contracts.require(completed["result_valid"] and completed["removed_any"], "manual entries removed")
    contracts.require(completed["code"] == "event_manual_reset_completed", "completed code")
    contracts.require(tuple(zip(
        completed["ledger_ids"], completed["ledger_loops"], completed["ledger_directions"]
    )) == (("other", 0, 1),), "all matching contexts removed only")
    armed = reset(ledger_ids=("other",), ledger_loops=(2,), ledger_directions=(-1,))
    contracts.require(armed["result_valid"] and not armed["removed_any"], "already armed accepted")
    contracts.require(armed["code"] == "event_manual_reset_already_armed", "already armed code")

    rng = random.Random(0xEDD940)
    for case in range(100):
        count = rng.randint(0, 80)
        triples = tuple(
            (rng.choice(("manual", f"other-{index}")), rng.randint(0, 6), rng.choice((-1, 1)))
            for index in range(count)
        )
        observed = reset(
            cue_ids=("manual", "once", "loop"),
            repeat_policies=("manual_reset", "once_per_session", "every_loop"),
            ledger_ids=tuple(item[0] for item in triples),
            ledger_loops=tuple(item[1] for item in triples),
            ledger_directions=tuple(item[2] for item in triples),
        )
        expected = tuple(item for item in triples if item[0] != "manual")
        actual = tuple(zip(
            observed["ledger_ids"], observed["ledger_loops"], observed["ledger_directions"]
        ))
        contracts.require(observed["result_valid"], f"seeded authority {case}")
        contracts.require(actual == expected, f"seeded stable filter {case}")
        contracts.require(len(observed["candidate_ids"]) == len(expected), f"seeded aligned candidate {case}")

    print(
        f"Bounded event manual ledger-reset contracts passed "
        f"({'paste' if args.paste else 'full'}): policy-safe atomic filtering and typed failures"
    )


if __name__ == "__main__":
    main()
