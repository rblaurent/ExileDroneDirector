"""Exact contracts for the history-free airframe/gimbal desired-pose solver."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


INPUTS = (
    "AirframeGimbalInputCurrentVelocityV1",
    "AirframeGimbalInputLookAheadVelocityV1",
    "AirframeGimbalInputAccelerationV1",
    "AirframeGimbalInputJerkV1",
    "AirframeGimbalInputAuthoredBodyQuatV1",
    "AirframeGimbalInputAuthoredGimbalQuatV1",
    "AirframeGimbalInputPathFollowWeightV1",
    "AirframeGimbalInputHorizonStabilizationWeightV1",
    "AirframeGimbalInputBankGainV1",
    "AirframeGimbalInputMaxBankDegreesV1",
    "AirframeGimbalInputCameraUptiltDegreesV1",
    "AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1",
    "AirframeGimbalInputMaxJerkCmPerSecondCubedV1",
    "AirframeGimbalInputMinimumTurnRadiusCmV1",
)
RESULTS = (
    "AirframeGimbalResultBodyQuatV1",
    "AirframeGimbalResultGimbalQuatV1",
    "AirframeGimbalResultPathQuatV1",
    "AirframeGimbalResultSpeedCmPerSecondV1",
    "AirframeGimbalResultLateralAccelerationCmPerSecondSquaredV1",
    "AirframeGimbalResultTurnRadiusCmV1",
    "AirframeGimbalResultBankDegreesV1",
    "AirframeGimbalResultValidV1",
)
EPSILON = "1e-9"
GRAVITY = "980.665"
NEGATIVE_RADIANS_TO_DEGREES = "-57.29577951308232"
FINITE_MIN = "-1.7976931348623157e+308"
FINITE_MAX = "1.7976931348623157e+308"


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_solve_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return None if match is None else match.group(1)


def members(nodes, name, node_class=None):
    return [
        node for node in nodes.values()
        if f'MemberName="{name}"' in node.text
        and (node_class is None or node_class in node.node_class)
    ]


def exact(nodes, c, name, node_class="K2Node_CallFunction"):
    found = members(nodes, name, node_class)
    c.require(len(found) == 1, f"one exact {node_class} {name}; found {len(found)}")
    return found[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load(args.project_root)
    nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (99 if args.paste else 100), f"solver node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")

    reset = exact(nodes, c, "ResetAirframeGimbalV1")
    validate = exact(nodes, c, "ValidateAirframeGimbalInputsV1")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 2, "validation and physical commit branches")
    validation_branch = next(node for node in branches if c.linked(validate, "then", node, "execute"))
    physical_branch = next(node for node in branches if node is not validation_branch)
    if args.paste:
        c.require(not reset.pins["execute"].links, "paste reset root must be exposed")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry-to-reset seam")
    c.require_link(reset, "then", validate, "execute", "reset-before-validation order")
    c.require_link(validate, "then", validation_branch, "execute", "validation-before-math order")
    stage_valid = exact(nodes, c, "AirframeGimbalStageValidV1", "K2Node_VariableGet")
    c.require_link(stage_valid, "AirframeGimbalStageValidV1", validation_branch, "Condition", "validated-stage guard")
    c.require(not members(nodes, "AirframeGimbalStageValidV1", "K2Node_VariableSet"), "solver cannot forge validation state")

    getters = {}
    for name in INPUTS:
        getters[name] = exact(nodes, c, name, "K2Node_VariableGet")
        c.require(not members(nodes, name, "K2Node_VariableSet"), f"solver cannot mutate input {name}")

    calls = {}
    for name in (
        "VSize", "Normal", "Quat_GetAxisX", "Quat_GetAxisZ", "Dot_VectorVector",
        "Greater_DoubleDouble", "GreaterEqual_DoubleDouble", "LessEqual_DoubleDouble",
        "BooleanOR", "BooleanAND", "MakeRotFromXZ", "Conv_RotatorToQuaternion",
        "Quat_Normalized", "Subtract_VectorVector", "Multiply_VectorVector",
        "Multiply_DoubleDouble", "Divide_DoubleDouble", "Quat_GetAxisY", "Atan2",
        "Subtract_DoubleDouble", "FClamp", "MakeVector", "Quat_MakeFromEuler",
        "Multiply_QuatQuat", "Quat_Slerp",
    ):
        calls[name] = members(nodes, name, "K2Node_CallFunction")

    c.require(len(calls["VSize"]) == 5, "five vector magnitudes")
    c.require(len(calls["Normal"]) == 2, "current and look-ahead normalization only")
    c.require(len(calls["Quat_Normalized"]) == 5, "path, banked path, body, locked gimbal, final gimbal normalization")
    c.require(len(calls["Dot_VectorVector"]) == 3, "vertical, forward-acceleration, and signed-bank dots")
    c.require(len(calls["MakeVector"]) == 3, "forward scalar replication plus bank and uptilt Euler vectors")
    c.require(len(calls["Quat_MakeFromEuler"]) == 2, "bank and uptilt quaternions")
    c.require(len(calls["Multiply_QuatQuat"]) == 2, "banked path and body-locked gimbal composition")
    c.require(len(calls["Quat_Slerp"]) == 2, "body and gimbal blending")

    current = getters["AirframeGimbalInputCurrentVelocityV1"]
    lookahead = getters["AirframeGimbalInputLookAheadVelocityV1"]
    authored_body = getters["AirframeGimbalInputAuthoredBodyQuatV1"]
    authored_forward = exact(nodes, c, "Quat_GetAxisX")
    authored_up = exact(nodes, c, "Quat_GetAxisZ")
    c.require_link(authored_body, "AirframeGimbalInputAuthoredBodyQuatV1", authored_forward, "Q", "authored forward source")
    c.require_link(authored_body, "AirframeGimbalInputAuthoredBodyQuatV1", authored_up, "Q", "authored up source")

    speed = next(node for node in calls["VSize"] if c.linked(current, "AirframeGimbalInputCurrentVelocityV1", node, "A"))
    lookahead_speed = next(node for node in calls["VSize"] if c.linked(lookahead, "AirframeGimbalInputLookAheadVelocityV1", node, "A"))
    current_has = next(node for node in calls["Greater_DoubleDouble"] if c.linked(speed, "ReturnValue", node, "A"))
    lookahead_has = next(node for node in calls["Greater_DoubleDouble"] if c.linked(lookahead_speed, "ReturnValue", node, "A"))
    c.require(default(current_has, "B") == default(lookahead_has, "B") == EPSILON, "velocity fallback epsilon")
    current_normal = next(node for node in calls["Normal"] if c.linked(current, "AirframeGimbalInputCurrentVelocityV1", node, "A"))
    lookahead_normal = next(node for node in calls["Normal"] if c.linked(lookahead, "AirframeGimbalInputLookAheadVelocityV1", node, "A"))
    for node in (current_normal, lookahead_normal):
        c.require(default(node, "Tolerance") == EPSILON, "normalization tolerance")
    vector_selects = [node for node in nodes.values() if "K2Node_Select" in node.node_class and 'PinType.PinCategory="struct"' in node.text]
    c.require(len(vector_selects) == 3, "current, predicted, and vertical-up vector selects")
    current_forward = next(node for node in vector_selects if c.linked(current_has, "ReturnValue", node, "Index"))
    predicted_forward = next(node for node in vector_selects if c.linked(lookahead_has, "ReturnValue", node, "Index"))
    c.require_link(authored_forward, "ReturnValue", current_forward, "Option 0", "stationary authored-forward fallback")
    c.require_link(current_normal, "ReturnValue", current_forward, "Option 1", "moving current-forward source")
    c.require_link(current_forward, "ReturnValue", predicted_forward, "Option 0", "zero look-ahead fallback")
    c.require_link(lookahead_normal, "ReturnValue", predicted_forward, "Option 1", "look-ahead direction source")

    vertical_dot = next(node for node in calls["Dot_VectorVector"] if c.linked(predicted_forward, "ReturnValue", node, "A"))
    c.require(default(vertical_dot, "B") in ("0, 0, 1", "0,0,1"), "world-up vertical dot")
    vertical_positive = next(node for node in calls["GreaterEqual_DoubleDouble"] if c.linked(vertical_dot, "ReturnValue", node, "A"))
    vertical_negative = next(node for node in calls["LessEqual_DoubleDouble"] if c.linked(vertical_dot, "ReturnValue", node, "A"))
    c.require(default(vertical_positive, "B") == "0.999999", "positive vertical threshold")
    c.require(default(vertical_negative, "B") == "-0.999999", "negative vertical threshold")
    vertical_or = exact(nodes, c, "BooleanOR")
    c.require_link(vertical_positive, "ReturnValue", vertical_or, "A", "positive vertical guard")
    c.require_link(vertical_negative, "ReturnValue", vertical_or, "B", "negative vertical guard")
    up_hint = next(node for node in vector_selects if c.linked(vertical_or, "ReturnValue", node, "Index"))
    c.require(default(up_hint, "Option 0") in ("0, 0, 1", "0,0,1"), "normal world-up hint")
    c.require_link(authored_up, "ReturnValue", up_hint, "Option 1", "vertical authored-up hint")
    make_rot = exact(nodes, c, "MakeRotFromXZ")
    c.require_link(predicted_forward, "ReturnValue", make_rot, "X", "path forward basis")
    c.require_link(up_hint, "ReturnValue", make_rot, "Z", "path up basis")
    rotator_to_quat = exact(nodes, c, "Conv_RotatorToQuaternion")
    path_quat = next(node for node in calls["Quat_Normalized"] if c.linked(rotator_to_quat, "ReturnValue", node, "Q"))
    c.require_link(make_rot, "ReturnValue", rotator_to_quat, "InRot", "path rotator conversion")

    accel = getters["AirframeGimbalInputAccelerationV1"]
    jerk = getters["AirframeGimbalInputJerkV1"]
    accel_magnitude = next(node for node in calls["VSize"] if c.linked(accel, "AirframeGimbalInputAccelerationV1", node, "A"))
    jerk_magnitude = next(node for node in calls["VSize"] if c.linked(jerk, "AirframeGimbalInputJerkV1", node, "A"))
    max_accel = getters["AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1"]
    max_jerk = getters["AirframeGimbalInputMaxJerkCmPerSecondCubedV1"]
    accel_ok = next(node for node in calls["LessEqual_DoubleDouble"] if c.linked(accel_magnitude, "ReturnValue", node, "A"))
    jerk_ok = next(node for node in calls["LessEqual_DoubleDouble"] if c.linked(jerk_magnitude, "ReturnValue", node, "A"))
    c.require_link(max_accel, "AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1", accel_ok, "B", "acceleration limit")
    c.require_link(max_jerk, "AirframeGimbalInputMaxJerkCmPerSecondCubedV1", jerk_ok, "B", "jerk limit")
    forward_dot = next(node for node in calls["Dot_VectorVector"] if c.linked(accel, "AirframeGimbalInputAccelerationV1", node, "A") and c.linked(current_forward, "ReturnValue", node, "B"))
    forward_components = next(node for node in calls["MakeVector"] if all(c.linked(forward_dot, "ReturnValue", node, pin) for pin in ("X", "Y", "Z")))
    forward_accel = exact(nodes, c, "Multiply_VectorVector", None)
    c.require_link(current_forward, "ReturnValue", forward_accel, "A", "forward unit vector scale")
    c.require_link(forward_components, "ReturnValue", forward_accel, "B", "forward scalar replication")
    lateral_vector = exact(nodes, c, "Subtract_VectorVector", None)
    c.require_link(accel, "AirframeGimbalInputAccelerationV1", lateral_vector, "A", "lateral source acceleration")
    c.require_link(forward_accel, "ReturnValue", lateral_vector, "B", "remove forward acceleration")
    lateral = next(node for node in calls["VSize"] if c.linked(lateral_vector, "ReturnValue", node, "A"))
    lateral_has = next(node for node in calls["Greater_DoubleDouble"] if c.linked(lateral, "ReturnValue", node, "A"))
    c.require(default(lateral_has, "B") == EPSILON, "lateral epsilon")
    has_turn = next(node for node in calls["BooleanAND"] if c.linked(current_has, "ReturnValue", node, "A") and c.linked(lateral_has, "ReturnValue", node, "B"))

    multiplies = calls["Multiply_DoubleDouble"]
    speed_squared = next(node for node in multiplies if c.linked(speed, "ReturnValue", node, "A") and c.linked(speed, "ReturnValue", node, "B"))
    real_selects = [node for node in nodes.values() if "K2Node_Select" in node.node_class and 'PinType.PinCategory="real"' in node.text]
    c.require(len(real_selects) == 2, "safe denominator and public radius selects")
    safe_lateral = next(node for node in real_selects if default(node, "Option 0") == "1.0")
    c.require_link(has_turn, "ReturnValue", safe_lateral, "Index", "safe denominator condition")
    c.require_link(lateral, "ReturnValue", safe_lateral, "Option 1", "turn lateral denominator")
    radius_raw = exact(nodes, c, "Divide_DoubleDouble")
    c.require_link(speed_squared, "ReturnValue", radius_raw, "A", "turn-radius numerator")
    c.require_link(safe_lateral, "ReturnValue", radius_raw, "B", "zero-safe turn-radius denominator")
    radius = next(node for node in real_selects if default(node, "Option 0") == "0.0")
    c.require_link(has_turn, "ReturnValue", radius, "Index", "straight-radius condition")
    c.require_link(radius_raw, "ReturnValue", radius, "Option 1", "finite-turn radius")
    radius_minimum = next(node for node in calls["GreaterEqual_DoubleDouble"] if c.linked(radius_raw, "ReturnValue", node, "A"))
    c.require_link(getters["AirframeGimbalInputMinimumTurnRadiusCmV1"], "AirframeGimbalInputMinimumTurnRadiusCmV1", radius_minimum, "B", "minimum radius limit")
    bool_selects = [
        node for node in nodes.values()
        if "K2Node_Select" in node.node_class
        and 'PinType.PinCategory="bool"' in node.pins["ReturnValue"].body
    ]
    c.require(len(bool_selects) == 1, "one no-turn radius acceptance select")
    radius_ok = bool_selects[0]
    c.require(default(radius_ok, "Option 0") == "true", "straight/stationary radius acceptance")
    c.require_link(has_turn, "ReturnValue", radius_ok, "Index", "radius acceptance condition")
    c.require_link(radius_minimum, "ReturnValue", radius_ok, "Option 1", "finite-turn radius acceptance")

    path_right = exact(nodes, c, "Quat_GetAxisY")
    c.require_link(path_quat, "ReturnValue", path_right, "Q", "path-right basis")
    signed_accel = next(node for node in calls["Dot_VectorVector"] if c.linked(accel, "AirframeGimbalInputAccelerationV1", node, "A") and c.linked(path_right, "ReturnValue", node, "B"))
    atan = exact(nodes, c, "Atan2")
    c.require_link(signed_accel, "ReturnValue", atan, "Y", "signed bank numerator")
    c.require(default(atan, "X") == GRAVITY, "bank gravity denominator")
    degrees_negative = next(node for node in multiplies if default(node, "B") == NEGATIVE_RADIANS_TO_DEGREES)
    c.require_link(atan, "ReturnValue", degrees_negative, "A", "radians-to-negative-degrees")
    gained_bank = next(node for node in multiplies if c.linked(degrees_negative, "ReturnValue", node, "A"))
    c.require_link(getters["AirframeGimbalInputBankGainV1"], "AirframeGimbalInputBankGainV1", gained_bank, "B", "bank gain")
    negative_max = exact(nodes, c, "Subtract_DoubleDouble")
    c.require(default(negative_max, "A") == "0.0", "negative max-bank origin")
    c.require_link(getters["AirframeGimbalInputMaxBankDegreesV1"], "AirframeGimbalInputMaxBankDegreesV1", negative_max, "B", "negative max-bank")
    bank = exact(nodes, c, "FClamp")
    c.require_link(gained_bank, "ReturnValue", bank, "Value", "unclamped bank")
    c.require_link(negative_max, "ReturnValue", bank, "Min", "bank lower clamp")
    c.require_link(getters["AirframeGimbalInputMaxBankDegreesV1"], "AirframeGimbalInputMaxBankDegreesV1", bank, "Max", "bank upper clamp")

    make_vectors = calls["MakeVector"]
    bank_euler = next(node for node in make_vectors if c.linked(bank, "ReturnValue", node, "X"))
    c.require(default(bank_euler, "Y") == default(bank_euler, "Z") == "0.0", "bank around local X only")
    uptilt_euler = next(node for node in make_vectors if c.linked(getters["AirframeGimbalInputCameraUptiltDegreesV1"], "AirframeGimbalInputCameraUptiltDegreesV1", node, "Y"))
    c.require(default(uptilt_euler, "X") == default(uptilt_euler, "Z") == "0.0", "uptilt on Unreal Euler Y only")
    quat_from_euler = calls["Quat_MakeFromEuler"]
    bank_quat = next(node for node in quat_from_euler if c.linked(bank_euler, "ReturnValue", node, "Euler"))
    uptilt_quat = next(node for node in quat_from_euler if c.linked(uptilt_euler, "ReturnValue", node, "Euler"))
    quat_products = calls["Multiply_QuatQuat"]
    banked_raw = next(node for node in quat_products if c.linked(path_quat, "ReturnValue", node, "A"))
    c.require_link(bank_quat, "ReturnValue", banked_raw, "B", "path-local bank composition")
    banked = next(node for node in calls["Quat_Normalized"] if c.linked(banked_raw, "ReturnValue", node, "Q"))
    slerps = calls["Quat_Slerp"]
    body_raw = next(node for node in slerps if c.linked(authored_body, "AirframeGimbalInputAuthoredBodyQuatV1", node, "A"))
    c.require_link(banked, "ReturnValue", body_raw, "B", "path-follow body target")
    c.require_link(getters["AirframeGimbalInputPathFollowWeightV1"], "AirframeGimbalInputPathFollowWeightV1", body_raw, "Alpha", "path-follow weight")
    body = next(node for node in calls["Quat_Normalized"] if c.linked(body_raw, "ReturnValue", node, "Q"))
    locked_raw = next(node for node in quat_products if c.linked(body, "ReturnValue", node, "A"))
    c.require_link(uptilt_quat, "ReturnValue", locked_raw, "B", "body-local uptilt composition")
    locked = next(node for node in calls["Quat_Normalized"] if c.linked(locked_raw, "ReturnValue", node, "Q"))
    gimbal_raw = next(node for node in slerps if c.linked(locked, "ReturnValue", node, "A"))
    c.require_link(getters["AirframeGimbalInputAuthoredGimbalQuatV1"], "AirframeGimbalInputAuthoredGimbalQuatV1", gimbal_raw, "B", "authored gimbal target")
    c.require_link(getters["AirframeGimbalInputHorizonStabilizationWeightV1"], "AirframeGimbalInputHorizonStabilizationWeightV1", gimbal_raw, "Alpha", "horizon stabilization weight")
    gimbal = next(node for node in calls["Quat_Normalized"] if c.linked(gimbal_raw, "ReturnValue", node, "Q"))

    finite_sources = (speed, lateral, radius, bank)
    finite_guards = []
    for source in finite_sources:
        lowers = [node for node in calls["GreaterEqual_DoubleDouble"] if c.linked(source, "ReturnValue", node, "A") and default(node, "B") == FINITE_MIN]
        uppers = [node for node in calls["LessEqual_DoubleDouble"] if c.linked(source, "ReturnValue", node, "A") and default(node, "B") == FINITE_MAX]
        c.require(len(lowers) == len(uppers) == 1, f"finite diagnostic guard for {source.name}")
        finite = [node for node in calls["BooleanAND"] if c.linked(lowers[0], "ReturnValue", node, "A") and c.linked(uppers[0], "ReturnValue", node, "B")]
        c.require(len(finite) == 1, f"finite diagnostic conjunction for {source.name}")
        finite_guards.append(finite[0])
    c.require_link(validation_branch, "then", physical_branch, "execute", "validated math reaches physical gate")
    aggregate_sources = {accel_ok.name, jerk_ok.name, radius_ok.name, *(guard.name for guard in finite_guards)}
    aggregate_ands = [
        node for node in calls["BooleanAND"]
        if node.name not in {has_turn.name, *(guard.name for guard in finite_guards)}
    ]
    c.require(len(aggregate_ands) == 6, "seven physical guards require six aggregate conjunctions")
    c.require(any(c.linked(node, "ReturnValue", physical_branch, "Condition") for node in aggregate_ands), "complete physical guard drives commit")
    linked_aggregate_inputs = {
        source.name
        for source in (accel_ok, jerk_ok, radius_ok, *finite_guards)
        if any(c.linked(source, "ReturnValue", node, pin) for node in aggregate_ands for pin in ("A", "B"))
    }
    c.require(linked_aggregate_inputs == aggregate_sources, "every physical guard participates in aggregate")

    publications = []
    expected_sources = (body, gimbal, path_quat, speed, lateral, radius, bank)
    for name, source in zip(RESULTS[:-1], expected_sources):
        setter = exact(nodes, c, name, "K2Node_VariableSet")
        c.require_link(source, "ReturnValue", setter, name, f"published {name} source")
        publications.append(setter)
    publish_valid = exact(nodes, c, RESULTS[-1], "K2Node_VariableSet")
    c.require(default(publish_valid, RESULTS[-1]) == "true", "result validity publishes true")
    publications.append(publish_valid)
    c.require_link(physical_branch, "then", publications[0], "execute", "physical acceptance begins atomic publication")
    for left, right in zip(publications, publications[1:]):
        c.require_link(left, "then", right, "execute", "valid-last atomic publication order")

    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knots forbidden")
    c.require(not any("ContainerType=Array" in node.text for node in nodes.values()), "solver must remain scalar/stateless")
    print(f"Airframe/gimbal solve contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
