"""Structural and executable contracts for playback-native preflight."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "DroneCameraRef",
    "DroneCamera",
    "CameraPlaybackNativeInputValidV1",
    "CameraPlaybackNativeStageValidV1",
    "CameraApplyScratchStageValidV1",
    "CameraPlaybackNativeInputPositionV1",
    "CameraPlaybackNativeInputBodyWorldQuatV1",
    "CameraPlaybackNativeInputGimbalWorldQuatV1",
    "CameraPlaybackNativeInputGimbalRelativeQuatV1",
}
WRITES = {"CameraPlaybackNativePreflightValidV1", "CameraPlaybackNativeFailureCodeV1"}
POSE_INPUTS = (
    "CameraPlaybackNativeInputBodyWorldQuatV1",
    "CameraPlaybackNativeInputGimbalWorldQuatV1",
    "CameraPlaybackNativeInputGimbalRelativeQuatV1",
)
FORBIDDEN = (
    "CameraPlaybackResult",
    "CameraPlaybackNativeBaseline",
    "CameraPlaybackNativeSessionActiveV1",
    "CameraPlaybackNativeAppliedFrameCountV1",
    "CameraPlaybackNativeResultValidV1",
    "CameraApplyBaseline",
    "CameraApplyCurrent",
    "CameraApplySessionActiveV1",
    "CameraApplyAppliedFrameCountV1",
    "CameraChannel",
    "CinematicPoseResultQuatV1",
    "CarrierFrameResultQuatV1",
    "CameraTransform",
    "K2_SetActor",
    "K2_SetRelative",
    "SetWorld",
    "SetRelative",
    "Flypath",
    "Repository",
    "Server",
    "HUD",
    "UI",
)
TOLERANCE = 1.0e-6


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_validation_contract_base", path)
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
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def finite_quat(value) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 4
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item)) for item in value)
        and 0.999999 <= math.sqrt(sum(float(item) * float(item) for item in value)) <= 1.000001
    )


def same_rotation(left, right) -> bool:
    return all(abs(a - b) <= TOLERANCE for a, b in zip(left, right)) or all(
        abs(a + b) <= TOLERANCE for a, b in zip(left, right)
    )


def validate(state: dict) -> tuple[bool, str]:
    if state.get("actor_valid") is not True or state.get("component_valid") is not True:
        return False, "native_preflight_failed"
    if state.get("input_valid") is not True or state.get("stage_valid") is not True or state.get("engine_valid") is not True:
        return False, "native_preflight_failed"
    position = state.get("position")
    if (
        not isinstance(position, tuple)
        or len(position) != 3
        or any(not isinstance(item, (int, float)) or isinstance(item, bool) or not math.isfinite(float(item)) for item in position)
    ):
        return False, "native_preflight_failed"
    body, gimbal, relative = state.get("body"), state.get("gimbal"), state.get("relative")
    if not all(finite_quat(value) for value in (body, gimbal, relative)):
        return False, "native_preflight_failed"
    if not same_rotation(multiply(body, relative), gimbal):
        return False, "native_preflight_failed"
    return True, ""


def axis_angle(axis, radians):
    half = radians * 0.5
    sine = math.sin(half)
    return tuple(component * sine for component in axis) + (math.cos(half),)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (98 if args.paste else 99), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to preflight root")

    getter_nodes = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setter_nodes = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    getters = {member(node) for node in getter_nodes}
    setters = [member(node) for node in setter_nodes]
    contracts.require(getters == READS, f"exact preflight reads: {getters}")
    contracts.require(set(setters) == WRITES, f"exact preflight writes: {setters}")
    contracts.require(setters.count("CameraPlaybackNativePreflightValidV1") == 2, "preflight validity brackets validation")
    contracts.require(setters.count("CameraPlaybackNativeFailureCodeV1") == 2, "diagnostic stages then clears")
    contracts.require(setters[-1] == "CameraPlaybackNativePreflightValidV1", "preflight authority publishes last")

    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "preflight is read-only and ownership-clean")
    contracts.require(text.count('MemberName="ValidateCameraEngineApplicationInputsV1"') == 1, "exact accepted engine validation call")
    contracts.require(text.count('MemberName="Multiply_QuatQuat"') == 1, "exact body-relative reconstruction")
    contracts.require(text.count('MemberName="Quat_IsFinite"') == 3, "three distinct quaternion finite checks")
    contracts.require(text.count('MemberName="Quat_Size"') == 3, "three distinct quaternion unit checks")
    contracts.require(text.count('MemberName="IsValid"') == 2, "actor and component validity checks")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 3, "ordered actor/component/pose guards")

    by_member = {member(node): node for node in getter_nodes}
    valid_nodes = sorted(
        (node for node in nodes.values() if 'MemberName="IsValid"' in node.text),
        key=lambda node: node.name,
    )
    branches = sorted(
        (node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class),
        key=lambda node: node.name,
    )
    engine_call = next(node for node in nodes.values() if 'MemberName="ValidateCameraEngineApplicationInputsV1"' in node.text)
    contracts.require_link(by_member["DroneCameraRef"], "DroneCameraRef", valid_nodes[0], "Object", "actor reference validity")
    contracts.require_link(by_member["DroneCameraRef"], "DroneCameraRef", by_member["DroneCamera"], "self", "component owner")
    contracts.require_link(by_member["DroneCamera"], "DroneCamera", valid_nodes[1], "Object", "component validity")
    contracts.require_link(root, "then", setter_nodes[1], "execute", "invalidate before diagnostic")
    contracts.require_link(setter_nodes[1], "then", engine_call, "execute", "diagnostic before engine validation")
    contracts.require_link(engine_call, "then", branches[0], "execute", "engine validation before actor guard")
    contracts.require_link(branches[0], "then", branches[1], "execute", "actor gates component")
    contracts.require_link(branches[1], "then", branches[2], "execute", "component gates pose")
    contracts.require_link(branches[2], "then", setter_nodes[2], "execute", "pose gates diagnostic clear")
    contracts.require_link(setter_nodes[2], "then", setter_nodes[3], "execute", "authority publishes last")
    contracts.require(f'MemberParent="/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C\'"' in text, "component getter has explicit drone owner")

    rng = random.Random(0xEDD822)
    for index in range(100):
        body = axis_angle((0.0, 0.0, 1.0), rng.uniform(-math.pi, math.pi))
        relative = axis_angle((0.0, 1.0, 0.0), rng.uniform(-1.2, 1.2))
        gimbal = multiply(body, relative)
        if index % 2:
            gimbal = tuple(-value for value in gimbal)
        state = {
            "actor_valid": True,
            "component_valid": True,
            "input_valid": True,
            "stage_valid": True,
            "engine_valid": True,
            "position": tuple(rng.uniform(-100000.0, 100000.0) for _ in range(3)),
            "body": body,
            "gimbal": gimbal,
            "relative": relative,
        }
        before = dict(state)
        contracts.require(validate(state) == (True, ""), f"valid distinct pose {index}")
        contracts.require(state == before, "preflight does not mutate inputs")

    base = {
        "actor_valid": True,
        "component_valid": True,
        "input_valid": True,
        "stage_valid": True,
        "engine_valid": True,
        "position": (1.0, 2.0, 3.0),
        "body": axis_angle((0.0, 0.0, 1.0), math.radians(45.0)),
        "relative": axis_angle((0.0, 1.0, 0.0), math.radians(-30.0)),
    }
    base["gimbal"] = multiply(base["body"], base["relative"])
    failures = [
        {**base, "actor_valid": False},
        {**base, "component_valid": False},
        {**base, "input_valid": False},
        {**base, "stage_valid": False},
        {**base, "engine_valid": False},
        {**base, "position": (math.nan, 2.0, 3.0)},
        {**base, "position": (1.0, math.inf, 3.0)},
        {**base, "position": (1.0, 2.0, -math.inf)},
        {**base, "body": (0.0, 0.0, 0.0, 2.0)},
        {**base, "gimbal": (0.0, 0.0, math.nan, 1.0)},
        {**base, "relative": (0.0, 0.0, 0.0, 0.5)},
        {**base, "gimbal": axis_angle((1.0, 0.0, 0.0), 0.5)},
    ]
    for index, state in enumerate(failures):
        before = dict(state)
        contracts.require(validate(state) == (False, "native_preflight_failed"), f"failure {index}")
        contracts.require(state == before, f"failure {index} read only")
    print(
        f"Camera playback native preflight contracts passed "
        f"({'paste' if args.paste else 'full'}): 100 distinct poses, {len(failures)} failures"
    )


if __name__ == "__main__":
    main()
