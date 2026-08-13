"""Exact semantic contracts for the smoothed flight-profile reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


PARAMETERS = (
    "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
    "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
    "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
)
RESETS = (
    ("SmoothedFlightProfileStageValidV1", "false"),
    ("SmoothedFlightProfileCurrentIdV1", ""),
    *((f"SmoothedFlightProfileCurrent{name}V1", "0.0") for name in PARAMETERS),
    ("SmoothedFlightProfileNeighborIdV1", ""),
    *((f"SmoothedFlightProfileNeighbor{name}V1", "0.0") for name in PARAMETERS),
    ("SmoothedFlightProfileNeighborWeightV1", "0.0"),
    ("SmoothedFlightProfileResultCurrentIdV1", ""),
    ("SmoothedFlightProfileResultNeighborIdV1", ""),
    ("SmoothedFlightProfileResultNeighborWeightV1", "0.0"),
    *((f"SmoothedFlightProfileResult{name}V1", "0.0") for name in PARAMETERS),
    ("SmoothedFlightProfileResultValidV1", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_smoothed_profile_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def explicit_default(body: str):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', body)
    if match is not None:
        return match.group(1)
    return "" if 'PinType.PinCategory="string"' in body else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (38 if args.paste else 39), f"reset node count {len(nodes)}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knots forbidden")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "reset entry count")
    contracts.require(not any('MemberName="Array_Clear"' in node.text for node in nodes.values()), "reset owns no arrays")

    setters = []
    for name, value in RESETS:
        setter = contracts.one(nodes, f'MemberName="{name}"')
        contracts.require("K2Node_VariableSet" in setter.node_class, f"{name} must be a setter")
        contracts.require(explicit_default(setter.pins[name].body) == value, f"{name} reset changed")
        setters.append(setter)

    for forbidden in ("SmoothedFlightProfileInputSegmentIndexV1", "SmoothedFlightProfileInputLocalTimeAlphaV1"):
        contracts.require(not any(f'MemberName="{forbidden}"' in node.text for node in nodes.values()), f"input reset forbidden: {forbidden}")
    if args.paste:
        contracts.require(not setters[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", setters[0], "execute", "entry must reach first reset")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values()
        for target, _ in pin.links if target not in known
    }
    contracts.require(not external, f"external links {external}")
    print(f"Smoothed flight-profile reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
