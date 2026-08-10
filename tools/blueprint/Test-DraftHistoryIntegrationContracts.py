"""Contracts for atomic history capture around waypoint mutations."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def calls(nodes, function_name: str):
    return [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class
        and re.search(rf'MemberName="{re.escape(function_name)}"', node.text)
    ]


def array_mutations(nodes, operation: str):
    return [
        node
        for node in nodes.values()
        if "K2Node_CallArrayFunction" in node.node_class
        and re.search(rf'MemberName="{re.escape(operation)}"', node.text)
    ]


def assert_history_path(c, preview, nodes, entry_name: str, expected_paths: int, operation: str, *, paste: bool):
    preview.assert_mutation(c, nodes, entry_name, expected_paths, paste=paste)
    records = calls(nodes, "RecordUndoSnapshotV1")
    c.require(len(records) == 1, f"{entry_name} must record exactly one undo snapshot")
    record = records[0]
    mutations = array_mutations(nodes, operation)
    c.require(mutations, f"{entry_name} lost its {operation} mutation chain")
    guarded = []
    for branch in [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]:
        if (record.name, record.pins["execute"].pin_id) in branch.pins["then"].links:
            guarded.append(branch)
    c.require(len(guarded) == 1, f"{entry_name} snapshot must have one successful precondition guard")
    guard = guarded[0]
    c.require(not guard.pins["else"].links, f"{entry_name} invalid attempt must remain a history-free no-op")
    first_mutation = c.linked_target(nodes, record, "then", "execute", "K2Node_CallArrayFunction")
    c.require(first_mutation in mutations, f"{entry_name} snapshot must precede the first {operation}")
    for mutation in mutations:
        c.require(
            (record.name, record.pins["then"].pin_id) not in mutation.pins["execute"].links
            or mutation is first_mutation,
            f"{entry_name} has an ambiguous history-to-mutation edge",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_module(
        "edd_history_integration_contract_base",
        args.project_root / "tools" / "blueprint" / "Test-PathPreviewContracts.py",
    )
    preview = load_module(
        "edd_history_integration_preview_contract",
        args.project_root / "tools" / "blueprint" / "Test-PathPreviewIntegrationContracts.py",
    )
    suffix = "-paste" if args.paste else ""

    def parse(stem: str):
        return c.parse(args.input_dir / f"{stem}{suffix}.eddgraph")

    assert_history_path(
        c,
        preview,
        parse("capture-current-waypoint-history-v1"),
        "CaptureCurrentWaypoint",
        1,
        "Array_Add",
        paste=args.paste,
    )
    assert_history_path(
        c,
        preview,
        parse("replace-selected-waypoint-history-v1"),
        "ReplaceSelectedWaypoint",
        1,
        "Array_Set",
        paste=args.paste,
    )
    assert_history_path(
        c,
        preview,
        parse("delete-selected-waypoint-history-v1"),
        "DeleteSelectedWaypoint",
        2,
        "Array_Remove",
        paste=args.paste,
    )
    print("Draft history mutation integration contracts passed")


if __name__ == "__main__":
    main()
