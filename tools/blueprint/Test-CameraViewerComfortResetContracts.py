"""Exact ownership and execution contracts for viewer-comfort reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = {"CameraComfortCandidateChannelValuesV1", "CameraComfortCandidateEffectiveWeightsV1"}
SCALARS = {
    "CameraComfortValidationValidV1", "CameraComfortCandidatePositionV1",
    "CameraComfortCandidateGimbalQuatV1", "CameraComfortCandidateAppliedV1",
    "CameraComfortCandidateValidV1", "CameraComfortResultValidV1",
    "CameraComfortFailureCodeV1", "CameraComfortScratchChannelIndexV1",
    "CameraComfortScratchValidV1",
}
PRESERVED = (
    "CameraComfortInputFrameValidV1", "CameraComfortInputPositionV1",
    "CameraComfortInputGimbalQuatV1", "CameraComfortInputProceduralTranslationOffsetV1",
    "CameraComfortInputProceduralRotationOffsetV1", "CameraComfortInputChannelValuesV1",
    "CameraComfortEnabledV1", "CameraComfortRollWeightV1", "CameraComfortShakeWeightV1",
    "CameraComfortBlurWeightV1", "CameraComfortExposureChangeWeightV1",
    "CameraComfortChromaticAberrationWeightV1", "CameraComfortResultPositionV1",
    "CameraComfortResultGimbalQuatV1", "CameraComfortResultChannelValuesV1",
    "CameraComfortResultEffectiveWeightsV1", "CameraComfortResultAppliedV1",
)
FORBIDDEN = ("CameraChannel", "CameraLook", "CameraApply", "Airframe", "Body", "Document", "Repository", "Playback", "Server")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_comfort_reset_contract_base", path)
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
    contracts.require(len(nodes) == (13 if args.paste else 14), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = sorted((node for node in nodes.values() if member(node) == "Array_Clear"), key=lambda node: node.name)
    setters = sorted((node for node in nodes.values() if "K2Node_VariableSet" in node.node_class), key=lambda node: node.name)
    contracts.require(len(clears) == 2, "two private candidate clears")
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
    contracts.require(not any(name in text for name in PRESERVED), "inputs, preferences, and accepted result preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "external ownership forbidden")

    state = {name: [object(), object()] for name in ARRAYS}
    state.update({name: "poison" for name in SCALARS})
    state.update({name: object() for name in PRESERVED})
    before = {name: state[name] for name in PRESERVED}
    for name in ARRAYS:
        state[name] = []
    state.update(
        CameraComfortValidationValidV1=False,
        CameraComfortCandidatePositionV1=(0.0, 0.0, 0.0),
        CameraComfortCandidateGimbalQuatV1=(0.0, 0.0, 0.0, 1.0),
        CameraComfortCandidateAppliedV1=False,
        CameraComfortCandidateValidV1=False,
        CameraComfortResultValidV1=False,
        CameraComfortFailureCodeV1="",
        CameraComfortScratchChannelIndexV1=0,
        CameraComfortScratchValidV1=False,
    )
    contracts.require(all(state[name] == [] for name in ARRAYS), "candidate arrays cleared")
    contracts.require(not state["CameraComfortValidationValidV1"] and not state["CameraComfortCandidateValidV1"] and not state["CameraComfortResultValidV1"], "fail-closed reset")
    contracts.require(state["CameraComfortCandidatePositionV1"] == (0.0, 0.0, 0.0), "position candidate reset")
    contracts.require(state["CameraComfortCandidateGimbalQuatV1"] == (0.0, 0.0, 0.0, 1.0), "gimbal candidate reset")
    contracts.require(state["CameraComfortFailureCodeV1"] == "" and state["CameraComfortScratchChannelIndexV1"] == 0 and not state["CameraComfortScratchValidV1"], "scratch converged")
    contracts.require(all(state[name] is before[name] for name in PRESERVED), "preserved object identity")
    print(f"Camera viewer-comfort reset contracts passed ({'paste' if args.paste else 'full'}): prior local snapshot preserved")


if __name__ == "__main__":
    main()
