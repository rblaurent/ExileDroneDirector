"""Build fail-closed validation for named camera-look composition inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateCameraLookInputsV1"
PRESET_IDS = (
    "raw", "clean_cinematic", "epic_landscape", "dreamy_shallow_focus",
    "dark_sorcery", "high_speed_fpv", "vintage_lens", "documentary",
)
CHANNEL_IDS = (
    "focal_length_mm", "aperture_fstop", "focus_distance_cm", "focus_influence",
    "exposure_ev", "bloom_weight", "vignette_weight", "color_grading_weight",
    "tint_weight", "motion_blur_weight", "chromatic_aberration_weight",
    "sharpening_weight", "matte_weight",
)
NORMALIZED_IDS = CHANNEL_IDS[3:4] + CHANNEL_IDS[5:]


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_look_validation_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""),
        "real": ("real", "double"), "string": ("string", ""),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
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
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    find_graph = bp.read_blocks(args.project_root / "tools/blueprint/snippets/find-record-index-v1.eddgraph")
    forms.update(
        foreach=bp.find_block(sync, r"K2Node_MacroInstance"),
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        find=bp.find_block(find_graph, r'MemberName="Array_Find"'),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name: str, kind: str, x: int, y: int, value: str):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        scalar.set_default(node, name, value)
        return node

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def length(source, source_pin: str, kind: str, x: int, y: int):
        node = add_form(f"length_{source_pin}_{len(b.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def foreach(source, source_pin: str, kind: str, x: int, y: int):
        node = add_form(f"foreach_{source_pin}_{len(b.nodes)}", "foreach", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Array Element", kind)
        pin_kind(node, "Array Index", "int")
        bp.connect(source, source_pin, node, "Array")
        return node

    def item(source, source_pin: str, kind: str, index, index_pin: str, x: int, y: int):
        node = add_form(f"item_{source_pin}_{len(b.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def find(source, source_pin: str, value, value_pin: str, x: int, y: int):
        node = add_form(f"find_{source_pin}_{len(b.nodes)}", "find", x, y)
        pin_kind(node, "TargetArray", "string", True)
        pin_kind(node, "ItemToFind", "string")
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        bp.connect(value, value_pin, node, "ItemToFind")
        return node

    def retarget(node, member: str, kinds: dict[str, str]):
        scalar.retarget_function(node, member)
        if member in ("EqualEqual_StrStr", "NotEqual_StrStr"):
            node.text = node.text.replace("KismetMathLibrary", "KismetStringLibrary")
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, kind: str, right=None, right_pin: str | None = None, default: str | None = None):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default)
        return node

    def combine(member: str, conditions, x: int, y: int):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = compare(member, current, "ReturnValue", x + index * 208, y, kind="bool", right=condition, right_pin="ReturnValue")
        return current

    invalidate = set_("CameraLookValidationValidV1", "bool", 256, 2688, "false")
    scratch_false = set_("CameraLookScratchValidV1", "bool", 480, 2688, "false")
    scratch_index = set_("CameraLookScratchChannelIndexV1", "int", 704, 2688, "0")
    failure = set_("CameraLookFailureCodeV1", "string", 928, 2688, "validation_failed")
    bp.connect(b.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", scratch_false, "execute")
    bp.connect(scratch_false, "then", scratch_index, "execute")
    bp.connect(scratch_index, "then", failure, "execute")

    preset = get("CameraLookInputPresetIdV1", "string", 0, 0)
    ids = get("CameraLookInputAuthoredChannelIdsV1", "string", 0, 224, True)
    values = get("CameraLookInputAuthoredValuesV1", "real", 0, 448, True)
    ids_length = length(ids, "CameraLookInputAuthoredChannelIdsV1", "string", 320, 224)
    values_length = length(values, "CameraLookInputAuthoredValuesV1", "real", 320, 448)

    preset_valid = combine(
        "BooleanOR",
        [compare("EqualEqual_StrStr", preset, "CameraLookInputPresetIdV1", 640 + index * 208, 0, kind="string", default=value) for index, value in enumerate(PRESET_IDS)],
        2304, 0,
    )
    lengths_equal = compare("EqualEqual_IntInt", ids_length, "ReturnValue", 640, 224, kind="int", right=values_length, right_pin="ReturnValue")
    count_valid = compare("LessEqual_IntInt", ids_length, "ReturnValue", 864, 224, kind="int", default="13")
    shape_valid = combine("BooleanAND", [preset_valid, lengths_equal, count_valid], 2512, 224)
    shape_branch = b.add("shape_branch", "branch", 3136, 2688)
    bp.connect(failure, "then", shape_branch, "execute")
    bp.connect(shape_valid, "ReturnValue", shape_branch, "Condition")
    scratch_true = set_("CameraLookScratchValidV1", "bool", 3360, 2688, "true")
    bp.connect(shape_branch, "then", scratch_true, "execute")

    loop = foreach(ids, "CameraLookInputAuthoredChannelIdsV1", "string", 3584, 2688)
    bp.connect(scratch_true, "then", loop, "Exec")
    value = item(values, "CameraLookInputAuthoredValuesV1", "real", loop, "Array Index", 3840, 448)
    first = find(ids, "CameraLookInputAuthoredChannelIdsV1", loop, "Array Element", 3840, 672)
    unique = compare("EqualEqual_IntInt", first, "ReturnValue", 4096, 672, kind="int", right=loop, right_pin="Array Index")
    finite = b.finite(value, "Output", 4096, 896)

    id_checks = {
        channel_id: compare("EqualEqual_StrStr", loop, "Array Element", 4096 + index * 208, 0, kind="string", default=channel_id)
        for index, channel_id in enumerate(CHANNEL_IDS)
    }
    normalized_id = combine("BooleanOR", [id_checks[channel_id] for channel_id in NORMALIZED_IDS], 6800, 0)

    def range_valid(identifier, minimum: str, maximum: str, x: int, y: int):
        lower = compare("GreaterEqual_DoubleDouble", value, "Output", x, y, kind="real", default=minimum)
        upper = compare("LessEqual_DoubleDouble", value, "Output", x + 208, y, kind="real", default=maximum)
        numeric = combine("BooleanAND", [lower, upper], x + 416, y)
        return combine("BooleanAND", [identifier, numeric], x + 624, y)

    focal_valid = range_valid(id_checks["focal_length_mm"], "1.0", "1000.0", 4096, 1120)
    aperture_valid = range_valid(id_checks["aperture_fstop"], "0.1", "64.0", 4096, 1344)
    focus_valid = range_valid(id_checks["focus_distance_cm"], "1.0", "1000000000.0", 4096, 1568)
    exposure_valid = range_valid(id_checks["exposure_ev"], "-20.0", "20.0", 4096, 1792)
    normalized_valid = range_valid(normalized_id, "0.0", "1.0", 4096, 2016)
    bounds_valid = combine("BooleanOR", [focal_valid, aperture_valid, focus_valid, exposure_valid, normalized_valid], 7840, 1568)
    item_valid = combine("BooleanAND", [unique, finite, bounds_valid], 8672, 1792)
    item_branch = b.add("item_branch", "branch", 9296, 2688)
    bp.connect(loop, "LoopBody", item_branch, "execute")
    bp.connect(item_valid, "ReturnValue", item_branch, "Condition")
    reject = set_("CameraLookScratchValidV1", "bool", 9520, 2912, "false")
    bp.connect(item_branch, "else", reject, "execute")

    final_scratch = get("CameraLookScratchValidV1", "bool", 9520, 2240)
    final_branch = b.add("final_branch", "branch", 9744, 2688)
    bp.connect(loop, "Completed", final_branch, "execute")
    bp.connect(final_scratch, "CameraLookScratchValidV1", final_branch, "Condition")
    success = set_("CameraLookFailureCodeV1", "string", 9968, 2688, "")
    publish = set_("CameraLookValidationValidV1", "bool", 10192, 2688, "true")
    bp.connect(final_branch, "then", success, "execute")
    bp.connect(success, "then", publish, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
