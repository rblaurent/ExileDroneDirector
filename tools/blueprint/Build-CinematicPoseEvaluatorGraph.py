"""Build atomic absolute-time evaluation of a compiled cinematic pose."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "EvaluateCompiledCinematicPoseV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
RESULT_FIELDS = (
    "CinematicPoseResultSegmentIndexV1",
    "CinematicPoseResultLocalTimeAlphaV1",
    "CinematicPoseResultDistanceAlphaV1",
    "CinematicPoseResultCurveUV1",
    "CinematicPoseResultPositionV1",
    "CinematicPoseResultQuatV1",
    "CinematicPoseResultCompleteV1",
    "CinematicPoseResultValidV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_evaluator_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin, value):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[value]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        return re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)

    node.mutate_pin(pin, mutate)


def variable(scalar, node, name, value):
    template_kind = "real" if value == "int" else ("vector" if value == "quat" else value)
    scalar.retarget_variable(node, name, template_kind)
    kind(node, name, value)
    if "Output_Get" in node.pins:
        kind(node, "Output_Get", value)


def set_default(node, pin, value):
    node.mutate_pin(
        pin,
        lambda line: re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, 1)
        if "DefaultValue=" in line
        else line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    builder = scalar.Builder(bp, forms, FUNCTION)
    reset_graph = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-cinematic-pose-v1.eddgraph")
    call_graph = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    call_form = bp.find_block(call_graph, r'MemberName="ValidateRecordV1"')

    def get(name, value, x, y):
        template_kind = "real" if value == "int" else ("vector" if value == "quat" else value)
        node = builder.get(name, template_kind, x, y)
        variable(scalar, node, name, value)
        return node

    def set_value(name, value, x, y, default=None):
        template_kind = "real" if value == "int" else ("vector" if value == "quat" else value)
        node = builder.set(name, template_kind, x, y, default)
        variable(scalar, node, name, value)
        return node

    def compare(member, left, left_pin, right, right_pin, x, y, value):
        node = builder.add(f"compare_{len(builder.nodes)}", "compare", x, y)
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

    def boolean_and(left, left_pin, right, right_pin, x, y):
        return compare("BooleanAND", left, left_pin, right, right_pin, x, y, "bool")

    def call(member, x, y):
        match = bp.BLOCK_RE.match(call_form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(f"call_{member}", call_form, f"{cls}_{index}", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}",
                line,
                1,
            ),
        )
        builder.nodes.append(node)
        return node

    resets = []
    publications = []
    for index, name in enumerate(RESULT_FIELDS):
        template = bp.find_block(reset_graph, rf'MemberName="{name}"')
        reset = bp.Node.clone(f"reset_{index}", template, f"K2Node_VariableSet_{index}", 256 + index * 288, 2048)
        publication = bp.Node.clone(f"publication_{index}", template, f"K2Node_VariableSet_{8 + index}", 6144 + index * 288, 2048)
        builder.nodes.extend((reset, publication))
        resets.append(reset)
        publications.append(publication)
    set_default(publications[-1], "CinematicPoseResultValidV1", "true")
    builder.serial["K2Node_VariableSet"] = 16
    bp.connect(builder.entry, "then", resets[0], "execute")
    for left, right in zip(resets, resets[1:]):
        bp.connect(left, "then", right, "execute")

    elapsed = get("CinematicPoseInputElapsedSecondsV1", "real", 0, 0)
    compile_valid = get("CinematicPoseCompileValidV1", "bool", 0, 160)
    pose_total = get("CinematicPoseCompiledTotalSecondsV1", "real", 0, 320)
    position_compile_valid = get("PositionRouteCompileValidV1", "bool", 0, 480)
    orientation_compile_valid = get("OrientationTrackCompileValidV1", "bool", 0, 640)
    position_total = get("PositionRouteCompiledTotalSecondsV1", "real", 0, 800)
    orientation_total = get("OrientationTrackCompiledTotalSecondsV1", "real", 0, 960)
    guards = (
        builder.finite(elapsed, "CinematicPoseInputElapsedSecondsV1", 320, 0),
        builder.finite(pose_total, "CinematicPoseCompiledTotalSecondsV1", 320, 320),
        compare("Greater_DoubleDouble", pose_total, "CinematicPoseCompiledTotalSecondsV1", None, "0.0", 544, 320, "real"),
        position_compile_valid,
        orientation_compile_valid,
        compare("EqualEqual_DoubleDouble", pose_total, "CinematicPoseCompiledTotalSecondsV1", position_total, "PositionRouteCompiledTotalSecondsV1", 320, 800, "real"),
        compare("EqualEqual_DoubleDouble", pose_total, "CinematicPoseCompiledTotalSecondsV1", orientation_total, "OrientationTrackCompiledTotalSecondsV1", 320, 960, "real"),
    )
    combined = boolean_and(compile_valid, "CinematicPoseCompileValidV1", guards[0], "ReturnValue", 800, 0)
    for index, guard in enumerate(guards[1:]):
        pin = guard.pins.get("ReturnValue") and "ReturnValue"
        if guard is position_compile_valid:
            pin = "PositionRouteCompileValidV1"
        elif guard is orientation_compile_valid:
            pin = "OrientationTrackCompileValidV1"
        combined = boolean_and(combined, "ReturnValue", guard, pin, 1024 + index * 224, 640)
    outer = builder.add("outer", "branch", 2560, 2048)
    bp.connect(resets[-1], "then", outer, "execute")
    bp.connect(combined, "ReturnValue", outer, "Condition")

    stage_position_elapsed = set_value("PositionRouteInputElapsedSecondsV1", "real", 2816, 2048)
    stage_orientation_elapsed = set_value("OrientationTrackInputElapsedSecondsV1", "real", 3072, 2048)
    bp.connect(outer, "then", stage_position_elapsed, "execute")
    bp.connect(elapsed, "CinematicPoseInputElapsedSecondsV1", stage_position_elapsed, "PositionRouteInputElapsedSecondsV1")
    bp.connect(stage_position_elapsed, "then", stage_orientation_elapsed, "execute")
    bp.connect(elapsed, "CinematicPoseInputElapsedSecondsV1", stage_orientation_elapsed, "OrientationTrackInputElapsedSecondsV1")
    position_call = call("EvaluateCompiledPositionRouteV1", 3328, 2048)
    orientation_call = call("EvaluateCompiledOrientationTrackV1", 3584, 2048)
    bp.connect(stage_orientation_elapsed, "then", position_call, "execute")
    bp.connect(position_call, "then", orientation_call, "execute")

    position_valid = get("PositionRouteResultValidV1", "bool", 3328, 1600)
    orientation_valid = get("OrientationTrackResultValidV1", "bool", 3584, 1600)
    position_segment = get("PositionRouteResultSegmentIndexV1", "int", 3840, 1440)
    orientation_segment = get("OrientationTrackResultSegmentIndexV1", "int", 3840, 1600)
    position_alpha = get("PositionRouteResultLocalTimeAlphaV1", "real", 3840, 1760)
    orientation_alpha = get("OrientationTrackResultAlphaV1", "real", 3840, 1920)
    position_complete = get("PositionRouteResultCompleteV1", "bool", 3840, 2080)
    orientation_complete = get("OrientationTrackResultCompleteV1", "bool", 3840, 2240)
    segment_equal = compare("EqualEqual_IntInt", position_segment, "PositionRouteResultSegmentIndexV1", orientation_segment, "OrientationTrackResultSegmentIndexV1", 4096, 1520, "int")
    alpha_equal = compare("EqualEqual_DoubleDouble", position_alpha, "PositionRouteResultLocalTimeAlphaV1", orientation_alpha, "OrientationTrackResultAlphaV1", 4096, 1840, "real")
    complete_equal = compare("EqualEqual_BoolBool", position_complete, "PositionRouteResultCompleteV1", orientation_complete, "OrientationTrackResultCompleteV1", 4096, 2160, "bool")
    evaluation_valid = boolean_and(position_valid, "PositionRouteResultValidV1", orientation_valid, "OrientationTrackResultValidV1", 4352, 1600)
    for index, guard in enumerate((segment_equal, alpha_equal, complete_equal)):
        evaluation_valid = boolean_and(evaluation_valid, "ReturnValue", guard, "ReturnValue", 4576 + index * 224, 1840)
    result_branch = builder.add("result_branch", "branch", 5344, 2048)
    bp.connect(orientation_call, "then", result_branch, "execute")
    bp.connect(evaluation_valid, "ReturnValue", result_branch, "Condition")

    sources = (
        (position_segment, "PositionRouteResultSegmentIndexV1"),
        (position_alpha, "PositionRouteResultLocalTimeAlphaV1"),
        (get("PositionRouteResultDistanceAlphaV1", "real", 5376, 1440), "PositionRouteResultDistanceAlphaV1"),
        (get("PositionRouteResultCurveUV1", "real", 5376, 1600), "PositionRouteResultCurveUV1"),
        (get("PositionRouteResultPositionV1", "vector", 5376, 1760), "PositionRouteResultPositionV1"),
        (get("OrientationTrackResultQuatV1", "quat", 5376, 1920), "OrientationTrackResultQuatV1"),
        (position_complete, "PositionRouteResultCompleteV1"),
    )
    bp.connect(result_branch, "then", publications[0], "execute")
    for index, ((source, source_pin), publication) in enumerate(zip(sources, publications)):
        bp.connect(source, source_pin, publication, RESULT_FIELDS[index])
    for left, right in zip(publications, publications[1:]):
        bp.connect(left, "then", right, "execute")

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
