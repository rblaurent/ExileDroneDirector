"""Executable ownership and atomicity contracts for final playback publication."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from copy import deepcopy
from pathlib import Path


READS = {
    "CameraPlaybackComfortStageValidV1", "CameraOperatorResultValidV1", "CameraComfortResultValidV1",
    "CameraChannelResultValidV1", "CameraComfortResultPositionV1", "CameraOperatorResultBodyQuatV1",
    "CameraComfortResultGimbalQuatV1", "CameraChannelResultFilmbackPresetIdV1",
    "CameraChannelResultFilmbackSensorWidthMmV1", "CameraChannelResultFilmbackSensorHeightMmV1",
    "CameraComfortResultChannelValuesV1", "CameraChannelResultCompleteV1", "CameraOperatorResultModeV1",
    "CameraOperatorResultOverrideActiveV1", "CameraOperatorResultTransitionActiveV1",
    "CameraOperatorResultTetherAppliedV1", "CameraComfortResultEffectiveWeightsV1",
    "CameraComfortResultAppliedV1",
}
WRITES = {
    "CameraPlaybackResultPositionV1", "CameraPlaybackResultBodyWorldQuatV1",
    "CameraPlaybackResultGimbalWorldQuatV1", "CameraPlaybackResultGimbalRelativeQuatV1",
    "CameraPlaybackResultFilmbackPresetIdV1", "CameraPlaybackResultFilmbackSensorWidthMmV1",
    "CameraPlaybackResultFilmbackSensorHeightMmV1", "CameraPlaybackResultChannelValuesV1",
    "CameraPlaybackResultCompleteV1", "CameraPlaybackResultModeV1",
    "CameraPlaybackResultOverrideActiveV1", "CameraPlaybackResultTransitionActiveV1",
    "CameraPlaybackResultTetherAppliedV1", "CameraPlaybackResultComfortEffectiveWeightsV1",
    "CameraPlaybackResultComfortAppliedV1", "CameraPlaybackResultValidV1", "CameraPlaybackFailureCodeV1",
}
FORBIDDEN = (
    "CinematicPoseResultQuatV1", "CameraTransform", "AirframePrebakeResultGimbalQuatV1",
    "CarrierFrameResultQuatV1", "CameraOperatorInput", "CameraComfortInput", "CameraOperatorState",
    "CameraComfortEnabledV1", "CameraComfortRollWeightV1", "CameraApply", "CineCameraComponent",
    "Flypath", "Repository", "Event", "Cue", "StateClip", "Server",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_commit_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def multiply(left, right):
    lx, ly, lz, lw = left; rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def inverse(quat):
    size_sq = sum(component * component for component in quat)
    return (-quat[0] / size_sq, -quat[1] / size_sq, -quat[2] / size_sq, quat[3] / size_sq)


def unit(quat):
    size = math.sqrt(sum(component * component for component in quat))
    return tuple(component / size for component in quat)


def valid_quat(quat):
    return len(quat) == 4 and all(math.isfinite(component) for component in quat) and 0.999999 <= math.sqrt(sum(component * component for component in quat)) <= 1.000001


def commit(state, prior):
    result = deepcopy(prior)
    result["valid"] = False
    result["failure"] = "commit_failed"
    required = all(state[name] for name in ("stage", "operator_valid", "comfort_valid", "channels_valid"))
    body, gimbal = state["body"], state["gimbal"]
    relative = multiply(inverse(body), gimbal) if valid_quat(body) and valid_quat(gimbal) else (math.nan,) * 4
    reconstructed = multiply(body, relative) if valid_quat(relative) else (math.nan,) * 4
    shape = (
        len(state["position"]) == 3 and all(math.isfinite(value) for value in state["position"])
        and valid_quat(body) and valid_quat(gimbal) and valid_quat(relative) and valid_quat(reconstructed)
        and all(abs(left - right) <= 1.0e-6 for left, right in zip(reconstructed, gimbal))
        and bool(state["preset"]) and math.isfinite(state["width"]) and state["width"] > 0.0
        and math.isfinite(state["height"]) and state["height"] > 0.0
        and len(state["channels"]) == 13 and all(math.isfinite(value) for value in state["channels"])
        and len(state["weights"]) == 5 and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in state["weights"])
    )
    if required and shape:
        result.update(
            position=tuple(state["position"]), body=tuple(body), gimbal=tuple(gimbal), relative=tuple(relative),
            preset=state["preset"], width=state["width"], height=state["height"],
            channels=list(state["channels"]), complete=state["complete"], mode=state["mode"],
            override=state["override"], transition=state["transition"], tether=state["tether"],
            weights=list(state["weights"]), comfort_applied=state["comfort_applied"], failure="", valid=True,
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (237 if args.paste else 238), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, "exact accepted-boundary reads")
    contracts.require({member(node) for node in setters} == WRITES, "playback-only writes")
    contracts.require(sum(member(node) == "CameraPlaybackResultValidV1" for node in setters) == 2, "validity invalidated and published")
    contracts.require(sum(member(node) == "CameraPlaybackFailureCodeV1" for node in setters) == 2, "diagnostic staged and cleared")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "native/upstream/legacy ownership isolation")
    contracts.require(text.count('MemberName="Quat_Inversed"') == 1, "one body inverse")
    contracts.require(text.count('MemberName="Multiply_QuatQuat"') == 2, "derive relative and reconstruct world gimbal")
    contracts.require(text.count('MemberName="Quat_IsFinite"') == 4 and text.count('MemberName="Quat_Size"') == 4, "four quaternion tamper checks")
    contracts.require(text.count('MemberName="BreakQuat"') == 2, "component reconstruction proof")
    contracts.require(text.count('MemberName="Array_Length"') == 2, "13/5 array cardinality proof")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 18, "all channel/weight values checked")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute ownership ambiguity")

    invalidator = next(node for node in setters if member(node) == "CameraPlaybackResultValidV1" and 'DefaultValue="true"' not in node.text)
    publisher = next(node for node in setters if member(node) == "CameraPlaybackResultValidV1" and 'DefaultValue="true"' in node.text)
    contracts.require(not publisher.pins["then"].links, "result authority publishes last")
    if args.paste:
        contracts.require(not invalidator.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", invalidator, "execute", "entry invalidates first")

    body_get = next(node for node in nodes.values() if member(node) == "CameraOperatorResultBodyQuatV1")
    gimbal_get = next(node for node in nodes.values() if member(node) == "CameraComfortResultGimbalQuatV1")
    body_set = next(node for node in setters if member(node) == "CameraPlaybackResultBodyWorldQuatV1")
    gimbal_set = next(node for node in setters if member(node) == "CameraPlaybackResultGimbalWorldQuatV1")
    relative_set = next(node for node in setters if member(node) == "CameraPlaybackResultGimbalRelativeQuatV1")
    inverse_node = next(node for node in nodes.values() if member(node) == "Quat_Inversed")
    multiply_nodes = [node for node in nodes.values() if member(node) == "Multiply_QuatQuat"]
    contracts.require_link(body_get, "CameraOperatorResultBodyQuatV1", body_set, "CameraPlaybackResultBodyWorldQuatV1", "body publication remains operator-owned")
    contracts.require_link(gimbal_get, "CameraComfortResultGimbalQuatV1", gimbal_set, "CameraPlaybackResultGimbalWorldQuatV1", "world gimbal publication remains comfort-owned")
    contracts.require_link(body_get, "CameraOperatorResultBodyQuatV1", inverse_node, "Q", "relative starts from body inverse")
    relative_node = next(node for node in multiply_nodes if any(link[0] == inverse_node.name for link in node.pins["A"].links))
    contracts.require_link(gimbal_get, "CameraComfortResultGimbalQuatV1", relative_node, "B", "relative uses distinct world gimbal")
    contracts.require_link(relative_node, "ReturnValue", relative_set, "CameraPlaybackResultGimbalRelativeQuatV1", "derived relative publication")
    reconstructed_node = next(node for node in multiply_nodes if any(link[0] == relative_node.name for link in node.pins["B"].links))
    contracts.require_link(body_get, "CameraOperatorResultBodyQuatV1", reconstructed_node, "A", "reconstruct body times relative")

    prior = {
        "position": (9.0, 8.0, 7.0), "body": (0.0, 0.0, 0.0, 1.0), "gimbal": (0.0, 0.0, 0.0, 1.0),
        "relative": (0.0, 0.0, 0.0, 1.0), "preset": "prior", "width": 1.0, "height": 1.0,
        "channels": [99.0], "complete": False, "mode": "directed", "override": False,
        "transition": False, "tether": False, "weights": [0.5], "comfort_applied": False,
        "failure": "old", "valid": True,
    }
    rng = random.Random(0xEDD10F5)
    for index in range(80):
        body = unit(tuple(rng.uniform(-1.0, 1.0) for _ in range(4)))
        relative = unit(tuple(rng.uniform(-1.0, 1.0) for _ in range(4)))
        gimbal = multiply(body, relative)
        state = {
            "stage": True, "operator_valid": True, "comfort_valid": True, "channels_valid": True,
            "position": tuple(rng.uniform(-1.0e6, 1.0e6) for _ in range(3)), "body": body, "gimbal": gimbal,
            "preset": f"preset_{index}", "width": rng.uniform(1.0, 70.0), "height": rng.uniform(1.0, 70.0),
            "channels": [rng.uniform(-100.0, 1000.0) for _ in range(13)], "complete": bool(index & 1),
            "mode": ("directed", "free_look", "carrier_freecam")[index % 3], "override": bool(index & 2),
            "transition": bool(index & 4), "tether": bool(index & 8),
            "weights": [rng.random() for _ in range(5)], "comfort_applied": bool(index & 16),
        }
        before = deepcopy(state)
        result = commit(state, prior)
        contracts.require(result["valid"] and result["failure"] == "", f"valid {index}: published")
        contracts.require(all(abs(a - b) <= 1.0e-6 for a, b in zip(multiply(result["body"], result["relative"]), result["gimbal"])), f"valid {index}: relative reconstructs")
        contracts.require(state == before and result["channels"] is not state["channels"] and result["weights"] is not state["weights"], f"valid {index}: immutable deep snapshot")

    base = {
        "stage": True, "operator_valid": True, "comfort_valid": True, "channels_valid": True,
        "position": (1.0, 2.0, 3.0), "body": (0.0, 0.0, 0.0, 1.0), "gimbal": (0.0, 0.0, 0.0, 1.0),
        "preset": "35mm", "width": 36.0, "height": 24.0, "channels": [0.0] * 13, "complete": False,
        "mode": "directed", "override": False, "transition": False, "tether": False,
        "weights": [0.5] * 5, "comfort_applied": False,
    }
    mutations = (
        ("stage", False), ("operator_valid", False), ("comfort_valid", False), ("channels_valid", False),
        ("position", (math.nan, 2.0, 3.0)), ("body", (0.0, 0.0, 0.0, 2.0)),
        ("gimbal", (math.inf, 0.0, 0.0, 1.0)), ("preset", ""), ("width", 0.0), ("height", math.inf),
        ("channels", [0.0] * 12), ("channels", [0.0] * 12 + [math.nan]),
        ("weights", [0.5] * 4), ("weights", [0.5, 0.5, 0.5, 0.5, 1.1]),
    )
    for name, value in mutations:
        state = deepcopy(base); state[name] = value; result = commit(state, prior)
        contracts.require(not result["valid"] and result["failure"] == "commit_failed", f"{name}: fail closed")
        contracts.require(all(result[key] == prior[key] for key in prior if key not in ("valid", "failure")), f"{name}: prior result preserved")
    print(f"Camera playback commit contracts passed ({'paste' if args.paste else 'full'}): 80 snapshots, {len(mutations)} failures")


if __name__ == "__main__":
    main()
