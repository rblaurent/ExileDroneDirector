"""Build exact whole-struct restoration of the captured viewer camera state."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "RestoreCameraEngineStateV1"
DRONE_CAMERA_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C'"
STRUCTS = {
    "filmback": "/Script/CinematicCamera.CameraFilmbackSettings",
    "focus": "/Script/CinematicCamera.CameraFocusSettings",
    "post_process": "/Script/Engine.PostProcessSettings",
}


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_engine_restore_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    capture_live = bp.read_blocks(args.project_root / "tools/blueprint/snippets/capture-current-waypoint.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/camera-engine-basic-node-forms.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture, r'MemberName="DroneCameraRef"'),
        is_valid=bp.find_block(capture_live, r'MemberName="IsValid"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        filmback_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="Filmback"'),
        focus_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="FocusSettings"'),
        post_process_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="PostProcessSettings"'),
        focal_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="CurrentFocalLength"'),
        aperture_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="CurrentAperture"'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        raw = forms[form]
        match = bp.BLOCK_RE.match(raw)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, raw, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def external_component(node):
        internal = 'VariableReference=(MemberName="DroneCamera",bSelfContext=True)'
        external = f'VariableReference=(MemberParent="{DRONE_CAMERA_CLASS}",MemberName="DroneCamera")'
        if node.text.count(internal) != 1:
            raise RuntimeError("native DroneCamera component form is not the reviewed internal-owner shape")
        node.text = node.text.replace(internal, external)
        return node

    def pin_type(node, pin: str, kind: str, *, array: bool = False) -> None:
        category, subcategory, object_name = {
            "bool": ("bool", "", None), "int": ("int", "", None),
            "real": ("real", "double", None), "string": ("string", "", None),
            "filmback": ("struct", "", STRUCTS["filmback"]),
            "focus": ("struct", "", STRUCTS["focus"]),
            "post_process": ("struct", "", STRUCTS["post_process"]),
        }[kind]
        def mutate(line: str) -> str:
            line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
            line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
            replacement = "None" if object_name is None else f'"/Script/CoreUObject.ScriptStruct\'{object_name}\'"'
            line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={replacement}", line, 1)
            return re.sub(r"PinType.ContainerType=(?:None|Array)", f"PinType.ContainerType={'Array' if array else 'None'}", line, 1)
        node.mutate_pin(pin, mutate)

    def variable(node, name: str, kind: str, *, array: bool = False) -> None:
        scalar.retarget_variable(node, name, "vector" if kind in STRUCTS else ("real" if kind == "int" else kind))
        pin_type(node, name, kind, array=array)
        if "Output_Get" in node.pins:
            pin_type(node, "Output_Get", kind, array=array)

    def get(name: str, kind: str, x: int, y: int, *, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array=array)
        return node

    def set_value(name: str, kind: str, x: int, y: int, default: str | None = None, *, array: bool = False):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind, array=array)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    camera_ref = add_form("camera_ref", "camera_ref", 0, 0)
    valid = add_form("camera_valid", "is_valid", 256, 0)
    bp.connect(camera_ref, "DroneCameraRef", valid, "Object")
    active = get("CameraApplySessionActiveV1", "bool", 0, 160)
    active_guard = builder.add("active_guard", "branch", 256, 2240)
    bp.connect(builder.entry, "then", active_guard, "execute")
    bp.connect(active, "CameraApplySessionActiveV1", active_guard, "Condition")

    baseline_values = get("CameraApplyBaselineTargetValuesV1", "real", 0, 320, array=True)
    length = add_form("baseline_length", "length", 256, 320)
    pin_type(length, "TargetArray", "real", array=True)
    pin_type(length, "ReturnValue", "int")
    bp.connect(baseline_values, "CameraApplyBaselineTargetValuesV1", length, "TargetArray")
    shape = builder.add("shape", "compare", 512, 320)
    scalar.retarget_function(shape, "EqualEqual_IntInt")
    for pin in ("A", "B"):
        pin_type(shape, pin, "int")
    pin_type(shape, "ReturnValue", "bool")
    scalar.set_default(shape, "B", "15")
    bp.connect(length, "ReturnValue", shape, "A")
    ready = builder.add("ready", "compare", 768, 320)
    scalar.retarget_function(ready, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"):
        pin_type(ready, pin, "bool")
    bp.connect(valid, "ReturnValue", ready, "A")
    bp.connect(shape, "ReturnValue", ready, "B")
    restore_guard = builder.add("restore_guard", "branch", 512, 2240)
    bp.connect(active_guard, "then", restore_guard, "execute")
    bp.connect(ready, "ReturnValue", restore_guard, "Condition")
    failure = set_value("CameraApplyFailureCodeV1", "string", 768, 2480, "restore_preflight_failed")
    bp.connect(restore_guard, "else", failure, "execute")

    component = external_component(add_form("component", "component", 256, 640))
    bp.connect(camera_ref, "DroneCameraRef", component, "self")
    baseline_filmback = get("CameraApplyBaselineFilmbackSettingsV1", "filmback", 512, 640)
    baseline_focus = get("CameraApplyBaselineFocusSettingsV1", "focus", 512, 800)
    baseline_post = get("CameraApplyBaselinePostProcessSettingsV1", "post_process", 512, 960)
    baseline_id = get("CameraApplyBaselineFilmbackPresetIdV1", "string", 512, 1120)
    focal_item = add_form("focal_item", "item", 768, 1280)
    aperture_item = add_form("aperture_item", "item", 768, 1440)
    for node, index in ((focal_item, 2), (aperture_item, 3)):
        pin_type(node, "Array", "real", array=True)
        pin_type(node, "Output", "real")
        scalar.set_default(node, "Dimension 1", str(index))
        bp.connect(baseline_values, "CameraApplyBaselineTargetValuesV1", node, "Array")

    filmback_set = add_form("filmback_set", "filmback_set", 768, 2240)
    focal_set = add_form("focal_set", "focal_set", 992, 2240)
    aperture_set = add_form("aperture_set", "aperture_set", 1216, 2240)
    focus_set = add_form("focus_set", "focus_set", 1440, 2240)
    post_set = add_form("post_set", "post_process_set", 1664, 2240)
    for node in (filmback_set, focal_set, aperture_set, focus_set, post_set):
        bp.connect(component, "DroneCamera", node, "self")
    bp.connect(baseline_filmback, "CameraApplyBaselineFilmbackSettingsV1", filmback_set, "Filmback")
    bp.connect(focal_item, "Output", focal_set, "CurrentFocalLength")
    bp.connect(aperture_item, "Output", aperture_set, "CurrentAperture")
    bp.connect(baseline_focus, "CameraApplyBaselineFocusSettingsV1", focus_set, "FocusSettings")
    bp.connect(baseline_post, "CameraApplyBaselinePostProcessSettingsV1", post_set, "PostProcessSettings")
    bp.connect(restore_guard, "then", filmback_set, "execute")
    for left, right in zip((filmback_set, focal_set, aperture_set, focus_set), (focal_set, aperture_set, focus_set, post_set)):
        bp.connect(left, "then", right, "execute")

    current_id = set_value("CameraApplyCurrentFilmbackPresetIdV1", "string", 1888, 2240)
    current_values = set_value("CameraApplyCurrentTargetValuesV1", "real", 2112, 2240, array=True)
    deactivate = set_value("CameraApplySessionActiveV1", "bool", 2336, 2240, "false")
    clear_failure = set_value("CameraApplyFailureCodeV1", "string", 2560, 2240, "")
    publish = set_value("CameraApplyResultValidV1", "bool", 2784, 2240, "true")
    bp.connect(baseline_id, "CameraApplyBaselineFilmbackPresetIdV1", current_id, "CameraApplyCurrentFilmbackPresetIdV1")
    bp.connect(baseline_values, "CameraApplyBaselineTargetValuesV1", current_values, "CameraApplyCurrentTargetValuesV1")
    bp.connect(post_set, "then", current_id, "execute")
    bp.connect(current_id, "then", current_values, "execute")
    bp.connect(current_values, "then", deactivate, "execute")
    bp.connect(deactivate, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", publish, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text) for node in builder.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
