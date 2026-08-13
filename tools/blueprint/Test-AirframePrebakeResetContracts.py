"""Exact semantic contracts for fixed-step airframe/gimbal prebake reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = (
    "AirframePrebakeCandidateBodyQuatsV1",
    "AirframePrebakeCandidateGimbalQuatsV1",
    "AirframePrebakeCandidateBodyAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCandidateGimbalAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCandidateBodyRateLimitedV1",
    "AirframePrebakeCandidateGimbalRateLimitedV1",
    "AirframePrebakeCompiledBodyQuatsV1",
    "AirframePrebakeCompiledGimbalQuatsV1",
    "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledBodyRateLimitedV1",
    "AirframePrebakeCompiledGimbalRateLimitedV1",
)
SCALARS = (
    ("AirframePrebakeStageIndexV1", "0"),
    ("AirframePrebakeStageValidV1", "false"),
    ("AirframePrebakeCompiledFixedStepSecondsV1", "0.0"),
    ("AirframePrebakeCompiledTotalSecondsV1", "0.0"),
    ("AirframePrebakeCompileValidV1", "false"),
    ("AirframePrebakeResultSegmentIndexV1", "-1"),
    ("AirframePrebakeResultAlphaV1", "0.0"),
    ("AirframePrebakeResultBodyQuatV1", None),
    ("AirframePrebakeResultGimbalQuatV1", None),
    ("AirframePrebakeResultCompleteV1", "false"),
    ("AirframePrebakeResultValidV1", "false"),
)
INPUTS = (
    "AirframePrebakeInputDesiredBodyQuatsV1",
    "AirframePrebakeInputDesiredGimbalQuatsV1",
    "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1",
    "AirframePrebakeInputTotalSecondsV1",
    "AirframePrebakeInputFixedStepSecondsV1",
    "AirframePrebakeInputElapsedSecondsV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_reset_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
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
    contracts.require(len(nodes) == (35 if args.paste else 36), f"reset node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "reset entry count")

    clears = []
    for name in ARRAYS:
        getter = contracts.one(nodes, f'MemberName="{name}"')
        clear = next((
            node for node in nodes.values()
            if 'MemberName="Array_Clear"' in node.text
            and any(target == getter.name for pin in node.pins.values() for target, _pin in pin.links)
        ), None)
        contracts.require(clear is not None, f"{name} clear missing")
        contracts.require_link(getter, name, clear, "TargetArray", f"{name} must be cleared")
        clears.append(clear)

    setters = []
    for name, value in SCALARS:
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
    chain = [*clears, *setters]
    if args.paste:
        contracts.require(not chain[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", chain[0], "execute", "entry must reach first clear")
    for left, right in zip(chain, chain[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values()
        for target, _pin in pin.links if target not in known
    }
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knot forbidden")
    print(f"Airframe prebake reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
