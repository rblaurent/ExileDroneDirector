"""Build explicit canonical values for one validated named camera look."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCameraLookBaseValuesV1"
PRESETS = (
    ("raw", (35.0, 2.8, 1000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    ("clean_cinematic", (50.0, 2.8, 1000.0, 1.0, 0.0, 0.10, 0.10, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0)),
    ("epic_landscape", (28.0, 8.0, 100000.0, 1.0, 0.25, 0.15, 0.05, 0.0, 0.0, 0.10, 0.0, 0.0, 0.0)),
    ("dreamy_shallow_focus", (85.0, 1.4, 500.0, 1.0, 0.50, 0.45, 0.20, 0.0, 0.0, 0.10, 0.05, 0.0, 0.0)),
    ("dark_sorcery", (50.0, 2.0, 800.0, 1.0, -1.0, 0.35, 0.55, 0.0, 0.0, 0.10, 0.15, 0.0, 0.0)),
    ("high_speed_fpv", (18.0, 5.6, 100000.0, 1.0, -0.20, 0.0, 0.10, 0.0, 0.0, 0.65, 0.10, 0.0, 0.0)),
    ("vintage_lens", (50.0, 2.0, 700.0, 1.0, 0.10, 0.25, 0.45, 0.0, 0.0, 0.25, 0.30, 0.0, 0.0)),
    ("documentary", (35.0, 4.0, 2000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0)),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_look_base_values", path)
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


def value_text(value: float) -> str:
    return str(float(value))


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
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    forms.update(
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

    def set_(name: str, kind: str, x: int, y: int, value: str):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        scalar.set_default(node, name, value)
        return node

    def array_op(form: str, source, source_pin: str, x: int, y: int, value: float | None = None):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y)
        pin_kind(node, "TargetArray", "real", True)
        bp.connect(source, source_pin, node, "TargetArray")
        if form == "array_add":
            pin_kind(node, "NewItem", "real")
            pin_kind(node, "ReturnValue", "int")
            scalar.set_default(node, "NewItem", value_text(value))
        return node

    base_values = get("CameraLookCandidateBaseValuesV1", "real", 0, 256, True)
    clear = array_op("array_clear", base_values, "CameraLookCandidateBaseValuesV1", 256, 2816)
    invalidate_candidate = set_("CameraLookCandidateValidV1", "bool", 480, 2816, "false")
    invalidate_scratch = set_("CameraLookScratchValidV1", "bool", 704, 2816, "false")
    validation = get("CameraLookValidationValidV1", "bool", 0, 0)
    guard = b.add("validation_guard", "branch", 928, 2816)
    bp.connect(b.entry, "then", clear, "execute")
    bp.connect(clear, "then", invalidate_candidate, "execute")
    bp.connect(invalidate_candidate, "then", invalidate_scratch, "execute")
    bp.connect(invalidate_scratch, "then", guard, "execute")
    bp.connect(validation, "CameraLookValidationValidV1", guard, "Condition")

    preset = get("CameraLookInputPresetIdV1", "string", 0, 512)
    branches = []
    for index, (preset_id, values) in enumerate(PRESETS):
        equal = b.equal_string(1152 + index * 416, index * 256, preset_id)
        bp.connect(preset, "CameraLookInputPresetIdV1", equal, "A")
        branch = b.add(f"preset_branch_{index}", "branch", 1152 + index * 416, 2816)
        bp.connect(equal, "ReturnValue", branch, "Condition")
        branches.append(branch)
        chain = [array_op("array_add", base_values, "CameraLookCandidateBaseValuesV1", 1376 + index * 416 + value_index * 224, 256 + index * 256, value) for value_index, value in enumerate(values)]
        success = set_("CameraLookScratchValidV1", "bool", 1376 + index * 416 + len(values) * 224, 256 + index * 256, "true")
        bp.connect(branch, "then", chain[0], "execute")
        for left, right in zip(chain, chain[1:]):
            bp.connect(left, "then", right, "execute")
        bp.connect(chain[-1], "then", success, "execute")
    bp.connect(guard, "then", branches[0], "execute")
    for left, right in zip(branches, branches[1:]):
        bp.connect(left, "else", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
