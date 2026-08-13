"""Build fail-closed current/neighbor staging for C2 flight-profile smoothing."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageSmoothedFlightProfileSamplesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
PARAMETERS = (
    "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
    "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
    "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_smoothed_flight_profile_stage_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, value: str, array: bool = False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""),
        "real": ("real", "double"), "string": ("string", ""),
    }[value]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
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
    evaluator = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-compiled-flight-profile-v1.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    forms.update({
        "length": bp.find_block(evaluator, r'MemberName="Array_Length"'),
        "select": bp.find_block(public_list, r'^Begin Object Class=/Script/BlueprintGraph.K2Node_Select '),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, value: str, array: bool = False):
        scalar.retarget_variable(node, name, "real" if value == "int" else value)
        pin_kind(node, name, value, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", value)

    def get(name: str, value: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, value, array)
        return node

    def set_value(name: str, value: str, x: int, y: int, default: str | None = None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, value)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def compare(member: str, left, left_pin: str, right, right_pin: str, value: str, x: int, y: int):
        node = builder.add(f"compare_{member}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, value)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def integer_math(member: str, left, left_pin: str, constant: str, x: int, y: int):
        node = builder.add(f"integer_{member}_{len(builder.nodes)}", "math", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, "int")
        bp.connect(left, left_pin, node, "A")
        scalar.set_default(node, "B", constant)
        return node

    def boolean_and(guards, x: int, y: int):
        node, output = guards[0]
        for index, (guard, guard_pin) in enumerate(guards[1:]):
            node = compare("BooleanAND", node, output, guard, guard_pin, "bool", x + index * 224, y)
            output = "ReturnValue"
        return node, output

    def select(condition, condition_pin: str, false_source, false_pin: str, true_source, true_pin: str, value: str, x: int, y: int, false_default=None, true_default=None):
        node = builder.add(f"select_{value}_{len(builder.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"):
            pin_kind(node, pin, value)
        pin_kind(node, "Index", "bool")
        bp.connect(condition, condition_pin, node, "Index")
        if false_source is None:
            scalar.set_default(node, "Option 0", false_default)
        else:
            bp.connect(false_source, false_pin, node, "Option 0")
        if true_source is None:
            scalar.set_default(node, "Option 1", true_default)
        else:
            bp.connect(true_source, true_pin, node, "Option 1")
        return node

    def call(member: str, x: int, y: int):
        node = builder.add(f"call_{member}_{len(builder.nodes)}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1,
            ),
        )
        return node

    # Immutable inputs and publication shape.
    requested = get("SmoothedFlightProfileInputSegmentIndexV1", "int", 0, 0)
    alpha = get("SmoothedFlightProfileInputLocalTimeAlphaV1", "real", 0, 160)
    compile_valid = get("FlightProfileCompileValidV1", "bool", 0, 320)
    compiled_ids = get("FlightProfileCompiledIdsV1", "string", 0, 480, True)
    length = builder.add("compiled_id_length", "length", 320, 480)
    pin_kind(length, "TargetArray", "string", True)
    bp.connect(compiled_ids, "FlightProfileCompiledIdsV1", length, "TargetArray")

    alpha_finite = builder.finite(alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1", 320, 0)
    guards = [
        (compile_valid, "FlightProfileCompileValidV1"),
        (alpha_finite, "ReturnValue"),
        (compare("GreaterEqual_DoubleDouble", alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1", None, "0.0", "real", 768, 0), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1", None, "1.0", "real", 768, 160), "ReturnValue"),
        (compare("GreaterEqual_IntInt", length, "ReturnValue", None, "1", "int", 768, 320), "ReturnValue"),
        (compare("LessEqual_IntInt", length, "ReturnValue", None, "511", "int", 768, 480), "ReturnValue"),
        (compare("GreaterEqual_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", None, "0", "int", 768, 640), "ReturnValue"),
        (compare("Less_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", length, "ReturnValue", "int", 768, 800), "ReturnValue"),
    ]
    ready, ready_pin = boolean_and(guards, 1024, 320)

    # Set the helper index before validation so every exit leaves it at the requested value.
    # Root at the selection center on a clear lane: Unreal recenters pasted
    # selections regardless of viewport panning, so this makes the native-entry
    # seam deterministic even for a wide generated body.
    set_requested = set_value("FlightProfileInputSegmentIndexV1", "int", 4800, 1280)
    bp.connect(builder.entry, "then", set_requested, "execute")
    bp.connect(requested, "SmoothedFlightProfileInputSegmentIndexV1", set_requested, "FlightProfileInputSegmentIndexV1")
    guard_branch = builder.add("guard_branch", "branch", 512, 1920)
    bp.connect(set_requested, "then", guard_branch, "execute")
    bp.connect(ready, ready_pin, guard_branch, "Condition")

    current_call = call("EvaluateCompiledFlightProfileV1", 768, 1920)
    bp.connect(guard_branch, "then", current_call, "execute")
    current_valid = get("FlightProfileResultValidV1", "bool", 1024, 1600)
    current_branch = builder.add("current_branch", "branch", 1024, 1920)
    bp.connect(current_call, "then", current_branch, "execute")
    bp.connect(current_valid, "FlightProfileResultValidV1", current_branch, "Condition")

    result_sources = [("Id", "string"), *((name, "real") for name in PARAMETERS)]
    current_setters = []
    for index, (suffix, value) in enumerate(result_sources):
        source_name = f"FlightProfileResult{suffix}V1"
        target_name = f"SmoothedFlightProfileCurrent{suffix}V1"
        source = get(source_name, value, 1280 + index * 288, 1280)
        setter = set_value(target_name, value, 1280 + index * 288, 1920)
        bp.connect(source, source_name, setter, target_name)
        current_setters.append(setter)
    bp.connect(current_branch, "then", current_setters[0], "execute")
    for left, right in zip(current_setters, current_setters[1:]):
        bp.connect(left, "then", right, "execute")

    # Pure, clamped adjacent-index choice. No Max_IntInt/Min_IntInt nodes.
    previous = integer_math("Subtract_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", "1", 1792, 320)
    following = integer_math("Add_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", "1", 1792, 480)
    last = integer_math("Subtract_IntInt", length, "ReturnValue", "1", 1792, 640)
    has_previous = compare("Greater_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", None, "0", "int", 2048, 320)
    has_following = compare("Less_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", last, "ReturnValue", "int", 2048, 480)
    left_index = select(has_previous, "ReturnValue", requested, "SmoothedFlightProfileInputSegmentIndexV1", previous, "ReturnValue", "int", 2304, 320)
    right_index = select(has_following, "ReturnValue", requested, "SmoothedFlightProfileInputSegmentIndexV1", following, "ReturnValue", "int", 2304, 480)
    right_half = compare("Greater_DoubleDouble", alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1", None, "0.5", "real", 2048, 640)
    neighbor_index = select(right_half, "ReturnValue", left_index, "ReturnValue", right_index, "ReturnValue", "int", 2560, 400)
    same_index = compare("EqualEqual_IntInt", requested, "SmoothedFlightProfileInputSegmentIndexV1", neighbor_index, "ReturnValue", "int", 2816, 400)

    # Quintic half-curve weight, then force endpoint/self-neighbor weight to exact zero.
    left_t = scalar.mul_const(builder, alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1", "2.0", 1792, 800)
    left_s, left_s_pin = scalar.profile_formula(builder, "smootherstep", left_t, 2048, 800)
    one_minus_left = builder.math("Subtract_DoubleDouble", 3552, 800)
    scalar.set_default(one_minus_left, "A", "1.0")
    bp.connect(left_s, left_s_pin, one_minus_left, "B")
    left_weight = scalar.mul_const(builder, one_minus_left, "ReturnValue", "0.5", 3776, 800)
    doubled_alpha = scalar.mul_const(builder, alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1", "2.0", 1792, 1120)
    right_t = builder.math("Subtract_DoubleDouble", 2048, 1120, "1.0")
    bp.connect(doubled_alpha, "ReturnValue", right_t, "A")
    right_s, right_s_pin = scalar.profile_formula(builder, "smootherstep", right_t, 2272, 1120)
    right_weight = scalar.mul_const(builder, right_s, right_s_pin, "0.5", 3776, 1120)
    half_weight = select(right_half, "ReturnValue", left_weight, "ReturnValue", right_weight, "ReturnValue", "real", 4032, 960)
    neighbor_weight = select(same_index, "ReturnValue", half_weight, "ReturnValue", None, "", "real", 4288, 960, true_default="0.0")

    set_neighbor_index = set_value("FlightProfileInputSegmentIndexV1", "int", 4608, 1920)
    bp.connect(current_setters[-1], "then", set_neighbor_index, "execute")
    bp.connect(neighbor_index, "ReturnValue", set_neighbor_index, "FlightProfileInputSegmentIndexV1")
    neighbor_call = call("EvaluateCompiledFlightProfileV1", 4864, 1920)
    bp.connect(set_neighbor_index, "then", neighbor_call, "execute")
    neighbor_valid = get("FlightProfileResultValidV1", "bool", 5120, 1600)
    neighbor_branch = builder.add("neighbor_branch", "branch", 5120, 1920)
    bp.connect(neighbor_call, "then", neighbor_branch, "execute")
    bp.connect(neighbor_valid, "FlightProfileResultValidV1", neighbor_branch, "Condition")

    neighbor_setters = []
    for index, (suffix, value) in enumerate(result_sources):
        source_name = f"FlightProfileResult{suffix}V1"
        target_name = f"SmoothedFlightProfileNeighbor{suffix}V1"
        source = get(source_name, value, 5376 + index * 288, 1280)
        setter = set_value(target_name, value, 5376 + index * 288, 1920)
        bp.connect(source, source_name, setter, target_name)
        neighbor_setters.append(setter)
    weight_setter = set_value("SmoothedFlightProfileNeighborWeightV1", "real", 8544, 1920)
    bp.connect(neighbor_weight, "ReturnValue", weight_setter, "SmoothedFlightProfileNeighborWeightV1")
    neighbor_setters.append(weight_setter)
    bp.connect(neighbor_branch, "then", neighbor_setters[0], "execute")
    for left, right in zip(neighbor_setters, neighbor_setters[1:]):
        bp.connect(left, "then", right, "execute")

    # Successful neighbor staging must restore and re-evaluate the requested current sample.
    restore_success = set_value("FlightProfileInputSegmentIndexV1", "int", 8832, 1920)
    bp.connect(neighbor_setters[-1], "then", restore_success, "execute")
    bp.connect(requested, "SmoothedFlightProfileInputSegmentIndexV1", restore_success, "FlightProfileInputSegmentIndexV1")
    restore_success_call = call("EvaluateCompiledFlightProfileV1", 9088, 1920)
    bp.connect(restore_success, "then", restore_success_call, "execute")
    restored_valid = get("FlightProfileResultValidV1", "bool", 9344, 1600)
    restored_branch = builder.add("restored_branch", "branch", 9344, 1920)
    bp.connect(restore_success_call, "then", restored_branch, "execute")
    bp.connect(restored_valid, "FlightProfileResultValidV1", restored_branch, "Condition")
    stage_valid = set_value("SmoothedFlightProfileStageValidV1", "bool", 9600, 1920, "true")
    bp.connect(restored_branch, "then", stage_valid, "execute")

    # A neighbor helper failure also restores the helper index, but never publishes stage validity.
    restore_failure = set_value("FlightProfileInputSegmentIndexV1", "int", 5376, 2240)
    bp.connect(neighbor_branch, "else", restore_failure, "execute")
    bp.connect(requested, "SmoothedFlightProfileInputSegmentIndexV1", restore_failure, "FlightProfileInputSegmentIndexV1")
    restore_failure_call = call("EvaluateCompiledFlightProfileV1", 5632, 2240)
    bp.connect(restore_failure, "then", restore_failure_call, "execute")

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
