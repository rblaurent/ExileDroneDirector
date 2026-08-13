"""Structural contracts for generated airframe/gimbal native call forms."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


EXPECTED = {
    "Quat_RotateVector": ("Q", "V", "ReturnValue"),
    "Quat_GetAxisX": ("Q", "ReturnValue"),
    "Quat_GetAxisY": ("Q", "ReturnValue"),
    "Quat_GetAxisZ": ("Q", "ReturnValue"),
    "Quat_MakeFromEuler": ("Euler", "ReturnValue"),
    "Conv_RotatorToQuaternion": ("InRot", "ReturnValue"),
    "Cross_VectorVector": ("A", "B", "ReturnValue"),
    "Dot_VectorVector": ("A", "B", "ReturnValue"),
    "Normal": ("A", "Tolerance", "ReturnValue"),
    "Atan2": ("Y", "X", "ReturnValue"),
}


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_native_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    args = parser.parse_args()
    c = load(args.project_root)
    nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == 11, f"native form node count {len(nodes)}")
    c.require(len([n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class]) == 1, "one entry fixture")
    calls = [n for n in nodes.values() if "K2Node_CallFunction" in n.node_class]
    c.require(len(calls) == 10, "ten native calls")
    for member, expected_pins in EXPECTED.items():
        matches = [node for node in calls if f'MemberName="{member}"' in node.text]
        c.require(len(matches) == 1, f"one {member}")
        node = matches[0]
        c.require(set(node.pins) == {"self", *expected_pins}, f"{member} exact pins")
        c.require("bDefaultsToPureFunc=True" in node.text, f"{member} must remain pure")
        c.require(not any("LinkedTo=" in pin.body for pin in node.pins.values()), f"{member} fixture must be unlinked")
    normal = next(node for node in calls if 'MemberName="Normal"' in node.text)
    c.require('DefaultValue="1e-9"' in normal.pins["Tolerance"].body, "normal tolerance default")
    c.require(not any("SubPins=" in node.text or "ParentPin=" in node.text for node in calls), "forms must remain unsplit")
    print("Airframe/gimbal native node-form contracts passed")


if __name__ == "__main__":
    main()
