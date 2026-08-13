"""Exact and executable contracts for absolute-time desired velocity sampling."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


VELOCITIES = "AirframeDesiredStreamCandidateVelocitiesV1"
ELAPSED = "AirframeDesiredStreamVelocitySampleInputSecondsV1"
TOTAL = "AirframeDesiredStreamInputTotalSecondsV1"
STEP = "AirframeDesiredStreamInputFixedStepSecondsV1"
STAGE = "AirframeDesiredStreamStageValidV1"
RESULT = "AirframeDesiredStreamVelocitySampleResultV1"
RESULT_VALID = "AirframeDesiredStreamVelocitySampleResultValidV1"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
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
        if text == "true": return True
        if text == "false": return False
        if text in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"):
            return (0.0, 0.0, 0.0)
        try: return float(text)
        except ValueError: return text

    def output(self, node, pin_name):
        key = (node.name, pin_name)
        if key not in self.cache:
            self.cache[key] = self._output(node, pin_name)
        return self.cache[key]

    def _output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class or "K2Node_VariableSet" in node.node_class:
            return self.state[member(node)]
        if "K2Node_GetArrayItem" in node.node_class:
            return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        name = member(node)
        if name == "Array_Length": return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble": return float(self.value(node, "InInt"))
        if name == "FFloor": return math.floor(self.value(node, "A"))
        if name == "FClamp": return min(max(self.value(node, "Value"), self.value(node, "Min")), self.value(node, "Max"))
        if name == "SelectFloat": return self.value(node, "A") if self.value(node, "bPickA") else self.value(node, "B")
        if name == "MakeVector": return tuple(float(self.value(node, axis)) for axis in "XYZ")
        if name == "BreakVector": return self.value(node, "InVec")[("X", "Y", "Z").index(pin_name)]
        if name == "BooleanAND": return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "GreaterEqual_IntInt": return int(left) >= int(right)
        if name == "LessEqual_IntInt": return int(left) <= int(right)
        if name == "EqualEqual_IntInt": return int(left) == int(right)
        if name == "Greater_DoubleDouble": return left > right
        if name == "GreaterEqual_DoubleDouble": return left >= right
        if name == "Less_DoubleDouble": return left < right
        if name == "LessEqual_DoubleDouble": return left <= right
        if name == "Add_IntInt": return int(left) + int(right)
        if name == "Subtract_IntInt": return int(left) - int(right)
        if name == "Multiply_DoubleDouble": return left * right
        if name == "Divide_DoubleDouble": return left / right
        if name == "Subtract_DoubleDouble": return left - right
        if name in ("Add_VectorVector", "Subtract_VectorVector", "Multiply_VectorVector"):
            operation = {
                "Add_VectorVector": lambda a, b: a + b,
                "Subtract_VectorVector": lambda a, b: a - b,
                "Multiply_VectorVector": lambda a, b: a * b,
            }[name]
            return tuple(operation(float(a), float(b)) for a, b in zip(left, right))
        raise RuntimeError(f"unsupported output {node.name}:{name}:{pin_name}")

    def next(self, node, pin_name="then"):
        if pin_name not in node.pins: return None
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
            current = next(node for node in self.nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == RESULT and not node.pins["execute"].links)
        while current is not None:
            if "K2Node_VariableSet" in current.node_class:
                self.state[member(current)] = self.value(current, member(current))
                self.cache.clear()
                current = self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next(current, "then" if self.value(current, "Condition") else "else")
            else:
                raise RuntimeError(f"unsupported exec {current.name}:{member(current)}")
        return self.state


def schedule(total, step):
    return tuple(min(index * step, total) for index in range(math.ceil(total / step) + 1))


def close_vector(actual, expected, tolerance=2e-9):
    return all(math.isclose(a, e, rel_tol=tolerance, abs_tol=tolerance) for a, e in zip(actual, expected))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load_module(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_velocity_sampler_contract_base")
    trajectory = str(args.project_root / "tools/trajectory")
    if trajectory not in sys.path: sys.path.insert(0, trajectory)
    reference = load_module(args.project_root / "tools/trajectory/airframe_desired_stream_reference.py", "edd_velocity_sampler_reference")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (93 if args.paste else 94), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    contracts.require(len([node for node in nodes.values() if member(node) == "Array_Length"]) == 1, "one velocity length")
    contracts.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 3, "last and active segment reads")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count(RESULT) == 3 and writes.count(RESULT_VALID) == 3 and len(writes) == 6, "result-only publication")
    contracts.require(not any("K2Node_MacroInstance" in node.node_class for node in nodes.values()), "sampler must remain O(1)")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute forbidden")
    known = set(nodes)
    contracts.require(not {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}, "external links")

    rng = random.Random(0xEDD_5A61)
    cases = []
    for total, step in ((0.1, 0.5), (1.0, 0.25), (1.0, 0.3), (2.35, 0.2)):
        times = schedule(total, step)
        velocities = [(2.0 * t + 1.0, -t * t + 3.0, 0.5 * t) for t in times]
        queries = (-1.0, 0.0, total * 0.17, total * 0.9, total, total + 5.0)
        cases.extend((total, step, velocities, query) for query in queries)
    for _ in range(100):
        step = rng.choice((0.05, 0.1, 0.2, 0.3, 0.5))
        total = rng.uniform(max(0.01, step * 0.1), 3.0)
        times = schedule(total, step)
        velocities = [(rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in times]
        cases.append((total, step, velocities, rng.uniform(-1.0, total + 1.0)))
    for index, (total, step, velocities, query) in enumerate(cases):
        expected = reference.sample_vector_track_linear(velocities, schedule(total, step), query)
        state = {VELOCITIES: list(velocities), ELAPSED: query, TOTAL: total, STEP: step, STAGE: True, RESULT: (999.0,) * 3, RESULT_VALID: True}
        result = Interpreter(nodes, state).run()
        contracts.require(result[RESULT_VALID] is True and close_vector(result[RESULT], expected), f"valid sample {index}")
        repeat = Interpreter(nodes, {**state, RESULT: (-999.0,) * 3, RESULT_VALID: False}).run()
        contracts.require(repeat[RESULT_VALID] is True and close_vector(repeat[RESULT], expected), f"repeat sample {index}")

    base = {VELOCITIES: [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (2.0, 4.0, 6.0)], ELAPSED: 0.5, TOTAL: 1.0, STEP: 0.5, STAGE: True, RESULT: (9.0,) * 3, RESULT_VALID: True}
    invalid = [
        {**base, STAGE: False}, {**base, ELAPSED: math.nan}, {**base, ELAPSED: math.inf},
        {**base, VELOCITIES: base[VELOCITIES][:-2]}, {**base, TOTAL: 0.0}, {**base, TOTAL: 1.1},
        {**base, STEP: 0.0}, {**base, STEP: 0.6},
        {**base, VELOCITIES: [base[VELOCITIES][0], (math.inf, 0.0, 0.0), base[VELOCITIES][2]]},
        {**base, ELAPSED: 2.0, VELOCITIES: [base[VELOCITIES][0], base[VELOCITIES][1], (math.nan, 0.0, 0.0)]},
    ]
    for index, state in enumerate(invalid):
        result = Interpreter(nodes, state).run()
        contracts.require(result[RESULT_VALID] is False and result[RESULT] == (0.0, 0.0, 0.0), f"invalid sample {index}")
    print(f"Airframe desired velocity sampler contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} valid, {len(invalid)} invalid")


if __name__ == "__main__":
    main()
