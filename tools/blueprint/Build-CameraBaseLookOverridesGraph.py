"""Compose sparse authored camera-look overrides in canonical channel order."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ApplyCameraLookAuthoredOverridesV1"
CHANNEL_IDS = (
    "focal_length_mm", "aperture_fstop", "focus_distance_cm", "focus_influence",
    "exposure_ev", "bloom_weight", "vignette_weight", "color_grading_weight",
    "tint_weight", "motion_blur_weight", "chromatic_aberration_weight",
    "sharpening_weight", "matte_weight",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_look_override_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""),
        "real": ("real", "double"), "string": ("string", ""),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-forloop-node-form.eddgraph")
    find_graph = bp.read_blocks(args.project_root / "tools/blueprint/snippets/find-record-index-v1.eddgraph")
    public = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    forms.update(
        array_add=bp.find_block(capture, r'MemberName="Array_Add"'),
        array_clear=bp.find_block(reset, r'MemberName="Array_Clear"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        loop=bp.find_block(loops, r"StandardMacros:ForLoop"),
        find=bp.find_block(find_graph, r'MemberName="Array_Find"'),
        select=bp.find_block(public, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name: str, kind: str, x: int, y: int, value: str):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        scalar.set_default(node, name, value)
        return node

    def add_form(key: str, form: str, x: int, y: int):
        raw = forms[form]
        match = bp.BLOCK_RE.match(raw)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, raw, f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, kind: str = "int", right=None, right_pin: str | None = None, default: str | None = None):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def item(source, source_pin: str, kind: str, index, index_pin: str, x: int, y: int):
        node = add_form(f"item_{source_pin}_{len(b.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def array_op(form: str, source, source_pin: str, kind: str, x: int, y: int, *, new=None, new_pin: str | None = None, default: str | None = None):
        node = add_form(f"{form}_{source_pin}_{len(b.nodes)}", form, x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(source, source_pin, node, "TargetArray")
        if form == "array_add":
            pin_kind(node, "NewItem", kind)
            pin_kind(node, "ReturnValue", "int")
            if new is None:
                scalar.set_default(node, "NewItem", default)
            else:
                bp.connect(new, new_pin, node, "NewItem")
        return node

    def select(condition, false_source, false_pin: str | None, true_value: str, x: int, y: int):
        node = add_form(f"select_{len(b.nodes)}", "select", x, y)
        pin_kind(node, "Index", "bool")
        for pin in ("Option 0", "Option 1", "ReturnValue"):
            pin_kind(node, pin, "string")
        bp.connect(condition, "ReturnValue", node, "Index")
        if false_source is None:
            scalar.set_default(node, "Option 0", CHANNEL_IDS[-1])
        else:
            bp.connect(false_source, false_pin, node, "Option 0")
        scalar.set_default(node, "Option 1", true_value)
        return node

    candidate_values = get("CameraLookCandidateValuesV1", "real", 0, 320, True)
    candidate_mask = get("CameraLookCandidateOverrideMaskV1", "bool", 0, 544, True)
    clear_values = array_op("array_clear", candidate_values, "CameraLookCandidateValuesV1", "real", 256, 2880)
    clear_mask = array_op("array_clear", candidate_mask, "CameraLookCandidateOverrideMaskV1", "bool", 480, 2880)
    invalidate = set_("CameraLookCandidateValidV1", "bool", 704, 2880, "false")
    scratch = get("CameraLookScratchValidV1", "bool", 0, 0)
    guard = b.add("base_guard", "branch", 928, 2880)
    bp.connect(b.entry, "then", clear_values, "execute")
    bp.connect(clear_values, "then", clear_mask, "execute")
    bp.connect(clear_mask, "then", invalidate, "execute")
    bp.connect(invalidate, "then", guard, "execute")
    bp.connect(scratch, "CameraLookScratchValidV1", guard, "Condition")

    loop = add_form("canonical_loop", "loop", 1152, 2880)
    scalar.set_default(loop, "FirstIndex", "0")
    scalar.set_default(loop, "LastIndex", "12")
    bp.connect(guard, "then", loop, "execute")
    index_checks = [compare("EqualEqual_IntInt", loop, "Index", 1152 + index * 208, index * 160, default=str(index)) for index in range(12)]
    channel = None
    for index in reversed(range(12)):
        channel = select(index_checks[index], channel, "ReturnValue" if channel is not None else None, CHANNEL_IDS[index], 3648 + index * 208, index * 160)

    authored_ids = get("CameraLookInputAuthoredChannelIdsV1", "string", 0, 800, True)
    authored_values = get("CameraLookInputAuthoredValuesV1", "real", 0, 1024, True)
    base_values = get("CameraLookCandidateBaseValuesV1", "real", 0, 1248, True)
    find = add_form("find_authored_channel", "find", 6368, 2400)
    pin_kind(find, "TargetArray", "string", True)
    pin_kind(find, "ItemToFind", "string")
    pin_kind(find, "ReturnValue", "int")
    bp.connect(authored_ids, "CameraLookInputAuthoredChannelIdsV1", find, "TargetArray")
    bp.connect(channel, "ReturnValue", find, "ItemToFind")
    found = compare("GreaterEqual_IntInt", find, "ReturnValue", 6592, 2400, default="0")
    branch = b.add("authored_branch", "branch", 6816, 2880)
    bp.connect(loop, "LoopBody", branch, "execute")
    bp.connect(found, "ReturnValue", branch, "Condition")

    authored_value = item(authored_values, "CameraLookInputAuthoredValuesV1", "real", find, "ReturnValue", 7040, 2240)
    base_value = item(base_values, "CameraLookCandidateBaseValuesV1", "real", loop, "Index", 7040, 2464)
    add_authored = array_op("array_add", candidate_values, "CameraLookCandidateValuesV1", "real", 7264, 2720, new=authored_value, new_pin="Output")
    mask_true = array_op("array_add", candidate_mask, "CameraLookCandidateOverrideMaskV1", "bool", 7488, 2720, default="true")
    add_base = array_op("array_add", candidate_values, "CameraLookCandidateValuesV1", "real", 7264, 3040, new=base_value, new_pin="Output")
    mask_false = array_op("array_add", candidate_mask, "CameraLookCandidateOverrideMaskV1", "bool", 7488, 3040, default="false")
    bp.connect(branch, "then", add_authored, "execute")
    bp.connect(add_authored, "then", mask_true, "execute")
    bp.connect(branch, "else", add_base, "execute")
    bp.connect(add_base, "then", mask_false, "execute")
    publish = set_("CameraLookCandidateValidV1", "bool", 7712, 2880, "true")
    bp.connect(loop, "Completed", publish, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
