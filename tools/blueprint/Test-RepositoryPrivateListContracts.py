"""Structural and semantic contracts for EncodeMetadataV1 and ListMineV1."""

from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_private_list_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nodes_with(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def one(c, nodes, marker: str):
    return c.one(nodes, marker)


def one_class(c, nodes, marker: str, node_class: str):
    matches = [
        node for node in nodes.values()
        if marker in node.text and node_class in node.node_class
    ]
    c.require(len(matches) == 1, f"Expected one {node_class} containing {marker!r}; found {len(matches)}")
    return matches[0]


def assert_closed(c, nodes, expected: int, entry: str | None) -> None:
    c.require(len(nodes) == expected, f"Expected {expected} nodes; found {len(nodes)}")
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
    c.require(len(entries) == (1 if entry else 0), "Function entry inclusion changed")
    if entry:
        c.require(f'MemberName="{entry}"' in entries[0].text, "Wrong function entry")


def assert_metadata(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 25 if paste else 26, None if paste else "EncodeMetadataV1")
    fields = (
        "flypathId",
        "ownerDisplayName",
        "title",
        "visibility",
        "regionId",
        "updatedUtc",
        "draftRevisionNumber",
        "hasPublishedRevision",
        "publishedRevisionNumber",
    )
    for field in fields:
        c.require(len(nodes_with(nodes, f'DefaultValue="{field}"')) == 1, f"Metadata field changed: {field}")
    for forbidden in (
        'DefaultValue="draft"',
        'DefaultValue="published"',
        'DefaultValue="waypoints"',
        'DefaultValue="segments"',
        'DefaultValue="description"',
        'DefaultValue="ownerAccountId"',
    ):
        c.require(not nodes_with(nodes, forbidden), f"Metadata payload leaked: {forbidden}")
    c.require(len(nodes_with(nodes, 'MemberName="SetStringField"')) == 6, "String metadata field count changed")
    c.require(len(nodes_with(nodes, 'MemberName="SetNumberField"')) == 2, "Number metadata field count changed")
    c.require(len(nodes_with(nodes, 'MemberName="SetBoolField"')) == 1, "Boolean metadata field count changed")
    encoded = one_class(c, nodes, 'MemberName="ScratchEncodedMetadataV1"', "K2Node_VariableSet")
    encode = one(c, nodes, 'MemberName="EncodeJson"')
    c.require_link(encode, "ReturnValue", encoded, "ScratchEncodedMetadataV1", "Metadata JSON must publish exactly once")
    if paste:
        root = one_class(c, nodes, 'MemberName="ScratchRootJsonV1"', "K2Node_VariableSet")
        c.require(not root.pins["execute"].links, "Paste body must expose its first setter")
    else:
        entry = one_class(c, nodes, 'MemberName="EncodeMetadataV1"', "K2Node_FunctionEntry")
        root = one_class(c, nodes, 'MemberName="ScratchRootJsonV1"', "K2Node_VariableSet")
        c.require_link(entry, "then", root, "execute", "Metadata entry must reach its root setter")


def assert_ordinal_compare(c, nodes, *, paste: bool) -> None:
    assert_closed(
        c,
        nodes,
        23 if paste else 24,
        None if paste else "CompareStringsOrdinalV1",
    )
    for function, count in (
        ("GetCharacterArrayFromString", 1),
        ("GetCharacterAsNumber", 2),
        ("Len", 2),
        ("NotEqual_IntInt", 1),
        ("Greater_IntInt", 2),
    ):
        c.require(
            len(nodes_with(nodes, f'MemberName="{function}"')) == count,
            f"Ordinal comparator {function} count changed",
        )
    c.require(
        len(nodes_with(nodes, "StandardMacros:ForEachLoop")) == 1,
        "Ordinal comparator loop changed",
    )
    for field in (
        "ScratchCompareLeftV1",
        "ScratchCompareRightV1",
        "ScratchCompareResolvedV1",
        "ScratchStringGreaterV1",
    ):
        c.require(nodes_with(nodes, f'MemberName="{field}"'), f"Comparator state missing: {field}")
    for node in nodes_with(nodes, 'MemberName="GetCharacterAsNumber"'):
        c.require(set(("SourceString", "Index", "ReturnValue")) <= set(node.pins), "Character-number signature changed")
    resets = [
        node
        for node in nodes_with(nodes, 'MemberName="ScratchCompareResolvedV1"')
        if (
            "K2Node_VariableSet" in node.node_class
            and 'DefaultValue="false"' in node.text
            and 'DefaultValue="true"' not in node.text
        )
    ]
    c.require(len(resets) == 1, "Comparator must own one false resolved reset")
    reset = resets[0]
    if paste:
        c.require(not reset.pins["execute"].links, "Comparator paste body must expose its reset seam")
    else:
        entry = one_class(c, nodes, 'MemberName="CompareStringsOrdinalV1"', "K2Node_FunctionEntry")
        c.require_link(entry, "then", reset, "execute", "Comparator entry must reach its reset")


def assert_list(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 151 if paste else 152, None if paste else "ListMineV1")
    for field in (
        "ActiveFlypathIdsV1",
        "ActiveOwnerAccountIdsV1",
        "ActiveVisibilitiesV1",
        "ActiveUpdatedUtcV1",
        "ActiveRecordEnvelopesV1",
        "ScratchListOwnerIndexesV1",
        "ScratchListSortedIndexesV1",
        "ScratchListBestIndexV1",
        "ScratchListBestUpdatedUtcV1",
        "ScratchListBestFlypathIdV1",
        "ScratchListSafeOffsetV1",
        "ScratchListSafeLimitV1",
        "ScratchListEndExclusiveV1",
        "ScratchListFailedV1",
        "ResultMetadataEnvelopesV1",
        "ResultPageOffsetV1",
        "ResultTotalCountV1",
        "ResultHasMoreV1",
    ):
        c.require(nodes_with(nodes, f'MemberName="{field}"'), f"List state missing: {field}")
    for function, count in (
        ("ResetRepositoryResultV1", 4),
        ("DecodeRecordV1", 1),
        ("ValidateRecordV1", 1),
        ("EncodeMetadataV1", 1),
        ("CompareStringsOrdinalV1", 2),
    ):
        c.require(len(nodes_with(nodes, f'MemberName="{function}"')) == count, f"{function} call count changed")
    c.require(not nodes_with(nodes, 'MemberName="Array_Sort"'), "Unsupported native array sorting is forbidden")
    c.require(not nodes_with(nodes, 'MemberName="Concat_StrStr"'), "Tuple-key concatenation is no longer used")
    c.require(len(nodes_with(nodes, 'MemberName="Array_Find"')) == 1, "Sorted-index exclusion changed")
    c.require(len(nodes_with(nodes, "StandardMacros:ForEachLoop")) == 4, "Filter/sort/page loop count changed")
    c.require(len([node for node in nodes.values() if "K2Node_Select" in node.node_class]) == 4, "Offset/limit/end clamps changed")
    c.require(nodes_with(nodes, 'DefaultValue="100"'), "Page limit must clamp to 100")
    request_limits = nodes_with(nodes, 'MemberName="RequestLimitV1"')
    c.require(len(request_limits) == 1, "List request limit getter changed")
    lower_bound_predicates = nodes_with(nodes, 'MemberName="GreaterEqual_IntInt"')
    c.require(
        any(
            c.linked(request_limits[0], "RequestLimitV1", predicate, "A")
            for predicate in lower_bound_predicates
        ),
        "Request limit must feed the >= 1 clamp predicate",
    )
    for forbidden in (
        'MemberName="PersistRepositoryV1"',
        'MemberName="PreparePersistenceCandidateV1"',
        'MemberName="CandidateRecordEnvelopesV1"',
        'MemberName="CandidateTombstoneFlypathIdsV1"',
    ):
        c.require(not nodes_with(nodes, forbidden), f"Read-only listing may not mutate persistence: {forbidden}")
    metadata_add = [
        node
        for node in nodes_with(nodes, 'MemberName="Array_Add"')
        if "ResultMetadataEnvelopesV1" in node.text or any(
            target_pin == "TargetArray"
            for pin in node.pins.values()
            for _, target_pin in pin.links
        )
    ]
    c.require(nodes_with(nodes, 'DefaultValue="InvalidListRequest"'), "Blank requester failure changed")
    c.require(nodes_with(nodes, 'DefaultValue="MetadataIndexMisaligned"'), "Alignment failure changed")
    c.require(nodes_with(nodes, 'DefaultValue="StoredRecordDecodeFailed"'), "Decode failure changed")
    c.require(nodes_with(nodes, 'DefaultValue="StoredRecordInvalid"'), "Validation failure changed")
    c.require(nodes_with(nodes, 'DefaultValue="StoredRecordIndexMismatch"'), "Identity failure changed")
    if paste:
        resets = nodes_with(nodes, 'MemberName="ResetRepositoryResultV1"')
        roots = [node for node in resets if not node.pins["execute"].links]
        c.require(len(roots) == 1, "Paste body must expose exactly the initial reset seam")
    else:
        entry = one_class(c, nodes, 'MemberName="ListMineV1"', "K2Node_FunctionEntry")
        targets = entry.pins["then"].links
        c.require(len(targets) == 1, "List entry must expose exactly one execution successor")
        target_name, _ = targets[0]
        target = nodes[target_name]
        c.require('MemberName="ResetRepositoryResultV1"' in target.text, "List entry must begin with result reset")
        c.require_link(entry, "then", target, "execute", "List entry/reset link must be reciprocal")


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


def ordinal_greater(left: str, right: str) -> bool:
    left_units = left.encode("utf-16-le")
    right_units = right.encode("utf-16-le")
    left_values = [int.from_bytes(left_units[i:i + 2], "little") for i in range(0, len(left_units), 2)]
    right_values = [int.from_bytes(right_units[i:i + 2], "little") for i in range(0, len(right_units), 2)]
    for index, value in enumerate(left_values):
        other = right_values[index] if index < len(right_values) else 0
        if value != other:
            return value > other
    return len(left_values) > len(right_values)


def list_mine(state: dict, requester: str, offset: int, limit: int):
    if not requester.strip():
        return "ValidationFailed", "InvalidListRequest", [], 0, 0, False
    arrays = (state["ids"], state["owners"], state["visibilities"], state["updated"], state["records"])
    if len({len(values) for values in arrays}) != 1:
        return "ValidationFailed", "MetadataIndexMisaligned", [], 0, 0, False
    selected = [index for index, owner in enumerate(state["owners"]) if owner == requester]
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
            or record["owner"] != requester
        ):
            return "ValidationFailed", "StoredRecordIndexMismatch", [], 0, 0, False
        page.append(encode_metadata(record))
    return "Success", "", page, safe_offset, len(selected), end < len(selected)


