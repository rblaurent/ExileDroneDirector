"""Build transactional fixed-step airframe/gimbal candidate samples."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildAirframePrebakeSamplesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
RESULT_QUAT = "AirframePrebakeScratchResultQuatV1"
RESULT_RATE = "AirframePrebakeScratchResultAngularRateDegreesPerSecondV1"
RESULT_LIMITED = "AirframePrebakeScratchResultRateLimitedV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_samples_base", path)
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
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-prebake-candidate-v1.eddgraph")
    loop_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    call_forms = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "array_length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "array_item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        "select": bp.find_block(speed, r'MemberName="SelectFloat"'),
        "loop": bp.find_block(loop_forms, r"StandardMacros:ForLoopWithBreak"),
        "self_call": bp.find_block(call_forms, r'MemberName="SwitchToDroneView"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, default_value=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if default_value is not None:
            scalar.set_default(node, name, default_value)
        return node

    def array_node(form, name, kind, x, y, source=None, source_pin=None):
        node = builder.add(f"{form}_{name}_{len(builder.nodes)}", form, x, y)
        target_pin = "TargetArray" if form in ("array_add", "array_clear", "array_length") else "Array"
        pin_kind(node, target_pin, kind, True)
        if form == "array_add":
            pin_kind(node, "NewItem", kind)
            pin_kind(node, "ReturnValue", "int")
        elif form == "array_length":
            pin_kind(node, "ReturnValue", "int")
        elif form == "array_item":
            pin_kind(node, "Output", kind)
        if source is not None:
            bp.connect(source, source_pin, node, target_pin)
        return node

    def item(source, source_pin, kind, index, index_pin, x, y, name):
        node = array_node("array_item", name, kind, x, y, source, source_pin)
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def add(target, target_pin, kind, x, y, name, source=None, source_pin=None, default_value=None):
        node = array_node("array_add", name, kind, x, y, target, target_pin)
        if source is not None:
            bp.connect(source, source_pin, node, "NewItem")
        elif default_value is not None:
            scalar.set_default(node, "NewItem", default_value)
        return node

    def math(member_name, kind, left, left_pin, x, y, right=None, right_pin=None, default_b=None):
        node = builder.math("Add_DoubleDouble", x, y)
        scalar.retarget_function(node, member_name)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, kind)
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default_b is not None:
            scalar.set_default(node, "B", default_b)
        return node

    def compare(member_name, kind, left, left_pin, x, y, right=None, right_pin=None, default_b=None):
        node = builder.add(f"compare_{member_name}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member_name)
        pin_kind(node, "A", kind)
        pin_kind(node, "B", kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default_b is not None:
            scalar.set_default(node, "B", default_b)
        return node

    def select_real(condition, when_true, true_pin, when_false, false_pin, x, y):
        node = builder.add(f"select_{len(builder.nodes)}", "select", x, y)
        bp.connect(when_true, true_pin, node, "A")
        bp.connect(when_false, false_pin, node, "B")
        bp.connect(condition, "ReturnValue", node, "bPickA")
        return node

    def self_call(name, x, y):
        node = builder.add(f"call_{name}_{len(builder.nodes)}", "self_call", x, y)
        node.text = re.sub(
            r"FunctionReference=\([^\n]*\)",
            f'FunctionReference=(MemberName="{name}",bSelfContext=True)',
            node.text,
            1,
        )
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}",
                line,
                1,
            ),
        )
        return node

    candidate_specs = (
        ("AirframePrebakeCandidateBodyQuatsV1", "quat"),
        ("AirframePrebakeCandidateGimbalQuatsV1", "quat"),
        ("AirframePrebakeCandidateBodyAngularRatesDegreesPerSecondV1", "real"),
        ("AirframePrebakeCandidateGimbalAngularRatesDegreesPerSecondV1", "real"),
        ("AirframePrebakeCandidateBodyRateLimitedV1", "bool"),
        ("AirframePrebakeCandidateGimbalRateLimitedV1", "bool"),
    )
    candidates = {name: get(name, kind, 0, index * 144, True) for index, (name, kind) in enumerate(candidate_specs)}
    clears = [
        array_node("array_clear", name, kind, 256 + index * 256, 3200, candidates[name], name)
        for index, (name, kind) in enumerate(candidate_specs)
    ]
    stage_index_reset = set_("AirframePrebakeStageIndexV1", "int", 1792, 3200, "0")
    bp.connect(builder.entry, "then", clears[0], "execute")
    for left, right in zip(clears, clears[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(clears[-1], "then", stage_index_reset, "execute")
    stage_valid = get("AirframePrebakeStageValidV1", "bool", 1792, 2880)
    stage_guard = builder.add("stage_guard", "branch", 2048, 3200)
    bp.connect(stage_index_reset, "then", stage_guard, "execute")
    bp.connect(stage_valid, "AirframePrebakeStageValidV1", stage_guard, "Condition")

    bodies = get("AirframePrebakeInputDesiredBodyQuatsV1", "quat", 0, 1040, True)
    gimbals = get("AirframePrebakeInputDesiredGimbalQuatsV1", "quat", 0, 1200, True)
    rates = get("AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real", 0, 1360, True)
    total = get("AirframePrebakeInputTotalSecondsV1", "real", 0, 1520)
    step = get("AirframePrebakeInputFixedStepSecondsV1", "real", 0, 1680)
    # The first element is safe because validation has already proven count >= 2.
    # Variable-set value pins are inputs. Use the native Output_Get pin for
    # both seed indices; linking the named value pin here produces a symmetric
    # clipboard record that nevertheless fails K2 compilation as input->input.
    body_zero = item(bodies, "AirframePrebakeInputDesiredBodyQuatsV1", "quat", stage_index_reset, "Output_Get", 2304, 400, "body_zero")
    gimbal_zero = item(gimbals, "AirframePrebakeInputDesiredGimbalQuatsV1", "quat", stage_index_reset, "Output_Get", 2304, 640, "gimbal_zero")
    count = array_node("array_length", "body_count", "quat", 2304, 1120, bodies, "AirframePrebakeInputDesiredBodyQuatsV1")
    last = math("Subtract_IntInt", "int", count, "ReturnValue", 2560, 1120, default_b="1")

    seed_sets = (
        set_("AirframePrebakeScratchPreviousQuatV1", "quat", 2560, 2880),
        set_("AirframePrebakeScratchDesiredQuatV1", "quat", 2816, 2880),
        set_("AirframePrebakeScratchDeltaSecondsV1", "real", 3072, 2880),
        set_("AirframePrebakeScratchMaximumRateDegreesPerSecondV1", "real", 3328, 2880),
    )
    bp.connect(body_zero, "Output", seed_sets[1], "AirframePrebakeScratchDesiredQuatV1")
    scalar.set_default(seed_sets[0], "AirframePrebakeScratchPreviousQuatV1", "0, 0, 0, 1")
    scalar.set_default(seed_sets[2], "AirframePrebakeScratchDeltaSecondsV1", "0.5")
    scalar.set_default(seed_sets[3], "AirframePrebakeScratchMaximumRateDegreesPerSecondV1", "720.0")
    bp.connect(stage_guard, "then", seed_sets[0], "execute")
    for left, right in zip(seed_sets, seed_sets[1:]):
        bp.connect(left, "then", right, "execute")
    body_seed_call = self_call("ApplyAirframeAngularRateLimitV1", 3584, 2880)
    bp.connect(seed_sets[-1], "then", body_seed_call, "execute")
    helper_valid = get("AirframePrebakeScratchResultValidV1", "bool", 3584, 2560)
    body_seed_guard = builder.add("body_seed_guard", "branch", 3840, 2880)
    bp.connect(body_seed_call, "then", body_seed_guard, "execute")
    bp.connect(helper_valid, "AirframePrebakeScratchResultValidV1", body_seed_guard, "Condition")
    reject_seed_body = set_("AirframePrebakeStageValidV1", "bool", 4096, 3360, "false")
    bp.connect(body_seed_guard, "else", reject_seed_body, "execute")
    helper_quat = get("AirframePrebakeScratchResultQuatV1", "quat", 3840, 2400)
    seed_body_adds = (
        add(candidates[candidate_specs[0][0]], candidate_specs[0][0], "quat", 4096, 2880, "seed_body_quat", helper_quat, RESULT_QUAT),
        add(candidates[candidate_specs[2][0]], candidate_specs[2][0], "real", 4352, 2880, "seed_body_rate", default_value="0.0"),
        add(candidates[candidate_specs[4][0]], candidate_specs[4][0], "bool", 4608, 2880, "seed_body_limited", default_value="false"),
    )
    bp.connect(body_seed_guard, "then", seed_body_adds[0], "execute")
    for left, right in zip(seed_body_adds, seed_body_adds[1:]):
        bp.connect(left, "then", right, "execute")

    gimbal_seed_sets = (
        set_("AirframePrebakeScratchPreviousQuatV1", "quat", 4864, 2880),
        set_("AirframePrebakeScratchDesiredQuatV1", "quat", 5120, 2880),
    )
    scalar.set_default(gimbal_seed_sets[0], "AirframePrebakeScratchPreviousQuatV1", "0, 0, 0, 1")
    bp.connect(gimbal_zero, "Output", gimbal_seed_sets[1], "AirframePrebakeScratchDesiredQuatV1")
    bp.connect(seed_body_adds[-1], "then", gimbal_seed_sets[0], "execute")
    bp.connect(gimbal_seed_sets[0], "then", gimbal_seed_sets[1], "execute")
    gimbal_seed_call = self_call("ApplyAirframeAngularRateLimitV1", 5376, 2880)
    bp.connect(gimbal_seed_sets[-1], "then", gimbal_seed_call, "execute")
    gimbal_seed_guard = builder.add("gimbal_seed_guard", "branch", 5632, 2880)
    bp.connect(gimbal_seed_call, "then", gimbal_seed_guard, "execute")
    bp.connect(helper_valid, "AirframePrebakeScratchResultValidV1", gimbal_seed_guard, "Condition")
    reject_seed_gimbal = set_("AirframePrebakeStageValidV1", "bool", 5888, 3360, "false")
    bp.connect(gimbal_seed_guard, "else", reject_seed_gimbal, "execute")
    seed_gimbal_adds = (
        add(candidates[candidate_specs[1][0]], candidate_specs[1][0], "quat", 5888, 2880, "seed_gimbal_quat", helper_quat, RESULT_QUAT),
        add(candidates[candidate_specs[3][0]], candidate_specs[3][0], "real", 6144, 2880, "seed_gimbal_rate", default_value="0.0"),
        add(candidates[candidate_specs[5][0]], candidate_specs[5][0], "bool", 6400, 2880, "seed_gimbal_limited", default_value="false"),
    )
    bp.connect(gimbal_seed_guard, "then", seed_gimbal_adds[0], "execute")
    for left, right in zip(seed_gimbal_adds, seed_gimbal_adds[1:]):
        bp.connect(left, "then", right, "execute")

    loop = builder.add("sample_loop", "loop", 6656, 2880)
    scalar.set_default(loop, "FirstIndex", "1")
    bp.connect(last, "ReturnValue", loop, "LastIndex")
    bp.connect(seed_gimbal_adds[-1], "then", loop, "Execute")
    previous_index = math("Subtract_IntInt", "int", loop, "Index", 6912, 1120, default_b="1")
    previous_body = item(candidates[candidate_specs[0][0]], candidate_specs[0][0], "quat", previous_index, "ReturnValue", 7168, 320, "previous_body")
    desired_body = item(bodies, "AirframePrebakeInputDesiredBodyQuatsV1", "quat", loop, "Index", 7168, 560, "desired_body")
    previous_gimbal = item(candidates[candidate_specs[1][0]], candidate_specs[1][0], "quat", previous_index, "ReturnValue", 7168, 800, "previous_gimbal")
    desired_gimbal = item(gimbals, "AirframePrebakeInputDesiredGimbalQuatsV1", "quat", loop, "Index", 7168, 1040, "desired_gimbal")
    previous_rate = item(rates, "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real", previous_index, "ReturnValue", 7168, 1280, "previous_rate")
    current_rate = item(rates, "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real", loop, "Index", 7168, 1520, "current_rate")
    previous_time_index = builder.add("previous_time_index", "convert", 7424, 1760)
    bp.connect(previous_index, "ReturnValue", previous_time_index, "InInt")
    previous_time = math("Multiply_DoubleDouble", "real", previous_time_index, "ReturnValue", 7680, 1760, step, "AirframePrebakeInputFixedStepSecondsV1")
    terminal_delta = math("Subtract_DoubleDouble", "real", total, "AirframePrebakeInputTotalSecondsV1", 7936, 1760, previous_time, "ReturnValue")
    is_terminal = compare("EqualEqual_IntInt", "int", loop, "Index", 7424, 2000, last, "ReturnValue")
    delta = select_real(is_terminal, terminal_delta, "ReturnValue", step, "AirframePrebakeInputFixedStepSecondsV1", 8192, 1760)
    previous_is_minimum = compare("LessEqual_DoubleDouble", "real", previous_rate, "Output", 7424, 2240, current_rate, "Output")
    interval_limit = select_real(previous_is_minimum, previous_rate, "Output", current_rate, "Output", 7680, 2240)

    body_sets = (
        set_("AirframePrebakeScratchPreviousQuatV1", "quat", 8448, 2880),
        set_("AirframePrebakeScratchDesiredQuatV1", "quat", 8704, 2880),
        set_("AirframePrebakeScratchDeltaSecondsV1", "real", 8960, 2880),
        set_("AirframePrebakeScratchMaximumRateDegreesPerSecondV1", "real", 9216, 2880),
    )
    for source, source_pin, target, target_pin in (
        (previous_body, "Output", body_sets[0], "AirframePrebakeScratchPreviousQuatV1"),
        (desired_body, "Output", body_sets[1], "AirframePrebakeScratchDesiredQuatV1"),
        (delta, "ReturnValue", body_sets[2], "AirframePrebakeScratchDeltaSecondsV1"),
        (interval_limit, "ReturnValue", body_sets[3], "AirframePrebakeScratchMaximumRateDegreesPerSecondV1"),
    ):
        bp.connect(source, source_pin, target, target_pin)
    bp.connect(loop, "LoopBody", body_sets[0], "execute")
    for left, right in zip(body_sets, body_sets[1:]):
        bp.connect(left, "then", right, "execute")
    body_call = self_call("ApplyAirframeAngularRateLimitV1", 9472, 2880)
    bp.connect(body_sets[-1], "then", body_call, "execute")
    body_guard = builder.add("body_guard", "branch", 9728, 2880)
    bp.connect(body_call, "then", body_guard, "execute")
    bp.connect(helper_valid, "AirframePrebakeScratchResultValidV1", body_guard, "Condition")
    body_reject = set_("AirframePrebakeStageValidV1", "bool", 9984, 3360, "false")
    bp.connect(body_guard, "else", body_reject, "execute")
    bp.connect(body_reject, "then", loop, "Break")
    helper_rate = get(RESULT_RATE, "real", 9728, 2400)
    helper_limited = get(RESULT_LIMITED, "bool", 9728, 2560)
    body_adds = (
        add(candidates[candidate_specs[0][0]], candidate_specs[0][0], "quat", 9984, 2880, "body_quat", helper_quat, RESULT_QUAT),
        add(candidates[candidate_specs[2][0]], candidate_specs[2][0], "real", 10240, 2880, "body_rate", helper_rate, RESULT_RATE),
        add(candidates[candidate_specs[4][0]], candidate_specs[4][0], "bool", 10496, 2880, "body_limited", helper_limited, RESULT_LIMITED),
    )
    bp.connect(body_guard, "then", body_adds[0], "execute")
    for left, right in zip(body_adds, body_adds[1:]):
        bp.connect(left, "then", right, "execute")

    gimbal_sets = (
        set_("AirframePrebakeScratchPreviousQuatV1", "quat", 10752, 2880),
        set_("AirframePrebakeScratchDesiredQuatV1", "quat", 11008, 2880),
    )
    bp.connect(previous_gimbal, "Output", gimbal_sets[0], "AirframePrebakeScratchPreviousQuatV1")
    bp.connect(desired_gimbal, "Output", gimbal_sets[1], "AirframePrebakeScratchDesiredQuatV1")
    bp.connect(body_adds[-1], "then", gimbal_sets[0], "execute")
    bp.connect(gimbal_sets[0], "then", gimbal_sets[1], "execute")
    gimbal_call = self_call("ApplyAirframeAngularRateLimitV1", 11264, 2880)
    bp.connect(gimbal_sets[-1], "then", gimbal_call, "execute")
    gimbal_guard = builder.add("gimbal_guard", "branch", 11520, 2880)
    bp.connect(gimbal_call, "then", gimbal_guard, "execute")
    bp.connect(helper_valid, "AirframePrebakeScratchResultValidV1", gimbal_guard, "Condition")
    gimbal_reject = set_("AirframePrebakeStageValidV1", "bool", 11776, 3360, "false")
    bp.connect(gimbal_guard, "else", gimbal_reject, "execute")
    bp.connect(gimbal_reject, "then", loop, "Break")
    gimbal_adds = (
        add(candidates[candidate_specs[1][0]], candidate_specs[1][0], "quat", 11776, 2880, "gimbal_quat", helper_quat, RESULT_QUAT),
        add(candidates[candidate_specs[3][0]], candidate_specs[3][0], "real", 12032, 2880, "gimbal_rate", helper_rate, RESULT_RATE),
        add(candidates[candidate_specs[5][0]], candidate_specs[5][0], "bool", 12288, 2880, "gimbal_limited", helper_limited, RESULT_LIMITED),
    )
    bp.connect(gimbal_guard, "then", gimbal_adds[0], "execute")
    for left, right in zip(gimbal_adds, gimbal_adds[1:]):
        bp.connect(left, "then", right, "execute")
    store_index = set_("AirframePrebakeStageIndexV1", "int", 12544, 2880)
    bp.connect(loop, "Index", store_index, "AirframePrebakeStageIndexV1")
    bp.connect(gimbal_adds[-1], "then", store_index, "execute")

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
