"""Structural and executable-oracle contracts for owner-only deletion."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_private_delete_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def calls(nodes, name: str):
    return [node for node in nodes.values() if f'MemberName="{name}"' in node.text]


def variables(nodes, name: str, node_class: str):
    return [
        node
        for node in nodes.values()
        if node_class in node.node_class
        and f'VariableReference=(MemberName="{name}"' in node.text
    ]


def one(c, values, label: str):
    c.require(len(values) == 1, f"{label}: expected one, found {len(values)}")
    return values[0]


def exact_default(c, node, pin: str, expected: str) -> None:
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', c.pin(node, pin).body)
    c.require((match.group(1) if match else "") == expected, f"{node.name}.{pin} default changed")


def error_pair(c, nodes, code: str, detail: str) -> None:
    codes = [
        node
        for node in variables(nodes, "ResultCodeV1", "K2Node_VariableSet")
        if f'DefaultValue="{code}"' in c.pin(node, "ResultCodeV1").body
    ]
    details = [
        node
        for node in variables(nodes, "ResultDetailV1", "K2Node_VariableSet")
        if f'DefaultValue="{detail}"' in c.pin(node, "ResultDetailV1").body
    ]
    detail_node = one(c, details, f"stable detail {detail}")
    c.require(
        any(c.linked(code_node, "then", detail_node, "execute") for code_node in codes),
        f"{code} must execute {detail}",
    )


def structural(c, path: Path, paste: bool) -> None:
    nodes = c.parse_graph(path)
    c.require(len(nodes) == (63 if paste else 64), f"DeleteFlypathV1 node count changed: {len(nodes)}")
    for node in nodes.values():
        for pin in node.pins.values():
            c.require(len(pin.links) == len(set(pin.links)), f"{node.name}.{pin.name} has duplicate links")

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "delete entry count changed")
    reset = one(c, calls(nodes, "ResetRepositoryResultV1"), "result reset")
    find = one(c, calls(nodes, "FindRecordIndexV1"), "record lookup")
    decode = one(c, calls(nodes, "DecodeRecordV1"), "stored record decoder")
    validate = one(c, calls(nodes, "ValidateRecordV1"), "stored record validator")
    prepare = one(c, calls(nodes, "PreparePersistenceCandidateV1"), "candidate preparation")
    persist = one(c, calls(nodes, "PersistRepositoryV1"), "accepted writer")
    if paste:
        c.require(not c.pin(reset, "execute").links, "paste root must be unwired")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry must reset results")
    c.require_link(reset, "then", find, "execute", "reset must precede lookup")

    index = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableGet"), "resolved index")
    cache_index = one(c, variables(nodes, "ScratchIndexV1", "K2Node_VariableSet"), "private resolved-index cache")
    cached_index = one(c, variables(nodes, "ScratchIndexV1", "K2Node_VariableGet"), "private resolved index")
    clear_index = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableSet"), "public result-index clear")
    exact_default(c, clear_index, "ResultRecordIndexV1", "-1")
    c.require_link(index, "ResultRecordIndexV1", cache_index, "ScratchIndexV1", "lookup result must enter private scratch")
    c.require_link(find, "then", cache_index, "execute", "lookup must cache before authorization")
    c.require_link(cache_index, "then", clear_index, "execute", "public result index must clear after caching")
    envelopes = one(c, variables(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableGet"), "active envelopes")
    valid_index = one(c, calls(nodes, "Array_IsValidIndex"), "record index guard")
    c.require_link(envelopes, "ActiveRecordEnvelopesV1", valid_index, "TargetArray", "lookup must guard envelopes")
    c.require_link(cached_index, "ScratchIndexV1", valid_index, "IndexToTest", "private lookup index guard changed")
    found_branch = one(
        c,
        [
            node
            for node in nodes.values()
            if "K2Node_IfThenElse" in node.node_class
            and c.linked(valid_index, "ReturnValue", node, "Condition")
        ],
        "record-found gate",
    )
    c.require_link(clear_index, "then", found_branch, "execute", "public index must clear before record-found gate")

    owner_getters = variables(nodes, "ActiveOwnerAccountIdsV1", "K2Node_VariableGet")
    c.require(len(owner_getters) == 2, "derived owner read/removal getters changed")
    array_items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(array_items) == 2, "owner and envelope reads are required")
    owner_item = one(
        c,
        [
            item
            for item in array_items
            if any(c.linked(owner, "ActiveOwnerAccountIdsV1", item, "Array") for owner in owner_getters)
        ],
        "derived owner item",
    )
    requester = one(c, variables(nodes, "RequestRequesterAccountIdV1", "K2Node_VariableGet"), "requester")
    request_id = one(c, variables(nodes, "RequestFlypathIdV1", "K2Node_VariableGet"), "requested ID")
    equalities = calls(nodes, "EqualEqual_StrStr")
    c.require(len(equalities) == 3, "derived owner and decoded identity comparisons changed")
    derived_owner_equal = one(
        c,
        [node for node in equalities if c.linked(owner_item, "Output", node, "A")],
        "derived owner equality",
    )
    c.require_link(requester, "RequestRequesterAccountIdV1", derived_owner_equal, "B", "derived owner requester changed")

    validity_getters = variables(nodes, "ScratchValidV1", "K2Node_VariableGet")
    decode_gate = one(
        c,
        [
            node
            for node in nodes.values()
            if "K2Node_IfThenElse" in node.node_class
            and c.linked(decode, "then", node, "execute")
            and any(c.linked(valid, "ScratchValidV1", node, "Condition") for valid in validity_getters)
        ],
        "decode validity gate",
    )
    c.require_link(decode, "then", decode_gate, "execute", "decode must execute its validity gate")
    validate_gate = one(
        c,
        [
            node
            for node in nodes.values()
            if "K2Node_IfThenElse" in node.node_class
            and c.linked(validate, "then", node, "execute")
            and any(c.linked(valid, "ScratchValidV1", node, "Condition") for valid in validity_getters)
        ],
        "validation gate",
    )
    c.require_link(decode_gate, "then", validate, "execute", "decode success must validate stored record")
    c.require_link(validate, "then", validate_gate, "execute", "stored validator must execute its gate")
    record_id = one(c, variables(nodes, "ScratchRecordFlypathIdV1", "K2Node_VariableGet"), "decoded ID")
    record_owner = one(c, variables(nodes, "ScratchRecordOwnerAccountIdV1", "K2Node_VariableGet"), "decoded owner")
    c.require(any(c.linked(record_id, "ScratchRecordFlypathIdV1", node, "A") and c.linked(request_id, "RequestFlypathIdV1", node, "B") for node in equalities), "decoded ID identity guard changed")
    c.require(any(c.linked(record_owner, "ScratchRecordOwnerAccountIdV1", node, "A") and c.linked(requester, "RequestRequesterAccountIdV1", node, "B") for node in equalities), "decoded owner identity guard changed")
    one(c, calls(nodes, "BooleanAND"), "decoded identity conjunction")

    current_revision = one(c, variables(nodes, "ScratchRecordDraftRevisionNumberV1", "K2Node_VariableGet"), "current revision")
    expected_revision = one(c, variables(nodes, "RequestExpectedRevisionV1", "K2Node_VariableGet"), "expected revision")
    revision_equal = one(c, calls(nodes, "EqualEqual_IntInt"), "optimistic revision equality")
    c.require_link(current_revision, "ScratchRecordDraftRevisionNumberV1", revision_equal, "A", "current revision source changed")
    c.require_link(expected_revision, "RequestExpectedRevisionV1", revision_equal, "B", "expected revision source changed")
    conflict_revision = one(c, variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet"), "conflict revision")
    conflict_flag = one(c, variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet"), "conflict revision flag")
    exact_default(c, conflict_flag, "ResultHasCurrentRevisionV1", "true")
    c.require_link(current_revision, "ScratchRecordDraftRevisionNumberV1", conflict_revision, "ResultCurrentRevisionV1", "conflict revision disclosure changed")


    removals = calls(nodes, "Array_Remove")
    c.require(len(removals) == 5, "candidate plus four derived index removals are required")
    candidate_records = one(c, variables(nodes, "CandidateRecordEnvelopesV1", "K2Node_VariableGet"), "candidate records")
    candidate_remove = one(
        c,
        [node for node in removals if c.linked(candidate_records, "CandidateRecordEnvelopesV1", node, "TargetArray")],
        "candidate record removal",
    )
    c.require_link(cached_index, "ScratchIndexV1", candidate_remove, "IndexToRemove", "candidate delete index changed")
    c.require_link(prepare, "then", candidate_remove, "execute", "prepare must precede candidate removal")

    candidate_tombstones = one(c, variables(nodes, "CandidateTombstoneFlypathIdsV1", "K2Node_VariableGet"), "candidate tombstones")
    add_tombstone = one(c, calls(nodes, "Array_Add"), "candidate tombstone append")
    c.require_link(candidate_tombstones, "CandidateTombstoneFlypathIdsV1", add_tombstone, "TargetArray", "candidate tombstone channel changed")
    c.require_link(request_id, "RequestFlypathIdV1", add_tombstone, "NewItem", "tombstone ID source changed")
    c.require_link(candidate_remove, "then", add_tombstone, "execute", "record removal must precede tombstone append")
    c.require_link(add_tombstone, "then", persist, "execute", "tombstone append must precede writer")

    committed = one(c, variables(nodes, "ScratchPersistenceCommitSavedV1", "K2Node_VariableGet"), "writer commit result")
    commit_branch = one(
        c,
        [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(committed, "ScratchPersistenceCommitSavedV1", node, "Condition")],
        "commit success gate",
    )
    c.require_link(persist, "then", commit_branch, "execute", "writer must execute commit gate")
    c.require(not c.pin(commit_branch, "else").links, "failed persistence must not mutate derived state")

    active_names = (
        "ActiveFlypathIdsV1",
        "ActiveOwnerAccountIdsV1",
        "ActiveVisibilitiesV1",
        "ActiveUpdatedUtcV1",
    )
    active_removals = []
    for name in active_names:
        getters = variables(nodes, name, "K2Node_VariableGet")
        remove = one(
            c,
            [
                node
                for node in removals
                if any(c.linked(getter, name, node, "TargetArray") for getter in getters)
            ],
            f"derived {name} removal",
        )
        c.require_link(cached_index, "ScratchIndexV1", remove, "IndexToRemove", f"{name} must use preserved index")
        active_removals.append(remove)
    c.require_link(commit_branch, "then", active_removals[0], "execute", "derived deletion must wait for physical commit")
    for before, after in zip(active_removals, active_removals[1:]):
        c.require_link(before, "then", after, "execute", "derived indexes must delete in lockstep")
    c.require(not c.pin(active_removals[-1], "then").links, "successful delete must terminate without payload publication")

    c.require(not variables(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableSet"), "delete must let the writer promote active records")
    c.require(not variables(nodes, "ActiveTombstoneFlypathIdsV1", "K2Node_VariableSet"), "delete must let the writer promote tombstones")
    c.require(not variables(nodes, "ResultRecordEnvelopeV1", "K2Node_VariableSet"), "delete must not publish a deleted envelope")
    c.require(not variables(nodes, "ResultDraftDocumentV1", "K2Node_VariableSet"), "delete must not publish a deleted draft")

    for code, detail in (
        ("NotFound", "FlypathNotFound"),
        ("Forbidden", "OwnerRequired"),
        ("ValidationFailed", "StoredRecordDecodeFailed"),
        ("ValidationFailed", "StoredRecordInvalid"),
        ("ValidationFailed", "StoredRecordIndexMismatch"),
        ("RevisionConflict", "ExpectedRevisionMismatch"),
    ):
        error_pair(c, nodes, code, detail)

    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"DeleteFlypathV1 external links: {sorted(external)}")


@dataclass(frozen=True)
class Request:
    requester: str = "owner-a"
    flypath_id: str = "private-a"
    expected_revision: int = 3


def delete(state: dict, request: Request, *, persist: bool = True):
    before = deepcopy(state)
    record = state["records"].get(request.flypath_id)
    if record is None:
        return "NotFound", "FlypathNotFound", None, before
    if record["owner"] != request.requester:
        return "Forbidden", "OwnerRequired", None, before
    if record.get("corrupt"):
        return "ValidationFailed", "StoredRecordInvalid", None, before
    if record.get("indexed_id", request.flypath_id) != request.flypath_id:
        return "ValidationFailed", "StoredRecordIndexMismatch", None, before
    if request.expected_revision != record["revision"]:
        return "RevisionConflict", "ExpectedRevisionMismatch", record["revision"], before
    if not persist:
        return "PersistenceUnavailable", "CommitWriteFailed", None, before
    del state["records"][request.flypath_id]
    state["tombstones"].append(request.flypath_id)
    state["generation"] += 1
    state["slot"] = "B" if state["slot"] == "A" else "A"
    return "Success", "", None, deepcopy(state)


def semantic() -> None:
    base = {
        "generation": 3,
        "slot": "A",
        "records": {
            "private-a": {"owner": "owner-a", "revision": 3},
            "private-b": {"owner": "owner-a", "revision": 1},
        },
        "tombstones": ["older-deleted"],
    }
    state = deepcopy(base)
    code, detail, revision, updated = delete(state, Request())
    assert (code, detail, revision) == ("Success", "", None)
    assert updated["generation"] == 4 and updated["slot"] == "B"
    assert "private-a" not in updated["records"]
    assert updated["records"]["private-b"] == base["records"]["private-b"]
    assert updated["tombstones"] == ["older-deleted", "private-a"]

    for request, expected in (
        (Request(flypath_id="missing"), ("NotFound", "FlypathNotFound", None)),
        (Request(requester="owner-b"), ("Forbidden", "OwnerRequired", None)),
        (Request(expected_revision=2), ("RevisionConflict", "ExpectedRevisionMismatch", 3)),
    ):
        candidate = deepcopy(base)
        assert delete(candidate, request)[0:3] == expected
        assert candidate == base
    corrupt = deepcopy(base)
    corrupt["records"]["private-a"]["corrupt"] = True
    corrupt_before = deepcopy(corrupt)
    assert delete(corrupt, Request())[0:2] == ("ValidationFailed", "StoredRecordInvalid")
    assert corrupt == corrupt_before
    mismatch = deepcopy(base)
    mismatch["records"]["private-a"]["indexed_id"] = "other"
    mismatch_before = deepcopy(mismatch)
    assert delete(mismatch, Request())[0:2] == ("ValidationFailed", "StoredRecordIndexMismatch")
    assert mismatch == mismatch_before
    failed = deepcopy(base)
    assert delete(failed, Request(), persist=False)[0] == "PersistenceUnavailable"
    assert failed == base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    structural(c, args.input, args.paste)
    semantic()
    print("Repository private delete contracts passed")


if __name__ == "__main__":
    main()
