"""Structural and executable-oracle contracts for owner-only unpublish."""

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
    spec = importlib.util.spec_from_file_location("edd_unpublish_contract_base", path)
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
        node for node in nodes.values()
        if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text
    ]


def one(c, values, label: str):
    c.require(len(values) == 1, f"{label}: expected one, found {len(values)}")
    return values[0]


def exact_default(c, node, pin: str, expected: str) -> None:
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', c.pin(node, pin).body)
    c.require((match.group(1) if match else "") == expected, f"{node.name}.{pin} default changed")


def error_pair(c, nodes, code: str, detail: str) -> None:
    codes = [
        node for node in variables(nodes, "ResultCodeV1", "K2Node_VariableSet")
        if f'DefaultValue="{code}"' in c.pin(node, "ResultCodeV1").body
    ]
    details = [
        node for node in variables(nodes, "ResultDetailV1", "K2Node_VariableSet")
        if f'DefaultValue="{detail}"' in c.pin(node, "ResultDetailV1").body
    ]
    detail_node = one(c, details, f"stable detail {detail}")
    c.require(
        any(c.linked(code_node, "then", detail_node, "execute") for code_node in codes),
        f"{code} must execute {detail}",
    )


def structural(c, path: Path, paste: bool) -> None:
    nodes = c.parse_graph(path)
    c.require(len(nodes) == (84 if paste else 85), f"UnpublishV1 node count changed: {len(nodes)}")
    for node in nodes.values():
        for pin in node.pins.values():
            c.require(len(pin.links) == len(set(pin.links)), f"{node.name}.{pin.name} has duplicate links")

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "unpublish entry count changed")
    reset = one(c, calls(nodes, "ResetRepositoryResultV1"), "result reset")
    find = one(c, calls(nodes, "FindRecordIndexV1"), "record lookup")
    decode = one(c, calls(nodes, "DecodeRecordV1"), "record decoder")
    validates = calls(nodes, "ValidateRecordV1")
    c.require(len(validates) == 2, "stored and published record validation required")
    encode = one(c, calls(nodes, "EncodeRecordV1"), "published record encoder")
    prepare = one(c, calls(nodes, "PreparePersistenceCandidateV1"), "candidate preparation")
    persist = one(c, calls(nodes, "PersistRepositoryV1"), "accepted writer")
    if paste:
        c.require(not c.pin(reset, "execute").links, "paste root must be unwired")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry must reset results")
    c.require_link(reset, "then", find, "execute", "reset must precede lookup")

    public_index = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableGet"), "lookup index")
    cache_index = one(c, variables(nodes, "ScratchIndexV1", "K2Node_VariableSet"), "private index cache")
    cached_index = one(c, variables(nodes, "ScratchIndexV1", "K2Node_VariableGet"), "cached index")
    result_index_sets = variables(nodes, "ResultRecordIndexV1", "K2Node_VariableSet")
    c.require(len(result_index_sets) == 2, "public index clear/success publication changed")
    clear_index = one(c, [node for node in result_index_sets if 'DefaultValue="-1"' in c.pin(node, "ResultRecordIndexV1").body], "public index clear")
    success_index = one(c, [node for node in result_index_sets if node is not clear_index], "success index")
    c.require_link(public_index, "ResultRecordIndexV1", cache_index, "ScratchIndexV1", "lookup index cache changed")
    c.require_link(find, "then", cache_index, "execute", "lookup must cache before authorization")
    c.require_link(cache_index, "then", clear_index, "execute", "public index must clear after caching")
    c.require_link(cached_index, "ScratchIndexV1", success_index, "ResultRecordIndexV1", "success index must restore cache")

    envelopes = one(c, variables(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableGet"), "active envelopes")
    valid_index = one(c, calls(nodes, "Array_IsValidIndex"), "record index guard")
    c.require_link(envelopes, "ActiveRecordEnvelopesV1", valid_index, "TargetArray", "index guard array changed")
    c.require_link(cached_index, "ScratchIndexV1", valid_index, "IndexToTest", "index guard source changed")
    found_branch = one(c, [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(valid_index, "ReturnValue", node, "Condition")], "found gate")
    c.require_link(clear_index, "then", found_branch, "execute", "public index must clear before found gate")

    owners = one(c, variables(nodes, "ActiveOwnerAccountIdsV1", "K2Node_VariableGet"), "derived owners")
    array_items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(array_items) == 2, "owner and envelope reads required")
    owner_item = one(c, [node for node in array_items if c.linked(owners, "ActiveOwnerAccountIdsV1", node, "Array")], "owner item")
    requester = one(c, variables(nodes, "RequestRequesterAccountIdV1", "K2Node_VariableGet"), "requester")
    request_id = one(c, variables(nodes, "RequestFlypathIdV1", "K2Node_VariableGet"), "request ID")
    equalities = calls(nodes, "EqualEqual_StrStr")
    c.require(len(equalities) == 3, "owner and identity comparisons changed")
    derived_owner_equal = one(c, [node for node in equalities if c.linked(owner_item, "Output", node, "A")], "derived owner equality")
    c.require_link(requester, "RequestRequesterAccountIdV1", derived_owner_equal, "B", "derived owner requester changed")

    validity_getters = variables(nodes, "ScratchValidV1", "K2Node_VariableGet")
    decode_gate = one(c, [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(decode, "then", node, "execute")], "decode gate")
    c.require(any(c.linked(valid, "ScratchValidV1", decode_gate, "Condition") for valid in validity_getters), "decode validity changed")
    stored_validate = one(c, [node for node in validates if c.linked(decode_gate, "then", node, "execute")], "stored validation")
    stored_gate = one(c, [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(stored_validate, "then", node, "execute")], "stored validation gate")
    record_id = one(c, variables(nodes, "ScratchRecordFlypathIdV1", "K2Node_VariableGet"), "decoded ID")
    record_owner = one(c, variables(nodes, "ScratchRecordOwnerAccountIdV1", "K2Node_VariableGet"), "decoded owner")
    c.require(any(c.linked(record_id, "ScratchRecordFlypathIdV1", node, "A") and c.linked(request_id, "RequestFlypathIdV1", node, "B") for node in equalities), "decoded ID guard changed")
    c.require(any(c.linked(record_owner, "ScratchRecordOwnerAccountIdV1", node, "A") and c.linked(requester, "RequestRequesterAccountIdV1", node, "B") for node in equalities), "decoded owner guard changed")
    one(c, calls(nodes, "BooleanAND"), "identity conjunction")

    current_revision = one(c, variables(nodes, "ScratchRecordDraftRevisionNumberV1", "K2Node_VariableGet"), "draft revision")
    expected_revision = one(c, variables(nodes, "RequestExpectedRevisionV1", "K2Node_VariableGet"), "expected revision")
    revision_equal = one(c, calls(nodes, "EqualEqual_IntInt"), "revision equality")
    c.require_link(current_revision, "ScratchRecordDraftRevisionNumberV1", revision_equal, "A", "draft revision source changed")
    c.require_link(expected_revision, "RequestExpectedRevisionV1", revision_equal, "B", "expected revision source changed")
    result_revision_sets = variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet")
    c.require(len(result_revision_sets) == 2, "conflict/success revision writers changed")
    result_flags = variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet")
    c.require(len(result_flags) == 2, "conflict/success revision flags changed")
    conflict_codes = [
        node for node in variables(nodes, "ResultCodeV1", "K2Node_VariableSet")
        if 'DefaultValue="RevisionConflict"' in c.pin(node, "ResultCodeV1").body
    ]
    conflict_code = one(c, conflict_codes, "revision conflict code")
    conflict_flag = one(c, [node for node in result_flags if c.linked(node, "then", conflict_code, "execute")], "conflict flag")
    conflict_revision = one(c, [node for node in result_revision_sets if c.linked(node, "then", conflict_flag, "execute")], "conflict revision")
    exact_default(c, conflict_flag, "ResultHasCurrentRevisionV1", "true")
    c.require_link(current_revision, "ScratchRecordDraftRevisionNumberV1", conflict_revision, "ResultCurrentRevisionV1", "conflict disclosure changed")

    visibility = one(c, variables(nodes, "ScratchRecordVisibilityV1", "K2Node_VariableSet"), "private visibility stage")
    updated = one(c, variables(nodes, "ScratchRecordUpdatedUtcV1", "K2Node_VariableSet"), "updated timestamp stage")
    exact_default(c, visibility, "ScratchRecordVisibilityV1", "private")
    c.require(not variables(nodes, "ScratchRecordPublishedDocumentV1", "K2Node_VariableSet"), "unpublish must retain published document")
    c.require(not variables(nodes, "ScratchRecordPublishedRevisionNumberV1", "K2Node_VariableSet"), "unpublish must retain published revision")
    c.require(not variables(nodes, "ScratchRecordHasPublishedRevisionV1", "K2Node_VariableSet"), "unpublish must retain published flag")
    draft_document = one(c, variables(nodes, "ScratchRecordDraftDocumentV1", "K2Node_VariableGet"), "draft document")
    c.require_link(visibility, "then", updated, "execute", "unpublish visibility/timestamp order changed")
    unpublished_validate = one(c, [node for node in validates if node is not stored_validate], "unpublished validation")
    c.require_link(updated, "then", unpublished_validate, "execute", "staged unpublish must validate")
    unpublished_gate = one(c, [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(unpublished_validate, "then", node, "execute")], "unpublished validation gate")
    c.require_link(unpublished_gate, "then", encode, "execute", "valid unpublish must encode")

    candidate_records = one(c, variables(nodes, "CandidateRecordEnvelopesV1", "K2Node_VariableGet"), "candidate records")
    array_sets = calls(nodes, "Array_Set")
    c.require(len(array_sets) == 3, "candidate/visibility/timestamp replacements required")
    candidate_set = one(c, [node for node in array_sets if c.linked(candidate_records, "CandidateRecordEnvelopesV1", node, "TargetArray")], "candidate replacement")
    c.require_link(cached_index, "ScratchIndexV1", candidate_set, "Index", "candidate index changed")
    encoded = one(c, variables(nodes, "ScratchEncodedRecordV1", "K2Node_VariableGet"), "encoded record")
    c.require_link(encoded, "ScratchEncodedRecordV1", candidate_set, "Item", "candidate envelope changed")
    c.require_link(prepare, "then", candidate_set, "execute", "prepare must precede candidate replacement")
    c.require_link(candidate_set, "then", persist, "execute", "candidate replacement must precede writer")

    committed = one(c, variables(nodes, "ScratchPersistenceCommitSavedV1", "K2Node_VariableGet"), "writer commit")
    commit_gate = one(c, [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(committed, "ScratchPersistenceCommitSavedV1", node, "Condition")], "commit gate")
    c.require_link(persist, "then", commit_gate, "execute", "writer must execute commit gate")
    c.require(not c.pin(commit_gate, "else").links, "failed writer must not mutate indexes or expose results")

    active_visibility = one(c, variables(nodes, "ActiveVisibilitiesV1", "K2Node_VariableGet"), "active visibility")
    visibility_set = one(c, [node for node in array_sets if c.linked(active_visibility, "ActiveVisibilitiesV1", node, "TargetArray")], "active visibility replacement")
    exact_default(c, visibility_set, "Item", "private")
    active_updated = one(c, variables(nodes, "ActiveUpdatedUtcV1", "K2Node_VariableGet"), "active timestamp")
    updated_set = one(c, [node for node in array_sets if c.linked(active_updated, "ActiveUpdatedUtcV1", node, "TargetArray")], "active timestamp replacement")
    c.require_link(cached_index, "ScratchIndexV1", visibility_set, "Index", "visibility index changed")
    c.require_link(cached_index, "ScratchIndexV1", updated_set, "Index", "timestamp index changed")
    c.require_link(commit_gate, "then", success_index, "execute", "unpublish result must wait for physical commit")
    c.require_link(success_index, "then", visibility_set, "execute", "visibility update order changed")
    c.require_link(visibility_set, "then", updated_set, "execute", "derived indexes must update together")

    result_envelope = one(c, variables(nodes, "ResultRecordEnvelopeV1", "K2Node_VariableSet"), "result envelope")
    result_revision = one(c, [node for node in result_revision_sets if node is not conflict_revision], "success revision")
    result_flag = one(c, [node for node in result_flags if node is not conflict_flag], "success revision flag")
    result_document = one(c, variables(nodes, "ResultDraftDocumentV1", "K2Node_VariableSet"), "result draft")
    c.require_link(encoded, "ScratchEncodedRecordV1", result_envelope, "ResultRecordEnvelopeV1", "result envelope changed")
    c.require_link(current_revision, "ScratchRecordDraftRevisionNumberV1", result_revision, "ResultCurrentRevisionV1", "unpublish must not advance draft revision")
    c.require_link(draft_document, "ScratchRecordDraftDocumentV1", result_document, "ResultDraftDocumentV1", "result draft changed")
    exact_default(c, result_flag, "ResultHasCurrentRevisionV1", "true")

    c.require(not variables(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableSet"), "writer must promote records")
    c.require(not variables(nodes, "ActiveTombstoneFlypathIdsV1", "K2Node_VariableSet"), "unpublish must not alter tombstones")
    for code, detail in (
        ("NotFound", "FlypathNotFound"),
        ("Forbidden", "OwnerRequired"),
        ("ValidationFailed", "StoredRecordDecodeFailed"),
        ("ValidationFailed", "StoredRecordInvalid"),
        ("ValidationFailed", "StoredRecordIndexMismatch"),
        ("RevisionConflict", "ExpectedRevisionMismatch"),
        ("ValidationFailed", "InvalidUnpublishRequest"),
        ("ValidationFailed", "UnpublishedRecordInvalid"),
        ("LimitExceeded", "SerializedSize"),
    ):
        error_pair(c, nodes, code, detail)

    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"UnpublishV1 external links: {sorted(external)}")


@dataclass(frozen=True)
class Request:
    requester: str = "owner-a"
    flypath_id: str = "public-a"
    expected_revision: int = 3
    now: str = "2026-08-12T00:00:00Z"


def unpublish(state: dict, request: Request, *, persist: bool = True):
    before = deepcopy(state)
    record = state["records"].get(request.flypath_id)
    if record is None:
        return "NotFound", None, before
    if record["owner"] != request.requester:
        return "Forbidden", None, before
    if record.get("corrupt") or record.get("indexed_id", request.flypath_id) != request.flypath_id:
        return "ValidationFailed", None, before
    if record["revision"] != request.expected_revision:
        return "RevisionConflict", record["revision"], before
    if not request.now.strip():
        return "ValidationFailed", None, before
    if not persist:
        return "PersistenceUnavailable", None, before
    record["visibility"] = "private"
    record["updated"] = request.now
    state["generation"] += 1
    state["slot"] = "B" if state["slot"] == "A" else "A"
    return "Success", record["revision"], deepcopy(state)


def semantic() -> None:
    base = {
        "generation": 3,
        "slot": "A",
        "records": {
            "public-a": {
                "owner": "owner-a",
                "revision": 3,
                "visibility": "public",
                "draft": {"revision": 3, "waypoints": [1, 2, 3]},
                "published_revision": 2,
                "published": {"revision": 2, "waypoints": [1, 2]},
                "updated": "before",
            }
        },
    }
    state = deepcopy(base)
    code, revision, updated = unpublish(state, Request())
    assert (code, revision) == ("Success", 3)
    record = updated["records"]["public-a"]
    assert updated["generation"] == 4 and updated["slot"] == "B"
    assert record["visibility"] == "private"
    assert record["published_revision"] == 2
    assert record["published"]["waypoints"] == [1, 2]
    for request, expected in (
        (Request(flypath_id="missing"), "NotFound"),
        (Request(requester="owner-b"), "Forbidden"),
        (Request(expected_revision=2), "RevisionConflict"),
        (Request(now="   "), "ValidationFailed"),
    ):
        candidate = deepcopy(base)
        assert unpublish(candidate, request)[0] == expected
        assert candidate == base
    failed = deepcopy(base)
    assert unpublish(failed, Request(), persist=False)[0] == "PersistenceUnavailable"
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
    print("Repository unpublish contracts passed")


if __name__ == "__main__":
    main()
