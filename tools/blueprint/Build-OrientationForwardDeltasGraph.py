"""Build deterministic adjacent-key logarithmic orientation deltas."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ComputeOrientationForwardDeltasV1"
TARGET_CLASS = (
    '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/'
    "Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'\""
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_orientation_delta_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def retarget_variable(scalar, node, name: str, kind: str, array: bool = False) -> None:
    scalar.retarget_variable(node, name, "vector" if kind in ("quat", "vector") else kind)
    pin_kind(node, name, kind, array)
    if "Output_Get" in node.pins:
        pin_kind(node, "Output_Get", kind)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    builder = scalar.Builder(bp, forms, FUNCTION)

    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-orientation-track-candidate-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")

    foreach_form = bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance")
    add_form = bp.find_block(capture, r'MemberName="Array_Add"')
    getitem_form = bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")
    clear_form = bp.find_block(reset, r'MemberName="Array_Clear"')
    self_call_form = bp.find_block(repository, r'MemberName="ValidateRecordV1"')

    def add(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    candidate = builder.get("OrientationTrackCandidateForwardDeltasV1", "vector", 0, 720)
    retarget_variable(scalar, candidate, "OrientationTrackCandidateForwardDeltasV1", "vector", True)
    clear = add("clear", clear_form, 256, 1280)
    pin_kind(clear, "TargetArray", "vector", True)
    bp.connect(candidate, "OrientationTrackCandidateForwardDeltasV1", clear, "TargetArray")
    bp.connect(builder.entry, "then", clear, "execute")

    stage = builder.get("OrientationTrackStageValidV1", "bool", 256, 960)
    outer_guard = builder.add("outer_guard", "branch", 512, 1280)
    bp.connect(clear, "then", outer_guard, "execute")
    bp.connect(stage, "OrientationTrackStageValidV1", outer_guard, "Condition")

    durations = builder.get("OrientationTrackInputDurationsV1", "real", 768, 160)
    pin_kind(durations, "OrientationTrackInputDurationsV1", "real", True)
    loop = add("loop", foreach_form, 1024, 448)
    pin_kind(loop, "Array", "real", True)
    pin_kind(loop, "Array Element", "real")
    bp.connect(durations, "OrientationTrackInputDurationsV1", loop, "Array")
    bp.connect(outer_guard, "then", loop, "Exec")

    inner_guard = builder.add("inner_guard", "branch", 1296, 832)
    bp.connect(loop, "LoopBody", inner_guard, "execute")
    bp.connect(stage, "OrientationTrackStageValidV1", inner_guard, "Condition")

    aligned = builder.get("OrientationTrackCandidateAlignedQuatsV1", "vector", 1296, 160)
    retarget_variable(scalar, aligned, "OrientationTrackCandidateAlignedQuatsV1", "quat", True)
    start_item = add("start_item", getitem_form, 1552, 160)
    pin_kind(start_item, "Array", "quat", True)
    pin_kind(start_item, "Output", "quat")
    bp.connect(aligned, "OrientationTrackCandidateAlignedQuatsV1", start_item, "Array")
    bp.connect(loop, "Array Index", start_item, "Dimension 1")

    plus_one = builder.math("Add_IntInt", 1552, 480)
    scalar.retarget_function(plus_one, "Add_IntInt")
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(plus_one, pin, "int")
    scalar.set_default(plus_one, "B", "1")
    bp.connect(loop, "Array Index", plus_one, "A")

    end_item = add("end_item", getitem_form, 1808, 320)
    pin_kind(end_item, "Array", "quat", True)
    pin_kind(end_item, "Output", "quat")
    bp.connect(aligned, "OrientationTrackCandidateAlignedQuatsV1", end_item, "Array")
    bp.connect(plus_one, "ReturnValue", end_item, "Dimension 1")

    set_start = builder.set("OrientationInputStartQuatV1", "vector", 2064, 720)
    retarget_variable(scalar, set_start, "OrientationInputStartQuatV1", "quat")
    bp.connect(inner_guard, "then", set_start, "execute")
    bp.connect(start_item, "Output", set_start, "OrientationInputStartQuatV1")
    set_end = builder.set("OrientationInputEndQuatV1", "vector", 2320, 720)
    retarget_variable(scalar, set_end, "OrientationInputEndQuatV1", "quat")
    bp.connect(set_start, "then", set_end, "execute")
    bp.connect(end_item, "Output", set_end, "OrientationInputEndQuatV1")

    primitive = add("primitive", self_call_form, 2576, 720)
    primitive.text = re.sub(
        r'FunctionReference=\([^\n]*\)',
        'FunctionReference=(MemberName="ComputeOrientationLogDeltaV1",bSelfContext=True)',
        primitive.text,
        count=1,
    )
    primitive.mutate_pin(
        "self",
        lambda line: re.sub(
            r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
            f"PinType.PinSubCategoryObject={TARGET_CLASS}",
            line,
            count=1,
        ),
    )
    bp.connect(set_end, "then", primitive, "execute")

    primitive_valid = builder.get("OrientationResultValidV1", "bool", 2832, 480)
    result_guard = builder.add("result_guard", "branch", 3088, 720)
    bp.connect(primitive, "then", result_guard, "execute")
    bp.connect(primitive_valid, "OrientationResultValidV1", result_guard, "Condition")

    result = builder.get("OrientationResultDeltaVectorV1", "vector", 3088, 400)
    append = add("append", add_form, 3344, 560)
    pin_kind(append, "TargetArray", "vector", True)
    pin_kind(append, "NewItem", "vector")
    bp.connect(candidate, "OrientationTrackCandidateForwardDeltasV1", append, "TargetArray")
    bp.connect(result, "OrientationResultDeltaVectorV1", append, "NewItem")
    bp.connect(result_guard, "then", append, "execute")

    reject = builder.set("OrientationTrackStageValidV1", "bool", 3344, 880, "false")
    bp.connect(result_guard, "else", reject, "execute")

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
