"""Build transactional native pose plus accepted engine-property application."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ApplyCameraPlaybackNativeFrameV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
DRONE_CAMERA_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C'"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_native_apply_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"), "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "rotator": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Rotator\'"'),
        "transform": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Transform\'"'),
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", "PinType.ContainerType=None", line, 1)
    node.mutate_pin(pin_name, mutate)


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name)
    lines = [line for line in node.text.splitlines() if f"PinId={pin_id}" not in line]
    node.text = "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    root = args.project_root / "tools/blueprint"
    capture = bp.read_blocks(root / "templates/waypoint-capture-node-forms.eddgraph")
    capture_live = bp.read_blocks(root / "snippets/capture-current-waypoint.eddgraph")
    native = bp.read_blocks(root / "templates/camera-engine-basic-node-forms.eddgraph")
    transform = bp.read_blocks(root / "templates/repository-codec-transform-node-forms.eddgraph")
    math_forms = bp.read_blocks(root / "templates/repository-codec-math-node-forms.eddgraph")
    linear = bp.read_blocks(root / "templates/linear-playback-node-forms.eddgraph")
    calls = bp.read_blocks(root / "snippets/activate-drone-view.eddgraph")
    quat_break = bp.read_blocks(root / "templates/repository-codec-break-quat-node-form.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture, r'MemberName="DroneCameraRef"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        is_valid=bp.find_block(capture_live, r'MemberName="IsValid"'),
        actor_set=bp.find_block(linear, r'MemberName="K2_SetActorTransform"'),
        actor_get=bp.find_block(capture, r'MemberName="GetTransform"'),
        break_transform=bp.find_block(transform, r'MemberName="BreakTransform"'),
        make_transform=bp.find_block(transform, r'MemberName="MakeTransform"'),
        quat_rotator=bp.find_block(math_forms, r'MemberName="Quat_Rotator"'),
        rotator_quat=bp.find_block(math_forms, r'MemberName="Conv_RotatorToQuaternion"'),
        break_quat=bp.find_block(quat_break, r'MemberName="BreakQuat"'),
        add_int=bp.find_block(capture, r'MemberName="Add_IntInt"'),
        self_call=bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0); builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        builder.nodes.append(node); return node

    def variable(node, name: str, kind: str) -> None:
        scalar.retarget_variable(node, name, "vector" if kind in ("quat", "rotator", "transform") else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y); variable(node, name, kind); return node

    def set_value(name: str, kind: str, x: int, y: int, default: str):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y); variable(node, name, kind); scalar.set_default(node, name, default); return node

    def self_call(name: str, x: int, y: int):
        node = add_form(f"call_{name}_{len(builder.nodes)}", "self_call", x, y)
        node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET}", line, 1))
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, default: str):
        node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): pin_kind(node, pin, "real")
        pin_kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A"); scalar.set_default(node, "B", default); return node

    def combine(member: str, conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (other, other_pin) in enumerate(conditions[1:]):
            node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x + index * 208, y); scalar.retarget_function(node, member)
            for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A"); bp.connect(other, other_pin, node, "B"); current, current_pin = node, "ReturnValue"
        return current, current_pin

    invalidate = set_value("CameraPlaybackNativeResultValidV1", "bool", 256, 5440, "false")
    failure = set_value("CameraPlaybackNativeFailureCodeV1", "string", 480, 5440, "native_apply_failed")
    bp.connect(builder.entry, "then", invalidate, "execute"); bp.connect(invalidate, "then", failure, "execute")

    camera_ref = add_form("camera_ref", "camera_ref", 0, 0)
    component = add_form("component", "component", 256, 160)
    internal = 'VariableReference=(MemberName="DroneCamera",bSelfContext=True)'
    external = f'VariableReference=(MemberParent="{DRONE_CAMERA_CLASS}",MemberName="DroneCamera")'
    if component.text.count(internal) != 1: raise RuntimeError("unexpected component owner")
    component.text = component.text.replace(internal, external); bp.connect(camera_ref, "DroneCameraRef", component, "self")
    actor_valid = add_form("actor_valid", "is_valid", 256, 0); bp.connect(camera_ref, "DroneCameraRef", actor_valid, "Object")
    component_valid = add_form("component_valid", "is_valid", 512, 160); bp.connect(component, "DroneCamera", component_valid, "Object")
    authority = []
    for index, name in enumerate(("CameraPlaybackNativePreflightValidV1", "CameraPlaybackNativeSessionActiveV1", "CameraApplyScratchStageValidV1", "CameraApplySessionActiveV1")):
        source = get(name, "bool", 0, 480 + index * 160); authority.append((source, name))
    ready = combine("BooleanAND", [(actor_valid, "ReturnValue"), (component_valid, "ReturnValue"), *authority], 768, 720)
    apply_guard = builder.add("apply_guard", "branch", 704, 5440); bp.connect(failure, "then", apply_guard, "execute"); bp.connect(*ready, apply_guard, "Condition")

    position = get("CameraPlaybackNativeInputPositionV1", "vector", 0, 1280)
    body = get("CameraPlaybackNativeInputBodyWorldQuatV1", "quat", 0, 1440)
    relative = get("CameraPlaybackNativeInputGimbalRelativeQuatV1", "quat", 0, 1600)
    baseline_actor = get("CameraPlaybackNativeBaselineActorTransformV1", "transform", 0, 1920)
    baseline_component = get("CameraPlaybackNativeBaselineComponentRelativeTransformV1", "transform", 0, 2240)
    break_actor = add_form("break_actor_baseline", "break_transform", 320, 1920); bp.connect(baseline_actor, "CameraPlaybackNativeBaselineActorTransformV1", break_actor, "InTransform")
    break_component = add_form("break_component_baseline", "break_transform", 320, 2240); bp.connect(baseline_component, "CameraPlaybackNativeBaselineComponentRelativeTransformV1", break_component, "InTransform")
    body_rotator = add_form("body_rotator", "quat_rotator", 320, 1440); bp.connect(body, "CameraPlaybackNativeInputBodyWorldQuatV1", body_rotator, "Q")
    relative_rotator = add_form("relative_rotator", "quat_rotator", 320, 1600); bp.connect(relative, "CameraPlaybackNativeInputGimbalRelativeQuatV1", relative_rotator, "Q")
    desired_actor = add_form("desired_actor", "make_transform", 640, 1920)
    bp.connect(position, "CameraPlaybackNativeInputPositionV1", desired_actor, "Location"); bp.connect(body_rotator, "ReturnValue", desired_actor, "Rotation"); bp.connect(break_actor, "Scale", desired_actor, "Scale")
    desired_component = add_form("desired_component", "make_transform", 640, 2240)
    bp.connect(break_component, "Location", desired_component, "Location"); bp.connect(relative_rotator, "ReturnValue", desired_component, "Rotation"); bp.connect(break_component, "Scale", desired_component, "Scale")

    actor_set = add_form("actor_set", "actor_set", 928, 5440); bp.connect(camera_ref, "DroneCameraRef", actor_set, "self"); bp.connect(desired_actor, "ReturnValue", actor_set, "NewTransform"); scalar.set_default(actor_set, "bTeleport", "true")
    bp.connect(apply_guard, "then", actor_set, "execute")
    actor_guard = builder.add("actor_result_guard", "branch", 1152, 5440); bp.connect(actor_set, "then", actor_guard, "execute"); bp.connect(actor_set, "ReturnValue", actor_guard, "Condition")

    component_set = add_form("component_set", "actor_set", 1376, 5440)
    component_set.text = component_set.text.replace('MemberParent="/Script/CoreUObject.Class\'/Script/Engine.Actor\'",MemberName="K2_SetActorTransform"', 'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'",MemberName="K2_SetRelativeTransform"')
    component_set.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.Actor\'"', 'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'"', line, 1))
    remove_pin(component_set, "ReturnValue"); bp.connect(component, "DroneCamera", component_set, "self"); bp.connect(desired_component, "ReturnValue", component_set, "NewTransform"); scalar.set_default(component_set, "bTeleport", "true")
    bp.connect(actor_guard, "then", component_set, "execute")

    observed = add_form("observed_component", "actor_get", 960, 2720)
    observed.text = observed.text.replace('MemberParent="/Script/CoreUObject.Class\'/Script/Engine.Actor\'",MemberName="GetTransform"', 'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'",MemberName="GetRelativeTransform"')
    observed.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.Actor\'"', 'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'"', line, 1)); bp.connect(component, "DroneCamera", observed, "self")
    break_observed = add_form("break_observed", "break_transform", 1216, 2720); bp.connect(observed, "ReturnValue", break_observed, "InTransform")
    observed_quat = add_form("observed_quat", "rotator_quat", 1472, 2720); bp.connect(break_observed, "Rotation", observed_quat, "InRot")
    actual_break = add_form("break_actual", "break_quat", 1728, 2720); bp.connect(observed_quat, "ReturnValue", actual_break, "InQuat")
    expected_break = add_form("break_expected", "break_quat", 1728, 3360); bp.connect(relative, "CameraPlaybackNativeInputGimbalRelativeQuatV1", expected_break, "InQuat")
    direct, antipodal = [], []
    for index, axis in enumerate("XYZW"):
        y = 4000 + index * 256
        delta = builder.add(f"delta_{axis}", "math", 1984, y); scalar.retarget_function(delta, "Subtract_DoubleDouble"); bp.connect(actual_break, axis, delta, "A"); bp.connect(expected_break, axis, delta, "B")
        total = builder.add(f"sum_{axis}", "math", 2688, y); scalar.retarget_function(total, "Add_DoubleDouble"); bp.connect(actual_break, axis, total, "A"); bp.connect(expected_break, axis, total, "B")
        direct.extend(((compare("GreaterEqual_DoubleDouble", delta, "ReturnValue", 2208, y - 48, "-0.000001"), "ReturnValue"), (compare("LessEqual_DoubleDouble", delta, "ReturnValue", 2432, y + 48, "0.000001"), "ReturnValue")))
        antipodal.extend(((compare("GreaterEqual_DoubleDouble", total, "ReturnValue", 2912, y - 48, "-0.000001"), "ReturnValue"), (compare("LessEqual_DoubleDouble", total, "ReturnValue", 3136, y + 48, "0.000001"), "ReturnValue")))
    direct_ready = combine("BooleanAND", direct, 3456, 4640); antipodal_ready = combine("BooleanAND", antipodal, 3456, 4864); pose_ready = combine("BooleanOR", (direct_ready, antipodal_ready), 5120, 4752)
    pose_guard = builder.add("pose_guard", "branch", 1600, 5440); bp.connect(component_set, "then", pose_guard, "execute"); bp.connect(*pose_ready, pose_guard, "Condition")

    engine_apply = self_call("ApplyCameraEngineFrameV1", 1824, 5440); bp.connect(pose_guard, "then", engine_apply, "execute")
    engine_result = get("CameraApplyResultValidV1", "bool", 5120, 5120)
    engine_guard = builder.add("engine_guard", "branch", 2048, 5440); bp.connect(engine_apply, "then", engine_guard, "execute"); bp.connect(engine_result, "CameraApplyResultValidV1", engine_guard, "Condition")
    restore = self_call("RestoreCameraPlaybackNativeStateV1", 2272, 5760)
    bp.connect(actor_guard, "else", restore, "execute"); bp.connect(pose_guard, "else", restore, "execute"); bp.connect(engine_guard, "else", restore, "execute")

    count = get("CameraPlaybackNativeAppliedFrameCountV1", "int", 5120, 5280)
    increment = add_form("increment", "add_int", 5344, 5280)
    for pin in ("A", "B", "ReturnValue"): pin_kind(increment, pin, "int")
    scalar.set_default(increment, "B", "1"); bp.connect(count, "CameraPlaybackNativeAppliedFrameCountV1", increment, "A")
    count_set = builder.add("set_count", "set", 2272, 5440); variable(count_set, "CameraPlaybackNativeAppliedFrameCountV1", "int"); bp.connect(increment, "ReturnValue", count_set, "CameraPlaybackNativeAppliedFrameCountV1")
    clear = set_value("CameraPlaybackNativeFailureCodeV1", "string", 2496, 5440, "")
    publish = set_value("CameraPlaybackNativeResultValidV1", "bool", 2720, 5440, "true")
    bp.connect(engine_guard, "then", count_set, "execute"); bp.connect(count_set, "then", clear, "execute"); bp.connect(clear, "then", publish, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
