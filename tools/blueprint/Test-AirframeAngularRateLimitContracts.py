"""Structural and executable contracts for ApplyAirframeAngularRateLimitV1."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


PREVIOUS = "AirframePrebakeScratchPreviousQuatV1"
DESIRED = "AirframePrebakeScratchDesiredQuatV1"
DELTA = "AirframePrebakeScratchDeltaSecondsV1"
MAXIMUM = "AirframePrebakeScratchMaximumRateDegreesPerSecondV1"
CANONICAL_PREVIOUS = "AirframePrebakeScratchCanonicalPreviousQuatV1"
CANONICAL_DESIRED = "AirframePrebakeScratchCanonicalDesiredQuatV1"
ALIGNED_DESIRED = "AirframePrebakeScratchAlignedDesiredQuatV1"
RESULT_QUAT = "AirframePrebakeScratchResultQuatV1"
RESULT_RATE = "AirframePrebakeScratchResultAngularRateDegreesPerSecondV1"
RESULT_LIMITED = "AirframePrebakeScratchResultRateLimitedV1"
RESULT_VALID = "AirframePrebakeScratchResultValidV1"
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def load(path: Path, name: str):
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


def variable(node):
    match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"variable name missing: {node.name}")
    return match.group(1)


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return "" if match is None else match.group(1)


def axis_angle(axis, angle_degrees):
    magnitude = math.sqrt(sum(value * value for value in axis))
    unit = tuple(value / magnitude for value in axis)
    half = math.radians(angle_degrees) * 0.5
    sine = math.sin(half)
    return (unit[0] * sine, unit[1] * sine, unit[2] * sine, math.cos(half))


def close_quat(left, right, tolerance=2.0e-9):
    return max(abs(a - b) for a, b in zip(left, right)) <= tolerance


class Interpreter:
    def __init__(self, nodes, state, orientation):
        self.nodes = nodes
        self.state = dict(state)
        self.orientation = orientation
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
        if text == "true":
            return True
        if text == "false":
            return False
        named = re.fullmatch(r"\(X=([^,]+),Y=([^,]+),Z=([^,]+),W=([^)]+)\)", text)
        if named:
            return tuple(float(value) for value in named.groups())
        if "," in text:
            return tuple(float(value.strip()) for value in text.split(","))
        try:
            return float(text)
        except ValueError:
            return text

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[variable(node)]
        name = member(node)
        if name == "BreakQuat":
            return self.value(node, "InQuat")["XYZW".index(pin_name)]
        if name == "Quat_IsFinite":
            return all(math.isfinite(value) for value in self.value(node, "Q"))
        if name == "Quat_Size":
            return math.sqrt(sum(value * value for value in self.value(node, "Q")))
        if name == "Quat_Normalized":
            return self.orientation.normalize(self.value(node, "Q"))
        if name == "Quat_Slerp":
            return self.orientation.slerp(
                self.value(node, "A"), self.value(node, "B"), self.value(node, "Alpha")
            )
        if name == "Quat_AngularDistance":
            left = self.orientation.normalize(self.value(node, "A"))
            right = self.orientation.normalize(self.value(node, "B"))
            dot = max(-1.0, min(1.0, abs(sum(a * b for a, b in zip(left, right)))))
            return 2.0 * math.acos(dot)
        if name == "SelectFloat":
            return self.value(node, "A") if self.value(node, "bPickA") else self.value(node, "B")
        if name == "FClamp":
            return max(self.value(node, "Min"), min(self.value(node, "Max"), self.value(node, "Value")))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "Add_DoubleDouble":
            return left + right
        if name == "Multiply_DoubleDouble":
            return left * right
        if name == "Divide_DoubleDouble":
            return left / right
        if name == "Greater_DoubleDouble":
            return left > right
        if name == "GreaterEqual_DoubleDouble":
            return left >= right
        if name == "Less_DoubleDouble":
            return left < right
        if name == "LessEqual_DoubleDouble":
            return left <= right
        if name == "EqualEqual_DoubleDouble":
            return left == right
        if name == "BooleanAND":
            return bool(left) and bool(right)
        if name == "BooleanOR":
            return bool(left) or bool(right)
        raise RuntimeError(f"unsupported node {node.name}:{name}")

    def next(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            if len(entries) != 1:
                raise RuntimeError(f"entry count {len(entries)}")
            current = self.next(entries[0])
        else:
            roots = [
                node for node in self.nodes.values()
                if "execute" in node.pins and not node.pins["execute"].links
            ]
            if len(roots) != 1:
                raise RuntimeError(f"root count {len(roots)}")
            current = roots[0]
        visits = 0
        while current is not None:
            visits += 1
            if visits > 32:
                raise RuntimeError("execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = variable(current)
                self.state[name] = self.value(current, name)
                current = self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next(current, "then" if self.value(current, "Condition") else "else")
            elif 'MemberName="Quat_SetComponents"' in current.text:
                source = self.source(current, "Q")
                if source is None or "K2Node_VariableGet" not in source[0].node_class:
                    raise RuntimeError("Quat_SetComponents must target explicit scratch storage")
                self.state[variable(source[0])] = tuple(self.value(current, axis) for axis in "XYZW")
                current = self.next(current)
            else:
                raise RuntimeError(f"unsupported execution node {current.name}")
        return self.state


def poisoned_state(previous, desired, delta, maximum):
    return {
        PREVIOUS: previous,
        DESIRED: desired,
        DELTA: delta,
        MAXIMUM: maximum,
        CANONICAL_PREVIOUS: (7.0, 7.0, 7.0, 7.0),
        CANONICAL_DESIRED: (8.0, 8.0, 8.0, 8.0),
        ALIGNED_DESIRED: (9.0, 9.0, 9.0, 9.0),
        RESULT_QUAT: (6.0, 6.0, 6.0, 6.0),
        RESULT_RATE: 666.0,
        RESULT_LIMITED: True,
        RESULT_VALID: True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(
        args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py",
        "edd_airframe_rate_limit_contract_base",
    )
    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    orientation = load(
        args.project_root / "tools/trajectory/orientation_reference.py",
        "edd_airframe_rate_limit_orientation",
    )
    oracle = load(
        args.project_root / "tools/trajectory/airframe_gimbal_prebake_reference.py",
        "edd_airframe_rate_limit_oracle",
    )
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (132 if args.paste else 133), f"helper node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "function entry count")

    text = "\n".join(node.text for node in nodes.values())
    contracts.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text, "unsafe graph form")
    contracts.require("K2Node_MakeStruct" not in text, "unsafe quaternion construction")
    contracts.require(text.count('MemberName="Quat_SetComponents"') == 3, "three explicit quaternion assembly writes")
    contracts.require(text.count('MemberName="Quat_AngularDistance"') == 1, "one angular-distance measurement")
    contracts.require(text.count('MemberName="Quat_Slerp"') == 1, "one shortest-arc interpolation")

    input_names = (PREVIOUS, DESIRED, DELTA, MAXIMUM)
    for name in input_names:
        gets = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and variable(node) == name]
        sets = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and variable(node) == name]
        contracts.require(len(gets) == 1 and not sets, f"immutable explicit input {name}")
    for forbidden in (
        "AirframePrebakeCandidateBodyQuatsV1", "AirframePrebakeCandidateGimbalQuatsV1",
        "AirframePrebakeCompiledBodyQuatsV1", "AirframePrebakeCompiledGimbalQuatsV1",
        "AirframePrebakeCompileValidV1", "AirframePrebakeResultValidV1",
    ):
        contracts.require(f'MemberName="{forbidden}"' not in text, f"helper touched {forbidden}")

    result_setters = {}
    for name in (RESULT_QUAT, RESULT_RATE, RESULT_LIMITED, RESULT_VALID):
        matches = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and variable(node) == name]
        contracts.require(len(matches) == 2, f"reset and publish setters for {name}")
        result_setters[name] = matches
    valid_true = next(node for node in result_setters[RESULT_VALID] if default(node, RESULT_VALID) == "true")
    contracts.require(not valid_true.pins["then"].links, "validity publication must be terminal")
    valid_false = next(node for node in result_setters[RESULT_VALID] if default(node, RESULT_VALID) == "false")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 1, "one fail-closed guard branch")
    branch = branches[0]
    contracts.require(contracts.linked(valid_false, "then", branch, "execute"), "reset validity must precede guard")
    contracts.require(not branch.pins["else"].links, "invalid branch must terminate after reset")

    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values()
        for target, _pin in pin.links if target not in known
    }
    contracts.require(not external, f"external links {external}")

    directed = [
        (IDENTITY, IDENTITY, 0.25, 120.0),
        (IDENTITY, axis_angle((1, 0, 0), 10.0), 0.25, 120.0),
        (IDENTITY, axis_angle((0, 1, 0), 30.0), 0.25, 120.0),
        (IDENTITY, axis_angle((0, 0, 1), 90.0), 0.25, 120.0),
        (axis_angle((1, 2, 3), -71.0), axis_angle((-2, 3, 1), 137.0), 1.0 / 60.0, 360.0),
    ]
    rng = random.Random(0xEDD_A17E)
    cases = list(directed)
    for _ in range(200):
        previous = orientation.normalize(tuple(rng.uniform(-1.0, 1.0) for _ in range(4)))
        desired = orientation.normalize(tuple(rng.uniform(-1.0, 1.0) for _ in range(4)))
        if rng.random() < 0.5:
            previous = tuple(-value for value in previous)
        if rng.random() < 0.5:
            desired = tuple(-value for value in desired)
        cases.append((previous, desired, rng.uniform(1.0 / 240.0, 0.5), rng.uniform(0.001, 720.0)))

    valid = 0
    for index, (previous, desired, delta, maximum) in enumerate(cases):
        state = poisoned_state(previous, desired, delta, maximum)
        actual = Interpreter(nodes, state, orientation).run()
        expected = oracle.apply_airframe_angular_rate_limit(previous, desired, delta, maximum)
        contracts.require(actual[RESULT_VALID] is True, f"valid case {index} rejected")
        contracts.require(close_quat(actual[RESULT_QUAT], expected.rotation), f"valid case {index} rotation mismatch")
        contracts.require(abs(actual[RESULT_RATE] - expected.angular_rate_degrees_per_second) <= 2.0e-8, f"valid case {index} rate mismatch")
        contracts.require(actual[RESULT_LIMITED] is expected.rate_limited, f"valid case {index} limited mismatch")
        contracts.require(actual[PREVIOUS] == previous and actual[DESIRED] == desired, f"valid case {index} mutated quaternion input")
        contracts.require(actual[DELTA] == delta and actual[MAXIMUM] == maximum, f"valid case {index} mutated scalar input")
        valid += 1

    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        target = axis_angle(axis, 180.0)
        left = Interpreter(nodes, poisoned_state(IDENTITY, target, 0.25, 90.0), orientation).run()
        right = Interpreter(
            nodes,
            poisoned_state(tuple(-value for value in IDENTITY), tuple(-value for value in target), 0.25, 90.0),
            orientation,
        ).run()
        contracts.require(left[RESULT_QUAT] == right[RESULT_QUAT], f"{axis} half-turn sign instability")
        contracts.require(left[RESULT_RATE] == right[RESULT_RATE], f"{axis} half-turn rate instability")
        contracts.require(left[RESULT_LIMITED] is right[RESULT_LIMITED], f"{axis} half-turn flag instability")

    invalid_cases = []
    for bad in ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0000011), (math.nan, 0.0, 0.0, 1.0), (math.inf, 0.0, 0.0, 1.0)):
        invalid_cases.append((bad, IDENTITY, 0.25, 120.0))
        invalid_cases.append((IDENTITY, bad, 0.25, 120.0))
    for bad in (0.0, -1.0, 0.501, math.nan, math.inf, -math.inf):
        invalid_cases.append((IDENTITY, IDENTITY, bad, 120.0))
    for bad in (0.0, -1.0, 720.001, math.nan, math.inf, -math.inf):
        invalid_cases.append((IDENTITY, IDENTITY, 0.25, bad))
    invalid = 0
    for index, values in enumerate(invalid_cases):
        actual = Interpreter(nodes, poisoned_state(*values), orientation).run()
        contracts.require(actual[RESULT_VALID] is False, f"invalid case {index} accepted")
        contracts.require(actual[RESULT_QUAT] == IDENTITY, f"invalid case {index} leaked quaternion")
        contracts.require(actual[RESULT_RATE] == 0.0, f"invalid case {index} leaked rate")
        contracts.require(actual[RESULT_LIMITED] is False, f"invalid case {index} leaked limited flag")
        invalid += 1

    print(
        f"Airframe angular-rate helper contracts passed ({'paste' if args.paste else 'full'}): "
        f"{valid} valid, {invalid} invalid, 3 antipodal half-turn pairs"
    )


if __name__ == "__main__":
    main()
