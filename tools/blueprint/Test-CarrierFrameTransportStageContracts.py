"""Structural and executable contracts for carrier-frame upstream staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "AirframeDesiredStreamCompileValidV1",
    "AirframeDesiredStreamInputPositionsV1",
    "AirframeDesiredStreamInputTotalSecondsV1",
    "AirframeDesiredStreamInputFixedStepSecondsV1",
}
WRITES = {
    "CarrierFrameInputPositionsV1",
    "CarrierFrameInputTotalSecondsV1",
    "CarrierFrameInputFixedStepSecondsV1",
    "CarrierFrameStageValidV1",
    "CarrierFrameFailureCodeV1",
}
FORBIDDEN = (
    "AuthoredBody",
    "AuthoredGimbal",
    "CameraTransform",
    "CarrierFrameCandidate",
    "CarrierFrameCompiled",
    "CarrierFrameResult",
    "CameraOperator",
    "PlaybackTime",
    "Event",
    "Repository",
    "Server",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_stage_contract_base", path)
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


class Interpreter:
    def __init__(self, nodes, source, prior, paste):
        self.nodes = nodes
        self.state = {**source, **prior}
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)
        if paste:
            self.current = next(
                node for node in nodes.values()
                if member(node) == "CarrierFrameStageValidV1"
                and explicit_default(node, "CarrierFrameStageValidV1") == "false"
                and not node.pins["execute"].links
            )
        else:
            entry = next(node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class)
            self.current = self.next(entry, "then")

    def next(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def linked_source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in target[1].body:
                return member(target[0])
        return None

    def run(self):
        visited = []
        while self.current is not None:
            node = self.current
            visited.append(node.name)
            name = member(node)
            if "K2Node_IfThenElse" in node.node_class:
                condition_name = self.linked_source(node, "Condition")
                branch = "then" if self.state[condition_name] is True else "else"
                self.current = self.next(node, branch)
                continue
            if "K2Node_VariableSet" not in node.node_class:
                raise RuntimeError(f"unsupported stage node {node.name}:{name}")
            source_name = self.linked_source(node, name)
            if source_name is not None:
                value = self.state[source_name]
                self.state[name] = list(value) if isinstance(value, list) else value
            else:
                raw = explicit_default(node, name)
                self.state[name] = raw == "true" if raw in ("true", "false") else raw
            self.current = self.next(node, "then")
        return self.state, visited


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (12 if args.paste else 13), f"stage node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "stage entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, f"exact upstream reads changed: {getters}")
    contracts.require({member(node) for node in setters} == WRITES, "exact stage writes")
    contracts.require(sum(member(node) == "CarrierFrameStageValidV1" for node in setters) == 2, "stage validity must invalidate then publish")
    contracts.require(sum(member(node) == "CarrierFrameFailureCodeV1" for node in setters) == 2, "failure must clear then diagnose")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "authored/external ownership forbidden")

    invalidator = next(node for node in setters if member(node) == "CarrierFrameStageValidV1" and explicit_default(node, "CarrierFrameStageValidV1") == "false")
    publisher = next(node for node in setters if member(node) == "CarrierFrameStageValidV1" and explicit_default(node, "CarrierFrameStageValidV1") == "true")
    failure = next(node for node in setters if member(node) == "CarrierFrameFailureCodeV1" and explicit_default(node, "CarrierFrameFailureCodeV1") == "source_invalid")
    guards = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(guards) == 1, "exactly one source guard")
    guard = guards[0]
    source_valid = contracts.one(nodes, 'MemberName="AirframeDesiredStreamCompileValidV1"')
    contracts.require_link(source_valid, "AirframeDesiredStreamCompileValidV1", guard, "Condition", "source validity must be the only branch condition")
    contracts.require_link(guard, "else", failure, "execute", "invalid source diagnostic")
    positions_get = contracts.one(nodes, 'MemberName="AirframeDesiredStreamInputPositionsV1"')
    positions_set = contracts.one(nodes, 'MemberName="CarrierFrameInputPositionsV1"')
    total_get = contracts.one(nodes, 'MemberName="AirframeDesiredStreamInputTotalSecondsV1"')
    total_set = contracts.one(nodes, 'MemberName="CarrierFrameInputTotalSecondsV1"')
    step_get = contracts.one(nodes, 'MemberName="AirframeDesiredStreamInputFixedStepSecondsV1"')
    step_set = contracts.one(nodes, 'MemberName="CarrierFrameInputFixedStepSecondsV1"')
    contracts.require_link(positions_get, "AirframeDesiredStreamInputPositionsV1", positions_set, "CarrierFrameInputPositionsV1", "positions snapshot")
    contracts.require_link(total_get, "AirframeDesiredStreamInputTotalSecondsV1", total_set, "CarrierFrameInputTotalSecondsV1", "total snapshot")
    contracts.require_link(step_get, "AirframeDesiredStreamInputFixedStepSecondsV1", step_set, "CarrierFrameInputFixedStepSecondsV1", "step snapshot")
    contracts.require_link(step_set, "then", publisher, "execute", "validity publishes last")
    if args.paste:
        contracts.require(not invalidator.pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", invalidator, "execute", "entry invalidates first")

    randomizer = random.Random(0xCA221E2)
    protected_names = ("CarrierFrameCompileValidV1", "CarrierFrameCompiledQuatsV1", "CameraOperatorInputCarrierFrameQuatV1")
    for index in range(80):
        positions = [(randomizer.uniform(-1e4, 1e4), randomizer.uniform(-1e4, 1e4), randomizer.uniform(-1e4, 1e4)) for _ in range(randomizer.randint(2, 20))]
        source = {
            "AirframeDesiredStreamCompileValidV1": True,
            "AirframeDesiredStreamInputPositionsV1": positions,
            "AirframeDesiredStreamInputTotalSecondsV1": randomizer.uniform(0.01, 30.0),
            "AirframeDesiredStreamInputFixedStepSecondsV1": randomizer.uniform(1.0 / 240.0, 0.5),
        }
        protected = {name: object() for name in protected_names}
        prior = {
            "CarrierFrameInputPositionsV1": ["poison"],
            "CarrierFrameInputTotalSecondsV1": "poison",
            "CarrierFrameInputFixedStepSecondsV1": "poison",
            "CarrierFrameStageValidV1": True,
            "CarrierFrameFailureCodeV1": "poison",
            **protected,
        }
        result, visited = Interpreter(nodes, source, prior, args.paste).run()
        contracts.require(result["CarrierFrameStageValidV1"] is True and result["CarrierFrameFailureCodeV1"] == "", f"valid publication {index}")
        contracts.require(result["CarrierFrameInputPositionsV1"] == positions and result["CarrierFrameInputPositionsV1"] is not positions, f"position value snapshot {index}")
        contracts.require(result["CarrierFrameInputTotalSecondsV1"] == source["AirframeDesiredStreamInputTotalSecondsV1"], f"total snapshot {index}")
        contracts.require(result["CarrierFrameInputFixedStepSecondsV1"] == source["AirframeDesiredStreamInputFixedStepSecondsV1"], f"step snapshot {index}")
        contracts.require(all(result[name] is value for name, value in protected.items()), f"protected ownership {index}")
        contracts.require(len(visited) == 7, f"valid execution traversal {index}:{visited}")

    old_positions = [(1.0, 2.0, 3.0)]
    protected = {name: object() for name in protected_names}
    invalid_source = {
        "AirframeDesiredStreamCompileValidV1": False,
        "AirframeDesiredStreamInputPositionsV1": [(9.0, 9.0, 9.0)],
        "AirframeDesiredStreamInputTotalSecondsV1": math.nan,
        "AirframeDesiredStreamInputFixedStepSecondsV1": math.inf,
    }
    prior = {
        "CarrierFrameInputPositionsV1": old_positions,
        "CarrierFrameInputTotalSecondsV1": 4.0,
        "CarrierFrameInputFixedStepSecondsV1": 0.25,
        "CarrierFrameStageValidV1": True,
        "CarrierFrameFailureCodeV1": "poison",
        **protected,
    }
    failed, visited = Interpreter(nodes, invalid_source, prior, args.paste).run()
    contracts.require(failed["CarrierFrameStageValidV1"] is False and failed["CarrierFrameFailureCodeV1"] == "source_invalid", "invalid source fails closed")
    contracts.require(failed["CarrierFrameInputPositionsV1"] is old_positions, "invalid source preserves prior position snapshot")
    contracts.require(failed["CarrierFrameInputTotalSecondsV1"] == 4.0 and failed["CarrierFrameInputFixedStepSecondsV1"] == 0.25, "invalid source preserves prior schedule")
    contracts.require(all(failed[name] is value for name, value in protected.items()), "invalid source protected ownership")
    contracts.require(len(visited) == 4, f"invalid execution traversal:{visited}")
    print(f"Carrier-frame stage contracts passed ({'paste' if args.paste else 'full'}): 80 valid snapshots, source-invalid preservation")


if __name__ == "__main__":
    main()
