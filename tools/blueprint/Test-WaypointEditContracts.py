"""Semantic contracts for selected-waypoint replacement and deletion graphs."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load_contract_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_capture_contracts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_replace(c, nodes) -> None:
    c.require(len(nodes) in {21, 22}, f"ReplaceSelectedWaypoint expected 21 or 22 nodes; found {len(nodes)}")
    entries = [node for node in nodes.values() if 'FunctionReference=(MemberName="ReplaceSelectedWaypoint")' in node.text]
    c.require(len(entries) <= 1, "Replace may contain at most one function entry")
    camera = c.one(nodes, 'VariableReference=(MemberName="DroneCameraRef"')
    valid_object = c.one(nodes, 'MemberName="IsValid"')
    ids = c.one(nodes, 'VariableReference=(MemberName="DraftWaypointIds"')
    selected_matches = [
        node for node in nodes.values()
        if 'MemberName="SelectedWaypointIndex",MemberGuid=23B9561944904F583A9AAE8770F8810B'
        in node.text
    ]
    c.require(len(selected_matches) == 1, "Replace must have exactly one selected-index getter")
    selected = selected_matches[0]
    valid_index = c.one(nodes, 'MemberName="Array_IsValidIndex"')
    branches = [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]
    c.require(len(branches) == 2, "Replace must guard camera and selected index separately")
    camera_branch = next(
        node for node in branches if c.linked(valid_object, "ReturnValue", node, "Condition")
    )
    index_branch = next(
        node for node in branches if c.linked(valid_index, "ReturnValue", node, "Condition")
    )
    if entries:
        c.require_link(entries[0], "then", camera_branch, "execute", "Replace entry must validate camera")
    else:
        c.require(not c.pin(camera_branch, "execute").links, "Replace paste entry pin must be intentionally unwired")
    c.require_link(camera, "DroneCameraRef", valid_object, "Object", "Replace must validate DroneCameraRef")
    c.require_link(camera_branch, "then", index_branch, "execute", "Index validation must follow camera validation")
    c.require_link(ids, "DraftWaypointIds", valid_index, "TargetArray", "Stable-ID array must define valid indices")
    c.require_link(selected, "SelectedWaypointIndex", valid_index, "IndexToTest", "Selected index must be range-checked")

    setters = sorted(
        [node for node in nodes.values() if 'MemberName="Array_Set"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    c.require(len(setters) == 4, f"Replace must update exactly four pose/lens channels; found {len(setters)}")
    channels = (
        ("DraftWaypointTransforms", "struct", "", c.one(nodes, 'MemberName="GetTransform"'), "ReturnValue"),
        ("DraftWaypointFocalLengths", "real", "double", c.one(nodes, 'MemberName="FocalLength",MemberGuid='), "FocalLength"),
        ("DraftWaypointApertures", "real", "double", c.one(nodes, 'MemberName="Aperture",MemberGuid='), "Aperture"),
        ("DraftWaypointFocusDistances", "real", "double", c.one(nodes, 'MemberName="ManualFocusDistance",MemberGuid='), "ManualFocusDistance"),
    )
    sync = c.one(nodes, 'MemberName="SyncDraftWaypointsV1"')
    exec_chain = [index_branch, *setters, sync, c.one(nodes, 'MemberName="PrintString"')]
    for before, after in zip(exec_chain, exec_chain[1:]):
        c.require_link(before, "then", after, "execute", "Replace mutation chain must be ordered and atomic")
    for (variable, category, subcategory, source, source_pin), setter in zip(channels, setters):
        getter = c.one(nodes, f'VariableReference=(MemberName="{variable}"')
        c.require_link(getter, variable, setter, "TargetArray", f"{variable} must feed its Array_Set")
        c.require_link(selected, "SelectedWaypointIndex", setter, "Index", f"{variable} must update the selected index")
        c.require_link(source, source_pin, setter, "Item", f"{variable} must snapshot the exact live value")
        for pin_name in ("TargetArray", "Item"):
            body = c.pin(setter, pin_name).body
            c.require(f'PinType.PinCategory="{category}"' in body, f"{variable} setter type changed")
            if subcategory:
                c.require(f'PinType.PinSubCategory="{subcategory}"' in body, f"{variable} precision changed")
        c.require('DefaultValue="false"' in c.pin(setter, "bSizeToFit").body, "Replace must never grow arrays")
    for marker in ('MemberName="DraftWaypointHoldSeconds"', 'MemberName="NextWaypointId"'):
        c.require(not any(marker in node.text for node in nodes.values()), f"Replace must preserve {marker}")
    c.require(not any('MemberName="Array_Remove"' in node.text for node in nodes.values()), "Replace must not remove elements")


def assert_delete(c, nodes) -> None:
    c.require(len(nodes) in {22, 23}, f"DeleteSelectedWaypoint expected 22 or 23 nodes; found {len(nodes)}")
    entries = [node for node in nodes.values() if 'FunctionReference=(MemberName="DeleteSelectedWaypoint")' in node.text]
    c.require(len(entries) <= 1, "Delete may contain at most one function entry")
    selected_nodes = [
        node for node in nodes.values()
        if 'MemberName="SelectedWaypointIndex",MemberGuid=23B9561944904F583A9AAE8770F8810B'
        in node.text
    ]
    c.require(len(selected_nodes) == 2, "Delete must have one selected-index getter and one setter")
    selected = c.one({n.name: n for n in selected_nodes}, "K2Node_VariableGet")
    selected_set = c.one({n.name: n for n in selected_nodes}, "K2Node_VariableSet")
    ids = c.one(nodes, 'VariableReference=(MemberName="DraftWaypointIds"')
    valid_nodes = [node for node in nodes.values() if 'MemberName="Array_IsValidIndex"' in node.text]
    branches = [node for node in nodes.values() if node.node_class.endswith("K2Node_IfThenElse")]
    c.require(len(valid_nodes) == 2 and len(branches) == 2, "Delete requires pre/post index validation")
    after_branch = next(
        branch
        for branch in branches
        if c.linked(branch, "else", selected_set, "execute")
    )
    before_branch = next(branch for branch in branches if branch is not after_branch)
    before_valid = next(
        node for node in valid_nodes if c.linked(node, "ReturnValue", before_branch, "Condition")
    )
    after_valid = next(
        node for node in valid_nodes if c.linked(node, "ReturnValue", after_branch, "Condition")
    )
    if entries:
        c.require_link(entries[0], "then", before_branch, "execute", "Delete entry must reach pre-validation")
    else:
        c.require(not c.pin(before_branch, "execute").links, "Delete paste entry pin must be intentionally unwired")
    c.require_link(ids, "DraftWaypointIds", before_valid, "TargetArray", "Delete must validate against stable IDs")
    c.require_link(selected, "SelectedWaypointIndex", before_valid, "IndexToTest", "Delete must validate the selected index")

    removes = sorted(
        [node for node in nodes.values() if 'MemberName="Array_Remove"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    c.require(len(removes) == 6, f"Delete must remove all six lockstep channels; found {len(removes)}")
    channels = (
        ("DraftWaypointIds", "int", ""),
        ("DraftWaypointTransforms", "struct", ""),
        ("DraftWaypointFocalLengths", "real", "double"),
        ("DraftWaypointApertures", "real", "double"),
        ("DraftWaypointFocusDistances", "real", "double"),
        ("DraftWaypointHoldSeconds", "real", "double"),
    )
    exec_chain = [before_branch, *removes, after_branch]
    for before, after in zip(exec_chain, exec_chain[1:]):
        c.require_link(before, "then", after, "execute", "Delete must remove every channel in one ordered chain")
    for (variable, category, subcategory), remove in zip(channels, removes):
        getter = c.one(nodes, f'VariableReference=(MemberName="{variable}"')
        c.require_link(getter, variable, remove, "TargetArray", f"{variable} must feed its Remove Index")
        c.require_link(selected, "SelectedWaypointIndex", remove, "IndexToRemove", f"{variable} must remove the selected index")
        target = c.pin(remove, "TargetArray").body
        c.require(f'PinType.PinCategory="{category}"' in target, f"{variable} remove type changed")
        if subcategory:
            c.require(f'PinType.PinSubCategory="{subcategory}"' in target, f"{variable} precision changed")

    c.require_link(ids, "DraftWaypointIds", after_valid, "TargetArray", "Delete must test whether the old index survived")
    c.require_link(selected, "SelectedWaypointIndex", after_valid, "IndexToTest", "Post-delete validation must test the old index")
    sync_nodes = [node for node in nodes.values() if 'MemberName="SyncDraftWaypointsV1"' in node.text]
    c.require(len(sync_nodes) == 2, "Delete needs one sync call for each successful selection-repair path")
    sync_keep = next(node for node in sync_nodes if c.linked(after_branch, "then", node, "execute"))
    c.require_link(after_branch, "then", sync_keep, "execute", "A surviving selected index must sync directly")
    c.require_link(after_branch, "else", selected_set, "execute", "Only an invalidated index may be repaired")
    length = c.one(nodes, 'MemberName="Array_Length"')
    subtract = c.one(nodes, 'MemberName="Subtract_IntInt"')
    c.require_link(ids, "DraftWaypointIds", length, "TargetArray", "Selection repair must use remaining ID count")
    c.require_link(length, "ReturnValue", subtract, "A", "Selection repair must start from array length")
    c.require('DefaultValue="1"' in c.pin(subtract, "B").body, "Selection repair must compute Length - 1")
    c.require_link(subtract, "ReturnValue", selected_set, "SelectedWaypointIndex", "Length - 1 must become the repaired selection")
    sync_repair = next(node for node in sync_nodes if node is not sync_keep)
    c.require_link(selected_set, "then", sync_repair, "execute", "A repaired selection must sync after the setter")
    c.require(not any('MemberName="Array_Set"' in node.text for node in nodes.values()), "Delete must not overwrite elements")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--replace", type=Path, required=True)
    parser.add_argument("--delete", type=Path, required=True)
    args = parser.parse_args()
    c = load_contract_helpers(args.project_root)
    assert_replace(c, c.parse_graph(args.replace))
    assert_delete(c, c.parse_graph(args.delete))
    print("Waypoint edit contracts valid: guarded replacement and six-channel atomic deletion")


if __name__ == "__main__":
    main()
