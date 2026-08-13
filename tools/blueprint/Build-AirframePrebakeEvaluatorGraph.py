"""Build fail-closed absolute-time evaluation of compiled airframe/gimbal samples."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "EvaluateCompiledAirframePrebakeV1"
RESULTS = (
    ("AirframePrebakeResultSegmentIndexV1", "int", "-1"),
    ("AirframePrebakeResultAlphaV1", "real", "0.0"),
    ("AirframePrebakeResultBodyQuatV1", "quat", "0, 0, 0, 1"),
    ("AirframePrebakeResultGimbalQuatV1", "quat", "0, 0, 0, 1"),
    ("AirframePrebakeResultCompleteV1", "bool", "false"),
    ("AirframePrebakeResultValidV1", "bool", "false"),
)
ARRAYS = (
    ("AirframePrebakeCompiledBodyQuatsV1", "quat"),
    ("AirframePrebakeCompiledGimbalQuatsV1", "quat"),
    ("AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1", "real"),
    ("AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1", "real"),
    ("AirframePrebakeCompiledBodyRateLimitedV1", "bool"),
    ("AirframePrebakeCompiledGimbalRateLimitedV1", "bool"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_eval_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[value]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    linear_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    quaternion = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    quaternion_eval = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "floor": bp.find_block(linear_forms, r'MemberName="FFloor"'),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        "quat_finite": bp.find_block(quaternion_eval, r'MemberName="Quat_IsFinite"'),
        "quat_size": bp.find_block(quaternion, r'MemberName="Quat_Size"'),
        "slerp": bp.find_block(quaternion_eval, r'MemberName="Quat_Slerp"'),
        "select": bp.find_block(speed, r'MemberName="SelectFloat"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, value, array=False):
        scalar.retarget_variable(node, name, "vector" if value == "quat" else ("real" if value == "int" else value))
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

    def length(source, source_pin, value, x, y):
        node = b.add(f"length_{len(b.nodes)}", "length", x, y)
        kind(node, "TargetArray", value, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin, value, index, index_pin, x, y):
        node = b.add(f"item_{len(b.nodes)}", "item", x, y)
        kind(node, "Array", value, True)
        kind(node, "Output", value)
        bp.connect(source, source_pin, node, "Array")
        if index is None:
            scalar.set_default(node, "Dimension 1", index_pin)
        else:
            bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def compare(member, left, left_pin, right, right_pin, value, x, y):
        node = b.add(f"compare_{len(b.nodes)}", "compare", x, y)
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

    def and_(left, left_pin, right, right_pin, x, y):
        return compare("BooleanAND", left, left_pin, right, right_pin, "bool", x, y)

    def and_all(guards, x, y):
        current, pin = guards[0]
        for index, (guard, guard_pin) in enumerate(guards[1:]):
            current = and_(current, pin, guard, guard_pin, x + index * 208, y)
            pin = "ReturnValue"
        return current

    def math_node(member, left, left_pin, right, right_pin, value, x, y):
        node = b.math("Add_DoubleDouble", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            kind(node, pin, value)
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def foreach(source, source_pin, value, x, y):
        node = b.add(f"foreach_{len(b.nodes)}", "foreach", x, y)
        kind(node, "Array", value, True)
        kind(node, "Array Element", value)
        bp.connect(source, source_pin, node, "Array")
        return node

    resets = [set_(name, value, 256 + index * 256, 2560, default) for index, (name, value, default) in enumerate(RESULTS)]
    bp.connect(b.entry, "then", resets[0], "execute")
    for left, right in zip(resets, resets[1:]):
        bp.connect(left, "then", right, "execute")

    arrays = {}
    lengths = {}
    for index, (name, value) in enumerate(ARRAYS):
        arrays[name] = get(name, value, 0, index * 160, True)
        lengths[name] = length(arrays[name], name, value, 320, index * 160)
    body_name = ARRAYS[0][0]
    count = lengths[body_name]
    elapsed = get("AirframePrebakeInputElapsedSecondsV1", "real", 0, 1120)
    compile_valid = get("AirframePrebakeCompileValidV1", "bool", 0, 1280)
    step = get("AirframePrebakeCompiledFixedStepSecondsV1", "real", 0, 1440)
    total = get("AirframePrebakeCompiledTotalSecondsV1", "real", 0, 1600)

    shape_guards = [
        (compile_valid, "AirframePrebakeCompileValidV1"),
        (b.finite(elapsed, "AirframePrebakeInputElapsedSecondsV1", 640, 1120), "ReturnValue"),
        (compare("GreaterEqual_IntInt", count, "ReturnValue", None, "2", "int", 640, 0), "ReturnValue"),
        (compare("LessEqual_IntInt", count, "ReturnValue", None, "65536", "int", 640, 128), "ReturnValue"),
    ]
    for index, (name, _value) in enumerate(ARRAYS[1:]):
        shape_guards.append((compare("EqualEqual_IntInt", lengths[name], "ReturnValue", count, "ReturnValue", "int", 640, 320 + index * 160), "ReturnValue"))
    shape_guards.extend((
        (b.finite(total, "AirframePrebakeCompiledTotalSecondsV1", 640, 1600), "ReturnValue"),
        (compare("Greater_DoubleDouble", total, "AirframePrebakeCompiledTotalSecondsV1", None, "0.0", "real", 864, 1600), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", total, "AirframePrebakeCompiledTotalSecondsV1", None, "3600.0", "real", 1088, 1600), "ReturnValue"),
        (b.finite(step, "AirframePrebakeCompiledFixedStepSecondsV1", 640, 1760), "ReturnValue"),
        (compare("GreaterEqual_DoubleDouble", step, "AirframePrebakeCompiledFixedStepSecondsV1", None, "0.004166666666666667", "real", 1088, 1760), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", step, "AirframePrebakeCompiledFixedStepSecondsV1", None, "0.5", "real", 1312, 1760), "ReturnValue"),
    ))
    count_minus_two = math_node("Subtract_IntInt", count, "ReturnValue", None, "2", "int", 640, 1920)
    count_minus_one = math_node("Subtract_IntInt", count, "ReturnValue", None, "1", "int", 640, 2080)
    convert_minus_two = b.add("convert_minus_two", "convert", 896, 1920); bp.connect(count_minus_two, "ReturnValue", convert_minus_two, "InInt")
    convert_minus_one = b.add("convert_minus_one", "convert", 896, 2080); bp.connect(count_minus_one, "ReturnValue", convert_minus_one, "InInt")
    lower_time = math_node("Multiply_DoubleDouble", convert_minus_two, "ReturnValue", step, "AirframePrebakeCompiledFixedStepSecondsV1", "real", 1152, 1920)
    upper_time = math_node("Multiply_DoubleDouble", convert_minus_one, "ReturnValue", step, "AirframePrebakeCompiledFixedStepSecondsV1", "real", 1152, 2080)
    shape_guards.extend((
        (compare("Less_DoubleDouble", lower_time, "ReturnValue", total, "AirframePrebakeCompiledTotalSecondsV1", "real", 1408, 1920), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", total, "AirframePrebakeCompiledTotalSecondsV1", upper_time, "ReturnValue", "real", 1408, 2080), "ReturnValue"),
    ))
    shape = and_all(shape_guards, 1792, 2080)
    shape_branch = b.add("shape_branch", "branch", 4928, 2560)
    bp.connect(resets[-1], "then", shape_branch, "execute")
    bp.connect(shape, "ReturnValue", shape_branch, "Condition")
    accept_shape = set_("AirframePrebakeResultValidV1", "bool", 5184, 2560, "true")
    bp.connect(shape_branch, "then", accept_shape, "execute")

    loops = []
    rejection_sets = []
    for index, (name, value) in enumerate(ARRAYS[:4]):
        loop = foreach(arrays[name], name, value, 5440 + index * 896, 2560)
        loops.append(loop)
        if value == "quat":
            finite = b.add(f"quat_finite_{index}", "quat_finite", 5440 + index * 896, 2240)
            size = b.add(f"quat_size_{index}", "quat_size", 5664 + index * 896, 2240)
            bp.connect(loop, "Array Element", finite, "Q"); bp.connect(loop, "Array Element", size, "Q")
            lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", None, "0.999999", "real", 5888 + index * 896, 2160)
            upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", None, "1.000001", "real", 5888 + index * 896, 2320)
            condition = and_all(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")), 6112 + index * 896, 2240)
        else:
            finite = b.finite(loop, "Array Element", 5440 + index * 896, 2240)
            lower = compare("GreaterEqual_DoubleDouble", loop, "Array Element", None, "0.0", "real", 5664 + index * 896, 2160)
            upper = compare("LessEqual_DoubleDouble", loop, "Array Element", None, "720.0000001", "real", 5664 + index * 896, 2320)
            condition = and_all(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")), 5888 + index * 896, 2240)
        branch = b.add(f"item_branch_{index}", "branch", 6560 + index * 896, 2560)
        bp.connect(loop, "LoopBody", branch, "execute"); bp.connect(condition, "ReturnValue", branch, "Condition")
        reject = set_("AirframePrebakeResultValidV1", "bool", 6816 + index * 896, 2784, "false")
        bp.connect(branch, "else", reject, "execute")
        rejection_sets.append(reject)
    bp.connect(accept_shape, "then", loops[0], "Exec")
    for left, right in zip(loops, loops[1:]):
        bp.connect(left, "Completed", right, "Exec")

    body_rate_zero = item(arrays[ARRAYS[2][0]], ARRAYS[2][0], "real", None, "0", 9088, 1920)
    gimbal_rate_zero = item(arrays[ARRAYS[3][0]], ARRAYS[3][0], "real", None, "0", 9088, 2080)
    body_flag_zero = item(arrays[ARRAYS[4][0]], ARRAYS[4][0], "bool", None, "0", 9088, 2240)
    gimbal_flag_zero = item(arrays[ARRAYS[5][0]], ARRAYS[5][0], "bool", None, "0", 9088, 2400)
    sticky = get("AirframePrebakeResultValidV1", "bool", 9088, 2560)
    post_guards = (
        (sticky, "AirframePrebakeResultValidV1"),
        (compare("EqualEqual_DoubleDouble", body_rate_zero, "Output", None, "0.0", "real", 9344, 1920), "ReturnValue"),
        (compare("EqualEqual_DoubleDouble", gimbal_rate_zero, "Output", None, "0.0", "real", 9344, 2080), "ReturnValue"),
        (compare("EqualEqual_BoolBool", body_flag_zero, "Output", None, "false", "bool", 9344, 2240), "ReturnValue"),
        (compare("EqualEqual_BoolBool", gimbal_flag_zero, "Output", None, "false", "bool", 9344, 2400), "ReturnValue"),
    )
    post_valid = and_all(post_guards, 9600, 2560)
    post_branch = b.add("post_branch", "branch", 10624, 2560)
    bp.connect(loops[-1], "Completed", post_branch, "execute"); bp.connect(post_valid, "ReturnValue", post_branch, "Condition")
    post_reject = set_("AirframePrebakeResultValidV1", "bool", 10880, 2816, "false")
    bp.connect(post_branch, "else", post_reject, "execute")

    complete_test = compare("GreaterEqual_DoubleDouble", elapsed, "AirframePrebakeInputElapsedSecondsV1", total, "AirframePrebakeCompiledTotalSecondsV1", "real", 10880, 2320)
    complete_branch = b.add("complete_branch", "branch", 10880, 2560)
    bp.connect(post_branch, "then", complete_branch, "execute"); bp.connect(complete_test, "ReturnValue", complete_branch, "Condition")
    body_last = item(arrays[ARRAYS[0][0]], ARRAYS[0][0], "quat", count_minus_one, "ReturnValue", 11136, 1920)
    gimbal_last = item(arrays[ARRAYS[1][0]], ARRAYS[1][0], "quat", count_minus_one, "ReturnValue", 11136, 2080)
    complete_sets = [
        set_("AirframePrebakeResultSegmentIndexV1", "int", 11136, 2560),
        set_("AirframePrebakeResultAlphaV1", "real", 11392, 2560, "1.0"),
        set_("AirframePrebakeResultBodyQuatV1", "quat", 11648, 2560),
        set_("AirframePrebakeResultGimbalQuatV1", "quat", 11904, 2560),
        set_("AirframePrebakeResultCompleteV1", "bool", 12160, 2560, "true"),
        set_("AirframePrebakeResultValidV1", "bool", 12416, 2560, "true"),
    ]
    bp.connect(complete_branch, "then", complete_sets[0], "execute")
    bp.connect(count_minus_two, "ReturnValue", complete_sets[0], RESULTS[0][0])
    bp.connect(body_last, "Output", complete_sets[2], RESULTS[2][0]); bp.connect(gimbal_last, "Output", complete_sets[3], RESULTS[3][0])
    for left, right in zip(complete_sets, complete_sets[1:]):
        bp.connect(left, "then", right, "execute")

    clamped = b.add("clamped", "clamp", 11136, 3200)
    scalar.set_default(clamped, "Min", "0.0"); bp.connect(elapsed, "AirframePrebakeInputElapsedSecondsV1", clamped, "Value"); bp.connect(total, "AirframePrebakeCompiledTotalSecondsV1", clamped, "Max")
    quotient = math_node("Divide_DoubleDouble", clamped, "ReturnValue", step, "AirframePrebakeCompiledFixedStepSecondsV1", "real", 11392, 3200)
    floor = b.add("floor", "floor", 11648, 3200); bp.connect(quotient, "ReturnValue", floor, "A")
    index_real = b.add("index_real", "convert", 11904, 3200); bp.connect(floor, "ReturnValue", index_real, "InInt")
    start_time = math_node("Multiply_DoubleDouble", index_real, "ReturnValue", step, "AirframePrebakeCompiledFixedStepSecondsV1", "real", 12160, 3200)
    relative = math_node("Subtract_DoubleDouble", clamped, "ReturnValue", start_time, "ReturnValue", "real", 12416, 3200)
    is_terminal = compare("EqualEqual_IntInt", floor, "ReturnValue", count_minus_two, "ReturnValue", "int", 12160, 3440)
    terminal_duration = math_node("Subtract_DoubleDouble", total, "AirframePrebakeCompiledTotalSecondsV1", start_time, "ReturnValue", "real", 12416, 3440)
    duration = b.add("duration", "select", 12672, 3440)
    bp.connect(terminal_duration, "ReturnValue", duration, "A"); bp.connect(step, "AirframePrebakeCompiledFixedStepSecondsV1", duration, "B"); bp.connect(is_terminal, "ReturnValue", duration, "bPickA")
    alpha = math_node("Divide_DoubleDouble", relative, "ReturnValue", duration, "ReturnValue", "real", 12928, 3200)
    next_index = math_node("Add_IntInt", floor, "ReturnValue", None, "1", "int", 12672, 3680)
    body_start = item(arrays[ARRAYS[0][0]], ARRAYS[0][0], "quat", floor, "ReturnValue", 12928, 3520)
    body_end = item(arrays[ARRAYS[0][0]], ARRAYS[0][0], "quat", next_index, "ReturnValue", 12928, 3680)
    gimbal_start = item(arrays[ARRAYS[1][0]], ARRAYS[1][0], "quat", floor, "ReturnValue", 12928, 3840)
    gimbal_end = item(arrays[ARRAYS[1][0]], ARRAYS[1][0], "quat", next_index, "ReturnValue", 12928, 4000)
    body_slerp = b.add("body_slerp", "slerp", 13216, 3520)
    gimbal_slerp = b.add("gimbal_slerp", "slerp", 13216, 3840)
    for node, start, end in ((body_slerp, body_start, body_end), (gimbal_slerp, gimbal_start, gimbal_end)):
        bp.connect(start, "Output", node, "A"); bp.connect(end, "Output", node, "B"); bp.connect(alpha, "ReturnValue", node, "Alpha")
    active_sets = [
        set_("AirframePrebakeResultSegmentIndexV1", "int", 13472, 3200),
        set_("AirframePrebakeResultAlphaV1", "real", 13728, 3200),
        set_("AirframePrebakeResultBodyQuatV1", "quat", 13984, 3200),
        set_("AirframePrebakeResultGimbalQuatV1", "quat", 14240, 3200),
        set_("AirframePrebakeResultCompleteV1", "bool", 14496, 3200, "false"),
        set_("AirframePrebakeResultValidV1", "bool", 14752, 3200, "true"),
    ]
    bp.connect(complete_branch, "else", active_sets[0], "execute")
    bp.connect(floor, "ReturnValue", active_sets[0], RESULTS[0][0]); bp.connect(alpha, "ReturnValue", active_sets[1], RESULTS[1][0])
    bp.connect(body_slerp, "ReturnValue", active_sets[2], RESULTS[2][0]); bp.connect(gimbal_slerp, "ReturnValue", active_sets[3], RESULTS[3][0])
    for left, right in zip(active_sets, active_sets[1:]):
        bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
