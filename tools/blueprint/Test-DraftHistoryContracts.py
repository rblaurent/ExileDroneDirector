"""Semantic contracts for bounded draft-history Blueprint graphs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-PathPreviewContracts.py"
    spec = importlib.util.spec_from_file_location("edd_history_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nodes_matching(nodes, node_class: str, marker: str):
    return [
        node for node in nodes.values()
        if node_class in node.node_class and marker in node.text
    ]


def one_variable(c, nodes, name: str):
    matches = nodes_matching(nodes, "K2Node_VariableGet", f'MemberName="{name}"')
    c.require(len(matches) == 1, f"Expected one {name} getter; found {len(matches)}")
    return matches[0]


def one_call(c, nodes, name: str):
    matches = [
        node for node in nodes.values()
        if "K2Node_Call" in node.node_class and f'MemberName="{name}"' in node.text
    ]
    c.require(len(matches) == 1, f"Expected one {name} call; found {len(matches)}")
    return matches[0]


def require_closed(c, nodes, expected: int, entry_name: str | None):
    c.require(len(nodes) == expected, f"Expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    unknown = sorted({
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _ in pin.links
        if target not in known
    })
    c.require(not unknown, f"External graph links are forbidden: {unknown}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (1 if entry_name else 0), "Function entry inclusion changed")
    if entry_name:
        c.require(f'MemberName="{entry_name}"' in entries[0].text, "Wrong function entry")


def pin_line(node, pin_name: str) -> str:
    pin_id = node.pins[pin_name].pin_id
    return next(line for line in node.text.splitlines() if f"PinId={pin_id}" in line)


def require_array_type(c, node, pin_name: str, kind: str):
    line = pin_line(node, pin_name)
    c.require("PinType.ContainerType=Array" in line, f"{node.name}.{pin_name} must be an array")
    if kind == "document":
        c.require('PinType.PinCategory="struct"' in line, f"{node.name}.{pin_name} must be a struct array")
        c.require("ST_EDD_FlypathDocument" in line, f"{node.name}.{pin_name} must use the document struct")
    else:
        c.require('PinType.PinCategory="int"' in line, f"{node.name}.{pin_name} must be an int array")


def assert_push(c, nodes, prefix: str, *, has_entry: bool):
    require_closed(c, nodes, 17 if has_entry else 16, f"PushCurrentTo{prefix}V1" if has_entry else None)
    documents = one_variable(c, nodes, f"{prefix}DocumentsV1")
    selections = one_variable(c, nodes, f"{prefix}SelectionsV1")
    next_ids = one_variable(c, nodes, f"{prefix}NextWaypointIdsV1")
    current_document = one_variable(c, nodes, "DraftDocumentV1")
    current_selection = one_variable(c, nodes, "SelectedWaypointIndex")
    current_next = one_variable(c, nodes, "NextWaypointId")
    limit = one_variable(c, nodes, "HistoryLimitV1")
    adds = nodes_matching(nodes, "K2Node_CallArrayFunction", 'MemberName="Array_Add"')
    removes = nodes_matching(nodes, "K2Node_CallArrayFunction", 'MemberName="Array_Remove"')
    c.require(len(adds) == 3, f"{prefix} push must append three synchronized values")
    c.require(len(removes) == 3, f"{prefix} push must trim three synchronized values")
    length = one_call(c, nodes, "Array_Length")
    greater = one_call(c, nodes, "Greater_IntInt")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 1, "Push must have one cap branch")
    branch = branches[0]

    document_add = c.linked_target(nodes, documents, f"{prefix}DocumentsV1", "TargetArray", 'MemberName="Array_Add"')
    selection_add = c.linked_target(nodes, selections, f"{prefix}SelectionsV1", "TargetArray", 'MemberName="Array_Add"')
    next_add = c.linked_target(nodes, next_ids, f"{prefix}NextWaypointIdsV1", "TargetArray", 'MemberName="Array_Add"')
    c.require_link(current_document, "DraftDocumentV1", document_add, "NewItem", "Snapshot must capture the full draft document")
    c.require_link(current_selection, "SelectedWaypointIndex", selection_add, "NewItem", "Snapshot must capture selection")
    c.require_link(current_next, "NextWaypointId", next_add, "NewItem", "Snapshot must capture next stable ID")
    c.require_link(document_add, "then", selection_add, "execute", "Document append must precede selection append")
    c.require_link(selection_add, "then", next_add, "execute", "Selection append must precede next-ID append")
    if has_entry:
        entry = c.one(nodes, f'FunctionReference=(MemberName="PushCurrentTo{prefix}V1")')
        c.require_link(entry, "then", document_add, "execute", "Native entry must reach the first append")
    else:
        c.require(not document_add.pins["execute"].links, "Paste body must expose exactly the first append")

    c.require_link(documents, f"{prefix}DocumentsV1", length, "TargetArray", "Cap must use post-append document count")
    c.require_link(next_add, "then", branch, "execute", "Cap check must execute after all appends")
    c.require_link(length, "ReturnValue", greater, "A", "Post-append count must drive cap comparison")
    c.require_link(limit, "HistoryLimitV1", greater, "B", "Configured limit must drive cap comparison")
    c.require_link(greater, "ReturnValue", branch, "Condition", "Only overflow may trim")

    document_remove = c.linked_target(nodes, documents, f"{prefix}DocumentsV1", "TargetArray", 'MemberName="Array_Remove"')
    selection_remove = c.linked_target(nodes, selections, f"{prefix}SelectionsV1", "TargetArray", 'MemberName="Array_Remove"')
    next_remove = c.linked_target(nodes, next_ids, f"{prefix}NextWaypointIdsV1", "TargetArray", 'MemberName="Array_Remove"')
    c.require_link(branch, "then", document_remove, "execute", "Overflow must trim the oldest document")
    c.require_link(document_remove, "then", selection_remove, "execute", "Trim arrays must remain in lockstep")
    c.require_link(selection_remove, "then", next_remove, "execute", "Trim arrays must remain in lockstep")
    c.require(not branch.pins["else"].links, "Non-overflow path must stop without removal")
    for remove in removes:
        c.require('DefaultValue="0"' in pin_line(remove, "IndexToRemove"), "History trimming must remove oldest index 0")
    require_array_type(c, documents, f"{prefix}DocumentsV1", "document")
    require_array_type(c, selections, f"{prefix}SelectionsV1", "int")
    require_array_type(c, next_ids, f"{prefix}NextWaypointIdsV1", "int")


def assert_record(c, nodes, *, has_entry: bool):
    require_closed(c, nodes, 8 if has_entry else 7, "RecordUndoSnapshotV1" if has_entry else None)
    push = one_call(c, nodes, "PushCurrentToUndoV1")
    documents = one_variable(c, nodes, "RedoDocumentsV1")
    selections = one_variable(c, nodes, "RedoSelectionsV1")
    next_ids = one_variable(c, nodes, "RedoNextWaypointIdsV1")
    clears = nodes_matching(nodes, "K2Node_CallArrayFunction", 'MemberName="Array_Clear"')
    c.require(len(clears) == 3, "Recording a new edit must clear all three redo arrays")
    document_clear = c.linked_target(nodes, documents, "RedoDocumentsV1", "TargetArray", 'MemberName="Array_Clear"')
    selection_clear = c.linked_target(nodes, selections, "RedoSelectionsV1", "TargetArray", 'MemberName="Array_Clear"')
    next_clear = c.linked_target(nodes, next_ids, "RedoNextWaypointIdsV1", "TargetArray", 'MemberName="Array_Clear"')
    if has_entry:
        entry = c.one(nodes, 'FunctionReference=(MemberName="RecordUndoSnapshotV1")')
        c.require_link(entry, "then", push, "execute", "Recording must first push current state to undo")
    else:
        c.require(not push.pins["execute"].links, "Paste body must expose the push call")
    c.require_link(push, "then", document_clear, "execute", "Redo invalidation must follow the undo snapshot")
    c.require_link(document_clear, "then", selection_clear, "execute", "Redo arrays must clear in lockstep")
    c.require_link(selection_clear, "then", next_clear, "execute", "Redo arrays must clear in lockstep")
    require_array_type(c, documents, "RedoDocumentsV1", "document")
    require_array_type(c, selections, "RedoSelectionsV1", "int")
    require_array_type(c, next_ids, "RedoNextWaypointIdsV1", "int")


def assert_pop(c, nodes, source: str, opposite: str, entry_name: str, *, has_entry: bool):
    require_closed(c, nodes, 19 if has_entry else 18, entry_name if has_entry else None)
    documents = one_variable(c, nodes, f"{source}DocumentsV1")
    selections = one_variable(c, nodes, f"{source}SelectionsV1")
    next_ids = one_variable(c, nodes, f"{source}NextWaypointIdsV1")
    length = one_call(c, nodes, "Array_Length")
    greater = one_call(c, nodes, "Greater_IntInt")
    subtract = c.one(nodes, 'MemberName="Subtract_IntInt"')
    branch = c.linked_target(nodes, greater, "ReturnValue", "Condition", "K2Node_IfThenElse")
    getters = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    c.require(len(getters) == 3, "Pop must read all three snapshot values")
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    c.require(len(setters) == 3, "Pop must stage all three snapshot values")
    removes = nodes_matching(nodes, "K2Node_CallArrayFunction", 'MemberName="Array_Remove"')
    c.require(len(removes) == 3, "Pop must remove all three synchronized values")
    push = one_call(c, nodes, f"PushCurrentTo{opposite}V1")
    apply_call = one_call(c, nodes, "ApplyHistorySnapshotV1")

    c.require_link(documents, f"{source}DocumentsV1", length, "TargetArray", "Primary stack count must guard pop")
    c.require_link(length, "ReturnValue", greater, "A", "Stack count must drive non-empty test")
    c.require('DefaultValue="0"' in pin_line(greater, "B"), "Pop guard must require count > 0")
    c.require_link(greater, "ReturnValue", branch, "Condition", "Non-empty result must guard mutation")
    c.require(not branch.pins["else"].links, "Empty history must be a strict no-op")
    c.require_link(length, "ReturnValue", subtract, "A", "Last index must derive from primary stack count")
    c.require('DefaultValue="1"' in pin_line(subtract, "B"), "Last index must be count - 1")

    document_get = c.linked_target(nodes, documents, f"{source}DocumentsV1", "Array", "K2Node_GetArrayItem")
    selection_get = c.linked_target(nodes, selections, f"{source}SelectionsV1", "Array", "K2Node_GetArrayItem")
    next_get = c.linked_target(nodes, next_ids, f"{source}NextWaypointIdsV1", "Array", "K2Node_GetArrayItem")
    stage_document = c.linked_target(nodes, document_get, "Output", "HistoryRestoreDocumentV1", "K2Node_VariableSet")
    stage_selection = c.linked_target(nodes, selection_get, "Output", "HistoryRestoreSelectionV1", "K2Node_VariableSet")
    stage_next = c.linked_target(nodes, next_get, "Output", "HistoryRestoreNextWaypointIdV1", "K2Node_VariableSet")
    for array_get in getters:
        c.require_link(subtract, "ReturnValue", array_get, "Dimension 1", "Every snapshot channel must read the same last index")
    c.require_link(branch, "then", stage_document, "execute", "Valid pop must stage document first")
    c.require_link(stage_document, "then", stage_selection, "execute", "Snapshot staging must remain ordered")
    c.require_link(stage_selection, "then", stage_next, "execute", "Snapshot staging must remain ordered")
    c.require_link(stage_next, "then", push, "execute", "Current state must be preserved after staging source")

    document_remove = c.linked_target(nodes, documents, f"{source}DocumentsV1", "TargetArray", 'MemberName="Array_Remove"')
    selection_remove = c.linked_target(nodes, selections, f"{source}SelectionsV1", "TargetArray", 'MemberName="Array_Remove"')
    next_remove = c.linked_target(nodes, next_ids, f"{source}NextWaypointIdsV1", "TargetArray", 'MemberName="Array_Remove"')
    c.require_link(push, "then", document_remove, "execute", "Opposite snapshot must precede source removal")
    c.require_link(document_remove, "then", selection_remove, "execute", "Source arrays must pop in lockstep")
    c.require_link(selection_remove, "then", next_remove, "execute", "Source arrays must pop in lockstep")
    c.require_link(next_remove, "then", apply_call, "execute", "Restore must occur only after the full source pop")
    for remove in removes:
        c.require_link(subtract, "ReturnValue", remove, "IndexToRemove", "Every source channel must remove the same last index")
    if has_entry:
        entry = c.one(nodes, f'FunctionReference=(MemberName="{entry_name}")')
        c.require_link(entry, "then", branch, "execute", "Native entry must reach the non-empty guard")
    else:
        c.require(not branch.pins["execute"].links, "Paste body must expose the non-empty guard")
    require_array_type(c, documents, f"{source}DocumentsV1", "document")
    require_array_type(c, selections, f"{source}SelectionsV1", "int")
    require_array_type(c, next_ids, f"{source}NextWaypointIdsV1", "int")


def pin_starting(c, node, prefix: str) -> str:
    matches = [name for name in node.pins if name.startswith(prefix)]
    c.require(len(matches) == 1, f"Expected one {node.name} pin starting {prefix!r}; found {matches}")
    return matches[0]


def assert_apply(c, nodes, *, has_entry: bool):
    require_closed(c, nodes, 31 if has_entry else 30, "ApplyHistorySnapshotV1" if has_entry else None)
    document = one_variable(c, nodes, "HistoryRestoreDocumentV1")
    break_document = c.one(nodes, 'StructType="/Script/CoreUObject.UserDefinedStruct\'/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument')
    break_waypoint = c.one(nodes, 'StructType="/Script/CoreUObject.UserDefinedStruct\'/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Waypoint')
    loop = c.one(nodes, "StandardMacros:ForEachLoop")
    clears = nodes_matching(nodes, "K2Node_CallArrayFunction", 'MemberName="Array_Clear"')
    adds = nodes_matching(nodes, "K2Node_CallArrayFunction", 'MemberName="Array_Add"')
    c.require(len(clears) == 6, "Restore must clear all six legacy channels")
    c.require(len(adds) == 6, "Restore must repopulate all six legacy channels")
    legacy = (
        ("DraftWaypointIds", "WaypointId_"),
        ("DraftWaypointTransforms", "CameraTransform_"),
        ("DraftWaypointFocalLengths", "FocalLength_"),
        ("DraftWaypointApertures", "Aperture_"),
        ("DraftWaypointFocusDistances", "ManualFocusDistance_"),
        ("DraftWaypointHoldSeconds", "HoldSeconds_"),
    )
    getters = [one_variable(c, nodes, member) for member, _ in legacy]
    ordered_clears = []
    ordered_adds = []
    for getter, (member, field_prefix) in zip(getters, legacy):
        clear = c.linked_target(nodes, getter, member, "TargetArray", 'MemberName="Array_Clear"')
        add = c.linked_target(nodes, getter, member, "TargetArray", 'MemberName="Array_Add"')
        c.require_link(break_waypoint, pin_starting(c, break_waypoint, field_prefix), add, "NewItem", f"{member} must restore from {field_prefix}")
        ordered_clears.append(clear)
        ordered_adds.append(add)

    if has_entry:
        entry = c.one(nodes, 'FunctionReference=(MemberName="ApplyHistorySnapshotV1")')
        c.require_link(entry, "then", ordered_clears[0], "execute", "Restore entry must clear legacy IDs first")
    else:
        c.require(not ordered_clears[0].pins["execute"].links, "Paste body must expose the first clear")
    for left, right in zip(ordered_clears, ordered_clears[1:]):
        c.require_link(left, "then", right, "execute", "Legacy clears must remain ordered")
    c.require_link(ordered_clears[-1], "then", loop, "Exec", "Waypoint projection must start only after all clears")
    c.require_link(loop, "LoopBody", ordered_adds[0], "execute", "Each waypoint must start one six-channel append")
    for left, right in zip(ordered_adds, ordered_adds[1:]):
        c.require_link(left, "then", right, "execute", "Legacy appends must remain atomic and ordered")

    waypoints_pin = pin_starting(c, break_document, "Waypoints_")
    segments_pin = pin_starting(c, break_document, "Segments_")
    c.require_link(document, "HistoryRestoreDocumentV1", break_document, "ST_EDD_FlypathDocument", "Staged document must drive typed projection")
    c.require_link(break_document, waypoints_pin, loop, "Array", "Restore loop must use staged typed waypoints")
    c.require_link(loop, "Array Element", break_waypoint, "ST_EDD_Waypoint", "Each typed waypoint must drive its native break")

    waypoint_sets = nodes_matching(nodes, "K2Node_VariableSet", 'MemberName="DraftWaypointsV1"')
    segment_sets = nodes_matching(nodes, "K2Node_VariableSet", 'MemberName="DraftSegmentsV1"')
    document_sets = nodes_matching(nodes, "K2Node_VariableSet", 'MemberName="DraftDocumentV1"')
    selected_sets = nodes_matching(nodes, "K2Node_VariableSet", 'MemberName="SelectedWaypointIndex"')
    next_sets = nodes_matching(nodes, "K2Node_VariableSet", 'MemberName="NextWaypointId"')
    for matches, label in ((waypoint_sets,"DraftWaypointsV1"),(segment_sets,"DraftSegmentsV1"),(document_sets,"DraftDocumentV1"),(selected_sets,"SelectedWaypointIndex"),(next_sets,"NextWaypointId")):
        c.require(len(matches) == 1, f"Restore must set {label} exactly once")
    typed_waypoints, typed_segments, typed_document = waypoint_sets[0], segment_sets[0], document_sets[0]
    set_selected, set_next = selected_sets[0], next_sets[0]
    selected = one_variable(c, nodes, "HistoryRestoreSelectionV1")
    next_id = one_variable(c, nodes, "HistoryRestoreNextWaypointIdV1")
    refresh = one_call(c, nodes, "RefreshPathPreviewV1")
    c.require_link(loop, "Completed", typed_waypoints, "execute", "Typed state commit must wait for legacy projection completion")
    c.require_link(break_document, waypoints_pin, typed_waypoints, "DraftWaypointsV1", "Typed waypoint array must restore exactly")
    c.require_link(typed_waypoints, "then", typed_segments, "execute", "Typed commits must remain ordered")
    c.require_link(break_document, segments_pin, typed_segments, "DraftSegmentsV1", "Authored segments must restore exactly")
    c.require_link(typed_segments, "then", typed_document, "execute", "Full document commit must follow typed arrays")
    c.require_link(document, "HistoryRestoreDocumentV1", typed_document, "DraftDocumentV1", "Full staged document must restore exactly")
    c.require_link(typed_document, "then", set_selected, "execute", "Selection restore must follow document commit")
    c.require_link(selected, "HistoryRestoreSelectionV1", set_selected, "SelectedWaypointIndex", "Selection must restore exactly")
    c.require_link(set_selected, "then", set_next, "execute", "Next-ID restore must follow selection")
    c.require_link(next_id, "HistoryRestoreNextWaypointIdV1", set_next, "NextWaypointId", "Next stable ID must restore exactly")
    c.require_link(set_next, "then", refresh, "execute", "Preview must refresh only after complete state restoration")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_helpers(args.project_root)
    suffix = "-paste" if args.paste else ""
    assert_push(c, c.parse(args.input_dir / f"push-current-to-undo-v1{suffix}.eddgraph"), "Undo", has_entry=not args.paste)
    assert_push(c, c.parse(args.input_dir / f"push-current-to-redo-v1{suffix}.eddgraph"), "Redo", has_entry=not args.paste)
    assert_record(c, c.parse(args.input_dir / f"record-undo-snapshot-v1{suffix}.eddgraph"), has_entry=not args.paste)
    assert_pop(c, c.parse(args.input_dir / f"undo-draft-v1{suffix}.eddgraph"), "Undo", "Redo", "UndoDraftV1", has_entry=not args.paste)
    assert_pop(c, c.parse(args.input_dir / f"redo-draft-v1{suffix}.eddgraph"), "Redo", "Undo", "RedoDraftV1", has_entry=not args.paste)
    assert_apply(c, c.parse(args.input_dir / f"apply-history-snapshot-v1{suffix}.eddgraph"), has_entry=not args.paste)
    print("Draft history lifecycle graph contracts passed")


if __name__ == "__main__":
    main()
