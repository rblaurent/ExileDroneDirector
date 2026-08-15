"""Structural and exported-link execution contracts for distinct operator staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


COMPILE_VALID = (
    "CinematicPoseCompileValidV1", "AirframePrebakeCompileValidV1",
    "CarrierFrameCompileValidV1", "CameraChannelCompileValidV1",
)
RESULT_VALID = (
    "CinematicPoseResultValidV1", "AirframePrebakeResultValidV1",
    "CarrierFrameResultValidV1", "CameraChannelResultValidV1",
)
TOTALS = (
    "CinematicPoseCompiledTotalSecondsV1", "AirframePrebakeCompiledTotalSecondsV1",
    "CarrierFrameCompiledTotalSecondsV1", "CameraChannelCompiledDurationV1",
)
COMPLETE = (
    "CinematicPoseResultCompleteV1", "AirframePrebakeResultCompleteV1",
    "CarrierFrameResultCompleteV1", "CameraChannelResultCompleteV1",
)
COPIES = (
    ("CameraPlaybackInputRequestedModeV1", "CameraOperatorInputRequestedModeV1"),
    ("CinematicPoseResultPositionV1", "CameraOperatorInputAuthoredPositionV1"),
    ("AirframePrebakeResultBodyQuatV1", "CameraOperatorInputAuthoredBodyQuatV1"),
    ("AirframePrebakeResultGimbalQuatV1", "CameraOperatorInputAuthoredGimbalQuatV1"),
    ("CarrierFrameResultQuatV1", "CameraOperatorInputCarrierFrameQuatV1"),
    ("CameraPlaybackInputTranslationV1", "CameraOperatorInputTranslationV1"),
    ("CameraPlaybackInputLookV1", "CameraOperatorInputLookV1"),
    ("CameraPlaybackInputDeltaSecondsV1", "CameraOperatorInputDeltaSecondsV1"),
    ("CameraPlaybackInputRecenterRequestedV1", "CameraOperatorInputRecenterRequestedV1"),
    ("CameraPlaybackInputReturnToDirectedRequestedV1", "CameraOperatorInputReturnToDirectedRequestedV1"),
)
STAGE = "CameraPlaybackStageValidV1"
READS = {STAGE, *COMPILE_VALID, *RESULT_VALID, *TOTALS, *COMPLETE, *(source for source, _target in COPIES)}
WRITES = {
    "CameraPlaybackSourcesValidV1", "CameraPlaybackOperatorStageValidV1",
    "CameraPlaybackFailureCodeV1", "CameraOperatorInputSourceValidV1",
    *(target for _source, target in COPIES),
}
PROTECTED = (
    "CinematicPoseResultQuatV1", "AirframePrebakeCompiledBodyQuatsV1",
    "AirframePrebakeCompiledGimbalQuatsV1", "CarrierFrameCompiledQuatsV1",
    "CameraChannelResultValuesV1", "CameraOperatorStateModeV1",
    "CameraOperatorStateLookOffsetQuatV1", "CameraComfortResultGimbalQuatV1",
    "CameraApplyCurrentTargetValuesV1", "PlaybackTime", "RepositoryRecordsV1",
)
FORBIDDEN = (
    "CinematicPoseResultQuatV1", "CameraTransform", "CameraComfortInput",
    "CameraApplyInput", "DroneCameraRef", "Event", "Cue", "StateClip", "Server",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_operator_stage_contract_base", path)
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
        self.nodes = nodes
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
                if member(node) == "CameraPlaybackSourcesValidV1"
                and explicit_default(node, "CameraPlaybackSourcesValidV1") == "false"
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
        source, _pin = linked
        name = member(source)
        if "K2Node_VariableGet" in source.node_class:
            return self.state[name]
        if name == "BooleanAND":
            return self.value(source, "A") is True and self.value(source, "B") is True
        if name == "GreaterEqual_DoubleDouble":
            return self.value(source, "A") >= self.value(source, "B")
        if name == "LessEqual_DoubleDouble":
            return self.value(source, "A") <= self.value(source, "B")
        if name == "Greater_DoubleDouble":
            return self.value(source, "A") > self.value(source, "B")
        if name == "EqualEqual_DoubleDouble":
            return self.value(source, "A") == self.value(source, "B")
        if name == "EqualEqual_BoolBool":
            return self.value(source, "A") is self.value(source, "B")
        raise RuntimeError(f"unsupported value source {source.name}:{name}")

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


def valid_state(total=2.0, complete=False):
    state = {STAGE: True}
    state.update({name: True for name in COMPILE_VALID + RESULT_VALID})
    state.update({name: total for name in TOTALS})
    state.update({name: complete for name in COMPLETE})
    distinct = {
        "CameraPlaybackInputRequestedModeV1": "carrier_freecam",
        "CinematicPoseResultPositionV1": (101.0, 202.0, 303.0),
        "AirframePrebakeResultBodyQuatV1": (0.1, 0.0, 0.0, 0.9949874371),
        "AirframePrebakeResultGimbalQuatV1": (0.0, -0.2, 0.0, 0.9797958971),
        "CarrierFrameResultQuatV1": (0.0, 0.0, 0.3, 0.9539392014),
        "CameraPlaybackInputTranslationV1": (0.25, -0.5, 1.0),
        "CameraPlaybackInputLookV1": (-1.0, 0.5, 0.0),
        "CameraPlaybackInputDeltaSecondsV1": 1.0 / 60.0,
        "CameraPlaybackInputRecenterRequestedV1": False,
        "CameraPlaybackInputReturnToDirectedRequestedV1": True,
    }
    state.update(distinct)
    state.update({name: object() for name in WRITES if name not in state})
    state.update({name: object() for name in PROTECTED})
    state["CameraPlaybackSourcesValidV1"] = True
    state["CameraPlaybackOperatorStageValidV1"] = True
    state["CameraOperatorInputSourceValidV1"] = True
    state["CameraPlaybackFailureCodeV1"] = "poison"
    return state


def assert_failed(contracts, nodes, state, code, paste, label):
    before_targets = {target: state[target] for _source, target in COPIES}
    before_protected = {name: state[name] for name in PROTECTED}
    result, _visited = Interpreter(nodes, state, paste).run()
    contracts.require(result["CameraPlaybackSourcesValidV1"] is False, label + ":sources")
    contracts.require(result["CameraPlaybackOperatorStageValidV1"] is False, label + ":operator-stage")
    contracts.require(result["CameraOperatorInputSourceValidV1"] is False, label + ":operator-source")
    contracts.require(result["CameraPlaybackFailureCodeV1"] == code, label + ":code")
    contracts.require(all(result[name] is before_targets[name] for name in before_targets), label + ":targets preserved")
    contracts.require(all(result[name] is before_protected[name] for name in PROTECTED), label + ":protected preserved")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (92 if args.paste else 93), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact source/control reads")
    contracts.require(setters == WRITES, "exact stage writes")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(token in text for token in FORBIDDEN), "legacy/native/unrelated sources forbidden")
    for source_name, target_name in COPIES:
        source = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == source_name)
        target = next(node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == target_name)
        contracts.require_link(source, source_name, target, target_name, f"exact copy {source_name} to {target_name}")

    rng = random.Random(0xEDD9F2)
    for index in range(80):
        state = valid_state(rng.uniform(0.01, 3600.0), bool(index % 2))
        before_protected = {name: state[name] for name in PROTECTED}
        result, _visited = Interpreter(nodes, state, args.paste).run()
        contracts.require(result["CameraPlaybackSourcesValidV1"] is True, f"valid {index}:sources")
        contracts.require(result["CameraPlaybackOperatorStageValidV1"] is True, f"valid {index}:stage")
        contracts.require(result["CameraOperatorInputSourceValidV1"] is True, f"valid {index}:operator-source")
        contracts.require(result["CameraPlaybackFailureCodeV1"] == "", f"valid {index}:failure")
        for source_name, target_name in COPIES:
            contracts.require(result[target_name] == state[source_name], f"valid {index}:{target_name}")
        contracts.require(result["CameraOperatorInputAuthoredBodyQuatV1"] != result["CameraOperatorInputAuthoredGimbalQuatV1"], f"valid {index}:distinct")
        contracts.require(all(result[name] is before_protected[name] for name in PROTECTED), f"valid {index}:protected")

    state = valid_state(); state[STAGE] = False; state["CameraPlaybackFailureCodeV1"] = "query_invalid"
    assert_failed(contracts, nodes, state, "query_invalid", args.paste, "stage-invalid")
    for name in COMPILE_VALID + RESULT_VALID:
        state = valid_state(); state[name] = False
        assert_failed(contracts, nodes, state, "source_invalid", args.paste, name)
    for index, value in enumerate((0.0, -1.0, math.nan, math.inf, -math.inf)):
        state = valid_state(); state[TOTALS[index % len(TOTALS)]] = value
        assert_failed(contracts, nodes, state, "timeline_mismatch", args.paste, f"timeline-{index}")
    state = valid_state(); state[TOTALS[-1]] += 0.001
    assert_failed(contracts, nodes, state, "timeline_mismatch", args.paste, "timeline-diverge")
    for name in COMPLETE[1:]:
        state = valid_state(complete=False); state[name] = True
        assert_failed(contracts, nodes, state, "completion_mismatch", args.paste, name)
    print(f"Camera playback operator-stage contracts passed ({'paste' if args.paste else 'full'}): 80 valid, 17 failures")


if __name__ == "__main__":
    main()
