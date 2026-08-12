"""Structural and executable contracts for private published-revision cloning."""

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
    spec = importlib.util.spec_from_file_location("edd_clone_contract_base", path)
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
    c.require((match.group(1) if match else "") == expected, f"{pin} default changed")


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
        any(c.linked(node, "then", detail_node, "execute") for node in codes),
        f"{code} must execute {detail}",
    )


def structural(c, path: Path, paste: bool) -> None:
    nodes = c.parse_graph(path)
    c.require(len(nodes) == (175 if paste else 176), f"ClonePublishedV1 node count changed: {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "clone entry count changed")
    for node in nodes.values():
        for pin in node.pins.values():
            c.require(len(pin.links) == len(set(pin.links)), f"{node.name}.{pin.name} duplicate links")

    reset = one(c, calls(nodes, "ResetRepositoryResultV1"), "result reset")
    decode = one(c, calls(nodes, "DecodeRecordV1"), "source decode")
    validates = calls(nodes, "ValidateRecordV1")
    c.require(len(validates) == 2, "source and clone record validators are required")
    encode = one(c, calls(nodes, "EncodeRecordV1"), "clone encoder")
    prepare = one(c, calls(nodes, "PreparePersistenceCandidateV1"), "candidate preparation")
    persist = one(c, calls(nodes, "PersistRepositoryV1"), "accepted writer")
    c.require(not calls(nodes, "FetchPublishedRevisionV1"), "clone must validate source in one transaction")
    if paste:
        c.require(not c.pin(reset, "execute").links, "paste root must be unwired")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry must reset results")

    source_request = one(c, variables(nodes, "RequestSourceFlypathIdV1", "K2Node_VariableGet"), "source request")
    target_requests = variables(nodes, "RequestFlypathIdV1", "K2Node_VariableGet")
    c.require(target_requests, "target request ID is required")
    finds = calls(nodes, "Array_Find")
    c.require(len(finds) == 3, "source, region, and target lookups are required")
    c.require(
        any(any(target == node.name for target, _ in c.pin(source_request, "RequestSourceFlypathIdV1").links) for node in finds),
        "source lookup must use RequestSourceFlypathIdV1",
    )

    for name in ("ActiveRecordEnvelopesV1", "ActiveVisibilitiesV1"):
        c.require(variables(nodes, name, "K2Node_VariableGet"), f"aligned source index {name} missing")
    derived_public = [
        node for node in calls(nodes, "EqualEqual_StrStr")
        if 'DefaultValue="public"' in c.pin(node, "B").body
    ]
    c.require(derived_public, "derived/decoded public visibility checks are required")
    one(c, variables(nodes, "ScratchRecordHasPublishedRevisionV1", "K2Node_VariableGet"), "published flag")
    published_revision = one(
        c, variables(nodes, "ScratchRecordPublishedRevisionNumberV1", "K2Node_VariableGet"),
        "published revision",
    )
    expected = one(c, variables(nodes, "RequestExpectedRevisionV1", "K2Node_VariableGet"), "requested revision")
    exact_revision = [
        node for node in calls(nodes, "EqualEqual_IntInt")
        if c.pin(node, "A").links and c.pin(node, "B").links
        and any(target == node.name for target, _ in c.pin(published_revision, "ScratchRecordPublishedRevisionNumberV1").links)
        and any(target == node.name for target, _ in c.pin(expected, "RequestExpectedRevisionV1").links)
    ]
    c.require(len(exact_revision) == 1, "clone must pin the exact immutable published revision")

    make_documents = [node for node in nodes.values() if "K2Node_MakeStruct" in node.node_class and "ST_EDD_FlypathDocument" in node.text]
    clone_document = one(c, make_documents, "clone document rebuild")
    revision_pins = [name for name in clone_document.pins if name.startswith("RevisionNumber_")]
    content_hash_pins = [name for name in clone_document.pins if name.startswith("ContentHash_")]
    c.require(len(revision_pins) == 1 and len(content_hash_pins) == 1, "clone document schema pins changed")
    exact_default(c, clone_document, revision_pins[0], "1")
    exact_default(c, clone_document, content_hash_pins[0], "")
    # Unreal normalizes an empty string pin by omitting DefaultValue entirely
    # after a live paste/export.  exact_default deliberately treats that native
    # representation as the empty value while still rejecting any non-empty
    # hash, so do not require the generator-only DefaultValue="" spelling.

    staged_defaults = {
        "ScratchRecordVisibilityV1": "private",
        "ScratchRecordDraftRevisionNumberV1": "1",
        "ScratchRecordHasPublishedRevisionV1": "false",
        "ScratchRecordPublishedRevisionNumberV1": "0",
        "ScratchRecordHasSourceAttributionV1": "true",
    }
    for name, expected_default in staged_defaults.items():
        node = one(c, variables(nodes, name, "K2Node_VariableSet"), f"staged {name}")
        exact_default(c, node, name, expected_default)
    for name in (
        "ScratchRecordSourceFlypathIdV1",
        "ScratchRecordSourceRevisionNumberV1",
        "ScratchRecordSourceTitleV1",
        "ScratchRecordSourceCreatorDisplayNameV1",
        "ScratchRecordRegionIdV1",
    ):
        one(c, variables(nodes, name, "K2Node_VariableSet"), f"source attribution {name}")

    owner_loop = one(
        c,
        [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class and "ForEachLoop" in node.text],
        "owner-limit loop",
    )
    owner_getters = variables(nodes, "ActiveOwnerAccountIdsV1", "K2Node_VariableGet")
    owners = one(
        c,
        [node for node in owner_getters if c.linked(node, "ActiveOwnerAccountIdsV1", owner_loop, "Array")],
        "active owners used by owner loop",
    )
    c.require_link(owners, "ActiveOwnerAccountIdsV1", owner_loop, "Array", "clone must enforce owner path limit")
    one(c, variables(nodes, "MaxPathsPerOwnerV1", "K2Node_VariableGet"), "owner limit policy")
    one(c, variables(nodes, "MaxWaypointsPerPathV1", "K2Node_VariableGet"), "waypoint limit policy")
    one(c, variables(nodes, "MaxSerializedBytesV1", "K2Node_VariableGet"), "serialized size policy")
    one(c, variables(nodes, "MaxTitleCharsV1", "K2Node_VariableGet"), "title policy")

    candidate = one(c, variables(nodes, "CandidateRecordEnvelopesV1", "K2Node_VariableGet"), "candidate records")
    candidate_adds = [
        node for node in calls(nodes, "Array_Add")
        if c.linked(candidate, "CandidateRecordEnvelopesV1", node, "TargetArray")
    ]
    candidate_add = one(c, candidate_adds, "candidate append")
    c.require_link(prepare, "then", candidate_add, "execute", "prepare must precede candidate append")
    c.require_link(candidate_add, "then", persist, "execute", "candidate append must precede writer")

    committed = one(c, variables(nodes, "ScratchPersistenceCommitSavedV1", "K2Node_VariableGet"), "writer result")
    committed_branches = [
        node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class
        and any(target == node.name for target, _ in c.pin(committed, "ScratchPersistenceCommitSavedV1").links)
    ]
    committed_branch = one(c, committed_branches, "commit-success gate")
    active_adds = []
    for name in ("ActiveFlypathIdsV1", "ActiveOwnerAccountIdsV1", "ActiveVisibilitiesV1", "ActiveUpdatedUtcV1"):
        source = variables(nodes, name, "K2Node_VariableGet")
        pairs = [(node, add) for node in source for add in calls(nodes, "Array_Add") if c.linked(node, name, add, "TargetArray")]
        c.require(len(pairs) == 1, f"derived append {name} changed")
        active_adds.append(pairs[0][1])
    c.require_link(committed_branch, "then", active_adds[0], "execute", "derived state must wait for commit")
    c.require(not c.pin(committed_branch, "else").links, "writer failure must not mutate authority")

    result_revision = one(
        c,
        [node for node in variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet")
         if 'DefaultValue="1"' in c.pin(node, "ResultCurrentRevisionV1").body],
        "success result revision",
    )
    exact_default(c, result_revision, "ResultCurrentRevisionV1", "1")
    result_flag = one(
        c,
        [node for node in variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet")
         if 'DefaultValue="true"' in c.pin(node, "ResultHasCurrentRevisionV1").body
         and any(c.linked(result_revision, "then", node, "execute") for _ in (0,))],
        "success result revision flag",
    )
    exact_default(c, result_flag, "ResultHasCurrentRevisionV1", "true")
    one(c, variables(nodes, "ResultDraftDocumentV1", "K2Node_VariableSet"), "clone result document")

    for code, detail in (
        ("ValidationFailed", "InvalidCloneRequest"),
        ("ValidationFailed", "InvalidPublishedRevisionRequest"),
        ("LimitExceeded", "TitleLength"),
        ("NotFound", "FlypathNotFound"),
        ("ValidationFailed", "MetadataIndexMisaligned"),
        ("ValidationFailed", "StoredRecordDecodeFailed"),
        ("ValidationFailed", "StoredRecordInvalid"),
        ("ValidationFailed", "StoredRecordIndexMismatch"),
        ("RevisionConflict", "PublishedRevisionMismatch"),
        ("RegionForbidden", "RegionNotAllowed"),
        ("LimitExceeded", "WaypointCount"),
        ("AlreadyExists", "FlypathIdCollision"),
        ("LimitExceeded", "OwnerPathLimit"),
        ("ValidationFailed", "CloneRecordInvalid"),
        ("LimitExceeded", "SerializedSize"),
    ):
        error_pair(c, nodes, code, detail)

    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"ClonePublishedV1 external links: {sorted(external)}")


