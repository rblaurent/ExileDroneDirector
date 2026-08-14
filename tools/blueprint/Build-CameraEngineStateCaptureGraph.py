"""Build one-shot native camera-state capture for an application session."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CaptureCameraEngineStateV1"
STRUCTS = {
    "filmback": "/Script/CinematicCamera.CameraFilmbackSettings",
    "focus": "/Script/CinematicCamera.CameraFocusSettings",
    "post_process": "/Script/Engine.PostProcessSettings",
}


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_engine_capture_base", path)
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
    capture_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    capture_live = bp.read_blocks(args.project_root / "tools/blueprint/snippets/capture-current-waypoint.eddgraph")
    sync_forms = bp.read_blocks(args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph")
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/camera-engine-basic-node-forms.eddgraph")
    structs = bp.read_blocks(args.project_root / "tools/blueprint/templates/camera-engine-struct-node-forms.eddgraph")
    forms.update(
        camera_ref=bp.find_block(capture_forms, r'MemberName="DroneCameraRef"'),
        is_valid=bp.find_block(capture_live, r'MemberName="IsValid"'),
        clear=bp.find_block(sync_forms, r'MemberName="Array_Clear"'),
        add=bp.find_block(capture_forms, r'MemberName="Array_Add"'),
        component=bp.find_block(native, r'MemberName="DroneCamera"'),
        filmback_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="Filmback"'),
        focus_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="FocusSettings"'),
        post_process_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="PostProcessSettings"'),
        focal_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="CurrentFocalLength"'),
        aperture_get=bp.find_block(native, r'K2Node_VariableGet.*MemberName="CurrentAperture"'),
        filmback_break=bp.find_block(structs, r'K2Node_BreakStruct.*CameraFilmbackSettings'),
        focus_break=bp.find_block(structs, r'K2Node_BreakStruct.*CameraFocusSettings'),
        post_process_break=bp.find_block(structs, r'K2Node_BreakStruct.*PostProcessSettings'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        raw = forms[form]
        match = bp.BLOCK_RE.match(raw)
        node_class = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(node_class, 0)
        builder.serial[node_class] = index + 1
        node = bp.Node.clone(key, raw, f"{node_class}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def pin_type(node, pin: str, kind: str, *, array: bool = False) -> None:
        category, subcategory, object_name = {
            "bool": ("bool", "", None),
            "int": ("int", "", None),
            "real": ("real", "double", None),
            "string": ("string", "", None),
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
    camera_guard = builder.add("camera_guard", "branch", 512, 2720)
    bp.connect(builder.entry, "then", camera_guard, "execute")
    bp.connect(valid, "ReturnValue", camera_guard, "Condition")
    failure = set_value("CameraApplyScratchStageValidV1", "bool", 768, 2944, "false")
    failure_code = set_value("CameraApplyFailureCodeV1", "string", 992, 2944, "camera_invalid")
    bp.connect(camera_guard, "else", failure, "execute")
    bp.connect(failure, "then", failure_code, "execute")

    active = get("CameraApplySessionActiveV1", "bool", 512, 2400)
    active_guard = builder.add("active_guard", "branch", 768, 2720)
    bp.connect(camera_guard, "then", active_guard, "execute")
    bp.connect(active, "CameraApplySessionActiveV1", active_guard, "Condition")

    component = add_form("component", "component", 256, 320)
    bp.connect(camera_ref, "DroneCameraRef", component, "self")
    filmback = add_form("filmback", "filmback_get", 512, 320)
    focus = add_form("focus", "focus_get", 512, 640)
    post_process = add_form("post_process", "post_process_get", 512, 960)
    focal = add_form("focal", "focal_get", 512, 1280)
    aperture = add_form("aperture", "aperture_get", 512, 1440)
    for node in (filmback, focus, post_process, focal, aperture):
        bp.connect(component, "DroneCamera", node, "self")
    break_filmback = add_form("break_filmback", "filmback_break", 768, 320)
    break_focus = add_form("break_focus", "focus_break", 768, 640)
    break_post_process = add_form("break_post_process", "post_process_break", 768, 960)
    bp.connect(filmback, "Filmback", break_filmback, "CameraFilmbackSettings")
    bp.connect(focus, "FocusSettings", break_focus, "CameraFocusSettings")
    bp.connect(post_process, "PostProcessSettings", break_post_process, "PostProcessSettings")

    baseline_values = get("CameraApplyBaselineTargetValuesV1", "real", 1024, 0, array=True)
    clear = add_form("clear_baseline", "clear", 1024, 2720)
    pin_type(clear, "TargetArray", "real", array=True)
    bp.connect(baseline_values, "CameraApplyBaselineTargetValuesV1", clear, "TargetArray")
    bp.connect(active_guard, "else", clear, "execute")

    struct_sets = []
    for index, (name, kind, source, source_pin) in enumerate((
        ("CameraApplyBaselineFilmbackSettingsV1", "filmback", filmback, "Filmback"),
        ("CameraApplyBaselineFocusSettingsV1", "focus", focus, "FocusSettings"),
        ("CameraApplyBaselinePostProcessSettingsV1", "post_process", post_process, "PostProcessSettings"),
    )):
        setter = set_value(name, kind, 1248 + index * 224, 2720)
        bp.connect(source, source_pin, setter, name)
        struct_sets.append(setter)
    bp.connect(clear, "then", struct_sets[0], "execute")
    for left, right in zip(struct_sets, struct_sets[1:]):
        bp.connect(left, "then", right, "execute")

    values = (
        (break_filmback, "SensorWidth", None), (break_filmback, "SensorHeight", None),
        (focal, "CurrentFocalLength", None), (aperture, "CurrentAperture", None),
        (break_focus, "ManualFocusDistance", None), (None, None, "1.0"),
        (break_post_process, "AutoExposureBias", None), (break_post_process, "BloomIntensity", None),
        (break_post_process, "VignetteIntensity", None), (None, None, "0.0"),
        (None, None, "0.0"), (break_post_process, "MotionBlurAmount", None),
        (break_post_process, "SceneFringeIntensity", None), (None, None, "0.0"), (None, None, "0.0"),
    )
    adds = []
    for index, (source, source_pin, default) in enumerate(values):
        node = add_form(f"add_{index}", "add", 1920 + index * 224, 2720)
        pin_type(node, "TargetArray", "real", array=True)
        pin_type(node, "NewItem", "real")
        pin_type(node, "ReturnValue", "int")
        bp.connect(baseline_values, "CameraApplyBaselineTargetValuesV1", node, "TargetArray")
        if source is None:
            scalar.set_default(node, "NewItem", default)
        else:
            bp.connect(source, source_pin, node, "NewItem")
        adds.append(node)
    bp.connect(struct_sets[-1], "then", adds[0], "execute")
    for left, right in zip(adds, adds[1:]):
        bp.connect(left, "then", right, "execute")

    baseline_id = set_value("CameraApplyBaselineFilmbackPresetIdV1", "string", 5280, 2720, "engine_native_baseline")
    current_values = set_value("CameraApplyCurrentTargetValuesV1", "real", 5504, 2720, array=True)
    current_id = set_value("CameraApplyCurrentFilmbackPresetIdV1", "string", 5728, 2720, "engine_native_baseline")
    activate = set_value("CameraApplySessionActiveV1", "bool", 5952, 2720, "true")
    bp.connect(baseline_values, "CameraApplyBaselineTargetValuesV1", current_values, "CameraApplyCurrentTargetValuesV1")
    bp.connect(adds[-1], "then", baseline_id, "execute")
    bp.connect(baseline_id, "then", current_values, "execute")
    bp.connect(current_values, "then", current_id, "execute")
    bp.connect(current_id, "then", activate, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text) for node in builder.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
