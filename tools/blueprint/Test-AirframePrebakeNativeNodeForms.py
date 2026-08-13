"""Structural contract for the isolated native angular-distance call form."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_native_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == 2, "native form node count")
    calls = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class]
    contracts.require(len(calls) == 1, "one native call")
    node = calls[0]
    contracts.require('MemberName="Quat_AngularDistance"' in node.text, "angular-distance member")
    contracts.require(set(node.pins) == {"self", "A", "B", "ReturnValue"}, "exact pins")
    contracts.require(all('PinSubCategoryObject="/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"' in node.pins[name].body for name in ("A", "B")), "quaternion inputs")
    contracts.require('PinCategory="real"' in node.pins["ReturnValue"].body, "double output")
    contracts.require("bDefaultsToPureFunc=True" in node.text, "pure call")
    contracts.require(not any("LinkedTo=" in pin.body for pin in node.pins.values()), "fixture must be unlinked")
    contracts.require("SubPins=(" not in node.text and "ParentPin=" not in node.text, "unsplit form")
    print("Airframe prebake native node-form contracts passed")


if __name__ == "__main__":
    main()