def record(path: str, owner: str, updated: str, *, visibility: str = "private", valid: bool = True):
    return {
        "id": path,
        "owner": owner,
        "display": owner.title(),
        "title": f"Title {path}",
        "visibility": visibility,
        "region": "ExiledLands",
        "updated": updated,
        "revision": 2,
        "has_published": visibility == "public",
        "published_revision": 2 if visibility == "public" else 0,
        "draft": {"waypoints": ["large-payload-must-not-leak"]},
        "valid": valid,
        "decoded": True,
    }


def state(records: list[dict]) -> dict:
    return {
        "ids": [item["id"] for item in records],
        "owners": [item["owner"] for item in records],
        "visibilities": [item["visibility"] for item in records],
        "updated": [item["updated"] for item in records],
        "records": records,
    }


def semantic() -> None:
    assert not ordinal_greater("", "")
    assert not ordinal_greater("alpha", "alpha")
    assert ordinal_greater("zulu", "alpha")
    assert ordinal_greater("alpha-2", "alpha")
    assert not ordinal_greater("alpha", "alpha-2")
    fixture = state(
        [
            record("alpha", "owner-a", "2026-08-11T18:00:00Z"),
            record("foreign", "owner-b", "2026-08-11T23:00:00Z"),
            record("zulu", "owner-a", "2026-08-11T18:00:00Z", visibility="public"),
            record("newest", "owner-a", "2026-08-11T19:00:00Z"),
        ]
    )
    before = deepcopy(fixture)
    code, detail, page, offset, total, has_more = list_mine(fixture, "owner-a", -9, 2)
    assert (code, detail, offset, total, has_more) == ("Success", "", 0, 3, True)
    decoded = [json.loads(item) for item in page]
    assert [item["flypathId"] for item in decoded] == ["newest", "zulu"]
    assert all("draft" not in item and "ownerAccountId" not in item for item in decoded)
    assert set(decoded[0]) == {
        "draftRevisionNumber",
        "flypathId",
        "hasPublishedRevision",
        "ownerDisplayName",
        "publishedRevisionNumber",
        "regionId",
        "title",
        "updatedUtc",
        "visibility",
    }
    assert fixture == before
    assert list_mine(fixture, "owner-a", 1, 1000)[4:] == (3, False)
    assert len(list_mine(fixture, "owner-a", 1, 1000)[2]) == 2
    assert list_mine(fixture, "owner-a", 50, 20)[2:] == ([], 50, 3, False)
    assert list_mine(fixture, "owner-a", 0, 0)[2].__len__() == 1
    assert list_mine(fixture, "   ", 0, 20)[0:3] == (
        "ValidationFailed", "InvalidListRequest", []
    )

    misaligned = deepcopy(fixture)
    misaligned["updated"].pop()
    assert list_mine(misaligned, "owner-a", 0, 20)[0:3] == (
        "ValidationFailed", "MetadataIndexMisaligned", []
    )
    corrupt = deepcopy(fixture)
    corrupt["records"][3]["valid"] = False
    assert list_mine(corrupt, "owner-a", 0, 20)[0:3] == (
        "ValidationFailed", "StoredRecordInvalid", []
    )
    foreign_corrupt = deepcopy(fixture)
    foreign_corrupt["records"][1]["decoded"] = False
    assert list_mine(foreign_corrupt, "owner-a", 0, 20)[0] == "Success"
    mismatch = deepcopy(fixture)
    mismatch["records"][3]["id"] = "tampered"
    assert list_mine(mismatch, "owner-a", 0, 20)[0:3] == (
        "ValidationFailed", "StoredRecordIndexMismatch", []
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    assert_ordinal_compare(c, c.parse_graph(args.input_dir / f"compare-strings-ordinal-v1{suffix}.eddgraph"), paste=args.paste)
    assert_metadata(c, c.parse_graph(args.input_dir / f"encode-metadata-v1{suffix}.eddgraph"), paste=args.paste)
    assert_list(c, c.parse_graph(args.input_dir / f"list-mine-v1{suffix}.eddgraph"), paste=args.paste)
    semantic()
    print("Repository private list contracts passed")


if __name__ == "__main__":
    main()
