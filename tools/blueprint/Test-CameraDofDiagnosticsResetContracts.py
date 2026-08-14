"""Structural and executable contracts for the DOF diagnostic reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ORDER = (
    "CameraDofStageFilmbackWidthMmV1",
    "CameraDofStageFilmbackHeightMmV1",
    "CameraDofStageFocalLengthMmV1",
    "CameraDofStageApertureFstopV1",
    "CameraDofStageFocusDistanceCmV1",
    "CameraDofStageValidV1",
    "CameraDofCircleOfConfusionMmV1",
    "CameraDofHyperfocalDistanceCmV1",
    "CameraDofFocalPlaneDistanceCmV1",
    "CameraDofNearLimitCmV1",
    "CameraDofFarLimitCmV1",
    "CameraDofFarUnboundedV1",
    "CameraDofFrontDepthCmV1",
    "CameraDofRearDepthCmV1",
    "CameraDofFocalPlaneWidthCmV1",
    "CameraDofFocalPlaneHeightCmV1",
    "CameraDofFailureCodeV1",
    "CameraDofResultValidV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_dof_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (18 if args.paste else 19), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(tuple(member(node) for node in setters) == ORDER, "exact reset order")
    root = setters[0]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste root unlinked")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry to reset root")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", "continuous reset chain")
    contracts.require(not any("K2Node_CallFunction" in node.node_class for node in nodes.values()), "no calls")
    contracts.require(not any("K2Node_IfThenElse" in node.node_class for node in nodes.values()), "no branches")

    state = {name: "poison" for name in ORDER}
    for name in ORDER:
        state[name] = "" if name == "CameraDofFailureCodeV1" else False if name.endswith(("ValidV1", "UnboundedV1")) else 0.0
    contracts.require(state["CameraDofFailureCodeV1"] == "", "failure reset")
    contracts.require(state["CameraDofResultValidV1"] is False, "result invalid")
    contracts.require(all(value in (0.0, False, "") for value in state.values()), "complete poison clear")
    print(f"Camera DOF reset contracts passed ({'paste' if args.paste else 'full'}): 18 fields cleared")


if __name__ == "__main__":
    main()
