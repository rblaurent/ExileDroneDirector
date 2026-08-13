"""Build fail-closed validation for fixed-step airframe/gimbal prebake inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateAirframePrebakeInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_validation_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
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
    builder = scalar.Builder(bp, forms, FUNCTION)

    raw = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    quaternion = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    quaternion_eval = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    foreach_form = bp.find_block(raw, r"K2Node_MacroInstance")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')
    quat_finite_form = bp.find_block(quaternion_eval, r'MemberName="Quat_IsFinite"')
    quat_size_form = bp.find_block(quaternion, r'MemberName="Quat_Size"')
    int_to_double_form = bp.find_block(playback, r'MemberName="Conv_IntToDouble"')

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def retarget_call(node, member, pin_types):
        scalar.retarget_function(node, member)
        for pin, kind in pin_types.items():
            pin_kind(node, pin, kind)
        return node

    def array_get(name, kind, x, y):
        node = builder.get(name, "real" if kind == "real" else "vector", x, y)
        scalar.retarget_variable(node, name, "real" if kind == "real" else "vector")
        pin_kind(node, name, kind, True)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)
        return node

    def scalar_get(name, kind, x, y):
        node = builder.get(name, kind, x, y)
        return node

    def array_length(source, source_pin, kind, x, y):
        node = add_form(f"length_{source_pin}", length_form, x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def foreach(source, source_pin, kind, x, y):
        node = add_form(f"foreach_{source_pin}", foreach_form, x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Array Element", kind)
        bp.connect(source, source_pin, node, "Array")
        return node

    def compare(member, left, left_pin, x, y, kind="real", right=None, right_pin=None, default_b=None):
        node = builder.add(f"compare_{member}_{len(builder.nodes)}", "compare", x, y)
        retarget_call(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default_b is not None:
            scalar.set_default(node, "B", default_b)
        return node

    def int_math(member, source, source_pin, amount, x, y):
        node = builder.math("Subtract_DoubleDouble", x, y)
        retarget_call(node, member, {"A": "int", "B": "int", "ReturnValue": "int"})
        bp.connect(source, source_pin, node, "A")
        scalar.set_default(node, "B", amount)
        return node

    def convert_int(source, source_pin, x, y):
        node = add_form(f"convert_{len(builder.nodes)}", int_to_double_form, x, y)
        bp.connect(source, source_pin, node, "InInt")
        return node

    def multiply(left, left_pin, right, right_pin, x, y):
        node = builder.math("Multiply_DoubleDouble", x, y)
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def boolean_and(left, right, x, y):
        node = builder.add(f"and_{len(builder.nodes)}", "compare", x, y)
        retarget_call(node, "BooleanAND", {"A": "bool", "B": "bool", "ReturnValue": "bool"})
        bp.connect(left, "ReturnValue", node, "A")
        bp.connect(right, "ReturnValue", node, "B")
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = boolean_and(current, condition, x + index * 224, y)
        return current

    reset = builder.set("AirframePrebakeStageValidV1", "bool", 256, 3040, "false")
    bp.connect(builder.entry, "then", reset, "execute")
    bodies = array_get("AirframePrebakeInputDesiredBodyQuatsV1", "quat", 0, 160)
    gimbals = array_get("AirframePrebakeInputDesiredGimbalQuatsV1", "quat", 0, 400)
    rates = array_get("AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real", 0, 640)
    total = scalar_get("AirframePrebakeInputTotalSecondsV1", "real", 0, 880)
    step = scalar_get("AirframePrebakeInputFixedStepSecondsV1", "real", 0, 1120)
    body_count = array_length(bodies, "AirframePrebakeInputDesiredBodyQuatsV1", "quat", 320, 160)
    gimbal_count = array_length(gimbals, "AirframePrebakeInputDesiredGimbalQuatsV1", "quat", 320, 400)
    rate_count = array_length(rates, "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real", 320, 640)

    conditions = [
        compare("GreaterEqual_IntInt", body_count, "ReturnValue", 640, 80, "int", default_b="2"),
        compare("LessEqual_IntInt", body_count, "ReturnValue", 640, 208, "int", default_b="65536"),
        compare("EqualEqual_IntInt", gimbal_count, "ReturnValue", 640, 400, "int", body_count, "ReturnValue"),
        compare("EqualEqual_IntInt", rate_count, "ReturnValue", 640, 640, "int", body_count, "ReturnValue"),
        builder.finite(total, "AirframePrebakeInputTotalSecondsV1", 640, 864),
        compare("Greater_DoubleDouble", total, "AirframePrebakeInputTotalSecondsV1", 1088, 864, default_b="0.0"),
        compare("LessEqual_DoubleDouble", total, "AirframePrebakeInputTotalSecondsV1", 1312, 864, default_b="3600.0"),
        builder.finite(step, "AirframePrebakeInputFixedStepSecondsV1", 640, 1120),
        compare("GreaterEqual_DoubleDouble", step, "AirframePrebakeInputFixedStepSecondsV1", 1088, 1120, default_b="0.004166666666666667"),
        compare("LessEqual_DoubleDouble", step, "AirframePrebakeInputFixedStepSecondsV1", 1312, 1120, default_b="0.5"),
    ]
    minus_two = int_math("Subtract_IntInt", body_count, "ReturnValue", "2", 640, 1360)
    minus_one = int_math("Subtract_IntInt", body_count, "ReturnValue", "1", 640, 1520)
    lower_index = convert_int(minus_two, "ReturnValue", 896, 1360)
    upper_index = convert_int(minus_one, "ReturnValue", 896, 1520)
    lower_time = multiply(lower_index, "ReturnValue", step, "AirframePrebakeInputFixedStepSecondsV1", 1152, 1360)
    upper_time = multiply(upper_index, "ReturnValue", step, "AirframePrebakeInputFixedStepSecondsV1", 1152, 1520)
    conditions.extend((
        compare("Less_DoubleDouble", lower_time, "ReturnValue", 1408, 1360, right=total, right_pin="AirframePrebakeInputTotalSecondsV1"),
        compare("LessEqual_DoubleDouble", total, "AirframePrebakeInputTotalSecondsV1", 1408, 1520, right=upper_time, right_pin="ReturnValue"),
    ))

    all_shape = and_all(conditions, 1792, 1760)
    shape_branch = builder.add("shape_branch", "branch", 4608, 3040)
    bp.connect(reset, "then", shape_branch, "execute")
    bp.connect(all_shape, "ReturnValue", shape_branch, "Condition")
    accept = builder.set("AirframePrebakeStageValidV1", "bool", 4864, 3040, "true")
    bp.connect(shape_branch, "then", accept, "execute")

    def quaternion_loop(source, source_pin, previous, previous_pin, x, y, label):
        loop = foreach(source, source_pin, "quat", x, y)
        bp.connect(previous, previous_pin, loop, "Exec")
        finite = add_form(f"finite_{label}", quat_finite_form, x + 288, y - 96)
        pin_kind(finite, "Q", "quat")
        pin_kind(finite, "ReturnValue", "bool")
        bp.connect(loop, "Array Element", finite, "Q")
        size = add_form(f"size_{label}", quat_size_form, x + 288, y + 96)
        pin_kind(size, "Q", "quat")
        pin_kind(size, "ReturnValue", "real")
        bp.connect(loop, "Array Element", size, "Q")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", x + 544, y + 32, default_b="0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", x + 544, y + 160, default_b="1.000001")
        valid = and_all((finite, lower, upper), x + 800, y)
        branch = builder.add(f"{label}_branch", "branch", x + 1280, y)
        bp.connect(loop, "LoopBody", branch, "execute")
        bp.connect(valid, "ReturnValue", branch, "Condition")
        reject = builder.set("AirframePrebakeStageValidV1", "bool", x + 1536, y + 192, "false")
        bp.connect(branch, "else", reject, "execute")
        return loop

    body_loop = quaternion_loop(bodies, "AirframePrebakeInputDesiredBodyQuatsV1", accept, "then", 5120, 480, "body")
    gimbal_loop = quaternion_loop(gimbals, "AirframePrebakeInputDesiredGimbalQuatsV1", body_loop, "Completed", 7168, 1120, "gimbal")
    rate_loop = foreach(rates, "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real", 9216, 2080)
    bp.connect(gimbal_loop, "Completed", rate_loop, "Exec")
    rate_finite = builder.finite(rate_loop, "Array Element", 9504, 1920)
    rate_positive = compare("Greater_DoubleDouble", rate_loop, "Array Element", 9952, 2080, default_b="0.0")
    rate_upper = compare("LessEqual_DoubleDouble", rate_loop, "Array Element", 9952, 2240, default_b="720.0")
    rate_valid = and_all((rate_finite, rate_positive, rate_upper), 10208, 2080)
    rate_branch = builder.add("rate_branch", "branch", 10688, 2080)
    bp.connect(rate_loop, "LoopBody", rate_branch, "execute")
    bp.connect(rate_valid, "ReturnValue", rate_branch, "Condition")
    rate_reject = builder.set("AirframePrebakeStageValidV1", "bool", 10944, 2272, "false")
    bp.connect(rate_branch, "else", rate_reject, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
