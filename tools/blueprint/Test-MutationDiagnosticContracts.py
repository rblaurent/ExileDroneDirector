"""Semantic contracts for stable waypoint mutation diagnostics."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


EXPECTED = {
    "CaptureCurrentWaypoint": {
        "accepted": {"[EDD] Waypoint captured": 1},
        "rejected": {"[EDD] Capture ignored: no drone camera": "camera"},
    },
    "ReplaceSelectedWaypoint": {
        "accepted": {"[EDD] Selected waypoint replaced": 1},
        "rejected": {
            "[EDD] Replace ignored: no drone camera": "camera",
            "[EDD] Replace ignored: invalid selection": "selection",
        },
    },
    "DeleteSelectedWaypoint": {
        "accepted": {"[EDD] Selected waypoint deleted": 2},
        "rejected": {"[EDD] Delete ignored: invalid selection": "selection"},
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helper: {path}")
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


def message(node) -> str:
    pin = next(line for line in node.text.splitlines() if 'PinName="InString"' in line)
    match = re.search(r'DefaultValue="([^"]*)"', pin)
    if match is None:
        raise AssertionError(f"{node.name} has no literal diagnostic message")
    return match.group(1)


def flag(node, pin_name: str) -> str:
    pin = next(line for line in node.text.splitlines() if f'PinName="{pin_name}"' in line)
    match = re.search(r'DefaultValue="(true|false)"', pin)
    if match is None:
        raise AssertionError(f"{node.name}.{pin_name} has no Boolean default")
    return match.group(1)


def branch_for_kind(c, nodes, kind: str):
    branches = [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]
    if kind == "camera":
        valid = calls(nodes, "IsValid")
        c.require(len(valid) == 1, "Camera rejection contract requires one IsValid call")
        matches = [branch for branch in branches if c.linked(valid[0], "ReturnValue", branch, "Condition")]
    else:
        valid_index = [
            node
            for node in nodes.values()
            if 'MemberName="Array_IsValidIndex"' in node.text
        ]
        matches = [
            branch
            for branch in branches
            if any(c.linked(check, "ReturnValue", branch, "Condition") for check in valid_index)
            and not branch.pins["else"].links
        ]
        # Once diagnostics are attached, the precondition branch is the one whose
        # false path reaches a PrintString.  Post-delete repair keeps both paths live.
        matches = [
            branch
            for branch in branches
            if any(c.linked(check, "ReturnValue", branch, "Condition") for check in valid_index)
            and any(
                target in nodes and 'MemberName="PrintString"' in nodes[target].text
                for target, _ in branch.pins["else"].links
            )
        ]
    c.require(len(matches) == 1, f"Expected one {kind} rejection guard; found {[node.name for node in matches]}")
    return matches[0]


def assert_graph(c, history, nodes, entry_name: str, expected_paths: int, operation: str, *, paste: bool) -> None:
    last_rejection = {
        "CaptureCurrentWaypoint": "[EDD] Capture ignored: no drone camera",
        "ReplaceSelectedWaypoint": "[EDD] Replace ignored: invalid selection",
        "DeleteSelectedWaypoint": "[EDD] Delete ignored: invalid selection",
    }[entry_name]
    history.assert_history_path(
        c,
        history.preview,
        nodes,
        entry_name,
        expected_paths,
        operation,
        paste=paste,
        rejection_message=last_rejection,
    )
    diagnostics = calls(nodes, "PrintString")
    actual = {}
    for node in diagnostics:
        actual.setdefault(message(node), []).append(node)
        c.require(flag(node, "bPrintToScreen") == "false", f"{message(node)} must not clutter the cinematic frame")
        c.require(flag(node, "bPrintToLog") == "true", f"{message(node)} must be written to the log")

    specification = EXPECTED[entry_name]
    expected_messages = set(specification["accepted"]) | set(specification["rejected"])
    c.require(set(actual) == expected_messages, f"{entry_name} diagnostic set changed: {sorted(actual)}")
    for text, count in specification["accepted"].items():
        c.require(len(actual[text]) == count, f"{entry_name} accepted diagnostic path count changed")
        for node in actual[text]:
            c.require(not node.pins["then"].links, f"{text} must terminate its accepted path")
    for text, kind in specification["rejected"].items():
        c.require(len(actual[text]) == 1, f"{entry_name} rejected diagnostic must be unique")
        guard = branch_for_kind(c, nodes, kind)
        c.require_link(guard, "else", actual[text][0], "execute", f"{text} must execute only from its failed precondition")
        c.require(not actual[text][0].pins["then"].links, f"{text} must remain a terminal no-op")

    # Rejected paths may log, but they must never record history or mutate arrays.
    record = calls(nodes, "RecordUndoSnapshotV1")
    c.require(len(record) == 1, f"{entry_name} history record call changed")
    for text in specification["rejected"]:
        node = actual[text][0]
        c.require(not node.pins["then"].links, f"{text} must not reach history or mutation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument("--only", choices=("capture", "replace", "delete"))
    args = parser.parse_args()
    c = load_module(
        "edd_mutation_diagnostic_contract_base",
        args.project_root / "tools" / "blueprint" / "Test-PathPreviewContracts.py",
    )
    history = load_module(
        "edd_mutation_diagnostic_history_contract",
        args.project_root / "tools" / "blueprint" / "Test-DraftHistoryIntegrationContracts.py",
    )
    history.preview = load_module(
        "edd_mutation_diagnostic_preview_contract",
        args.project_root / "tools" / "blueprint" / "Test-PathPreviewIntegrationContracts.py",
    )
    suffix = "-paste" if args.paste else ""

    def parse(stem: str):
        return c.parse(args.input_dir / f"{stem}{suffix}.eddgraph")

    if args.only in (None, "capture"):
        assert_graph(c, history, parse("capture-current-waypoint-diagnostics-v1"), "CaptureCurrentWaypoint", 1, "Array_Add", paste=args.paste)
    if args.only in (None, "replace"):
        assert_graph(c, history, parse("replace-selected-waypoint-diagnostics-v1"), "ReplaceSelectedWaypoint", 1, "Array_Set", paste=args.paste)
    if args.only in (None, "delete"):
        assert_graph(c, history, parse("delete-selected-waypoint-diagnostics-v1"), "DeleteSelectedWaypoint", 2, "Array_Remove", paste=args.paste)
    print("Mutation diagnostic contracts passed: stable accepted/rejected terminal logs")


if __name__ == "__main__":
    main()
