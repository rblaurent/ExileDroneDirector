"""Structural and executable-oracle contracts for owner-only draft saves."""

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
    spec = importlib.util.spec_from_file_location("edd_private_save_contract_base", path)
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


def error_pair(c, nodes, code: str, detail: str):
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
    c.require(len(nodes) == (97 if paste else 98), f"SaveDraftV1 node count changed: {len(nodes)}")
    for node in nodes.values():
        for pin in node.pins.values():
            c.require(len(pin.links) == len(set(pin.links)), f"{node.name}.{pin.name} has duplicate links")

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "save entry count changed")
    reset = one(c, calls(nodes, "ResetRepositoryResultV1"), "result reset")
    find = one(c, calls(nodes, "FindRecordIndexV1"), "record lookup")
    decode = one(c, calls(nodes, "DecodeRecordV1"), "stored record decoder")
    validators = calls(nodes, "ValidateRecordV1")
    c.require(len(validators) == 2, "stored and updated record validation are both required")
    encode = one(c, calls(nodes, "EncodeRecordV1"), "updated record encoder")
    prepare = one(c, calls(nodes, "PreparePersistenceCandidateV1"), "candidate preparation")
    persist = one(c, calls(nodes, "PersistRepositoryV1"), "accepted writer")
    if paste:
        c.require(not c.pin(reset, "execute").links, "paste root must be unwired")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry must reset results")
    c.require_link(reset, "then", find, "execute", "reset must precede lookup")

    index = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableGet"), "resolved index")
    envelopes = one(c, variables(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableGet"), "active envelopes")
    valid_index = one(c, calls(nodes, "Array_IsValidIndex"), "record index guard")
    c.require_link(envelopes, "ActiveRecordEnvelopesV1", valid_index, "TargetArray", "lookup must guard envelopes")
    c.require_link(index, "ResultRecordIndexV1", valid_index, "IndexToTest", "lookup index guard changed")
    found_branch = one(
        c,
        [
            node for node in nodes.values()
            if "K2Node_IfThenElse" in node.node_class
            and c.linked(valid_index, "ReturnValue", node, "Condition")
        ],
        "record-found gate",
    )
    c.require_link(find, "then", found_branch, "execute", "lookup must execute record-found gate")

    owners = one(c, variables(nodes, "ActiveOwnerAccountIdsV1", "K2Node_VariableGet"), "derived owners")
    array_items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(array_items) == 2, "owner and envelope reads are required")
    c.require(any(c.linked(owners, "ActiveOwnerAccountIdsV1", item, "Array") for item in array_items), "derived owner read changed")
    requester = one(c, variables(nodes, "RequestRequesterAccountIdV1", "K2Node_VariableGet"), "requester")
    owner_equalities = calls(nodes, "EqualEqual_StrStr")
    c.require(len(owner_equalities) == 4, "derived owner, record ID/owner, and region comparisons changed")
    c.require(any(any(target == requester.name for target, _ in c.pin(eq, "B").links) or c.linked(requester, "RequestRequesterAccountIdV1", eq, "B") for eq in owner_equalities), "requester does not gate ownership")

    current_revision = one(c, variables(nodes, "ScratchRecordDraftRevisionNumberV1", "K2Node_VariableGet"), "current revision")
    expected_revision = one(c, variables(nodes, "RequestExpectedRevisionV1", "K2Node_VariableGet"), "expected revision")
    revision_equalities = calls(nodes, "EqualEqual_IntInt")
    revision_equal = one(
        c,
        [node for node in revision_equalities if c.linked(current_revision, "ScratchRecordDraftRevisionNumberV1", node, "A")],
        "optimistic revision equality",
    )
    c.require_link(expected_revision, "RequestExpectedRevisionV1", revision_equal, "B", "expected revision source changed")
    next_revision = one(c, calls(nodes, "Add_IntInt"), "next revision")
    exact_default(c, next_revision, "B", "1")
    c.require_link(current_revision, "ScratchRecordDraftRevisionNumberV1", next_revision, "A", "next revision source changed")

    breaks = [node for node in nodes.values() if "K2Node_BreakStruct" in node.node_class and "ST_EDD_FlypathDocument" in node.text]
    makes = [node for node in nodes.values() if "K2Node_MakeStruct" in node.node_class and "ST_EDD_FlypathDocument" in node.text]
    split = one(c, breaks, "request document split")
    make = one(c, makes, "saved document rebuild")
    document_revision_pin = "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"
    document_hash_pin = "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"
    c.require_link(next_revision, "ReturnValue", make, document_revision_pin, "saved document must use next revision")
    exact_default(c, make, document_hash_pin, "")
    c.require(not c.pin(split, document_revision_pin).links, "caller revision must not control saved revision")
    c.require(not c.pin(split, document_hash_pin).links, "caller hash must not survive save")
    one(c, variables(nodes, "ScratchRecordDraftDocumentV1", "K2Node_VariableSet"), "updated document staging")
    one(c, variables(nodes, "ScratchRecordDraftRevisionNumberV1", "K2Node_VariableSet"), "updated revision staging")
    one(c, variables(nodes, "ScratchRecordUpdatedUtcV1", "K2Node_VariableSet"), "updated timestamp staging")

    waypoint_length = one(c, calls(nodes, "Array_Length"), "waypoint count")
    max_waypoints = one(c, variables(nodes, "MaxWaypointsPerPathV1", "K2Node_VariableGet"), "waypoint policy")
    limit_comparisons = calls(nodes, "LessEqual_IntInt")
    c.require(len(limit_comparisons) == 2, "waypoint and serialized limits are required")
    c.require(any(c.linked(max_waypoints, "MaxWaypointsPerPathV1", node, "B") for node in limit_comparisons), "waypoint policy not enforced")
    c.require(c.pin(waypoint_length, "TargetArray").links, "waypoint length source missing")
    one(c, variables(nodes, "MaxSerializedBytesV1", "K2Node_VariableGet"), "serialized policy")
    one(c, calls(nodes, "Len"), "encoded record length")

    array_sets = calls(nodes, "Array_Set")
    c.require(len(array_sets) == 2, "candidate record and derived timestamp replacements are required")
    for node in array_sets:
        exact_default(c, node, "bSizeToFit", "false")
    candidate_records = one(c, variables(nodes, "CandidateRecordEnvelopesV1", "K2Node_VariableGet"), "candidate records")
    candidate_set = one(
        c,
        [node for node in array_sets if c.linked(candidate_records, "CandidateRecordEnvelopesV1", node, "TargetArray")],
        "candidate record replacement",
    )
    encoded = one(c, variables(nodes, "ScratchEncodedRecordV1", "K2Node_VariableGet"), "encoded updated record")
    c.require_link(encoded, "ScratchEncodedRecordV1", candidate_set, "Item", "candidate must receive encoded update")
    c.require_link(index, "ResultRecordIndexV1", candidate_set, "Index", "candidate replacement index changed")
    scratch_index_set = one(c, variables(nodes, "ScratchIndexV1", "K2Node_VariableSet"), "pre-writer index cache")
    scratch_index_get = one(c, variables(nodes, "ScratchIndexV1", "K2Node_VariableGet"), "post-writer index cache")
    c.require_link(index, "ResultRecordIndexV1", scratch_index_set, "ScratchIndexV1", "record index cache source changed")
    c.require_link(scratch_index_set, "then", prepare, "execute", "index must be cached immediately before candidate preparation")
    c.require_link(prepare, "then", candidate_set, "execute", "prepare must precede candidate replacement")
    c.require_link(candidate_set, "then", persist, "execute", "candidate replacement must precede writer")

    committed = one(c, variables(nodes, "ScratchPersistenceCommitSavedV1", "K2Node_VariableGet"), "writer commit result")
    commit_branch = one(
        c,
        [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and c.linked(committed, "ScratchPersistenceCommitSavedV1", node, "Condition")],
        "commit success gate",
    )
    active_updated = one(c, variables(nodes, "ActiveUpdatedUtcV1", "K2Node_VariableGet"), "derived updated index")
    updated_set = one(
        c,
        [node for node in array_sets if c.linked(active_updated, "ActiveUpdatedUtcV1", node, "TargetArray")],
        "derived timestamp replacement",
    )
    c.require_link(scratch_index_get, "ScratchIndexV1", updated_set, "Index", "derived update must use preserved index")
    published_index = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableSet"), "success result index")
    c.require_link(scratch_index_get, "ScratchIndexV1", published_index, "ResultRecordIndexV1", "success index must use preserved index")
    c.require_link(commit_branch, "then", published_index, "execute", "success index must wait for physical commit")
    c.require_link(published_index, "then", updated_set, "execute", "derived state must follow success index publication")
    c.require(not c.pin(commit_branch, "else").links, "failed persistence must not mutate derived state")

    result_envelope = one(c, variables(nodes, "ResultRecordEnvelopeV1", "K2Node_VariableSet"), "success envelope")
    c.require_link(updated_set, "then", result_envelope, "execute", "results must follow derived commit")
    result_revisions = variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet")
    result_flags = variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet")
    c.require(len(result_revisions) == 2 and len(result_flags) == 2, "conflict/success revision results changed")
    for flag in result_flags:
        exact_default(c, flag, "ResultHasCurrentRevisionV1", "true")
    success_revision = one(
        c,
        [
            node for node in result_revisions
            if c.linked(current_revision, "ScratchRecordDraftRevisionNumberV1", node, "ResultCurrentRevisionV1")
            and c.linked(result_envelope, "then", node, "execute")
        ],
        "success staged revision",
    )
    saved_document = one(
        c,
        variables(nodes, "ScratchRecordDraftDocumentV1", "K2Node_VariableGet"),
        "post-writer staged document",
    )
    result_document = one(c, variables(nodes, "ResultDraftDocumentV1", "K2Node_VariableSet"), "success typed document")
    c.require_link(saved_document, "ScratchRecordDraftDocumentV1", result_document, "ResultDraftDocumentV1", "success document must use staged record document")

    for code, detail in (
        ("NotFound", "FlypathNotFound"),
        ("Forbidden", "OwnerRequired"),
        ("ValidationFailed", "StoredRecordDecodeFailed"),
        ("ValidationFailed", "StoredRecordInvalid"),
        ("ValidationFailed", "StoredRecordIndexMismatch"),
        ("RevisionConflict", "ExpectedRevisionMismatch"),
        ("ValidationFailed", "InvalidSaveRequest"),
        ("LimitExceeded", "WaypointLimit"),
        ("RegionForbidden", "DraftRegionMismatch"),
        ("ValidationFailed", "DraftInvalid"),
        ("LimitExceeded", "SerializedSize"),
    ):
        error_pair(c, nodes, code, detail)

    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"SaveDraftV1 external links: {sorted(external)}")


