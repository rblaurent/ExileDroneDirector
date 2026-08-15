"""Structural and exported-link execution contracts for comfort staging."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


VALIDITY = (
    "CameraPlaybackOperatorStageValidV1", "CameraOperatorResultValidV1",
    "CameraPlaybackSourcesValidV1", "CameraChannelResultValidV1",
)
COPIES = (
    ("CameraOperatorResultPositionV1", "CameraComfortInputPositionV1"),
    ("CameraOperatorResultGimbalQuatV1", "CameraComfortInputGimbalQuatV1"),
    ("CameraPlaybackInputProceduralTranslationOffsetV1", "CameraComfortInputProceduralTranslationOffsetV1"),
    ("CameraPlaybackInputProceduralRotationOffsetV1", "CameraComfortInputProceduralRotationOffsetV1"),
    ("CameraChannelResultValuesV1", "CameraComfortInputChannelValuesV1"),
)
READS = {*VALIDITY, *(source for source, _target in COPIES)}
WRITES = {
    "CameraPlaybackComfortStageValidV1", "CameraComfortInputFrameValidV1",
    "CameraPlaybackFailureCodeV1", *(target for _source, target in COPIES),
}
PROTECTED = (
    "CameraOperatorResultBodyQuatV1", "AirframePrebakeResultBodyQuatV1",
    "AirframePrebakeResultGimbalQuatV1", "CarrierFrameResultQuatV1",
    "CameraOperatorStateModeV1", "CameraOperatorStateLookOffsetQuatV1",
    "CameraComfortEnabledV1", "CameraComfortRollWeightV1",
    "CameraApplyCurrentTargetValuesV1", "CinematicPoseResultQuatV1",
    "RepositoryRecordsV1", "PlaybackTime",
)
FORBIDDEN = (
    "CameraOperatorResultBodyQuatV1", "AirframePrebake", "CarrierFrame",
    "CinematicPoseResultQuatV1", "CameraTransform", "CameraApplyInput",
    "DroneCameraRef", "Repository", "Event", "Cue", "StateClip", "Server",
)


def load(path):
    spec = importlib.util.spec_from_file_location("edd_playback_comfort_stage_contract_base", path)
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
    def __init__(self, nodes, state, paste):
        self.state = dict(state)
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)
        if paste:
            self.current = next(
                node for node in nodes.values()
                if member(node) == "CameraPlaybackComfortStageValidV1"
                and explicit_default(node, "CameraPlaybackComfortStageValidV1") == "false"
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
        source, _pin = linked
        name = member(source)
        if "K2Node_VariableGet" in source.node_class:
            return self.state[name]
        if name == "BooleanAND":
            return self.value(source, "A") is True and self.value(source, "B") is True
        raise RuntimeError(f"unsupported condition {source.name}:{name}")

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
                raise RuntimeError(f"unsupported executable {node.name}:{name}")
            linked = self.linked_output(node, name)
            if linked is not None:
                source_name = member(linked[0])
                value = self.state[source_name]
                self.state[name] = list(value) if isinstance(value, list) else value
            else:
                raw = explicit_default(node, name)
                self.state[name] = raw == "true" if raw in ("true", "false") else raw
            self.current = self.next(node, "then")
        return self.state, visited


def fixture(rng):
    state = {name: True for name in VALIDITY}
    state.update({
        "CameraOperatorResultPositionV1": (rng.random(), rng.random(), rng.random()),
        "CameraOperatorResultGimbalQuatV1": (0.0, 0.0, 0.0, 1.0),
        "CameraPlaybackInputProceduralTranslationOffsetV1": (0.1, -0.2, 0.3),
        "CameraPlaybackInputProceduralRotationOffsetV1": (0.0, 0.0, 0.1, 0.9949874371),
        "CameraChannelResultValuesV1": [35.0, 2.8, 1000.0, 1.0, 0.0, *([0.0] * 8)],
    })
    state.update({name: object() for name in WRITES if name not in state})
    state.update({name: object() for name in PROTECTED})
    state["CameraPlaybackComfortStageValidV1"] = True
    state["CameraComfortInputFrameValidV1"] = True
    state["CameraPlaybackFailureCodeV1"] = "poison"
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (25 if args.paste else 26), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact comfort-stage reads")
    contracts.require(setters == WRITES, "exact comfort-stage writes")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(text.count('MemberName="BooleanAND"') == 2, "two exact validity conjunctions")
    contracts.require(not any(token in text for token in FORBIDDEN), "body/native/authoritative ownership forbidden")
    for source_name, target_name in COPIES:
        source = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == source_name)
        target = next(node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == target_name)
        contracts.require_link(source, source_name, target, target_name, f"exact copy {source_name} to {target_name}")

    rng = random.Random(0xEDD9F3)
    for index in range(80):
        state = fixture(rng)
        protected = {name: state[name] for name in PROTECTED}
        result, _visited = Interpreter(nodes, state, args.paste).run()
        contracts.require(result["CameraPlaybackComfortStageValidV1"] is True, f"valid {index}:stage")
        contracts.require(result["CameraComfortInputFrameValidV1"] is True, f"valid {index}:input")
        contracts.require(result["CameraPlaybackFailureCodeV1"] == "", f"valid {index}:failure")
        for source_name, target_name in COPIES:
            contracts.require(result[target_name] == state[source_name], f"valid {index}:{target_name}")
        contracts.require(result["CameraComfortInputChannelValuesV1"] is not state["CameraChannelResultValuesV1"], f"valid {index}:channel copy")
        contracts.require(all(result[name] is protected[name] for name in PROTECTED), f"valid {index}:protected")

    for name, code in (
        ("CameraPlaybackOperatorStageValidV1", "operator_invalid"),
        ("CameraOperatorResultValidV1", "operator_invalid"),
        ("CameraPlaybackSourcesValidV1", "source_invalid"),
        ("CameraChannelResultValidV1", "source_invalid"),
    ):
        state = fixture(rng); state[name] = False
        prior = {target: state[target] for _source, target in COPIES}
        protected = {item: state[item] for item in PROTECTED}
        result, _visited = Interpreter(nodes, state, args.paste).run()
        contracts.require(result["CameraPlaybackComfortStageValidV1"] is False, name + ":stage")
        contracts.require(result["CameraComfortInputFrameValidV1"] is False, name + ":input")
        contracts.require(result["CameraPlaybackFailureCodeV1"] == code, name + ":failure")
        contracts.require(all(result[item] is prior[item] for item in prior), name + ":inputs preserved")
        contracts.require(all(result[item] is protected[item] for item in PROTECTED), name + ":protected")
    print(f"Camera playback comfort-stage contracts passed ({'paste' if args.paste else 'full'}): 80 valid, 4 failures")


if __name__ == "__main__":
    main()
