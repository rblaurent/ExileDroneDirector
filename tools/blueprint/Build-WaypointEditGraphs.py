"""Build reviewed Blueprint graphs for selected-waypoint replacement and deletion.

Both functions operate on the client-local six-channel draft. Replacement
updates only transform and lens channels, preserving stable ID and hold time.
Deletion removes one index from every channel before repairing selection.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
)
SELECTED_INDEX_GUID = "23B9561944904F583A9AAE8770F8810B"
ENTRY_PIN_IDS = {
    "ReplaceSelectedWaypoint": "111F89B1473FE6CA0E8F79BAD3C77596",
    "DeleteSelectedWaypoint": "CA70052643B7E8D2362F3DAD07B8A2F5",
}


def load_capture_builder(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_capture_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load shared graph builder: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def set_array_element_type(node, pin_names: tuple[str, ...], kind: str) -> None:
    def mutate(line: str) -> str:
        line = line.replace('PinType.PinCategory="wildcard"', f'PinType.PinCategory="{kind}"', 1)
        if kind == "real":
            line = line.replace('PinType.PinSubCategory=""', 'PinType.PinSubCategory="double"', 1)
        elif kind == "struct":
            line = line.replace(
                "PinType.PinSubCategoryObject=None",
                "PinType.PinSubCategoryObject=\"/Script/CoreUObject.ScriptStruct'"
                "/Script/CoreUObject.Transform'\"",
                1,
            )
        return line

    if kind not in {"int", "real", "struct"}:
        raise RuntimeError(f"Unsupported array element kind: {kind}")
    for pin_name in pin_names:
        node.mutate_pin(pin_name, mutate)


def retarget_entry(node, function_name: str) -> None:
    node.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{function_name}")',
        node.text,
        count=1,
    )
    old_pin_id = node.pins["then"]
    new_pin_id = ENTRY_PIN_IDS[function_name]
    node.text = node.text.replace(f"PinId={old_pin_id}", f"PinId={new_pin_id}", 1)
    node.pins["then"] = new_pin_id


def make_templates(bp, project_root: Path) -> dict[str, str]:
    blueprint_root = project_root / "tools" / "blueprint"
    capture = bp.read_blocks(
        blueprint_root / "templates" / "waypoint-capture-node-forms.eddgraph"
    )
    edit = bp.read_blocks(
        blueprint_root / "templates" / "waypoint-edit-node-forms.eddgraph"
    )
    enter = bp.read_blocks(blueprint_root / "snippets" / "enter-drone-mode.eddgraph")
    event = bp.read_blocks(
        blueprint_root / "snippets" / "client-director-event-graph.eddgraph"
    )
    return {
        "entry": bp.find_block(capture, r"K2Node_FunctionEntry"),
        "ids": bp.find_block(capture, r'MemberName="DraftWaypointIds"'),
        "transforms": bp.find_block(capture, r'MemberName="DraftWaypointTransforms"'),
        "focals": bp.find_block(capture, r'MemberName="DraftWaypointFocalLengths"'),
        "apertures": bp.find_block(capture, r'MemberName="DraftWaypointApertures"'),
        "focuses": bp.find_block(capture, r'MemberName="DraftWaypointFocusDistances"'),
        "holds": bp.find_block(capture, r'MemberName="DraftWaypointHoldSeconds"'),
        "selected_get": bp.find_block(
            capture, r'K2Node_VariableGet.*?MemberName="NextWaypointId"'
        ),
        "selected_set": bp.find_block(
            capture, r'K2Node_VariableSet.*?MemberName="NextWaypointId"'
        ),
        "drone": bp.find_block(capture, r'MemberName="DroneCameraRef"'),
        "focal": bp.find_block(capture, r'MemberName="FocalLength"'),
        "aperture": bp.find_block(capture, r'MemberName="Aperture"'),
        "focus": bp.find_block(capture, r'MemberName="ManualFocusDistance"'),
        "transform": bp.find_block(capture, r'MemberName="GetTransform"'),
        "int_add": bp.find_block(capture, r'OperationName="Add".*?Add_IntInt'),
        "set_array": bp.find_block(edit, r'MemberName="Array_Set"'),
        "remove_index": bp.find_block(edit, r'MemberName="Array_Remove"'),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "valid_index": bp.find_block(edit, r'MemberName="Array_IsValidIndex"'),
        "valid_object": bp.find_block(enter, r'MemberName="IsValid"'),
        "branch": bp.find_block(
            enter, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse\b"
        ),
        "print": bp.find_block(enter, r'MemberName="PrintString"'),
        "sync": bp.find_block(event, r'MemberName="StopLinearPlayback"'),
    }


def build_replace(bp, templates: dict[str, str]):
    graph = "ReplaceSelectedWaypoint"
    bp.TARGET_GRAPH = graph
    nodes = {}

    def add(key: str, template: str, name: str, x: int, y: int):
        node = bp.Node.clone(key, templates[template], name, x, y)
        nodes[key] = node
        return node

    entry = add("entry", "entry", "K2Node_FunctionEntry_0", 0, 0)
    retarget_entry(entry, graph)
    camera_branch = add("camera_branch", "branch", "K2Node_IfThenElse_0", 256, 0)
    drone = add("drone", "drone", "K2Node_VariableGet_0", 0, 224)
    valid_object = add("valid_object", "valid_object", "K2Node_CallFunction_0", 256, 224)

    ids = add("ids", "ids", "K2Node_VariableGet_1", 416, 304)
    selected = add("selected", "selected_get", "K2Node_VariableGet_2", 416, 400)
    bp.retarget_variable(
        selected, "NextWaypointId", "SelectedWaypointIndex", SELECTED_INDEX_GUID
    )
    valid_index = add("valid_index", "valid_index", "K2Node_CallArrayFunction_0", 672, 304)
    set_array_element_type(valid_index, ("TargetArray",), "int")
    index_branch = add("index_branch", "branch", "K2Node_IfThenElse_1", 928, 0)

    transforms = add("transforms", "transforms", "K2Node_VariableGet_3", 928, 304)
    transform = add("transform", "transform", "K2Node_CallFunction_1", 928, 400)
    set_transform = add("set_transform", "set_array", "K2Node_CallArrayFunction_1", 1216, 0)
    set_array_element_type(set_transform, ("TargetArray", "Item"), "struct")

    focals = add("focals", "focals", "K2Node_VariableGet_4", 1376, 304)
    focal = add("focal", "focal", "K2Node_VariableGet_5", 1376, 400)
    set_focal = add("set_focal", "set_array", "K2Node_CallArrayFunction_2", 1664, 0)
    set_array_element_type(set_focal, ("TargetArray", "Item"), "real")

    apertures = add("apertures", "apertures", "K2Node_VariableGet_6", 1824, 304)
    aperture = add("aperture", "aperture", "K2Node_VariableGet_7", 1824, 400)
    set_aperture = add("set_aperture", "set_array", "K2Node_CallArrayFunction_3", 2112, 0)
    set_array_element_type(set_aperture, ("TargetArray", "Item"), "real")

    focuses = add("focuses", "focuses", "K2Node_VariableGet_8", 2272, 304)
    focus = add("focus", "focus", "K2Node_VariableGet_9", 2272, 400)
    set_focus = add("set_focus", "set_array", "K2Node_CallArrayFunction_4", 2560, 0)
    set_array_element_type(set_focus, ("TargetArray", "Item"), "real")
    sync = add("sync", "sync", "K2Node_CallFunction_2", 2912, 0)
    bp.retarget_self_call(sync, "SyncDraftWaypointsV1")
    print_node = add("print", "print", "K2Node_CallFunction_3", 3232, 0)
    bp.set_pin_default(print_node, "InString", "[EDD] Selected waypoint replaced")

    bp.connect(entry, "then", camera_branch, "execute")
    bp.connect(drone, "DroneCameraRef", valid_object, "Object")
    bp.connect(valid_object, "ReturnValue", camera_branch, "Condition")
    bp.connect(camera_branch, "then", index_branch, "execute")
    bp.connect(ids, "DraftWaypointIds", valid_index, "TargetArray")
    bp.connect(selected, "SelectedWaypointIndex", valid_index, "IndexToTest")
    bp.connect(valid_index, "ReturnValue", index_branch, "Condition")

    exec_chain = [
        index_branch,
        set_transform,
        set_focal,
        set_aperture,
        set_focus,
        sync,
        print_node,
    ]
    for before, after in zip(exec_chain, exec_chain[1:]):
        bp.connect(before, "then", after, "execute")

    for array_node, array_pin, setter in (
        (transforms, "DraftWaypointTransforms", set_transform),
        (focals, "DraftWaypointFocalLengths", set_focal),
        (apertures, "DraftWaypointApertures", set_aperture),
        (focuses, "DraftWaypointFocusDistances", set_focus),
    ):
        bp.connect(array_node, array_pin, setter, "TargetArray")
        bp.connect(selected, "SelectedWaypointIndex", setter, "Index")

    bp.connect(drone, "DroneCameraRef", transform, "self")
    bp.connect(transform, "ReturnValue", set_transform, "Item")
    bp.connect(drone, "DroneCameraRef", focal, "self")
    bp.connect(focal, "FocalLength", set_focal, "Item")
    bp.connect(drone, "DroneCameraRef", aperture, "self")
    bp.connect(aperture, "Aperture", set_aperture, "Item")
    bp.connect(drone, "DroneCameraRef", focus, "self")
    bp.connect(focus, "ManualFocusDistance", set_focus, "Item")
    return list(nodes.values())


def build_delete(bp, templates: dict[str, str]):
    graph = "DeleteSelectedWaypoint"
    bp.TARGET_GRAPH = graph
    nodes = {}

    def add(key: str, template: str, name: str, x: int, y: int):
        node = bp.Node.clone(key, templates[template], name, x, y)
        nodes[key] = node
        return node

    entry = add("entry", "entry", "K2Node_FunctionEntry_0", 0, 0)
    retarget_entry(entry, graph)
    selected = add("selected", "selected_get", "K2Node_VariableGet_0", 0, 304)
    bp.retarget_variable(
        selected, "NextWaypointId", "SelectedWaypointIndex", SELECTED_INDEX_GUID
    )

    channel_specs = (
        ("ids", "DraftWaypointIds", "int"),
        ("transforms", "DraftWaypointTransforms", "struct"),
        ("focals", "DraftWaypointFocalLengths", "real"),
        ("apertures", "DraftWaypointApertures", "real"),
        ("focuses", "DraftWaypointFocusDistances", "real"),
        ("holds", "DraftWaypointHoldSeconds", "real"),
    )
    getters = {}
    removes = []
    for index, (key, pin_name, kind) in enumerate(channel_specs):
        x = 416 + index * 400
        getter = add(key, key, f"K2Node_VariableGet_{index + 1}", x, 304)
        remove = add(
            f"remove_{key}",
            "remove_index",
            f"K2Node_CallArrayFunction_{index + 2}",
            x + 160,
            0,
        )
        set_array_element_type(remove, ("TargetArray",), kind)
        bp.connect(getter, pin_name, remove, "TargetArray")
        bp.connect(selected, "SelectedWaypointIndex", remove, "IndexToRemove")
        getters[key] = getter
        removes.append(remove)

    valid_before = add("valid_before", "valid_index", "K2Node_CallArrayFunction_0", 160, 304)
    set_array_element_type(valid_before, ("TargetArray",), "int")
    branch_before = add("branch_before", "branch", "K2Node_IfThenElse_0", 416, 0)
    valid_after = add("valid_after", "valid_index", "K2Node_CallArrayFunction_1", 2816, 304)
    set_array_element_type(valid_after, ("TargetArray",), "int")
    branch_after = add("branch_after", "branch", "K2Node_IfThenElse_1", 3072, 0)
    length = add("length", "length", "K2Node_CallArrayFunction_8", 3072, 304)
    set_array_element_type(length, ("TargetArray",), "int")
    subtract = add("subtract", "int_add", "K2Node_PromotableOperator_0", 3328, 304)
    subtract.text = subtract.text.replace('OperationName="Add"', 'OperationName="Subtract"', 1)
    subtract.text = subtract.text.replace('MemberName="Add_IntInt"', 'MemberName="Subtract_IntInt"', 1)
    bp.set_pin_default(subtract, "B", "1")
    selected_set = add("selected_set", "selected_set", "K2Node_VariableSet_0", 3552, 128)
    bp.retarget_variable(
        selected_set, "NextWaypointId", "SelectedWaypointIndex", SELECTED_INDEX_GUID
    )
    sync_keep = add("sync_keep", "sync", "K2Node_CallFunction_0", 3360, -128)
    bp.retarget_self_call(sync_keep, "SyncDraftWaypointsV1")
    sync_repair = add("sync_repair", "sync", "K2Node_CallFunction_1", 3840, 128)
    bp.retarget_self_call(sync_repair, "SyncDraftWaypointsV1")

    bp.connect(entry, "then", branch_before, "execute")
    bp.connect(getters["ids"], "DraftWaypointIds", valid_before, "TargetArray")
    bp.connect(selected, "SelectedWaypointIndex", valid_before, "IndexToTest")
    bp.connect(valid_before, "ReturnValue", branch_before, "Condition")
    bp.connect(branch_before, "then", removes[0], "execute")
    for before, after in zip(removes, removes[1:]):
        bp.connect(before, "then", after, "execute")
    bp.connect(removes[-1], "then", branch_after, "execute")

    bp.connect(getters["ids"], "DraftWaypointIds", valid_after, "TargetArray")
    bp.connect(selected, "SelectedWaypointIndex", valid_after, "IndexToTest")
    bp.connect(valid_after, "ReturnValue", branch_after, "Condition")
    bp.connect(branch_after, "then", sync_keep, "execute")
    bp.connect(branch_after, "else", selected_set, "execute")
    bp.connect(getters["ids"], "DraftWaypointIds", length, "TargetArray")
    bp.connect(length, "ReturnValue", subtract, "A")
    bp.connect(subtract, "ReturnValue", selected_set, "SelectedWaypointIndex")
    bp.connect(selected_set, "then", sync_repair, "execute")
    return list(nodes.values())


def write_graph(bp, nodes, output: Path, paste_output: Path | None) -> None:
    full = "\n".join(node.text for node in nodes) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(full, encoding="utf-8")
    if paste_output is None:
        return
    paste = "\n".join(
        re.sub(
            r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)",
            "",
            node.text,
        )
        for node in nodes
        if node.key != "entry"
    ) + "\n"
    paste_output.parent.mkdir(parents=True, exist_ok=True)
    paste_output.write_text(paste, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--replace-output", type=Path, required=True)
    parser.add_argument("--replace-paste-output", type=Path)
    parser.add_argument("--delete-output", type=Path, required=True)
    parser.add_argument("--delete-paste-output", type=Path)
    args = parser.parse_args()

    bp = load_capture_builder(args.project_root)
    templates = make_templates(bp, args.project_root)
    write_graph(
        bp,
        build_replace(bp, templates),
        args.replace_output,
        args.replace_paste_output,
    )
    write_graph(
        bp,
        build_delete(bp, templates),
        args.delete_output,
        args.delete_paste_output,
    )


if __name__ == "__main__":
    main()
