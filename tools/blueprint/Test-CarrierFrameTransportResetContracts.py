"""Exact ownership and execution contracts for ResetCarrierFrameTransportV1."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = (
    "CarrierFrameCandidateTangentsV1",
    "CarrierFrameCandidateQuatsV1",
    "CarrierFrameCompiledTangentsV1",
    "CarrierFrameCompiledQuatsV1",
)
DEFAULTS = {
    "CarrierFrameCompileValidV1": "false",
    "CarrierFrameResultValidV1": "false",
    "CarrierFrameStageValidV1": "false",
    "CarrierFrameCompiledTotalSecondsV1": "0.0",
    "CarrierFrameCompiledFixedStepSecondsV1": "0.0",
    "CarrierFrameResultSegmentIndexV1": "-1",
    "CarrierFrameResultAlphaV1": "0.0",
    "CarrierFrameResultQuatV1": "0, 0, 0, 1",
    "CarrierFrameResultCompleteV1": "false",
    "CarrierFrameFailureCodeV1": "",
    "CarrierFrameScratchIndexV1": "0",
    "CarrierFrameScratchForwardV1": "1, 0, 0",
    "CarrierFrameScratchRightV1": "0, 1, 0",
    "CarrierFrameScratchUpV1": "0, 0, 1",
    "CarrierFrameScratchQuatV1": "0, 0, 0, 1",
    "CarrierFrameScratchValidV1": "false",
}
PRESERVED = (
    "CarrierFrameInputPositionsV1",
    "CarrierFrameInputTotalSecondsV1",
    "CarrierFrameInputFixedStepSecondsV1",
    "CarrierFrameInputElapsedSecondsV1",
)
FORBIDDEN = (
    "InputAuthoredBodyQuats",
    "InputAuthoredGimbalQuats",
    "CameraTransform",
    "CameraOperator",
    "PlaybackTime",
    "Event",
    "Cue",
    "Repository",
    "Server",
)
VECTOR_DEFAULTS = {
    "0, 0, 0": (0.0, 0.0, 0.0),
    "1, 0, 0": (1.0, 0.0, 0.0),
    "0, 1, 0": (0.0, 1.0, 0.0),
    "0, 0, 1": (0.0, 0.0, 1.0),
    "(X=0.000000,Y=0.000000,Z=0.000000)": (0.0, 0.0, 0.0),
    "(X=1.000000,Y=0.000000,Z=0.000000)": (1.0, 0.0, 0.0),
    "(X=0.000000,Y=1.000000,Z=0.000000)": (0.0, 1.0, 0.0),
    "(X=0.000000,Y=0.000000,Z=1.000000)": (0.0, 0.0, 1.0),
}
QUAT_DEFAULTS = {
    "0, 0, 0, 1": (0.0, 0.0, 0.0, 1.0),
    "(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)": (0.0, 0.0, 0.0, 1.0),
}


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_reset_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def explicit_default(node, name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[name].body)
    return "" if match is None else match.group(1)


def scalar_value(value):
    if value == "false":
        return False
    if value == "true":
        return True
    if value in VECTOR_DEFAULTS:
        return VECTOR_DEFAULTS[value]
    if value in QUAT_DEFAULTS:
        return QUAT_DEFAULTS[value]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
        return float(value)
    return value


class Interpreter:
    def __init__(self, nodes, state, paste):
        self.nodes = nodes
        self.state = dict(state)
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)
        entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if paste:
            self.current = next(node for node in nodes.values() if member(node) == "CarrierFrameCompileValidV1" and not node.pins["execute"].links)
        else:
            self.current = self.next(entries[0])

    def next(self, node):
        for link in node.pins["then"].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def linked_getter(self, node):
        for link in node.pins["TargetArray"].links:
            target = self.pin_owner[link]
            if "K2Node_VariableGet" in target[0].node_class:
                return target[0]
        return None

    def run(self):
        visited = []
        while self.current is not None:
            node = self.current
            visited.append(node.name)
            name = member(node)
            if name == "Array_Clear":
                getter = self.linked_getter(node)
                if getter is None:
                    raise RuntimeError("Array_Clear source contract")
                self.state[member(getter)] = []
            elif "K2Node_VariableSet" in node.node_class:
                self.state[name] = scalar_value(explicit_default(node, name))
            else:
                raise RuntimeError(f"unsupported reset node {node.name}:{name}")
            self.current = self.next(node)
        if len(visited) != len(ARRAYS) + len(DEFAULTS):
            raise RuntimeError(f"reset traversal count {len(visited)}")
        return self.state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (24 if args.paste else 25), f"reset node count {len(nodes)}")
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

    setters = {member(node): node for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(set(setters) == set(DEFAULTS), "exact carrier reset scalar ownership")
    for name, expected in DEFAULTS.items():
        actual = explicit_default(setters[name], name)
        if expected in QUAT_DEFAULTS:
            contracts.require(actual in QUAT_DEFAULTS, f"{name} quaternion default changed: {actual!r}")
        elif expected in VECTOR_DEFAULTS:
            contracts.require(actual in VECTOR_DEFAULTS and VECTOR_DEFAULTS[actual] == VECTOR_DEFAULTS[expected], f"{name} vector default changed: {actual!r}")
        else:
            contracts.require(actual == expected, f"{name} default changed: {actual!r}")

    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "staged path and evaluation input must be preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "external or authored-track ownership forbidden")

    chain = [
        setters["CarrierFrameCompileValidV1"],
        setters["CarrierFrameResultValidV1"],
        setters["CarrierFrameStageValidV1"],
        *clears,
        *(setters[name] for name in list(DEFAULTS)[3:]),
    ]
    if args.paste:
        contracts.require(not chain[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", chain[0], "execute", "entry must invalidate compile authority first")
    for left, right in zip(chain, chain[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")

    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knot forbidden")

    preserved = {name: object() for name in PRESERVED}
    state = dict(preserved)
    state.update({name: ["poison"] for name in ARRAYS})
    state.update({name: "poison" for name in DEFAULTS})
    result = Interpreter(nodes, state, args.paste).run()
    contracts.require(all(result[name] == [] for name in ARRAYS), "array reset execution failed")
    contracts.require(all(result[name] == scalar_value(value) for name, value in DEFAULTS.items()), "scalar reset execution failed")
    contracts.require(all(result[name] is value for name, value in preserved.items()), "preserved input mutated")
    contracts.require(result["CarrierFrameCompileValidV1"] is False and result["CarrierFrameResultValidV1"] is False, "authority survived reset")
    print(f"Carrier-frame transport reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
