"""Exact semantic contracts for the airframe/gimbal desired-pose reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


RESULTS = (
    ("AirframeGimbalStageValidV1", "false"),
    ("AirframeGimbalResultBodyQuatV1", None),
    ("AirframeGimbalResultGimbalQuatV1", None),
    ("AirframeGimbalResultPathQuatV1", None),
    ("AirframeGimbalResultSpeedCmPerSecondV1", "0.0"),
    ("AirframeGimbalResultLateralAccelerationCmPerSecondSquaredV1", "0.0"),
    ("AirframeGimbalResultTurnRadiusCmV1", "0.0"),
    ("AirframeGimbalResultBankDegreesV1", "0.0"),
    ("AirframeGimbalResultValidV1", "false"),
)
INPUTS = (
    "AirframeGimbalInputCurrentVelocityV1",
    "AirframeGimbalInputLookAheadVelocityV1",
    "AirframeGimbalInputAccelerationV1",
    "AirframeGimbalInputJerkV1",
    "AirframeGimbalInputAuthoredBodyQuatV1",
    "AirframeGimbalInputAuthoredGimbalQuatV1",
    "AirframeGimbalInputPathFollowWeightV1",
    "AirframeGimbalInputHorizonStabilizationWeightV1",
    "AirframeGimbalInputLookAheadSecondsV1",
    "AirframeGimbalInputBankGainV1",
    "AirframeGimbalInputMaxBankDegreesV1",
    "AirframeGimbalInputCameraUptiltDegreesV1",
    "AirframeGimbalInputMaxAngularRateDegreesPerSecondV1",
    "AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1",
    "AirframeGimbalInputMaxJerkCmPerSecondCubedV1",
    "AirframeGimbalInputMinimumTurnRadiusCmV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def explicit_default(body):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', body)
    return None if match is None else match.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (9 if args.paste else 10), f"reset node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = []
    for name, value in RESULTS:
        setter = contracts.one(nodes, f'MemberName="{name}"')
        actual = explicit_default(setter.pins[name].body)
        if value is None:
            contracts.require(
                actual in ("0, 0, 0, 1", "(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)"),
                f"{name} identity reset changed: {actual!r}",
            )
        else:
            contracts.require(actual == value, f"{name} reset changed: {actual!r}")
        setters.append(setter)
    contracts.require(
        not any(f'MemberName="{name}"' in node.text for name in INPUTS for node in nodes.values()),
        "reset must never read or mutate an input",
    )
    if args.paste:
        contracts.require(not setters[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", setters[0], "execute", "entry reset seam")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _pin in pin.links
        if target not in known
    }
    contracts.require(not external, f"external links {external}")
    contracts.require(
        not any("K2Node_Knot" in node.node_class for node in nodes.values()),
        "reset must not contain reroute knots",
    )
    print(f"Airframe/gimbal reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
