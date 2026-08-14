"""Exact ownership and execution contracts for camera-look reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = {
    "CameraLookCandidateBaseValuesV1",
    "CameraLookCandidateValuesV1",
    "CameraLookCandidateOverrideMaskV1",
}
SCALARS = {
    "CameraLookValidationValidV1",
    "CameraLookCandidateValidV1",
    "CameraLookResultValidV1",
    "CameraLookFailureCodeV1",
    "CameraLookScratchChannelIndexV1",
    "CameraLookScratchValidV1",
}
PRESERVED = (
    "CameraLookInputPresetIdV1",
    "CameraLookInputAuthoredChannelIdsV1",
    "CameraLookInputAuthoredValuesV1",
    "CameraLookResultPresetIdV1",
    "CameraLookResultChannelIdsV1",
    "CameraLookResultBaseValuesV1",
    "CameraLookResultValuesV1",
    "CameraLookResultOverrideMaskV1",
)
FORBIDDEN = ("CameraChannel", "CameraApply", "Airframe", "Gimbal", "Document", "Playback", "Comfort")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_look_reset_contract_base", path)
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
    contracts.require(len(nodes) == (12 if args.paste else 13), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = sorted((node for node in nodes.values() if member(node) == "Array_Clear"), key=lambda node: node.name)
    setters = sorted((node for node in nodes.values() if "K2Node_VariableSet" in node.node_class), key=lambda node: node.name)
    contracts.require(len(clears) == 3, "three candidate clears")
    if args.paste:
        contracts.require(not clears[0].pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", clears[0], "execute", "native entry to reset root")
    chain = clears + setters
    for left, right in zip(chain, chain[1:]):
        contracts.require_link(left, "then", right, "execute", f"ordered reset seam {left.name} to {right.name}")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setter_names = {member(node) for node in setters}
    contracts.require(getters == ARRAYS, "exact candidate arrays")
    contracts.require(setter_names == SCALARS, "exact reset scalars")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "inputs and accepted result snapshot preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "external ownership forbidden")

    state = {name: [object(), object()] for name in ARRAYS}
    state.update({name: "poison" for name in SCALARS})
    state.update({name: object() for name in PRESERVED})
    before = {name: state[name] for name in PRESERVED}
    for name in ARRAYS:
        state[name] = []
    state.update(
        CameraLookValidationValidV1=False,
        CameraLookCandidateValidV1=False,
        CameraLookResultValidV1=False,
        CameraLookFailureCodeV1="",
        CameraLookScratchChannelIndexV1=0,
        CameraLookScratchValidV1=False,
    )
    contracts.require(all(state[name] == [] for name in ARRAYS), "candidate arrays cleared")
    contracts.require(not state["CameraLookValidationValidV1"] and not state["CameraLookCandidateValidV1"] and not state["CameraLookResultValidV1"], "fail-closed reset")
    contracts.require(state["CameraLookFailureCodeV1"] == "" and state["CameraLookScratchChannelIndexV1"] == 0 and not state["CameraLookScratchValidV1"], "scratch converged")
    contracts.require(all(state[name] is before[name] for name in PRESERVED), "preserved object identity")
    print(f"Camera base-look reset contracts passed ({'paste' if args.paste else 'full'}): accepted snapshot preserved")


if __name__ == "__main__":
    main()
