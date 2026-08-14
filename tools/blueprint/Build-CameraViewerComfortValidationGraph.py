"""Build fail-closed validation for viewer-local comfort inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateCameraViewerComfortInputsV1"
VECTOR_INPUTS = ("CameraComfortInputPositionV1", "CameraComfortInputProceduralTranslationOffsetV1")
QUAT_INPUTS = ("CameraComfortInputGimbalQuatV1", "CameraComfortInputProceduralRotationOffsetV1")
WEIGHTS = (
    "CameraComfortRollWeightV1", "CameraComfortShakeWeightV1", "CameraComfortBlurWeightV1",
    "CameraComfortExposureChangeWeightV1", "CameraComfortChromaticAberrationWeightV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_comfort_validation_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "string": ("string", "", "None"),
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
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
    vector_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    quat_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    forms.update(
        break_vector=bp.find_block(vector_forms, r'MemberName="BreakVector"'),
        quat_finite=bp.find_block(quat_forms, r'MemberName="Quat_IsFinite"'),
        quat_size=bp.find_block(quat_compiler, r'MemberName="Quat_Size"'),
        foreach=bp.find_block(sync, r"K2Node_MacroInstance"),
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y); b.nodes.append(node); return node

    def variable(node, name: str, kind: str, array: bool = False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind, array); return node

    def set_(name: str, kind: str, x: int, y: int, value: str):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind); scalar.set_default(node, name, value); return node

    def compare(member: str, left, left_pin: str, x: int, y: int, default: str, kind: str = "real"):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A"); scalar.set_default(node, "B", default); return node

    def combine(member: str, conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            node = b.add(f"{member}_{len(b.nodes)}", "compare", x + index * 208, y)
            scalar.retarget_function(node, member)
            for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A"); bp.connect(condition, condition_pin, node, "B")
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    invalidate = set_("CameraComfortValidationValidV1", "bool", 256, 4000, "false")
    scratch_false = set_("CameraComfortScratchValidV1", "bool", 480, 4000, "false")
    scratch_index = set_("CameraComfortScratchChannelIndexV1", "int", 704, 4000, "0")
    failure = set_("CameraComfortFailureCodeV1", "string", 928, 4000, "validation_failed")
    bp.connect(b.entry, "then", invalidate, "execute"); bp.connect(invalidate, "then", scratch_false, "execute")
    bp.connect(scratch_false, "then", scratch_index, "execute"); bp.connect(scratch_index, "then", failure, "execute")

    conditions = []
    frame_valid = get("CameraComfortInputFrameValidV1", "bool", 0, 0)
    conditions.append((frame_valid, "CameraComfortInputFrameValidV1"))
    for index, name in enumerate(VECTOR_INPUTS):
        y = 256 + index * 560; source = get(name, "vector", 0, y)
        split = add_form(f"break_{name}", "break_vector", 320, y); pin_kind(split, "InVec", "vector")
        for pin in ("X", "Y", "Z"): pin_kind(split, pin, "real")
        bp.connect(source, name, split, "InVec")
        for component_index, component in enumerate(("X", "Y", "Z")):
            finite = b.finite(split, component, 640, y + component_index * 144); conditions.append((finite, "ReturnValue"))
    for index, name in enumerate(QUAT_INPUTS):
        y = 1440 + index * 560; source = get(name, "quat", 0, y)
        finite = add_form(f"finite_{name}", "quat_finite", 320, y); pin_kind(finite, "Q", "quat"); pin_kind(finite, "ReturnValue", "bool"); bp.connect(source, name, finite, "Q")
        size = add_form(f"size_{name}", "quat_size", 320, y + 160); pin_kind(size, "Q", "quat"); pin_kind(size, "ReturnValue", "real"); bp.connect(source, name, size, "Q")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", 640, y + 112, "0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", 640, y + 256, "1.000001")
        conditions.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))
    for index, name in enumerate(WEIGHTS):
        y = index * 208; source = get(name, "real", 2048, y)
        finite = b.finite(source, name, 2368, y)
        lower = compare("GreaterEqual_DoubleDouble", source, name, 2816, y, "0.0")
        upper = compare("LessEqual_DoubleDouble", source, name, 3040, y, "1.0")
        conditions.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))
    values = get("CameraComfortInputChannelValuesV1", "real", 2048, 1248, True)
    length = add_form("channel_length", "length", 2368, 1248); pin_kind(length, "TargetArray", "real", True); pin_kind(length, "ReturnValue", "int"); bp.connect(values, "CameraComfortInputChannelValuesV1", length, "TargetArray")
    shape = compare("EqualEqual_IntInt", length, "ReturnValue", 2816, 1248, "13", "int"); conditions.append((shape, "ReturnValue"))
    static, static_pin = combine("BooleanAND", conditions, 3328, 2560)
    shape_branch = b.add("shape_branch", "branch", 9728, 4000); bp.connect(failure, "then", shape_branch, "execute"); bp.connect(static, static_pin, shape_branch, "Condition")
    scratch_true = set_("CameraComfortScratchValidV1", "bool", 9952, 4000, "true"); bp.connect(shape_branch, "then", scratch_true, "execute")
    loop = add_form("channel_loop", "foreach", 10176, 4000); pin_kind(loop, "Array", "real", True); pin_kind(loop, "Array Element", "real"); pin_kind(loop, "Array Index", "int"); bp.connect(values, "CameraComfortInputChannelValuesV1", loop, "Array"); bp.connect(scratch_true, "then", loop, "Exec")
    item = add_form("channel_item", "item", 10432, 1440); pin_kind(item, "Array", "real", True); pin_kind(item, "Output", "real"); bp.connect(values, "CameraComfortInputChannelValuesV1", item, "Array"); bp.connect(loop, "Array Index", item, "Dimension 1")
    finite_item = b.finite(item, "Output", 10752, 1440)

    def index_eq(value: str, y: int): return compare("EqualEqual_IntInt", loop, "Array Index", 10752, y, value, "int")
    i0, i1, i2, i3, i4 = (index_eq(str(index), 1760 + index * 144) for index in range(5))
    ge5 = compare("GreaterEqual_IntInt", loop, "Array Index", 10752, 2480, "5", "int")
    le12 = compare("LessEqual_IntInt", loop, "Array Index", 10976, 2480, "12", "int")
    high_norm, high_norm_pin = combine("BooleanAND", [(ge5, "ReturnValue"), (le12, "ReturnValue")], 11200, 2480)
    normalized_index, normalized_index_pin = combine("BooleanOR", [(i3, "ReturnValue"), (high_norm, high_norm_pin)], 11424, 2336)

    def range_case(identifier, identifier_pin: str, minimum: str, maximum: str, x: int, y: int):
        lower = compare("GreaterEqual_DoubleDouble", item, "Output", x, y, minimum)
        upper = compare("LessEqual_DoubleDouble", item, "Output", x + 208, y, maximum)
        return combine("BooleanAND", [(identifier, identifier_pin), (lower, "ReturnValue"), (upper, "ReturnValue")], x + 416, y)

    focal = range_case(i0, "ReturnValue", "1.0", "1000.0", 11840, 1760)
    aperture = range_case(i1, "ReturnValue", "0.1", "64.0", 11840, 1984)
    focus = range_case(i2, "ReturnValue", "1.0", "1000000000.0", 11840, 2208)
    exposure = range_case(i4, "ReturnValue", "-20.0", "20.0", 11840, 2432)
    normalized = range_case(normalized_index, normalized_index_pin, "0.0", "1.0", 11840, 2656)
    bounds, bounds_pin = combine("BooleanOR", [focal, aperture, focus, exposure, normalized], 12880, 2208)
    item_valid, item_valid_pin = combine("BooleanAND", [(finite_item, "ReturnValue"), (bounds, bounds_pin)], 13712, 2432)
    item_branch = b.add("item_branch", "branch", 14128, 4000); bp.connect(loop, "LoopBody", item_branch, "execute"); bp.connect(item_valid, item_valid_pin, item_branch, "Condition")
    reject = set_("CameraComfortScratchValidV1", "bool", 14352, 4224, "false"); bp.connect(item_branch, "else", reject, "execute")
    final_scratch = get("CameraComfortScratchValidV1", "bool", 14352, 3040)
    final_branch = b.add("final_branch", "branch", 14576, 4000); bp.connect(loop, "Completed", final_branch, "execute"); bp.connect(final_scratch, "CameraComfortScratchValidV1", final_branch, "Condition")
    success = set_("CameraComfortFailureCodeV1", "string", 14800, 4000, "")
    publish = set_("CameraComfortValidationValidV1", "bool", 15024, 4000, "true")
    bp.connect(final_branch, "then", success, "execute"); bp.connect(success, "then", publish, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
