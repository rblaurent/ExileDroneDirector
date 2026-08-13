"""Exact contracts for airframe/gimbal desired-pose input validation."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


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
FINITE_MIN = "-1.7976931348623157e+308"
FINITE_MAX = "1.7976931348623157e+308"


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_validation_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return None if match is None else match.group(1)


def members(nodes, member):
    return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load(args.project_root)
    nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (164 if args.paste else 165), f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")

    getters = {}
    for name in (*VECTOR_INPUTS, *QUAT_INPUTS, *(item[0] for item in PROFILE_BOUNDS)):
        matches = members(nodes, name)
        c.require(len(matches) == 1, f"one exact getter required for {name}; found {len(matches)}")
        getters[name] = matches[0]
        c.require("K2Node_VariableGet" in matches[0].node_class, f"{name} must be read-only")

    def require_finite(source, source_pin: str, label: str):
        lowers = [node for node in members(nodes, "GreaterEqual_DoubleDouble") if c.linked(source, source_pin, node, "A") and default(node, "B") == FINITE_MIN]
        uppers = [node for node in members(nodes, "LessEqual_DoubleDouble") if c.linked(source, source_pin, node, "A") and default(node, "B") == FINITE_MAX]
        c.require(len(lowers) == 1 and len(uppers) == 1, f"{label} exact finite bounds")
        finite_and = [node for node in members(nodes, "BooleanAND") if c.linked(lowers[0], "ReturnValue", node, "A") and c.linked(uppers[0], "ReturnValue", node, "B")]
        c.require(len(finite_and) == 1, f"{label} finite conjunction")
        return finite_and[0]

    breaks = members(nodes, "BreakVector")
    c.require(len(breaks) == 4, "four exact vector decompositions")
    for name in VECTOR_INPUTS:
        split = next(node for node in breaks if c.linked(getters[name], name, node, "InVec"))
        for component in ("X", "Y", "Z"):
            require_finite(split, component, f"{name}.{component}")

    finite_quats = members(nodes, "Quat_IsFinite")
    sizes = members(nodes, "Quat_Size")
    c.require(len(finite_quats) == 2 and len(sizes) == 2, "two quaternion finite/size checks")
    for name in QUAT_INPUTS:
        c.require(any(c.linked(getters[name], name, node, "Q") for node in finite_quats), f"{name} finite guard")
        size = next(node for node in sizes if c.linked(getters[name], name, node, "Q"))
        lowers = [node for node in members(nodes, "GreaterEqual_DoubleDouble") if c.linked(size, "ReturnValue", node, "A") and default(node, "B") == "0.999999"]
        uppers = [node for node in members(nodes, "LessEqual_DoubleDouble") if c.linked(size, "ReturnValue", node, "A") and default(node, "B") == "1.000001"]
        c.require(len(lowers) == 1 and len(uppers) == 1, f"{name} exact unit tolerance")

    for name, lower_value, upper_value, inclusive_lower in PROFILE_BOUNDS:
        getter = getters[name]
        require_finite(getter, name, name)
        lower_member = "GreaterEqual_DoubleDouble" if inclusive_lower else "Greater_DoubleDouble"
        lower = [node for node in members(nodes, lower_member) if c.linked(getter, name, node, "A") and default(node, "B") == lower_value]
        upper = [node for node in members(nodes, "LessEqual_DoubleDouble") if c.linked(getter, name, node, "A") and default(node, "B") == upper_value]
        c.require(len(lower) == 1 and len(upper) == 1, f"{name} exact domain")

    conjunctions = members(nodes, "BooleanAND")
    c.require(len(conjunctions) == 69, "22 finite guards plus 47 aggregate conjunctions")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 1, "one atomic validation branch")
    stage_sets = members(nodes, "AirframeGimbalStageValidV1")
    c.require(len(stage_sets) == 2, "stage reset and accept writes")
    reset = next(node for node in stage_sets if default(node, "AirframeGimbalStageValidV1") == "false")
    accept = next(node for node in stage_sets if default(node, "AirframeGimbalStageValidV1") == "true")
    c.require_link(reset, "then", branches[0], "execute", "reset-before-validation execution")
    c.require_link(branches[0], "then", accept, "execute", "accept publication")
    c.require_link(conjunctions[-1], "ReturnValue", branches[0], "Condition", "complete guard conjunction")
    if args.paste:
        c.require(not reset.pins["execute"].links, "paste root must be exposed")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry reset seam")
    c.require(not members(nodes, "AirframeGimbalResultValidV1"), "validator cannot publish a result")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    print(f"Airframe/gimbal validation contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
