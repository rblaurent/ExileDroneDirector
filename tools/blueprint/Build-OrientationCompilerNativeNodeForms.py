"""Build unsplit native call forms required by quaternion control compilation.

The pin serializations come from already compiled Enhanced fixtures.  The
result is first installed only into the disposable automation probe; production
generation may use a form only after that probe compiles and re-exports it.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CALLS = {
    "Quat_EnforceShortestArcWith": ("A:q", "B:q", "ReturnValue:qo"),
    "Multiply_QuatQuat": ("A:q", "B:q", "ReturnValue:qo"),
    "Add_QuatQuat": ("A:q", "B:q", "ReturnValue:qo"),
    "Quat_Inversed": ("Q:q", "ReturnValue:qo"),
    "Quat_Log": ("Q:q", "ReturnValue:qo"),
    "Quat_Exp": ("Q:q", "ReturnValue:qo"),
    "Quat_SetComponents": ("Q:q", "X:f", "Y:f", "Z:f", "W:f"),
    "Quat_Size": ("Q:q", "ReturnValue:fo"),
    "VSize": ("A:v", "ReturnValue:do"),
}


def load_helpers(root: Path):
    path = root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_orientation_native_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_line(block: str, name: str) -> str:
    values = [line for line in block.splitlines() if f'PinName="{name}"' in line]
    if len(values) != 1:
        raise RuntimeError(f"Expected one {name} pin, got {len(values)}")
    return values[0]


def clean(line: str) -> str:
    line = re.sub(r",SubPins=\([^)]*\)", "", line)
    line = re.sub(r",ParentPin=[^,]+", "", line)
    line = re.sub(r",LinkedTo=\([^)]*\)", "", line)
    return line.replace("bHidden=True", "bHidden=False")


def pin(source: str, old: str, new: str, pin_id: str, direction: str) -> str:
    value = clean(source)
    value = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={pin_id}", value, count=1)
    value = value.replace(f'PinName="{old}"', f'PinName="{new}"', 1)
    if direction == "input":
        value = value.replace(',Direction="EGPD_Output"', "")
    elif 'Direction="EGPD_Output"' not in value:
        value = value.replace(",PinType.PinCategory=", ',Direction="EGPD_Output",PinType.PinCategory=', 1)
    return value


def build(root: Path) -> str:
    bp = load_helpers(root)
    templates = root / "tools" / "blueprint" / "templates"
    math = bp.read_blocks(templates / "repository-codec-math-node-forms.eddgraph")
    quat = bp.read_blocks(templates / "repository-codec-break-quat-node-form.eddgraph")
    scalar = bp.read_blocks(templates / "linear-playback-node-forms.eddgraph")
    impure = bp.read_blocks(root / "tools" / "blueprint" / "live-snippets" / "reset-repository-result-v1.eddgraph")
    entry = bp.find_block(quat, r"K2Node_FunctionEntry")
    call_template = bp.find_block(math, r'MemberName="Conv_RotatorToQuaternion"')
    q_input = pin_line(bp.find_block(math, r'MemberName="Quat_Rotator"'), "Q")
    q_output = pin_line(call_template, "ReturnValue")
    float_source = pin_line(bp.find_block(quat, r'MemberName="BreakQuat"'), "X")
    vector_blocks = bp.read_blocks(templates / "repository-codec-vector-node-forms.eddgraph")
    vector_input = pin_line(bp.find_block(vector_blocks, r'MemberName="BreakVector"'), "InVec")
    double_source = pin_line(bp.find_block(vector_blocks, r'MemberName="BreakVector"'), "X")
    self_source = pin_line(call_template, "self")
    impure_source = bp.find_block(impure, r'MemberName="Array_Clear"')
    execute_source = pin_line(impure_source, "execute")
    then_source = pin_line(impure_source, "then")

    bp.TARGET_ASSET = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_JsonNodeProbe.BP_EDD_JsonNodeProbe"
    bp.TARGET_GRAPH = "ProbeJsonNodesV1"
    nodes = [bp.Node.clone("entry", entry, "K2Node_FunctionEntry_0", 0, 0).text]
    for index, (member, specs) in enumerate(CALLS.items()):
        node = bp.Node.clone(member, call_template, f"K2Node_CallFunction_{index}", 256 + (index % 4) * 384, (index // 4) * 256)
        head = node.text.splitlines()
        first_pin = next(i for i, line in enumerate(head) if "CustomProperties Pin" in line)
        head = [line for line in head[:first_pin] if "FunctionReference=" not in line]
        if member == "Quat_SetComponents":
            head = [line for line in head if "bDefaultsToPureFunc=True" not in line]
        if member == "Quat_SetComponents":
            insert_at = 1
        else:
            insert_at = next(i for i, line in enumerate(head) if "bDefaultsToPureFunc=True" in line) + 1
        head.insert(insert_at, '   FunctionReference=(MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetMathLibrary\'",MemberName="' + member + '")')
        output = [*head]
        if member == "Quat_SetComponents":
            output.append(pin(execute_source, "execute", "execute", bp.new_id(), "input"))
            output.append(pin(then_source, "then", "then", bp.new_id(), "output"))
        output.append(pin(self_source, "self", "self", bp.new_id(), "input"))
        for spec in specs:
            name, kind = spec.split(":")
            if kind == "q":
                output.append(pin(q_input, "Q", name, bp.new_id(), "input"))
            elif kind == "qo":
                output.append(pin(q_output, "ReturnValue", name, bp.new_id(), "output"))
            elif kind == "f":
                output.append(pin(float_source, "X", name, bp.new_id(), "input"))
            elif kind == "fo":
                output.append(pin(float_source, "X", name, bp.new_id(), "output"))
            elif kind == "v":
                output.append(pin(vector_input, "InVec", name, bp.new_id(), "input"))
            elif kind == "do":
                output.append(pin(double_source, "X", name, bp.new_id(), "output"))
            else:
                raise RuntimeError(kind)
        output.append("End Object")
        nodes.append("\n".join(output))
    return "\n".join(nodes) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(args.project_root), encoding="utf-8")


if __name__ == "__main__":
    main()
