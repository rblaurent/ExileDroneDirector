"""Exact ownership and execution contracts for dolly-zoom reset."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

ARRAYS = {"CameraDollyCandidateSubjectDistancesCmV1", "CameraDollyCandidateFocalLengthsMmV1"}
SCALARS = {"CameraDollyValidationValidV1", "CameraDollyCandidateValidV1", "CameraDollyCompileValidV1", "CameraDollyFailureCodeV1"}
PRESERVED = (
    "CameraDollyInputTimesSecondsV1", "CameraDollyInputCameraPositionsV1", "CameraDollyInputSubjectPositionV1",
    "CameraDollyInputReferenceSampleIndexV1", "CameraDollyInputReferenceFocalLengthMmV1",
    "CameraDollyCompiledTimesSecondsV1", "CameraDollyCompiledSubjectDistancesCmV1",
    "CameraDollyCompiledFocalLengthsMmV1", "CameraDollyCompiledReferenceDistanceCmV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_dolly_reset_contract_base", path)
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
    contracts.require(len(nodes) == (8 if args.paste else 9), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = [node for node in nodes.values() if member(node) == "Array_Clear"]
    contracts.require(len(clears) == 2, "two candidate clears")
    if args.paste:
        contracts.require(not clears[0].pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", clears[0], "execute", "native entry to reset root")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == ARRAYS, "exact candidate arrays")
    contracts.require(setters == SCALARS, "exact reset scalars")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "inputs and accepted compiled snapshot preserved")
    state = {name: [1.0, 2.0] for name in ARRAYS}
    state.update({name: "poison" for name in SCALARS})
    state.update({name: object() for name in PRESERVED})
    before = {name: state[name] for name in PRESERVED}
    for name in ARRAYS:
        state[name] = []
    state.update(CameraDollyValidationValidV1=False, CameraDollyCandidateValidV1=False, CameraDollyCompileValidV1=False, CameraDollyFailureCodeV1="")
    contracts.require(all(state[name] == [] for name in ARRAYS), "candidate arrays cleared")
    contracts.require(not state["CameraDollyValidationValidV1"] and not state["CameraDollyCandidateValidV1"] and not state["CameraDollyCompileValidV1"], "fail-closed reset")
    contracts.require(state["CameraDollyFailureCodeV1"] == "", "failure cleared")
    contracts.require(all(state[name] is before[name] for name in PRESERVED), "preserved object identity")
    print(f"Camera dolly reset contracts passed ({'paste' if args.paste else 'full'}): compiled snapshot preserved")


if __name__ == "__main__":
    main()
