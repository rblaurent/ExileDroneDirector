"""Exact semantic contracts for the flight-profile reset transaction."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


PARAMETERS = (
    "PathFollowWeights", "HorizonStabilizationWeights", "LookAheadSeconds",
    "BankGains", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRatesDegreesPerSecond", "MaxAccelerationsCmPerSecondSquared",
    "MaxJerksCmPerSecondCubed", "MinimumTurnRadiiCm",
)
ARRAYS = (
    "FlightProfileCandidateIdsV1",
    *(f"FlightProfileCandidate{name}V1" for name in PARAMETERS),
    "FlightProfileCompiledIdsV1",
    *(f"FlightProfileCompiled{name}V1" for name in PARAMETERS),
)
SCALARS = (
    ("FlightProfileStageValidV1", "false"),
    ("FlightProfileEvaluationStageValidV1", "false"),
    ("FlightProfileCompileValidV1", "false"),
    ("FlightProfileResultIdV1", ""),
    ("FlightProfileResultPathFollowWeightV1", "0.0"),
    ("FlightProfileResultHorizonStabilizationWeightV1", "0.0"),
    ("FlightProfileResultLookAheadSecondsV1", "0.0"),
    ("FlightProfileResultBankGainV1", "0.0"),
    ("FlightProfileResultMaxBankDegreesV1", "0.0"),
    ("FlightProfileResultCameraUptiltDegreesV1", "0.0"),
    ("FlightProfileResultMaxAngularRateDegreesPerSecondV1", "0.0"),
    ("FlightProfileResultMaxAccelerationCmPerSecondSquaredV1", "0.0"),
    ("FlightProfileResultMaxJerkCmPerSecondCubedV1", "0.0"),
    ("FlightProfileResultMinimumTurnRadiusCmV1", "0.0"),
    ("FlightProfileResultValidV1", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def explicit_default(body):
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
    contracts.require(len(nodes) == (59 if args.paste else 60), f"reset node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "reset entry count")
    clears = []
    for name in ARRAYS:
        getter = contracts.one(nodes, f'MemberName="{name}"')
        clear = next((node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text and contracts.linked(getter, name, node, "TargetArray")), None)
        contracts.require(clear is not None, f"{name} clear missing")
        clears.append(clear)
    setters = []
    for name, value in SCALARS:
        setter = contracts.one(nodes, f'MemberName="{name}"')
        contracts.require(explicit_default(setter.pins[name].body) == value, f"{name} reset changed")
        setters.append(setter)
    chain = [*clears, *setters]
    if args.paste:
        contracts.require(not chain[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", chain[0], "execute", "entry must reach first clear")
    for left, right in zip(chain, chain[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Flight-profile reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