@dataclass(frozen=True)
class CloneRequest:
    requester: str = "viewer-b"
    requester_display: str = "Viewer B"
    source_id: str = "source-a"
    source_revision: int = 2
    target_id: str = "clone-b"
    title: str = "Remix"
    now: str = "2026-08-12T02:00:00Z"


def clone(state: dict, request: CloneRequest, *, max_paths=4, max_title=12,
          max_waypoints=8, allowed=("ExiledLands",), max_size=2000, persist=True):
    before = deepcopy(state)
    required = (request.requester, request.source_id, request.target_id, request.title, request.now)
    if not all(value.strip() for value in required):
        return "ValidationFailed", "InvalidCloneRequest", before
    if request.source_revision <= 0:
        return "ValidationFailed", "InvalidPublishedRevisionRequest", before
    if len(request.title) > max_title:
        return "LimitExceeded", "TitleLength", before
    source = state["records"].get(request.source_id)
    if source is None or source["visibility"] != "public" or source.get("published") is None:
        return "NotFound", "FlypathNotFound", before
    if source["published_revision"] != request.source_revision:
        return "RevisionConflict", "PublishedRevisionMismatch", before
    if source["region"] not in allowed:
        return "RegionForbidden", "RegionNotAllowed", before
    if len(source["published"]["waypoints"]) > max_waypoints:
        return "LimitExceeded", "WaypointCount", before
    if request.target_id in state["records"]:
        return "AlreadyExists", "FlypathIdCollision", before
    if sum(record["owner"] == request.requester for record in state["records"].values()) >= max_paths:
        return "LimitExceeded", "OwnerPathLimit", before
    published = deepcopy(source["published"])
    published["revision"] = 1
    published["hash"] = ""
    result = {
        "owner": request.requester,
        "owner_display": request.requester_display,
        "title": request.title,
        "visibility": "private",
        "region": source["region"],
        "created": request.now,
        "updated": request.now,
        "draft_revision": 1,
        "draft": published,
        "published_revision": 0,
        "published": None,
        "source": {
            "id": source["id"],
            "revision": source["published_revision"],
            "title": source["title"],
            "creator": source["owner_display"],
        },
    }
    if len(repr(result)) > max_size:
        return "LimitExceeded", "SerializedSize", before
    if not persist:
        return "PersistenceUnavailable", "CommitWriteFailed", before
    state["generation"] += 1
    state["slot"] = "B" if state["slot"] == "A" else "A"
    state["records"][request.target_id] = result
    return "Success", "", deepcopy(result)


