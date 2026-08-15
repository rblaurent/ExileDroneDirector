"""Build one-shot verbatim native transform and engine baseline capture."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CaptureCameraPlaybackNativeStateV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
DRONE_CAMERA_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C'"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_native_capture_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "string": ("string", "", "None"),
        "transform": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Transform\'"'),
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
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/camera-engine-basic-node-forms.eddgraph")
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture, r'MemberName="DroneCameraRef"'),
        actor_transform=bp.find_block(capture, r'MemberName="GetTransform"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        self_call=bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
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
        scalar.retarget_variable(node, name, "vector" if kind == "transform" else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind)
        return node

    def set_value(name: str, kind: str, x: int, y: int, *, source=None, source_pin=None, default=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if source is not None:
            bp.connect(source, source_pin, node, name)
        else:
            scalar.set_default(node, name, default)
        return node

    preflight = get("CameraPlaybackNativePreflightValidV1", "bool", 0, 0)
    preflight_guard = builder.add("preflight_guard", "branch", 256, 1440)
    bp.connect(builder.entry, "then", preflight_guard, "execute")
    bp.connect(preflight, "CameraPlaybackNativePreflightValidV1", preflight_guard, "Condition")
    active = get("CameraPlaybackNativeSessionActiveV1", "bool", 0, 160)
    active_guard = builder.add("active_guard", "branch", 480, 1440)
    bp.connect(preflight_guard, "then", active_guard, "execute")
    bp.connect(active, "CameraPlaybackNativeSessionActiveV1", active_guard, "Condition")

    failure = set_value("CameraPlaybackNativeFailureCodeV1", "string", 704, 1440, default="native_capture_failed")
    engine_capture = add_form("engine_capture", "self_call", 928, 1440)
    engine_capture.text = re.sub(
        r"FunctionReference=\([^\n]*\)",
        'FunctionReference=(MemberName="CaptureCameraEngineStateV1",bSelfContext=True)',
        engine_capture.text,
        1,
    )
    engine_capture.mutate_pin(
        "self",
        lambda line: re.sub(
            r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
            f"PinType.PinSubCategoryObject={TARGET}",
            line,
            1,
        ),
    )
    bp.connect(active_guard, "else", failure, "execute")
    bp.connect(failure, "then", engine_capture, "execute")

    engine_stage = get("CameraApplyScratchStageValidV1", "bool", 0, 480)
    engine_active = get("CameraApplySessionActiveV1", "bool", 0, 640)
    ready = builder.add("engine_ready", "compare", 320, 560)
    scalar.retarget_function(ready, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(ready, pin, "bool")
    bp.connect(engine_stage, "CameraApplyScratchStageValidV1", ready, "A")
    bp.connect(engine_active, "CameraApplySessionActiveV1", ready, "B")
    engine_guard = builder.add("engine_guard", "branch", 1152, 1440)
    bp.connect(engine_capture, "then", engine_guard, "execute")
    bp.connect(ready, "ReturnValue", engine_guard, "Condition")

    camera_ref = add_form("camera_ref", "camera_ref", 0, 880)
    actor_transform = add_form("actor_transform", "actor_transform", 320, 880)
    bp.connect(camera_ref, "DroneCameraRef", actor_transform, "self")
    component = add_form("component", "component", 320, 1040)
    internal = 'VariableReference=(MemberName="DroneCamera",bSelfContext=True)'
    external = f'VariableReference=(MemberParent="{DRONE_CAMERA_CLASS}",MemberName="DroneCamera")'
    if component.text.count(internal) != 1:
        raise RuntimeError("native DroneCamera component form is not the reviewed internal-owner shape")
    component.text = component.text.replace(internal, external)
    bp.connect(camera_ref, "DroneCameraRef", component, "self")
    component_transform = add_form("component_relative_transform", "actor_transform", 576, 1040)
    component_transform.text = component_transform.text.replace(
        'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.Actor\'",MemberName="GetTransform"',
        'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'",MemberName="GetRelativeTransform"',
    )
    component_transform.mutate_pin(
        "self",
        lambda line: re.sub(
            r'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.Actor\'"',
            'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.SceneComponent\'"',
            line,
            1,
        ),
    )
    component_transform.mutate_pin(
        "ReturnValue",
        lambda line: line.replace("PinType.bIsReference=True", "PinType.bIsReference=False").replace(
            "PinType.bIsConst=True", "PinType.bIsConst=False"
        ),
    )
    bp.connect(component, "DroneCamera", component_transform, "self")

    baseline_actor = set_value(
        "CameraPlaybackNativeBaselineActorTransformV1", "transform", 1376, 1440,
        source=actor_transform, source_pin="ReturnValue",
    )
    baseline_component = set_value(
        "CameraPlaybackNativeBaselineComponentRelativeTransformV1", "transform", 1600, 1440,
        source=component_transform, source_pin="ReturnValue",
    )
    count = set_value("CameraPlaybackNativeAppliedFrameCountV1", "int", 1824, 1440, default="0")
    clear = set_value("CameraPlaybackNativeFailureCodeV1", "string", 2048, 1440, default="")
    activate = set_value("CameraPlaybackNativeSessionActiveV1", "bool", 2272, 1440, default="true")
    bp.connect(engine_guard, "then", baseline_actor, "execute")
    bp.connect(baseline_actor, "then", baseline_component, "execute")
    bp.connect(baseline_component, "then", count, "execute")
    bp.connect(count, "then", clear, "execute")
    bp.connect(clear, "then", activate, "execute")

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
