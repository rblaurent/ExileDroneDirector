"""Structural and executable contracts for the vector quintic wrapper."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


INPUTS = (
    "TrajectoryInputStartPositionVectorV1",
    "TrajectoryInputStartVelocityUVectorV1",
    "TrajectoryInputStartAccelerationUVectorV1",
    "TrajectoryInputEndPositionVectorV1",
    "TrajectoryInputEndVelocityUVectorV1",
    "TrajectoryInputEndAccelerationUVectorV1",
)
SCALAR_INPUTS = (
    "TrajectoryInputStartValueV1",
    "TrajectoryInputStartVelocityUV1",
    "TrajectoryInputStartAccelerationUV1",
    "TrajectoryInputEndValueV1",
    "TrajectoryInputEndVelocityUV1",
    "TrajectoryInputEndAccelerationUV1",
)
OUTPUTS = (
    "TrajectoryResultPositionVectorV1",
    "TrajectoryResultDerivativeUVectorV1",
    "TrajectoryResultSecondDerivativeUVectorV1",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VectorInterpreter:
    def __init__(self, scalar, nodes, scalar_nodes, state):
        self.scalar, self.nodes, self.scalar_nodes, self.state = scalar, nodes, scalar_nodes, dict(state)
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match:
                    self.pin_owner[(node.name, match.group(1))] = (node, pin)

    @staticmethod
    def variable(node):
        match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
        if match is None:
            raise RuntimeError(node.name)
        return match.group(1)

    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            linked_node, linked_pin = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in linked_pin.body:
                return linked_node, linked_pin.name
        return None

    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        if source:
            return self.output(*source)
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
        value = "" if match is None else match.group(1)
        if value == "true": return True
        if value == "false": return False
        if "," in value: return tuple(float(part.strip()) for part in value.split(","))
        try: return float(value)
        except ValueError: return value

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[self.variable(node)]
        member = re.search(r'MemberName="([^"]+)"', node.text)
        if member and member.group(1) == "BreakVector":
            return self.value(node, "InVec")["XYZ".index(pin_name)]
        if member and member.group(1) == "MakeVector":
            return tuple(float(self.value(node, axis)) for axis in "XYZ")
        raise RuntimeError(f"unsupported output {node.name}/{pin_name}")

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
        current = self.next_exec(entries[0]) if entries else None
        if not entries:
            executable = [node for node in self.nodes.values() if "execute" in node.pins]
            roots = [node for node in executable if not node.pins["execute"].links]
            if len(roots) != 1:
                raise RuntimeError(f"expected one paste root, found {len(roots)}")
            current = roots[0]
        visited = 0
        while current is not None:
            visited += 1
            if visited > 100:
                raise RuntimeError("execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = self.variable(current)
                self.state[name] = self.value(current, name)
                current = self.next_exec(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next_exec(current, "then" if self.value(current, "Condition") else "else")
            elif 'MemberName="EvaluateQuinticScalarV1"' in current.text:
                self.state = self.scalar.Interpreter(self.scalar.c, self.scalar_nodes, self.state).run()
                current = self.next_exec(current)
            else:
                raise RuntimeError(f"unsupported executable {current.name}")
        return self.state


def variables(nodes, name, kind):
    return [node for node in nodes.values() if kind in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--vector-path", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    scalar = load(args.project_root / "tools/blueprint/Test-TrajectoryScalarEvaluatorContracts.py", "edd_vector_scalar_contract")
    scalar.c = scalar.load_contracts(args.project_root)
    nodes = scalar.c.parse_graph(args.vector_path)
    scalar_nodes = scalar.c.parse_graph(args.project_root / "tools/blueprint/snippets/evaluate-quintic-scalar-v1.eddgraph")
    expected = 77 if args.paste else 78
    scalar.c.require(len(nodes) == expected, f"vector node count changed: {len(nodes)}")
    text = "\n".join(node.text for node in nodes.values())
    scalar.c.require("K2Node_Knot" not in text, "vector graph contains reroute nodes")
    scalar.c.require(text.count('MemberName="EvaluateQuinticScalarV1"') == 3, "scalar call count changed")
    scalar.c.require(text.count('MemberName="BreakVector"') == 6, "vector break count changed")
    scalar.c.require(text.count('MemberName="MakeVector"') == 3, "vector make count changed")
    scalar.c.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 3, "axis guards changed")
    for name in INPUTS:
        scalar.c.require(len(variables(nodes, name, "K2Node_VariableGet")) == 1, f"{name} getter changed")
    for name in SCALAR_INPUTS:
        scalar.c.require(len(variables(nodes, name, "K2Node_VariableSet")) == 3, f"{name} axis staging changed")
    for name in OUTPUTS:
        scalar.c.require(len(variables(nodes, name, "K2Node_VariableSet")) == 2, f"{name} reset/commit changed")
    scalar.c.require(len(variables(nodes, "TrajectoryResultVectorValidV1", "K2Node_VariableSet")) == 2, "validity reset/commit changed")

    def state(vectors, alpha):
        result = scalar.default_state()
        result.update(dict(zip(INPUTS, vectors)))
        result["TrajectoryInputAlphaV1"] = alpha
        result.update({name: (123.0, 456.0, 789.0) for name in OUTPUTS})
        result["TrajectoryResultVectorValidV1"] = True
        for axis in "XYZ":
            for channel in ("Value", "Derivative", "SecondDerivative"):
                result[f"TrajectoryVectorScratch{channel}{axis}V1"] = 999.0
        return result

    randomizer = random.Random(0xEDD055)
    fixtures = [
        (((0,0,0),(0,0,0),(0,0,0),(10,20,30),(0,0,0),(0,0,0)), -2.0),
        (((0,1,2),(3,4,5),(6,7,8),(9,10,11),(12,13,14),(15,16,17)), 0.5),
        (((0,1,2),(3,4,5),(6,7,8),(9,10,11),(12,13,14),(15,16,17)), 2.0),
    ]
    fixtures += [
        (tuple(tuple(randomizer.uniform(-100,100) for _ in range(3)) for _ in range(6)), randomizer.uniform(-1,2))
        for _ in range(100)
    ]
    for vectors, alpha in fixtures:
        actual = VectorInterpreter(scalar, nodes, scalar_nodes, state(vectors, alpha)).run()
        scalar.c.require(actual["TrajectoryResultVectorValidV1"] is True, "valid vector rejected")
        expected_axes = [scalar.reference_quintic(tuple(vector[index] for vector in vectors), alpha) for index in range(3)]
        expected_vectors = tuple(tuple(axis[channel] for axis in expected_axes) for channel in range(3))
        for name, expected_vector in zip(OUTPUTS, expected_vectors):
            for value, wanted in zip(actual[name], expected_vector):
                scalar.c.require(abs(value-wanted) <= 1e-9*max(1,abs(wanted)), f"{name}: {actual[name]} != {expected_vector}")

    invalid = 0
    for nonfinite in (math.nan, math.inf, -math.inf):
        for bad_index in range(19):
            flat = [1.0] * 19
            flat[bad_index] = nonfinite
            vectors = tuple(tuple(flat[1+i*3+j] for j in range(3)) for i in range(6))
            actual = VectorInterpreter(scalar, nodes, scalar_nodes, state(vectors, flat[0])).run()
            scalar.c.require(actual["TrajectoryResultVectorValidV1"] is False, f"invalid vector accepted: {bad_index}/{nonfinite}")
            scalar.c.require(all(actual[name] == (0.0,0.0,0.0) for name in OUTPUTS), "invalid vector leaked stale output")
            invalid += 1
    print(f"Trajectory vector evaluator contracts passed ({'paste' if args.paste else 'full'}): {len(fixtures)} valid, {invalid} invalid.")


if __name__ == "__main__":
    main()
