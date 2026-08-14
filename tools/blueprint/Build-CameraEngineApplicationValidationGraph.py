"""Build engine-neutral validation for staged camera application input."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateCameraEngineApplicationInputsV1"
BOUNDS = (
    (0.0, None, False),
    (0.0, None, False),
    (1.0, 1000.0, True),
    (0.1, 64.0, True),
    (1.0, 1.0e9, True),
    (0.0, 1.0, True),
    (-20.0, 20.0, True),
    *((0.0, 1.0, True) for _ in range(8)),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_apply_validation_base", path)
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
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
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
        pin_kind(node, "A", kind)
        pin_kind(node, "B", kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def length(source, source_pin: str, kind: str, x: int, y: int):
        node = add_form(f"length_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin: str, kind: str, index: int, x: int, y: int):
        node = add_form(f"item_{source_pin}_{index}_{len(builder.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        scalar.set_default(node, "Dimension 1", str(index))
        bp.connect(source, source_pin, node, "Array")
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

    invalidate = set_value("CameraApplyScratchStageValidV1", "bool", 256, 3840, "false")
    failure = set_value("CameraApplyFailureCodeV1", "string", 480, 3840, "validation_failed")
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", failure, "execute")

    input_valid = get("CameraApplyInputValidV1", "bool", 0, 0)
    input_valid_condition = compare("BooleanAND", input_valid, "CameraApplyInputValidV1", 256, 0, default="true")
    engine_version = get("CameraApplyCapabilityEngineVersionV1", "string", 0, 160)
    engine_condition = compare("NotEqual_StrStr", engine_version, "CameraApplyCapabilityEngineVersionV1", 256, 160, default="", kind="string")
    manifest_id = get("CameraApplyCapabilityManifestIdV1", "string", 0, 320)
    manifest_condition = compare("NotEqual_StrStr", manifest_id, "CameraApplyCapabilityManifestIdV1", 256, 320, default="", kind="string")
    preset_id = get("CameraApplyInputFilmbackPresetIdV1", "string", 0, 480)
    preset_condition = compare("NotEqual_StrStr", preset_id, "CameraApplyInputFilmbackPresetIdV1", 256, 480, default="", kind="string")
    capability = get("CameraApplyCapabilityAvailableV1", "bool", 0, 640, True)
    capability_length = length(capability, "CameraApplyCapabilityAvailableV1", "bool", 256, 640)
    capability_shape = compare("EqualEqual_IntInt", capability_length, "ReturnValue", 480, 640, default="15", kind="int")
    values = get("CameraApplyInputTargetValuesV1", "real", 0, 800, True)
    value_length = length(values, "CameraApplyInputTargetValuesV1", "real", 256, 800)
    value_shape = compare("EqualEqual_IntInt", value_length, "ReturnValue", 480, 800, default="15", kind="int")

    required_conditions = []
    for index in range(5):
        capability_item = item(capability, "CameraApplyCapabilityAvailableV1", "bool", index, 704 + index * 224, 1120)
        required_conditions.append(compare("BooleanAND", capability_item, "Output", 704 + index * 224, 1280, default="true"))

    value_conditions = []
    for index, (minimum, maximum, inclusive) in enumerate(BOUNDS):
        column = index % 5
        row = index // 5
        x = 704 + column * 1184
        y = 1600 + row * 640
        value_item = item(values, "CameraApplyInputTargetValuesV1", "real", index, x, y)
        value_conditions.append(builder.finite(value_item, "Output", x + 224, y))
        lower_member = "GreaterEqual_DoubleDouble" if inclusive else "Greater_DoubleDouble"
        value_conditions.append(compare(lower_member, value_item, "Output", x + 448, y, default=str(minimum), kind="real"))
        if maximum is not None:
            value_conditions.append(compare("LessEqual_DoubleDouble", value_item, "Output", x + 672, y, default=str(maximum), kind="real"))

    all_conditions = [
        input_valid_condition,
        engine_condition,
        manifest_condition,
        preset_condition,
        capability_shape,
        value_shape,
        *required_conditions,
        *value_conditions,
    ]
    ready = combine(all_conditions, 704, 3200)
    guard = builder.add("validation_guard", "branch", 11008, 3840)
    bp.connect(failure, "then", guard, "execute")
    bp.connect(ready, "ReturnValue", guard, "Condition")
    clear_failure = set_value("CameraApplyFailureCodeV1", "string", 11232, 3840, "")
    publish = set_value("CameraApplyScratchStageValidV1", "bool", 11456, 3840, "true")
    bp.connect(guard, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", publish, "execute")

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
