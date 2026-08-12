"""Build validated cumulative arc-table inversion for trajectory version 1."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "InvertArcLengthTableV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_arc_table_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


def kind(node, pin: str, value: str, array: bool = False):
    category, subcategory = {"bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double")}[value]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def variable(scalar, node, name: str, value: str, array: bool = False):
    scalar.retarget_variable(node, name, "real" if value == "int" else value)
    kind(node, name, value, array)
    if "Output_Get" in node.pins: kind(node, "Output_Get", value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp); b = scalar.Builder(bp, forms, FUNCTION)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    foreach_form = bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')
    item_form = bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")

    def add_node(key, form, x, y):
        match = bp.BLOCK_RE.match(form); cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def get(name, value, x, y, array=False):
        node = b.get(name, "real" if value == "int" else value, x, y); variable(scalar, node, name, value, array); return node
    def setv(name, value, x, y, default=None):
        node = b.set(name, "real" if value == "int" else value, x, y, default); variable(scalar, node, name, value); return node
    def length(source, pin, x, y, key):
        node = add_node(key, length_form, x, y); kind(node, "TargetArray", "real", True); bp.connect(source, pin, node, "TargetArray"); return node
    def item(source, pin, index, index_pin, x, y, key):
        node = add_node(key, item_form, x, y); kind(node, "Array", "real", True); kind(node, "Output", "real")
        bp.connect(source, pin, node, "Array")
        if index is None: scalar.set_default(node, "Dimension 1", index_pin)
        else: bp.connect(index, index_pin, node, "Dimension 1")
        return node
    def compare(member, left, left_pin, right, right_pin, x, y, value):
        node = b.add(f"cmp_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): kind(node, pin, value)
        kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", right_pin)
        else: bp.connect(right, right_pin, node, "B")
        return node
    def and_(left, right, x, y): return compare("BooleanAND", left, "ReturnValue", right, "ReturnValue", x, y, "bool")
    def math(member, left, left_pin, right, right_pin, x, y, value="real"):
        node = b.math(member, x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"): kind(node, pin, value)
        bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", right_pin)
        else: bp.connect(right, right_pin, node, "B")
        return node
    def combine(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]): current = and_(current, condition, x + index * 208, y)
        return current

    us = get("TrajectoryArcInputUsV1", "real", 0, 80, True)
    distances = get("TrajectoryArcInputDistancesV1", "real", 0, 240, True)
    total = get("TrajectoryArcInputLengthV1", "real", 0, 400)
    distance_alpha = get("TrajectoryArcInputDistanceAlphaV1", "real", 0, 560)
    u_length = length(us, "TrajectoryArcInputUsV1", 256, 80, "u_length")
    d_length = length(distances, "TrajectoryArcInputDistancesV1", 256, 240, "d_length")

    reset = (
        setv("TrajectoryArcResultUV1", "real", 256, 1760, "0.0"),
        setv("TrajectoryArcResultValidV1", "bool", 512, 1760, "false"),
        setv("TrajectoryArcScratchUpperIndexV1", "int", 768, 1760, "-1"),
        setv("TrajectoryArcScratchValidV1", "bool", 1024, 1760, "true"),
    )
    bp.connect(b.entry, "then", reset[0], "execute")
    for left, right in zip(reset, reset[1:]): bp.connect(left, "then", right, "execute")

    shape = combine((
        compare("GreaterEqual_IntInt", u_length, "ReturnValue", None, "2", 512, 400, "int"),
        compare("EqualEqual_IntInt", d_length, "ReturnValue", u_length, "ReturnValue", 736, 400, "int"),
        b.finite(total, "TrajectoryArcInputLengthV1", 960, 400),
        compare("GreaterEqual_DoubleDouble", total, "TrajectoryArcInputLengthV1", None, "0.0", 1184, 400, "real"),
        b.finite(distance_alpha, "TrajectoryArcInputDistanceAlphaV1", 1408, 400),
    ), 1632, 400)
    shape_branch = b.add("shape_branch", "branch", 2560, 1760)
    bp.connect(reset[-1], "then", shape_branch, "execute"); bp.connect(shape, "ReturnValue", shape_branch, "Condition")
    shape_fail = setv("TrajectoryArcScratchValidV1", "bool", 2784, 2000, "false"); bp.connect(shape_branch, "else", shape_fail, "execute")

    last_index = math("Subtract_IntInt", u_length, "ReturnValue", None, "1", 2560, 560, "int")
    first_u = item(us, "TrajectoryArcInputUsV1", None, "0", 2784, 560, "first_u")
    first_d = item(distances, "TrajectoryArcInputDistancesV1", None, "0", 2784, 720, "first_d")
    last_u = item(us, "TrajectoryArcInputUsV1", last_index, "ReturnValue", 2784, 880, "last_u")
    last_d = item(distances, "TrajectoryArcInputDistancesV1", last_index, "ReturnValue", 2784, 1040, "last_d")
    endpoints = combine((
        compare("EqualEqual_DoubleDouble", first_u, "Output", None, "0.0", 3040, 560, "real"),
        compare("EqualEqual_DoubleDouble", first_d, "Output", None, "0.0", 3040, 720, "real"),
        compare("EqualEqual_DoubleDouble", last_u, "Output", None, "1.0", 3040, 880, "real"),
        compare("EqualEqual_DoubleDouble", last_d, "Output", total, "TrajectoryArcInputLengthV1", 3040, 1040, "real"),
    ), 3264, 720)
    endpoint_branch = b.add("endpoint_branch", "branch", 3936, 1760)
    bp.connect(shape_branch, "then", endpoint_branch, "execute"); bp.connect(endpoints, "ReturnValue", endpoint_branch, "Condition")
    endpoint_fail = setv("TrajectoryArcScratchValidV1", "bool", 4160, 2000, "false"); bp.connect(endpoint_branch, "else", endpoint_fail, "execute")

    clamped = b.add("clamped_alpha", "clamp", 3936, 1120); scalar.set_default(clamped, "Min", "0.0"); scalar.set_default(clamped, "Max", "1.0"); bp.connect(distance_alpha, "TrajectoryArcInputDistanceAlphaV1", clamped, "Value")
    target = math("Multiply_DoubleDouble", clamped, "ReturnValue", total, "TrajectoryArcInputLengthV1", 4192, 1120)
    loop = add_node("loop", foreach_form, 4160, 2400); kind(loop, "Array", "real", True); kind(loop, "Array Element", "real")
    bp.connect(distances, "TrajectoryArcInputDistancesV1", loop, "Array"); bp.connect(endpoint_branch, "then", loop, "Exec")
    not_first = compare("Greater_IntInt", loop, "Array Index", None, "0", 4416, 2240, "int")
    item_branch = b.add("item_branch", "branch", 4672, 2400); bp.connect(loop, "LoopBody", item_branch, "execute"); bp.connect(not_first, "ReturnValue", item_branch, "Condition")
    previous_index = math("Subtract_IntInt", loop, "Array Index", None, "1", 4416, 2640, "int")
    current_u = item(us, "TrajectoryArcInputUsV1", loop, "Array Index", 4672, 2800, "current_u")
    previous_u = item(us, "TrajectoryArcInputUsV1", previous_index, "ReturnValue", 4672, 2960, "previous_u")
    previous_d = item(distances, "TrajectoryArcInputDistancesV1", previous_index, "ReturnValue", 4672, 3120, "previous_d")
    sticky = get("TrajectoryArcScratchValidV1", "bool", 4672, 3280)
    sticky_wrap = b.add("sticky_wrap", "compare", 4928, 3280); scalar.retarget_function(sticky_wrap, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"): kind(sticky_wrap, pin, "bool")
    bp.connect(sticky, "TrajectoryArcScratchValidV1", sticky_wrap, "A"); scalar.set_default(sticky_wrap, "B", "true")
    valid_item = combine((
        sticky_wrap,
        b.finite(current_u, "Output", 4928, 2800),
        b.finite(loop, "Array Element", 4928, 3040),
        compare("Less_DoubleDouble", previous_u, "Output", current_u, "Output", 5152, 3360, "real"),
        compare("LessEqual_DoubleDouble", previous_d, "Output", loop, "Array Element", 5376, 3360, "real"),
    ), 5600, 3200)
    valid_branch = b.add("valid_item_branch", "branch", 6528, 2400); bp.connect(item_branch, "then", valid_branch, "execute"); bp.connect(valid_item, "ReturnValue", valid_branch, "Condition")
    item_fail = setv("TrajectoryArcScratchValidV1", "bool", 6752, 2640, "false"); bp.connect(valid_branch, "else", item_fail, "execute")
    upper = get("TrajectoryArcScratchUpperIndexV1", "int", 6528, 2880)
    choose = and_(
        compare("GreaterEqual_DoubleDouble", loop, "Array Element", target, "ReturnValue", 6752, 2880, "real"),
        compare("EqualEqual_IntInt", upper, "TrajectoryArcScratchUpperIndexV1", None, "-1", 6752, 3040, "int"),
        6976, 2960,
    )
    choose_branch = b.add("choose_branch", "branch", 7232, 2400); bp.connect(valid_branch, "then", choose_branch, "execute"); bp.connect(choose, "ReturnValue", choose_branch, "Condition")
    store_upper = setv("TrajectoryArcScratchUpperIndexV1", "int", 7488, 2400); bp.connect(choose_branch, "then", store_upper, "execute"); bp.connect(loop, "Array Index", store_upper, "TrajectoryArcScratchUpperIndexV1")

    final_sticky = get("TrajectoryArcScratchValidV1", "bool", 7488, 3280)
    final_upper = get("TrajectoryArcScratchUpperIndexV1", "int", 7488, 3440)
    zero_length = compare("LessEqual_DoubleDouble", total, "TrajectoryArcInputLengthV1", None, "1e-12", 7744, 3280, "real")
    found_upper = compare("GreaterEqual_IntInt", final_upper, "TrajectoryArcScratchUpperIndexV1", None, "1", 7744, 3440, "int")
    zero_or_found = b.add("zero_or_found", "compare", 8000, 3360); scalar.retarget_function(zero_or_found, "BooleanOR")
    for pin in ("A", "B", "ReturnValue"): kind(zero_or_found, pin, "bool")
    bp.connect(zero_length, "ReturnValue", zero_or_found, "A"); bp.connect(found_upper, "ReturnValue", zero_or_found, "B")
    final_valid = b.add("final_valid", "compare", 8256, 3360); scalar.retarget_function(final_valid, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"): kind(final_valid, pin, "bool")
    bp.connect(final_sticky, "TrajectoryArcScratchValidV1", final_valid, "A")
    bp.connect(zero_or_found, "ReturnValue", final_valid, "B")
    final_branch = b.add("final_branch", "branch", 8512, 2400); bp.connect(loop, "Completed", final_branch, "execute"); bp.connect(final_valid, "ReturnValue", final_branch, "Condition")
    zero_branch = b.add("zero_branch", "branch", 8768, 2400); bp.connect(final_branch, "then", zero_branch, "execute"); bp.connect(zero_length, "ReturnValue", zero_branch, "Condition")
    zero_result = setv("TrajectoryArcResultUV1", "real", 9024, 2240); zero_valid = setv("TrajectoryArcResultValidV1", "bool", 9280, 2240, "true")
    bp.connect(zero_branch, "then", zero_result, "execute"); bp.connect(clamped, "ReturnValue", zero_result, "TrajectoryArcResultUV1"); bp.connect(zero_result, "then", zero_valid, "execute")

    left_index = math("Subtract_IntInt", final_upper, "TrajectoryArcScratchUpperIndexV1", None, "1", 8768, 2800, "int")
    left_u = item(us, "TrajectoryArcInputUsV1", left_index, "ReturnValue", 9024, 2800, "left_u")
    right_u = item(us, "TrajectoryArcInputUsV1", final_upper, "TrajectoryArcScratchUpperIndexV1", 9024, 2960, "right_u")
    left_d = item(distances, "TrajectoryArcInputDistancesV1", left_index, "ReturnValue", 9024, 3120, "left_d")
    right_d = item(distances, "TrajectoryArcInputDistancesV1", final_upper, "TrajectoryArcScratchUpperIndexV1", 9024, 3280, "right_d")
    span = math("Subtract_DoubleDouble", right_d, "Output", left_d, "Output", 9280, 3200)
    plateau = compare("LessEqual_DoubleDouble", span, "ReturnValue", None, "1e-12", 9536, 3200, "real")
    plateau_branch = b.add("plateau_branch", "branch", 9792, 2400); bp.connect(zero_branch, "else", plateau_branch, "execute"); bp.connect(plateau, "ReturnValue", plateau_branch, "Condition")
    plateau_result = setv("TrajectoryArcResultUV1", "real", 10048, 2240); plateau_valid = setv("TrajectoryArcResultValidV1", "bool", 10304, 2240, "true")
    bp.connect(plateau_branch, "then", plateau_result, "execute"); bp.connect(left_u, "Output", plateau_result, "TrajectoryArcResultUV1"); bp.connect(plateau_result, "then", plateau_valid, "execute")
    relative = math("Subtract_DoubleDouble", target, "ReturnValue", left_d, "Output", 9792, 3440)
    fraction = math("Divide_DoubleDouble", relative, "ReturnValue", span, "ReturnValue", 10048, 3440)
    u_span = math("Subtract_DoubleDouble", right_u, "Output", left_u, "Output", 10304, 3440)
    scaled = math("Multiply_DoubleDouble", u_span, "ReturnValue", fraction, "ReturnValue", 10560, 3440)
    result = math("Add_DoubleDouble", left_u, "Output", scaled, "ReturnValue", 10816, 3440)
    store_result = setv("TrajectoryArcResultUV1", "real", 11072, 2400); store_valid = setv("TrajectoryArcResultValidV1", "bool", 11328, 2400, "true")
    bp.connect(plateau_branch, "else", store_result, "execute"); bp.connect(result, "ReturnValue", store_result, "TrajectoryArcResultUV1"); bp.connect(store_result, "then", store_valid, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
