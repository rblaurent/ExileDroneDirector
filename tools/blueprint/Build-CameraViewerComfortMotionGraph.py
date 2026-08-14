"""Build viewer-local motion comfort candidates after validated inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCameraViewerComfortMotionV1"
WEIGHTS = (
    "CameraComfortRollWeightV1", "CameraComfortShakeWeightV1", "CameraComfortBlurWeightV1",
    "CameraComfortExposureChangeWeightV1", "CameraComfortChromaticAberrationWeightV1",
)
EPSILON = "1e-9"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_comfort_motion_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def pin_kind(node, pin: str, kind: str, array: bool = False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"), "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "rotator": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Rotator\'"'),
    }[kind]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path); args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    airframe = bp.read_blocks(args.project_root / "tools/blueprint/templates/airframe-gimbal-native-node-forms.eddgraph")
    quat_native = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    horizon = bp.read_blocks(args.project_root / "tools/blueprint/templates/horizon-node-forms.eddgraph")
    position = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-compiled-position-route-v1.eddgraph")
    velocity = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/compute-position-route-velocities-v1.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    forms.update(
        select=bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
        array_add=bp.find_block(capture, r'MemberName="Array_Add"'), array_clear=bp.find_block(reset, r'MemberName="Array_Clear"'),
        vector_multiply=bp.find_block(position, r'MemberName="Multiply_VectorVector"'), vector_add=bp.find_block(position, r'MemberName="Add_VectorVector"'),
        make_vector=bp.find_block(velocity, r'MemberName="MakeVector"'),
        quat_slerp=bp.find_block(quat_native, r'MemberName="Quat_Slerp"'), quat_normalized=bp.find_block(quat_native, r'MemberName="Quat_Normalized"'),
        quat_multiply=bp.find_block(quat_compiler, r'MemberName="Multiply_QuatQuat"'),
        quat_axis_x=bp.find_block(airframe, r'MemberName="Quat_GetAxisX"'), quat_axis_z=bp.find_block(airframe, r'MemberName="Quat_GetAxisZ"'),
        dot=bp.find_block(airframe, r'MemberName="Dot_VectorVector"'), make_rot_xz=bp.find_block(horizon, r'MemberName="MakeRotFromXZ"'),
        rotator_to_quat=bp.find_block(airframe, r'MemberName="Conv_RotatorToQuaternion"'),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else kind); pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind, array)
    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind, array); return node
    def set_(name, kind, x, y, source=None, source_pin=None, default=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind)
        if source is not None: bp.connect(source, source_pin, node, name)
        elif default is not None: scalar.set_default(node, name, default)
        return node
    def select(condition, false_default, true_source, true_pin, kind, x, y):
        node = b.add(f"select_{kind}_{len(b.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"): pin_kind(node, pin, kind)
        pin_kind(node, "Index", "bool"); bp.connect(condition, "CameraComfortEnabledV1", node, "Index"); scalar.set_default(node, "Option 0", false_default); bp.connect(true_source, true_pin, node, "Option 1"); return node
    def compare(member, source, source_pin, default, kind, x, y):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool"); bp.connect(source, source_pin, node, "A"); scalar.set_default(node, "B", default); return node
    def bool_op(member, left, left_pin, right, right_pin, x, y):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A"); bp.connect(right, right_pin, node, "B"); return node
    def array_op(form, array_get, array_pin, x, y, item=None, item_pin=None):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y); pin_kind(node, "TargetArray", "real", True); bp.connect(array_get, array_pin, node, "TargetArray")
        if form == "array_add": pin_kind(node, "NewItem", "real"); pin_kind(node, "ReturnValue", "int"); bp.connect(item, item_pin, node, "NewItem")
        return node
    def make_scalar_vector(source, source_pin, x, y):
        node = b.add(f"scalar_vector_{len(b.nodes)}", "make_vector", x, y)
        for pin in ("X", "Y", "Z"): pin_kind(node, pin, "real"); bp.connect(source, source_pin, node, pin)
        pin_kind(node, "ReturnValue", "vector"); return node

    validation = get("CameraComfortValidationValidV1", "bool", 0, 0)
    guard = b.add("validation_guard", "branch", 256, 3200); bp.connect(b.entry, "then", guard, "execute"); bp.connect(validation, "CameraComfortValidationValidV1", guard, "Condition")
    enabled = get("CameraComfortEnabledV1", "bool", 0, 256)
    weight_sources = [get(name, "real", 0, 512 + index * 160) for index, name in enumerate(WEIGHTS)]
    effective = [select(enabled, "1.0", source, name, "real", 320, 512 + index * 160) for index, (source, name) in enumerate(zip(weight_sources, WEIGHTS))]
    effective_array = get("CameraComfortCandidateEffectiveWeightsV1", "real", 0, 1440, True)
    clear = array_op("array_clear", effective_array, "CameraComfortCandidateEffectiveWeightsV1", 512, 3200)
    appends = [array_op("array_add", effective_array, "CameraComfortCandidateEffectiveWeightsV1", 736 + index * 224, 3200, source, "ReturnValue") for index, source in enumerate(effective)]
    bp.connect(guard, "then", clear, "execute"); bp.connect(clear, "then", appends[0], "execute")
    for left, right in zip(appends, appends[1:]): bp.connect(left, "then", right, "execute")

    position_input = get("CameraComfortInputPositionV1", "vector", 1600, 0)
    translation = get("CameraComfortInputProceduralTranslationOffsetV1", "vector", 1600, 192)
    shake_vector = make_scalar_vector(effective[1], "ReturnValue", 1920, 192)
    scaled_translation = b.add("scaled_translation", "vector_multiply", 2144, 192); bp.connect(translation, "CameraComfortInputProceduralTranslationOffsetV1", scaled_translation, "A"); bp.connect(shake_vector, "ReturnValue", scaled_translation, "B")
    final_position = b.add("final_position", "vector_add", 2368, 96); bp.connect(position_input, "CameraComfortInputPositionV1", final_position, "A"); bp.connect(scaled_translation, "ReturnValue", final_position, "B")

    gimbal_input = get("CameraComfortInputGimbalQuatV1", "quat", 1600, 512)
    shake_quat = get("CameraComfortInputProceduralRotationOffsetV1", "quat", 1600, 704)
    scaled_shake = b.add("scaled_shake", "quat_slerp", 1920, 704); pin_kind(scaled_shake, "A", "quat"); pin_kind(scaled_shake, "B", "quat"); pin_kind(scaled_shake, "Alpha", "real"); pin_kind(scaled_shake, "ReturnValue", "quat"); scalar.set_default(scaled_shake, "A", "0, 0, 0, 1"); bp.connect(shake_quat, "CameraComfortInputProceduralRotationOffsetV1", scaled_shake, "B"); bp.connect(effective[1], "ReturnValue", scaled_shake, "Alpha")
    shaken_raw = b.add("shaken_raw", "quat_multiply", 2144, 608); bp.connect(gimbal_input, "CameraComfortInputGimbalQuatV1", shaken_raw, "A"); bp.connect(scaled_shake, "ReturnValue", shaken_raw, "B")
    shaken = b.add("shaken", "quat_normalized", 2368, 608); bp.connect(shaken_raw, "ReturnValue", shaken, "Q"); scalar.set_default(shaken, "Tolerance", EPSILON)
    forward = b.add("forward", "quat_axis_x", 2592, 512); bp.connect(shaken, "ReturnValue", forward, "Q")
    authored_up = b.add("authored_up", "quat_axis_z", 2592, 704); bp.connect(shaken, "ReturnValue", authored_up, "Q")
    dot = b.add("vertical_dot", "dot", 2816, 512); bp.connect(forward, "ReturnValue", dot, "A"); scalar.set_default(dot, "B", "0, 0, 1")
    positive = compare("GreaterEqual_DoubleDouble", dot, "ReturnValue", "0.999999", "real", 3040, 448)
    negative = compare("LessEqual_DoubleDouble", dot, "ReturnValue", "-0.999999", "real", 3040, 592)
    vertical = bool_op("BooleanOR", positive, "ReturnValue", negative, "ReturnValue", 3264, 512)
    up_hint = b.add("up_hint", "select", 3488, 608)
    for pin in ("Option 0", "Option 1", "ReturnValue"): pin_kind(up_hint, pin, "vector")
    pin_kind(up_hint, "Index", "bool"); bp.connect(vertical, "ReturnValue", up_hint, "Index"); scalar.set_default(up_hint, "Option 0", "0, 0, 1"); bp.connect(authored_up, "ReturnValue", up_hint, "Option 1")
    level_rot = b.add("level_rot", "make_rot_xz", 3712, 512); bp.connect(forward, "ReturnValue", level_rot, "X"); bp.connect(up_hint, "ReturnValue", level_rot, "Z")
    level_quat = b.add("level_quat", "rotator_to_quat", 3936, 512); bp.connect(level_rot, "ReturnValue", level_quat, "InRot")
    comforted_raw = b.add("comforted_raw", "quat_slerp", 4160, 512); bp.connect(level_quat, "ReturnValue", comforted_raw, "A"); bp.connect(shaken, "ReturnValue", comforted_raw, "B"); bp.connect(effective[0], "ReturnValue", comforted_raw, "Alpha")
    comforted = b.add("comforted", "quat_normalized", 4384, 512); bp.connect(comforted_raw, "ReturnValue", comforted, "Q"); scalar.set_default(comforted, "Tolerance", EPSILON)

    reductions = [compare("Less_DoubleDouble", source, name, "1.0", "real", 1920 + index * 224, 1088) for index, (source, name) in enumerate(zip(weight_sources, WEIGHTS))]
    any_reduction = reductions[0]
    for index, condition in enumerate(reductions[1:]): any_reduction = bool_op("BooleanOR", any_reduction, "ReturnValue", condition, "ReturnValue", 3040 + index * 224, 1088)
    applied = bool_op("BooleanAND", enabled, "CameraComfortEnabledV1", any_reduction, "ReturnValue", 3936, 1088)
    publications = [
        set_("CameraComfortCandidatePositionV1", "vector", 2080, 3200, final_position, "ReturnValue"),
        set_("CameraComfortCandidateGimbalQuatV1", "quat", 2400, 3200, comforted, "ReturnValue"),
        set_("CameraComfortCandidateAppliedV1", "bool", 2720, 3200, applied, "ReturnValue"),
    ]
    bp.connect(appends[-1], "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]): bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
