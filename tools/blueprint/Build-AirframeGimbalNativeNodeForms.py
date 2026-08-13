"""Build unsplit native call forms used by the airframe/gimbal solver.

Pin serializations are derived from already compiled Enhanced fixtures.  These
forms stay isolated until the disposable probe and production graph compile.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CALLS = {
    "Quat_RotateVector": ("Q:q", "V:v", "ReturnValue:vo"),
    "Quat_GetAxisX": ("Q:q", "ReturnValue:vo"),
    "Quat_GetAxisY": ("Q:q", "ReturnValue:vo"),
    "Quat_GetAxisZ": ("Q:q", "ReturnValue:vo"),
    "Quat_MakeFromEuler": ("Euler:v", "ReturnValue:qo"),
    "Conv_RotatorToQuaternion": ("InRot:r", "ReturnValue:qo"),
    "Cross_VectorVector": ("A:v", "B:v", "ReturnValue:vo"),
    "Dot_VectorVector": ("A:v", "B:v", "ReturnValue:do"),
    "Normal": ("A:v", "Tolerance:d", "ReturnValue:vo"),
    "Atan2": ("Y:d", "X:d", "ReturnValue:do"),
}


def load_helpers(root: Path):
    path = root / "tools/blueprint/Build-OrientationCompilerNativeNodeForms.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_native_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build(root: Path) -> str:
    base = load_helpers(root)
    bp = base.load_helpers(root)
    templates = root / "tools/blueprint/templates"
    math = bp.read_blocks(templates / "repository-codec-math-node-forms.eddgraph")
    quat = bp.read_blocks(templates / "repository-codec-break-quat-node-form.eddgraph")
    vector = bp.read_blocks(templates / "repository-codec-vector-node-forms.eddgraph")
    scalar = bp.read_blocks(templates / "linear-playback-node-forms.eddgraph")
    entry_form = bp.find_block(quat, r"K2Node_FunctionEntry")
    call_form = bp.find_block(math, r'MemberName="Conv_RotatorToQuaternion"')
    q_input = base.pin_line(bp.find_block(math, r'MemberName="Quat_Rotator"'), "Q")
    vector_input = base.pin_line(bp.find_block(vector, r'MemberName="BreakVector"'), "InVec")
    rotator_input = base.pin_line(call_form, "InRot")
    position_route = bp.read_blocks(root / "tools/blueprint/live-snippets/compute-position-route-velocities-v1.eddgraph")
    vector_output = base.pin_line(bp.find_block(position_route, r'MemberName="MakeVector"'), "ReturnValue")
    quat_output = base.pin_line(call_form, "ReturnValue")
    double_input = base.pin_line(bp.find_block(scalar, r'MemberName="GreaterEqual_DoubleDouble"'), "A")
    double_output = base.pin_line(bp.find_block(vector, r'MemberName="BreakVector"'), "X")
    self_input = base.pin_line(call_form, "self")

    bp.TARGET_ASSET = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_JsonNodeProbe.BP_EDD_JsonNodeProbe"
    bp.TARGET_GRAPH = "ProbeJsonNodesV1"
    nodes = [bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0).text]
    for index, (member, specs) in enumerate(CALLS.items()):
        node = bp.Node.clone(member, call_form, f"K2Node_CallFunction_{index}", 256 + index * 384, 0)
        head = node.text.splitlines()
        first_pin = next(i for i, line in enumerate(head) if "CustomProperties Pin" in line)
        head = [line for line in head[:first_pin] if "FunctionReference=" not in line]
        head.insert(
            next(i for i, line in enumerate(head) if "bDefaultsToPureFunc=True" in line) + 1,
            '   FunctionReference=(MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetMathLibrary\'",'
            f'MemberName="{member}")',
        )
        output = [*head, base.pin(self_input, "self", "self", bp.new_id(), "input")]
        for spec in specs:
            name, kind = spec.split(":")
            if kind == "q":
                output.append(base.pin(q_input, "Q", name, bp.new_id(), "input"))
            elif kind == "v":
                output.append(base.pin(vector_input, "InVec", name, bp.new_id(), "input"))
            elif kind == "r":
                output.append(base.pin(rotator_input, "InRot", name, bp.new_id(), "input"))
            elif kind == "vo":
                output.append(base.pin(vector_output, "ReturnValue", name, bp.new_id(), "output"))
            elif kind == "qo":
                output.append(base.pin(quat_output, "ReturnValue", name, bp.new_id(), "output"))
            elif kind == "d":
                line = base.pin(double_input, "A", name, bp.new_id(), "input")
                if name == "Tolerance":
                    line = re.sub(r'DefaultValue="[^"]*"', 'DefaultValue="1e-9"', line, 1)
                output.append(line)
            elif kind == "do":
                output.append(base.pin(double_output, "X", name, bp.new_id(), "output"))
            else:
                raise RuntimeError(kind)
        output.append("End Object")
        nodes.append("\n".join(output))
    return "\n".join(nodes) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(args.project_root), encoding="utf-8")


if __name__ == "__main__":
    main()
