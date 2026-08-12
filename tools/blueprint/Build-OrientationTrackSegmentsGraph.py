"""Build deterministic multi-key orientation segment controls and start times."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "BuildOrientationTrackSegmentsV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_track_segments_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"), "real": ("real", "double", "None"),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[value]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def variable(scalar, node, name, value, array=False):
    scalar.retarget_variable(node, name, "vector" if value in ("quat", "vector") else value)
    kind(node, name, value, array)
    if "Output_Get" in node.pins:
        kind(node, "Output_Get", value)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args(); scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp); b = scalar.Builder(bp, forms, FUNCTION)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-orientation-track-candidate-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    foreach_form = bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance")
    add_form = bp.find_block(capture, r'MemberName="Array_Add"')
    item_form = bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")
    clear_form = bp.find_block(reset, r'MemberName="Array_Clear"')
    call_form = bp.find_block(repository, r'MemberName="ValidateRecordV1"')

    def add(key, form, x, y):
        match = bp.BLOCK_RE.match(form); cls = match.group("class").rsplit(".", 1)[-1]; index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def array_get(name, value, x, y):
        node = b.get(name, "vector" if value in ("quat", "vector") else "real", x, y); variable(scalar, node, name, value, True); return node
    def item(source, source_pin, value, index, index_pin, x, y, key):
        node = add(key, item_form, x, y); kind(node, "Array", value, True); kind(node, "Output", value); bp.connect(source, source_pin, node, "Array"); bp.connect(index, index_pin, node, "Dimension 1"); return node
    def append(target, target_pin, value, source, source_pin, x, y, key):
        node = add(key, add_form, x, y); kind(node, "TargetArray", value, True); kind(node, "NewItem", value); bp.connect(target, target_pin, node, "TargetArray"); bp.connect(source, source_pin, node, "NewItem"); return node

    starts = array_get("OrientationTrackCandidateSegmentStartsV1", "real", 0, 240)
    start_controls = array_get("OrientationTrackCandidateStartControlsV1", "quat", 0, 480)
    end_controls = array_get("OrientationTrackCandidateEndControlsV1", "quat", 0, 720)
    clear_starts = add("clear_starts", clear_form, 256, 1200); kind(clear_starts, "TargetArray", "real", True); bp.connect(starts, "OrientationTrackCandidateSegmentStartsV1", clear_starts, "TargetArray"); bp.connect(b.entry, "then", clear_starts, "execute")
    clear_start_controls = add("clear_start_controls", clear_form, 512, 1200); kind(clear_start_controls, "TargetArray", "quat", True); bp.connect(start_controls, "OrientationTrackCandidateStartControlsV1", clear_start_controls, "TargetArray"); bp.connect(clear_starts, "then", clear_start_controls, "execute")
    clear_end_controls = add("clear_end_controls", clear_form, 768, 1200); kind(clear_end_controls, "TargetArray", "quat", True); bp.connect(end_controls, "OrientationTrackCandidateEndControlsV1", clear_end_controls, "TargetArray"); bp.connect(clear_start_controls, "then", clear_end_controls, "execute")
    reset_total = b.set("OrientationTrackCandidateTotalSecondsV1", "real", 1024, 1200, "0.0"); bp.connect(clear_end_controls, "then", reset_total, "execute")
    stage = b.get("OrientationTrackStageValidV1", "bool", 1024, 960)
    outer = b.add("outer", "branch", 1280, 1200); bp.connect(reset_total, "then", outer, "execute"); bp.connect(stage, "OrientationTrackStageValidV1", outer, "Condition")

    durations = array_get("OrientationTrackInputDurationsV1", "real", 1536, 160)
    loop = add("loop", foreach_form, 1792, 480); kind(loop, "Array", "real", True); kind(loop, "Array Element", "real"); bp.connect(durations, "OrientationTrackInputDurationsV1", loop, "Array"); bp.connect(outer, "then", loop, "Exec")
    inner = b.add("inner", "branch", 2064, 960); bp.connect(loop, "LoopBody", inner, "execute"); bp.connect(stage, "OrientationTrackStageValidV1", inner, "Condition")
    plus_one = b.math("Add_IntInt", 2064, 240); scalar.retarget_function(plus_one, "Add_IntInt")
    for pin in ("A", "B", "ReturnValue"): kind(plus_one, pin, "int")
    scalar.set_default(plus_one, "B", "1"); bp.connect(loop, "Array Index", plus_one, "A")
    aligned = array_get("OrientationTrackCandidateAlignedQuatsV1", "quat", 1536, 720)
    tangents = array_get("OrientationTrackCandidateTangentRatesV1", "vector", 1536, 960)
    q0 = item(aligned, "OrientationTrackCandidateAlignedQuatsV1", "quat", loop, "Array Index", 2320, 80, "q0")
    q1 = item(aligned, "OrientationTrackCandidateAlignedQuatsV1", "quat", plus_one, "ReturnValue", 2320, 240, "q1")
    t0 = item(tangents, "OrientationTrackCandidateTangentRatesV1", "vector", loop, "Array Index", 2320, 400, "t0")
    t1 = item(tangents, "OrientationTrackCandidateTangentRatesV1", "vector", plus_one, "ReturnValue", 2320, 560, "t1")
    staged = []
    for name, value, source, pin in (
        ("OrientationInputStartQuatV1", "quat", q0, "Output"), ("OrientationInputEndQuatV1", "quat", q1, "Output"),
        ("OrientationInputStartTangentRateVectorV1", "vector", t0, "Output"), ("OrientationInputEndTangentRateVectorV1", "vector", t1, "Output"),
        ("OrientationInputDurationV1", "real", loop, "Array Element"),
    ):
        node = b.set(name, "vector" if value in ("quat", "vector") else "real", 2640, 800 + len(staged) * 144); variable(scalar, node, name, value); bp.connect(source, pin, node, name); staged.append(node)
    bp.connect(inner, "then", staged[0], "execute")
    for left, right in zip(staged, staged[1:]): bp.connect(left, "then", right, "execute")
    primitive = add("primitive", call_form, 2960, 1520); primitive.text = re.sub(r'FunctionReference=\([^\n]*\)', 'FunctionReference=(MemberName="BuildOrientationSegmentControlsV1",bSelfContext=True)', primitive.text, 1)
    primitive.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1)); bp.connect(staged[-1], "then", primitive, "execute")
    result_valid = b.get("OrientationResultValidV1", "bool", 3216, 1280)
    guard = b.add("result_guard", "branch", 3472, 1520); bp.connect(primitive, "then", guard, "execute"); bp.connect(result_valid, "OrientationResultValidV1", guard, "Condition")
    total = b.get("OrientationTrackCandidateTotalSecondsV1", "real", 3472, 960)
    add_start = append(starts, "OrientationTrackCandidateSegmentStartsV1", "real", total, "OrientationTrackCandidateTotalSecondsV1", 3728, 1200, "append_start"); bp.connect(guard, "then", add_start, "execute")
    result_start = b.get("OrientationResultStartControlQuatV1", "vector", 3728, 720); variable(scalar, result_start, "OrientationResultStartControlQuatV1", "quat")
    add_start_control = append(start_controls, "OrientationTrackCandidateStartControlsV1", "quat", result_start, "OrientationResultStartControlQuatV1", 3984, 1200, "append_start_control"); bp.connect(add_start, "then", add_start_control, "execute")
    result_end = b.get("OrientationResultEndControlQuatV1", "vector", 3984, 720); variable(scalar, result_end, "OrientationResultEndControlQuatV1", "quat")
    add_end_control = append(end_controls, "OrientationTrackCandidateEndControlsV1", "quat", result_end, "OrientationResultEndControlQuatV1", 4240, 1200, "append_end_control"); bp.connect(add_start_control, "then", add_end_control, "execute")
    sum_total = b.math("Add_DoubleDouble", 4240, 880); scalar.retarget_function(sum_total, "Add_DoubleDouble")
    for pin in ("A", "B", "ReturnValue"): kind(sum_total, pin, "real")
    bp.connect(total, "OrientationTrackCandidateTotalSecondsV1", sum_total, "A"); bp.connect(loop, "Array Element", sum_total, "B")
    commit_total = b.set("OrientationTrackCandidateTotalSecondsV1", "real", 4496, 1200); bp.connect(add_end_control, "then", commit_total, "execute"); bp.connect(sum_total, "ReturnValue", commit_total, "OrientationTrackCandidateTotalSecondsV1")
    reject = b.set("OrientationTrackStageValidV1", "bool", 3728, 1680, "false"); bp.connect(guard, "else", reject, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]; args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
