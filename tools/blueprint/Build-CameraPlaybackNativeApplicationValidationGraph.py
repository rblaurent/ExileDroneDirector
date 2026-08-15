"""Build read-only preflight for staged playback-native application input."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateCameraPlaybackNativeApplicationInputsV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
DRONE_CAMERA_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C'"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_native_validation_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
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
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", "PinType.ContainerType=None", line, 1)

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
    templates = args.project_root / "tools/blueprint/templates"
    capture_forms = bp.read_blocks(templates / "waypoint-capture-node-forms.eddgraph")
    capture_live = bp.read_blocks(args.project_root / "tools/blueprint/snippets/capture-current-waypoint.eddgraph")
    native = bp.read_blocks(templates / "camera-engine-basic-node-forms.eddgraph")
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    quat_eval = bp.read_blocks(templates / "trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(templates / "orientation-compiler-native-node-forms.eddgraph")
    quat_break = bp.read_blocks(templates / "repository-codec-break-quat-node-form.eddgraph")
    vector = bp.read_blocks(templates / "repository-codec-vector-node-forms.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture_forms, r'MemberName="DroneCameraRef"'),
        is_valid=bp.find_block(capture_live, r'MemberName="IsValid"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        self_call=bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
        quat_finite=bp.find_block(quat_eval, r'MemberName="Quat_IsFinite"'),
        quat_size=bp.find_block(quat_compiler, r'MemberName="Quat_Size"'),
        quat_multiply=bp.find_block(quat_compiler, r'MemberName="Multiply_QuatQuat"'),
        break_quat=bp.find_block(quat_break, r'MemberName="BreakQuat"'),
        break_vector=bp.find_block(vector, r'MemberName="BreakVector"'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def variable(node, name: str, kind: str) -> None:
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else kind)
        pin_kind(node, name, kind)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind)
        return node

    def set_value(name: str, kind: str, x: int, y: int, value: str):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        scalar.set_default(node, name, value)
        return node

    def retarget(node, member: str, kinds: dict[str, str]):
        scalar.retarget_function(node, member)
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, right=None, right_pin=None, default=None):
        node = builder.add(f"cmp_{member}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member, {"A": "real", "B": "real", "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def combine(member: str, conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (other, other_pin) in enumerate(conditions[1:]):
            node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x + index * 208, y)
            retarget(node, member, {"A": "bool", "B": "bool", "ReturnValue": "bool"})
            bp.connect(current, current_pin, node, "A")
            bp.connect(other, other_pin, node, "B")
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    invalidate = set_value("CameraPlaybackNativePreflightValidV1", "bool", 256, 6720, "false")
    failure = set_value("CameraPlaybackNativeFailureCodeV1", "string", 480, 6720, "native_preflight_failed")
    engine_validate = add_form("engine_validate", "self_call", 704, 6720)
    engine_validate.text = re.sub(
        r"FunctionReference=\([^\n]*\)",
        'FunctionReference=(MemberName="ValidateCameraEngineApplicationInputsV1",bSelfContext=True)',
        engine_validate.text,
        1,
    )
    engine_validate.mutate_pin(
        "self",
        lambda line: re.sub(
            r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
            f"PinType.PinSubCategoryObject={TARGET}",
            line,
            1,
        ),
    )
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", failure, "execute")
    bp.connect(failure, "then", engine_validate, "execute")

    camera_ref = add_form("camera_ref", "camera_ref", 0, 0)
    actor_valid = add_form("actor_valid", "is_valid", 256, 0)
    bp.connect(camera_ref, "DroneCameraRef", actor_valid, "Object")
    actor_guard = builder.add("actor_guard", "branch", 960, 6720)
    bp.connect(engine_validate, "then", actor_guard, "execute")
    bp.connect(actor_valid, "ReturnValue", actor_guard, "Condition")

    component = add_form("component", "component", 256, 256)
    internal = 'VariableReference=(MemberName="DroneCamera",bSelfContext=True)'
    external = f'VariableReference=(MemberParent="{DRONE_CAMERA_CLASS}",MemberName="DroneCamera")'
    if component.text.count(internal) != 1:
        raise RuntimeError("native DroneCamera component form is not the reviewed internal-owner shape")
    component.text = component.text.replace(internal, external)
    bp.connect(camera_ref, "DroneCameraRef", component, "self")
    component_valid = add_form("component_valid", "is_valid", 512, 256)
    bp.connect(component, "DroneCamera", component_valid, "Object")
    component_guard = builder.add("component_guard", "branch", 1184, 6720)
    bp.connect(actor_guard, "then", component_guard, "execute")
    bp.connect(component_valid, "ReturnValue", component_guard, "Condition")

    conditions = []
    for index, name in enumerate(("CameraPlaybackNativeInputValidV1", "CameraPlaybackNativeStageValidV1", "CameraApplyScratchStageValidV1")):
        source = get(name, "bool", 0, 640 + index * 160)
        conditions.append((source, name))

    position = get("CameraPlaybackNativeInputPositionV1", "vector", 0, 1280)
    break_position = add_form("break_position", "break_vector", 320, 1280)
    pin_kind(break_position, "InVec", "vector")
    bp.connect(position, "CameraPlaybackNativeInputPositionV1", break_position, "InVec")
    for index, axis in enumerate("XYZ"):
        pin_kind(break_position, axis, "real")
        finite = builder.finite(break_position, axis, 576, 1280 + index * 144)
        conditions.append((finite, "ReturnValue"))

    quaternion_sources = {}
    for index, (label, name) in enumerate((
        ("body", "CameraPlaybackNativeInputBodyWorldQuatV1"),
        ("gimbal", "CameraPlaybackNativeInputGimbalWorldQuatV1"),
        ("relative", "CameraPlaybackNativeInputGimbalRelativeQuatV1"),
    )):
        y = 1920 + index * 512
        source = get(name, "quat", 0, y)
        finite = add_form(f"{label}_finite", "quat_finite", 320, y)
        size = add_form(f"{label}_size", "quat_size", 320, y + 160)
        for node in (finite, size):
            pin_kind(node, "Q", "quat")
            bp.connect(source, name, node, "Q")
        pin_kind(finite, "ReturnValue", "bool")
        pin_kind(size, "ReturnValue", "real")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", 576, y + 112, default="0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", 800, y + 240, default="1.000001")
        conditions.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))
        quaternion_sources[label] = (source, name)

    recomposed = add_form("recomposed_gimbal", "quat_multiply", 1152, 1920)
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(recomposed, pin, "quat")
    bp.connect(*quaternion_sources["body"], recomposed, "A")
    bp.connect(*quaternion_sources["relative"], recomposed, "B")
    expected_break = add_form("break_expected_gimbal", "break_quat", 1408, 1920)
    actual_break = add_form("break_recomposed_gimbal", "break_quat", 1408, 2560)
    for node, source, source_pin in (
        (expected_break, *quaternion_sources["gimbal"]),
        (actual_break, recomposed, "ReturnValue"),
    ):
        pin_kind(node, "InQuat", "quat")
        for axis in "XYZW":
            pin_kind(node, axis, "real")
        bp.connect(source, source_pin, node, "InQuat")

    direct_conditions = []
    antipodal_conditions = []
    for index, axis in enumerate("XYZW"):
        y = 3840 + index * 416
        delta = builder.add(f"reconstruction_delta_{axis}", "math", 1664, y)
        retarget(delta, "Subtract_DoubleDouble", {"A": "real", "B": "real", "ReturnValue": "real"})
        bp.connect(actual_break, axis, delta, "A")
        bp.connect(expected_break, axis, delta, "B")
        direct_conditions.extend((
            (compare("GreaterEqual_DoubleDouble", delta, "ReturnValue", 1888, y - 64, default="-0.000001"), "ReturnValue"),
            (compare("LessEqual_DoubleDouble", delta, "ReturnValue", 2112, y + 64, default="0.000001"), "ReturnValue"),
        ))
        total = builder.add(f"reconstruction_sum_{axis}", "math", 2400, y)
        retarget(total, "Add_DoubleDouble", {"A": "real", "B": "real", "ReturnValue": "real"})
        bp.connect(actual_break, axis, total, "A")
        bp.connect(expected_break, axis, total, "B")
        antipodal_conditions.extend((
            (compare("GreaterEqual_DoubleDouble", total, "ReturnValue", 2624, y - 64, default="-0.000001"), "ReturnValue"),
            (compare("LessEqual_DoubleDouble", total, "ReturnValue", 2848, y + 64, default="0.000001"), "ReturnValue"),
        ))
    direct = combine("BooleanAND", direct_conditions, 3200, 5280)
    antipodal = combine("BooleanAND", antipodal_conditions, 3200, 5504)
    reconstruction = combine("BooleanOR", (direct, antipodal), 4864, 5392)
    conditions.append(reconstruction)
    ready = combine("BooleanAND", conditions, 5120, 5952)

    guard = builder.add("preflight_guard", "branch", 1408, 6720)
    clear = set_value("CameraPlaybackNativeFailureCodeV1", "string", 1632, 6720, "")
    publish = set_value("CameraPlaybackNativePreflightValidV1", "bool", 1856, 6720, "true")
    bp.connect(component_guard, "then", guard, "execute")
    bp.connect(ready[0], ready[1], guard, "Condition")
    bp.connect(guard, "then", clear, "execute")
    bp.connect(clear, "then", publish, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
