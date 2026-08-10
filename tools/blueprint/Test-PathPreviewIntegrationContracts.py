"""Semantic contracts for preview integration in production client functions."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-PathPreviewContracts.py"
    spec = importlib.util.spec_from_file_location("edd_preview_integration_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
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


def assert_closed(c, nodes, entry_name: str, *, paste: bool) -> None:
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
    c.require(not external, f"{entry_name} contains external links: {external}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), f"{entry_name} entry inclusion changed")
    if not paste:
        c.require(f'MemberName="{entry_name}"' in entries[0].text, f"Wrong {entry_name} entry")


def assert_enter(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, "EnterDroneMode", paste=paste)
    branches = [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]
    c.require(len(branches) == 1, "Enter camera-validity branch changed")
    if paste:
        c.require(not branches[0].pins["execute"].links, "Enter paste body must expose its camera-validity branch")
    else:
        entry = next(node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class)
        c.require_link(entry, "then", branches[0], "execute", "Enter entry must evaluate camera validity")
    activates = calls(nodes, "ActivateDroneView")
    refreshes = calls(nodes, "RefreshPathPreviewV1")
    c.require(len(activates) == 2 and len(refreshes) == 2, "Both enter success paths need one refresh")
    reached = []
    for activate in activates:
        refresh = c.linked_target(nodes, activate, "then", "execute", 'MemberName="RefreshPathPreviewV1"')
        c.require(not refresh.pins["then"].links, "Enter refresh must remain the terminal success step")
        reached.append(refresh.name)
    c.require(len(set(reached)) == 2, "Enter success paths must not converge through a shared refresh call")


def assert_exit(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, "ExitDroneMode", paste=paste)
    destroys = calls(nodes, "DestroyPathPreviewV1")
    c.require(len(destroys) == 1, "Exit must destroy the owned preview exactly once")
    destroy = destroys[0]
    branches = [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]
    c.require(len(branches) == 1, "Exit original-view guard changed")
    c.require_link(destroy, "then", branches[0], "execute", "Preview cleanup must precede view restoration")
    if paste:
        c.require(not destroy.pins["execute"].links, "Exit paste body must expose Destroy as its entry pin")
    else:
        entry = next(node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class)
        c.require_link(entry, "then", destroy, "execute", "Exit entry must always destroy the preview first")


def assert_mutation(
    c,
    nodes,
    entry_name: str,
    expected_paths: int,
    *,
    paste: bool,
    diagnostic_terminals: bool = False,
) -> None:
    assert_closed(c, nodes, entry_name, paste=paste)
    branches = [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]
    exposed = [node for node in branches if not node.pins["execute"].links]
    if paste:
        c.require(len(exposed) == 1, f"{entry_name} paste body must expose exactly one entry branch")
    else:
        entry = next(node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class)
        entry_branch = c.linked_target(nodes, entry, "then", "execute", "K2Node_IfThenElse")
        c.require(entry_branch in branches, f"{entry_name} entry must drive a branch")
    if entry_name in {"CaptureCurrentWaypoint", "ReplaceSelectedWaypoint"}:
        validity_calls = calls(nodes, "IsValid")
        c.require(len(validity_calls) == 1, f"{entry_name} camera-validity call count changed")
        validity_call = validity_calls[0]
        validity_guards = [
            branch
            for branch in branches
            if any(target == validity_call.name for target, _ in branch.pins["Condition"].links)
        ]
        c.require(len(validity_guards) == 1, f"{entry_name} camera-validity guard changed")
        validity_guard = validity_guards[0]
        if paste:
            c.require(
                not validity_guard.pins["execute"].links,
                f"{entry_name} paste entry must expose the camera-validity guard",
            )
        else:
            entry = next(node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class)
            c.require_link(
                entry,
                "then",
                validity_guard,
                "execute",
                f"{entry_name} entry must evaluate camera validity first",
            )
        if entry_name == "ReplaceSelectedWaypoint":
            index_guards = [branch for branch in branches if branch is not validity_guard]
            c.require(len(index_guards) == 1, "Replace must retain exactly one selected-index guard")
            c.require_link(
                validity_guard,
                "then",
                index_guards[0],
                "execute",
                "Replace must evaluate selected-index validity only after camera validity",
            )
    c.require(not calls(nodes, "SyncDraftWaypointsV1"), f"{entry_name} must not leave the document stale")
    syncs = calls(nodes, "SyncDraftDocumentV1")
    refreshes = calls(nodes, "RefreshPathPreviewV1")
    c.require(len(syncs) == expected_paths, f"{entry_name} document-sync path count changed")
    c.require(len(refreshes) == expected_paths, f"{entry_name} refresh path count changed")
    reached = []
    for sync in syncs:
        refresh = c.linked_target(nodes, sync, "then", "execute", 'MemberName="RefreshPathPreviewV1"')
        reached.append(refresh.name)
    c.require(len(set(reached)) == expected_paths, f"{entry_name} must refresh independently after every sync")
    if entry_name in {"CaptureCurrentWaypoint", "ReplaceSelectedWaypoint"}:
        refresh = refreshes[0]
        prints = calls(nodes, "PrintString")
        accepted = [node for node in prints if c.linked(refresh, "then", node, "execute")]
        c.require(len(accepted) == 1, f"{entry_name} accepted feedback path changed")
        if not diagnostic_terminals:
            c.require(len(prints) == 1, f"{entry_name} feedback node changed")
    else:
        for refresh in refreshes:
            if diagnostic_terminals:
                diagnostic = c.linked_target(nodes, refresh, "then", "execute", 'MemberName="PrintString"')
                c.require(not diagnostic.pins["then"].links, "Delete success diagnostic must terminate its branch")
            else:
                c.require(not refresh.pins["then"].links, "Delete refreshes must terminate their successful branches")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_helpers(args.project_root)
    suffix = "-paste" if args.paste else ""

    def parse(stem: str):
        return c.parse(args.input_dir / f"{stem}{suffix}.eddgraph")

    assert_enter(c, parse("enter-drone-mode-preview"), paste=args.paste)
    assert_exit(c, parse("exit-drone-mode-preview"), paste=args.paste)
    assert_mutation(c, parse("capture-current-waypoint-preview"), "CaptureCurrentWaypoint", 1, paste=args.paste)
    assert_mutation(c, parse("replace-selected-waypoint-preview"), "ReplaceSelectedWaypoint", 1, paste=args.paste)
    assert_mutation(c, parse("delete-selected-waypoint-preview"), "DeleteSelectedWaypoint", 2, paste=args.paste)
    print("Path preview integration graph contracts passed")


if __name__ == "__main__":
    main()
