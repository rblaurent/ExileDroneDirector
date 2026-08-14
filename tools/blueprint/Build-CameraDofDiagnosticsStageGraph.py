"""Build complete evaluated-frame staging for camera DOF diagnostics."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageEvaluatedCameraDofFrameV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_dof_stage_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory = {
        "bool": ("bool", ""),
        "int": ("int", ""),
        "real": ("real", "double"),
        "string": ("string", ""),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", f"PinType.ContainerType={'Array' if array else 'None'}", line, 1)

    node.mutate_pin(pin_name, mutate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    forms.update(
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form])
        node_class = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(node_class, 0)
        builder.serial[node_class] = index + 1
        node = bp.Node.clone(key, forms[form], f"{node_class}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def variable(node, name: str, kind: str, array: bool = False):
        scalar.retarget_variable(node, name, kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_value(name: str, kind: str, x: int, y: int, default=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, default: str, kind: str):
        node = builder.add(f"cmp_{member}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        scalar.set_default(node, "B", default)
        return node

    def combine(conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            node = builder.add(f"and_{index}_{len(builder.nodes)}", "compare", x + index * 208, y)
            scalar.retarget_function(node, "BooleanAND")
            for pin in ("A", "B", "ReturnValue"):
                pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A")
            bp.connect(condition, condition_pin, node, "B")
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    def item(source, index: int, x: int, y: int):
        node = add_form(f"item_{index}", "item", x, y)
        pin_kind(node, "Array", "real", True)
        pin_kind(node, "Output", "real")
        scalar.set_default(node, "Dimension 1", str(index))
        bp.connect(source, "CameraChannelResultValuesV1", node, "Array")
        return node

    clear_specs = (
        ("CameraDofStageValidV1", "bool", "false"),
        ("CameraDofStageFilmbackWidthMmV1", "real", "0.0"),
        ("CameraDofStageFilmbackHeightMmV1", "real", "0.0"),
        ("CameraDofStageFocalLengthMmV1", "real", "0.0"),
        ("CameraDofStageApertureFstopV1", "real", "0.0"),
        ("CameraDofStageFocusDistanceCmV1", "real", "0.0"),
        ("CameraDofFailureCodeV1", "string", ""),
    )
    clear_nodes = [set_value(name, kind, 256 + index * 320, 3600, value) for index, (name, kind, value) in enumerate(clear_specs)]
    bp.connect(builder.entry, "then", clear_nodes[0], "execute")
    for left, right in zip(clear_nodes, clear_nodes[1:]):
        bp.connect(left, "then", right, "execute")

    result_valid = get("CameraChannelResultValidV1", "bool", 0, 0)
    result_values = get("CameraChannelResultValuesV1", "real", 0, 240, True)
    length = add_form("result_length", "length", 256, 240)
    pin_kind(length, "TargetArray", "real", True)
    pin_kind(length, "ReturnValue", "int")
    bp.connect(result_values, "CameraChannelResultValuesV1", length, "TargetArray")
    count_ok = compare("EqualEqual_IntInt", length, "ReturnValue", 480, 240, default="13", kind="int")
    width = get("CameraChannelResultFilmbackSensorWidthMmV1", "real", 0, 480)
    width_finite = builder.finite(width, "CameraChannelResultFilmbackSensorWidthMmV1", 256, 480)
    width_positive = compare("Greater_DoubleDouble", width, "CameraChannelResultFilmbackSensorWidthMmV1", 480, 480, default="0.0", kind="real")
    height = get("CameraChannelResultFilmbackSensorHeightMmV1", "real", 0, 720)
    height_finite = builder.finite(height, "CameraChannelResultFilmbackSensorHeightMmV1", 256, 720)
    height_positive = compare("Greater_DoubleDouble", height, "CameraChannelResultFilmbackSensorHeightMmV1", 480, 720, default="0.0", kind="real")
    items = [item(result_values, index, 0 + (index % 4) * 576, 1120 + (index // 4) * 400) for index in range(13)]
    finite_items = [builder.finite(node, "Output", 256 + (index % 4) * 576, 1120 + (index // 4) * 400) for index, node in enumerate(items)]
    ready, ready_pin = combine(
        [(result_valid, "CameraChannelResultValidV1"), (count_ok, "ReturnValue"), (width_finite, "ReturnValue"), (width_positive, "ReturnValue"), (height_finite, "ReturnValue"), (height_positive, "ReturnValue"), *[(node, "ReturnValue") for node in finite_items]],
        2560,
        1600,
    )
    guard = builder.add("stage_guard", "branch", 2560, 3600)
    bp.connect(clear_nodes[-1], "then", guard, "execute")
    bp.connect(ready, ready_pin, guard, "Condition")

    success_specs = (
        ("CameraDofStageFilmbackWidthMmV1", width, "CameraChannelResultFilmbackSensorWidthMmV1"),
        ("CameraDofStageFilmbackHeightMmV1", height, "CameraChannelResultFilmbackSensorHeightMmV1"),
        ("CameraDofStageFocalLengthMmV1", items[0], "Output"),
        ("CameraDofStageApertureFstopV1", items[1], "Output"),
        ("CameraDofStageFocusDistanceCmV1", items[2], "Output"),
    )
    success_nodes = []
    for index, (name, source, source_pin) in enumerate(success_specs):
        setter = set_value(name, "real", 2816 + index * 384, 3600)
        bp.connect(source, source_pin, setter, name)
        success_nodes.append(setter)
    publish = set_value("CameraDofStageValidV1", "bool", 4736, 3600, "true")
    bp.connect(guard, "then", success_nodes[0], "execute")
    for left, right in zip(success_nodes, success_nodes[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(success_nodes[-1], "then", publish, "execute")
    failure = set_value("CameraDofFailureCodeV1", "string", 2816, 3920, "camera_dof_stage_failed")
    bp.connect(guard, "else", failure, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text)
            for node in builder.nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
