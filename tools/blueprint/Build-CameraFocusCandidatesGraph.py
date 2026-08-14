"""Build per-sample physical focus distances on the accepted absolute schedule."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCameraFocusDistanceCandidatesV1"
MODES = ("manual_distance", "fixed_world", "rack_fixed", "track_prebaked", "smoothed_autofocus")


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_focus_candidates_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, kind: str, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
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
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-camera-focus-compile-v1.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    vectors = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    preview = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-segment-node-forms.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    forms.update({
        "add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        "loop": bp.find_block(loops, r"StandardMacros:ForLoopWithBreak"),
        "break_vector": bp.find_block(vectors, r'MemberName="BreakVector"'),
        "distance": bp.find_block(preview, r'MemberName="Vector_Distance"'),
        "select": bp.find_block(speed, r'MemberName="SelectFloat"'),
        "exp": bp.find_block(speed, r'MemberName="Exp"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, default=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def array_node(form, source, source_pin, kind, x, y):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y)
        target = "Array" if form == "item" else "TargetArray"
        pin_kind(node, target, kind, True)
        if form == "item":
            pin_kind(node, "Output", kind)
        elif form == "length":
            pin_kind(node, "ReturnValue", "int")
        elif form == "add":
            pin_kind(node, "NewItem", kind)
            pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, target)
        return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = array_node("item", source, source_pin, kind, x, y)
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def operation(member, left, left_pin, x, y, right=None, right_pin=None, default=None, kind="real", result=None):
        node = b.add(f"op_{member}_{len(b.nodes)}", "math", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": result or kind})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default is not None:
            scalar.set_default(node, "B", default)
        return node

    def operation_left_default(member, default_a, right, right_pin, x, y):
        node = b.add(f"op_{member}_{len(b.nodes)}", "math", x, y)
        retarget(node, member, {"A": "real", "B": "real", "ReturnValue": "real"})
        scalar.set_default(node, "A", default_a)
        bp.connect(right, right_pin, node, "B")
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default=None, kind="real"):
        node = b.add(f"cmp_{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default)
        return node

    def boolean(member, left, right, x, y):
        return compare(member, left, "ReturnValue", x, y, right, "ReturnValue", kind="bool")

    def combine(items, x, y):
        current = items[0]
        for offset, item_node in enumerate(items[1:]):
            current = boolean("BooleanAND", current, item_node, x + offset * 192, y)
        return current

    def equal_string(source, pin, expected, x, y):
        node = b.add(f"str_{expected}_{len(b.nodes)}", "string_equal", x, y)
        scalar.set_default(node, "B", expected)
        bp.connect(source, pin, node, "A")
        return node

    def convert(index, index_pin, x, y):
        node = b.add(f"convert_{len(b.nodes)}", "convert", x, y)
        bp.connect(index, index_pin, node, "InInt")
        return node

    def select(condition, when_true, true_pin, when_false, false_pin, x, y, kind="real", true_default=None):
        node = b.add(f"select_{len(b.nodes)}", "select", x, y)
        retarget(node, "SelectFloat" if kind == "real" else "SelectInt", {"A": kind, "B": kind, "ReturnValue": kind, "bPickA": "bool"})
        if when_true is None:
            scalar.set_default(node, "A", true_default)
        else:
            bp.connect(when_true, true_pin, node, "A")
        bp.connect(when_false, false_pin, node, "B")
        bp.connect(condition, "ReturnValue", node, "bPickA")
        return node

    def distance(left, left_pin, right, right_pin, x, y):
        node = b.add(f"distance_{len(b.nodes)}", "distance", x, y)
        bp.connect(left, left_pin, node, "V1")
        bp.connect(right, right_pin, node, "V2")
        return node

    def finite_vector(source, source_pin, x, y):
        node = b.add(f"break_vector_{len(b.nodes)}", "break_vector", x, y)
        bp.connect(source, source_pin, node, "InVec")
        checks = [b.finite(node, axis, x + 224, y + offset * 160) for offset, axis in enumerate(("X", "Y", "Z"))]
        return combine(checks, x + 672, y + 160)

    def pure_exp(source, source_pin, x, y):
        node = b.add(f"exp_{len(b.nodes)}", "exp", x, y)
        bp.connect(source, source_pin, node, "A")
        return node

    inputs = {
        "mode": get("CameraFocusInputModeV1", "string", 0, 0),
        "domain": get("CameraFocusInputDomainV1", "string", 0, 160),
        "step": get("CameraFocusInputFixedStepSecondsV1", "real", 0, 320),
        "times": get("CameraFocusInputTimesSecondsV1", "real", 0, 480, True),
        "cameras": get("CameraFocusInputCameraPositionsV1", "vector", 0, 640, True),
        "manual": get("CameraFocusInputManualDistancesCmV1", "real", 0, 800, True),
        "targets": get("CameraFocusInputTargetPositionsV1", "vector", 0, 960, True),
        "rack_a": get("CameraFocusInputRackTargetAV1", "vector", 0, 1120),
        "rack_b": get("CameraFocusInputRackTargetBV1", "vector", 0, 1280),
        "weights": get("CameraFocusInputRackBlendWeightsV1", "real", 0, 1440, True),
        "response": get("CameraFocusInputSmoothingResponseSecondsV1", "real", 0, 1600),
        "candidate": get("CameraFocusCandidateDistancesCmV1", "real", 0, 1760, True),
        "stage": get("CameraFocusCandidateValidV1", "bool", 0, 1920),
    }
    count = array_node("length", inputs["times"], "CameraFocusInputTimesSecondsV1", "real", 256, 480)
    last_index = operation("Subtract_IntInt", count, "ReturnValue", 480, 480, default="1", kind="int")
    total = item(inputs["times"], "CameraFocusInputTimesSecondsV1", "real", last_index, "ReturnValue", 704, 480)

    guard = b.add("stage_guard", "branch", 256, 2400)
    invalidate = set_("CameraFocusCandidateValidV1", "bool", 480, 2400, "false")
    fail_code = set_("CameraFocusFailureCodeV1", "string", 704, 2400, "candidate_failed")
    clear = array_node("clear", inputs["candidate"], "CameraFocusCandidateDistancesCmV1", "real", 928, 2400)
    bp.connect(b.entry, "then", guard, "execute")
    bp.connect(inputs["stage"], "CameraFocusCandidateValidV1", guard, "Condition")
    bp.connect(guard, "then", invalidate, "execute")
    bp.connect(invalidate, "then", fail_code, "execute")
    bp.connect(fail_code, "then", clear, "execute")

    mode_branches = []
    prior = clear
    for index, mode_name in enumerate(MODES):
        equal = equal_string(inputs["mode"], "CameraFocusInputModeV1", mode_name, 1152, 2080 + index * 160)
        branch = b.add(f"mode_{mode_name}", "branch", 1376 + index * 224, 2400)
        bp.connect(prior, "then" if index == 0 else "else", branch, "execute")
        bp.connect(equal, "ReturnValue", branch, "Condition")
        mode_branches.append(branch)
        prior = branch

    def schedule(prefix, loop, x, y):
        index_as_real = convert(loop, "Index", x, y)
        raw_expected = operation("Multiply_DoubleDouble", index_as_real, "ReturnValue", x + 224, y, inputs["step"], "CameraFocusInputFixedStepSecondsV1")
        expected = operation("FMin", raw_expected, "ReturnValue", x + 448, y, total, "Output")
        current = item(inputs["times"], "CameraFocusInputTimesSecondsV1", "real", loop, "Index", x, y + 192)
        is_first = compare("EqualEqual_IntInt", loop, "Index", x + 224, y + 192, default="0", kind="int")
        previous_raw = operation("Subtract_IntInt", loop, "Index", x + 448, y + 192, default="1", kind="int")
        previous_index = select(is_first, None, None, previous_raw, "ReturnValue", x + 672, y + 192, "int", "0")
        previous = item(inputs["times"], "CameraFocusInputTimesSecondsV1", "real", previous_index, "ReturnValue", x + 896, y + 192)
        increasing = compare("Greater_DoubleDouble", current, "Output", x + 1120, y + 192, previous, "Output")
        order = boolean("BooleanOR", is_first, increasing, x + 1344, y + 192)
        exact = compare("EqualEqual_DoubleDouble", current, "Output", x + 672, y, expected, "ReturnValue")
        finite_time = b.finite(current, "Output", x + 896, y)
        finite_total = b.finite(total, "Output", x + 1344, y)
        camera = item(inputs["cameras"], "CameraFocusInputCameraPositionsV1", "vector", loop, "Index", x, y + 640)
        camera_finite = finite_vector(camera, "Output", x + 224, y + 576)
        common = combine((exact, finite_time, finite_total, order, camera_finite), x + 1792, y + 256)
        return current, previous, camera, is_first, common

    def append_path(prefix, branch_source, branch_pin, value, value_pin, loop, x, y):
        add = array_node("add", inputs["candidate"], "CameraFocusCandidateDistancesCmV1", "real", x, y)
        bp.connect(value, value_pin, add, "NewItem")
        bp.connect(branch_source, branch_pin, add, "execute")
        failure_break = loop
        return add, failure_break

    def finish(loop, x, y):
        built_count = array_node("length", inputs["candidate"], "CameraFocusCandidateDistancesCmV1", "real", x, y - 160)
        complete = compare("EqualEqual_IntInt", built_count, "ReturnValue", x + 224, y - 160, count, "ReturnValue", kind="int")
        branch = b.add(f"complete_{len(b.nodes)}", "branch", x + 448, y)
        clear_failure = set_("CameraFocusFailureCodeV1", "string", x + 672, y, "")
        publish = set_("CameraFocusCandidateValidV1", "bool", x + 896, y, "true")
        bp.connect(loop, "Completed", branch, "execute")
        bp.connect(complete, "ReturnValue", branch, "Condition")
        bp.connect(branch, "then", clear_failure, "execute")
        bp.connect(clear_failure, "then", publish, "execute")

    def loop_for(branch, prefix, lane):
        y = 3040 + lane * 2200
        loop = b.add(f"loop_{prefix}", "loop", 2720, y)
        scalar.set_default(loop, "FirstIndex", "0")
        bp.connect(last_index, "ReturnValue", loop, "LastIndex")
        bp.connect(branch, "then", loop, "Execute")
        return loop, y

    # Manual authored distances.
    loop, y = loop_for(mode_branches[0], "manual", 0)
    current, previous, camera, is_first, common = schedule("manual", loop, 2944, y - 960)
    value = item(inputs["manual"], "CameraFocusInputManualDistancesCmV1", "real", loop, "Index", 2944, y + 640)
    finite_value = b.finite(value, "Output", 3168, y + 640)
    minimum = compare("GreaterEqual_DoubleDouble", value, "Output", 3616, y + 640, default="1.0")
    valid = combine((common, finite_value, minimum), 3840, y + 640)
    check = b.add("manual_sample_guard", "branch", 4288, y)
    bp.connect(loop, "LoopBody", check, "execute"); bp.connect(valid, "ReturnValue", check, "Condition")
    append_path("manual", check, "then", value, "Output", loop, 4512, y)
    bp.connect(check, "else", loop, "Break")
    finish(loop, 4736, y)

    # One fixed world target.
    loop, y = loop_for(mode_branches[1], "fixed", 1)
    current, previous, camera, is_first, common = schedule("fixed", loop, 2944, y - 960)
    zero = operation("Subtract_IntInt", loop, "Index", 2944, y + 640, loop, "Index", kind="int")
    target = item(inputs["targets"], "CameraFocusInputTargetPositionsV1", "vector", zero, "ReturnValue", 3168, y + 640)
    value = distance(camera, "Output", target, "Output", 3392, y + 640)
    finite_value = b.finite(value, "ReturnValue", 3616, y + 640)
    minimum = compare("GreaterEqual_DoubleDouble", value, "ReturnValue", 4064, y + 640, default="1.0")
    valid = combine((common, finite_value, minimum), 4288, y + 640)
    check = b.add("fixed_sample_guard", "branch", 4736, y)
    bp.connect(loop, "LoopBody", check, "execute"); bp.connect(valid, "ReturnValue", check, "Condition")
    append_path("fixed", check, "then", value, "ReturnValue", loop, 4960, y)
    bp.connect(check, "else", loop, "Break")
    finish(loop, 5184, y)

    # Rack between two fixed targets, interpolated in the declared optical domain.
    loop, y = loop_for(mode_branches[2], "rack", 2)
    current, previous, camera, is_first, common = schedule("rack", loop, 2944, y - 960)
    weight = item(inputs["weights"], "CameraFocusInputRackBlendWeightsV1", "real", loop, "Index", 2944, y + 640)
    distance_a = distance(camera, "Output", inputs["rack_a"], "CameraFocusInputRackTargetAV1", 3168, y + 640)
    distance_b = distance(camera, "Output", inputs["rack_b"], "CameraFocusInputRackTargetBV1", 3168, y + 800)
    weight_finite = b.finite(weight, "Output", 3392, y + 480)
    low = compare("GreaterEqual_DoubleDouble", weight, "Output", 3840, y + 480, default="0.0")
    high = compare("LessEqual_DoubleDouble", weight, "Output", 4064, y + 480, default="1.0")
    a_finite = b.finite(distance_a, "ReturnValue", 3392, y + 800)
    b_finite = b.finite(distance_b, "ReturnValue", 3840, y + 800)
    a_min = compare("GreaterEqual_DoubleDouble", distance_a, "ReturnValue", 4288, y + 800, default="1.0")
    b_min = compare("GreaterEqual_DoubleDouble", distance_b, "ReturnValue", 4512, y + 800, default="1.0")
    delta = operation("Subtract_DoubleDouble", distance_b, "ReturnValue", 3392, y + 1120, distance_a, "ReturnValue")
    weighted_delta = operation("Multiply_DoubleDouble", delta, "ReturnValue", 3616, y + 1120, weight, "Output")
    linear = operation("Add_DoubleDouble", distance_a, "ReturnValue", 3840, y + 1120, weighted_delta, "ReturnValue")
    # Subtract helper computes A-B; use 1 + (-weight) for exact 1-weight.
    neg_weight = operation("Multiply_DoubleDouble", weight, "Output", 3616, y + 1280, default="-1.0")
    one_minus = operation("Add_DoubleDouble", neg_weight, "ReturnValue", 3840, y + 1280, default="1.0")
    left_term = operation("Divide_DoubleDouble", one_minus, "ReturnValue", 4064, y + 1280, distance_a, "ReturnValue")
    right_term = operation("Divide_DoubleDouble", weight, "Output", 4064, y + 1440, distance_b, "ReturnValue")
    denominator = operation("Add_DoubleDouble", left_term, "ReturnValue", 4288, y + 1360, right_term, "ReturnValue")
    reciprocal = operation_left_default("Divide_DoubleDouble", "1.0", denominator, "ReturnValue", 4736, y + 1440)
    reciprocal_domain = equal_string(inputs["domain"], "CameraFocusInputDomainV1", "reciprocal", 4064, y + 1120)
    value = select(reciprocal_domain, reciprocal, "ReturnValue", linear, "ReturnValue", 4960, y + 1280)
    value_finite = b.finite(value, "ReturnValue", 5184, y + 1280)
    value_min = compare("GreaterEqual_DoubleDouble", value, "ReturnValue", 5632, y + 1280, default="1.0")
    valid = combine((common, weight_finite, low, high, a_finite, b_finite, a_min, b_min, value_finite, value_min), 5856, y + 960)
    check = b.add("rack_sample_guard", "branch", 7584, y)
    bp.connect(loop, "LoopBody", check, "execute"); bp.connect(valid, "ReturnValue", check, "Condition")
    append_path("rack", check, "then", value, "ReturnValue", loop, 7808, y)
    bp.connect(check, "else", loop, "Break")
    finish(loop, 8032, y)

    # Prebaked target positions.
    loop, y = loop_for(mode_branches[3], "track", 3)
    current, previous, camera, is_first, common = schedule("track", loop, 2944, y - 960)
    target = item(inputs["targets"], "CameraFocusInputTargetPositionsV1", "vector", loop, "Index", 2944, y + 640)
    value = distance(camera, "Output", target, "Output", 3168, y + 640)
    finite_value = b.finite(value, "ReturnValue", 3392, y + 640)
    minimum = compare("GreaterEqual_DoubleDouble", value, "ReturnValue", 3840, y + 640, default="1.0")
    valid = combine((common, finite_value, minimum), 4064, y + 640)
    check = b.add("track_sample_guard", "branch", 4512, y)
    bp.connect(loop, "LoopBody", check, "execute"); bp.connect(valid, "ReturnValue", check, "Condition")
    append_path("track", check, "then", value, "ReturnValue", loop, 4736, y)
    bp.connect(check, "else", loop, "Break")
    finish(loop, 4960, y)

    # Chronological autofocus smoothing. The first sample bypasses prior-candidate access.
    loop, y = loop_for(mode_branches[4], "smooth", 4)
    current, previous, camera, is_first, common = schedule("smooth", loop, 2944, y - 960)
    target = item(inputs["targets"], "CameraFocusInputTargetPositionsV1", "vector", loop, "Index", 2944, y + 640)
    raw = distance(camera, "Output", target, "Output", 3168, y + 640)
    finite_raw = b.finite(raw, "ReturnValue", 3392, y + 640)
    raw_min = compare("GreaterEqual_DoubleDouble", raw, "ReturnValue", 3840, y + 640, default="1.0")
    valid = combine((common, finite_raw, raw_min), 4064, y + 640)
    check = b.add("smooth_sample_guard", "branch", 4512, y)
    first_branch = b.add("smooth_first_branch", "branch", 4736, y)
    bp.connect(loop, "LoopBody", check, "execute"); bp.connect(valid, "ReturnValue", check, "Condition")
    bp.connect(check, "then", first_branch, "execute"); bp.connect(is_first, "ReturnValue", first_branch, "Condition")
    first_add, _ = append_path("smooth_first", first_branch, "then", raw, "ReturnValue", loop, 4960, y - 160)
    previous_index = operation("Subtract_IntInt", loop, "Index", 4736, y + 960, default="1", kind="int")
    prior_value = item(inputs["candidate"], "CameraFocusCandidateDistancesCmV1", "real", previous_index, "ReturnValue", 4960, y + 960)
    dt = operation("Subtract_DoubleDouble", current, "Output", 5184, y + 960, previous, "Output")
    ratio = operation("Divide_DoubleDouble", dt, "ReturnValue", 5408, y + 960, inputs["response"], "CameraFocusInputSmoothingResponseSecondsV1")
    negative = operation("Multiply_DoubleDouble", ratio, "ReturnValue", 5632, y + 960, default="-1.0")
    decay = pure_exp(negative, "ReturnValue", 5856, y + 960)
    negative_decay = operation("Multiply_DoubleDouble", decay, "ReturnValue", 6080, y + 960, default="-1.0")
    alpha = operation("Add_DoubleDouble", negative_decay, "ReturnValue", 6304, y + 960, default="1.0")
    delta = operation("Subtract_DoubleDouble", raw, "ReturnValue", 6528, y + 960, prior_value, "Output")
    weighted = operation("Multiply_DoubleDouble", delta, "ReturnValue", 6752, y + 960, alpha, "ReturnValue")
    smoothed = operation("Add_DoubleDouble", prior_value, "Output", 6976, y + 960, weighted, "ReturnValue")
    smooth_finite = b.finite(smoothed, "ReturnValue", 7200, y + 960)
    smooth_min = compare("GreaterEqual_DoubleDouble", smoothed, "ReturnValue", 7648, y + 960, default="1.0")
    smooth_valid = boolean("BooleanAND", smooth_finite, smooth_min, 7872, y + 960)
    smooth_guard = b.add("smooth_result_guard", "branch", 8096, y)
    bp.connect(first_branch, "else", smooth_guard, "execute"); bp.connect(smooth_valid, "ReturnValue", smooth_guard, "Condition")
    append_path("smooth", smooth_guard, "then", smoothed, "ReturnValue", loop, 8320, y)
    bp.connect(check, "else", loop, "Break"); bp.connect(smooth_guard, "else", loop, "Break")
    finish(loop, 8544, y)

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
