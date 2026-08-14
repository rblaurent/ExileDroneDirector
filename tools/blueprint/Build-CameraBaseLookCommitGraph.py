"""Atomically publish one complete named camera-look composition."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCameraLookCompositionV1"
CHANNEL_IDS = (
    "focal_length_mm", "aperture_fstop", "focus_distance_cm", "focus_influence",
    "exposure_ev", "bloom_weight", "vignette_weight", "color_grading_weight",
    "tint_weight", "motion_blur_weight", "chromatic_aberration_weight",
    "sharpening_weight", "matte_weight",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_look_commit_base", path)
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
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    forms.update(
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        array_add=bp.find_block(capture, r'MemberName="Array_Add"'),
        array_clear=bp.find_block(reset, r'MemberName="Array_Clear"'),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name: str, kind: str, x: int, y: int, *, source=None, source_pin: str | None = None, default: str | None = None, array: bool = False):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind, array)
        if source is None:
            scalar.set_default(node, name, default)
        else:
            bp.connect(source, source_pin, node, name)
        return node

    def add_form(key: str, form: str, x: int, y: int):
        raw = forms[form]
        match = bp.BLOCK_RE.match(raw)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, raw, f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def length(source, source_pin: str, kind: str, x: int, y: int):
        node = add_form(f"length_{source_pin}_{len(b.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, kind: str = "int", right=None, right_pin: str | None = None, default: str | None = None):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def array_op(form: str, source, source_pin: str, x: int, y: int, value: str | None = None):
        node = add_form(f"{form}_{len(b.nodes)}", form, x, y)
        pin_kind(node, "TargetArray", "string", True)
        bp.connect(source, source_pin, node, "TargetArray")
        if form == "array_add":
            pin_kind(node, "NewItem", "string")
            pin_kind(node, "ReturnValue", "int")
            scalar.set_default(node, "NewItem", value)
        return node

    candidate_valid = get("CameraLookCandidateValidV1", "bool", 0, 0)
    candidate_base = get("CameraLookCandidateBaseValuesV1", "real", 0, 224, True)
    candidate_values = get("CameraLookCandidateValuesV1", "real", 0, 448, True)
    candidate_mask = get("CameraLookCandidateOverrideMaskV1", "bool", 0, 672, True)
    base_length = length(candidate_base, "CameraLookCandidateBaseValuesV1", "real", 320, 224)
    value_length = length(candidate_values, "CameraLookCandidateValuesV1", "real", 320, 448)
    mask_length = length(candidate_mask, "CameraLookCandidateOverrideMaskV1", "bool", 320, 672)
    base_exact = compare("EqualEqual_IntInt", base_length, "ReturnValue", 544, 224, default="13")
    values_exact = compare("EqualEqual_IntInt", value_length, "ReturnValue", 544, 448, default="13")
    mask_exact = compare("EqualEqual_IntInt", mask_length, "ReturnValue", 544, 672, default="13")
    base_and_values = compare("BooleanAND", base_exact, "ReturnValue", 768, 336, kind="bool", right=values_exact, right_pin="ReturnValue")
    shape = compare("BooleanAND", base_and_values, "ReturnValue", 992, 448, kind="bool", right=mask_exact, right_pin="ReturnValue")
    ready = compare("BooleanAND", candidate_valid, "CameraLookCandidateValidV1", 1216, 448, kind="bool", right=shape, right_pin="ReturnValue")

    invalidate = set_("CameraLookResultValidV1", "bool", 256, 2816, default="false")
    failure = set_("CameraLookFailureCodeV1", "string", 480, 2816, default="commit_failed")
    guard = b.add("commit_guard", "branch", 1440, 2816)
    bp.connect(b.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", failure, "execute")
    bp.connect(failure, "then", guard, "execute")
    bp.connect(ready, "ReturnValue", guard, "Condition")

    preset = get("CameraLookInputPresetIdV1", "string", 0, 896)
    publish_preset = set_("CameraLookResultPresetIdV1", "string", 1664, 2816, source=preset, source_pin="CameraLookInputPresetIdV1")
    result_ids = get("CameraLookResultChannelIdsV1", "string", 0, 1120, True)
    clear_ids = array_op("array_clear", result_ids, "CameraLookResultChannelIdsV1", 1888, 2816)
    bp.connect(guard, "then", publish_preset, "execute")
    bp.connect(publish_preset, "then", clear_ids, "execute")
    id_chain = [array_op("array_add", result_ids, "CameraLookResultChannelIdsV1", 2112 + index * 224, 2816, channel_id) for index, channel_id in enumerate(CHANNEL_IDS)]
    bp.connect(clear_ids, "then", id_chain[0], "execute")
    for left, right in zip(id_chain, id_chain[1:]):
        bp.connect(left, "then", right, "execute")

    publish_base = set_("CameraLookResultBaseValuesV1", "real", 5024, 2816, source=candidate_base, source_pin="CameraLookCandidateBaseValuesV1", array=True)
    publish_values = set_("CameraLookResultValuesV1", "real", 5248, 2816, source=candidate_values, source_pin="CameraLookCandidateValuesV1", array=True)
    publish_mask = set_("CameraLookResultOverrideMaskV1", "bool", 5472, 2816, source=candidate_mask, source_pin="CameraLookCandidateOverrideMaskV1", array=True)
    clear_failure = set_("CameraLookFailureCodeV1", "string", 5696, 2816, default="")
    publish_valid = set_("CameraLookResultValidV1", "bool", 5920, 2816, default="true")
    chain = [publish_base, publish_values, publish_mask, clear_failure, publish_valid]
    bp.connect(id_chain[-1], "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
