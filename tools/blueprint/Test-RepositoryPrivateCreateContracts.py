"""Structural and executable-oracle contracts for private Flypath creation."""

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
    spec = importlib.util.spec_from_file_location("edd_private_create_contract_base", path)
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


def error_pair(c, nodes, code: str, detail: str):
    codes = [
        node for node in variables(nodes, "ResultCodeV1", "K2Node_VariableSet")
        if f'DefaultValue="{code}"' in c.pin(node, "ResultCodeV1").body
    ]
    details = [
        node for node in variables(nodes, "ResultDetailV1", "K2Node_VariableSet")
        if f'DefaultValue="{detail}"' in c.pin(node, "ResultDetailV1").body
    ]
    c.require(codes, f"missing result code {code}")
    detail_node = one(c, details, f"stable detail {detail}")
    c.require(
        any(c.linked(node, "then", detail_node, "execute") for node in codes),
        f"{code} must execute {detail}",
    )


def structural(c, path: Path, paste: bool) -> None:
    nodes = c.parse_graph(path)
    c.require(len(nodes) == (112 if paste else 113), f"CreatePrivateFlypathV1 node count changed: {len(nodes)}")
    for node in nodes.values():
        for pin in node.pins.values():
            c.require(len(pin.links) == len(set(pin.links)), f"{node.name}.{pin.name} has duplicate links")

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "create entry count changed")
    reset = one(c, calls(nodes, "ResetRepositoryResultV1"), "result reset")
    find = one(c, calls(nodes, "FindRecordIndexV1"), "collision lookup")
    validate = one(c, calls(nodes, "ValidateRecordV1"), "record validation")
    encode = one(c, calls(nodes, "EncodeRecordV1"), "record encoder")
    prepare = one(c, calls(nodes, "PreparePersistenceCandidateV1"), "candidate preparation")
    persist = one(c, calls(nodes, "PersistRepositoryV1"), "accepted writer")
    if paste:
        c.require(not c.pin(reset, "execute").links, "paste root must be unwired")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry must reset results")
    c.require_link(reset, "then", find, "execute", "reset must precede collision lookup")

    index = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableGet"), "collision index")
    absent = one(c, calls(nodes, "EqualEqual_IntInt"), "collision equality")
    exact_default(c, absent, "B", "-1")
    c.require_link(index, "ResultRecordIndexV1", absent, "A", "collision check must use lookup result")

    string_len = calls(nodes, "Len")
    c.require(len(string_len) == 2, "title and encoded-size Len calls are required")
    title_sources = variables(nodes, "RequestTitleV1", "K2Node_VariableGet")
    c.require(len(title_sources) == 2, "title must be read for validation and record staging")
    max_title = one(c, variables(nodes, "MaxTitleCharsV1", "K2Node_VariableGet"), "title policy")
    title_comparison = [node for node in calls(nodes, "LessEqual_IntInt") if c.pin(node, "B").links]
    c.require(title_comparison, "title/size bounded comparisons missing")
    c.require(
        any(
            c.linked(title, "RequestTitleV1", node, "S")
            for title in title_sources for node in string_len
        ),
        "title length source changed",
    )
    c.require(any(any(target == max_title.name for target, _ in c.pin(node, "B").links) for node in title_comparison), "title policy is not enforced")

    allowed = one(c, variables(nodes, "AllowedRegionsV1", "K2Node_VariableGet"), "allowed regions")
    region_find = [node for node in calls(nodes, "Array_Find") if "string" in c.pin(node, "TargetArray").body]
    c.require(region_find, "allowed-region lookup missing")
    c.require(any(any(target == allowed.name for target, _ in c.pin(node, "TargetArray").links) for node in region_find), "region policy source changed")

    owner_loop = one(c, [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class and "ForEachLoop" in node.text], "owner loop")
    owner_sources = variables(nodes, "ActiveOwnerAccountIdsV1", "K2Node_VariableGet")
    owners = one(
        c,
        [node for node in owner_sources if c.linked(node, "ActiveOwnerAccountIdsV1", owner_loop, "Array")],
        "active owners used by limit loop",
    )
    c.require_link(owners, "ActiveOwnerAccountIdsV1", owner_loop, "Array", "owner limit must count active owners")
    c.require(len(variables(nodes, "ScratchIndexV1", "K2Node_VariableSet")) == 2, "owner count reset/increment changed")
    one(c, variables(nodes, "MaxPathsPerOwnerV1", "K2Node_VariableGet"), "owner limit policy")

    staged_defaults = {
        "ScratchRecordVisibilityV1": "private",
        "ScratchRecordDraftRevisionNumberV1": "1",
        "ScratchRecordHasPublishedRevisionV1": "false",
        "ScratchRecordPublishedRevisionNumberV1": "0",
        "ScratchRecordHasSourceAttributionV1": "false",
        "ScratchRecordSourceRevisionNumberV1": "0",
    }
    for name, expected in staged_defaults.items():
        node = one(c, variables(nodes, name, "K2Node_VariableSet"), f"staged {name}")
        exact_default(c, node, name, expected)
    one(c, variables(nodes, "ScratchRecordDraftDocumentV1", "K2Node_VariableSet"), "initial draft staging")

    candidate = one(c, variables(nodes, "CandidateRecordEnvelopesV1", "K2Node_VariableGet"), "candidate records")
    encoded = one(c, variables(nodes, "ScratchEncodedRecordV1", "K2Node_VariableGet"), "encoded record")
    record_adds = [node for node in calls(nodes, "Array_Add") if "CandidateRecordEnvelopesV1" in candidate.text and any(target == node.name for target, _ in c.pin(candidate, "CandidateRecordEnvelopesV1").links)]
    candidate_add = one(c, record_adds, "candidate append")
    c.require_link(encoded, "ScratchEncodedRecordV1", candidate_add, "NewItem", "candidate must append encoded record")
    c.require_link(prepare, "then", candidate_add, "execute", "prepare must precede candidate mutation")
    c.require_link(candidate_add, "then", persist, "execute", "candidate mutation must precede persistence")

    committed = one(c, variables(nodes, "ScratchPersistenceCommitSavedV1", "K2Node_VariableGet"), "writer commit result")
    committed_branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and any(target == node.name for target, _ in c.pin(committed, "ScratchPersistenceCommitSavedV1").links)]
    committed_branch = one(c, committed_branches, "commit-success gate")
    active_arrays = (
        ("ActiveFlypathIdsV1", "RequestFlypathIdV1", None),
        ("ActiveOwnerAccountIdsV1", "RequestRequesterAccountIdV1", None),
        ("ActiveVisibilitiesV1", None, "private"),
        ("ActiveUpdatedUtcV1", "RequestNowUtcV1", None),
    )
    active_adds = []
    for array_name, source_name, default in active_arrays:
        array_sources = variables(nodes, array_name, "K2Node_VariableGet")
        pairs = [
            (array, add) for array in array_sources for add in calls(nodes, "Array_Add")
            if c.linked(array, array_name, add, "TargetArray")
        ]
        c.require(len(pairs) == 1, f"derived add {array_name}: expected one, found {len(pairs)}")
        array, add = pairs[0]
        active_adds.append(add)
        if source_name:
            sources = variables(nodes, source_name, "K2Node_VariableGet")
            c.require(any(any(target == add.name for target, _ in c.pin(source, source_name).links) for source in sources), f"{array_name} source changed")
        else:
            exact_default(c, add, "NewItem", default or "")
    c.require_link(committed_branch, "then", active_adds[0], "execute", "derived state must wait for committed writer")
    c.require(not c.pin(committed_branch, "else").links, "failed persistence must not mutate derived state")

    result_revision = one(c, variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet"), "result revision")
    exact_default(c, result_revision, "ResultCurrentRevisionV1", "1")
    result_flag = one(c, variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet"), "result revision flag")
    exact_default(c, result_flag, "ResultHasCurrentRevisionV1", "true")
    one(c, variables(nodes, "ResultRecordEnvelopeV1", "K2Node_VariableSet"), "result envelope")
    one(c, variables(nodes, "ResultDraftDocumentV1", "K2Node_VariableSet"), "result document")

    for code, detail in (
        ("AlreadyExists", "FlypathIdCollision"),
        ("ValidationFailed", "InvalidCreateRequest"),
        ("LimitExceeded", "TitleLength"),
        ("RegionForbidden", "RegionNotAllowed"),
        ("LimitExceeded", "OwnerPathLimit"),
        ("ValidationFailed", "InitialRecordInvalid"),
        ("LimitExceeded", "SerializedSize"),
    ):
        error_pair(c, nodes, code, detail)

    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"CreatePrivateFlypathV1 external links: {sorted(external)}")


@dataclass(frozen=True)
class Request:
    owner: str = "owner-a"
    display: str = "Owner A"
    flypath_id: str = "private-a"
    title: str = "First Flight"
    region: str = "ExiledLands"
    now: str = "2026-08-11T18:00:00Z"
    draft_revision: int = 1
    draft_region: str = "ExiledLands"


def create(state: dict, request: Request, *, max_paths=2, max_title=12, allowed=("ExiledLands",), persist=True):
    before = deepcopy(state)
    if request.flypath_id in state["records"]:
        return "AlreadyExists", "FlypathIdCollision", before
    if not all(value.strip() for value in (request.owner, request.flypath_id, request.title, request.region, request.now)):
        return "ValidationFailed", "InvalidCreateRequest", before
    if len(request.title) > max_title:
        return "LimitExceeded", "TitleLength", before
    if request.region not in allowed:
        return "RegionForbidden", "RegionNotAllowed", before
    if sum(record["owner"] == request.owner for record in state["records"].values()) >= max_paths:
        return "LimitExceeded", "OwnerPathLimit", before
    if request.draft_revision != 1 or request.draft_region != request.region:
        return "ValidationFailed", "InitialRecordInvalid", before
    if not persist:
        return "PersistenceUnavailable", "CommitWriteFailed", before
    state["generation"] += 1
    state["slot"] = "B" if state["slot"] == "A" else "A"
    state["records"][request.flypath_id] = {
        "owner": request.owner,
        "visibility": "private",
        "revision": 1,
        "created": request.now,
        "updated": request.now,
    }
    return "Success", "", deepcopy(state)


def semantic() -> None:
    empty = {"generation": 0, "slot": "", "records": {}}
    state = deepcopy(empty)
    code, detail, created = create(state, Request())
    assert (code, detail) == ("Success", "")
    assert created["generation"] == 1 and created["slot"] == "A"
    assert created["records"]["private-a"] == {
        "owner": "owner-a", "visibility": "private", "revision": 1,
        "created": "2026-08-11T18:00:00Z", "updated": "2026-08-11T18:00:00Z",
    }
    snapshot = deepcopy(state)
    assert create(state, Request())[0:2] == ("AlreadyExists", "FlypathIdCollision")
    assert state == snapshot
    for field in ("owner", "flypath_id", "title", "region", "now"):
        bad = Request(**{**Request().__dict__, field: "   "})
        assert create(deepcopy(empty), bad)[0:2] == ("ValidationFailed", "InvalidCreateRequest")
    assert create(deepcopy(empty), Request(title="title-is-too-long"))[0:2] == ("LimitExceeded", "TitleLength")
    assert create(deepcopy(empty), Request(region="Unknown", draft_region="Unknown"))[0:2] == ("RegionForbidden", "RegionNotAllowed")
    full = {"generation": 4, "slot": "A", "records": {"old": {"owner": "owner-a"}}}
    assert create(full, Request(), max_paths=1)[0:2] == ("LimitExceeded", "OwnerPathLimit")
    assert full["generation"] == 4 and set(full["records"]) == {"old"}
    assert create(deepcopy(empty), Request(draft_revision=0))[0:2] == ("ValidationFailed", "InitialRecordInvalid")
    failed = deepcopy(empty)
    assert create(failed, Request(), persist=False)[0] == "PersistenceUnavailable"
    assert failed == empty


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    structural(c, args.input, args.paste)
    semantic()
    print("Repository private create contracts passed")


if __name__ == "__main__":
    main()
