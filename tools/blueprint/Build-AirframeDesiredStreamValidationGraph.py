"""Build fail-closed validation for sampled airframe desired-stream inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateAirframeDesiredStreamInputsV1"
ARRAYS = (
    ("AirframeDesiredStreamInputPositionsV1", "vector"),
    ("AirframeDesiredStreamInputAuthoredBodyQuatsV1", "quat"),
    ("AirframeDesiredStreamInputAuthoredGimbalQuatsV1", "quat"),
    ("AirframeDesiredStreamInputPathFollowWeightsV1", "real"),
    ("AirframeDesiredStreamInputHorizonStabilizationWeightsV1", "real"),
    ("AirframeDesiredStreamInputLookAheadSecondsV1", "real"),
    ("AirframeDesiredStreamInputBankGainsV1", "real"),
    ("AirframeDesiredStreamInputMaxBankDegreesV1", "real"),
    ("AirframeDesiredStreamInputCameraUptiltDegreesV1", "real"),
    ("AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1", "real"),
    ("AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1", "real"),
    ("AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1", "real"),
    ("AirframeDesiredStreamInputMinimumTurnRadiiCmV1", "real"),
)
PROFILE_BOUNDS = (
    (ARRAYS[3][0], "0.0", "1.0", True),
    (ARRAYS[4][0], "0.0", "1.0", True),
    (ARRAYS[5][0], "0.0", "5.0", True),
    (ARRAYS[6][0], "0.0", "2.0", True),
    (ARRAYS[7][0], "0.0", "85.0", True),
    (ARRAYS[8][0], "-45.0", "45.0", True),
    (ARRAYS[9][0], "0.0", "720.0", False),
    (ARRAYS[10][0], "0.0", "10000.0", False),
    (ARRAYS[11][0], "0.0", "50000.0", False),
    (ARRAYS[12][0], "0.0", "100000.0", False),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_validation_base", path)
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
    b = scalar.Builder(bp, forms, FUNCTION)
    raw = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    vector_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    quat_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    foreach_form = bp.find_block(raw, r"K2Node_MacroInstance")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')
    break_vector_form = bp.find_block(vector_forms, r'MemberName="BreakVector"')
    quat_finite_form = bp.find_block(quat_forms, r'MemberName="Quat_IsFinite"')
    quat_size_form = bp.find_block(quat_compiler, r'MemberName="Quat_Size"')
    int_to_double_form = bp.find_block(playback, r'MemberName="Conv_IntToDouble"')

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def retarget_call(node, member, pin_types):
        scalar.retarget_function(node, member)
        for pin, kind in pin_types.items():
            pin_kind(node, pin, kind)
        return node

    def array_get(name, kind, x, y):
        node = b.get(name, "real" if kind == "real" else "vector", x, y)
        scalar.retarget_variable(node, name, "real" if kind == "real" else "vector")
        pin_kind(node, name, kind, True)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)
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
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        retarget_call(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean_and(left, right, x, y):
        node = b.add(f"and_{len(b.nodes)}", "compare", x, y)
        retarget_call(node, "BooleanAND", {"A": "bool", "B": "bool", "ReturnValue": "bool"})
        bp.connect(left, "ReturnValue", node, "A")
        bp.connect(right, "ReturnValue", node, "B")
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = boolean_and(current, condition, x + index * 224, y)
        return current

    def int_math(member, source, amount, x, y):
        node = b.math("Subtract_DoubleDouble", x, y)
        retarget_call(node, member, {"A": "int", "B": "int", "ReturnValue": "int"})
        bp.connect(source, "ReturnValue", node, "A")
        scalar.set_default(node, "B", amount)
        return node

    def convert_int(source, x, y):
        node = add_form(f"convert_{len(b.nodes)}", int_to_double_form, x, y)
        bp.connect(source, "ReturnValue", node, "InInt")
        return node

    def multiply(left, left_pin, right, right_pin, x, y):
        node = b.math("Multiply_DoubleDouble", x, y)
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    reset = b.set("AirframeDesiredStreamStageValidV1", "bool", 256, 4160, "false")
    bp.connect(b.entry, "then", reset, "execute")
    getters = [array_get(name, kind, 0, 160 + index * 240) for index, (name, kind) in enumerate(ARRAYS)]
    lengths = [array_length(source, name, kind, 320, 160 + index * 240) for index, (source, (name, kind)) in enumerate(zip(getters, ARRAYS))]
    total = b.get("AirframeDesiredStreamInputTotalSecondsV1", "real", 0, 3440)
    step = b.get("AirframeDesiredStreamInputFixedStepSecondsV1", "real", 0, 3680)
    count = lengths[0]
    conditions = [
        compare("GreaterEqual_IntInt", count, "ReturnValue", 640, 160, "int", default_b="2"),
        compare("LessEqual_IntInt", count, "ReturnValue", 640, 288, "int", default_b="65536"),
    ]
    for index, length in enumerate(lengths[1:]):
        conditions.append(compare("EqualEqual_IntInt", length, "ReturnValue", 640, 480 + index * 144, "int", count, "ReturnValue"))
    conditions.extend((
        b.finite(total, "AirframeDesiredStreamInputTotalSecondsV1", 640, 2304),
        compare("Greater_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 1088, 2304, default_b="0.0"),
        compare("LessEqual_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 1312, 2304, default_b="3600.0"),
        b.finite(step, "AirframeDesiredStreamInputFixedStepSecondsV1", 640, 2544),
        compare("GreaterEqual_DoubleDouble", step, "AirframeDesiredStreamInputFixedStepSecondsV1", 1088, 2544, default_b="0.004166666666666667"),
        compare("LessEqual_DoubleDouble", step, "AirframeDesiredStreamInputFixedStepSecondsV1", 1312, 2544, default_b="0.5"),
    ))
    minus_two = int_math("Subtract_IntInt", count, "2", 640, 2800)
    minus_one = int_math("Subtract_IntInt", count, "1", 640, 2960)
    lower_index = convert_int(minus_two, 896, 2800)
    upper_index = convert_int(minus_one, 896, 2960)
    lower_time = multiply(lower_index, "ReturnValue", step, "AirframeDesiredStreamInputFixedStepSecondsV1", 1152, 2800)
    upper_time = multiply(upper_index, "ReturnValue", step, "AirframeDesiredStreamInputFixedStepSecondsV1", 1152, 2960)
    conditions.extend((
        compare("Less_DoubleDouble", lower_time, "ReturnValue", 1408, 2800, right=total, right_pin="AirframeDesiredStreamInputTotalSecondsV1"),
        compare("LessEqual_DoubleDouble", total, "AirframeDesiredStreamInputTotalSecondsV1", 1408, 2960, right=upper_time, right_pin="ReturnValue"),
    ))
    all_shape = and_all(conditions, 1792, 3360)
    shape_branch = b.add("shape_branch", "branch", 7424, 4160)
    bp.connect(reset, "then", shape_branch, "execute")
    bp.connect(all_shape, "ReturnValue", shape_branch, "Condition")
    accept = b.set("AirframeDesiredStreamStageValidV1", "bool", 7680, 4160, "true")
    bp.connect(shape_branch, "then", accept, "execute")

    position_loop = foreach(getters[0], ARRAYS[0][0], "vector", 7936, 160)
    bp.connect(accept, "then", position_loop, "Exec")
    split = add_form("position_break", break_vector_form, 8224, 160)
    pin_kind(split, "InVec", "vector")
    for pin in ("X", "Y", "Z"):
        pin_kind(split, pin, "real")
    bp.connect(position_loop, "Array Element", split, "InVec")
    vector_valid = and_all(tuple(b.finite(split, pin, 8512, 64 + index * 160) for index, pin in enumerate(("X", "Y", "Z"))), 8960, 160)
    position_branch = b.add("position_branch", "branch", 9472, 160)
    bp.connect(position_loop, "LoopBody", position_branch, "execute")
    bp.connect(vector_valid, "ReturnValue", position_branch, "Condition")
    position_reject = b.set("AirframeDesiredStreamStageValidV1", "bool", 9728, 352, "false")
    bp.connect(position_branch, "else", position_reject, "execute")

    previous = position_loop
    previous_pin = "Completed"
    for offset, (source, (name, _kind)) in enumerate(zip(getters[1:3], ARRAYS[1:3])):
        x = 9984 + offset * 2048
        loop = foreach(source, name, "quat", x, 720 + offset * 480)
        bp.connect(previous, previous_pin, loop, "Exec")
        finite = add_form(f"quat_finite_{offset}", quat_finite_form, x + 288, 624 + offset * 480)
        pin_kind(finite, "Q", "quat")
        pin_kind(finite, "ReturnValue", "bool")
        bp.connect(loop, "Array Element", finite, "Q")
        size = add_form(f"quat_size_{offset}", quat_size_form, x + 288, 816 + offset * 480)
        pin_kind(size, "Q", "quat")
        pin_kind(size, "ReturnValue", "real")
        bp.connect(loop, "Array Element", size, "Q")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", x + 544, 736 + offset * 480, default_b="0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", x + 544, 896 + offset * 480, default_b="1.000001")
        valid = and_all((finite, lower, upper), x + 800, 800 + offset * 480)
        branch = b.add(f"quat_branch_{offset}", "branch", x + 1280, 800 + offset * 480)
        bp.connect(loop, "LoopBody", branch, "execute")
        bp.connect(valid, "ReturnValue", branch, "Condition")
        reject = b.set("AirframeDesiredStreamStageValidV1", "bool", x + 1536, 992 + offset * 480, "false")
        bp.connect(branch, "else", reject, "execute")
        previous, previous_pin = loop, "Completed"

    profile_start_x = 14080
    for index, ((name, lower_value, upper_value, inclusive_lower), source) in enumerate(zip(PROFILE_BOUNDS, getters[3:])):
        x = profile_start_x + index * 1664
        y = 1920 + (index % 2) * 480
        loop = foreach(source, name, "real", x, y)
        bp.connect(previous, previous_pin, loop, "Exec")
        finite = b.finite(loop, "Array Element", x + 288, y - 128)
        lower = compare(
            "GreaterEqual_DoubleDouble" if inclusive_lower else "Greater_DoubleDouble",
            loop, "Array Element", x + 736, y - 32, default_b=lower_value,
        )
        upper = compare("LessEqual_DoubleDouble", loop, "Array Element", x + 736, y + 128, default_b=upper_value)
        valid = and_all((finite, lower, upper), x + 992, y)
        branch = b.add(f"profile_branch_{index}", "branch", x + 1408, y)
        bp.connect(loop, "LoopBody", branch, "execute")
        bp.connect(valid, "ReturnValue", branch, "Condition")
        reject = b.set("AirframeDesiredStreamStageValidV1", "bool", x + 1408, y + 224, "false")
        bp.connect(branch, "else", reject, "execute")
        previous, previous_pin = loop, "Completed"

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in b.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
