"""Structural and semantic contracts for immutable public revision fetch."""

from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def matching(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def variables(nodes, name: str, node_class: str):
    return [
        node for node in nodes.values()
        if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text
    ]


def assert_graph(project_root: Path, path: Path, *, paste: bool) -> None:
    c = load(
        project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py",
        "edd_published_fetch_contract_base",
    )
    nodes = c.parse_graph(path)
    c.require(len(nodes) == (61 if paste else 62), f"Published fetch node count changed: {len(nodes)}")
    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"Published fetch external links: {sorted(external)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "Published fetch entry count changed")
    if not paste:
        c.require('MemberName="FetchPublishedRevisionV1"' in entries[0].text, "Wrong fetch entry")

    for function, count in (
        ("ResetRepositoryResultV1", 1),
        ("FindRecordIndexV1", 1),
        ("DecodeRecordV1", 1),
        ("ValidateRecordV1", 1),
    ):
        c.require(len(matching(nodes, f'MemberName="{function}"')) == count, f"{function} changed")
    for forbidden in (
        'MemberName="RequestRequesterAccountIdV1"',
        'MemberName="PersistRepositoryV1"',
        'MemberName="PreparePersistenceCandidateV1"',
        'MemberName="CandidateRecordEnvelopesV1"',
        'MemberName="ResultRecordEnvelopeV1"',
        'MemberName="ResultDraftDocumentV1"',
        'MemberName="ScratchRecordDraftDocumentV1"',
    ):
        c.require(not matching(nodes, forbidden), f"Fetch crossed forbidden boundary: {forbidden}")
    c.require(len(variables(nodes, "ResultPublishedDocumentV1", "K2Node_VariableSet")) == 1, "published result missing")
    c.require(len(variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet")) == 1, "published revision missing")
    c.require(len(variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet")) == 1, "revision flag missing")
    c.require(len(matching(nodes, 'DefaultValue="public"')) >= 2, "derived and decoded public gates changed")
    for detail in (
        "FlypathNotFound",
        "MetadataIndexMisaligned",
        "StoredRecordDecodeFailed",
        "StoredRecordInvalid",
        "StoredRecordIndexMismatch",
        "InvalidPublishedRevisionRequest",
        "PublishedRevisionNotFound",
    ):
        c.require(matching(nodes, f'DefaultValue="{detail}"'), f"Missing failure detail {detail}")

    reset = matching(nodes, 'MemberName="ResetRepositoryResultV1"')[0]
    if paste:
        c.require(not reset.pins["execute"].links, "Paste fetch body must expose reset root")
    else:
        c.require_link(entries[0], "then", reset, "execute", "Fetch must reset before lookup")


def fetch(records: dict, flypath_id: str, requested_revision: int):
    if requested_revision < 0:
        return "ValidationFailed", "InvalidPublishedRevisionRequest", None
    row = records.get(flypath_id)
    if row is None or row["derived_visibility"] != "public":
        return "NotFound", "FlypathNotFound", None
    if not row.get("decoded", True):
        return "ValidationFailed", "StoredRecordDecodeFailed", None
    if not row.get("valid", True):
        return "ValidationFailed", "StoredRecordInvalid", None
    if row["id"] != flypath_id or row["visibility"] != "public" or not row["has_published"]:
        return "ValidationFailed", "StoredRecordIndexMismatch", None
    revision = row["published_revision"]
    if requested_revision not in (0, revision):
        return "NotFound", "PublishedRevisionNotFound", None
    return "Success", "", (revision, deepcopy(row["published_document"]))


def semantic() -> None:
    public = {
        "id": "public-a",
        "derived_visibility": "public",
        "visibility": "public",
        "has_published": True,
        "published_revision": 3,
        "published_document": {"revision": 3, "duration": 12.5},
        "draft_document": {"revision": 5, "duration": 99.0},
    }
    private = deepcopy(public)
    private.update({"id": "private-a", "derived_visibility": "private", "visibility": "private"})
    rows = {"public-a": public, "private-a": private}
    before = deepcopy(rows)
    assert fetch(rows, "missing", 0) == ("NotFound", "FlypathNotFound", None)
    assert fetch(rows, "private-a", 0) == ("NotFound", "FlypathNotFound", None)
    assert fetch(rows, "public-a", -1) == ("ValidationFailed", "InvalidPublishedRevisionRequest", None)
    latest = fetch(rows, "public-a", 0)
    exact = fetch(rows, "public-a", 3)
    assert latest == exact == ("Success", "", (3, {"revision": 3, "duration": 12.5}))
    assert fetch(rows, "public-a", 2) == ("NotFound", "PublishedRevisionNotFound", None)
    latest[2][1]["duration"] = 500
    assert rows == before
    corrupt_private = deepcopy(rows)
    corrupt_private["private-a"]["decoded"] = False
    assert fetch(corrupt_private, "private-a", 0) == ("NotFound", "FlypathNotFound", None)
    corrupt_public = deepcopy(rows)
    corrupt_public["public-a"]["decoded"] = False
    assert fetch(corrupt_public, "public-a", 0)[:2] == ("ValidationFailed", "StoredRecordDecodeFailed")
    mismatched = deepcopy(rows)
    mismatched["public-a"]["visibility"] = "private"
    assert fetch(mismatched, "public-a", 0)[:2] == ("ValidationFailed", "StoredRecordIndexMismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    assert_graph(args.project_root, args.input, paste=args.paste)
    semantic()
    print("Repository immutable published fetch contracts passed")


if __name__ == "__main__":
    main()
