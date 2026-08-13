"""Exact graph and execution contracts for camera scalar result reset."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

RESET = {
    "CameraScalarTrackResultValueV1": 0.0,
    "CameraScalarTrackResultVelocityV1": 0.0,
    "CameraScalarTrackResultAccelerationV1": 0.0,
    "CameraScalarTrackResultSegmentIndexV1": -1,
    "CameraScalarTrackResultLocalAlphaV1": 0.0,
    "CameraScalarTrackResultCompleteV1": False,
    "CameraScalarTrackResultValidV1": False,
    "CameraScalarTrackScratchIndexV1": 0,
    "CameraScalarTrackScratchValidV1": False,
    "CameraScalarTrackScratchDomainValueV1": 0.0,
    "CameraScalarTrackScratchDomainVelocityV1": 0.0,
    "CameraScalarTrackScratchDomainAccelerationV1": 0.0,
}
PRESERVED = (
    "CameraScalarTrackInputDurationV1",
    "CameraScalarTrackInputKeyTimesV1",
    "CameraScalarTrackInputKeyValuesV1",
    "CameraScalarTrackInputInterpolationModesV1",
    "CameraScalarTrackInputArriveTangentsV1",
    "CameraScalarTrackInputLeaveTangentsV1",
    "CameraScalarTrackInputDomainV1",
    "CameraScalarTrackInputHasMinimumV1",
    "CameraScalarTrackInputMinimumV1",
    "CameraScalarTrackInputHasMaximumV1",
    "CameraScalarTrackInputMaximumV1",
    "CameraScalarTrackInputClampOutputV1",
    "CameraScalarTrackCandidateKeyTimesV1",
    "CameraScalarTrackCandidateDomainValuesV1",
    "CameraScalarTrackCandidateInterpolationModesV1",
    "CameraScalarTrackCandidateArriveTangentsV1",
    "CameraScalarTrackCandidateLeaveTangentsV1",
    "CameraScalarTrackCompileValidV1",
    "CameraScalarTrackFailureCodeV1",
    "CameraScalarTrackQueryTimeV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_scalar_result_reset_contract_base", path)
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
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in setters} == set(RESET), "result/scratch ownership")
    first = nodes["K2Node_VariableSet_0"]
    if args.paste:
        contracts.require(not first.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", first, "execute", "native entry to first result reset")
    for index in range(len(RESET) - 1):
        contracts.require_link(
            nodes[f"K2Node_VariableSet_{index}"],
            "then",
            nodes[f"K2Node_VariableSet_{index + 1}"],
            "execute",
            "ordered result reset",
        )
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "compile/authored/query preservation")
    state = {name: "poison" for name in RESET}
    state.update({name: [name] for name in PRESERVED})
    before = {name: state[name] for name in PRESERVED}
    state.update(RESET)
    contracts.require(all(state[name] == value for name, value in RESET.items()), "exact reset execution")
    contracts.require(all(state[name] == before[name] for name in PRESERVED), "preserved state")
    print(
        f"Camera scalar-track result-reset contracts passed ({'paste' if args.paste else 'full'}): "
        f"{len(nodes)} nodes, compile snapshot preserved"
    )


if __name__ == "__main__":
    main()
