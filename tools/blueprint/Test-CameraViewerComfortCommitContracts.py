"""Atomic publication contracts for viewer-local comfort results."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from copy import deepcopy
from pathlib import Path


READS = {
    "CameraComfortCandidateValidV1", "CameraComfortCandidatePositionV1", "CameraComfortCandidateGimbalQuatV1",
    "CameraComfortCandidateChannelValuesV1", "CameraComfortCandidateEffectiveWeightsV1", "CameraComfortCandidateAppliedV1",
}
WRITES = {
    "CameraComfortResultValidV1", "CameraComfortFailureCodeV1", "CameraComfortResultPositionV1",
    "CameraComfortResultGimbalQuatV1", "CameraComfortResultChannelValuesV1",
    "CameraComfortResultEffectiveWeightsV1", "CameraComfortResultAppliedV1",
}
FORBIDDEN = (
    "CameraComfortInput", "CameraComfortEnabledV1", "CameraComfortRollWeightV1", "CameraComfortShakeWeightV1",
    "CameraComfortBlurWeightV1", "CameraComfortExposureChangeWeightV1", "CameraComfortChromaticAberrationWeightV1",
    "CameraComfortValidationValidV1", "CameraComfortScratch", "CameraChannel", "CameraLook", "CameraApply",
    "Airframe", "BodyQuat", "Document", "Repository", "Playback", "Server", "CameraTransform",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_comfort_commit_contract", path); module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def commit(candidate_valid, position, gimbal, values, weights, applied, prior):
    result = deepcopy(prior); result["valid"] = False; result["failure"] = "commit_failed"
    if candidate_valid and len(values) == 13 and len(weights) == 5:
        result.update(position=tuple(position), gimbal=tuple(gimbal), values=list(values), weights=list(weights), applied=bool(applied), failure="", valid=True)
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py"); nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (22 if args.paste else 23), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]; c.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}; setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    c.require(getters == READS, "exact commit reads"); c.require({member(node) for node in setters} == WRITES, "exact commit writes")
    c.require(sum(member(node) == "CameraComfortResultValidV1" for node in setters) == 2, "validity invalidated then published")
    c.require(sum(member(node) == "CameraComfortFailureCodeV1" for node in setters) == 2, "failure staged then cleared")
    c.require(sum(member(node) == "Array_Length" for node in nodes.values()) == 2, "13/5 preflight cardinalities")
    for name in ("CameraComfortResultChannelValuesV1", "CameraComfortResultEffectiveWeightsV1"):
        node = next(node for node in setters if member(node) == name); c.require("PinType.ContainerType=Array" in node.pins[name].body, f"{name} whole-array publication")
    text = args.graph.read_text(encoding="utf-8"); c.require(not any(value in text for value in FORBIDDEN), "commit boundary isolation")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    invalidator = next(node for node in setters if member(node) == "CameraComfortResultValidV1" and 'DefaultValue="true"' not in node.text)
    publisher = next(node for node in setters if member(node) == "CameraComfortResultValidV1" and 'DefaultValue="true"' in node.text)
    c.require(not publisher.pins["then"].links, "validity published last")
    if args.paste: c.require(not invalidator.pins["execute"].links, "paste root")
    else: c.require_link(entries[0], "then", invalidator, "execute", "entry invalidates first")

    prior = {"position": (9.0, 8.0, 7.0), "gimbal": (1.0, 0.0, 0.0, 0.0), "values": [8.0], "weights": [7.0], "applied": True, "valid": True, "failure": "old"}
    rng = random.Random(0xEDD10C4)
    for _ in range(80):
        position = tuple(rng.uniform(-1e6, 1e6) for _ in range(3)); gimbal = (0.0, 0.0, 0.0, 1.0)
        values = [rng.uniform(-20.0, 1000.0) for _ in range(13)]; weights = [rng.random() for _ in range(5)]; applied = rng.choice((True, False))
        before = (deepcopy(values), deepcopy(weights)); result = commit(True, position, gimbal, values, weights, applied, prior)
        c.require(result == {"position": position, "gimbal": gimbal, "values": values, "weights": weights, "applied": applied, "valid": True, "failure": ""}, "exact atomic publication")
        c.require((values, weights) == before and result["values"] is not values and result["weights"] is not weights, "deep value snapshot")
    failures = ((False, [0.0] * 13, [1.0] * 5), (True, [0.0] * 12, [1.0] * 5), (True, [0.0] * 13, [1.0] * 4), (True, [0.0] * 14, [1.0] * 6))
    for candidate_valid, values, weights in failures:
        result = commit(candidate_valid, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), values, weights, False, prior)
        c.require(all(result[key] == prior[key] for key in ("position", "gimbal", "values", "weights", "applied")), "failure preserves prior snapshot")
        c.require(not result["valid"] and result["failure"] == "commit_failed", "failure invalidates publication")
    print(f"Camera viewer-comfort commit contracts passed ({'paste' if args.paste else 'full'}): 80 snapshots, {len(failures)} failures")


if __name__ == "__main__": main()
