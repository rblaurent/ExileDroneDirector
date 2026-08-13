"""Build the history-free absolute-time desired velocity sampler."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "SampleAirframeDesiredVelocityAtTimeV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_velocity_sampler_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin_name, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[value]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    linear = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    translation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-translation-input.eddgraph")
    vector_codec = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    forms.update({
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "floor": bp.find_block(linear, r'MemberName="FFloor"'),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        "select": bp.find_block(speed, r'MemberName="SelectFloat"'),
        "make_vector": bp.find_block(marker, r'MemberName="MakeVector"'),
        "vector_math": bp.find_block(translation, r'MemberName="Multiply_VectorVector"'),
        "break_vector": bp.find_block(vector_codec, r'MemberName="BreakVector"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, value, array=False):
        scalar.retarget_variable(node, name, "real" if value == "int" else value)
        kind(node, name, value, array)
        if "Output_Get" in node.pins:
            kind(node, "Output_Get", value)

    def get(name, value, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, value, array)
        return node

    def set_(name, value, x, y, default_value=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, value)
        if default_value is not None:
            scalar.set_default(node, name, default_value)
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, value in kinds.items():
            kind(node, pin, value)
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, value="real"):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": value, "B": value, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def and_all(conditions, x, y):
        first = conditions[0]
        current, current_pin = first if isinstance(first, tuple) else (first, "ReturnValue")
        for index, raw_condition in enumerate(conditions[1:]):
            condition, condition_pin = raw_condition if isinstance(raw_condition, tuple) else (raw_condition, "ReturnValue")
            current = compare("BooleanAND", current, current_pin, x + index * 208, y, condition, condition_pin, value="bool")
            current_pin = "ReturnValue"
        return current

    def math_node(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, value="real"):
        node = b.math("Add_DoubleDouble", x, y)
        retarget(node, member, {"A": value, "B": value, "ReturnValue": value})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def item(source, index, index_pin, x, y):
        node = b.add(f"item_{len(b.nodes)}", "item", x, y)
        kind(node, "Array", "vector", True)
        kind(node, "Output", "vector")
        bp.connect(velocities, "AirframeDesiredStreamCandidateVelocitiesV1", node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def make_uniform(value, value_pin, x, y):
        node = b.add(f"uniform_{len(b.nodes)}", "make_vector", x, y)
        for axis in "XYZ":
            bp.connect(value, value_pin, node, axis)
        return node

    def vector_math(member, left, left_pin, right, right_pin, x, y):
        node = b.add(f"vector_{member}_{len(b.nodes)}", "vector_math", x, y)
        retarget(node, member, {"A": "vector", "B": "vector", "ReturnValue": "vector"})
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def finite_vector(value, value_pin, x, y):
        broken = b.add(f"break_{len(b.nodes)}", "break_vector", x, y)
        bp.connect(value, value_pin, broken, "InVec")
        return and_all([b.finite(broken, axis, x + 224, y + index * 160) for index, axis in enumerate("XYZ")], x + 704, y)

    reset_result = set_("AirframeDesiredStreamVelocitySampleResultV1", "vector", 256, 2400, "0, 0, 0")
    reset_valid = set_("AirframeDesiredStreamVelocitySampleResultValidV1", "bool", 512, 2400, "false")
    bp.connect(b.entry, "then", reset_result, "execute")
    bp.connect(reset_result, "then", reset_valid, "execute")
    velocities = get("AirframeDesiredStreamCandidateVelocitiesV1", "vector", 0, 0, True)
    elapsed = get("AirframeDesiredStreamVelocitySampleInputSecondsV1", "real", 0, 240)
    total = get("AirframeDesiredStreamInputTotalSecondsV1", "real", 0, 480)
    step = get("AirframeDesiredStreamInputFixedStepSecondsV1", "real", 0, 720)
    stage = get("AirframeDesiredStreamStageValidV1", "bool", 0, 960)
    length = b.add("length", "length", 320, 0)
    kind(length, "TargetArray", "vector", True)
    bp.connect(velocities, "AirframeDesiredStreamCandidateVelocitiesV1", length, "TargetArray")
    count_minus_two = math_node("Subtract_IntInt", length, "ReturnValue", 640, 0, default_b="2", value="int")
    count_minus_one = math_node("Subtract_IntInt", length, "ReturnValue", 640, 160, default_b="1", value="int")
    convert_minus_two = b.add("convert_minus_two", "convert", 896, 0); bp.connect(count_minus_two, "ReturnValue", convert_minus_two, "InInt")
    convert_minus_one = b.add("convert_minus_one", "convert", 896, 160); bp.connect(count_minus_one, "ReturnValue", convert_minus_one, "InInt")
    lower_schedule = math_node("Multiply_DoubleDouble", convert_minus_two, "ReturnValue", 1152, 0, step, "AirframeDesiredStreamInputFixedStepSecondsV1")
    upper_schedule = math_node("Multiply_DoubleDouble", convert_minus_one, "ReturnValue", 1152, 160, step, "AirframeDesiredStreamInputFixedStepSecondsV1")
    shape = and_all([
        (stage, "AirframeDesiredStreamStageValidV1"),
        b.finite(elapsed, "AirframeDesiredStreamVelocitySampleInputSecondsV1", 320, 240),
        compare("GreaterEqual_IntInt", length, "ReturnValue", 640, 400, default_b="2", value="int"),
        compare("LessEqual_IntInt", length, "ReturnValue", 640, 520, default_b="65536", value="int"),
        b.finite(total, "AirframeDesiredStreamInputTotalSecondsV1", 320, 640),
        compare("Greater_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 640, 640, default_b="0.0"),
        compare("LessEqual_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 640, 760, default_b="3600.0"),
        b.finite(step, "AirframeDesiredStreamInputFixedStepSecondsV1", 320, 880),
        compare("GreaterEqual_DoubleDouble", step, "AirframeDesiredStreamInputFixedStepSecondsV1", 640, 880, default_b="0.004166666666666667"),
        compare("LessEqual_DoubleDouble", step, "AirframeDesiredStreamInputFixedStepSecondsV1", 640, 1000, default_b="0.5"),
        compare("Less_DoubleDouble", lower_schedule, "ReturnValue", 1408, 0, total, "AirframeDesiredStreamInputTotalSecondsV1"),
        compare("LessEqual_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 1408, 160, upper_schedule, "ReturnValue"),
    ], 1664, 1120)
    shape_branch = b.add("shape_branch", "branch", 3968, 2400)
    bp.connect(reset_valid, "then", shape_branch, "execute")
    bp.connect(shape, "ReturnValue", shape_branch, "Condition")
    complete = compare("GreaterEqual_DoubleDouble", elapsed, "AirframeDesiredStreamVelocitySampleInputSecondsV1", 4224, 2080, total, "AirframeDesiredStreamInputTotalSecondsV1")
    complete_branch = b.add("complete_branch", "branch", 4224, 2400)
    bp.connect(shape_branch, "then", complete_branch, "execute")
    bp.connect(complete, "ReturnValue", complete_branch, "Condition")
    last_value = item(velocities, count_minus_one, "ReturnValue", 4480, 1920)
    last_finite = finite_vector(last_value, "Output", 4480, 1600)
    complete_guard = b.add("complete_guard", "branch", 5504, 2400)
    bp.connect(complete_branch, "then", complete_guard, "execute")
    bp.connect(last_finite, "ReturnValue", complete_guard, "Condition")
    complete_result = set_("AirframeDesiredStreamVelocitySampleResultV1", "vector", 5760, 2400)
    complete_valid = set_("AirframeDesiredStreamVelocitySampleResultValidV1", "bool", 6016, 2400, "true")
    bp.connect(complete_guard, "then", complete_result, "execute")
    bp.connect(last_value, "Output", complete_result, "AirframeDesiredStreamVelocitySampleResultV1")
    bp.connect(complete_result, "then", complete_valid, "execute")

    clamped = b.add("clamped", "clamp", 4480, 2880)
    scalar.set_default(clamped, "Min", "0.0")
    bp.connect(elapsed, "AirframeDesiredStreamVelocitySampleInputSecondsV1", clamped, "Value")
    bp.connect(total, "AirframeDesiredStreamInputTotalSecondsV1", clamped, "Max")
    quotient = math_node("Divide_DoubleDouble", clamped, "ReturnValue", 4736, 2880, step, "AirframeDesiredStreamInputFixedStepSecondsV1")
    floor = b.add("floor", "floor", 4992, 2880); bp.connect(quotient, "ReturnValue", floor, "A")
    index_real = b.add("index_real", "convert", 5248, 2880); bp.connect(floor, "ReturnValue", index_real, "InInt")
    start_time = math_node("Multiply_DoubleDouble", index_real, "ReturnValue", 5504, 2880, step, "AirframeDesiredStreamInputFixedStepSecondsV1")
    relative = math_node("Subtract_DoubleDouble", clamped, "ReturnValue", 5760, 2880, start_time, "ReturnValue")
    is_terminal = compare("EqualEqual_IntInt", floor, "ReturnValue", 5504, 3120, count_minus_two, "ReturnValue", value="int")
    terminal_duration = math_node("Subtract_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 5760, 3120, start_time, "ReturnValue")
    duration = b.add("duration", "select", 6016, 3120)
    bp.connect(terminal_duration, "ReturnValue", duration, "A")
    bp.connect(step, "AirframeDesiredStreamInputFixedStepSecondsV1", duration, "B")
    bp.connect(is_terminal, "ReturnValue", duration, "bPickA")
    alpha = math_node("Divide_DoubleDouble", relative, "ReturnValue", 6272, 2880, duration, "ReturnValue")
    next_index = math_node("Add_IntInt", floor, "ReturnValue", 6016, 3360, default_b="1", value="int")
    left = item(velocities, floor, "ReturnValue", 6272, 3280)
    right = item(velocities, next_index, "ReturnValue", 6272, 3440)
    delta = vector_math("Subtract_VectorVector", right, "Output", left, "Output", 6528, 3360)
    alpha_vector = make_uniform(alpha, "ReturnValue", 6528, 3600)
    scaled = vector_math("Multiply_VectorVector", delta, "ReturnValue", alpha_vector, "ReturnValue", 6784, 3440)
    result = vector_math("Add_VectorVector", left, "Output", scaled, "ReturnValue", 7040, 3360)
    result_finite = finite_vector(result, "ReturnValue", 7296, 3200)
    result_branch = b.add("result_branch", "branch", 8320, 2880)
    bp.connect(complete_branch, "else", result_branch, "execute")
    bp.connect(result_finite, "ReturnValue", result_branch, "Condition")
    active_result = set_("AirframeDesiredStreamVelocitySampleResultV1", "vector", 8576, 2880)
    active_valid = set_("AirframeDesiredStreamVelocitySampleResultValidV1", "bool", 8832, 2880, "true")
    bp.connect(result_branch, "then", active_result, "execute")
    bp.connect(result, "ReturnValue", active_result, "AirframeDesiredStreamVelocitySampleResultV1")
    bp.connect(active_result, "then", active_valid, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
