"""Build atomic publication of one cross-validated cinematic pose timeline."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCompiledCinematicPoseV1"
RESET_FIELDS = (
    "CinematicPoseCompiledTotalSecondsV1",
    "CinematicPoseCompileValidV1",
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
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_commit_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
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
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


def variable(scalar, node, name, value, array=False):
    template_kind = "real" if value == "int" else ("vector" if value == "quat" else value)
    scalar.retarget_variable(node, name, template_kind)
    kind(node, name, value, array)
    if "Output_Get" in node.pins:
        kind(node, "Output_Get", value)


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
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset_graph = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-cinematic-pose-v1.eddgraph")
    raw = {
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
    }

    def add(key, form, x, y):
        text = raw[form]
        match = bp.BLOCK_RE.match(text)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, text, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def get(name, value, x, y, array=False):
        template_kind = "real" if value == "int" else value
        node = builder.get(name, template_kind, x, y)
        variable(scalar, node, name, value, array)
        return node

    def set_value(name, value, x, y, default=None):
        template_kind = "real" if value == "int" else value
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

    def boolean_and(left, right, x, y):
        return compare("BooleanAND", left, "ReturnValue", right, "ReturnValue", x, y, "bool")

    def length(source, source_pin, x, y, key):
        node = add(key, "length", x, y)
        kind(node, "TargetArray", "real", True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin, index, index_pin, x, y, key):
        node = add(key, "item", x, y)
        kind(node, "Array", "real", True)
        kind(node, "Output", "real")
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    resets = []
    for index, name in enumerate(RESET_FIELDS):
        template = bp.find_block(reset_graph, rf'MemberName="{name}"')
        node = bp.Node.clone(f"reset_{index}", template, f"K2Node_VariableSet_{index}", 256 + index * 288, 2048)
        builder.nodes.append(node)
        resets.append(node)
    builder.serial["K2Node_VariableSet"] = len(RESET_FIELDS)
    bp.connect(builder.entry, "then", resets[0], "execute")
    for left, right in zip(resets, resets[1:]):
        bp.connect(left, "then", right, "execute")

    stage = get("CinematicPoseStageValidV1", "bool", 0, 0)
    position_valid = get("PositionRouteCompileValidV1", "bool", 0, 160)
    orientation_valid = get("OrientationTrackCompileValidV1", "bool", 0, 320)
    position_total = get("PositionRouteCompiledTotalSecondsV1", "real", 0, 480)
    orientation_total = get("OrientationTrackCompiledTotalSecondsV1", "real", 0, 640)
    position_durations = get("PositionRouteCompiledDurationsV1", "real", 0, 800, True)
    orientation_durations = get("OrientationTrackCompiledDurationsV1", "real", 0, 960, True)
    position_starts = get("PositionRouteCompiledSegmentStartsV1", "real", 0, 1120, True)
    orientation_starts = get("OrientationTrackCompiledSegmentStartsV1", "real", 0, 1280, True)
    position_duration_count = length(position_durations, "PositionRouteCompiledDurationsV1", 320, 800, "position_duration_count")
    orientation_duration_count = length(orientation_durations, "OrientationTrackCompiledDurationsV1", 320, 960, "orientation_duration_count")
    position_start_count = length(position_starts, "PositionRouteCompiledSegmentStartsV1", 320, 1120, "position_start_count")
    orientation_start_count = length(orientation_starts, "OrientationTrackCompiledSegmentStartsV1", 320, 1280, "orientation_start_count")
    guards = (
        builder.finite(position_total, "PositionRouteCompiledTotalSecondsV1", 640, 480),
        compare("Greater_DoubleDouble", position_total, "PositionRouteCompiledTotalSecondsV1", None, "0.0", 864, 480, "real"),
        compare("EqualEqual_DoubleDouble", position_total, "PositionRouteCompiledTotalSecondsV1", orientation_total, "OrientationTrackCompiledTotalSecondsV1", 1088, 560, "real"),
        compare("Greater_IntInt", position_duration_count, "ReturnValue", None, "0", 640, 800, "int"),
        compare("EqualEqual_IntInt", position_duration_count, "ReturnValue", orientation_duration_count, "ReturnValue", 864, 880, "int"),
        compare("EqualEqual_IntInt", position_duration_count, "ReturnValue", position_start_count, "ReturnValue", 1088, 1040, "int"),
        compare("EqualEqual_IntInt", position_duration_count, "ReturnValue", orientation_start_count, "ReturnValue", 1312, 1200, "int"),
    )
    combined = compare(
        "BooleanAND",
        stage,
        "CinematicPoseStageValidV1",
        position_valid,
        "PositionRouteCompileValidV1",
        1536,
        1440,
        "bool",
    )
    combined = compare(
        "BooleanAND",
        combined,
        "ReturnValue",
        orientation_valid,
        "OrientationTrackCompileValidV1",
        1744,
        1440,
        "bool",
    )
    for index, guard in enumerate(guards):
        combined = boolean_and(combined, guard, 1952 + index * 208, 1440)
    preflight = builder.add("preflight", "branch", 3456, 2048)
    bp.connect(resets[-1], "then", preflight, "execute")
    bp.connect(combined, "ReturnValue", preflight, "Condition")
    preflight_reject = set_value("CinematicPoseStageValidV1", "bool", 3712, 2240, "false")
    bp.connect(preflight, "else", preflight_reject, "execute")
    loop = add("timeline_loop", "foreach", 3712, 1536)
    kind(loop, "Array", "real", True)
    kind(loop, "Array Element", "real")
    bp.connect(position_durations, "PositionRouteCompiledDurationsV1", loop, "Array")
    bp.connect(preflight, "then", loop, "Exec")
    other_duration = item(orientation_durations, "OrientationTrackCompiledDurationsV1", loop, "Array Index", 3968, 1440, "other_duration")
    position_start = item(position_starts, "PositionRouteCompiledSegmentStartsV1", loop, "Array Index", 3968, 1600, "position_start")
    orientation_start = item(orientation_starts, "OrientationTrackCompiledSegmentStartsV1", loop, "Array Index", 3968, 1760, "orientation_start")
    duration_equal = compare("EqualEqual_DoubleDouble", loop, "Array Element", other_duration, "Output", 4224, 1440, "real")
    start_equal = compare("EqualEqual_DoubleDouble", position_start, "Output", orientation_start, "Output", 4224, 1680, "real")
    item_valid = boolean_and(duration_equal, start_equal, 4480, 1536)
    item_branch = builder.add("item_branch", "branch", 4736, 1536)
    bp.connect(loop, "LoopBody", item_branch, "execute")
    bp.connect(item_valid, "ReturnValue", item_branch, "Condition")
    item_reject = set_value("CinematicPoseStageValidV1", "bool", 4992, 1760, "false")
    bp.connect(item_branch, "else", item_reject, "execute")
    final_stage = get("CinematicPoseStageValidV1", "bool", 4992, 1376)
    final_branch = builder.add("final_branch", "branch", 5248, 1536)
    bp.connect(loop, "Completed", final_branch, "execute")
    bp.connect(final_stage, "CinematicPoseStageValidV1", final_branch, "Condition")
    publish_total = set_value("CinematicPoseCompiledTotalSecondsV1", "real", 5504, 1536)
    publish_valid = set_value("CinematicPoseCompileValidV1", "bool", 5760, 1536, "true")
    bp.connect(final_branch, "then", publish_total, "execute")
    bp.connect(position_total, "PositionRouteCompiledTotalSecondsV1", publish_total, "CinematicPoseCompiledTotalSecondsV1")
    bp.connect(publish_total, "then", publish_valid, "execute")

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
