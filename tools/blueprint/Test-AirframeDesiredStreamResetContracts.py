"""Exact structural and executable contracts for ResetAirframeDesiredStreamV1."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = (
    "AirframeDesiredStreamCandidateVelocitiesV1",
    "AirframeDesiredStreamCandidateAccelerationsV1",
    "AirframeDesiredStreamCandidateJerksV1",
    "AirframeDesiredStreamCandidateLookAheadVelocitiesV1",
    "AirframeDesiredStreamCandidateBodyQuatsV1",
    "AirframeDesiredStreamCandidateGimbalQuatsV1",
    "AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1",
    "AirframePrebakeInputDesiredBodyQuatsV1",
    "AirframePrebakeInputDesiredGimbalQuatsV1",
    "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1",
)
SCALARS = (
    ("AirframeDesiredStreamStageIndexV1", "0"),
    ("AirframeDesiredStreamStageValidV1", "false"),
    ("AirframeDesiredStreamVelocitySampleInputSecondsV1", "0.0"),
    ("AirframeDesiredStreamVelocitySampleResultV1", None),
    ("AirframeDesiredStreamVelocitySampleResultValidV1", "false"),
    ("AirframeDesiredStreamCompileValidV1", "false"),
    ("AirframePrebakeInputTotalSecondsV1", "0.0"),
    ("AirframePrebakeInputFixedStepSecondsV1", "0.0"),
)
IMMUTABLE_INPUTS = (
    "AirframeDesiredStreamInputPositionsV1",
    "AirframeDesiredStreamInputAuthoredBodyQuatsV1",
    "AirframeDesiredStreamInputAuthoredGimbalQuatsV1",
    "AirframeDesiredStreamInputPathFollowWeightsV1",
    "AirframeDesiredStreamInputHorizonStabilizationWeightsV1",
    "AirframeDesiredStreamInputLookAheadSecondsV1",
    "AirframeDesiredStreamInputBankGainsV1",
    "AirframeDesiredStreamInputMaxBankDegreesV1",
    "AirframeDesiredStreamInputCameraUptiltDegreesV1",
    "AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1",
    "AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1",
    "AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1",
    "AirframeDesiredStreamInputMinimumTurnRadiiCmV1",
    "AirframeDesiredStreamInputTotalSecondsV1",
    "AirframeDesiredStreamInputFixedStepSecondsV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_reset_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def explicit_default(body):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', body)
    return None if match is None else match.group(1)


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


class Interpreter:
    """Execute the generated reset chain from its exported pin links."""

    def __init__(self, nodes, state, paste):
        self.nodes = nodes
        self.state = dict(state)
        self.paste = paste
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)

    def linked_output(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in target[1].body:
                return target
        return None

    def next(self, node):
        for link in node.pins["then"].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def scalar_default(self, node, name):
        value = explicit_default(node.pins[name].body)
        if value == "false":
            return False
        if value == "true":
            return True
        if value in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"):
            return (0.0, 0.0, 0.0)
        return int(value) if value is not None and re.fullmatch(r"-?\d+", value) else float(value)

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.next(entries[0])
        else:
            current = next(
                node for node in self.nodes.values()
                if member(node) == "ResetAirframePrebakeCandidateV1" and not node.pins["execute"].links
            )
        visited = []
        while current is not None:
            visited.append(current.name)
            name = member(current)
            if name == "ResetAirframePrebakeCandidateV1":
                # Observable contract of the already-accepted downstream reset.
                self.state["__downstream_reset_called__"] = True
                self.state["AirframePrebakeCompileValidV1"] = False
                self.state["AirframePrebakeResultValidV1"] = False
                self.state["AirframePrebakeCompiledBodyQuatsV1"] = []
            elif name == "Array_Clear":
                source = self.linked_output(current, "TargetArray")
                if source is None or "K2Node_VariableGet" not in source[0].node_class:
                    raise RuntimeError("Array_Clear source contract")
                self.state[member(source[0])] = []
            elif "K2Node_VariableSet" in current.node_class:
                self.state[name] = self.scalar_default(current, name)
            else:
                raise RuntimeError(f"unsupported reset node {current.name}:{name}")
            current = self.next(current)
        if len(visited) != 1 + len(ARRAYS) + len(SCALARS):
            raise RuntimeError(f"reset traversal count {len(visited)}")
        return self.state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (29 if args.paste else 30), f"reset node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "reset entry count")
    downstream = contracts.one(nodes, 'MemberName="ResetAirframePrebakeCandidateV1"')
    contracts.require('bSelfContext=True' in downstream.text, "downstream reset must be self-context")

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
    for name, expected in SCALARS:
        setter = contracts.one(nodes, f'MemberName="{name}"')
        actual = explicit_default(setter.pins[name].body)
        if expected is None:
            contracts.require(
                actual in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"),
                f"{name} vector reset changed: {actual!r}",
            )
        else:
            contracts.require(actual == expected, f"{name} reset changed: {actual!r}")
        setters.append(setter)

    contracts.require(
        not any(f'MemberName="{name}"' in node.text for name in IMMUTABLE_INPUTS for node in nodes.values()),
        "reset must never read or mutate an immutable source input",
    )
    chain = [downstream, *clears, *setters]
    if args.paste:
        contracts.require(not downstream.pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", downstream, "execute", "entry must invalidate downstream first")
    for left, right in zip(chain, chain[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values()
        for target, _pin in pin.links if target not in known
    }
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knot forbidden")

    state = {name: [1, 2, 3] for name in ARRAYS}
    state.update({name: "poison" for name, _expected in SCALARS})
    state.update({
        "AirframePrebakeCompileValidV1": True,
        "AirframePrebakeResultValidV1": True,
        "AirframePrebakeCompiledBodyQuatsV1": ["poison"],
    })
    immutable = {name: object() for name in IMMUTABLE_INPUTS}
    state.update(immutable)
    result = Interpreter(nodes, state, args.paste).run()
    contracts.require(result["__downstream_reset_called__"] is True, "downstream reset was not executed")
    contracts.require(result["AirframePrebakeCompileValidV1"] is False, "downstream compile state survived")
    contracts.require(result["AirframePrebakeResultValidV1"] is False, "downstream result state survived")
    contracts.require(result["AirframePrebakeCompiledBodyQuatsV1"] == [], "downstream arrays survived")
    contracts.require(all(result[name] == [] for name in ARRAYS), "array reset execution failed")
    expected_scalars = {
        name: (0.0, 0.0, 0.0) if expected is None else (
            False if expected == "false" else int(expected) if re.fullmatch(r"-?\d+", expected) else float(expected)
        ) for name, expected in SCALARS
    }
    contracts.require(all(result[name] == expected for name, expected in expected_scalars.items()), "scalar reset execution failed")
    contracts.require(all(result[name] is value for name, value in immutable.items()), "source input mutated")
    print(f"Airframe desired-stream reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
