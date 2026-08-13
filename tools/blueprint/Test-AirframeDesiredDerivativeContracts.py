"""Exact structural and executable contracts for desired vector derivatives."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


STAGES = {
    "velocity": (
        "BuildAirframeDesiredVelocitySamplesV1",
        "AirframeDesiredStreamInputPositionsV1",
        "AirframeDesiredStreamCandidateVelocitiesV1",
    ),
    "acceleration": (
        "BuildAirframeDesiredAccelerationSamplesV1",
        "AirframeDesiredStreamCandidateVelocitiesV1",
        "AirframeDesiredStreamCandidateAccelerationsV1",
    ),
    "jerk": (
        "BuildAirframeDesiredJerkSamplesV1",
        "AirframeDesiredStreamCandidateAccelerationsV1",
        "AirframeDesiredStreamCandidateJerksV1",
    ),
}
TOTAL = "AirframeDesiredStreamInputTotalSecondsV1"
STEP = "AirframeDesiredStreamInputFixedStepSecondsV1"
VALID = "AirframeDesiredStreamStageValidV1"
INDEX = "AirframeDesiredStreamStageIndexV1"


def load_contracts(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_derivative_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_reference(root: Path):
    path = root / "tools/trajectory/airframe_desired_stream_reference.py"
    trajectory = str(path.parent)
    if trajectory not in sys.path:
        sys.path.insert(0, trajectory)
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_derivative_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, pin_name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
    return "" if match is None else match.group(1)


class Interpreter:
    def __init__(self, nodes, state):
        self.nodes = nodes
        self.state = dict(state)
        self.loop_indices = {}
        self.cache = {}
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
        if text in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"):
            return (0.0, 0.0, 0.0)
        try:
            return float(text)
        except ValueError:
            return text

    def output(self, node, pin_name):
        key = (node.name, pin_name)
        if key not in self.cache:
            self.cache[key] = self._output(node, pin_name)
        return self.cache[key]

    def _output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[member(node)]
        if "K2Node_VariableSet" in node.node_class:
            return self.state[member(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name == "Index":
                return self.loop_indices[node.name]
            raise RuntimeError(f"unsupported loop output {pin_name}")
        if "K2Node_GetArrayItem" in node.node_class:
            return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        if name == "SelectInt":
            return int(self.value(node, "A") if self.value(node, "bPickA") else self.value(node, "B"))
        if name == "MakeVector":
            return tuple(float(self.value(node, axis)) for axis in "XYZ")
        if name == "BreakVector":
            return self.value(node, "InVec")[("X", "Y", "Z").index(pin_name)]
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "EqualEqual_IntInt":
            return int(left) == int(right)
        if name == "GreaterEqual_DoubleDouble":
            return left >= right
        if name == "LessEqual_DoubleDouble":
            return left <= right
        if name == "Add_IntInt":
            return int(left) + int(right)
        if name == "Subtract_IntInt":
            return int(left) - int(right)
        if name == "Add_DoubleDouble":
            return left + right
        if name == "Subtract_DoubleDouble":
            return left - right
        if name == "Multiply_DoubleDouble":
            return left * right
        if name == "Divide_DoubleDouble":
            return left / right
        if name == "Min_DoubleDouble":
            return min(left, right)
        if name in ("Add_VectorVector", "Subtract_VectorVector", "Multiply_VectorVector", "Divide_VectorVector"):
            operation = {
                "Add_VectorVector": lambda a, b: a + b,
                "Subtract_VectorVector": lambda a, b: a - b,
                "Multiply_VectorVector": lambda a, b: a * b,
                "Divide_VectorVector": lambda a, b: a / b,
            }[name]
            return tuple(operation(float(a), float(b)) for a, b in zip(left, right))
        raise RuntimeError(f"unsupported output {node.name}:{name}:{pin_name}")

    def next_target(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec", "Execute", "Break"):
                return target[0], target[1].name
        return None

    def execute_chain(self, current, enclosing_loop=None):
        while current is not None:
            if "K2Node_VariableSet" in current.node_class:
                self.state[member(current)] = self.value(current, member(current))
                self.cache.clear()
                target = self.next_target(current)
            elif member(current) == "Array_Clear":
                source = self.source(current, "TargetArray")
                self.state[member(source[0])] = []
                self.cache.clear()
                target = self.next_target(current)
            elif member(current) == "Array_Add":
                source = self.source(current, "TargetArray")
                self.state[member(source[0])].append(self.value(current, "NewItem"))
                self.cache.clear()
                target = self.next_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                target = self.next_target(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                first = int(self.value(current, "FirstIndex"))
                last = int(self.value(current, "LastIndex"))
                body_target = self.next_target(current, "LoopBody")
                for index in range(first, last + 1):
                    self.loop_indices[current.name] = index
                    self.cache.clear()
                    if body_target is not None and self.execute_chain(body_target[0], current):
                        break
                target = self.next_target(current, "Completed")
            else:
                raise RuntimeError(f"unsupported exec {current.name}:{member(current)}")
            if target is None:
                return False
            if enclosing_loop is not None and target[0] is enclosing_loop and target[1] == "Break":
                return True
            current = target[0]
        return False

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            target = self.next_target(entries[0])
            start = target[0]
        else:
            clear = next(node for node in self.nodes.values() if member(node) == "Array_Clear" and not node.pins["execute"].links)
            start = clear
        self.execute_chain(start)
        return self.state


def schedule(total, step):
    count = math.ceil(total / step) + 1
    return tuple(min(index * step, total) for index in range(count))


def close_vectors(actual, expected, tolerance=2e-9):
    return len(actual) == len(expected) and all(
        math.isclose(a, e, rel_tol=tolerance, abs_tol=tolerance)
        for av, ev in zip(actual, expected) for a, e in zip(av, ev)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    function, source_name, target_name = STAGES[args.stage]
    contracts = load_contracts(args.project_root)
    reference = load_reference(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (103 if args.paste else 104), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    if entries:
        contracts.require(f'MemberName="{function}"' in entries[0].text, "function identity")
    source_getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == source_name]
    target_getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == target_name]
    contracts.require(len(source_getters) == len(target_getters) == 1, "source/target getter boundary")
    clears = [node for node in nodes.values() if member(node) == "Array_Clear"]
    adds = [node for node in nodes.values() if member(node) == "Array_Add"]
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    contracts.require(len(clears) == 1 and contracts.linked(target_getters[0], target_name, clears[0], "TargetArray"), "one exact target clear")
    contracts.require(len(adds) == 3 and all(contracts.linked(target_getters[0], target_name, node, "TargetArray") for node in adds), "two secant adds and one loop add")
    contracts.require(len(items) == 5 and all(contracts.linked(source_getters[0], source_name, node, "Array") for node in items), "all five samples must read only the stage source")
    contracts.require(len([node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]) == 1, "one bounded loop")
    contracts.require(len([node for node in nodes.values() if member(node) == "Divide_DoubleDouble"]) == 3, "three Lagrange weights")
    contracts.require(len([node for node in nodes.values() if member(node) == "Min_DoubleDouble"]) == 4, "four exact schedule samples")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count(VALID) == 2 and writes.count(INDEX) == 1 and len(writes) == 3, "write boundary changed")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute forbidden")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")

    cases = [
        (0.1, 0.5, [(0.0, 1.0, -2.0), (5.0, -3.0, 4.0)]),
        (1.0, 0.25, [(float(i * i), float(3 * i * i - 2 * i), float(-i * i)) for i in range(5)]),
        (1.0, 0.3, [(t * t, -2.0 * t * t + t, 0.5 * t * t - 3.0 * t) for t in schedule(1.0, 0.3)]),
    ]
    rng = random.Random(0xEDD_D311)
    for _ in range(80):
        step = rng.choice((0.05, 0.1, 0.2, 0.3, 0.5))
        total = rng.uniform(max(0.01, step * 0.15), 3.0)
        times = schedule(total, step)
        coefficients = [[rng.uniform(-20.0, 20.0) for _ in range(3)] for _axis in range(3)]
        values = [tuple(c[0] + c[1] * t + c[2] * t * t for c in coefficients) for t in times]
        cases.append((total, step, values))
    for index, (total, step, values) in enumerate(cases):
        times = schedule(total, step)
        expected = reference.differentiate_sampled_vectors(values, times)
        initial = {source_name: list(values), target_name: ["poison"], TOTAL: total, STEP: step, VALID: True, INDEX: 777}
        result = Interpreter(nodes, initial).run()
        contracts.require(result[VALID] is True, f"valid case {index} invalidated")
        contracts.require(close_vectors(result[target_name], expected), f"valid case {index} derivative mismatch")
        reverse = Interpreter(nodes, {**initial, target_name: list(reversed(expected))}).run()
        contracts.require(close_vectors(reverse[target_name], expected), f"valid case {index} invocation-state leak")

    guarded = Interpreter(nodes, {source_name: object(), target_name: ["poison"], TOTAL: math.nan, STEP: 0.0, VALID: False, INDEX: 91}).run()
    contracts.require(guarded[target_name] == [] and guarded[VALID] is False, "false-stage guard must only clear target")
    overflow_values = [(0.0, 0.0, 0.0), (1e308, 0.0, 0.0), (-1e308, 0.0, 0.0)]
    overflow = Interpreter(nodes, {source_name: overflow_values, target_name: ["poison"], TOTAL: 2 / 240, STEP: 1 / 240, VALID: True, INDEX: 0}).run()
    contracts.require(overflow[VALID] is False, "non-finite derivative must fail closed")
    contracts.require(len(overflow[target_name]) < len(overflow_values), "failed derivative must not publish a complete candidate")
    print(f"Airframe desired {args.stage} derivative contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} valid, guarded no-op, overflow rejection")


if __name__ == "__main__":
    main()
