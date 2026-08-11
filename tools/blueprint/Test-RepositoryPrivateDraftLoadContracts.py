"""Structural and semantic contracts for owner-only private draft loading."""

from __future__ import annotations

import argparse
import importlib.util
from dataclasses import dataclass
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_private_load_contract_base", path)
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


def exact_default(c, node, pin: str, expected: str) -> None:
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', c.pin(node, pin).body)
    c.require((match.group(1) if match else "") == expected, f"{pin} default changed")


def one(c, values, label: str):
    c.require(len(values) == 1, f"{label}: expected one, found {len(values)}")
    return values[0]


def structural(c, path: Path, paste: bool) -> None:
    nodes = c.parse_graph(path)
    c.require(len(nodes) == (33 if paste else 34), f"LoadDraftV1 node count changed: {len(nodes)}")
    for node in nodes.values():
        for pin in node.pins.values():
            c.require(
                len(pin.links) == len(set(pin.links)),
                f"{node.name}.{pin.name} contains a duplicate Blueprint link",
            )
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), "LoadDraftV1 entry count changed")
    reset = one(c, calls(nodes, "ResetRepositoryResultV1"), "result reset")
    find = one(c, calls(nodes, "FindRecordIndexV1"), "record lookup")
    decode = one(c, calls(nodes, "DecodeRecordV1"), "record decode")
    validate = one(c, calls(nodes, "ValidateRecordV1"), "record validation")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 4, "LoadDraftV1 needs found/owner/decode/validation branches")
    if not paste:
        c.require_link(entries[0], "then", reset, "execute", "entry must reset result")
    else:
        c.require(not c.pin(reset, "execute").links, "paste root must be intentionally unwired")
    c.require_link(reset, "then", find, "execute", "reset must precede lookup")

    owner_get = one(c, variables(nodes, "ActiveOwnerAccountIdsV1", "K2Node_VariableGet"), "owner index")
    requester = one(c, variables(nodes, "RequestRequesterAccountIdV1", "K2Node_VariableGet"), "requester")
    envelope_get = one(c, variables(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableGet"), "envelopes")
    index_get = one(c, variables(nodes, "ResultRecordIndexV1", "K2Node_VariableGet"), "index")
    c.require(owner_get and requester and envelope_get and index_get, "required lookup staging missing")

    for code, detail in (
        ("NotFound", "FlypathNotFound"),
        ("Forbidden", "OwnerRequired"),
        ("ValidationFailed", "StoredRecordDecodeFailed"),
        ("ValidationFailed", "StoredRecordInvalid"),
    ):
        matching_codes = [
            node for node in variables(nodes, "ResultCodeV1", "K2Node_VariableSet")
            if f'DefaultValue="{code}"' in c.pin(node, "ResultCodeV1").body
        ]
        matching_details = [
            node for node in variables(nodes, "ResultDetailV1", "K2Node_VariableSet")
            if f'DefaultValue="{detail}"' in c.pin(node, "ResultDetailV1").body
        ]
        c.require(matching_codes, f"missing result code {code}")
        c.require(len(matching_details) == 1, f"missing stable detail {detail}")

    has_revision = one(c, variables(nodes, "ResultHasCurrentRevisionV1", "K2Node_VariableSet"), "revision flag")
    exact_default(c, has_revision, "ResultHasCurrentRevisionV1", "true")
    one(c, variables(nodes, "ResultCurrentRevisionV1", "K2Node_VariableSet"), "current revision")
    one(c, variables(nodes, "ResultRecordEnvelopeV1", "K2Node_VariableSet"), "result envelope")
    one(c, variables(nodes, "ResultDraftDocumentV1", "K2Node_VariableSet"), "result document")
    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"LoadDraftV1 external links: {sorted(external)}")


@dataclass(frozen=True)
class Record:
    owner: str
    revision: int
    envelope: str
    document: str
    decodes: bool = True
    validates: bool = True


def load(records: dict[str, Record], requester: str, flypath_id: str):
    record = records.get(flypath_id)
    if record is None:
        return "NotFound", "FlypathNotFound", None
    if record.owner != requester:
        return "Forbidden", "OwnerRequired", None
    if not record.decodes:
        return "ValidationFailed", "StoredRecordDecodeFailed", None
    if not record.validates:
        return "ValidationFailed", "StoredRecordInvalid", None
    return "Success", "", (record.envelope, record.revision, record.document)


def semantic() -> None:
    good = Record("owner-a", 7, "canonical-envelope", "private-document")
    assert load({}, "owner-a", "missing") == ("NotFound", "FlypathNotFound", None)
    assert load({"p": good}, "owner-b", "p") == ("Forbidden", "OwnerRequired", None)
    assert load({"p": Record("owner-a", 7, "bad", "doc", False)}, "owner-a", "p") == (
        "ValidationFailed", "StoredRecordDecodeFailed", None
    )
    assert load({"p": Record("owner-a", 7, "bad", "doc", True, False)}, "owner-a", "p") == (
        "ValidationFailed", "StoredRecordInvalid", None
    )
    assert load({"p": good}, "owner-a", "p") == (
        "Success", "", ("canonical-envelope", 7, "private-document")
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    structural(c, args.input, args.paste)
    semantic()
    print("Repository private draft load contracts passed")


if __name__ == "__main__":
    main()
