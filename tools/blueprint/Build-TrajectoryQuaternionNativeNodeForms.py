"""Build crash-safe unsplit native quaternion call forms for Enhanced 5.6.

Every pin line is derived from an editor-harvested, compiled fixture.  The
generated calls deliberately keep quaternion pins unsplit; split quaternion
call pins trigger K2 reconstruction assertions in the Enhanced DevKit.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTIONS = ("Quat_IsFinite", "Quat_IsNormalized", "Quat_Normalized", "Quat_Slerp")


def load_helpers(root: Path):
    path = root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_quat_native_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_line(block: str, name: str) -> str:
    matches = [line for line in block.splitlines() if f'PinName="{name}"' in line]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {name} pin; found {len(matches)}")
    return matches[0]


def unsplit(line: str) -> str:
    line = re.sub(r",SubPins=\([^)]*\)", "", line)
    line = re.sub(r",ParentPin=[^,]+", "", line)
    return line.replace("bHidden=True", "bHidden=False")


def renamed_pin(line: str, old: str, new: str, pin_id: str) -> str:
    line = unsplit(line)
    line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={pin_id}", line, count=1)
    line = line.replace(f'PinName="{old}"', f'PinName="{new}"', 1)
    return line


def build_call(bp, template: str, name: str, member: str, x: int, y: int,
               pins: list[str]) -> str:
    node = bp.Node.clone(member, template, name, x, y)
    lines = node.text.splitlines()
    first_pin = next(index for index, line in enumerate(lines) if "CustomProperties Pin" in line)
    lines = [line for line in lines[:first_pin] if "FunctionReference=" not in line]
    lines.insert(
        next(index for index, line in enumerate(lines) if "bDefaultsToPureFunc=True" in line) + 1,
        '   FunctionReference=(MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetMathLibrary\'",'
        f'MemberName="{member}")',
    )
    return "\n".join([*lines, *pins, "End Object"])


def build(root: Path) -> str:
    bp = load_helpers(root)
    forms = root / "tools" / "blueprint" / "templates"
    math = bp.read_blocks(forms / "repository-codec-math-node-forms.eddgraph")
    scalar = bp.read_blocks(forms / "linear-playback-node-forms.eddgraph")
    native = bp.read_blocks(forms / "repository-codec-break-quat-node-form.eddgraph")
    entry_template = bp.find_block(native, r"K2Node_FunctionEntry")
    call_template = bp.find_block(math, r'MemberName="Conv_RotatorToQuaternion"')
    input_template = bp.find_block(math, r'MemberName="Quat_Rotator"')
    compare_template = bp.find_block(scalar, r'MemberName="GreaterEqual_DoubleDouble"')

    bp.TARGET_ASSET = (
        "/Game/Mods/ExileDroneDirector/Developer/Automation/"
        "BP_EDD_JsonNodeProbe.BP_EDD_JsonNodeProbe"
    )
    bp.TARGET_GRAPH = "ProbeJsonNodesV1"
    entry = bp.Node.clone("entry", entry_template, "K2Node_FunctionEntry_0", 0, 0)
    q_input = pin_line(input_template, "Q")
    q_output = pin_line(call_template, "ReturnValue")
    double_input = pin_line(compare_template, "A")
    bool_output = pin_line(compare_template, "ReturnValue")
    self_pin = pin_line(call_template, "self")

    def ids(count: int) -> list[str]:
        return [bp.new_id() for _ in range(count)]

    i = ids(3)
    finite = build_call(bp, call_template, "K2Node_CallFunction_0", "Quat_IsFinite", 256, 0, [
        renamed_pin(self_pin, "self", "self", i[0]),
        renamed_pin(q_input, "Q", "Q", i[1]),
        renamed_pin(bool_output, "ReturnValue", "ReturnValue", i[2]),
    ])
    i = ids(3)
    is_normalized = build_call(bp, call_template, "K2Node_CallFunction_1", "Quat_IsNormalized", 256, 192, [
        renamed_pin(self_pin, "self", "self", i[0]),
        renamed_pin(q_input, "Q", "Q", i[1]),
        renamed_pin(bool_output, "ReturnValue", "ReturnValue", i[2]),
    ])
    i = ids(4)
    normalized = build_call(bp, call_template, "K2Node_CallFunction_2", "Quat_Normalized", 256, 384, [
        renamed_pin(self_pin, "self", "self", i[0]),
        renamed_pin(q_input, "Q", "Q", i[1]),
        renamed_pin(double_input, "A", "Tolerance", i[2]).replace(
            'PinSubCategory="double"', 'PinSubCategory="float"'
        ).replace('DefaultValue="0.0"', 'DefaultValue="0.0001"'),
        renamed_pin(q_output, "ReturnValue", "ReturnValue", i[3]),
    ])
    i = ids(5)
    slerp = build_call(bp, call_template, "K2Node_CallFunction_3", "Quat_Slerp", 256, 608, [
        renamed_pin(self_pin, "self", "self", i[0]),
        renamed_pin(q_input, "Q", "A", i[1]),
        renamed_pin(q_input, "Q", "B", i[2]),
        renamed_pin(double_input, "A", "Alpha", i[3]),
        renamed_pin(q_output, "ReturnValue", "ReturnValue", i[4]),
    ])
    return "\n".join((entry.text, finite, is_normalized, normalized, slerp)) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(args.project_root), encoding="utf-8")


if __name__ == "__main__":
    main()
