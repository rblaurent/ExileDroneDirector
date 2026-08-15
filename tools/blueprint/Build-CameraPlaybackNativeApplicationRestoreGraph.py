"""Build exact idempotent playback-native pose and engine restoration."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "RestoreCameraPlaybackNativeStateV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
DRONE_CAMERA_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C'"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_native_restore_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def pin_kind(node, pin_name: str, kind: str) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "transform": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Transform\'"'),
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", "PinType.ContainerType=None", line, 1)
    node.mutate_pin(pin_name, mutate)


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name); node.text = "\n".join(line for line in node.text.splitlines() if f"PinId={pin_id}" not in line)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path); args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    root = args.project_root / "tools/blueprint"
    capture = bp.read_blocks(root / "templates/waypoint-capture-node-forms.eddgraph")
    capture_live = bp.read_blocks(root / "snippets/capture-current-waypoint.eddgraph")
    native = bp.read_blocks(root / "templates/camera-engine-basic-node-forms.eddgraph")
    linear = bp.read_blocks(root / "templates/linear-playback-node-forms.eddgraph")
    calls = bp.read_blocks(root / "snippets/activate-drone-view.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture, r'MemberName="DroneCameraRef"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        is_valid=bp.find_block(capture_live, r'MemberName="IsValid"'),
        actor_set=bp.find_block(linear, r'MemberName="K2_SetActorTransform"'),
        self_call=bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)
    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]; index = builder.serial.get(cls, 0); builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y); builder.nodes.append(node); return node
    def variable(node, name, kind):
        scalar.retarget_variable(node, name, "vector" if kind == "transform" else kind); pin_kind(node, name, kind)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)
    def get(name, kind, x, y):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y); variable(node, name, kind); return node
    def set_bool(name, x, y, value):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y); variable(node, name, "bool"); scalar.set_default(node, name, value); return node
    def self_call(name, x, y):
        node = add_form(f"call_{name}_{len(builder.nodes)}", "self_call", x, y); node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET}", line, 1)); return node
    def bool_compare(left, left_pin, default, x, y):
        node = builder.add(f"bool_equal_{len(builder.nodes)}", "compare", x, y); scalar.retarget_function(node, "EqualEqual_BoolBool")
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A"); scalar.set_default(node, "B", default); return node
    def bool_and(left, left_pin, right, right_pin, x, y):
        node = builder.add(f"and_{len(builder.nodes)}", "compare", x, y); scalar.retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A"); bp.connect(right, right_pin, node, "B"); return node

    active = get("CameraPlaybackNativeSessionActiveV1", "bool", 0, 0)
    active_guard = builder.add("active_guard", "branch", 256, 1760); bp.connect(builder.entry, "then", active_guard, "execute"); bp.connect(active, "CameraPlaybackNativeSessionActiveV1", active_guard, "Condition")
    invalidate = set_bool("CameraPlaybackNativeResultValidV1", 480, 1760, "false"); bp.connect(active_guard, "then", invalidate, "execute")
    camera_ref = add_form("camera_ref", "camera_ref", 0, 320)
    component = add_form("component", "component", 256, 480)
    internal = 'VariableReference=(MemberName="DroneCamera",bSelfContext=True)'; external = f'VariableReference=(MemberParent="{DRONE_CAMERA_CLASS}",MemberName="DroneCamera")'
    if component.text.count(internal) != 1: raise RuntimeError("unexpected component owner")
    component.text = component.text.replace(internal, external); bp.connect(camera_ref, "DroneCameraRef", component, "self")
    actor_valid = add_form("actor_valid", "is_valid", 256, 320); component_valid = add_form("component_valid", "is_valid", 512, 480)
    bp.connect(camera_ref, "DroneCameraRef", actor_valid, "Object"); bp.connect(component, "DroneCamera", component_valid, "Object")
    ready = bool_and(actor_valid, "ReturnValue", component_valid, "ReturnValue", 768, 400)
    restore_guard = builder.add("restore_guard", "branch", 704, 1760); bp.connect(invalidate, "then", restore_guard, "execute"); bp.connect(ready, "ReturnValue", restore_guard, "Condition")
    baseline_actor = get("CameraPlaybackNativeBaselineActorTransformV1", "transform", 0, 800)
    baseline_component = get("CameraPlaybackNativeBaselineComponentRelativeTransformV1", "transform", 0, 960)
    actor_set = add_form("actor_set", "actor_set", 928, 1760); bp.connect(camera_ref, "DroneCameraRef", actor_set, "self"); bp.connect(baseline_actor, "CameraPlaybackNativeBaselineActorTransformV1", actor_set, "NewTransform"); scalar.set_default(actor_set, "bTeleport", "true"); bp.connect(restore_guard, "then", actor_set, "execute")
    actor_guard = builder.add("actor_guard", "branch", 1152, 1760); bp.connect(actor_set, "then", actor_guard, "execute"); bp.connect(actor_set, "ReturnValue", actor_guard, "Condition")
    component_set = add_form("component_set", "actor_set", 1376, 1760)
    component_set.text = component_set.text.replace('MemberParent="/Script/CoreUObject.Class\'/Script/Engine.Actor\'",MemberName="K2_SetActorTransform"', 'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'",MemberName="K2_SetRelativeTransform"')
    component_set.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.Actor\'"', 'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'"', line, 1)); remove_pin(component_set, "ReturnValue")
    bp.connect(component, "DroneCamera", component_set, "self"); bp.connect(baseline_component, "CameraPlaybackNativeBaselineComponentRelativeTransformV1", component_set, "NewTransform"); scalar.set_default(component_set, "bTeleport", "true"); bp.connect(actor_guard, "then", component_set, "execute")
    engine_reset = self_call("ResetCameraEngineApplicationResultV1", 1600, 1760); engine_restore = self_call("RestoreCameraEngineStateV1", 1824, 1760)
    bp.connect(component_set, "then", engine_reset, "execute"); bp.connect(engine_reset, "then", engine_restore, "execute")
    engine_result = get("CameraApplyResultValidV1", "bool", 1152, 1280); engine_active = get("CameraApplySessionActiveV1", "bool", 1152, 1440)
    engine_inactive = bool_compare(engine_active, "CameraApplySessionActiveV1", "false", 1408, 1440); restored = bool_and(engine_result, "CameraApplyResultValidV1", engine_inactive, "ReturnValue", 1632, 1360)
    engine_guard = builder.add("engine_guard", "branch", 2048, 1760); bp.connect(engine_restore, "then", engine_guard, "execute"); bp.connect(restored, "ReturnValue", engine_guard, "Condition")
    deactivate = set_bool("CameraPlaybackNativeSessionActiveV1", 2272, 1760, "false"); bp.connect(engine_guard, "then", deactivate, "execute")
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
