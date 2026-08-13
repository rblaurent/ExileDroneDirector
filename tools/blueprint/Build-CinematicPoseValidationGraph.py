"""Build fail-closed authored-timeline validation for cinematic pose composition."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateCinematicPoseInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_validation_base", path)
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
        template_kind = "real" if value == "int" else ("vector" if value == "quat" else value)
        node = builder.get(name, template_kind, x, y)
        variable(scalar, node, name, value, array)
        return node

    def compare(member, left, left_pin, right, right_pin, x, y, value="int"):
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

    def length(source, source_pin, value, x, y, key):
        node = add(key, "length", x, y)
        kind(node, "TargetArray", value, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    reset = builder.set("CinematicPoseStageValidV1", "bool", 256, 1536, "false")
    bp.connect(builder.entry, "then", reset, "execute")
    positions = get("PositionRouteInputWaypointPositionsV1", "vector", 0, 0, True)
    quats = get("OrientationTrackInputWaypointQuatsV1", "quat", 0, 192, True)
    position_durations = get("PositionRouteInputDurationsV1", "real", 0, 384, True)
    orientation_durations = get("OrientationTrackInputDurationsV1", "real", 0, 576, True)
    position_count = length(positions, "PositionRouteInputWaypointPositionsV1", "vector", 320, 0, "position_count")
    quat_count = length(quats, "OrientationTrackInputWaypointQuatsV1", "quat", 320, 192, "quat_count")
    position_duration_count = length(position_durations, "PositionRouteInputDurationsV1", "real", 320, 384, "position_duration_count")
    orientation_duration_count = length(orientation_durations, "OrientationTrackInputDurationsV1", "real", 320, 576, "orientation_duration_count")
    minimum = compare("GreaterEqual_IntInt", position_count, "ReturnValue", None, "2", 640, 0)
    maximum = compare("LessEqual_IntInt", position_count, "ReturnValue", None, "512", 640, 128)
    waypoint_match = compare("EqualEqual_IntInt", position_count, "ReturnValue", quat_count, "ReturnValue", 640, 256)
    minus_one = builder.math("Subtract_DoubleDouble", 640, 384)
    scalar.retarget_function(minus_one, "Subtract_IntInt")
    for pin in ("A", "B", "ReturnValue"):
        kind(minus_one, pin, "int")
    bp.connect(position_count, "ReturnValue", minus_one, "A")
    scalar.set_default(minus_one, "B", "1")
    position_shape = compare("EqualEqual_IntInt", position_duration_count, "ReturnValue", minus_one, "ReturnValue", 896, 384)
    duration_shape = compare("EqualEqual_IntInt", position_duration_count, "ReturnValue", orientation_duration_count, "ReturnValue", 896, 512)
    combined = minimum
    for index, guard in enumerate((maximum, waypoint_match, position_shape, duration_shape)):
        combined = boolean_and(combined, guard, 1152 + index * 224, 256)
    shape_branch = builder.add("shape_branch", "branch", 2048, 1536)
    bp.connect(reset, "then", shape_branch, "execute")
    bp.connect(combined, "ReturnValue", shape_branch, "Condition")
    accept = builder.set("CinematicPoseStageValidV1", "bool", 2304, 1536, "true")
    bp.connect(shape_branch, "then", accept, "execute")
    loop = add("duration_loop", "foreach", 2560, 896)
    kind(loop, "Array", "real", True)
    kind(loop, "Array Element", "real")
    bp.connect(position_durations, "PositionRouteInputDurationsV1", loop, "Array")
    bp.connect(accept, "then", loop, "Exec")
    other = add("orientation_duration", "item", 2816, 1088)
    kind(other, "Array", "real", True)
    kind(other, "Output", "real")
    bp.connect(orientation_durations, "OrientationTrackInputDurationsV1", other, "Array")
    bp.connect(loop, "Array Index", other, "Dimension 1")
    equal = compare("EqualEqual_DoubleDouble", loop, "Array Element", other, "Output", 3072, 960, "real")
    item_branch = builder.add("item_branch", "branch", 3328, 896)
    bp.connect(loop, "LoopBody", item_branch, "execute")
    bp.connect(equal, "ReturnValue", item_branch, "Condition")
    reject = builder.set("CinematicPoseStageValidV1", "bool", 3584, 1088, "false")
    bp.connect(item_branch, "else", reject, "execute")

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
