"""Build the thirteen-value viewer-comfort camera candidate."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCameraViewerComfortChannelsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_comfort_channels_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def pin_kind(node, pin: str, kind: str, array: bool = False):
    category, subcategory = {"bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double")}[kind]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path); args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    forms.update(foreach=bp.find_block(sync, r"K2Node_MacroInstance"), length=bp.find_block(edit, r'MemberName="Array_Length"'),
                 item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
                 select=bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
                 array_add=bp.find_block(capture, r'MemberName="Array_Add"'), array_clear=bp.find_block(reset, r'MemberName="Array_Clear"'))
    b = scalar.Builder(bp, forms, FUNCTION)
    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]; index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind); pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind, array)
    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind, array); return node
    def set_(name, kind, x, y, default):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind); scalar.set_default(node, name, default); return node
    def length(source, pin, x, y):
        node = add_form(f"length_{len(b.nodes)}", "length", x, y); pin_kind(node, "TargetArray", "real", True); pin_kind(node, "ReturnValue", "int"); bp.connect(source, pin, node, "TargetArray"); return node
    def item(source, pin, index_source, index_pin, x, y, default_index=None):
        node = add_form(f"item_{len(b.nodes)}", "item", x, y); pin_kind(node, "Array", "real", True); pin_kind(node, "Output", "real"); bp.connect(source, pin, node, "Array")
        if index_source is None: scalar.set_default(node, "Dimension 1", default_index)
        else: bp.connect(index_source, index_pin, node, "Dimension 1")
        return node
    def compare(member, source, source_pin, default, x, y):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): pin_kind(node, pin, "int")
        pin_kind(node, "ReturnValue", "bool"); bp.connect(source, source_pin, node, "A"); scalar.set_default(node, "B", default); return node
    def bool_op(member, left, left_pin, right, right_pin, x, y):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A"); bp.connect(right, right_pin, node, "B"); return node
    def select(condition, false_source, false_pin, true_source, true_pin, x, y, false_default=None):
        node = b.add(f"select_{len(b.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"): pin_kind(node, pin, "real")
        pin_kind(node, "Index", "bool"); bp.connect(condition, "ReturnValue", node, "Index")
        if false_source is None: scalar.set_default(node, "Option 0", false_default)
        else: bp.connect(false_source, false_pin, node, "Option 0")
        bp.connect(true_source, true_pin, node, "Option 1"); return node
    def array_op(form, source, source_pin, x, y, value=None, value_pin=None):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y); pin_kind(node, "TargetArray", "real", True); bp.connect(source, source_pin, node, "TargetArray")
        if form == "array_add": pin_kind(node, "NewItem", "real"); pin_kind(node, "ReturnValue", "int"); bp.connect(value, value_pin, node, "NewItem")
        return node

    source_values = get("CameraComfortInputChannelValuesV1", "real", 0, 0, True)
    effective = get("CameraComfortCandidateEffectiveWeightsV1", "real", 0, 224, True)
    candidates = get("CameraComfortCandidateChannelValuesV1", "real", 0, 448, True)
    clear = array_op("array_clear", candidates, "CameraComfortCandidateChannelValuesV1", 256, 3000)
    invalidate = set_("CameraComfortCandidateValidV1", "bool", 480, 3000, "false")
    validation = get("CameraComfortValidationValidV1", "bool", 0, 672)
    source_length = length(source_values, "CameraComfortInputChannelValuesV1", 320, 0)
    effective_length = length(effective, "CameraComfortCandidateEffectiveWeightsV1", 320, 224)
    source_shape = compare("EqualEqual_IntInt", source_length, "ReturnValue", "13", 544, 0)
    effective_shape = compare("EqualEqual_IntInt", effective_length, "ReturnValue", "5", 544, 224)
    shape = bool_op("BooleanAND", source_shape, "ReturnValue", effective_shape, "ReturnValue", 768, 112)
    valid_shape = bool_op("BooleanAND", validation, "CameraComfortValidationValidV1", shape, "ReturnValue", 992, 112)
    guard = b.add("shape_guard", "branch", 1216, 3000); bp.connect(b.entry, "then", clear, "execute"); bp.connect(clear, "then", invalidate, "execute"); bp.connect(invalidate, "then", guard, "execute"); bp.connect(valid_shape, "ReturnValue", guard, "Condition")
    loop = add_form("channel_loop", "foreach", 1440, 3000); pin_kind(loop, "Array", "real", True); pin_kind(loop, "Array Element", "real"); pin_kind(loop, "Array Index", "int"); bp.connect(source_values, "CameraComfortInputChannelValuesV1", loop, "Array"); bp.connect(guard, "then", loop, "Exec")
    blur = item(effective, "CameraComfortCandidateEffectiveWeightsV1", None, "", 1440, 512, "2")
    exposure = item(effective, "CameraComfortCandidateEffectiveWeightsV1", None, "", 1440, 672, "3")
    chromatic = item(effective, "CameraComfortCandidateEffectiveWeightsV1", None, "", 1440, 832, "4")
    is_focus_blur = compare("EqualEqual_IntInt", loop, "Array Index", "3", 1760, 512)
    is_motion_blur = compare("EqualEqual_IntInt", loop, "Array Index", "9", 1760, 672)
    is_blur = bool_op("BooleanOR", is_focus_blur, "ReturnValue", is_motion_blur, "ReturnValue", 1984, 592)
    is_exposure = compare("EqualEqual_IntInt", loop, "Array Index", "4", 1760, 832)
    is_chromatic = compare("EqualEqual_IntInt", loop, "Array Index", "10", 1760, 992)
    blur_factor = select(is_blur, None, "", blur, "Output", 2208, 592, "1.0")
    exposure_factor = select(is_exposure, blur_factor, "ReturnValue", exposure, "Output", 2432, 752)
    factor = select(is_chromatic, exposure_factor, "ReturnValue", chromatic, "Output", 2656, 912)
    scaled = b.math("Multiply_DoubleDouble", 2880, 912); bp.connect(loop, "Array Element", scaled, "A"); bp.connect(factor, "ReturnValue", scaled, "B")
    append = array_op("array_add", candidates, "CameraComfortCandidateChannelValuesV1", 3104, 3000, scaled, "ReturnValue"); bp.connect(loop, "LoopBody", append, "execute")
    publish = set_("CameraComfortCandidateValidV1", "bool", 3328, 3000, "true"); bp.connect(loop, "Completed", publish, "execute")
    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
