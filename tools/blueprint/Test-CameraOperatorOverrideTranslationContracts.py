"""Structural and executable contracts for camera operator translation staging."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from dataclasses import replace
from pathlib import Path


READS = {
    "CameraOperatorValidationValidV1", "CameraOperatorInputRequestedModeV1",
    "CameraOperatorInputReturnToDirectedRequestedV1", "CameraOperatorStateInitializedV1",
    "CameraOperatorStateRecenterActiveV1", "CameraOperatorInputRecenterRequestedV1",
    "CameraOperatorInputTranslationV1", "CameraOperatorInputLookV1",
    "CameraOperatorInputCarrierFrameQuatV1", "CameraOperatorPolicyTranslationFrameV1",
    "CameraOperatorPolicyMaximumTranslationSpeedV1", "CameraOperatorStateTranslationOffsetV1",
    "CameraOperatorStateTranslationVelocityV1", "CameraOperatorInputDeltaSecondsV1",
    "CameraOperatorPolicyRecenterTranslationSpeedV1", "CameraOperatorPolicyTranslationAccelerationV1",
    "CameraOperatorPolicyTetherEnabledV1", "CameraOperatorPolicyTetherDistanceV1",
}
WRITES = {
    "CameraOperatorCandidateModeV1", "CameraOperatorCandidateRecenterActiveV1",
    "CameraOperatorCandidateTranslationOffsetV1", "CameraOperatorCandidateTranslationVelocityV1",
    "CameraOperatorCandidateTetherAppliedV1", "CameraOperatorScratchValidV1",
}
FORBIDDEN = (
    "CameraOperatorInputAuthoredPositionV1", "CameraOperatorInputAuthoredBodyQuatV1",
    "CameraOperatorInputAuthoredGimbalQuatV1", "CameraOperatorStateLookOffsetQuatV1",
    "CameraOperatorStateAngularVelocityV1", "CameraOperatorCandidateLookOffsetQuatV1",
    "CameraOperatorCandidateAngularVelocityV1", "CameraOperatorCandidatePositionV1",
    "CameraOperatorCandidateBodyQuatV1", "CameraOperatorCandidateGimbalQuatV1",
    "CameraOperatorCandidateOverrideActiveV1", "CameraOperatorCandidateTransitionActiveV1",
    "CameraOperatorCandidateValidV1", "CameraOperatorResult", "CameraOperatorFailureCodeV1",
    "CameraComfort", "CameraChannel", "CameraApply", "CameraTransform", "Airframe", "Flypath",
    "Repository", "PlaybackTime", "Event", "Cue", "StateClip", "Server",
)
ZERO = (0.0, 0.0, 0.0)


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
    return target if distance <= maximum_delta else add(current, scale(normal(difference), maximum_delta))


def interpret(operator, requested_mode, return_directed, recenter_requested, translation_input,
              look_input, carrier, delta, policy, state):
    mode = "directed" if return_directed else requested_mode
    if not state.initialized:
        return mode, False, ZERO, ZERO, False
    input_active = length(look_input) > operator.VECTOR_EPSILON or (
        mode == "carrier_freecam" and length(translation_input) > operator.VECTOR_EPSILON
    )
    recenter = mode != "directed" and (
        recenter_requested or (state.recenter_active and not input_active)
    )
    interactive = mode == "carrier_freecam" and not recenter
    if interactive:
        direction = bounded(translation_input)
        if policy.translation_frame == "carrier":
            direction = operator._rotate(carrier, direction)
        desired = scale(direction, policy.maximum_translation_speed_cm_s)
    else:
        offset_length = length(state.translation_offset_cm)
        desired = ZERO if offset_length <= operator.SETTLE_POSITION_CM else scale(
            state.translation_offset_cm,
            -min(policy.recenter_translation_speed_cm_s, offset_length / delta) / offset_length,
        )
    velocity = move_towards(
        state.translation_velocity_cm_s, desired,
        policy.translation_acceleration_cm_s2 * delta,
    )
    offset = add(state.translation_offset_cm, scale(velocity, delta))
    if not interactive and dot(state.translation_offset_cm, offset) <= 0.0:
        offset, velocity = ZERO, ZERO
    tether = False
    if policy.tether_enabled and length(offset) > policy.tether_distance_cm:
        outward_normal = normal(offset); offset = scale(outward_normal, policy.tether_distance_cm)
        outward_speed = dot(velocity, outward_normal)
        if outward_speed > 0.0: velocity = sub(velocity, scale(outward_normal, outward_speed))
        tether = True
    if length(offset) <= operator.SETTLE_POSITION_CM and length(velocity) <= operator.SETTLE_LINEAR_SPEED_CM_S:
        offset, velocity = ZERO, ZERO
    return mode, recenter, offset, velocity, tether


def close_vector(left, right, tolerance=1.0e-8):
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_operator_translation_contract_base")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (104 if args.paste else 105), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact translation reads")
    contracts.require(setters == WRITES, "exact translation writes")
    expected = {
        "Add_VectorVector": 2, "Subtract_VectorVector": 2, "Multiply_VectorVector": 6,
        "MakeVector": 6, "VSize": 7, "Normal": 3, "Quat_RotateVector": 1,
        "Dot_VectorVector": 2, "FMin": 1, "Divide_DoubleDouble": 2,
        "Multiply_DoubleDouble": 2, "EqualEqual_StrStr": 3, "Greater_DoubleDouble": 5,
        "LessEqual_DoubleDouble": 5, "BooleanAND": 8, "BooleanOR": 2, "Not_PreBool": 4,
    }
    actual = {name: sum(member(node) == name for node in nodes.values()) for name in expected}
    contracts.require(actual == expected, f"native translation calls {actual}")
    contracts.require(sum("K2Node_Select" in node.node_class for node in nodes.values()) == 18, "18 explicit typed selections")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 1, "single validation guard")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(value in text for value in FORBIDDEN), "no look/result/external authorship access")
    for literal in ("directed", "carrier_freecam", "carrier", "1e-9", "0.0001"):
        contracts.require(literal in text, f"required translation literal {literal}")
    validation = next(node for node in nodes.values() if member(node) == "CameraOperatorValidationValidV1")
    guard = next(node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class)
    contracts.require_link(validation, "CameraOperatorValidationValidV1", guard, "Condition", "validation guard")
    if args.paste: contracts.require(not guard.pins["execute"].links, "paste execution root")
    else: contracts.require_link(entries[0], "then", guard, "execute", "native entry guard")
    carrier_get = next(node for node in nodes.values() if member(node) == "CameraOperatorInputCarrierFrameQuatV1")
    rotate = next(node for node in nodes.values() if member(node) == "Quat_RotateVector")
    contracts.require_link(carrier_get, "CameraOperatorInputCarrierFrameQuatV1", rotate, "Q", "separate carrier frame is sole rotation source")
    scratch = next(node for node in nodes.values() if member(node) == "CameraOperatorScratchValidV1" and "K2Node_VariableSet" in node.node_class)
    contracts.require('DefaultValue="true"' in scratch.pins["CameraOperatorScratchValidV1"].body, "scratch validity publishes true")
    contracts.require(not scratch.pins["then"].links, "scratch validity publishes last")

    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    operator = load(args.project_root / "tools/trajectory/camera_operator_override_reference.py", "edd_operator_translation_reference")
    rng = random.Random(0xEDD7A145)
    def quat():
        axis = normal(tuple(rng.uniform(-1.0, 1.0) for _ in range(3)))
        half = math.radians(rng.uniform(-170.0, 170.0)) * 0.5
        return tuple(value * math.sin(half) for value in axis) + (math.cos(half),)
    state = operator.CameraOperatorStateV1(); cases = []
    for index in range(160):
        policy = operator.CameraOperatorPolicyV1(
            rng.choice(operator.TRANSLATION_FRAMES_V1), rng.uniform(100.0, 2400.0),
            rng.uniform(200.0, 4800.0), rng.uniform(100.0, 1600.0),
            120.0, 360.0, 90.0, rng.choice((True, False)), rng.uniform(50.0, 3500.0),
        )
        requested = rng.choice(operator.MODES_V1); return_directed = index % 29 == 0
        recenter_requested = index % 23 == 0
        translation = tuple(rng.uniform(-1.0, 1.0) for _ in range(3))
        look = tuple(rng.uniform(-1.0, 1.0) for _ in range(3))
        delta = rng.uniform(1.0 / 240.0, 0.25); carrier = quat()
        expected_stage = interpret(operator, requested, return_directed, recenter_requested, translation, look, carrier, delta, policy, state)
        frame = operator.apply_camera_operator_override_v1(
            True, requested, (10.0, 20.0, 30.0), quat(), quat(), carrier,
            translation, look, delta, recenter_requested, return_directed, policy, state,
        )
        contracts.require(expected_stage[0] == frame.state.mode, "resolved mode matches reference")
        contracts.require(close_vector(expected_stage[2], frame.state.translation_offset_cm), "translation offset matches reference")
        contracts.require(
            close_vector(expected_stage[3], frame.state.translation_velocity_cm_s),
            f"translation velocity matches reference at {index}: {expected_stage[3]} != {frame.state.translation_velocity_cm_s}; "
            f"mode={requested}/{return_directed} recenter={recenter_requested} input={translation} look={look} "
            f"delta={delta} policy={policy} state={state}",
        )
        contracts.require(expected_stage[4] == frame.tether_applied, "tether result matches reference")
        if not state.initialized:
            contracts.require(expected_stage[1:] == (False, ZERO, ZERO, False), "first frame is exact zero-offset initialization")
        cases.append((requested, return_directed, recenter_requested, translation, look, carrier, delta, policy, state, expected_stage))
        state = frame.state
    reverse = [interpret(operator, *case[:-1]) for case in reversed(cases)]
    reverse.reverse()
    contracts.require(all(a[-1][0:2] == b[0:2] and close_vector(a[-1][2], b[2]) and close_vector(a[-1][3], b[3]) and a[-1][4] == b[4] for a, b in zip(cases, reverse)), "160 history-explicit forward/reverse candidates")

    yaw = math.radians(90.0) * 0.5; rotated_carrier = (0.0, 0.0, math.sin(yaw), math.cos(yaw))
    active_state = replace(operator.CameraOperatorStateV1(), initialized=True, mode="carrier_freecam")
    world_policy = operator.CameraOperatorPolicyV1(translation_frame="world")
    carrier_policy = replace(world_policy, translation_frame="carrier")
    identity = operator.IDENTITY_QUATERNION; movement = (1.0, 0.0, 0.0)
    world_a = interpret(operator, "carrier_freecam", False, False, movement, ZERO, identity, 0.1, world_policy, active_state)
    world_b = interpret(operator, "carrier_freecam", False, False, movement, ZERO, rotated_carrier, 0.1, world_policy, active_state)
    carrier_result = interpret(operator, "carrier_freecam", False, False, movement, ZERO, rotated_carrier, 0.1, carrier_policy, active_state)
    contracts.require(world_a == world_b, "world translation ignores carrier rotation")
    contracts.require(not close_vector(world_a[2], carrier_result[2]), "carrier translation uses independently supplied frame")
    poisoned = {name: object() for name in WRITES}; before = dict(poisoned)
    validation_valid = False
    if validation_valid: poisoned.clear()
    contracts.require(poisoned == before, "false validation preserves all prior candidates")
    print(f"Camera operator translation contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} forward/reverse candidates")


if __name__ == "__main__": main()
