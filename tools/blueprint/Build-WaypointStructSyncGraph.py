"""Build the Blueprint bridge from legacy waypoint channels to ST_EDD_Waypoint.

The generated function is deliberately transactional for channel-shape errors:
all six legacy arrays must have the same length before DraftWaypointsV1 is
cleared.  A successful pass preserves source order and every authored value.

Scalar-domain validation remains an upstream responsibility in this milestone;
the document oracle is stricter and is the target for the next validation pass.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_GRAPH = "SyncDraftWaypointsV1"
WAYPOINT_STRUCT = (
    "/Script/CoreUObject.UserDefinedStruct'"
    "/Game/Mods/ExileDroneDirector/Data/Structs/"
    "ST_EDD_Waypoint.ST_EDD_Waypoint'"
)


def load_builder(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_graph_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph builder primitives from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.TARGET_GRAPH = TARGET_GRAPH
    module._id_counter = 0
    return module


def replace_pin_type(node, pin_name: str, category: str, subcategory: str = "", obj: str = "None") -> None:
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, count=1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, count=1)
        return re.sub(
            r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',
            f'PinType.PinSubCategoryObject={obj}',
            line,
            count=1,
        )

    node.mutate_pin(pin_name, mutate)


def set_array_kind(node, array_pin: str, value_pin: str | None, kind: str) -> None:
    if kind == "int":
        category, subcategory, obj = "int", "", "None"
    elif kind == "real":
        category, subcategory, obj = "real", "double", "None"
    elif kind == "transform":
        category, subcategory = "struct", ""
        obj = '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Transform\'"'
    elif kind == "waypoint":
        category, subcategory, obj = "struct", "", f'"{WAYPOINT_STRUCT}"'
    else:
        raise RuntimeError(f"Unsupported array kind: {kind}")
    replace_pin_type(node, array_pin, category, subcategory, obj)
    if value_pin is not None:
        replace_pin_type(node, value_pin, category, subcategory, obj)


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name)
    node.text = "\n".join(
        line for line in node.text.splitlines() if f"PinId={pin_id}" not in line
    )


def make_clear(node) -> None:
    node.text = node.text.replace('MemberName="Array_Add"', 'MemberName="Array_Clear"', 1)
    remove_pin(node, "NewItem")
    remove_pin(node, "ReturnValue")


def make_equal(node) -> None:
    node.text = node.text.replace('MemberName="GreaterEqual_IntInt"', 'MemberName="EqualEqual_IntInt"', 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    base = load_builder(args.project_root)
    Node = base.Node
    connect = base.connect
    set_pin_default = base.set_pin_default
    read_blocks = base.read_blocks
    find_block = base.find_block

    blueprint = args.project_root / "tools" / "blueprint"
    forms = read_blocks(blueprint / "templates" / "waypoint-struct-sync-node-forms.eddgraph")
    capture_forms = read_blocks(blueprint / "templates" / "waypoint-capture-node-forms.eddgraph")
    playback = read_blocks(blueprint / "snippets" / "update-linear-playback.eddgraph")
    start = read_blocks(blueprint / "snippets" / "start-linear-playback.eddgraph")
    enter = read_blocks(blueprint / "snippets" / "enter-drone-mode.eddgraph")

    legacy_names = [
        "DraftWaypointIds",
        "DraftWaypointTransforms",
        "DraftWaypointFocalLengths",
        "DraftWaypointApertures",
        "DraftWaypointFocusDistances",
        "DraftWaypointHoldSeconds",
    ]
    templates = {
        "entry": find_block(forms, r"K2Node_FunctionEntry"),
        "foreach": find_block(forms, r"K2Node_MacroInstance"),
        "make": find_block(forms, r"K2Node_MakeStruct"),
        "typed": find_block(forms, r'MemberName="DraftWaypointsV1"'),
        "length": find_block(playback, r'MemberName="Array_Length"'),
        "equal": find_block(start, r'MemberName="GreaterEqual_IntInt"'),
        "branch": find_block(enter, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse\b"),
        "get_item": find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_GetArrayItem\b"),
        "array_add": find_block(capture_forms, r'MemberName="Array_Add"'),
        "print": find_block(enter, r'MemberName="PrintString"'),
    }
    for name in legacy_names:
        templates[name] = find_block(capture_forms, rf'MemberName="{name}"')

    nodes = {}

    def add(key: str, template_key: str, name: str, x: int, y: int):
        node = Node.clone(key, templates[template_key], name, x, y)
        nodes[key] = node
        return node

    entry = add("entry", "entry", "K2Node_FunctionEntry_0", 0, 0)

    getters = {}
    lengths = {}
    for index, legacy_name in enumerate(legacy_names):
        getters[legacy_name] = add(
            f"get_{index}", legacy_name, f"K2Node_VariableGet_{index}", 0, 240 + index * 128
        )
        lengths[legacy_name] = add(
            f"length_{index}", "length", f"K2Node_CallArrayFunction_{index}", 288, 240 + index * 128
        )
        kind = "int" if index == 0 else "transform" if index == 1 else "real"
        set_array_kind(lengths[legacy_name], "TargetArray", None, kind)
        connect(getters[legacy_name], legacy_name, lengths[legacy_name], "TargetArray")

    branches = []
    for index, legacy_name in enumerate(legacy_names[1:]):
        equal = add(
            f"equal_{index}", "equal", f"K2Node_CallFunction_{index}", 608 + index * 400, 224
        )
        make_equal(equal)
        branch = add(
            f"branch_{index}", "branch", f"K2Node_IfThenElse_{index}", 800 + index * 400, 0
        )
        failure = add(
            f"failure_{index}", "print", f"K2Node_CallFunction_{index + 5}", 800 + index * 400, -272
        )
        set_pin_default(
            failure,
            "InString",
            f"[EDD] Waypoint struct sync rejected: {legacy_name} length mismatch",
        )
        connect(lengths[legacy_names[0]], "ReturnValue", equal, "A")
        connect(lengths[legacy_name], "ReturnValue", equal, "B")
        connect(equal, "ReturnValue", branch, "Condition")
        connect(branch, "else", failure, "execute")
        branches.append(branch)

    connect(entry, "then", branches[0], "execute")
    for before, after in zip(branches, branches[1:]):
        connect(before, "then", after, "execute")

    typed_clear_get = add("typed_clear_get", "typed", "K2Node_VariableGet_6", 2784, 256)
    clear = add("clear", "array_add", "K2Node_CallArrayFunction_10", 3008, 0)
    make_clear(clear)
    set_array_kind(clear, "TargetArray", None, "waypoint")
    connect(branches[-1], "then", clear, "execute")
    connect(typed_clear_get, "DraftWaypointsV1", clear, "TargetArray")

    foreach = add("foreach", "foreach", "K2Node_MacroInstance_0", 3296, 0)
    set_array_kind(foreach, "Array", "Array Element", "int")
    connect(clear, "then", foreach, "Exec")
    connect(getters[legacy_names[0]], legacy_names[0], foreach, "Array")

    item_nodes = {}
    for index, legacy_name in enumerate(legacy_names[1:]):
        item = add(
            f"item_{index}", "get_item", f"K2Node_GetArrayItem_{index}", 3296, 320 + index * 160
        )
        kind = "transform" if index == 0 else "real"
        set_array_kind(item, "Array", "Output", kind)
        connect(getters[legacy_name], legacy_name, item, "Array")
        connect(foreach, "Array Index", item, "Dimension 1")
        item_nodes[legacy_name] = item

    make = add("make", "make", "K2Node_MakeStruct_0", 3712, 288)
    connect(foreach, "Array Element", make, "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE")
    make_pins = {
        "DraftWaypointTransforms": "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9",
        "DraftWaypointFocalLengths": "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B",
        "DraftWaypointApertures": "Aperture_10_949C579344F8DFA750F1948051A417B2",
        "DraftWaypointFocusDistances": "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F",
        "DraftWaypointHoldSeconds": "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB",
    }
    for legacy_name, make_pin in make_pins.items():
        connect(item_nodes[legacy_name], "Output", make, make_pin)

    typed_add_get = add("typed_add_get", "typed", "K2Node_VariableGet_7", 3712, 992)
    add_item = add("add_item", "array_add", "K2Node_CallArrayFunction_11", 4096, 0)
    set_array_kind(add_item, "TargetArray", "NewItem", "waypoint")
    connect(foreach, "LoopBody", add_item, "execute")
    connect(typed_add_get, "DraftWaypointsV1", add_item, "TargetArray")
    connect(make, "ST_EDD_Waypoint", add_item, "NewItem")

    success = add("success", "print", "K2Node_CallFunction_10", 4096, -176)
    set_pin_default(success, "InString", "[EDD] Waypoint struct sync complete")
    connect(foreach, "Completed", success, "execute")

    ordered = list(nodes.values())
    full_text = "\n".join(node.text for node in ordered) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full_text, encoding="utf-8")
    if args.paste_output:
        paste_blocks = []
        for node in ordered:
            if node.key == "entry":
                continue
            text = node.text
            if node.key == "branch_0":
                # Unreal does not preserve a serialized link to a function-entry
                # node that is outside the pasted selection.  Emit the real
                # paste contract: import all body nodes, then connect this one
                # execution pin in the editor and round-trip the full graph.
                text = re.sub(
                    r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)",
                    "",
                    text,
                    count=1,
                )
            paste_blocks.append(text)
        paste = "\n".join(paste_blocks) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
