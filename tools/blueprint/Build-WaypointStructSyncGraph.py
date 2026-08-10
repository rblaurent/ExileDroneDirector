"""Build the Blueprint bridge from legacy waypoint channels to ST_EDD_Waypoint.

The generated function is deliberately transactional for channel-shape errors:
all six legacy arrays must have the same length before DraftWaypointsV1 is
cleared.  A successful pass preserves source order and every authored value.

After channel-shape validation, a non-mutating preflight scans every source
index.  It rejects non-positive or duplicate IDs, non-finite scalar values, and
invalid camera/timing domains before the prior typed snapshot can be cleared.
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
PREFLIGHT_VARIABLE = "WaypointPreflightValid"


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


def rename_pin(node, old_name: str, new_name: str) -> None:
    node.text = node.text.replace(f'PinName="{old_name}"', f'PinName="{new_name}"')
    node.pins[new_name] = node.pins.pop(old_name)


def retarget_member_variable(node, old_name: str, new_name: str) -> None:
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{re.escape(old_name)}"[^)]*\)',
        f'VariableReference=(MemberName="{new_name}",bSelfContext=True)',
        node.text,
        count=1,
    )
    rename_pin(node, old_name, new_name)


def retarget_function(node, member_name: str) -> None:
    node.text = re.sub(
        r'MemberName="[^"]+"',
        f'MemberName="{member_name}"',
        node.text,
        count=1,
    )


def set_node_pin_default(node, pin_name: str, value: str) -> None:
    def mutate(line: str) -> str:
        if "DefaultValue=" in line:
            return re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, count=1)
        return line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1)

    node.mutate_pin(pin_name, mutate)


def make_array_find(node) -> None:
    retarget_function(node, "Array_Find")
    rename_pin(node, "IndexToTest", "ItemToFind")
    replace_pin_type(node, "TargetArray", "int")
    replace_pin_type(node, "ItemToFind", "int")
    replace_pin_type(node, "ReturnValue", "int")
    set_node_pin_default(node, "ReturnValue", "-1")


def make_subtract_double(node) -> None:
    retarget_function(node, "Subtract_DoubleDouble")
    replace_pin_type(node, "ReturnValue", "real", "double")
    set_node_pin_default(node, "ReturnValue", "0.0")


def make_equal_double(node) -> None:
    retarget_function(node, "EqualEqual_DoubleDouble")


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
    edit_forms = read_blocks(blueprint / "templates" / "waypoint-edit-node-forms.eddgraph")
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
        "double_compare": find_block(start, r'MemberName="GreaterEqual_DoubleDouble"'),
        "array_find": find_block(edit_forms, r'MemberName="Array_IsValidIndex"'),
        "preflight_get": find_block(playback, r'K2Node_VariableGet.*?MemberName="PlaybackActive"'),
        "preflight_set": find_block(start, r'K2Node_VariableSet.*?MemberName="PlaybackActive"'),
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

    preflight_set_true = add(
        "preflight_set_true",
        "preflight_set",
        "K2Node_VariableSet_0",
        2784,
        0,
    )
    retarget_member_variable(preflight_set_true, "PlaybackActive", PREFLIGHT_VARIABLE)
    set_pin_default(preflight_set_true, PREFLIGHT_VARIABLE, "true")
    connect(branches[-1], "then", preflight_set_true, "execute")

    preflight_foreach = add(
        "preflight_foreach",
        "foreach",
        "K2Node_MacroInstance_0",
        3072,
        0,
    )
    set_array_kind(preflight_foreach, "Array", "Array Element", "int")
    connect(preflight_set_true, "then", preflight_foreach, "Exec")
    connect(getters[legacy_names[0]], legacy_names[0], preflight_foreach, "Array")

    preflight_items = {}
    for index, legacy_name in enumerate(legacy_names[2:]):
        item = add(
            f"preflight_item_{index}",
            "get_item",
            f"K2Node_GetArrayItem_{index}",
            3264,
            400 + index * 160,
        )
        set_array_kind(item, "Array", "Output", "real")
        connect(getters[legacy_name], legacy_name, item, "Array")
        connect(preflight_foreach, "Array Index", item, "Dimension 1")
        preflight_items[legacy_name] = item

    validations = []
    id_positive = add(
        "id_positive",
        "equal",
        "K2Node_CallFunction_20",
        3520,
        256,
    )
    retarget_function(id_positive, "Greater_IntInt")
    set_pin_default(id_positive, "B", "0")
    connect(preflight_foreach, "Array Element", id_positive, "A")
    validations.append(("positive waypoint ID", id_positive))

    id_find = add(
        "id_find",
        "array_find",
        "K2Node_CallArrayFunction_20",
        3520,
        400,
    )
    make_array_find(id_find)
    connect(getters[legacy_names[0]], legacy_names[0], id_find, "TargetArray")
    connect(preflight_foreach, "Array Element", id_find, "ItemToFind")
    id_unique = add(
        "id_unique",
        "equal",
        "K2Node_CallFunction_21",
        3744,
        400,
    )
    make_equal(id_unique)
    connect(id_find, "ReturnValue", id_unique, "A")
    connect(preflight_foreach, "Array Index", id_unique, "B")
    validations.append(("unique waypoint ID", id_unique))

    scalar_rules = (
        ("DraftWaypointFocalLengths", "positive focal length", "Greater_DoubleDouble"),
        ("DraftWaypointApertures", "positive aperture", "Greater_DoubleDouble"),
        ("DraftWaypointFocusDistances", "non-negative focus distance", "GreaterEqual_DoubleDouble"),
        ("DraftWaypointHoldSeconds", "non-negative hold", "GreaterEqual_DoubleDouble"),
    )
    for index, (legacy_name, label, domain_function) in enumerate(scalar_rules):
        item = preflight_items[legacy_name]
        subtract = add(
            f"finite_subtract_{index}",
            "double_compare",
            f"K2Node_CallFunction_{22 + index * 3}",
            3520,
            608 + index * 288,
        )
        make_subtract_double(subtract)
        connect(item, "Output", subtract, "A")
        connect(item, "Output", subtract, "B")

        finite_equal = add(
            f"finite_equal_{index}",
            "double_compare",
            f"K2Node_CallFunction_{23 + index * 3}",
            3744,
            608 + index * 288,
        )
        make_equal_double(finite_equal)
        set_pin_default(finite_equal, "B", "0.0")
        connect(subtract, "ReturnValue", finite_equal, "A")
        validations.append((f"finite {legacy_name}", finite_equal))

        domain = add(
            f"domain_{index}",
            "double_compare",
            f"K2Node_CallFunction_{24 + index * 3}",
            3968,
            608 + index * 288,
        )
        retarget_function(domain, domain_function)
        set_pin_default(domain, "B", "0.0")
        connect(item, "Output", domain, "A")
        validations.append((label, domain))

    validation_branches = []
    validation_start_x = 4256
    for index, (label, condition) in enumerate(validations):
        branch = add(
            f"preflight_branch_{index}",
            "branch",
            f"K2Node_IfThenElse_{index + 5}",
            validation_start_x + index * 352,
            0,
        )
        failure_set = add(
            f"preflight_failure_set_{index}",
            "preflight_set",
            f"K2Node_VariableSet_{index + 1}",
            validation_start_x + index * 352,
            -256,
        )
        retarget_member_variable(failure_set, "PlaybackActive", PREFLIGHT_VARIABLE)
        set_pin_default(failure_set, PREFLIGHT_VARIABLE, "false")
        connect(condition, "ReturnValue", branch, "Condition")
        connect(branch, "else", failure_set, "execute")
        validation_branches.append(branch)

    connect(preflight_foreach, "LoopBody", validation_branches[0], "execute")
    for before, after in zip(validation_branches, validation_branches[1:]):
        connect(before, "then", after, "execute")

    result_x = validation_start_x + len(validation_branches) * 352
    preflight_get = add(
        "preflight_get",
        "preflight_get",
        "K2Node_VariableGet_8",
        result_x,
        240,
    )
    retarget_member_variable(preflight_get, "PlaybackActive", PREFLIGHT_VARIABLE)
    preflight_result = add(
        "preflight_result",
        "branch",
        "K2Node_IfThenElse_15",
        result_x + 224,
        0,
    )
    preflight_failure = add(
        "preflight_failure",
        "print",
        "K2Node_CallFunction_50",
        result_x + 224,
        -256,
    )
    set_pin_default(
        preflight_failure,
        "InString",
        "[EDD] Waypoint struct sync rejected: ID or scalar preflight failed",
    )
    connect(preflight_foreach, "Completed", preflight_result, "execute")
    connect(preflight_get, PREFLIGHT_VARIABLE, preflight_result, "Condition")
    connect(preflight_result, "else", preflight_failure, "execute")

    typed_clear_get = add("typed_clear_get", "typed", "K2Node_VariableGet_6", result_x + 512, 256)
    clear = add("clear", "array_add", "K2Node_CallArrayFunction_10", result_x + 736, 0)
    make_clear(clear)
    set_array_kind(clear, "TargetArray", None, "waypoint")
    connect(preflight_result, "then", clear, "execute")
    connect(typed_clear_get, "DraftWaypointsV1", clear, "TargetArray")

    foreach = add("foreach", "foreach", "K2Node_MacroInstance_1", result_x + 1024, 0)
    set_array_kind(foreach, "Array", "Array Element", "int")
    connect(clear, "then", foreach, "Exec")
    connect(getters[legacy_names[0]], legacy_names[0], foreach, "Array")

    item_nodes = {}
    for index, legacy_name in enumerate(legacy_names[1:]):
        item = add(
            f"item_{index}", "get_item", f"K2Node_GetArrayItem_{index + 4}", result_x + 1024, 320 + index * 160
        )
        kind = "transform" if index == 0 else "real"
        set_array_kind(item, "Array", "Output", kind)
        connect(getters[legacy_name], legacy_name, item, "Array")
        connect(foreach, "Array Index", item, "Dimension 1")
        item_nodes[legacy_name] = item

    make = add("make", "make", "K2Node_MakeStruct_0", result_x + 1440, 288)
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

    typed_add_get = add("typed_add_get", "typed", "K2Node_VariableGet_7", result_x + 1440, 992)
    add_item = add("add_item", "array_add", "K2Node_CallArrayFunction_11", result_x + 1824, 0)
    set_array_kind(add_item, "TargetArray", "NewItem", "waypoint")
    connect(foreach, "LoopBody", add_item, "execute")
    connect(typed_add_get, "DraftWaypointsV1", add_item, "TargetArray")
    connect(make, "ST_EDD_Waypoint", add_item, "NewItem")

    success = add("success", "print", "K2Node_CallFunction_10", result_x + 1824, -176)
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