def semantic() -> None:
    published = {
        "revision": 2,
        "hash": "sealed-source",
        "waypoints": [{"id": 1, "annotation": "source"}],
        "segments": [],
    }
    base = {
        "generation": 4,
        "slot": "B",
        "records": {
            "source-a": {
                "id": "source-a", "owner": "owner-a", "owner_display": "Author A",
                "title": "Original", "visibility": "public", "region": "ExiledLands",
                "published_revision": 2, "published": published,
            }
        },
    }
    state = deepcopy(base)
    code, detail, result = clone(state, CloneRequest())
    assert (code, detail) == ("Success", "")
    assert state["generation"] == 5 and state["slot"] == "A"
    assert result["visibility"] == "private" and result["owner"] == "viewer-b"
    assert result["draft_revision"] == result["draft"]["revision"] == 1
    assert result["published"] is None and result["published_revision"] == 0
    assert result["source"] == {"id": "source-a", "revision": 2, "title": "Original", "creator": "Author A"}
    assert result["draft"]["waypoints"] == published["waypoints"]
    assert result["draft"] is not published and result["draft"]["waypoints"] is not published["waypoints"]
    result["draft"]["waypoints"][0]["annotation"] = "remixed"
    assert published["waypoints"][0]["annotation"] == "source"

    for field in ("requester", "source_id", "target_id", "title", "now"):
        bad = CloneRequest(**{**CloneRequest().__dict__, field: "   "})
        probe = deepcopy(base)
        assert clone(probe, bad)[0:2] == ("ValidationFailed", "InvalidCloneRequest")
        assert probe == base
    for revision in (0, -1):
        assert clone(deepcopy(base), CloneRequest(source_revision=revision))[0:2] == (
            "ValidationFailed", "InvalidPublishedRevisionRequest"
        )
    assert clone(deepcopy(base), CloneRequest(title="title-is-too-long"))[0:2] == ("LimitExceeded", "TitleLength")
    assert clone(deepcopy(base), CloneRequest(source_id="missing"))[0:2] == ("NotFound", "FlypathNotFound")
    private = deepcopy(base); private["records"]["source-a"]["visibility"] = "private"
    assert clone(private, CloneRequest())[0:2] == ("NotFound", "FlypathNotFound")
    assert clone(deepcopy(base), CloneRequest(source_revision=1))[0:2] == ("RevisionConflict", "PublishedRevisionMismatch")
    assert clone(deepcopy(base), CloneRequest(), allowed=("Siptah",))[0:2] == ("RegionForbidden", "RegionNotAllowed")
    assert clone(deepcopy(base), CloneRequest(), max_waypoints=0)[0:2] == ("LimitExceeded", "WaypointCount")
    collision = deepcopy(base); collision["records"]["clone-b"] = {"owner": "other"}
    assert clone(collision, CloneRequest())[0:2] == ("AlreadyExists", "FlypathIdCollision")
    full = deepcopy(base); full["records"]["owned"] = {"owner": "viewer-b"}
    assert clone(full, CloneRequest(), max_paths=1)[0:2] == ("LimitExceeded", "OwnerPathLimit")
    assert clone(deepcopy(base), CloneRequest(), max_size=1)[0:2] == ("LimitExceeded", "SerializedSize")
    failed = deepcopy(base)
    assert clone(failed, CloneRequest(), persist=False)[0] == "PersistenceUnavailable"
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
    print("Repository published clone contracts passed")


if __name__ == "__main__":
    main()
