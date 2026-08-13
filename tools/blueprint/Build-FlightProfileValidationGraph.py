"""Build fail-closed authored flight-profile shape and identity validation."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateFlightProfileInputsV1"
PROFILE_IDS = ("cinematic_drone", "hybrid", "fpv_cinewhoop", "fpv_freestyle", "fpv_long_range")


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_validation_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""), "string": ("string", ""),
    }[value]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


def variable(scalar, node, name, value, array=False):
    scalar.retarget_variable(node, name, "real" if value == "int" else value)
    kind(node, name, value, array)
    if "Output_Get" in node.pins:
        kind(node, "Output_Get", value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    builder = scalar.Builder(bp, forms, FUNCTION)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    raw = {
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
    }

    def add(key, form, x, y):
        text = raw[form]
        match = bp.BLOCK_RE.match(text)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, text, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def get(name, value, x, y, array=False):
        node = builder.get(name, "real" if value == "int" else value, x, y)
        variable(scalar, node, name, value, array)
        return node

    def compare(member, left, left_pin, right, right_pin, x, y, value="int"):
        node = builder.add(f"compare_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            kind(node, pin, value)
        kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def boolean(member, left, right, x, y):
        return compare(member, left, "ReturnValue", right, "ReturnValue", x, y, "bool")

    def string_equal(source, pin, expected, x, y):
        node = builder.equal_string(x, y, expected)
        bp.connect(source, pin, node, "A")
        return node

    def any_known(source, pin, x, y, include_empty):
        values = (("",) if include_empty else ()) + PROFILE_IDS
        comparisons = [string_equal(source, pin, expected, x, y + index * 128) for index, expected in enumerate(values)]
        result = comparisons[0]
        for index, comparison in enumerate(comparisons[1:]):
            result = boolean("BooleanOR", result, comparison, x + 256 + index * 224, y + index * 96)
        return result

    reset = builder.set("FlightProfileStageValidV1", "bool", 256, 1280, "false")
    bp.connect(builder.entry, "then", reset, "execute")
    default_id = get("FlightProfileInputDefaultIdV1", "string", 0, 0)
    overrides = get("FlightProfileInputSegmentOverrideIdsV1", "string", 0, 192, True)
    count = get("FlightProfileInputSegmentCountV1", "int", 0, 384)
    length = add("override_length", "length", 320, 192)
    kind(length, "TargetArray", "string", True)
    bp.connect(overrides, "FlightProfileInputSegmentOverrideIdsV1", length, "TargetArray")
    minimum = compare("GreaterEqual_IntInt", count, "FlightProfileInputSegmentCountV1", None, "1", 576, 0)
    maximum = compare("LessEqual_IntInt", count, "FlightProfileInputSegmentCountV1", None, "511", 576, 128)
    shape = compare("EqualEqual_IntInt", length, "ReturnValue", count, "FlightProfileInputSegmentCountV1", 576, 256)
    default_known = any_known(default_id, "FlightProfileInputDefaultIdV1", 576, 512, False)
    combined = minimum
    for index, guard in enumerate((maximum, shape, default_known)):
        combined = boolean("BooleanAND", combined, guard, 2176 + index * 224, 320, )
    shape_branch = builder.add("shape_branch", "branch", 2944, 1280)
    bp.connect(reset, "then", shape_branch, "execute")
    bp.connect(combined, "ReturnValue", shape_branch, "Condition")
    accept = builder.set("FlightProfileStageValidV1", "bool", 3200, 1280, "true")
    bp.connect(shape_branch, "then", accept, "execute")
    loop = add("override_loop", "foreach", 3456, 640)
    kind(loop, "Array", "string", True)
    kind(loop, "Array Element", "string")
    bp.connect(overrides, "FlightProfileInputSegmentOverrideIdsV1", loop, "Array")
    bp.connect(accept, "then", loop, "Exec")
    override_known = any_known(loop, "Array Element", 3712, 448, True)
    item_branch = builder.add("item_branch", "branch", 5312, 640)
    bp.connect(loop, "LoopBody", item_branch, "execute")
    bp.connect(override_known, "ReturnValue", item_branch, "Condition")
    reject = builder.set("FlightProfileStageValidV1", "bool", 5568, 832, "false")
    bp.connect(item_branch, "else", reject, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
