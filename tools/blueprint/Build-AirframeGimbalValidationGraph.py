"""Build fail-closed validation for airframe/gimbal desired-pose inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateAirframeGimbalInputsV1"
VECTOR_INPUTS = (
    "AirframeGimbalInputCurrentVelocityV1",
    "AirframeGimbalInputLookAheadVelocityV1",
    "AirframeGimbalInputAccelerationV1",
    "AirframeGimbalInputJerkV1",
)
QUAT_INPUTS = (
    "AirframeGimbalInputAuthoredBodyQuatV1",
    "AirframeGimbalInputAuthoredGimbalQuatV1",
)
PROFILE_BOUNDS = (
    ("AirframeGimbalInputPathFollowWeightV1", "0.0", "1.0", True),
    ("AirframeGimbalInputHorizonStabilizationWeightV1", "0.0", "1.0", True),
    ("AirframeGimbalInputLookAheadSecondsV1", "0.0", "5.0", True),
    ("AirframeGimbalInputBankGainV1", "0.0", "2.0", True),
    ("AirframeGimbalInputMaxBankDegreesV1", "0.0", "85.0", True),
    ("AirframeGimbalInputCameraUptiltDegreesV1", "-45.0", "45.0", True),
    ("AirframeGimbalInputMaxAngularRateDegreesPerSecondV1", "0.0", "720.0", False),
    ("AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1", "0.0", "10000.0", False),
    ("AirframeGimbalInputMaxJerkCmPerSecondCubedV1", "0.0", "50000.0", False),
    ("AirframeGimbalInputMinimumTurnRadiusCmV1", "0.0", "100000.0", False),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_validation_base", path)
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
    vector_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    quat_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    raw_forms = {
        "break_vector": bp.find_block(vector_forms, r'MemberName="BreakVector"'),
        "quat_finite": bp.find_block(quat_forms, r'MemberName="Quat_IsFinite"'),
        "quat_size": bp.find_block(quat_compiler_forms, r'MemberName="Quat_Size"'),
    }
    b = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        text = raw_forms[form]
        match = bp.BLOCK_RE.match(text)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, text, f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def variable(node, name: str, value: str):
        scalar.retarget_variable(node, name, "vector" if value == "quat" else value)
        pin_kind(node, name, value)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", value)

    def get(name: str, value: str, x: int, y: int):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, value)
        return node

    def compare(member: str, source, source_pin: str, default_b: str, x: int, y: int):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, "real")
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(source, source_pin, node, "A")
        scalar.set_default(node, "B", default_b)
        return node

    def boolean_and(left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.add(f"and_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    reset = b.set("AirframeGimbalStageValidV1", "bool", 256, 2560, "false")
    bp.connect(b.entry, "then", reset, "execute")
    conditions = []

    vector_getters = []
    for index, name in enumerate(VECTOR_INPUTS):
        y = index * 480
        source = get(name, "vector", 0, y)
        vector_getters.append(source)
        split = add_form(f"break_{name}", "break_vector", 320, y)
        pin_kind(split, "InVec", "vector")
        for pin in ("X", "Y", "Z"):
            pin_kind(split, pin, "real")
        bp.connect(source, name, split, "InVec")
        for component_index, component in enumerate(("X", "Y", "Z")):
            conditions.append((b.finite(split, component, 640, y + component_index * 144), "ReturnValue"))

    quat_getters = []
    for index, name in enumerate(QUAT_INPUTS):
        y = 2080 + index * 480
        source = get(name, "quat", 0, y)
        quat_getters.append(source)
        finite = add_form(f"finite_{name}", "quat_finite", 320, y)
        pin_kind(finite, "Q", "quat")
        pin_kind(finite, "ReturnValue", "bool")
        bp.connect(source, name, finite, "Q")
        size = add_form(f"size_{name}", "quat_size", 320, y + 160)
        pin_kind(size, "Q", "quat")
        pin_kind(size, "ReturnValue", "real")
        bp.connect(source, name, size, "Q")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", "0.999999", 640, y + 112)
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", "1.000001", 640, y + 256)
        conditions.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))

    profile_getters = []
    for index, (name, lower_value, upper_value, inclusive_lower) in enumerate(PROFILE_BOUNDS):
        y = index * 176
        source = get(name, "real", 3072, y)
        profile_getters.append(source)
        finite = b.finite(source, name, 3392, y)
        lower = compare(
            "GreaterEqual_DoubleDouble" if inclusive_lower else "Greater_DoubleDouble",
            source, name, lower_value, 3840, y,
        )
        upper = compare("LessEqual_DoubleDouble", source, name, upper_value, 4064, y)
        conditions.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))

    combined, combined_pin = conditions[0]
    for index, (condition, condition_pin) in enumerate(conditions[1:]):
        combined = boolean_and(combined, combined_pin, condition, condition_pin, 4544 + index * 224, 2080)
        combined_pin = "ReturnValue"
    branch = b.add("validation_branch", "branch", 15296, 2560)
    bp.connect(reset, "then", branch, "execute")
    bp.connect(combined, combined_pin, branch, "Condition")
    accept = b.set("AirframeGimbalStageValidV1", "bool", 15552, 2560, "true")
    bp.connect(branch, "then", accept, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in b.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
