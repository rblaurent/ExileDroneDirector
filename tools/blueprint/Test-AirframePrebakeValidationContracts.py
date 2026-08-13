"""Structural and executable contracts for fixed-step prebake validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


BODY = "AirframePrebakeInputDesiredBodyQuatsV1"
GIMBAL = "AirframePrebakeInputDesiredGimbalQuatsV1"
RATES = "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"
TOTAL = "AirframePrebakeInputTotalSecondsV1"
STEP = "AirframePrebakeInputFixedStepSecondsV1"
STAGE = "AirframePrebakeStageValidV1"
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_validation_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return "" if match is None else match.group(1)


class Interpreter:
    def __init__(self, contracts, nodes, state):
        self.contracts = contracts
        self.nodes = nodes
        self.state = dict(state)
        self.loop_values = {}
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)

    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in target[1].body:
                return target[0], target[1].name
        return None

    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        if source:
            return self.output(*source)
        text = default(node, pin_name)
        if text == "true":
            return True
        if text == "false":
            return False
        try:
            return float(text)
        except ValueError:
            return text

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[member(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name == "Array Element":
                return self.loop_values[node.name]
            raise RuntimeError(f"unsupported loop output {pin_name}")
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        if name == "Quat_IsFinite":
            return all(math.isfinite(value) for value in self.value(node, "Q"))
        if name == "Quat_Size":
            return math.sqrt(sum(value * value for value in self.value(node, "Q")))
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "GreaterEqual_IntInt" or name == "GreaterEqual_DoubleDouble":
            return left >= right
        if name == "LessEqual_IntInt" or name == "LessEqual_DoubleDouble":
            return left <= right
        if name == "EqualEqual_IntInt":
            return left == right
        if name == "Greater_DoubleDouble":
            return left > right
        if name == "Less_DoubleDouble":
            return left < right
        if name == "Subtract_IntInt":
            return int(left) - int(right)
        if name == "Multiply_DoubleDouble":
            return left * right
        raise RuntimeError(f"unsupported node {node.name}:{name}")

    def next(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.next(entries[0])
        else:
            setters = [node for node in self.nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == STAGE]
            current = next(node for node in setters if not node.pins["execute"].links)
        while current is not None:
            if "K2Node_VariableSet" in current.node_class:
                self.state[member(current)] = self.value(current, member(current))
                current = self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                values = self.value(current, "Array")
                body = self.next(current, "LoopBody")
                if body is None or "K2Node_IfThenElse" not in body.node_class:
                    raise RuntimeError("loop body contract")
                for value in values:
                    self.loop_values[current.name] = value
                    if not self.value(body, "Condition"):
                        reject = self.next(body, "else")
                        if reject is None:
                            raise RuntimeError("missing rejection")
                        self.state[member(reject)] = self.value(reject, member(reject))
                current = self.next(current, "Completed")
            else:
                raise RuntimeError(current.name)
        return self.state[STAGE]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (72 if args.paste else 73), f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")

    getters = {}
    for name in (BODY, GIMBAL, RATES, TOTAL, STEP):
        matches = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and f'MemberName="{name}"' in node.text]
        contracts.require(len(matches) == 1, f"{name} getter count")
        getters[name] = matches[0]
    lengths = [node for node in nodes.values() if member(node) == "Array_Length"]
    contracts.require(len(lengths) == 3, "three array lengths")
    body_length = next(node for node in lengths if contracts.linked(getters[BODY], BODY, node, "TargetArray"))
    gimbal_length = next(node for node in lengths if contracts.linked(getters[GIMBAL], GIMBAL, node, "TargetArray"))
    rate_length = next(node for node in lengths if contracts.linked(getters[RATES], RATES, node, "TargetArray"))

    count_lower = next(node for node in nodes.values() if member(node) == "GreaterEqual_IntInt")
    count_upper = next(node for node in nodes.values() if member(node) == "LessEqual_IntInt")
    contracts.require(default(count_lower, "B") == "2" and contracts.linked(body_length, "ReturnValue", count_lower, "A"), "minimum sample count")
    contracts.require(default(count_upper, "B") == "65536" and contracts.linked(body_length, "ReturnValue", count_upper, "A"), "maximum sample count")
    equalities = [node for node in nodes.values() if member(node) == "EqualEqual_IntInt"]
    contracts.require(len(equalities) == 2, "two cardinality equalities")
    contracts.require(any(contracts.linked(gimbal_length, "ReturnValue", node, "A") and contracts.linked(body_length, "ReturnValue", node, "B") for node in equalities), "gimbal cardinality")
    contracts.require(any(contracts.linked(rate_length, "ReturnValue", node, "A") and contracts.linked(body_length, "ReturnValue", node, "B") for node in equalities), "rate cardinality")

    subtracts = [node for node in nodes.values() if member(node) == "Subtract_IntInt"]
    conversions = [node for node in nodes.values() if member(node) == "Conv_IntToDouble"]
    multiplies = [node for node in nodes.values() if member(node) == "Multiply_DoubleDouble"]
    contracts.require(len(subtracts) == len(conversions) == len(multiplies) == 2, "exact schedule arithmetic")
    contracts.require({default(node, "B") for node in subtracts} == {"1", "2"}, "schedule index offsets")
    for node in subtracts:
        contracts.require_link(body_length, "ReturnValue", node, "A", "schedule must use sample count")
    for node in conversions:
        contracts.require(any(contracts.linked(source, "ReturnValue", node, "InInt") for source in subtracts), "schedule conversion")
    for node in multiplies:
        contracts.require(contracts.linked(getters[STEP], STEP, node, "B"), "schedule duration must use fixed step")

    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 3, "three validation loops")
    body_loop = next(node for node in loops if contracts.linked(getters[BODY], BODY, node, "Array"))
    gimbal_loop = next(node for node in loops if contracts.linked(getters[GIMBAL], GIMBAL, node, "Array"))
    rate_loop = next(node for node in loops if contracts.linked(getters[RATES], RATES, node, "Array"))
    quat_finite = [node for node in nodes.values() if member(node) == "Quat_IsFinite"]
    quat_size = [node for node in nodes.values() if member(node) == "Quat_Size"]
    contracts.require(len(quat_finite) == len(quat_size) == 2, "two exact quaternion guards")
    for loop in (body_loop, gimbal_loop):
        contracts.require(any(contracts.linked(loop, "Array Element", node, "Q") for node in quat_finite), "quat finite loop binding")
        contracts.require(any(contracts.linked(loop, "Array Element", node, "Q") for node in quat_size), "quat norm loop binding")
    lower_norm = [node for node in nodes.values() if member(node) == "GreaterEqual_DoubleDouble" and default(node, "B") == "0.999999"]
    upper_norm = [node for node in nodes.values() if member(node) == "LessEqual_DoubleDouble" and default(node, "B") == "1.000001"]
    contracts.require(len(lower_norm) == len(upper_norm) == 2, "exact quaternion tolerance")
    contracts.require(any(member(node) == "Greater_DoubleDouble" and default(node, "B") == "0.0" and contracts.linked(rate_loop, "Array Element", node, "A") for node in nodes.values()), "positive rate guard")
    contracts.require(any(member(node) == "LessEqual_DoubleDouble" and default(node, "B") == "720.0" and contracts.linked(rate_loop, "Array Element", node, "A") for node in nodes.values()), "maximum rate guard")

    stage_sets = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == STAGE]
    contracts.require(len(stage_sets) == 5, "reset accept and three rejection writes")
    stage_defaults = [default(node, STAGE) for node in stage_sets]
    contracts.require(stage_defaults.count("true") == 1 and stage_defaults.count("false") == 4, "stage validity writes")
    forbidden = tuple(name for name in (
        "AirframePrebakeCompiledBodyQuatsV1", "AirframePrebakeCompiledGimbalQuatsV1",
        "AirframePrebakeCompileValidV1", "AirframePrebakeResultValidV1",
    ))
    contracts.require(not any(f'MemberName="{name}"' in node.text for name in forbidden for node in nodes.values()), "validation mutated publication")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    text = "\n".join(node.text for node in nodes.values())
    contracts.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text, "unsafe graph form")

    valid_cases = [
        {BODY: [IDENTITY, IDENTITY], GIMBAL: [IDENTITY, IDENTITY], RATES: [90.0, 90.0], TOTAL: 0.001, STEP: 1/60, STAGE: True},
        {BODY: [IDENTITY] * 5, GIMBAL: [IDENTITY] * 5, RATES: [720.0] * 5, TOTAL: 1.0, STEP: 0.25, STAGE: False},
        {BODY: [IDENTITY] * 5, GIMBAL: [IDENTITY] * 5, RATES: [1.0] * 5, TOTAL: 1.0, STEP: 0.3, STAGE: False},
    ]
    rng = random.Random(0xEDD_0B84)
    for _ in range(100):
        count = rng.randint(2, 40)
        step = rng.uniform(1/240, 0.5)
        total = rng.uniform((count - 2) * step + max(1e-9, step * 1e-8), (count - 1) * step)
        valid_cases.append({BODY: [IDENTITY] * count, GIMBAL: [IDENTITY] * count,
                            RATES: [rng.uniform(0.001, 720.0) for _ in range(count)],
                            TOTAL: total, STEP: step, STAGE: rng.choice((True, False))})
    for index, state in enumerate(valid_cases):
        contracts.require(Interpreter(contracts, nodes, state).run() is True, f"valid executable case {index}")

    base = {BODY: [IDENTITY] * 5, GIMBAL: [IDENTITY] * 5, RATES: [90.0] * 5, TOTAL: 1.0, STEP: 0.25, STAGE: True}
    invalid_states = []
    for name, value in (
        (BODY, [IDENTITY]), (GIMBAL, [IDENTITY] * 4), (RATES, [90.0] * 4),
        (TOTAL, 0.0), (TOTAL, 3600.001), (TOTAL, math.nan), (TOTAL, math.inf),
        (STEP, 1/241), (STEP, 0.501), (STEP, math.nan), (STEP, math.inf),
        (TOTAL, 0.75), (TOTAL, 1.001),
    ):
        invalid_states.append({**base, name: value})
    for stream in (BODY, GIMBAL):
        for bad in ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0000011), (math.nan, 0.0, 0.0, 1.0), (math.inf, 0.0, 0.0, 1.0)):
            values = list(base[stream]); values[2] = bad
            invalid_states.append({**base, stream: values})
    for bad in (0.0, -1.0, 720.001, math.nan, math.inf, -math.inf):
        values = list(base[RATES]); values[2] = bad
        invalid_states.append({**base, RATES: values})
    class Oversized:
        def __len__(self): return 65537
    invalid_states.append({**base, BODY: Oversized(), GIMBAL: Oversized(), RATES: Oversized()})
    for index, state in enumerate(invalid_states):
        contracts.require(Interpreter(contracts, nodes, state).run() is False, f"invalid executable case {index}")
    print(f"Airframe prebake validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid_cases)} valid, {len(invalid_states)} invalid")


if __name__ == "__main__":
    main()