@dataclass(frozen=True)
class Request:
    requester: str = "owner-a"
    flypath_id: str = "private-a"
    expected_revision: int = 1
    now: str = "2026-08-11T19:00:00Z"
    region: str = "ExiledLands"
    waypoints: int = 2
    valid_document: bool = True
    serialized_size: int = 800


def save(state: dict, request: Request, *, max_waypoints=4, max_size=2000, persist=True):
    before = deepcopy(state)
    record = state["records"].get(request.flypath_id)
    if record is None:
        return "NotFound", "FlypathNotFound", None, before
    if record["owner"] != request.requester:
        return "Forbidden", "OwnerRequired", None, before
    if record.get("corrupt"):
        return "ValidationFailed", "StoredRecordInvalid", None, before
    if request.expected_revision != record["revision"]:
        return "RevisionConflict", "ExpectedRevisionMismatch", record["revision"], before
    if not request.now.strip():
        return "ValidationFailed", "InvalidSaveRequest", None, before
    if request.waypoints > max_waypoints:
        return "LimitExceeded", "WaypointLimit", None, before
    if request.region != record["region"]:
        return "RegionForbidden", "DraftRegionMismatch", None, before
    if not request.valid_document:
        return "ValidationFailed", "DraftInvalid", None, before
    if request.serialized_size > max_size:
        return "LimitExceeded", "SerializedSize", None, before
    if not persist:
        return "PersistenceUnavailable", "CommitWriteFailed", None, before
    next_revision = record["revision"] + 1
    record["revision"] = next_revision
    record["updated"] = request.now
    record["draft"] = {"revision": next_revision, "region": request.region, "waypoints": request.waypoints}
    state["generation"] += 1
    state["slot"] = "B" if state["slot"] == "A" else "A"
    return "Success", "", next_revision, deepcopy(state)


