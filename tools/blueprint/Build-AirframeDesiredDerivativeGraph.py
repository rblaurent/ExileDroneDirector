"""Build one deterministic desired-stream vector derivative stage.

Velocity, acceleration, and jerk intentionally share this generator so their
Blueprint bodies cannot drift from the accepted local-quadratic operator.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


STAGES = {
    "velocity": (
        "BuildAirframeDesiredVelocitySamplesV1",
        "AirframeDesiredStreamInputPositionsV1",
        "AirframeDesiredStreamCandidateVelocitiesV1",
    ),
    "acceleration": (
        "BuildAirframeDesiredAccelerationSamplesV1",
        "AirframeDesiredStreamCandidateVelocitiesV1",
        "AirframeDesiredStreamCandidateAccelerationsV1",
    ),
    "jerk": (
        "BuildAirframeDesiredJerkSamplesV1",
        "AirframeDesiredStreamCandidateAccelerationsV1",
        "AirframeDesiredStreamCandidateJerksV1",
    ),
}


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_derivative_base", path)
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
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    function, source_name, target_name = STAGES[args.stage]
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-desired-stream-v1.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    translation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-translation-input.eddgraph")
    vector_codec = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    forms.update({
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "array_length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "array_item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        "loop": bp.find_block(loops, r"StandardMacros:ForLoopWithBreak"),
        "make_vector": bp.find_block(marker, r'MemberName="MakeVector"'),
        "vector_math": bp.find_block(translation, r'MemberName="Multiply_VectorVector"'),
        "break_vector": bp.find_block(vector_codec, r'MemberName="BreakVector"'),
        "select": bp.find_block(speed, r'MemberName="SelectFloat"'),
    })
    b = scalar.Builder(bp, forms, function)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        if value is not None:
            scalar.set_default(node, name, value)
        return node

    def array_node(form, kind, x, y, source, source_pin):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y)
        target_pin = "TargetArray" if form in ("array_add", "array_clear", "array_length") else "Array"
        pin_kind(node, target_pin, kind, True)
        if form == "array_add":
            pin_kind(node, "NewItem", kind)
            pin_kind(node, "ReturnValue", "int")
        elif form == "array_length":
            pin_kind(node, "ReturnValue", "int")
        elif form == "array_item":
            pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, target_pin)
        return node

    def item(source, source_pin, index, index_pin, x, y):
        node = array_node("array_item", "vector", x, y, source, source_pin)
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def add_item(target, value, exec_source, exec_pin, x, y):
        node = array_node("array_add", "vector", x, y, target, target_name)
        bp.connect(value, "ReturnValue", node, "NewItem")
        bp.connect(exec_source, exec_pin, node, "execute")
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def math(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.math("Add_DoubleDouble", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": kind})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default_b is not None:
            scalar.set_default(node, "B", default_b)
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def select_int(condition, when_true, true_pin, when_false, false_pin, x, y, default_true=None):
        node = b.add(f"select_{len(b.nodes)}", "select", x, y)
        retarget(node, "SelectInt", {"A": "int", "B": "int", "ReturnValue": "int", "bPickA": "bool"})
        if when_true is not None:
            bp.connect(when_true, true_pin, node, "A")
        else:
            scalar.set_default(node, "A", default_true)
        bp.connect(when_false, false_pin, node, "B")
        bp.connect(condition, "ReturnValue", node, "bPickA")
        return node

    def convert(index, index_pin, x, y):
        node = b.add(f"convert_{len(b.nodes)}", "convert", x, y)
        bp.connect(index, index_pin, node, "InInt")
        return node

    def sample_time(index, index_pin, total, step, x, y):
        converted = convert(index, index_pin, x, y)
        product = math("Multiply_DoubleDouble", converted, "ReturnValue", x + 224, y, step, "AirframeDesiredStreamInputFixedStepSecondsV1")
        # Enhanced 5.6 exposes the double-compatible minimum UFunction as
        # KismetMathLibrary.FMin. The synthetic promoted name
        # Min_DoubleDouble is not reflected and is therefore dropped on paste.
        return math("FMin", product, "ReturnValue", x + 448, y, total, "AirframeDesiredStreamInputTotalSecondsV1")

    def uniform_vector(value, value_pin, x, y):
        node = b.add(f"make_vector_{len(b.nodes)}", "make_vector", x, y)
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
        broken = b.add(f"break_vector_{len(b.nodes)}", "break_vector", x, y)
        bp.connect(value, value_pin, broken, "InVec")
        finite = [b.finite(broken, axis, x + 224, y + offset * 160) for offset, axis in enumerate("XYZ")]
        current = finite[0]
        for offset, condition in enumerate(finite[1:]):
            current = compare("BooleanAND", current, "ReturnValue", x + 704 + offset * 224, y, condition, "ReturnValue", kind="bool")
        return current

    def weight(at, first, second, third, x, y):
        a = math("Subtract_DoubleDouble", at, "ReturnValue", x, y, second, "ReturnValue")
        c = math("Subtract_DoubleDouble", at, "ReturnValue", x, y + 96, third, "ReturnValue")
        numerator = math("Add_DoubleDouble", a, "ReturnValue", x + 224, y, c, "ReturnValue")
        d = math("Subtract_DoubleDouble", first, "ReturnValue", x, y + 224, second, "ReturnValue")
        e = math("Subtract_DoubleDouble", first, "ReturnValue", x, y + 320, third, "ReturnValue")
        denominator = math("Multiply_DoubleDouble", d, "ReturnValue", x + 224, y + 224, e, "ReturnValue")
        return math("Divide_DoubleDouble", numerator, "ReturnValue", x + 448, y + 112, denominator, "ReturnValue")

    source = get(source_name, "vector", 0, 160, True)
    target = get(target_name, "vector", 0, 400, True)
    total = get("AirframeDesiredStreamInputTotalSecondsV1", "real", 0, 640)
    step = get("AirframeDesiredStreamInputFixedStepSecondsV1", "real", 0, 880)
    stage = get("AirframeDesiredStreamStageValidV1", "bool", 0, 1120)
    clear = array_node("array_clear", "vector", 256, 3200, target, target_name)
    bp.connect(b.entry, "then", clear, "execute")
    stage_guard = b.add("stage_guard", "branch", 512, 3200)
    bp.connect(clear, "then", stage_guard, "execute")
    bp.connect(stage, "AirframeDesiredStreamStageValidV1", stage_guard, "Condition")
    count = array_node("array_length", "vector", 256, 160, source, source_name)
    last = math("Subtract_IntInt", count, "ReturnValue", 512, 160, default_b="1", kind="int")
    is_two = compare("EqualEqual_IntInt", count, "ReturnValue", 768, 160, default_b="2", kind="int")
    two_branch = b.add("two_branch", "branch", 768, 3200)
    bp.connect(stage_guard, "then", two_branch, "execute")
    bp.connect(is_two, "ReturnValue", two_branch, "Condition")

    # Exact two-sample secant, published twice.
    zero = set_("AirframeDesiredStreamStageIndexV1", "int", 1024, 3040, "0")
    one = math("Add_IntInt", zero, "Output_Get", 1024, 160, default_b="1", kind="int")
    first_value = item(source, source_name, zero, "Output_Get", 1280, 160)
    second_value = item(source, source_name, one, "ReturnValue", 1280, 400)
    delta = vector_math("Subtract_VectorVector", second_value, "Output", first_value, "Output", 1536, 240)
    total_vector = uniform_vector(total, "AirframeDesiredStreamInputTotalSecondsV1", 1536, 560)
    slope = vector_math("Divide_VectorVector", delta, "ReturnValue", total_vector, "ReturnValue", 1792, 320)
    slope_finite = finite_vector(slope, "ReturnValue", 2048, 160)
    two_valid = b.add("two_valid", "branch", 3072, 3040)
    bp.connect(two_branch, "then", zero, "execute")
    bp.connect(zero, "then", two_valid, "execute")
    bp.connect(slope_finite, "ReturnValue", two_valid, "Condition")
    two_reject = set_("AirframeDesiredStreamStageValidV1", "bool", 3328, 3360, "false")
    bp.connect(two_valid, "else", two_reject, "execute")
    first_add = add_item(target, slope, two_valid, "then", 3328, 3040)
    second_add = add_item(target, slope, first_add, "then", 3584, 3040)

    # Three-or-more local quadratic derivative over the exact terminal time.
    loop = b.add("loop", "loop", 1024, 3520)
    scalar.set_default(loop, "FirstIndex", "0")
    bp.connect(last, "ReturnValue", loop, "LastIndex")
    bp.connect(two_branch, "else", loop, "Execute")
    loop_guard = b.add("loop_guard", "branch", 1280, 3520)
    bp.connect(loop, "LoopBody", loop_guard, "execute")
    bp.connect(stage, "AirframeDesiredStreamStageValidV1", loop_guard, "Condition")
    is_first = compare("EqualEqual_IntInt", loop, "Index", 1280, 1120, default_b="0", kind="int")
    is_last = compare("EqualEqual_IntInt", loop, "Index", 1280, 1280, last, "ReturnValue", kind="int")
    previous = math("Subtract_IntInt", loop, "Index", 1536, 1120, default_b="1", kind="int")
    last_minus_two = math("Subtract_IntInt", last, "ReturnValue", 1536, 1280, default_b="2", kind="int")
    last_or_previous = select_int(is_last, last_minus_two, "ReturnValue", previous, "ReturnValue", 1792, 1200)
    start = select_int(is_first, None, "", last_or_previous, "ReturnValue", 2048, 1200, "0")
    index_one = math("Add_IntInt", start, "ReturnValue", 2304, 1120, default_b="1", kind="int")
    index_two = math("Add_IntInt", start, "ReturnValue", 2304, 1280, default_b="2", kind="int")
    value_zero = item(source, source_name, start, "ReturnValue", 2560, 960)
    value_one = item(source, source_name, index_one, "ReturnValue", 2560, 1200)
    value_two = item(source, source_name, index_two, "ReturnValue", 2560, 1440)
    time_zero = sample_time(start, "ReturnValue", total, step, 2816, 960)
    time_one = sample_time(index_one, "ReturnValue", total, step, 2816, 1200)
    time_two = sample_time(index_two, "ReturnValue", total, step, 2816, 1440)
    at = sample_time(loop, "Index", total, step, 2816, 1680)
    weight_zero = weight(at, time_zero, time_one, time_two, 3584, 800)
    weight_one = weight(at, time_one, time_zero, time_two, 3584, 1376)
    weight_two = weight(at, time_two, time_zero, time_one, 3584, 1952)
    vector_zero = uniform_vector(weight_zero, "ReturnValue", 4288, 960)
    vector_one = uniform_vector(weight_one, "ReturnValue", 4288, 1200)
    vector_two = uniform_vector(weight_two, "ReturnValue", 4288, 1440)
    term_zero = vector_math("Multiply_VectorVector", value_zero, "Output", vector_zero, "ReturnValue", 4544, 960)
    term_one = vector_math("Multiply_VectorVector", value_one, "Output", vector_one, "ReturnValue", 4544, 1200)
    term_two = vector_math("Multiply_VectorVector", value_two, "Output", vector_two, "ReturnValue", 4544, 1440)
    partial = vector_math("Add_VectorVector", term_zero, "ReturnValue", term_one, "ReturnValue", 4800, 1080)
    derivative = vector_math("Add_VectorVector", partial, "ReturnValue", term_two, "ReturnValue", 5056, 1200)
    derivative_finite = finite_vector(derivative, "ReturnValue", 5312, 960)
    derivative_guard = b.add("derivative_guard", "branch", 6336, 3520)
    bp.connect(loop_guard, "then", derivative_guard, "execute")
    bp.connect(derivative_finite, "ReturnValue", derivative_guard, "Condition")
    loop_add = add_item(target, derivative, derivative_guard, "then", 6592, 3360)
    reject = set_("AirframeDesiredStreamStageValidV1", "bool", 6592, 3680, "false")
    bp.connect(derivative_guard, "else", reject, "execute")
    bp.connect(reject, "then", loop, "Break")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
