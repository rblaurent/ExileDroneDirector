"""Semantic contracts for reversible Conan-native Clean Frame graphs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-PathPreviewContracts.py"
    spec = importlib.util.spec_from_file_location("edd_clean_frame_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def one(c, nodes, pattern: str, label: str):
    matches = [node for node in nodes.values() if re.search(pattern, node.text)]
    c.require(len(matches) == 1, f"Expected one {label}; found {len(matches)}")
    return matches[0]


def calls(c, nodes, name: str):
    return [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class
        and f'MemberName="{name}"' in node.text
    ]


def assert_closed(c, nodes, count: int, function: str | None) -> None:
    c.require(len(nodes) == count, f"Unexpected node count: {len(nodes)}")
    known = set(nodes)
    unknown = sorted(
        {
            target
            for node in nodes.values()
            for pin in node.pins.values()
            for target, _ in pin.links
            if target not in known
        }
    )
    c.require(not unknown, f"External links found: {unknown}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (1 if function else 0), "Function-entry count changed")
    if function:
        c.require(f'MemberName="{function}"' in entries[0].text, "Wrong function entry")


def variable(c, nodes, name: str, setter: bool):
    kind = "K2Node_VariableSet" if setter else "K2Node_VariableGet"
    matches = [
        node
        for node in nodes.values()
        if kind in node.node_class and f'MemberName="{name}"' in node.text
    ]
    c.require(len(matches) == 1, f"Expected one {name} {kind}; found {len(matches)}")
    return matches[0]


def category_node(c, nodes, function: str, category: str):
    matches = [
        node
        for node in calls(c, nodes, function)
        if any(
            f'PinId={node.pins["Category"].pin_id}' in line
            and f'DefaultValue="{category}"' in line
            for line in node.text.splitlines()
        )
    ]
    c.require(len(matches) == 1, f"Expected one {function}({category}); found {len(matches)}")
    return matches[0]


def assert_enter(c, nodes, full: bool) -> None:
    assert_closed(c, nodes, 25 if full else 24, "EnterCleanFrameV1" if full else None)
    active = variable(c, nodes, "CleanFrameActiveV1", False)
    save_popup = variable(c, nodes, "CleanFrameRestorePopupCategoryV1", True)
    save_hud = variable(c, nodes, "CleanFrameRestoreHUDCategoryV1", True)
    set_active = variable(c, nodes, "CleanFrameActiveV1", True)
    guard = c.linked_target(nodes, active, "CleanFrameActiveV1", "Condition", "K2Node_IfThenElse")
    popup_query = category_node(c, nodes, "IsCategoryEnabled", "Popup")
    hud_query = category_node(c, nodes, "IsCategoryEnabled", "HUD")
    popup_disable = category_node(c, nodes, "EnableCategory", "Popup")
    hud_disable = category_node(c, nodes, "EnableCategory", "HUD")
    c.require_pin_default(popup_disable, "Enable", "false", "Popup must hide")
    c.require_pin_default(hud_disable, "Enable", "false", "HUD must hide")
    c.require_link(popup_query, "ReturnValue", save_popup, "CleanFrameRestorePopupCategoryV1", "Popup state must be captured")
    c.require_link(hud_query, "ReturnValue", save_hud, "CleanFrameRestoreHUDCategoryV1", "HUD state must be captured")
    c.require_link(save_popup, "then", save_hud, "execute", "Both states must be captured before suppression")
    c.require_link(save_hud, "then", popup_disable, "execute", "Capture must precede suppression")
    c.require_link(popup_disable, "then", hud_disable, "execute", "Popup and HUD suppression must be ordered")

    set_visibility = one(c, nodes, r'MemberName="SetHUDVisibility"', "ConanHUD visibility call")
    c.require_pin_default(set_visibility, "visibility", "Hidden", "Native notification layer must hide")
    hidden = one(c, nodes, r'MemberName="SetActorHiddenInGame"', "preview hide")
    c.require_pin_default(hidden, "bNewHidden", "true", "Preview actor must hide")
    c.require_link(hidden, "then", set_active, "execute", "Active state must commit after preview suppression")
    c.require_pin_default(set_active, "CleanFrameActiveV1", "true", "Enter must commit active=true")
    enabled_log = one(c, nodes, r'\[EDD\] Clean Frame enabled', "enabled log")
    c.require_link(set_active, "then", enabled_log, "execute", "Success log must follow state commit")
    ignored_log = one(c, nodes, r'already enabled', "idempotent enter log")
    c.require_link(guard, "then", ignored_log, "execute", "Repeated enter must not recapture state")
    if full:
        entry = one(c, nodes, r'FunctionReference=\(MemberName="EnterCleanFrameV1"\)', "entry")
        c.require_link(entry, "then", guard, "execute", "Entry must reach the active guard")
    else:
        c.require(not guard.pins["execute"].links, "Paste body must expose the guard entry")


def assert_exit(c, nodes, full: bool) -> None:
    assert_closed(c, nodes, 22 if full else 21, "ExitCleanFrameV1" if full else None)
    active = variable(c, nodes, "CleanFrameActiveV1", False)
    popup_state = variable(c, nodes, "CleanFrameRestorePopupCategoryV1", False)
    hud_state = variable(c, nodes, "CleanFrameRestoreHUDCategoryV1", False)
    clear_active = variable(c, nodes, "CleanFrameActiveV1", True)
    guard = c.linked_target(nodes, active, "CleanFrameActiveV1", "Condition", "K2Node_IfThenElse")
    popup_restore = category_node(c, nodes, "EnableCategory", "Popup")
    hud_restore = category_node(c, nodes, "EnableCategory", "HUD")
    c.require_link(popup_state, "CleanFrameRestorePopupCategoryV1", popup_restore, "Enable", "Popup must restore its captured state")
    c.require_link(hud_state, "CleanFrameRestoreHUDCategoryV1", hud_restore, "Enable", "HUD must restore its captured state")
    c.require_link(popup_restore, "then", hud_restore, "execute", "Native category restoration must be ordered")
    select_matches = [node for node in nodes.values() if node.node_class.endswith("K2Node_Select")]
    c.require(len(select_matches) == 1, f"Expected one HUD visibility select; found {len(select_matches)}")
    select = select_matches[0]
    c.require_pin_default(select, "Option 0", "Hidden", "False HUD state must remain hidden")
    c.require_pin_default(select, "Option 1", "SelfHitTestInvisible", "True HUD state must restore")
    c.require_link(hud_state, "CleanFrameRestoreHUDCategoryV1", select, "Index", "Notification visibility must follow captured HUD state")
    shown = one(c, nodes, r'MemberName="SetActorHiddenInGame"', "preview restore")
    c.require_pin_default(shown, "bNewHidden", "false", "Preview actor must restore")
    c.require_link(shown, "then", clear_active, "execute", "Active flag clears after preview restoration")
    c.require_pin_default(clear_active, "CleanFrameActiveV1", "false", "Exit must commit active=false")
    disabled_log = one(c, nodes, r'\[EDD\] Clean Frame disabled', "disabled log")
    c.require_link(clear_active, "then", disabled_log, "execute", "Success log must follow restoration")
    ignored_log = one(c, nodes, r'already disabled', "idempotent exit log")
    c.require_link(guard, "else", ignored_log, "execute", "Repeated exit must not overwrite state")
    if full:
        entry = one(c, nodes, r'FunctionReference=\(MemberName="ExitCleanFrameV1"\)', "entry")
        c.require_link(entry, "then", guard, "execute", "Entry must reach the active guard")
    else:
        c.require(not guard.pins["execute"].links, "Paste body must expose the guard entry")


def assert_toggle(c, nodes, full: bool) -> None:
    assert_closed(c, nodes, 5 if full else 4, "ToggleCleanFrameV1" if full else None)
    active = variable(c, nodes, "CleanFrameActiveV1", False)
    branch = c.linked_target(nodes, active, "CleanFrameActiveV1", "Condition", "K2Node_IfThenElse")
    exit_call = one(c, nodes, r'MemberName="ExitCleanFrameV1"', "exit call")
    enter_call = one(c, nodes, r'MemberName="EnterCleanFrameV1"', "enter call")
    c.require_link(branch, "then", exit_call, "execute", "Active toggle must exit")
    c.require_link(branch, "else", enter_call, "execute", "Inactive toggle must enter")
    if full:
        entry = one(c, nodes, r'FunctionReference=\(MemberName="ToggleCleanFrameV1"\)', "entry")
        c.require_link(entry, "then", branch, "execute", "Entry must reach toggle branch")
    else:
        c.require(not branch.pins["execute"].links, "Paste body must expose the branch entry")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--enter", type=Path, required=True)
    parser.add_argument("--exit", type=Path, required=True)
    parser.add_argument("--toggle", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_helpers(args.project_root)
    assert_enter(c, c.parse(args.enter), not args.paste)
    assert_exit(c, c.parse(args.exit), not args.paste)
    assert_toggle(c, c.parse(args.toggle), not args.paste)
    print("Clean Frame graph contracts passed")


if __name__ == "__main__":
    main()
