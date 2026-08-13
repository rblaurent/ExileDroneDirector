"""Build transactional desired airframe/gimbal samples from kinematic tracks."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "SolveAirframeDesiredPoseSamplesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
PROFILE_PAIRS = (
    ("AirframeDesiredStreamInputPathFollowWeightsV1", "AirframeGimbalInputPathFollowWeightV1"),
    ("AirframeDesiredStreamInputHorizonStabilizationWeightsV1", "AirframeGimbalInputHorizonStabilizationWeightV1"),
    ("AirframeDesiredStreamInputLookAheadSecondsV1", "AirframeGimbalInputLookAheadSecondsV1"),
    ("AirframeDesiredStreamInputBankGainsV1", "AirframeGimbalInputBankGainV1"),
    ("AirframeDesiredStreamInputMaxBankDegreesV1", "AirframeGimbalInputMaxBankDegreesV1"),
    ("AirframeDesiredStreamInputCameraUptiltDegreesV1", "AirframeGimbalInputCameraUptiltDegreesV1"),
    ("AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1", "AirframeGimbalInputMaxAngularRateDegreesPerSecondV1"),
    ("AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1", "AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1"),
    ("AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1", "AirframeGimbalInputMaxJerkCmPerSecondCubedV1"),
    ("AirframeDesiredStreamInputMinimumTurnRadiiCmV1", "AirframeGimbalInputMinimumTurnRadiusCmV1"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_pose_samples_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"), "real": ("real", "double", "None"),
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
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args(); scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-desired-stream-v1.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'), "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'), "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'), "loop": bp.find_block(loops, r"StandardMacros:ForLoopWithBreak"),
        "self_call": bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind)); pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)
    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind, array); return node
    def set_(name, kind, x, y, value=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind)
        if value is not None: scalar.set_default(node, name, value)
        return node
    def array_node(form, source, source_pin, kind, x, y):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y); target_pin = "TargetArray" if form in ("array_add", "array_clear", "length") else "Array"; pin_kind(node, target_pin, kind, True)
        if form == "array_add": pin_kind(node, "NewItem", kind); pin_kind(node, "ReturnValue", "int")
        elif form == "length": pin_kind(node, "ReturnValue", "int")
        elif form == "item": pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, target_pin); return node
    def item(source, source_pin, kind, index, x, y):
        node = array_node("item", source, source_pin, kind, x, y); bp.connect(index, "Index", node, "Dimension 1"); return node
    def math(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.math("Add_DoubleDouble", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, kind)
        bp.connect(left, left_pin, node, "A")
        if right is not None: bp.connect(right, right_pin, node, "B")
        else: scalar.set_default(node, "B", default_b)
        return node
    def self_call(name, x, y):
        node = b.add(f"call_{name}_{len(b.nodes)}", "self_call", x, y); node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1)); return node
    def append(target, target_pin, kind, value, value_pin, exec_source, x, y):
        node = array_node("array_add", target, target_pin, kind, x, y); bp.connect(value, value_pin, node, "NewItem"); bp.connect(exec_source, "then", node, "execute"); return node

    candidates_spec = (
        ("AirframeDesiredStreamCandidateLookAheadVelocitiesV1", "vector"), ("AirframeDesiredStreamCandidateBodyQuatsV1", "quat"),
        ("AirframeDesiredStreamCandidateGimbalQuatsV1", "quat"), ("AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1", "real"),
    )
    candidates = {name: get(name, kind, 0, 160 + i * 160, True) for i, (name, kind) in enumerate(candidates_spec)}
    clears = [array_node("array_clear", candidates[name], name, kind, 256 + i * 256, 3520) for i, (name, kind) in enumerate(candidates_spec)]
    bp.connect(b.entry, "then", clears[0], "execute")
    for left, right in zip(clears, clears[1:]): bp.connect(left, "then", right, "execute")
    stage = get("AirframeDesiredStreamStageValidV1", "bool", 0, 960)
    stage_guard = b.add("stage_guard", "branch", 1280, 3520); bp.connect(clears[-1], "then", stage_guard, "execute"); bp.connect(stage, "AirframeDesiredStreamStageValidV1", stage_guard, "Condition")

    source_specs = (
        ("AirframeDesiredStreamCandidateVelocitiesV1", "vector"), ("AirframeDesiredStreamCandidateAccelerationsV1", "vector"),
        ("AirframeDesiredStreamCandidateJerksV1", "vector"), ("AirframeDesiredStreamInputAuthoredBodyQuatsV1", "quat"),
        ("AirframeDesiredStreamInputAuthoredGimbalQuatsV1", "quat"), *[(name, "real") for name, _ in PROFILE_PAIRS],
    )
    sources = {name: get(name, kind, 0, 1280 + i * 144, True) for i, (name, kind) in enumerate(source_specs)}
    velocities = sources[source_specs[0][0]]; length = array_node("length", velocities, source_specs[0][0], "vector", 320, 1280)
    last = math("Subtract_IntInt", length, "ReturnValue", 576, 1280, default_b="1", kind="int")
    total = get("AirframeDesiredStreamInputTotalSecondsV1", "real", 0, 3520); step = get("AirframeDesiredStreamInputFixedStepSecondsV1", "real", 0, 3680)
    loop = b.add("loop", "loop", 1536, 3520); scalar.set_default(loop, "FirstIndex", "0"); bp.connect(last, "ReturnValue", loop, "LastIndex"); bp.connect(stage_guard, "then", loop, "Execute")
    loop_guard = b.add("loop_guard", "branch", 1792, 3520); bp.connect(loop, "LoopBody", loop_guard, "execute"); bp.connect(stage, "AirframeDesiredStreamStageValidV1", loop_guard, "Condition")
    stage_index = set_("AirframeDesiredStreamStageIndexV1", "int", 2048, 3520); bp.connect(loop, "Index", stage_index, "AirframeDesiredStreamStageIndexV1"); bp.connect(loop_guard, "then", stage_index, "execute")
    items = {name: item(sources[name], name, kind, loop, 2304, 1120 + i * 144) for i, (name, kind) in enumerate(source_specs)}
    converted = b.add("converted_index", "convert", 2304, 3360); bp.connect(loop, "Index", converted, "InInt")
    sample_time_raw = math("Multiply_DoubleDouble", converted, "ReturnValue", 2560, 3360, step, "AirframeDesiredStreamInputFixedStepSecondsV1")
    sample_time = math("FMin", sample_time_raw, "ReturnValue", 2816, 3360, total, "AirframeDesiredStreamInputTotalSecondsV1")
    lookahead_item = items[PROFILE_PAIRS[2][0]]
    query_time = math("Add_DoubleDouble", sample_time, "ReturnValue", 3072, 3360, lookahead_item, "Output")
    query_set = set_("AirframeDesiredStreamVelocitySampleInputSecondsV1", "real", 3328, 3520); bp.connect(query_time, "ReturnValue", query_set, "AirframeDesiredStreamVelocitySampleInputSecondsV1"); bp.connect(stage_index, "then", query_set, "execute")
    sample_call = self_call("SampleAirframeDesiredVelocityAtTimeV1", 3584, 3520); bp.connect(query_set, "then", sample_call, "execute")
    sample_valid = get("AirframeDesiredStreamVelocitySampleResultValidV1", "bool", 3584, 3200); sample_guard = b.add("sample_guard", "branch", 3840, 3520); bp.connect(sample_call, "then", sample_guard, "execute"); bp.connect(sample_valid, "AirframeDesiredStreamVelocitySampleResultValidV1", sample_guard, "Condition")
    sample_reject = set_("AirframeDesiredStreamStageValidV1", "bool", 4096, 3840, "false"); bp.connect(sample_guard, "else", sample_reject, "execute"); bp.connect(sample_reject, "then", loop, "Break")
    sample_result = get("AirframeDesiredStreamVelocitySampleResultV1", "vector", 3840, 3040)

    solver_sets = []
    solver_inputs = (
        ("AirframeGimbalInputCurrentVelocityV1", "vector", items[source_specs[0][0]], "Output"),
        ("AirframeGimbalInputLookAheadVelocityV1", "vector", sample_result, "AirframeDesiredStreamVelocitySampleResultV1"),
        ("AirframeGimbalInputAccelerationV1", "vector", items[source_specs[1][0]], "Output"),
        ("AirframeGimbalInputJerkV1", "vector", items[source_specs[2][0]], "Output"),
        ("AirframeGimbalInputAuthoredBodyQuatV1", "quat", items[source_specs[3][0]], "Output"),
        ("AirframeGimbalInputAuthoredGimbalQuatV1", "quat", items[source_specs[4][0]], "Output"),
        *[(target_name, "real", items[source_name], "Output") for source_name, target_name in PROFILE_PAIRS],
    )
    for i, (name, kind, value, value_pin) in enumerate(solver_inputs):
        node = set_(name, kind, 4096 + i * 224, 3520); bp.connect(value, value_pin, node, name); solver_sets.append(node)
    bp.connect(sample_guard, "then", solver_sets[0], "execute")
    for left, right in zip(solver_sets, solver_sets[1:]): bp.connect(left, "then", right, "execute")
    solve_call = self_call("SolveAirframeGimbalV1", 7808, 3520); bp.connect(solver_sets[-1], "then", solve_call, "execute")
    solve_valid = get("AirframeGimbalResultValidV1", "bool", 7808, 3200); solve_guard = b.add("solve_guard", "branch", 8064, 3520); bp.connect(solve_call, "then", solve_guard, "execute"); bp.connect(solve_valid, "AirframeGimbalResultValidV1", solve_guard, "Condition")
    solve_reject = set_("AirframeDesiredStreamStageValidV1", "bool", 8320, 3840, "false"); bp.connect(solve_guard, "else", solve_reject, "execute"); bp.connect(solve_reject, "then", loop, "Break")
    body_result = get("AirframeGimbalResultBodyQuatV1", "quat", 8064, 2880); gimbal_result = get("AirframeGimbalResultGimbalQuatV1", "quat", 8064, 3040)
    outputs = (
        (candidates_spec[0], sample_result, "AirframeDesiredStreamVelocitySampleResultV1"),
        (candidates_spec[1], body_result, "AirframeGimbalResultBodyQuatV1"),
        (candidates_spec[2], gimbal_result, "AirframeGimbalResultGimbalQuatV1"),
        (candidates_spec[3], items[PROFILE_PAIRS[6][0]], "Output"),
    )
    adds = []
    for i, ((name, kind), value, value_pin) in enumerate(outputs):
        exec_source = solve_guard if i == 0 else adds[-1]; node = append(candidates[name], name, kind, value, value_pin, exec_source, 8320 + i * 256, 3520); adds.append(node)

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]; args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
