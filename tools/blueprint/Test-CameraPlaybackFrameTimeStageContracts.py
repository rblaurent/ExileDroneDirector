"""Structural and exported-link execution contracts for playback time staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


INPUT = "CameraPlaybackInputElapsedSecondsV1"
TARGETS = (
    "CinematicPoseInputElapsedSecondsV1",
    "AirframePrebakeInputElapsedSecondsV1",
    "CarrierFrameInputElapsedSecondsV1",
    "CameraChannelQueryTimeV1",
)
WRITES = set(TARGETS) | {"CameraPlaybackStageValidV1", "CameraPlaybackFailureCodeV1"}
PRESERVED = (
    "CameraPlaybackInputDeltaSecondsV1", "CameraPlaybackInputRequestedModeV1",
    "CameraPlaybackInputTranslationV1", "CameraPlaybackInputLookV1",
    "CameraPlaybackInputRecenterRequestedV1",
    "CameraPlaybackInputReturnToDirectedRequestedV1",
    "CameraPlaybackInputProceduralTranslationOffsetV1",
    "CameraPlaybackInputProceduralRotationOffsetV1",
    "CameraPlaybackSourcesValidV1", "CameraPlaybackOperatorStageValidV1",
    "CameraPlaybackComfortStageValidV1", "CameraPlaybackResultValidV1",
)
FORBIDDEN = (
    "CinematicPoseResult", "AirframePrebakeResult", "CarrierFrameResult",
    "CameraChannelResult", "CameraOperator", "CameraComfort", "CameraApply",
    "CameraTransform", "BodyQuat", "GimbalQuat", "DroneCameraRef", "Event",
    "Repository", "Server",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_time_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def explicit_default(node, pin_name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
    return "" if match is None else match.group(1)


class Interpreter:
    def __init__(self, nodes, elapsed, prior, paste):
        self.nodes = nodes
        self.state = {INPUT: elapsed, **prior}
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)
        if paste:
            self.current = next(
                node for node in nodes.values()
                if member(node) == "CameraPlaybackStageValidV1"
                and explicit_default(node, "CameraPlaybackStageValidV1") == "false"
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

    def linked_output(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in target[1].body:
                return target
        return None

    def value(self, node, pin_name):
        linked = self.linked_output(node, pin_name)
        if linked is None:
            raw = explicit_default(node, pin_name)
            if raw in ("true", "false"):
                return raw == "true"
            return float(raw)
        source, pin = linked
        name = member(source)
        if "K2Node_VariableGet" in source.node_class:
            return self.state[name]
        if name == "GreaterEqual_DoubleDouble":
            return self.value(source, "A") >= self.value(source, "B")
        if name == "LessEqual_DoubleDouble":
            return self.value(source, "A") <= self.value(source, "B")
        if name == "BooleanAND":
            return self.value(source, "A") is True and self.value(source, "B") is True
        raise RuntimeError(f"unsupported value source {source.name}:{name}:{pin.name}")

    def run(self):
        visited = []
        while self.current is not None:
            node = self.current
            visited.append(node.name)
            name = member(node)
            if "K2Node_IfThenElse" in node.node_class:
                self.current = self.next(node, "then" if self.value(node, "Condition") else "else")
                continue
            if "K2Node_VariableSet" not in node.node_class:
                raise RuntimeError(f"unsupported executable node {node.name}:{name}")
            linked = self.linked_output(node, name)
            if linked is not None:
                source, _pin = linked
                self.state[name] = self.state[member(source)]
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
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (13 if args.paste else 14), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == {INPUT}, "elapsed is the sole read")
    contracts.require(setters == WRITES, "exact query-stage writes")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require("GreaterEqual_DoubleDouble" in text and "LessEqual_DoubleDouble" in text, "finite bounds")
    contracts.require(text.count('MemberName="BooleanAND"') == 1, "one finite conjunction")
    contracts.require(not any(name in text for name in PRESERVED), "delta, other inputs, and downstream authority preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "unrelated ownership forbidden")

    rng = random.Random(0xEDD9F1)
    valid = (-1.7976931348623157e308, -100.0, -1.0, 0.0, 1.0, 100.0, 1.7976931348623157e308)
    valid += tuple(rng.uniform(-10000.0, 10000.0) for _ in range(73))
    for index, elapsed in enumerate(valid):
        prior = {name: object() for name in TARGETS + PRESERVED}
        prior.update(CameraPlaybackStageValidV1=True, CameraPlaybackFailureCodeV1="poison")
        before_preserved = {name: prior[name] for name in PRESERVED}
        state, _visited = Interpreter(nodes, elapsed, prior, args.paste).run()
        contracts.require(state["CameraPlaybackStageValidV1"] is True, f"valid {index} stage")
        contracts.require(state["CameraPlaybackFailureCodeV1"] == "", f"valid {index} failure")
        contracts.require(all(state[name] == elapsed for name in TARGETS), f"valid {index} exact common query")
        contracts.require(all(state[name] is before_preserved[name] for name in PRESERVED), f"valid {index} preserved")
    for elapsed in (math.nan, math.inf, -math.inf):
        prior = {name: object() for name in TARGETS + PRESERVED}
        prior.update(CameraPlaybackStageValidV1=True, CameraPlaybackFailureCodeV1="poison")
        before_queries = {name: prior[name] for name in TARGETS}
        state, _visited = Interpreter(nodes, elapsed, prior, args.paste).run()
        contracts.require(state["CameraPlaybackStageValidV1"] is False, "invalid stage")
        contracts.require(state["CameraPlaybackFailureCodeV1"] == "query_invalid", "invalid failure")
        contracts.require(all(state[name] is before_queries[name] for name in TARGETS), "invalid preserves prior queries")
    print(f"Camera playback time-stage contracts passed ({'paste' if args.paste else 'full'}): 80 valid, 3 non-finite")


if __name__ == "__main__":
    main()
