"""Structural and semantic contracts for metadata-only ListPublicV1."""

from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
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


def nodes_with(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def one_class(c, nodes, marker: str, node_class: str):
    matches = [
        node for node in nodes.values()
        if marker in node.text and node_class in node.node_class
    ]
    c.require(
        len(matches) == 1,
        f"Expected one {node_class} containing {marker!r}; found {len(matches)}",
    )
    return matches[0]


def assert_graph(project_root: Path, graph: Path, *, paste: bool) -> None:
    c = load(
        project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py",
        "edd_public_list_contract_base",
    )
    nodes = c.parse_graph(graph)
    c.require(len(nodes) == (144 if paste else 145), f"Public list node count changed: {len(nodes)}")
    known = set(nodes)
    external = sorted(
        {
            target
            for node in nodes.values()
            for pin in node.pins.values()
            for target, _ in pin.links
            if target not in known
        }
    )
    c.require(not external, f"External links are forbidden: {external}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "Public-list entry inclusion changed")
    if not paste:
        c.require('MemberName="ListPublicV1"' in entries[0].text, "Wrong public-list entry")

    for forbidden in (
        'MemberName="RequestRequesterAccountIdV1"',
        'DefaultValue="InvalidListRequest"',
        'MemberName="PersistRepositoryV1"',
        'MemberName="PreparePersistenceCandidateV1"',
        'MemberName="CandidateRecordEnvelopesV1"',
        'MemberName="CandidateTombstoneFlypathIdsV1"',
        'DefaultValue="draft"',
        'DefaultValue="published"',
        'DefaultValue="waypoints"',
        'DefaultValue="segments"',
        'DefaultValue="ownerAccountId"',
    ):
        c.require(not nodes_with(nodes, forbidden), f"Public discovery leaked/used forbidden seam: {forbidden}")

    c.require(
        len(nodes_with(nodes, 'MemberName="ActiveVisibilitiesV1"')) == 1,
        "Visibility must drive derived filtering and selected-record identity",
    )
    public_defaults = nodes_with(nodes, 'DefaultValue="public"')
    c.require(len(public_defaults) == 2, "Public filter/authorization defaults changed")
    c.require(
        len(nodes_with(nodes, 'MemberName="ActiveOwnerAccountIdsV1"')) == 1,
        "Owner derived index must be alignment-checked and identity-checked only",
    )
    for function, count in (
        ("ResetRepositoryResultV1", 4),
        ("DecodeRecordV1", 1),
        ("ValidateRecordV1", 1),
        ("EncodeMetadataV1", 1),
        ("CompareStringsOrdinalV1", 2),
    ):
        c.require(
            len(nodes_with(nodes, f'MemberName="{function}"')) == count,
            f"{function} call count changed",
        )
    c.require(len(nodes_with(nodes, "StandardMacros:ForEachLoop")) == 4, "Loop topology changed")
    c.require(len(nodes_with(nodes, 'MemberName="Array_Find"')) == 1, "Selection-sort exclusion changed")
    c.require(len([n for n in nodes.values() if "K2Node_Select" in n.node_class]) == 4, "Paging clamps changed")
    c.require(nodes_with(nodes, 'DefaultValue="100"'), "Page limit must clamp to 100")
    for detail in (
        "MetadataIndexMisaligned",
        "StoredRecordDecodeFailed",
        "StoredRecordInvalid",
        "StoredRecordIndexMismatch",
    ):
        c.require(nodes_with(nodes, f'DefaultValue="{detail}"'), f"Failure detail changed: {detail}")

    misaligned_detail = c.one(nodes, 'DefaultValue="MetadataIndexMisaligned"')
    misaligned_codes = [
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class
        and c.linked(node, "then", misaligned_detail, "execute")
    ]
    c.require(len(misaligned_codes) == 1, "Misalignment result chain changed")
    alignment = [
        node for node in nodes.values()
        if "K2Node_IfThenElse" in node.node_class
        and c.linked(node, "else", misaligned_codes[0], "execute")
    ]
    c.require(len(alignment) == 1, "Alignment branch changed")
    resets = nodes_with(nodes, 'MemberName="ResetRepositoryResultV1"')
    reset_candidates = [
        node for node in resets
        if c.linked(node, "then", alignment[0], "execute")
    ]
    c.require(len(reset_candidates) == 1, "Initial reset/alignment seam changed")
    reset = reset_candidates[0]
    if paste:
        c.require(not reset.pins["execute"].links, "Paste body must expose its initial reset")
    else:
        c.require_link(entries[0], "then", reset, "execute", "Entry must begin with reset")
        c.require_link(reset, "then", alignment[0], "execute", "Public query must go directly to alignment")


def encode_metadata(record: dict) -> str:
    payload = {
        "draftRevisionNumber": record["revision"],
        "flypathId": record["id"],
        "hasPublishedRevision": record["has_published"],
        "ownerDisplayName": record["display"],
        "publishedRevisionNumber": record["published_revision"],
        "regionId": record["region"],
        "title": record["title"],
        "updatedUtc": record["updated"],
        "visibility": record["visibility"],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def list_public(state: dict, offset: int, limit: int):
    arrays = (state["ids"], state["owners"], state["visibilities"], state["updated"], state["records"])
    if len({len(values) for values in arrays}) != 1:
        return "ValidationFailed", "MetadataIndexMisaligned", [], 0, 0, False
    selected = [
        index for index, visibility in enumerate(state["visibilities"])
        if visibility == "public"
    ]
    selected.sort(key=lambda index: (state["updated"][index], state["ids"][index]), reverse=True)
    safe_offset = max(0, offset)
    safe_limit = min(100, max(1, limit))
    end = min(len(selected), safe_offset + safe_limit)
    page = []
    for index in selected[safe_offset:end]:
        record = state["records"][index]
        if not record.get("decoded", True):
            return "ValidationFailed", "StoredRecordDecodeFailed", [], 0, 0, False
        if not record.get("valid", True):
            return "ValidationFailed", "StoredRecordInvalid", [], 0, 0, False
        if (
            record["id"] != state["ids"][index]
            or record["owner"] != state["owners"][index]
            or record["visibility"] != state["visibilities"][index]
            or record["updated"] != state["updated"][index]
            or record["visibility"] != "public"
        ):
            return "ValidationFailed", "StoredRecordIndexMismatch", [], 0, 0, False
        page.append(encode_metadata(record))
    return "Success", "", page, safe_offset, len(selected), end < len(selected)


def record(path: str, owner: str, updated: str, *, visibility: str, valid: bool = True):
    return {
        "id": path,
        "owner": owner,
        "display": owner.title(),
        "title": f"Title {path}",
        "visibility": visibility,
        "region": "ExiledLands",
        "updated": updated,
        "revision": 3,
        "has_published": visibility == "public",
        "published_revision": 2 if visibility == "public" else 0,
        "draft": {"waypoints": ["must-not-leak"]},
        "published": {"waypoints": ["must-not-leak"]},
        "valid": valid,
        "decoded": True,
    }


def make_state(records: list[dict]) -> dict:
    return {
        "ids": [item["id"] for item in records],
        "owners": [item["owner"] for item in records],
        "visibilities": [item["visibility"] for item in records],
        "updated": [item["updated"] for item in records],
        "records": records,
    }


def semantic() -> None:
    fixture = make_state(
        [
            record("private-newest", "owner-a", "2026-08-11T23:59:00Z", visibility="private", valid=False),
            record("alpha", "owner-a", "2026-08-11T18:00:00Z", visibility="public"),
            record("zulu", "owner-b", "2026-08-11T18:00:00Z", visibility="public"),
            record("newest", "owner-c", "2026-08-11T19:00:00Z", visibility="public"),
            record("private-other", "owner-d", "2026-08-11T20:00:00Z", visibility="private"),
        ]
    )
    before = deepcopy(fixture)
    result = list_public(fixture, -5, 2)
    assert result[:2] == ("Success", "")
    assert result[3:] == (0, 3, True)
    decoded = [json.loads(item) for item in result[2]]
    assert [item["flypathId"] for item in decoded] == ["newest", "zulu"]
    assert all(item["visibility"] == "public" for item in decoded)
    assert all("draft" not in item and "published" not in item and "ownerAccountId" not in item for item in decoded)
    assert fixture == before
    assert len(list_public(fixture, 1, 1000)[2]) == 2
    assert list_public(fixture, 50, 20)[2:] == ([], 50, 3, False)
    assert len(list_public(fixture, 0, 0)[2]) == 1

    empty = make_state([record("private", "owner-a", "2026-08-11T20:00:00Z", visibility="private")])
    assert list_public(empty, 0, 20) == ("Success", "", [], 0, 0, False)
    misaligned = deepcopy(fixture)
    misaligned["owners"].pop()
    assert list_public(misaligned, 0, 20)[:3] == (
        "ValidationFailed", "MetadataIndexMisaligned", []
    )
    corrupt = deepcopy(fixture)
    corrupt["records"][3]["decoded"] = False
    assert list_public(corrupt, 0, 20)[:3] == (
        "ValidationFailed", "StoredRecordDecodeFailed", []
    )
    invalid = deepcopy(fixture)
    invalid["records"][2]["valid"] = False
    assert list_public(invalid, 0, 20)[:3] == (
        "ValidationFailed", "StoredRecordInvalid", []
    )
    mismatch = deepcopy(fixture)
    mismatch["records"][1]["visibility"] = "private"
    assert list_public(mismatch, 0, 20)[:3] == (
        "ValidationFailed", "StoredRecordIndexMismatch", []
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    assert_graph(args.project_root, args.input, paste=args.paste)
    semantic()
    print("Repository public-list graph contracts passed")


if __name__ == "__main__":
    main()