def semantic() -> None:
    base = {
        "generation": 1,
        "slot": "A",
        "records": {
            "private-a": {
                "owner": "owner-a",
                "region": "ExiledLands",
                "revision": 1,
                "created": "2026-08-11T18:00:00Z",
                "updated": "2026-08-11T18:00:00Z",
                "title": "Preserved",
                "published": {"revision": 1},
                "source": {"flypath": "source-a"},
                "draft": {"revision": 1},
            }
        },
    }
    state = deepcopy(base)
    code, detail, revision, updated = save(state, Request())
    assert (code, detail, revision) == ("Success", "", 2)
    assert updated["generation"] == 2 and updated["slot"] == "B"
    record = updated["records"]["private-a"]
    assert record["revision"] == 2 and record["draft"]["revision"] == 2
    assert record["created"] == base["records"]["private-a"]["created"]
    assert record["title"] == "Preserved" and record["published"] == {"revision": 1}
    assert record["source"] == {"flypath": "source-a"}

    stale_before = deepcopy(state)
    assert save(state, Request(expected_revision=1))[0:3] == (
        "RevisionConflict", "ExpectedRevisionMismatch", 2
    )
    assert state == stale_before
    cases = (
        (Request(flypath_id="missing"), "NotFound", "FlypathNotFound"),
        (Request(requester="owner-b"), "Forbidden", "OwnerRequired"),
        (Request(now="   "), "ValidationFailed", "InvalidSaveRequest"),
        (Request(waypoints=5), "LimitExceeded", "WaypointLimit"),
        (Request(region="Siptah"), "RegionForbidden", "DraftRegionMismatch"),
        (Request(valid_document=False), "ValidationFailed", "DraftInvalid"),
        (Request(serialized_size=2001), "LimitExceeded", "SerializedSize"),
    )
    for request, expected_code, expected_detail in cases:
        candidate = deepcopy(base)
        assert save(candidate, request)[0:2] == (expected_code, expected_detail)
        assert candidate == base
    corrupt = deepcopy(base)
    corrupt["records"]["private-a"]["corrupt"] = True
    corrupt_before = deepcopy(corrupt)
    assert save(corrupt, Request())[0:2] == ("ValidationFailed", "StoredRecordInvalid")
    assert corrupt == corrupt_before
    failed = deepcopy(base)
    assert save(failed, Request(), persist=False)[0] == "PersistenceUnavailable"
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
    print("Repository private save contracts passed")


if __name__ == "__main__":
    main()
