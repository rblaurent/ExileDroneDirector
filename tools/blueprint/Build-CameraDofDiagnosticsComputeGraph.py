"""Build thin-lens camera DOF diagnostic computation from an accepted stage."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ComputeCameraDofDiagnosticsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_dof_compute_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        return re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)

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
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    forms.update(
        vsize=bp.find_block(native, r'MemberName="VSize"'),
        make_vector=bp.find_block(marker, r'MemberName="MakeVector"'),
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

    def get(name: str, kind: str, x: int, y: int):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        scalar.retarget_variable(node, name, kind)
        return node

    def set_value(name: str, kind: str, x: int, y: int, default=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        scalar.retarget_variable(node, name, kind)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def math(member: str, left, left_pin: str, x: int, y: int, *, right=None, right_pin=None, default=None):
        node = builder.math(member, x, y)
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, right=None, right_pin=None, default=None):
        node = builder.add(f"cmp_{member}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, "real")
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def combine(conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            node = builder.add(f"and_{index}_{len(builder.nodes)}", "compare", x + (index % 5) * 224, y + (index // 5) * 128)
            scalar.retarget_function(node, "BooleanAND")
            for pin in ("A", "B", "ReturnValue"):
                pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A")
            bp.connect(condition, condition_pin, node, "B")
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    invalidate = set_value("CameraDofResultValidV1", "bool", 256, 4800, "false")
    clear_failure = set_value("CameraDofFailureCodeV1", "string", 576, 4800, "")
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", clear_failure, "execute")

    stage_valid = get("CameraDofStageValidV1", "bool", 0, 0)
    width = get("CameraDofStageFilmbackWidthMmV1", "real", 0, 240)
    height = get("CameraDofStageFilmbackHeightMmV1", "real", 0, 480)
    focal = get("CameraDofStageFocalLengthMmV1", "real", 0, 720)
    aperture = get("CameraDofStageApertureFstopV1", "real", 0, 960)
    focus = get("CameraDofStageFocusDistanceCmV1", "real", 0, 1200)

    finite = [
        builder.finite(source, pin, 256, 240 + index * 320)
        for index, (source, pin) in enumerate((
            (width, "CameraDofStageFilmbackWidthMmV1"),
            (height, "CameraDofStageFilmbackHeightMmV1"),
            (focal, "CameraDofStageFocalLengthMmV1"),
            (aperture, "CameraDofStageApertureFstopV1"),
            (focus, "CameraDofStageFocusDistanceCmV1"),
        ))
    ]
    ranges = [
        compare("Greater_DoubleDouble", width, "CameraDofStageFilmbackWidthMmV1", 704, 240, default="0.0"),
        compare("Greater_DoubleDouble", height, "CameraDofStageFilmbackHeightMmV1", 704, 480, default="0.0"),
        compare("GreaterEqual_DoubleDouble", focal, "CameraDofStageFocalLengthMmV1", 704, 720, default="1.0"),
        compare("LessEqual_DoubleDouble", focal, "CameraDofStageFocalLengthMmV1", 928, 720, default="1000.0"),
        compare("GreaterEqual_DoubleDouble", aperture, "CameraDofStageApertureFstopV1", 704, 960, default="0.1"),
        compare("LessEqual_DoubleDouble", aperture, "CameraDofStageApertureFstopV1", 928, 960, default="64.0"),
        compare("GreaterEqual_DoubleDouble", focus, "CameraDofStageFocusDistanceCmV1", 704, 1200, default="1.0"),
        compare("LessEqual_DoubleDouble", focus, "CameraDofStageFocusDistanceCmV1", 928, 1200, default="1000000000.0"),
    ]
    focus_mm = math("Multiply_DoubleDouble", focus, "CameraDofStageFocusDistanceCmV1", 1152, 1200, default="10.0")
    beyond_focal = compare("Greater_DoubleDouble", focus_mm, "ReturnValue", 1376, 1200, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    ready, ready_pin = combine(
        [(stage_valid, "CameraDofStageValidV1"), *[(node, "ReturnValue") for node in finite], *[(node, "ReturnValue") for node in ranges], (beyond_focal, "ReturnValue")],
        1792,
        1600,
    )
    guard = builder.add("compute_guard", "branch", 896, 4800)
    bp.connect(clear_failure, "then", guard, "execute")
    bp.connect(ready, ready_pin, guard, "Condition")
    failure = set_value("CameraDofFailureCodeV1", "string", 1152, 5120, "camera_dof_compute_failed")
    bp.connect(guard, "else", failure, "execute")

    sensor_vector = add_form("sensor_vector", "make_vector", 0, 1920)
    for axis, source, pin in (
        ("X", width, "CameraDofStageFilmbackWidthMmV1"),
        ("Y", height, "CameraDofStageFilmbackHeightMmV1"),
    ):
        pin_kind(sensor_vector, axis, "real")
        bp.connect(source, pin, sensor_vector, axis)
    pin_kind(sensor_vector, "Z", "real")
    scalar.set_default(sensor_vector, "Z", "0.0")
    pin_kind(sensor_vector, "ReturnValue", "vector")
    diagonal = add_form("sensor_diagonal", "vsize", 256, 1920)
    pin_kind(diagonal, "A", "vector")
    pin_kind(diagonal, "ReturnValue", "real")
    bp.connect(sensor_vector, "ReturnValue", diagonal, "A")
    coc = math("Divide_DoubleDouble", diagonal, "ReturnValue", 480, 1920, default="1500.0")
    focal_squared = math("Multiply_DoubleDouble", focal, "CameraDofStageFocalLengthMmV1", 0, 2240, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    aperture_coc = math("Multiply_DoubleDouble", aperture, "CameraDofStageApertureFstopV1", 480, 2240, right=coc, right_pin="ReturnValue")
    hyperfocal_quotient = math("Divide_DoubleDouble", focal_squared, "ReturnValue", 704, 2240, right=aperture_coc, right_pin="ReturnValue")
    hyperfocal_mm = math("Add_DoubleDouble", hyperfocal_quotient, "ReturnValue", 928, 2240, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    hyperfocal_cm = math("Multiply_DoubleDouble", hyperfocal_mm, "ReturnValue", 1152, 2240, default="0.1")
    focus_minus_focal = math("Subtract_DoubleDouble", focus_mm, "ReturnValue", 0, 2560, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    near_denominator = math("Add_DoubleDouble", hyperfocal_mm, "ReturnValue", 480, 2560, right=focus_minus_focal, right_pin="ReturnValue")
    numerator = math("Multiply_DoubleDouble", hyperfocal_mm, "ReturnValue", 704, 2560, right=focus_mm, right_pin="ReturnValue")
    near_mm = math("Divide_DoubleDouble", numerator, "ReturnValue", 928, 2560, right=near_denominator, right_pin="ReturnValue")
    near_cm = math("Multiply_DoubleDouble", near_mm, "ReturnValue", 1152, 2560, default="0.1")
    front_depth = math("Subtract_DoubleDouble", focus, "CameraDofStageFocusDistanceCmV1", 1376, 2560, right=near_cm, right_pin="ReturnValue")
    width_numerator = math("Multiply_DoubleDouble", focus, "CameraDofStageFocusDistanceCmV1", 0, 2880, right=width, right_pin="CameraDofStageFilmbackWidthMmV1")
    plane_width = math("Divide_DoubleDouble", width_numerator, "ReturnValue", 256, 2880, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    height_numerator = math("Multiply_DoubleDouble", focus, "CameraDofStageFocusDistanceCmV1", 480, 2880, right=height, right_pin="CameraDofStageFilmbackHeightMmV1")
    plane_height = math("Divide_DoubleDouble", height_numerator, "ReturnValue", 704, 2880, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    hyperfocal_plus_focal = math("Add_DoubleDouble", hyperfocal_mm, "ReturnValue", 0, 3200, right=focal, right_pin="CameraDofStageFocalLengthMmV1")
    far_unbounded = compare("GreaterEqual_DoubleDouble", focus_mm, "ReturnValue", 256, 3200, right=hyperfocal_plus_focal, right_pin="ReturnValue")
    far_denominator = math("Subtract_DoubleDouble", hyperfocal_mm, "ReturnValue", 480, 3200, right=focus_minus_focal, right_pin="ReturnValue")
    far_mm = math("Divide_DoubleDouble", numerator, "ReturnValue", 704, 3200, right=far_denominator, right_pin="ReturnValue")
    far_cm = math("Multiply_DoubleDouble", far_mm, "ReturnValue", 928, 3200, default="0.1")
    rear_depth = math("Subtract_DoubleDouble", far_cm, "ReturnValue", 1152, 3200, right=focus, right_pin="CameraDofStageFocusDistanceCmV1")

    common_specs = (
        ("CameraDofCircleOfConfusionMmV1", coc, "ReturnValue"),
        ("CameraDofHyperfocalDistanceCmV1", hyperfocal_cm, "ReturnValue"),
        ("CameraDofFocalPlaneDistanceCmV1", focus, "CameraDofStageFocusDistanceCmV1"),
        ("CameraDofNearLimitCmV1", near_cm, "ReturnValue"),
        ("CameraDofFrontDepthCmV1", front_depth, "ReturnValue"),
        ("CameraDofFocalPlaneWidthCmV1", plane_width, "ReturnValue"),
        ("CameraDofFocalPlaneHeightCmV1", plane_height, "ReturnValue"),
    )
    common = []
    for index, (name, source, pin) in enumerate(common_specs):
        setter = set_value(name, "real", 1152 + index * 352, 4800)
        bp.connect(source, pin, setter, name)
        common.append(setter)
    bp.connect(guard, "then", common[0], "execute")
    for left, right in zip(common, common[1:]):
        bp.connect(left, "then", right, "execute")
    far_branch = builder.add("far_branch", "branch", 3616, 4800)
    bp.connect(common[-1], "then", far_branch, "execute")
    bp.connect(far_unbounded, "ReturnValue", far_branch, "Condition")

    unbounded_far = set_value("CameraDofFarLimitCmV1", "real", 3872, 4640, "0.0")
    unbounded_rear = set_value("CameraDofRearDepthCmV1", "real", 4224, 4640, "0.0")
    unbounded_flag = set_value("CameraDofFarUnboundedV1", "bool", 4576, 4640, "true")
    unbounded_valid = set_value("CameraDofResultValidV1", "bool", 4928, 4640, "true")
    bp.connect(far_branch, "then", unbounded_far, "execute")
    for left, right in zip((unbounded_far, unbounded_rear, unbounded_flag), (unbounded_rear, unbounded_flag, unbounded_valid)):
        bp.connect(left, "then", right, "execute")

    bounded_far = set_value("CameraDofFarLimitCmV1", "real", 3872, 4960)
    bounded_rear = set_value("CameraDofRearDepthCmV1", "real", 4224, 4960)
    bounded_flag = set_value("CameraDofFarUnboundedV1", "bool", 4576, 4960, "false")
    bounded_valid = set_value("CameraDofResultValidV1", "bool", 4928, 4960, "true")
    bp.connect(far_cm, "ReturnValue", bounded_far, "CameraDofFarLimitCmV1")
    bp.connect(rear_depth, "ReturnValue", bounded_rear, "CameraDofRearDepthCmV1")
    bp.connect(far_branch, "else", bounded_far, "execute")
    for left, right in zip((bounded_far, bounded_rear, bounded_flag), (bounded_rear, bounded_flag, bounded_valid)):
        bp.connect(left, "then", right, "execute")

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
