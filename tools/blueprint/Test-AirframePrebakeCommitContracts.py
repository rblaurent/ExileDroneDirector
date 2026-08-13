"""Structural and executable contracts for CommitCompiledAirframePrebakeV1."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CHANNELS = (
    ("BodyQuats", "quat"),
    ("GimbalQuats", "quat"),
    ("BodyAngularRatesDegreesPerSecond", "real"),
    ("GimbalAngularRatesDegreesPerSecond", "real"),
    ("BodyRateLimited", "bool"),
    ("GimbalRateLimited", "bool"),
)
STAGE_VALID = "AirframePrebakeStageValidV1"
STAGE_INDEX = "AirframePrebakeStageIndexV1"
INPUT_STEP = "AirframePrebakeInputFixedStepSecondsV1"
INPUT_TOTAL = "AirframePrebakeInputTotalSecondsV1"
COMPILED_STEP = "AirframePrebakeCompiledFixedStepSecondsV1"
COMPILED_TOTAL = "AirframePrebakeCompiledTotalSecondsV1"
COMPILE_VALID = "AirframePrebakeCompileValidV1"
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_commit_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def variable(node):
    match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"variable name missing: {node.name}")
    return match.group(1)


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return "" if match is None else match.group(1)


def candidate(suffix):
    return f"AirframePrebakeCandidate{suffix}V1"


def compiled(suffix):
    return f"AirframePrebakeCompiled{suffix}V1"


class HugeSequence:
    def __len__(self):
        return 65537


class Interpreter:
    def __init__(self, nodes, state):
        self.nodes = nodes
        self.state = dict(state)
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)

    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and 'Direction="EGPD_Output"' in target[1].body:
                return target[0], target[1].name
        return None

    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        if source is not None:
            return self.output(*source)
        text = default(node, pin_name)
        if text == "" and 'PinType.PinCategory="real"' in node.pins[pin_name].body:
            return 0.0
        if text == "true":
            return True
        if text == "false":
            return False
        try:
            return int(text) if re.fullmatch(r"-?\d+", text) else float(text)
        except ValueError:
            return text

    def output(self, node, pin_name):
        if "K2Node_Variable" in node.node_class:
            return self.state[variable(node)]
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "Subtract_IntInt":
            return int(self.value(node, "A")) - int(self.value(node, "B"))
        if name == "GreaterEqual_IntInt":
            return int(self.value(node, "A")) >= int(self.value(node, "B"))
        if name == "LessEqual_IntInt":
            return int(self.value(node, "A")) <= int(self.value(node, "B"))
        if name == "EqualEqual_IntInt":
            return int(self.value(node, "A")) == int(self.value(node, "B"))
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        raise RuntimeError(f"unsupported output {node.name}:{name}.{pin_name}")

    def exec_target(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and target[1].name == "execute":
                return target[0]
        return None

    def array_owner(self, node):
        source = self.source(node, "TargetArray")
        if source is None or "K2Node_VariableGet" not in source[0].node_class:
            raise RuntimeError(f"clear target is not explicit storage: {node.name}")
        return variable(source[0])

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.exec_target(entries[0])
        else:
            roots = [node for node in self.nodes.values() if "execute" in node.pins and not node.pins["execute"].links]
            if len(roots) != 1:
                raise RuntimeError(f"paste root count {len(roots)}")
            current = roots[0]
        visits = 0
        while current is not None:
            visits += 1
            if visits > 64:
                raise RuntimeError("execution cycle")
            if "K2Node_CallArrayFunction" in current.node_class and member(current) == "Array_Clear":
                self.state[self.array_owner(current)] = []
                current = self.exec_target(current)
            elif "K2Node_VariableSet" in current.node_class:
                name = variable(current)
                value = self.value(current, name)
                self.state[name] = list(value) if "PinType.ContainerType=Array" in current.pins[name].body else value
                current = self.exec_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.exec_target(current, "then" if self.value(current, "Condition") else "else")
            else:
                raise RuntimeError(f"unsupported execution node {current.name}:{member(current)}")
        return self.state


def valid_state(count=4):
    values = {
        STAGE_VALID: True,
        STAGE_INDEX: count - 1,
        INPUT_STEP: 0.3,
        INPUT_TOTAL: 0.91,
        COMPILED_STEP: 99.0,
        COMPILED_TOTAL: 99.0,
        COMPILE_VALID: True,
    }
    sample_values = {
        "BodyQuats": [IDENTITY, (0.1, 0.0, 0.0, 0.994987), (0.2, 0.0, 0.0, 0.979796), (0.3, 0.0, 0.0, 0.953939)],
        "GimbalQuats": [IDENTITY, (0.0, 0.1, 0.0, 0.994987), (0.0, 0.2, 0.0, 0.979796), (0.0, 0.3, 0.0, 0.953939)],
        "BodyAngularRatesDegreesPerSecond": [0.0, 10.0, 20.0, 30.0],
        "GimbalAngularRatesDegreesPerSecond": [0.0, 5.0, 10.0, 15.0],
        "BodyRateLimited": [False, False, True, True],
        "GimbalRateLimited": [False, True, False, True],
    }
    for suffix, _kind in CHANNELS:
        values[candidate(suffix)] = sample_values[suffix][:count]
        values[compiled(suffix)] = ["stale"]
    return values


def assert_failed(contracts, nodes, state, label):
    original_candidates = {candidate(suffix): state[candidate(suffix)] for suffix, _ in CHANNELS}
    result = Interpreter(nodes, state).run()
    contracts.require(result[COMPILE_VALID] is False, f"{label}: validity leaked")
    contracts.require(result[COMPILED_STEP] == 0.0 and result[COMPILED_TOTAL] == 0.0, f"{label}: schedule leaked")
    contracts.require(all(result[compiled(suffix)] == [] for suffix, _ in CHANNELS), f"{label}: compiled payload leaked")
    contracts.require(all(result[candidate(suffix)] is original_candidates[candidate(suffix)] for suffix, _ in CHANNELS), f"{label}: candidates mutated")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (58 if args.paste else 59), f"commit node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "function entry count")
    text = "\n".join(node.text for node in nodes.values())
    contracts.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text, "unsafe graph form")

    clears = [node for node in nodes.values() if member(node) == "Array_Clear"]
    lengths = [node for node in nodes.values() if member(node) == "Array_Length"]
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(clears) == 6 and len(lengths) == 6 and len(branches) == 1, "six-channel atomic shape")
    for suffix, _kind in CHANNELS:
        candidate_name = candidate(suffix)
        compiled_name = compiled(suffix)
        contracts.require(len([node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and variable(node) == candidate_name]) == 1, f"one candidate read {candidate_name}")
        compiled_get = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and variable(node) == compiled_name)
        contracts.require(sum(contracts.linked(compiled_get, compiled_name, node, "TargetArray") for node in clears) == 1, f"one preflight clear {compiled_name}")
        setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and variable(node) == compiled_name]
        contracts.require(len(setters) == 1, f"one publication {compiled_name}")

    valid_sets = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and variable(node) == COMPILE_VALID]
    contracts.require(len(valid_sets) == 2, "validity reset and publication")
    reset_valid = next(node for node in valid_sets if default(node, COMPILE_VALID) == "false")
    publish_valid = next(node for node in valid_sets if default(node, COMPILE_VALID) == "true")
    publish_total = next(
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class
        and variable(node) == COMPILED_TOTAL
        and bool(node.pins[COMPILED_TOTAL].links)
    )
    contracts.require(contracts.linked(publish_total, "then", publish_valid, "execute"), "compile-validity must be final publication write")
    contracts.require(any(contracts.linked(reset_valid, "then", node, "execute") for node in branches), "guard only after invalidation")
    contracts.require(not any("AirframePrebakeResult" in variable(node) for node in nodes.values() if "K2Node_Variable" in node.node_class), "commit must not touch evaluation state")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")

    good = valid_state()
    originals = {candidate(suffix): good[candidate(suffix)] for suffix, _ in CHANNELS}
    actual = Interpreter(nodes, good).run()
    contracts.require(actual[COMPILE_VALID] is True, "valid candidate rejected")
    contracts.require(actual[COMPILED_STEP] == good[INPUT_STEP] and actual[COMPILED_TOTAL] == good[INPUT_TOTAL], "schedule not copied exactly")
    for suffix, _kind in CHANNELS:
        contracts.require(actual[compiled(suffix)] == good[candidate(suffix)], f"channel not copied: {suffix}")
        contracts.require(actual[compiled(suffix)] is not originals[candidate(suffix)], f"channel aliases candidate: {suffix}")
        contracts.require(actual[candidate(suffix)] is originals[candidate(suffix)], f"candidate mutated: {suffix}")

    stage_false = valid_state(); stage_false[STAGE_VALID] = False
    assert_failed(contracts, nodes, stage_false, "false stage")
    count_one = valid_state(1); count_one[STAGE_INDEX] = 0
    assert_failed(contracts, nodes, count_one, "count one")
    wrong_index = valid_state(); wrong_index[STAGE_INDEX] = 2
    assert_failed(contracts, nodes, wrong_index, "wrong terminal index")
    for suffix, _kind in CHANNELS[1:]:
        mismatch = valid_state(); mismatch[candidate(suffix)] = mismatch[candidate(suffix)][:-1]
        assert_failed(contracts, nodes, mismatch, f"mismatched {suffix}")
    huge = valid_state()
    huge_sequence = HugeSequence()
    for suffix, _kind in CHANNELS:
        huge[candidate(suffix)] = huge_sequence
    huge[STAGE_INDEX] = 65536
    assert_failed(contracts, nodes, huge, "count over maximum")

    first = Interpreter(nodes, valid_state()).run()
    second = dict(first)
    second[STAGE_VALID] = False
    for suffix, _kind in CHANNELS:
        second[candidate(suffix)] = []
    assert_failed(contracts, nodes, second, "second invocation after prior success")

    print(
        f"Airframe prebake commit contracts passed ({'paste' if args.paste else 'full'}): "
        "exact six-channel publication, 10 fail-closed cases, invocation independence"
    )


if __name__ == "__main__":
    main()
