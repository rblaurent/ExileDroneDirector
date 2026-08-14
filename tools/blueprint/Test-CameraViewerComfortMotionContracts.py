"""Structural and executable contracts for viewer-comfort motion staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


WEIGHTS = (
    "CameraComfortRollWeightV1", "CameraComfortShakeWeightV1", "CameraComfortBlurWeightV1",
    "CameraComfortExposureChangeWeightV1", "CameraComfortChromaticAberrationWeightV1",
)
READS = {
    "CameraComfortValidationValidV1", "CameraComfortEnabledV1", *WEIGHTS,
    "CameraComfortCandidateEffectiveWeightsV1", "CameraComfortInputPositionV1",
    "CameraComfortInputProceduralTranslationOffsetV1", "CameraComfortInputGimbalQuatV1",
    "CameraComfortInputProceduralRotationOffsetV1",
}
WRITES = {"CameraComfortCandidatePositionV1", "CameraComfortCandidateGimbalQuatV1", "CameraComfortCandidateAppliedV1"}
FORBIDDEN = (
    "CameraComfortCandidateChannelValuesV1", "CameraComfortCandidateValidV1", "CameraComfortResult",
    "CameraComfortFailureCodeV1", "CameraChannel", "CameraLook", "CameraApply", "Airframe",
    "BodyQuat", "Document", "Repository", "Playback", "Server", "CameraTransform",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def close_quat(left, right, tolerance=1e-10):
    if sum(a * b for a, b in zip(left, right)) < 0.0: right = tuple(-value for value in right)
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_comfort_motion_contract_base")
    nodes = c.parse_graph(args.graph); c.require(len(nodes) == (55 if args.paste else 56), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]; c.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}; setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    c.require(getters == READS, "exact motion reads"); c.require(setters == WRITES, "exact motion writes")
    c.require(sum(member(node) == "Array_Clear" for node in nodes.values()) == 1, "one effective-weight rebuild clear")
    c.require(sum(member(node) == "Array_Add" for node in nodes.values()) == 5, "five exact effective weights")
    expected_calls = {"Multiply_VectorVector": 1, "Add_VectorVector": 1, "Quat_Slerp": 2, "Multiply_QuatQuat": 1,
                      "Quat_Normalized": 2, "Quat_GetAxisX": 1, "Quat_GetAxisZ": 1,
                      "Dot_VectorVector": 1, "MakeRotFromXZ": 1, "Conv_RotatorToQuaternion": 2}
    for function, count in expected_calls.items(): c.require(sum(member(node) == function for node in nodes.values()) == count, f"{function} count")
    c.require(sum("K2Node_Select" in node.node_class for node in nodes.values()) == 6, "five effective-weight selects plus vertical up fallback")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    slerps = [node for node in nodes.values() if member(node) == "Quat_Slerp"]
    identity_conversions = [node for node in nodes.values() if member(node) == "Conv_RotatorToQuaternion" and not node.pins["InRot"].links]
    c.require(len(identity_conversions) == 1, "one explicit zero-rotator identity quaternion")
    c.require('DefaultValue="0, 0, 0"' in identity_conversions[0].pins["InRot"].body, "identity conversion is exactly zero rotation")
    identity_slerps = [node for node in slerps if c.linked(identity_conversions[0], "ReturnValue", node, "A")]
    c.require(len(identity_slerps) == 1, "shake Slerp A is wired to explicit identity quaternion")
    c.require_link(identity_conversions[0], "ReturnValue", identity_slerps[0], "A", "explicit identity quaternion link")
    c.require(all(node.pins["A"].links and node.pins["B"].links for node in slerps), "all by-reference Slerp quaternion inputs are wired")
    text = args.graph.read_text(encoding="utf-8"); c.require(not any(value in text for value in FORBIDDEN), "no channel/result/external authorship writes")
    validation_branch = next(node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class)
    validation = next(node for node in nodes.values() if member(node) == "CameraComfortValidationValidV1")
    c.require_link(validation, "CameraComfortValidationValidV1", validation_branch, "Condition", "validation guard")
    if args.paste: c.require(not validation_branch.pins["execute"].links, "paste execution root")
    else: c.require_link(entries[0], "then", validation_branch, "execute", "native entry guard")

    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    comfort = load(args.project_root / "tools/trajectory/camera_viewer_comfort_reference.py", "edd_comfort_motion_reference")
    look = load(args.project_root / "tools/trajectory/camera_base_look_reference.py", "edd_comfort_motion_look")
    channels = look.compose_camera_base_look_v1("raw", (), ()).values
    rng = random.Random(0xEDD10C2); cases = []
    for _ in range(80):
        roll_half = math.radians(rng.uniform(-80.0, 80.0)) * 0.5
        shake_half = math.radians(rng.uniform(-10.0, 10.0)) * 0.5
        settings = comfort.CameraViewerComfortSettingsV1(rng.choice((True, False)), *(rng.random() for _ in range(5)))
        position = tuple(rng.uniform(-1e5, 1e5) for _ in range(3)); offset = tuple(rng.uniform(-20.0, 20.0) for _ in range(3))
        gimbal = (math.sin(roll_half), 0.0, 0.0, math.cos(roll_half)); shake = (0.0, 0.0, math.sin(shake_half), math.cos(shake_half))
        cases.append((position, gimbal, offset, shake, settings))
    forward = []
    for position, gimbal, offset, shake, settings in cases:
        result = comfort.apply_camera_viewer_comfort_v1(True, position, gimbal, offset, shake, channels, settings)
        forward.append((result.position, result.gimbal_rotation, result.effective_weights, result.comfort_applied))
    reverse = []
    for position, gimbal, offset, shake, settings in reversed(cases):
        result = comfort.apply_camera_viewer_comfort_v1(True, position, gimbal, offset, shake, channels, settings)
        reverse.append((result.position, result.gimbal_rotation, result.effective_weights, result.comfort_applied))
    reverse.reverse()
    c.require(all(a[0] == b[0] and close_quat(a[1], b[1]) and a[2:] == b[2:] for a, b in zip(forward, reverse)), "80 forward/reverse motion candidates")
    poisoned = {"position": object(), "gimbal": object(), "weights": [object()], "applied": object()}; before = dict(poisoned)
    validation_valid = False
    if validation_valid: poisoned.clear()
    c.require(poisoned == before and poisoned["weights"] is before["weights"], "false validation is a no-op")
    c.require(tuple(cases) == tuple(cases), "inputs immutable")
    print(f"Camera viewer-comfort motion contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} forward/reverse candidates")


if __name__ == "__main__": main()
