"""Stage one accepted playback snapshot into native pose and engine inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageCameraPlaybackNativeApplicationInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_native_stage_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(
            r"PinType.ContainerType=(?:None|Array)",
            f"PinType.ContainerType={'Array' if array else 'None'}",
            line,
            1,
        )

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
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    forms.update(
        clear=bp.find_block(sync, r'MemberName="Array_Clear"'),
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        add=bp.find_block(capture, r'MemberName="Array_Add"'),
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
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind))
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

    def compare(member: str, left, left_pin: str, x: int, y: int, *, right=None, right_pin=None, default=None, kind="bool"):
        node = builder.add(f"cmp_{member}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        if member in ("EqualEqual_StrStr", "NotEqual_StrStr"):
            node.text = node.text.replace("KismetMathLibrary", "KismetStringLibrary")
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def combine(conditions, x: int, y: int):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = compare(
                "BooleanAND",
                current,
                "ReturnValue",
                x + index * 208,
                y,
                right=condition,
                right_pin="ReturnValue",
            )
        return current

    def length(source, source_pin: str, x: int, y: int):
        node = add_form(f"length_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", "real", True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin: str, index: int, x: int, y: int):
        node = add_form(f"item_{index}_{len(builder.nodes)}", "item", x, y)
        pin_kind(node, "Array", "real", True)
        pin_kind(node, "Output", "real")
        scalar.set_default(node, "Dimension 1", str(index))
        bp.connect(source, source_pin, node, "Array")
        return node

    def add(target, target_pin: str, value, value_pin: str, x: int, y: int):
        node = add_form(f"add_{len(builder.nodes)}", "add", x, y)
        pin_kind(node, "TargetArray", "real", True)
        pin_kind(node, "NewItem", "real")
        pin_kind(node, "ReturnValue", "int")
        bp.connect(target, target_pin, node, "TargetArray")
        bp.connect(value, value_pin, node, "NewItem")
        return node

    invalidate_native = set_value("CameraPlaybackNativeInputValidV1", "bool", 256, 3200, "false")
    invalidate_stage = set_value("CameraPlaybackNativeStageValidV1", "bool", 672, 3200, "false")
    invalidate = set_value("CameraApplyInputValidV1", "bool", 1088, 3200, "false")
    target = get("CameraApplyInputTargetValuesV1", "real", 256, 2880, True)
    clear = add_form("clear_input", "clear", 1504, 3200)
    pin_kind(clear, "TargetArray", "real", True)
    bp.connect(target, "CameraApplyInputTargetValuesV1", clear, "TargetArray")
    clear_id = set_value("CameraApplyInputFilmbackPresetIdV1", "string", 1728, 3200, "")
    bp.connect(builder.entry, "then", invalidate_native, "execute")
    bp.connect(invalidate_native, "then", invalidate_stage, "execute")
    bp.connect(invalidate_stage, "then", invalidate, "execute")
    bp.connect(invalidate, "then", clear, "execute")
    bp.connect(clear, "then", clear_id, "execute")

    result_valid = get("CameraPlaybackResultValidV1", "bool", 0, 0)
    result_values = get("CameraPlaybackResultChannelValuesV1", "real", 0, 160, True)
    count = length(result_values, "CameraPlaybackResultChannelValuesV1", 256, 160)
    count_ok = compare("EqualEqual_IntInt", count, "ReturnValue", 480, 160, default="13", kind="int")
    preset = get("CameraPlaybackResultFilmbackPresetIdV1", "string", 0, 320)
    preset_ok = compare("NotEqual_StrStr", preset, "CameraPlaybackResultFilmbackPresetIdV1", 256, 320, default="", kind="string")
    width = get("CameraPlaybackResultFilmbackSensorWidthMmV1", "real", 0, 480)
    width_finite = builder.finite(width, "CameraPlaybackResultFilmbackSensorWidthMmV1", 256, 480)
    width_positive = compare("Greater_DoubleDouble", width, "CameraPlaybackResultFilmbackSensorWidthMmV1", 480, 480, default="0.0", kind="real")
    height = get("CameraPlaybackResultFilmbackSensorHeightMmV1", "real", 0, 640)
    height_finite = builder.finite(height, "CameraPlaybackResultFilmbackSensorHeightMmV1", 256, 640)
    height_positive = compare("Greater_DoubleDouble", height, "CameraPlaybackResultFilmbackSensorHeightMmV1", 480, 640, default="0.0", kind="real")
    shape_ready = combine(
        [count_ok, preset_ok, width_finite, width_positive, height_finite, height_positive],
        704,
        400,
    )
    ready = compare(
        "BooleanAND",
        result_valid,
        "CameraPlaybackResultValidV1",
        1792,
        400,
        right=shape_ready,
        right_pin="ReturnValue",
    )
    guard = builder.add("frame_guard", "branch", 2000, 3200)
    bp.connect(clear_id, "then", guard, "execute")
    bp.connect(ready, "ReturnValue", guard, "Condition")

    pose_sources = (
        ("CameraPlaybackResultPositionV1", "CameraPlaybackNativeInputPositionV1", "vector"),
        ("CameraPlaybackResultBodyWorldQuatV1", "CameraPlaybackNativeInputBodyWorldQuatV1", "quat"),
        ("CameraPlaybackResultGimbalWorldQuatV1", "CameraPlaybackNativeInputGimbalWorldQuatV1", "quat"),
        ("CameraPlaybackResultGimbalRelativeQuatV1", "CameraPlaybackNativeInputGimbalRelativeQuatV1", "quat"),
    )
    pose_getters = [get(source, kind, 2224 + index * 416, 960) for index, (source, _target, kind) in enumerate(pose_sources)]
    pose_setters = []
    for index, ((source, target_name, kind), source_node) in enumerate(zip(pose_sources, pose_getters)):
        setter = set_value(target_name, kind, 2224 + index * 416, 3200)
        bp.connect(source_node, source, setter, target_name)
        pose_setters.append(setter)
    bp.connect(guard, "then", pose_setters[0], "execute")
    for left, right in zip(pose_setters, pose_setters[1:]):
        bp.connect(left, "then", right, "execute")

    store_id = set_value("CameraApplyInputFilmbackPresetIdV1", "string", 3888, 3200)
    bp.connect(preset, "CameraPlaybackResultFilmbackPresetIdV1", store_id, "CameraApplyInputFilmbackPresetIdV1")
    bp.connect(pose_setters[-1], "then", store_id, "execute")
    add_width = add(target, "CameraApplyInputTargetValuesV1", width, "CameraPlaybackResultFilmbackSensorWidthMmV1", 4112, 3200)
    add_height = add(target, "CameraApplyInputTargetValuesV1", height, "CameraPlaybackResultFilmbackSensorHeightMmV1", 4336, 3200)
    bp.connect(store_id, "then", add_width, "execute")
    bp.connect(add_width, "then", add_height, "execute")

    value_items = [item(result_values, "CameraPlaybackResultChannelValuesV1", index, 2224 + index * 224, 1280) for index in range(13)]
    value_adds = [
        add(target, "CameraApplyInputTargetValuesV1", value_item, "Output", 4560 + index * 224, 3200)
        for index, value_item in enumerate(value_items)
    ]
    bp.connect(add_height, "then", value_adds[0], "execute")
    for left, right in zip(value_adds, value_adds[1:]):
        bp.connect(left, "then", right, "execute")
    publish_engine = set_value("CameraApplyInputValidV1", "bool", 7472, 3200, "true")
    publish_native = set_value("CameraPlaybackNativeInputValidV1", "bool", 7888, 3200, "true")
    publish_stage = set_value("CameraPlaybackNativeStageValidV1", "bool", 8304, 3200, "true")
    bp.connect(value_adds[-1], "then", publish_engine, "execute")
    bp.connect(publish_engine, "then", publish_native, "execute")
    bp.connect(publish_native, "then", publish_stage, "execute")

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
