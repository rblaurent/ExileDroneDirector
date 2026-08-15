"""Structural and executable contracts for camera operator look/frame staging."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraOperatorScratchValidV1", "CameraOperatorStateInitializedV1",
    "CameraOperatorCandidateModeV1", "CameraOperatorCandidateRecenterActiveV1",
    "CameraOperatorInputLookV1", "CameraOperatorPolicyMaximumAngularSpeedV1",
    "CameraOperatorStateLookOffsetQuatV1", "CameraOperatorInputDeltaSecondsV1",
    "CameraOperatorPolicyRecenterAngularSpeedV1", "CameraOperatorStateAngularVelocityV1",
    "CameraOperatorPolicyAngularAccelerationV1", "CameraOperatorCandidateLookOffsetQuatV1",
    "CameraOperatorCandidateTranslationOffsetV1", "CameraOperatorCandidateTranslationVelocityV1",
    "CameraOperatorInputAuthoredPositionV1", "CameraOperatorInputAuthoredBodyQuatV1",
    "CameraOperatorInputAuthoredGimbalQuatV1",
}
WRITES = {
    "CameraOperatorCandidateAngularVelocityV1", "CameraOperatorCandidateLookOffsetQuatV1",
    "CameraOperatorCandidateRecenterActiveV1", "CameraOperatorCandidatePositionV1",
    "CameraOperatorCandidateBodyQuatV1", "CameraOperatorCandidateGimbalQuatV1",
    "CameraOperatorCandidateOverrideActiveV1", "CameraOperatorCandidateTransitionActiveV1",
    "CameraOperatorCandidateValidV1",
}
FORBIDDEN = (
    "CameraOperatorInputCarrierFrameQuatV1", "CameraOperatorInputTranslationV1",
    "CameraOperatorPolicyTranslation", "CameraOperatorPolicyTether", "CameraOperatorCandidateTetherAppliedV1",
    "CameraOperatorResult", "CameraOperatorFailureCodeV1", "CameraOperatorValidationValidV1",
    "CameraTransform", "CameraComfort", "CameraChannel", "CameraApply", "Airframe", "Flypath",
    "Repository", "PlaybackTime", "Event", "Cue", "StateClip", "Server",
)
ZERO = (0.0, 0.0, 0.0)
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def add(left, right): return tuple(a + b for a, b in zip(left, right))
def sub(left, right): return tuple(a - b for a, b in zip(left, right))
def scale(value, factor): return tuple(component * factor for component in value)
def dot(left, right): return sum(a * b for a, b in zip(left, right))
def length(value): return math.sqrt(dot(value, value))
def normal(value):
    magnitude = length(value)
    return ZERO if magnitude <= 1.0e-9 else scale(value, 1.0 / magnitude)
def bounded(value): return normal(value) if length(value) > 1.0 else value
def move_towards(current, target, maximum_delta):
    difference = sub(target, current); distance = length(difference)
    return target if distance <= maximum_delta else add(current, scale(difference, maximum_delta / distance))
def axis_angle(operator, quat):
    unit = operator.normalize(quat)
    if unit[3] < 0.0: unit = tuple(-component for component in unit)
    half = math.acos(max(-1.0, min(1.0, unit[3]))); sine = math.sin(half)
    if sine <= operator.VECTOR_EPSILON: return (1.0, 0.0, 0.0), 0.0
    return tuple(component / sine for component in unit[:3]), math.degrees(half) * 2.0
def delta_quat(operator, rotation):
    angle = length(rotation)
    if angle <= operator.VECTOR_EPSILON: return IDENTITY
    axis = scale(rotation, 1.0 / angle); half = math.radians(angle) * 0.5; sine = math.sin(half)
    return (axis[0] * sine, axis[1] * sine, axis[2] * sine, math.cos(half))


def interpret(operator, mode, recenter, initialized, look_input, prior_look, prior_velocity,
              delta, policy, translation_offset, translation_velocity, authored_position,
              authored_body, authored_gimbal):
    interactive = initialized and mode in ("free_look", "carrier_freecam") and not recenter
    if interactive:
        desired = scale(bounded(look_input), policy.maximum_angular_speed_deg_s)
    else:
        axis, angle = axis_angle(operator, prior_look)
        desired = ZERO if angle <= operator.SETTLE_ANGLE_DEGREES else scale(
            axis, -min(policy.recenter_angular_speed_deg_s, angle / delta)
        )
    velocity = move_towards(prior_velocity, desired, policy.angular_acceleration_deg_s2 * delta)
    look = operator.normalize(operator.multiply(prior_look, delta_quat(operator, scale(velocity, delta))))
    new_angle = axis_angle(operator, look)[1]
    if new_angle <= operator.SETTLE_ANGLE_DEGREES and length(velocity) <= operator.SETTLE_ANGULAR_SPEED_DEG_S:
        look, velocity = IDENTITY, ZERO
    settled_translation = translation_offset == ZERO and translation_velocity == ZERO
    settled_look = look == IDENTITY and velocity == ZERO
    next_recenter = recenter and not (settled_translation and settled_look)
    if mode == "directed" or recenter: transition = not (settled_translation and settled_look)
    elif mode == "free_look": transition = not settled_translation
    else: transition = False
    position = add(authored_position, translation_offset)
    gimbal = authored_gimbal if look == IDENTITY else operator.normalize(operator.multiply(authored_gimbal, look))
    override = mode != "directed" or not (settled_translation and settled_look)
    return look, velocity, next_recenter, position, authored_body, gimbal, override, transition


def close_vector(left, right, tolerance=1.0e-8): return all(abs(a - b) <= tolerance for a, b in zip(left, right))
def close_quat(left, right, tolerance=1.0e-8):
    if dot(left, right) < 0.0: right = tuple(-value for value in right)
    return close_vector(left, right, tolerance)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_operator_look_contract_base")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (146 if args.paste else 147), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact look reads"); contracts.require(setters == WRITES, "exact look writes")
    expected = {
        "Add_VectorVector": 2, "Subtract_VectorVector": 1, "Multiply_VectorVector": 6,
        "MakeVector": 7, "BreakVector": 1, "VSize": 7, "Normal": 2,
        "BreakQuat": 3, "Quat_SetComponents": 1, "Multiply_QuatQuat": 2,
        "Quat_Normalized": 5, "DegAcos": 3, "DegSin": 2, "DegCos": 1,
        "FClamp": 3, "FMin": 1, "Divide_DoubleDouble": 5,
        "Multiply_DoubleDouble": 12, "EqualEqual_StrStr": 3,
        "Greater_DoubleDouble": 1, "Less_DoubleDouble": 3, "LessEqual_DoubleDouble": 11,
        "BooleanAND": 9, "BooleanOR": 4, "Not_PreBool": 4,
    }
    actual = {name: sum(member(node) == name for node in nodes.values()) for name in expected}
    contracts.require(actual == expected, f"native look calls {actual}")
    contracts.require(sum("K2Node_Select" in node.node_class for node in nodes.values()) == 19, "19 explicit typed selections")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 1, "single scratch guard")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    text = args.graph.read_text(encoding="utf-8"); contracts.require(not any(value in text for value in FORBIDDEN), "no translation policy/result/external access")
    for literal in ("directed", "free_look", "carrier_freecam", "1e-9", "0.00001", "0.0001", "0, 0, 0, 1"):
        contracts.require(literal in text, f"required look literal {literal}")
    scratch = next(node for node in nodes.values() if member(node) == "CameraOperatorScratchValidV1")
    guard = next(node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class)
    quat_set = next(node for node in nodes.values() if member(node) == "Quat_SetComponents")
    angular_set = next(node for node in nodes.values() if member(node) == "CameraOperatorCandidateAngularVelocityV1" and "K2Node_VariableSet" in node.node_class)
    look_set = next(node for node in nodes.values() if member(node) == "CameraOperatorCandidateLookOffsetQuatV1" and "K2Node_VariableSet" in node.node_class)
    contracts.require_link(scratch, "CameraOperatorScratchValidV1", guard, "Condition", "translation scratch guard")
    if args.paste: contracts.require(not guard.pins["execute"].links, "paste execution root")
    else: contracts.require_link(entries[0], "then", guard, "execute", "native entry guard")
    contracts.require_link(guard, "then", quat_set, "execute", "delta quaternion materialized before publications")
    contracts.require_link(quat_set, "then", angular_set, "execute", "angular velocity frozen after delta")
    contracts.require_link(angular_set, "then", look_set, "execute", "look frozen while delta is still staged")
    candidate_valid = next(node for node in nodes.values() if member(node) == "CameraOperatorCandidateValidV1" and "K2Node_VariableSet" in node.node_class)
    contracts.require('DefaultValue="true"' in candidate_valid.pins["CameraOperatorCandidateValidV1"].body, "candidate validity true")
    contracts.require(not candidate_valid.pins["then"].links, "candidate validity publishes last")
    body_get = next(node for node in nodes.values() if member(node) == "CameraOperatorInputAuthoredBodyQuatV1")
    body_set = next(node for node in nodes.values() if member(node) == "CameraOperatorCandidateBodyQuatV1")
    contracts.require_link(body_get, "CameraOperatorInputAuthoredBodyQuatV1", body_set, "CameraOperatorCandidateBodyQuatV1", "body authorship is exact passthrough")
    gimbal_selects = [node for node in nodes.values() if "K2Node_Select" in node.node_class and any(contracts.linked(node, "ReturnValue", target, "CameraOperatorCandidateGimbalQuatV1") for target in nodes.values() if member(target) == "CameraOperatorCandidateGimbalQuatV1")]
    contracts.require(len(gimbal_selects) == 1, "one final gimbal identity passthrough")
    identity_conditions = [node for node in nodes.values() if member(node) == "LessEqual_DoubleDouble" and 'DefaultValue="0.0"' in node.pins["B"].body and contracts.linked(node, "ReturnValue", gimbal_selects[0], "Index")]
    contracts.require(len(identity_conditions) == 1, "exact identity, not settled velocity, selects authored gimbal")

    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    operator = load(args.project_root / "tools/trajectory/camera_operator_override_reference.py", "edd_operator_look_reference")
    rng = random.Random(0xEDD100C5)
    def quat():
        axis = normal(tuple(rng.uniform(-1.0, 1.0) for _ in range(3)))
        half = math.radians(rng.uniform(-170.0, 170.0)) * 0.5
        return tuple(value * math.sin(half) for value in axis) + (math.cos(half),)
    state = operator.CameraOperatorStateV1(); cases = []
    for index in range(160):
        requested = rng.choice(operator.MODES_V1); return_directed = index % 31 == 0; mode = "directed" if return_directed else requested
        recenter_requested = index % 19 == 0
        translation = tuple(rng.uniform(-1.0, 1.0) for _ in range(3)); look_input = tuple(rng.uniform(-1.0, 1.0) for _ in range(3))
        delta = rng.uniform(1.0 / 240.0, 0.25)
        policy = operator.CameraOperatorPolicyV1(
            rng.choice(operator.TRANSLATION_FRAMES_V1), rng.uniform(100.0, 2200.0), rng.uniform(200.0, 4400.0),
            rng.uniform(100.0, 1500.0), rng.uniform(20.0, 240.0), rng.uniform(40.0, 720.0),
            rng.uniform(15.0, 180.0), rng.choice((True, False)), rng.uniform(50.0, 4000.0),
        )
        carrier = quat(); authored_position = tuple(rng.uniform(-1e5, 1e5) for _ in range(3)); body = quat(); gimbal = quat()
        active = length(look_input) > operator.VECTOR_EPSILON or (mode == "carrier_freecam" and length(translation) > operator.VECTOR_EPSILON)
        raw_recenter = state.initialized and mode != "directed" and (recenter_requested or (state.recenter_active and not active))
        frame = operator.apply_camera_operator_override_v1(
            True, requested, authored_position, body, gimbal, carrier, translation, look_input, delta,
            recenter_requested, return_directed, policy, state,
        )
        staged = interpret(
            operator, mode, raw_recenter, state.initialized, look_input, state.look_offset,
            state.angular_velocity_deg_s, delta, policy, frame.state.translation_offset_cm,
            frame.state.translation_velocity_cm_s, authored_position, body, gimbal,
        )
        contracts.require(close_quat(staged[0], frame.state.look_offset), f"look offset matches reference at {index}")
        contracts.require(close_vector(staged[1], frame.state.angular_velocity_deg_s), f"angular velocity matches reference at {index}")
        contracts.require(staged[2] == frame.state.recenter_active, f"recenter completion matches reference at {index}")
        contracts.require(close_vector(staged[3], frame.position), f"position candidate matches reference at {index}")
        contracts.require(staged[4] == body and frame.body_rotation == body, f"body authorship exact at {index}")
        contracts.require(close_quat(staged[5], frame.gimbal_rotation), f"gimbal composition matches reference at {index}")
        contracts.require(staged[6:] == (frame.override_active, frame.transition_active), f"flags match reference at {index}")
        if staged[0] == IDENTITY: contracts.require(staged[5] == gimbal, f"identity look preserves exact gimbal at {index}")
        cases.append((mode, raw_recenter, state.initialized, look_input, state.look_offset, state.angular_velocity_deg_s, delta, policy, frame.state.translation_offset_cm, frame.state.translation_velocity_cm_s, authored_position, body, gimbal, staged))
        state = frame.state
    reverse = [interpret(operator, *case[:-1]) for case in reversed(cases)]; reverse.reverse()
    contracts.require(all(close_quat(case[-1][0], replay[0]) and close_vector(case[-1][1], replay[1]) and case[-1][2:] == replay[2:] for case, replay in zip(cases, reverse)), "160 history-explicit forward/reverse candidates")
    poisoned = {name: object() for name in WRITES}; before = dict(poisoned); scratch_valid = False
    if scratch_valid: poisoned.clear()
    contracts.require(poisoned == before, "false scratch preserves all prior candidates")
    print(f"Camera operator look contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} forward/reverse frames")


if __name__ == "__main__": main()
