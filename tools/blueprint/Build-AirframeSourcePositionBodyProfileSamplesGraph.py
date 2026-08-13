"""Build aligned position, authored-body, and smoothed-profile source samples."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildAirframeSourcePositionBodyProfileSamplesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
PROFILE_FIELDS = (
    "PathFollowWeight",
    "HorizonStabilizationWeight",
    "LookAheadSeconds",
    "BankGain",
    "MaxBankDegrees",
    "CameraUptiltDegrees",
    "MaxAngularRateDegreesPerSecond",
    "MaxAccelerationCmPerSecondSquared",
    "MaxJerkCmPerSecondCubed",
    "MinimumTurnRadiusCm",
)
CANDIDATES = (
    ("AirframeSourceCandidatePositionsV1", "vector", "PositionRouteResultPositionV1"),
    ("AirframeSourceCandidateBodyQuatsV1", "quat", "OrientationTrackResultQuatV1"),
    ("AirframeSourceCandidatePathFollowWeightsV1", "real", "SmoothedFlightProfileResultPathFollowWeightV1"),
    ("AirframeSourceCandidateHorizonStabilizationWeightsV1", "real", "SmoothedFlightProfileResultHorizonStabilizationWeightV1"),
    ("AirframeSourceCandidateLookAheadSecondsV1", "real", "SmoothedFlightProfileResultLookAheadSecondsV1"),
    ("AirframeSourceCandidateBankGainsV1", "real", "SmoothedFlightProfileResultBankGainV1"),
    ("AirframeSourceCandidateMaxBankDegreesV1", "real", "SmoothedFlightProfileResultMaxBankDegreesV1"),
    ("AirframeSourceCandidateCameraUptiltDegreesV1", "real", "SmoothedFlightProfileResultCameraUptiltDegreesV1"),
    ("AirframeSourceCandidateMaxAngularRatesDegreesPerSecondV1", "real", "SmoothedFlightProfileResultMaxAngularRateDegreesPerSecondV1"),
    ("AirframeSourceCandidateMaxAccelerationsCmPerSecondSquaredV1", "real", "SmoothedFlightProfileResultMaxAccelerationCmPerSecondSquaredV1"),
    ("AirframeSourceCandidateMaxJerksCmPerSecondCubedV1", "real", "SmoothedFlightProfileResultMaxJerkCmPerSecondCubedV1"),
    ("AirframeSourceCandidateMinimumTurnRadiiCmV1", "real", "SmoothedFlightProfileResultMinimumTurnRadiusCmV1"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_body_samples_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind, array=False):
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
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-source-sampling-v1.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "loop": bp.find_block(loops, r"StandardMacros:ForLoopWithBreak"),
        "self_call": bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None, array=False):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind, array)
        if value is not None:
            scalar.set_default(node, name, value)
        return node

    def array_node(form, source, source_pin, kind, x, y):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y)
        target_pin = "TargetArray" if form in ("array_add", "array_clear", "length") else "Array"
        pin_kind(node, target_pin, kind, True)
        if form == "array_add":
            pin_kind(node, "NewItem", kind)
            pin_kind(node, "ReturnValue", "int")
        elif form == "length":
            pin_kind(node, "ReturnValue", "int")
        elif form == "item":
            pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, target_pin)
        return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = array_node("item", source, source_pin, kind, x, y)
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default_b)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def math_node(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.math("Add_DoubleDouble", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, kind)
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default_b)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        current_pin = current[1]
        current_node = current[0]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            current_node = compare("BooleanAND", current_node, current_pin, x + index * 224, y, condition, condition_pin, kind="bool")
            current_pin = "ReturnValue"
        return current_node

    def self_call(name, x, y):
        node = b.add(f"call_{name}_{len(b.nodes)}", "self_call", x, y)
        node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1,
            ),
        )
        return node

    candidates = {
        name: get(name, kind, 0, 160 + index * 144, True)
        for index, (name, kind, _source) in enumerate(CANDIDATES)
    }
    clears = [
        array_node("array_clear", candidates[name], name, kind, 320 + index * 256, 4160)
        for index, (name, kind, _source) in enumerate(CANDIDATES)
    ]
    bp.connect(b.entry, "then", clears[0], "execute")
    for left, right in zip(clears, clears[1:]):
        bp.connect(left, "then", right, "execute")
    stage = get("AirframeSourceStageValidV1", "bool", 0, 2080)
    stage_guard = b.add("stage_guard", "branch", 3584, 4160)
    bp.connect(clears[-1], "then", stage_guard, "execute")
    bp.connect(stage, "AirframeSourceStageValidV1", stage_guard, "Condition")

    body_authored = get("AirframeSourceInputBodyWaypointQuatsV1", "quat", 0, 2320, True)
    durations_input = get("PositionRouteInputDurationsV1", "real", 0, 2480, True)
    stage_body = set_("OrientationTrackInputWaypointQuatsV1", "quat", 3840, 4160, array=True)
    stage_durations = set_("OrientationTrackInputDurationsV1", "real", 4096, 4160, array=True)
    bp.connect(body_authored, "AirframeSourceInputBodyWaypointQuatsV1", stage_body, "OrientationTrackInputWaypointQuatsV1")
    bp.connect(durations_input, "PositionRouteInputDurationsV1", stage_durations, "OrientationTrackInputDurationsV1")
    bp.connect(stage_guard, "then", stage_body, "execute")
    bp.connect(stage_body, "then", stage_durations, "execute")
    compile_body = self_call("CompileOrientationTrackV1", 4352, 4160)
    bp.connect(stage_durations, "then", compile_body, "execute")

    orientation_valid = get("OrientationTrackCompileValidV1", "bool", 3840, 2720)
    source_total = get("AirframeSourceTotalSecondsV1", "real", 3840, 2880)
    position_total = get("PositionRouteCompiledTotalSecondsV1", "real", 3840, 3040)
    orientation_total = get("OrientationTrackCompiledTotalSecondsV1", "real", 3840, 3200)
    position_durations = get("PositionRouteCompiledDurationsV1", "real", 3840, 3360, True)
    orientation_durations = get("OrientationTrackCompiledDurationsV1", "real", 3840, 3520, True)
    position_starts = get("PositionRouteCompiledSegmentStartsV1", "real", 3840, 3680, True)
    orientation_starts = get("OrientationTrackCompiledSegmentStartsV1", "real", 3840, 3840, True)
    timeline_arrays = (
        (position_durations, "PositionRouteCompiledDurationsV1"),
        (orientation_durations, "OrientationTrackCompiledDurationsV1"),
        (position_starts, "PositionRouteCompiledSegmentStartsV1"),
        (orientation_starts, "OrientationTrackCompiledSegmentStartsV1"),
    )
    lengths = [array_node("length", node, pin, "real", 4672, 3360 + index * 160) for index, (node, pin) in enumerate(timeline_arrays)]
    preflight_conditions = (
        (orientation_valid, "OrientationTrackCompileValidV1"),
        (compare("EqualEqual_DoubleDouble", source_total, "AirframeSourceTotalSecondsV1", 4928, 2880, position_total, "PositionRouteCompiledTotalSecondsV1"), "ReturnValue"),
        (compare("EqualEqual_DoubleDouble", source_total, "AirframeSourceTotalSecondsV1", 4928, 3200, orientation_total, "OrientationTrackCompiledTotalSecondsV1"), "ReturnValue"),
        (compare("Greater_IntInt", lengths[0], "ReturnValue", 4928, 3360, default_b="0", kind="int"), "ReturnValue"),
        *((compare("EqualEqual_IntInt", lengths[0], "ReturnValue", 4928, 3520 + index * 160, other, "ReturnValue", kind="int"), "ReturnValue") for index, other in enumerate(lengths[1:])),
    )
    preflight_valid = and_all(preflight_conditions, 5376, 4000)
    preflight = b.add("preflight", "branch", 6720, 4160)
    bp.connect(compile_body, "then", preflight, "execute")
    bp.connect(preflight_valid, "ReturnValue", preflight, "Condition")
    preflight_reject = set_("AirframeSourceStageValidV1", "bool", 6976, 4480, "false")
    bp.connect(preflight, "else", preflight_reject, "execute")

    timeline_loop = b.add("timeline_loop", "foreach", 6976, 3520)
    pin_kind(timeline_loop, "Array", "real", True)
    pin_kind(timeline_loop, "Array Element", "real")
    bp.connect(position_durations, "PositionRouteCompiledDurationsV1", timeline_loop, "Array")
    bp.connect(preflight, "then", timeline_loop, "Exec")
    other_duration = item(orientation_durations, "OrientationTrackCompiledDurationsV1", "real", timeline_loop, "Array Index", 7232, 3360)
    position_start = item(position_starts, "PositionRouteCompiledSegmentStartsV1", "real", timeline_loop, "Array Index", 7232, 3520)
    orientation_start = item(orientation_starts, "OrientationTrackCompiledSegmentStartsV1", "real", timeline_loop, "Array Index", 7232, 3680)
    duration_equal = compare("EqualEqual_DoubleDouble", timeline_loop, "Array Element", 7488, 3360, other_duration, "Output")
    start_equal = compare("EqualEqual_DoubleDouble", position_start, "Output", 7488, 3600, orientation_start, "Output")
    item_valid = compare("BooleanAND", duration_equal, "ReturnValue", 7744, 3520, start_equal, "ReturnValue", kind="bool")
    item_branch = b.add("timeline_item_branch", "branch", 8000, 3520)
    bp.connect(timeline_loop, "LoopBody", item_branch, "execute")
    bp.connect(item_valid, "ReturnValue", item_branch, "Condition")
    timeline_reject = set_("AirframeSourceStageValidV1", "bool", 8256, 3760, "false")
    bp.connect(item_branch, "else", timeline_reject, "execute")

    final_stage = get("AirframeSourceStageValidV1", "bool", 8256, 3200)
    timeline_guard = b.add("timeline_guard", "branch", 8512, 3520)
    bp.connect(timeline_loop, "Completed", timeline_guard, "execute")
    bp.connect(final_stage, "AirframeSourceStageValidV1", timeline_guard, "Condition")
    expected_count = get("AirframeSourceExpectedSampleCountV1", "int", 8256, 4000)
    last_index = math_node("Subtract_IntInt", expected_count, "AirframeSourceExpectedSampleCountV1", 8512, 4000, default_b="1", kind="int")
    sample_loop = b.add("sample_loop", "loop", 8768, 3520)
    scalar.set_default(sample_loop, "FirstIndex", "0")
    bp.connect(last_index, "ReturnValue", sample_loop, "LastIndex")
    bp.connect(timeline_guard, "then", sample_loop, "Execute")
    sample_guard = b.add("sample_stage_guard", "branch", 9024, 3520)
    bp.connect(sample_loop, "LoopBody", sample_guard, "execute")
    bp.connect(stage, "AirframeSourceStageValidV1", sample_guard, "Condition")

    set_index = set_("AirframeSourceSampleIndexV1", "int", 9280, 3520)
    bp.connect(sample_loop, "Index", set_index, "AirframeSourceSampleIndexV1")
    bp.connect(sample_guard, "then", set_index, "execute")
    converted = b.add("converted_index", "convert", 9280, 3200)
    bp.connect(sample_loop, "Index", converted, "InInt")
    fixed_step = get("AirframeSourceInputFixedStepSecondsV1", "real", 9024, 3040)
    elapsed_raw = math_node("Multiply_DoubleDouble", converted, "ReturnValue", 9536, 3200, fixed_step, "AirframeSourceInputFixedStepSecondsV1")
    elapsed = math_node("FMin", elapsed_raw, "ReturnValue", 9792, 3200, source_total, "AirframeSourceTotalSecondsV1")
    set_elapsed = set_("AirframeSourceSampleElapsedSecondsV1", "real", 9536, 3520)
    bp.connect(elapsed, "ReturnValue", set_elapsed, "AirframeSourceSampleElapsedSecondsV1")
    bp.connect(set_index, "then", set_elapsed, "execute")
    set_position_elapsed = set_("PositionRouteInputElapsedSecondsV1", "real", 9792, 3520)
    set_orientation_elapsed = set_("OrientationTrackInputElapsedSecondsV1", "real", 10048, 3520)
    for setter, name in ((set_position_elapsed, "PositionRouteInputElapsedSecondsV1"), (set_orientation_elapsed, "OrientationTrackInputElapsedSecondsV1")):
        bp.connect(elapsed, "ReturnValue", setter, name)
    bp.connect(set_elapsed, "then", set_position_elapsed, "execute")
    bp.connect(set_position_elapsed, "then", set_orientation_elapsed, "execute")
    evaluate_position = self_call("EvaluateCompiledPositionRouteV1", 10304, 3520)
    evaluate_body = self_call("EvaluateCompiledOrientationTrackV1", 10560, 3520)
    bp.connect(set_orientation_elapsed, "then", evaluate_position, "execute")
    bp.connect(evaluate_position, "then", evaluate_body, "execute")

    position_valid = get("PositionRouteResultValidV1", "bool", 10304, 2400)
    body_valid = get("OrientationTrackResultValidV1", "bool", 10560, 2400)
    position_segment = get("PositionRouteResultSegmentIndexV1", "int", 10816, 2400)
    body_segment = get("OrientationTrackResultSegmentIndexV1", "int", 10816, 2560)
    position_alpha = get("PositionRouteResultLocalTimeAlphaV1", "real", 10816, 2720)
    body_alpha = get("OrientationTrackResultAlphaV1", "real", 10816, 2880)
    position_complete = get("PositionRouteResultCompleteV1", "bool", 10816, 3040)
    body_complete = get("OrientationTrackResultCompleteV1", "bool", 10816, 3200)
    evaluation_conditions = (
        (position_valid, "PositionRouteResultValidV1"),
        (body_valid, "OrientationTrackResultValidV1"),
        (compare("EqualEqual_IntInt", position_segment, "PositionRouteResultSegmentIndexV1", 11072, 2480, body_segment, "OrientationTrackResultSegmentIndexV1", kind="int"), "ReturnValue"),
        (compare("EqualEqual_DoubleDouble", position_alpha, "PositionRouteResultLocalTimeAlphaV1", 11072, 2800, body_alpha, "OrientationTrackResultAlphaV1"), "ReturnValue"),
        (compare("EqualEqual_BoolBool", position_complete, "PositionRouteResultCompleteV1", 11072, 3120, body_complete, "OrientationTrackResultCompleteV1", kind="bool"), "ReturnValue"),
    )
    evaluation_valid = and_all(evaluation_conditions, 11520, 3360)
    evaluation_branch = b.add("evaluation_branch", "branch", 12640, 3520)
    bp.connect(evaluate_body, "then", evaluation_branch, "execute")
    bp.connect(evaluation_valid, "ReturnValue", evaluation_branch, "Condition")
    evaluation_reject = set_("AirframeSourceStageValidV1", "bool", 12896, 3840, "false")
    bp.connect(evaluation_branch, "else", evaluation_reject, "execute")
    bp.connect(evaluation_reject, "then", sample_loop, "Break")

    stage_profile_segment = set_("SmoothedFlightProfileInputSegmentIndexV1", "int", 12896, 3520)
    stage_profile_alpha = set_("SmoothedFlightProfileInputLocalTimeAlphaV1", "real", 13152, 3520)
    bp.connect(position_segment, "PositionRouteResultSegmentIndexV1", stage_profile_segment, "SmoothedFlightProfileInputSegmentIndexV1")
    bp.connect(position_alpha, "PositionRouteResultLocalTimeAlphaV1", stage_profile_alpha, "SmoothedFlightProfileInputLocalTimeAlphaV1")
    bp.connect(evaluation_branch, "then", stage_profile_segment, "execute")
    bp.connect(stage_profile_segment, "then", stage_profile_alpha, "execute")
    evaluate_profile = self_call("EvaluateSmoothedFlightProfileV1", 13408, 3520)
    bp.connect(stage_profile_alpha, "then", evaluate_profile, "execute")
    profile_valid = get("SmoothedFlightProfileResultValidV1", "bool", 13408, 3200)
    profile_branch = b.add("profile_branch", "branch", 13664, 3520)
    bp.connect(evaluate_profile, "then", profile_branch, "execute")
    bp.connect(profile_valid, "SmoothedFlightProfileResultValidV1", profile_branch, "Condition")
    profile_reject = set_("AirframeSourceStageValidV1", "bool", 13920, 3840, "false")
    bp.connect(profile_branch, "else", profile_reject, "execute")
    bp.connect(profile_reject, "then", sample_loop, "Break")

    result_sources = {
        "PositionRouteResultPositionV1": get("PositionRouteResultPositionV1", "vector", 13664, 2240),
        "OrientationTrackResultQuatV1": get("OrientationTrackResultQuatV1", "quat", 13664, 2400),
        **{
            f"SmoothedFlightProfileResult{field}V1": get(f"SmoothedFlightProfileResult{field}V1", "real", 13664, 2560 + index * 144)
            for index, field in enumerate(PROFILE_FIELDS)
        },
    }
    adds = []
    for index, (name, kind, source_name) in enumerate(CANDIDATES):
        node = array_node("array_add", candidates[name], name, kind, 13920 + index * 256, 3520)
        bp.connect(result_sources[source_name], source_name, node, "NewItem")
        bp.connect(profile_branch if index == 0 else adds[-1], "then", node, "execute")
        adds.append(node)

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
