"""Build the deterministic history-free airframe/gimbal desired-pose solver."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "SolveAirframeGimbalV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
EPSILON = "1e-9"
GRAVITY = "980.665"
NEGATIVE_RADIANS_TO_DEGREES = "-57.29577951308232"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_solve_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, value: str):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
        "rotator": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Rotator\'"'),
    }[value]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', 'PinType.ContainerType=None', line, 1)

    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/airframe-gimbal-native-node-forms.eddgraph")
    quat_native = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    horizon = bp.read_blocks(args.project_root / "tools/blueprint/templates/horizon-node-forms.eddgraph")
    position = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-compiled-position-route-v1.eddgraph")
    route_velocity = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/compute-position-route-velocities-v1.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    forms.update({
        **{f"native_{member}": bp.find_block(native, rf'MemberName="{member}"') for member in (
            "Quat_GetAxisX", "Quat_GetAxisY", "Quat_GetAxisZ", "Quat_MakeFromEuler", "Conv_RotatorToQuaternion",
            "Dot_VectorVector", "Normal", "Atan2",
        )},
        "quat_slerp": bp.find_block(quat_native, r'MemberName="Quat_Slerp"'),
        "quat_normalized": bp.find_block(quat_native, r'MemberName="Quat_Normalized"'),
        "quat_multiply": bp.find_block(quat_compiler, r'MemberName="Multiply_QuatQuat"'),
        "vsize": bp.find_block(quat_compiler, r'MemberName="VSize"'),
        "make_rot_xz": bp.find_block(horizon, r'MemberName="MakeRotFromXZ"'),
        "rotator_to_quat": bp.find_block(native, r'MemberName="Conv_RotatorToQuaternion"'),
        "vector_subtract": bp.find_block(position, r'MemberName="Subtract_VectorVector"'),
        "vector_multiply": bp.find_block(position, r'MemberName="Multiply_VectorVector"'),
        "make_vector": bp.find_block(route_velocity, r'MemberName="MakeVector"'),
        "select": bp.find_block(public_list, r'^Begin Object Class=/Script/BlueprintGraph.K2Node_Select '),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, value: str):
        scalar.retarget_variable(node, name, "vector" if value == "quat" else value)
        pin_kind(node, name, value)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", value)

    def get(name: str, value: str, x: int, y: int):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, value)
        return node

    def set_value(name: str, value: str, x: int, y: int, default=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, value)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def call(member: str, x: int, y: int):
        node = b.add(f"call_{member}_{len(b.nodes)}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1,
            ),
        )
        return node

    def native_call(member: str, x: int, y: int):
        return b.add(f"native_{member}_{len(b.nodes)}", f"native_{member}", x, y)

    def compare(member: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, "real")
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def bool_op(member: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.add(f"bool_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def select(condition, condition_pin: str, false_source, false_pin: str, true_source, true_pin: str, value: str, x: int, y: int, false_default=None, true_default=None):
        node = b.add(f"select_{value}_{len(b.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"):
            pin_kind(node, pin, value)
        pin_kind(node, "Index", "bool")
        bp.connect(condition, condition_pin, node, "Index")
        if false_source is None:
            scalar.set_default(node, "Option 0", false_default)
        else:
            bp.connect(false_source, false_pin, node, "Option 0")
        if true_source is None:
            scalar.set_default(node, "Option 1", true_default)
        else:
            bp.connect(true_source, true_pin, node, "Option 1")
        return node

    def vsize(source, source_pin: str, x: int, y: int):
        node = b.add(f"vsize_{len(b.nodes)}", "vsize", x, y)
        bp.connect(source, source_pin, node, "A")
        return node

    def normalize_vector(source, source_pin: str, x: int, y: int):
        node = native_call("Normal", x, y)
        bp.connect(source, source_pin, node, "A")
        scalar.set_default(node, "Tolerance", EPSILON)
        return node

    def vector_axis(quat, quat_pin: str, axis: str, x: int, y: int):
        node = native_call(f"Quat_GetAxis{axis}", x, y)
        bp.connect(quat, quat_pin, node, "Q")
        return node

    def make_vector(x_source, x_pin, y_source, y_pin, z_source, z_pin, px, py, defaults=("0.0", "0.0", "0.0")):
        node = b.add(f"make_vector_{len(b.nodes)}", "make_vector", px, py)
        for pin, source, source_pin, default in zip(("X", "Y", "Z"), (x_source, y_source, z_source), (x_pin, y_pin, z_pin), defaults):
            pin_kind(node, pin, "real")
            if source is None:
                scalar.set_default(node, pin, default)
            else:
                bp.connect(source, source_pin, node, pin)
        pin_kind(node, "ReturnValue", "vector")
        return node

    reset = call("ResetAirframeGimbalV1", 256, 3200)
    validate = call("ValidateAirframeGimbalInputsV1", 512, 3200)
    bp.connect(b.entry, "then", reset, "execute")
    bp.connect(reset, "then", validate, "execute")
    stage_valid = get("AirframeGimbalStageValidV1", "bool", 512, 3040)
    valid_branch = b.add("valid_branch", "branch", 768, 3200)
    bp.connect(validate, "then", valid_branch, "execute")
    bp.connect(stage_valid, "AirframeGimbalStageValidV1", valid_branch, "Condition")

    current = get("AirframeGimbalInputCurrentVelocityV1", "vector", 0, 0)
    lookahead = get("AirframeGimbalInputLookAheadVelocityV1", "vector", 0, 160)
    accel = get("AirframeGimbalInputAccelerationV1", "vector", 0, 320)
    jerk = get("AirframeGimbalInputJerkV1", "vector", 0, 480)
    authored_body = get("AirframeGimbalInputAuthoredBodyQuatV1", "quat", 0, 640)
    authored_gimbal = get("AirframeGimbalInputAuthoredGimbalQuatV1", "quat", 0, 800)
    path_weight = get("AirframeGimbalInputPathFollowWeightV1", "real", 0, 960)
    horizon_weight = get("AirframeGimbalInputHorizonStabilizationWeightV1", "real", 0, 1120)
    bank_gain = get("AirframeGimbalInputBankGainV1", "real", 0, 1280)
    max_bank = get("AirframeGimbalInputMaxBankDegreesV1", "real", 0, 1440)
    uptilt = get("AirframeGimbalInputCameraUptiltDegreesV1", "real", 0, 1600)
    max_accel = get("AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1", "real", 0, 1760)
    max_jerk = get("AirframeGimbalInputMaxJerkCmPerSecondCubedV1", "real", 0, 1920)
    min_radius = get("AirframeGimbalInputMinimumTurnRadiusCmV1", "real", 0, 2080)

    authored_forward = vector_axis(authored_body, "AirframeGimbalInputAuthoredBodyQuatV1", "X", 320, 640)
    authored_up = vector_axis(authored_body, "AirframeGimbalInputAuthoredBodyQuatV1", "Z", 320, 800)
    speed = vsize(current, "AirframeGimbalInputCurrentVelocityV1", 320, 0)
    current_has = compare("Greater_DoubleDouble", speed, "ReturnValue", None, EPSILON, 544, 0)
    current_normal = normalize_vector(current, "AirframeGimbalInputCurrentVelocityV1", 544, 160)
    current_forward = select(current_has, "ReturnValue", authored_forward, "ReturnValue", current_normal, "ReturnValue", "vector", 768, 80)
    lookahead_speed = vsize(lookahead, "AirframeGimbalInputLookAheadVelocityV1", 320, 320)
    lookahead_has = compare("Greater_DoubleDouble", lookahead_speed, "ReturnValue", None, EPSILON, 544, 320)
    lookahead_normal = normalize_vector(lookahead, "AirframeGimbalInputLookAheadVelocityV1", 544, 480)
    predicted_forward = select(lookahead_has, "ReturnValue", current_forward, "ReturnValue", lookahead_normal, "ReturnValue", "vector", 768, 400)

    vertical_dot = native_call("Dot_VectorVector", 1024, 320)
    bp.connect(predicted_forward, "ReturnValue", vertical_dot, "A")
    scalar.set_default(vertical_dot, "B", "0, 0, 1")
    vertical_positive = compare("GreaterEqual_DoubleDouble", vertical_dot, "ReturnValue", None, "0.999999", 1248, 256)
    vertical_negative = compare("LessEqual_DoubleDouble", vertical_dot, "ReturnValue", None, "-0.999999", 1248, 400)
    vertical = bool_op("BooleanOR", vertical_positive, "ReturnValue", vertical_negative, "ReturnValue", 1472, 320)
    up_hint = select(vertical, "ReturnValue", None, "", authored_up, "ReturnValue", "vector", 1696, 320, false_default="0, 0, 1")
    make_rot = b.add("path_rotator", "make_rot_xz", 1920, 320)
    bp.connect(predicted_forward, "ReturnValue", make_rot, "X")
    bp.connect(up_hint, "ReturnValue", make_rot, "Z")
    path_quat_raw = b.add("path_quat_raw", "rotator_to_quat", 2144, 320)
    bp.connect(make_rot, "ReturnValue", path_quat_raw, "InRot")
    path_quat = b.add("path_quat", "quat_normalized", 2368, 320)
    bp.connect(path_quat_raw, "ReturnValue", path_quat, "Q")
    scalar.set_default(path_quat, "Tolerance", EPSILON)

    accel_magnitude = vsize(accel, "AirframeGimbalInputAccelerationV1", 1024, 800)
    jerk_magnitude = vsize(jerk, "AirframeGimbalInputJerkV1", 1024, 960)
    accel_ok = compare("LessEqual_DoubleDouble", accel_magnitude, "ReturnValue", max_accel, "AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1", 1248, 800)
    jerk_ok = compare("LessEqual_DoubleDouble", jerk_magnitude, "ReturnValue", max_jerk, "AirframeGimbalInputMaxJerkCmPerSecondCubedV1", 1248, 960)
    forward_dot = native_call("Dot_VectorVector", 1024, 1120)
    bp.connect(accel, "AirframeGimbalInputAccelerationV1", forward_dot, "A")
    bp.connect(current_forward, "ReturnValue", forward_dot, "B")
    forward_components = make_vector(forward_dot, "ReturnValue", forward_dot, "ReturnValue", forward_dot, "ReturnValue", 1248, 1120)
    forward_accel = b.add("forward_accel", "vector_multiply", 1472, 1120)
    bp.connect(current_forward, "ReturnValue", forward_accel, "A")
    bp.connect(forward_components, "ReturnValue", forward_accel, "B")
    lateral_vector = b.add("lateral_vector", "vector_subtract", 1696, 1120)
    bp.connect(accel, "AirframeGimbalInputAccelerationV1", lateral_vector, "A")
    bp.connect(forward_accel, "ReturnValue", lateral_vector, "B")
    lateral = vsize(lateral_vector, "ReturnValue", 1920, 1120)
    lateral_has = compare("Greater_DoubleDouble", lateral, "ReturnValue", None, EPSILON, 2144, 1120)
    has_turn = bool_op("BooleanAND", current_has, "ReturnValue", lateral_has, "ReturnValue", 2368, 1040)
    speed_squared = b.math("Multiply_DoubleDouble", 2144, 1280)
    bp.connect(speed, "ReturnValue", speed_squared, "A")
    bp.connect(speed, "ReturnValue", speed_squared, "B")
    safe_lateral = select(
        has_turn, "ReturnValue",
        None, "", lateral, "ReturnValue",
        "real", 2368, 1200,
        false_default="1.0",
    )
    radius_raw = b.math("Divide_DoubleDouble", 2592, 1280)
    bp.connect(speed_squared, "ReturnValue", radius_raw, "A")
    bp.connect(safe_lateral, "ReturnValue", radius_raw, "B")
    radius = select(has_turn, "ReturnValue", None, "", radius_raw, "ReturnValue", "real", 2816, 1200, false_default="0.0")
    radius_minimum = compare("GreaterEqual_DoubleDouble", radius_raw, "ReturnValue", min_radius, "AirframeGimbalInputMinimumTurnRadiusCmV1", 2816, 1360)
    radius_ok = select(has_turn, "ReturnValue", None, "", radius_minimum, "ReturnValue", "bool", 3040, 1280, false_default="true")

    path_right = vector_axis(path_quat, "ReturnValue", "Y", 2816, 320)
    signed_accel = native_call("Dot_VectorVector", 3040, 480)
    bp.connect(accel, "AirframeGimbalInputAccelerationV1", signed_accel, "A")
    bp.connect(path_right, "ReturnValue", signed_accel, "B")
    atan = native_call("Atan2", 3264, 480)
    bp.connect(signed_accel, "ReturnValue", atan, "Y")
    scalar.set_default(atan, "X", GRAVITY)
    degrees_negative = b.math("Multiply_DoubleDouble", 3488, 480, NEGATIVE_RADIANS_TO_DEGREES)
    bp.connect(atan, "ReturnValue", degrees_negative, "A")
    gained_bank = b.math("Multiply_DoubleDouble", 3712, 480)
    bp.connect(degrees_negative, "ReturnValue", gained_bank, "A")
    bp.connect(bank_gain, "AirframeGimbalInputBankGainV1", gained_bank, "B")
    negative_max = b.math("Subtract_DoubleDouble", 3712, 640)
    scalar.set_default(negative_max, "A", "0.0")
    bp.connect(max_bank, "AirframeGimbalInputMaxBankDegreesV1", negative_max, "B")
    bank = b.add("bank_clamp", "clamp", 3936, 480)
    bp.connect(gained_bank, "ReturnValue", bank, "Value")
    bp.connect(negative_max, "ReturnValue", bank, "Min")
    bp.connect(max_bank, "AirframeGimbalInputMaxBankDegreesV1", bank, "Max")
    bank_euler = make_vector(bank, "ReturnValue", None, "", None, "", 4160, 480)
    bank_quat = native_call("Quat_MakeFromEuler", 4384, 480)
    bp.connect(bank_euler, "ReturnValue", bank_quat, "Euler")
    banked_path_raw = b.add("banked_path_raw", "quat_multiply", 4608, 480)
    bp.connect(path_quat, "ReturnValue", banked_path_raw, "A")
    bp.connect(bank_quat, "ReturnValue", banked_path_raw, "B")
    banked_path = b.add("banked_path", "quat_normalized", 4832, 480)
    bp.connect(banked_path_raw, "ReturnValue", banked_path, "Q")
    scalar.set_default(banked_path, "Tolerance", EPSILON)
    body_raw = b.add("body_raw", "quat_slerp", 5056, 480)
    bp.connect(authored_body, "AirframeGimbalInputAuthoredBodyQuatV1", body_raw, "A")
    bp.connect(banked_path, "ReturnValue", body_raw, "B")
    bp.connect(path_weight, "AirframeGimbalInputPathFollowWeightV1", body_raw, "Alpha")
    body = b.add("body", "quat_normalized", 5280, 480)
    bp.connect(body_raw, "ReturnValue", body, "Q")
    scalar.set_default(body, "Tolerance", EPSILON)

    uptilt_euler = make_vector(None, "", uptilt, "AirframeGimbalInputCameraUptiltDegreesV1", None, "", 4160, 800)
    uptilt_quat = native_call("Quat_MakeFromEuler", 4384, 800)
    bp.connect(uptilt_euler, "ReturnValue", uptilt_quat, "Euler")
    locked_raw = b.add("locked_raw", "quat_multiply", 4608, 800)
    bp.connect(body, "ReturnValue", locked_raw, "A")
    bp.connect(uptilt_quat, "ReturnValue", locked_raw, "B")
    locked = b.add("locked", "quat_normalized", 4832, 800)
    bp.connect(locked_raw, "ReturnValue", locked, "Q")
    scalar.set_default(locked, "Tolerance", EPSILON)
    gimbal_raw = b.add("gimbal_raw", "quat_slerp", 5056, 800)
    bp.connect(locked, "ReturnValue", gimbal_raw, "A")
    bp.connect(authored_gimbal, "AirframeGimbalInputAuthoredGimbalQuatV1", gimbal_raw, "B")
    bp.connect(horizon_weight, "AirframeGimbalInputHorizonStabilizationWeightV1", gimbal_raw, "Alpha")
    gimbal = b.add("gimbal", "quat_normalized", 5280, 800)
    bp.connect(gimbal_raw, "ReturnValue", gimbal, "Q")
    scalar.set_default(gimbal, "Tolerance", EPSILON)

    guards = [(accel_ok, "ReturnValue"), (jerk_ok, "ReturnValue"), (radius_ok, "ReturnValue")]
    for source, pin, x, y in ((speed, "ReturnValue", 3040, 1120), (lateral, "ReturnValue", 3040, 1280), (radius, "ReturnValue", 3040, 1440), (bank, "ReturnValue", 3040, 1600)):
        guards.append((b.finite(source, pin, x, y), "ReturnValue"))
    combined, combined_pin = guards[0]
    for index, (guard, guard_pin) in enumerate(guards[1:]):
        combined = bool_op("BooleanAND", combined, combined_pin, guard, guard_pin, 3712 + index * 224, 1760)
        combined_pin = "ReturnValue"
    physical_branch = b.add("physical_branch", "branch", 5504, 3200)
    bp.connect(valid_branch, "then", physical_branch, "execute")
    bp.connect(combined, combined_pin, physical_branch, "Condition")

    publications = (
        ("AirframeGimbalResultBodyQuatV1", "quat", body, "ReturnValue"),
        ("AirframeGimbalResultGimbalQuatV1", "quat", gimbal, "ReturnValue"),
        ("AirframeGimbalResultPathQuatV1", "quat", path_quat, "ReturnValue"),
        ("AirframeGimbalResultSpeedCmPerSecondV1", "real", speed, "ReturnValue"),
        ("AirframeGimbalResultLateralAccelerationCmPerSecondSquaredV1", "real", lateral, "ReturnValue"),
        ("AirframeGimbalResultTurnRadiusCmV1", "real", radius, "ReturnValue"),
        ("AirframeGimbalResultBankDegreesV1", "real", bank, "ReturnValue"),
    )
    setters = []
    for index, (name, value, source, source_pin) in enumerate(publications):
        setter = set_value(name, value, 5760 + index * 320, 3200)
        bp.connect(source, source_pin, setter, name)
        setters.append(setter)
    publish_valid = set_value("AirframeGimbalResultValidV1", "bool", 8000, 3200, "true")
    bp.connect(physical_branch, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(setters[-1], "then", publish_valid, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
