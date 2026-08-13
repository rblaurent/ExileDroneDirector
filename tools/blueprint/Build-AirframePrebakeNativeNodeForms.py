"""Build isolated native call forms required by the angular-rate limiter."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Build-AirframeGimbalNativeNodeForms.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_native_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build(root: Path) -> str:
    source = load(root)
    base = source.load_helpers(root)
    bp = base.load_helpers(root)
    templates = root / "tools/blueprint/templates"
    math = bp.read_blocks(templates / "repository-codec-math-node-forms.eddgraph")
    quat = bp.read_blocks(templates / "repository-codec-break-quat-node-form.eddgraph")
    vector = bp.read_blocks(templates / "repository-codec-vector-node-forms.eddgraph")
    scalar = bp.read_blocks(templates / "linear-playback-node-forms.eddgraph")
    entry_form = bp.find_block(quat, r"K2Node_FunctionEntry")
    call_form = bp.find_block(math, r'MemberName="Conv_RotatorToQuaternion"')
    quat_input = base.pin_line(bp.find_block(math, r'MemberName="Quat_Rotator"'), "Q")
    double_output = base.pin_line(bp.find_block(vector, r'MemberName="BreakVector"'), "X")
    self_input = base.pin_line(call_form, "self")

    bp.TARGET_ASSET = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_JsonNodeProbe.BP_EDD_JsonNodeProbe"
    bp.TARGET_GRAPH = "ProbeJsonNodesV1"
    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0).text
    node = bp.Node.clone("angular_distance", call_form, "K2Node_CallFunction_0", 256, 0)
    head = node.text.splitlines()
    first_pin = next(index for index, line in enumerate(head) if "CustomProperties Pin" in line)
    head = [line for line in head[:first_pin] if "FunctionReference=" not in line]
    head.insert(
        next(index for index, line in enumerate(head) if "bDefaultsToPureFunc=True" in line) + 1,
        '   FunctionReference=(MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetMathLibrary\'",MemberName="Quat_AngularDistance")',
    )
    output = [*head, base.pin(self_input, "self", "self", bp.new_id(), "input")]
    output.append(base.pin(quat_input, "Q", "A", bp.new_id(), "input"))
    output.append(base.pin(quat_input, "Q", "B", bp.new_id(), "input"))
    output.append(base.pin(double_output, "X", "ReturnValue", bp.new_id(), "output"))
    output.append("End Object")
    return entry + "\n" + "\n".join(output) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(args.project_root), encoding="utf-8")


if __name__ == "__main__":
    main()
