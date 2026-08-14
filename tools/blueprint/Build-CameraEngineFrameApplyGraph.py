"""Build preflighted writes of one staged frame to the native Cine Camera."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ApplyCameraEngineFrameV1"
TARGET_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C'"
DRONE_CAMERA_CLASS = "/Script/Engine.BlueprintGeneratedClass'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C'"
STRUCTS = {
    "filmback": "/Script/CinematicCamera.CameraFilmbackSettings",
    "focus": "/Script/CinematicCamera.CameraFocusSettings",
    "post_process": "/Script/Engine.PostProcessSettings",
}


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_engine_apply_base", path)
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
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/camera-engine-basic-node-forms.eddgraph")
    structs = bp.read_blocks(args.project_root / "tools/blueprint/templates/camera-engine-struct-node-forms.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture, r'MemberName="DroneCameraRef"'),
        is_valid=bp.find_block(capture_live, r'MemberName="IsValid"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        add_int=bp.find_block(capture, r'MemberName="Add_IntInt"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        filmback_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="Filmback"'),
        focus_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="FocusSettings"'),
        post_process_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="PostProcessSettings"'),
        filmback_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="Filmback"'),
        focus_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="FocusSettings"'),
        post_process_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="PostProcessSettings"'),
        focal_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="CurrentFocalLength"'),
        aperture_set=bp.find_block(native, r'K2Node_VariableSet.*MemberName="CurrentAperture"'),
        filmback_members=bp.find_block(structs, r'K2Node_SetFieldsInStruct.*CameraFilmbackSettings'),
        focus_members=bp.find_block(structs, r'K2Node_SetFieldsInStruct.*CameraFocusSettings'),
        post_process_members=bp.find_block(structs, r'K2Node_SetFieldsInStruct.*PostProcessSettings'),
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

    def item(source, index: int, x: int, y: int):
        node = add_form(f"item_{index}", "item", x, y)
        pin_type(node, "Array", "real", array=True)
        pin_type(node, "Output", "real")
        scalar.set_default(node, "Dimension 1", str(index))
        bp.connect(source, "CameraApplyInputTargetValuesV1", node, "Array")
        return node

    def compare(left, default: str, x: int, y: int):
        node = builder.add(f"equal_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, "EqualEqual_DoubleDouble")
        for pin in ("A", "B"):
            pin_type(node, pin, "real")
        pin_type(node, "ReturnValue", "bool")
        bp.connect(left, "Output", node, "A")
        scalar.set_default(node, "B", default)
        return node

    def bool_and(left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = builder.add(f"and_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"):
            pin_type(node, pin, "bool")
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    camera_ref = add_form("camera_ref", "camera_ref", 0, 0)
    valid = add_form("camera_valid", "is_valid", 256, 0)
    bp.connect(camera_ref, "DroneCameraRef", valid, "Object")
    active = get("CameraApplySessionActiveV1", "bool", 0, 160)
    staged = get("CameraApplyScratchStageValidV1", "bool", 0, 320)
    values = get("CameraApplyInputTargetValuesV1", "real", 0, 480, array=True)
    items = [item(values, index, 256 + index * 208, 800) for index in range(15)]
    neutral = {5: "1.0", 9: "0.0", 10: "0.0", 13: "0.0", 14: "0.0"}
    conditions = [valid, active, staged, *(compare(items[index], value, 256 + index * 208, 1040) for index, value in neutral.items())]
    pins = ["ReturnValue", "CameraApplySessionActiveV1", "CameraApplyScratchStageValidV1", *("ReturnValue" for _ in neutral)]
    current, current_pin = conditions[0], pins[0]
    for index, (condition, condition_pin) in enumerate(zip(conditions[1:], pins[1:])):
        current = bool_and(current, current_pin, condition, condition_pin, 1536 + index * 208, 1200)
        current_pin = "ReturnValue"
    guard = builder.add("apply_guard", "branch", 3328, 2880)
    bp.connect(builder.entry, "then", guard, "execute")
    bp.connect(current, current_pin, guard, "Condition")
    failure = set_value("CameraApplyFailureCodeV1", "string", 3552, 3136, "application_preflight_failed")
    bp.connect(guard, "else", failure, "execute")

    component = external_component(add_form("component", "component", 256, 1440))
    bp.connect(camera_ref, "DroneCameraRef", component, "self")
    filmback_get = add_form("filmback_get", "filmback_get", 512, 1440)
    focus_get = add_form("focus_get", "focus_get", 512, 1600)
    post_get = add_form("post_get", "post_process_get", 512, 1760)
    for node in (filmback_get, focus_get, post_get):
        bp.connect(component, "DroneCamera", node, "self")

    scratch_filmback_set = set_value("CameraApplyScratchFilmbackSettingsV1", "filmback", 3552, 2880)
    scratch_filmback_get = get("CameraApplyScratchFilmbackSettingsV1", "filmback", 3552, 2400)
    filmback_members = add_form("filmback_members", "filmback_members", 3776, 2880)
    bp.connect(filmback_get, "Filmback", scratch_filmback_set, "CameraApplyScratchFilmbackSettingsV1")
    bp.connect(scratch_filmback_get, "CameraApplyScratchFilmbackSettingsV1", filmback_members, "StructRef")
    bp.connect(items[0], "Output", filmback_members, "SensorWidth")
    bp.connect(items[1], "Output", filmback_members, "SensorHeight")
    filmback_set = add_form("filmback_set", "filmback_set", 4000, 2880)
    bp.connect(component, "DroneCamera", filmback_set, "self")
    bp.connect(filmback_members, "StructOut", filmback_set, "Filmback")
    bp.connect(guard, "then", scratch_filmback_set, "execute")
    bp.connect(scratch_filmback_set, "then", filmback_members, "execute")
    bp.connect(filmback_members, "then", filmback_set, "execute")

    focal_set = add_form("focal_set", "focal_set", 4224, 2880)
    aperture_set = add_form("aperture_set", "aperture_set", 4448, 2880)
    for node in (focal_set, aperture_set):
        bp.connect(component, "DroneCamera", node, "self")
    bp.connect(items[2], "Output", focal_set, "CurrentFocalLength")
    bp.connect(items[3], "Output", aperture_set, "CurrentAperture")
    bp.connect(filmback_set, "then", focal_set, "execute")
    bp.connect(focal_set, "then", aperture_set, "execute")

    scratch_focus_set = set_value("CameraApplyScratchFocusSettingsV1", "focus", 4672, 2880)
    scratch_focus_get = get("CameraApplyScratchFocusSettingsV1", "focus", 4672, 2400)
    focus_members = add_form("focus_members", "focus_members", 4896, 2880)
    focus_set = add_form("focus_set", "focus_set", 5120, 2880)
    bp.connect(focus_get, "FocusSettings", scratch_focus_set, "CameraApplyScratchFocusSettingsV1")
    bp.connect(scratch_focus_get, "CameraApplyScratchFocusSettingsV1", focus_members, "StructRef")
    bp.connect(items[4], "Output", focus_members, "ManualFocusDistance")
    bp.connect(component, "DroneCamera", focus_set, "self")
    bp.connect(focus_members, "StructOut", focus_set, "FocusSettings")
    bp.connect(aperture_set, "then", scratch_focus_set, "execute")
    bp.connect(scratch_focus_set, "then", focus_members, "execute")
    bp.connect(focus_members, "then", focus_set, "execute")

    scratch_post_set = set_value("CameraApplyScratchPostProcessSettingsV1", "post_process", 5344, 2880)
    scratch_post_get = get("CameraApplyScratchPostProcessSettingsV1", "post_process", 5344, 2400)
    post_members = add_form("post_members", "post_process_members", 5568, 2880)
    post_set = add_form("post_set", "post_process_set", 5792, 2880)
    bp.connect(post_get, "PostProcessSettings", scratch_post_set, "CameraApplyScratchPostProcessSettingsV1")
    bp.connect(scratch_post_get, "CameraApplyScratchPostProcessSettingsV1", post_members, "StructRef")
    for index, pin in ((6, "AutoExposureBias"), (7, "BloomIntensity"), (8, "VignetteIntensity"), (11, "MotionBlurAmount"), (12, "SceneFringeIntensity")):
        bp.connect(items[index], "Output", post_members, pin)
    bp.connect(component, "DroneCamera", post_set, "self")
    bp.connect(post_members, "StructOut", post_set, "PostProcessSettings")
    bp.connect(focus_set, "then", scratch_post_set, "execute")
    bp.connect(scratch_post_set, "then", post_members, "execute")
    bp.connect(post_members, "then", post_set, "execute")

    input_id = get("CameraApplyInputFilmbackPresetIdV1", "string", 5792, 2240)
    current_id = set_value("CameraApplyCurrentFilmbackPresetIdV1", "string", 6016, 2880)
    current_values = set_value("CameraApplyCurrentTargetValuesV1", "real", 6240, 2880, array=True)
    count = get("CameraApplyAppliedFrameCountV1", "int", 6240, 2240)
    increment = add_form("increment", "add_int", 6464, 2400)
    for pin in ("A", "B", "ReturnValue"):
        pin_type(increment, pin, "int")
    scalar.set_default(increment, "B", "1")
    bp.connect(count, "CameraApplyAppliedFrameCountV1", increment, "A")
    count_set = set_value("CameraApplyAppliedFrameCountV1", "int", 6464, 2880)
    publish = set_value("CameraApplyResultValidV1", "bool", 6688, 2880, "true")
    bp.connect(input_id, "CameraApplyInputFilmbackPresetIdV1", current_id, "CameraApplyCurrentFilmbackPresetIdV1")
    bp.connect(values, "CameraApplyInputTargetValuesV1", current_values, "CameraApplyCurrentTargetValuesV1")
    bp.connect(increment, "ReturnValue", count_set, "CameraApplyAppliedFrameCountV1")
    bp.connect(post_set, "then", current_id, "execute")
    bp.connect(current_id, "then", current_values, "execute")
    bp.connect(current_values, "then", count_set, "execute")
    bp.connect(count_set, "then", publish, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text) for node in builder.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
