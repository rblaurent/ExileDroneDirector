"""Structural and seeded numeric contracts for scalar sample publication."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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

    @staticmethod
    def default(pin):
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', pin.body)
        if match is None:
            return 0.0
        value = match.group(1)
        if value == "true":
            return True
        if value == "false":
            return False
        try:
            return float(value)
        except ValueError:
            return value

    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            linked_node, linked_pin = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in linked_pin.body:
                return linked_node, linked_pin.name
        return None

    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        return self.output(*source) if source else self.default(node.pins[pin_name])

    @staticmethod
    def member(node):
        match = re.search(r'(?:VariableReference=\()?MemberName="([^"]+)"', node.text)
        if match is None:
            raise RuntimeError(f"No member on {node.name}")
        return match.group(1)

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[self.member(node)]
        if "K2Node_Select" in node.node_class:
            return self.value(node, "Option 1" if self.value(node, "Index") else "Option 0")
        name = self.member(node)
        a = self.value(node, "A")
        b = self.value(node, "B")
        if name == "Multiply_DoubleDouble":
            return a * b
        if name == "Divide_DoubleDouble":
            return a / b
        if name == "Subtract_DoubleDouble":
            return a - b
        if name == "Max_DoubleDouble":
            return max(a, b)
        if name == "Min_DoubleDouble":
            return min(a, b)
        if name == "Greater_DoubleDouble":
            return a > b
        if name == "Less_DoubleDouble":
            return a < b
        if name == "GreaterEqual_DoubleDouble":
            return a >= b
        if name == "LessEqual_DoubleDouble":
            return a <= b
        if name == "EqualEqual_StrStr":
            return a == b
        if name == "BooleanAND":
            return bool(a) and bool(b)
        if name == "BooleanOR":
            return bool(a) or bool(b)
        raise RuntimeError(f"Unsupported operation {name}")

    def next_exec(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target, pin = self.pin_owner[link]
            if pin.name == "execute":
                return target
        return None

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.next_exec(entries[0])
        else:
            executable = [node for node in self.nodes.values() if "execute" in node.pins]
            roots = [node for node in executable if not node.pins["execute"].links]
            if len(roots) != 1:
                raise RuntimeError(f"Expected one paste root, found {len(roots)}")
            current = roots[0]
        steps = 0
        while current is not None:
            steps += 1
            if steps > 20:
                raise RuntimeError("Execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = self.member(current)
                self.state[name] = self.value(current, name)
                current = self.next_exec(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next_exec(current, "then" if self.value(current, "Condition") else "else")
            else:
                raise RuntimeError(f"Unsupported executable {current.name}")
        return self.state


def default_state():
    return {
        "CameraScalarTrackCompileValidV1": True,
        "CameraScalarTrackScratchValidV1": True,
        "CameraScalarTrackInputDomainV1": "linear",
        "CameraScalarTrackScratchDomainValueV1": 0.0,
        "CameraScalarTrackScratchDomainVelocityV1": 0.0,
        "CameraScalarTrackScratchDomainAccelerationV1": 0.0,
        "CameraScalarTrackInputHasMinimumV1": False,
        "CameraScalarTrackInputMinimumV1": 0.0,
        "CameraScalarTrackInputHasMaximumV1": False,
        "CameraScalarTrackInputMaximumV1": 0.0,
        "CameraScalarTrackInputClampOutputV1": False,
        "CameraScalarTrackResultValueV1": 111.0,
        "CameraScalarTrackResultVelocityV1": 222.0,
        "CameraScalarTrackResultAccelerationV1": 333.0,
        "CameraScalarTrackResultValidV1": True,
    }


def expected(state):
    value = state["CameraScalarTrackScratchDomainValueV1"]
    velocity = state["CameraScalarTrackScratchDomainVelocityV1"]
    acceleration = state["CameraScalarTrackScratchDomainAccelerationV1"]
    if state["CameraScalarTrackInputDomainV1"] == "reciprocal":
        value, velocity, acceleration = (
            1.0 / value,
            -velocity / (value * value),
            2.0 * velocity * velocity / (value**3) - acceleration / (value * value),
        )
    unclamped = value
    if state["CameraScalarTrackInputClampOutputV1"]:
        if state["CameraScalarTrackInputHasMinimumV1"]:
            value = max(value, state["CameraScalarTrackInputMinimumV1"])
        if state["CameraScalarTrackInputHasMaximumV1"]:
            value = min(value, state["CameraScalarTrackInputMaximumV1"])
        if value != unclamped:
            velocity = acceleration = 0.0
    return value, velocity, acceleration


def close(left, right):
    return abs(left - right) <= 2e-11 * max(1.0, abs(right))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_camera_scalar_publish_contracts")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (77 if args.paste else 78), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = [Interpreter.member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(set(setters) == {
        "CameraScalarTrackResultValueV1", "CameraScalarTrackResultVelocityV1",
        "CameraScalarTrackResultAccelerationV1", "CameraScalarTrackResultValidV1",
    }, "publication write ownership")
    contracts.require(setters.count("CameraScalarTrackResultValidV1") == 2, "validity reset/last publication")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require("CameraScalarTrackCandidate" not in text, "compiled snapshot is read-only")
    for operation in ("Divide_DoubleDouble", "Max_DoubleDouble", "Min_DoubleDouble", "Greater_DoubleDouble", "Less_DoubleDouble"):
        contracts.require(f'MemberName="{operation}"' in text, f"missing {operation}")

    randomizer = random.Random(0xEDD5A9)
    cases = []
    for _ in range(160):
        state = default_state()
        state["CameraScalarTrackInputDomainV1"] = randomizer.choice(("linear", "reciprocal"))
        state["CameraScalarTrackScratchDomainValueV1"] = (
            randomizer.uniform(0.002, 2.0) if state["CameraScalarTrackInputDomainV1"] == "reciprocal"
            else randomizer.uniform(-200.0, 200.0)
        )
        state["CameraScalarTrackScratchDomainVelocityV1"] = randomizer.uniform(-20.0, 20.0)
        state["CameraScalarTrackScratchDomainAccelerationV1"] = randomizer.uniform(-20.0, 20.0)
        state["CameraScalarTrackInputHasMinimumV1"] = randomizer.choice((False, True))
        state["CameraScalarTrackInputMinimumV1"] = randomizer.uniform(-100.0, 0.0)
        state["CameraScalarTrackInputHasMaximumV1"] = randomizer.choice((False, True))
        state["CameraScalarTrackInputMaximumV1"] = randomizer.uniform(0.0, 100.0)
        state["CameraScalarTrackInputClampOutputV1"] = randomizer.choice((False, True))
        cases.append(state)
    zero_linear = default_state()
    zero_linear["CameraScalarTrackScratchDomainValueV1"] = 0.0
    cases.append(zero_linear)
    for state in cases:
        result = Interpreter(nodes, state).run()
        wanted = expected(state)
        contracts.require(result["CameraScalarTrackResultValidV1"] is True, "valid sample rejected")
        actual = tuple(result[name] for name in (
            "CameraScalarTrackResultValueV1", "CameraScalarTrackResultVelocityV1",
            "CameraScalarTrackResultAccelerationV1",
        ))
        contracts.require(all(close(a, b) for a, b in zip(actual, wanted)), f"numeric mismatch {actual} != {wanted}")

    invalid = []
    for field, value in (
        ("CameraScalarTrackCompileValidV1", False),
        ("CameraScalarTrackScratchValidV1", False),
        ("CameraScalarTrackInputDomainV1", "bad"),
        ("CameraScalarTrackScratchDomainValueV1", math.nan),
        ("CameraScalarTrackScratchDomainVelocityV1", math.inf),
        ("CameraScalarTrackScratchDomainAccelerationV1", -math.inf),
    ):
        state = default_state(); state[field] = value; invalid.append(state)
    for value in (0.0, -1.0):
        state = default_state(); state["CameraScalarTrackInputDomainV1"] = "reciprocal"
        state["CameraScalarTrackScratchDomainValueV1"] = value; invalid.append(state)
    for state in invalid:
        result = Interpreter(nodes, state).run()
        contracts.require(result["CameraScalarTrackResultValidV1"] is False, "invalid sample published")
        contracts.require(result["CameraScalarTrackResultValueV1"] == 111.0, "invalid sample overwrote stale value")
        contracts.require(result["CameraScalarTrackResultVelocityV1"] == 222.0, "invalid sample overwrote stale velocity")
        contracts.require(result["CameraScalarTrackResultAccelerationV1"] == 333.0, "invalid sample overwrote stale acceleration")
    print(
        f"Camera scalar publication contracts passed ({'paste' if args.paste else 'full'}): "
        f"{len(cases)} valid samples, {len(invalid)} fail-closed cases"
    )


if __name__ == "__main__":
    main()
