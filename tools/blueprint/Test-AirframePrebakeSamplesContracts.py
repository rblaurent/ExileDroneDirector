"""Structural and executable contracts for BuildAirframePrebakeSamplesV1."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


BODY_INPUT = "AirframePrebakeInputDesiredBodyQuatsV1"
GIMBAL_INPUT = "AirframePrebakeInputDesiredGimbalQuatsV1"
RATE_INPUT = "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"
TOTAL_INPUT = "AirframePrebakeInputTotalSecondsV1"
STEP_INPUT = "AirframePrebakeInputFixedStepSecondsV1"
STAGE_INDEX = "AirframePrebakeStageIndexV1"
STAGE_VALID = "AirframePrebakeStageValidV1"
BODY = "AirframePrebakeCandidateBodyQuatsV1"
GIMBAL = "AirframePrebakeCandidateGimbalQuatsV1"
BODY_RATE = "AirframePrebakeCandidateBodyAngularRatesDegreesPerSecondV1"
GIMBAL_RATE = "AirframePrebakeCandidateGimbalAngularRatesDegreesPerSecondV1"
BODY_LIMITED = "AirframePrebakeCandidateBodyRateLimitedV1"
GIMBAL_LIMITED = "AirframePrebakeCandidateGimbalRateLimitedV1"
PREVIOUS = "AirframePrebakeScratchPreviousQuatV1"
DESIRED = "AirframePrebakeScratchDesiredQuatV1"
DELTA = "AirframePrebakeScratchDeltaSecondsV1"
MAXIMUM = "AirframePrebakeScratchMaximumRateDegreesPerSecondV1"
RESULT_QUAT = "AirframePrebakeScratchResultQuatV1"
RESULT_RATE = "AirframePrebakeScratchResultAngularRateDegreesPerSecondV1"
RESULT_LIMITED = "AirframePrebakeScratchResultRateLimitedV1"
RESULT_VALID = "AirframePrebakeScratchResultValidV1"
IDENTITY = (0.0, 0.0, 0.0, 1.0)
CANDIDATES = (BODY, GIMBAL, BODY_RATE, GIMBAL_RATE, BODY_LIMITED, GIMBAL_LIMITED)


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
    def __init__(self, nodes, state, oracle):
        self.nodes = nodes
        self.state = dict(state)
        self.oracle = oracle
        self.loop_values = {}
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
        # Enhanced omits an authored numeric zero when it serializes a live
        # default-valued pin. The absence is the native zero default, not an
        # empty string runtime value. Keep source and post-paste execution
        # proofs semantically equivalent while still requiring the pin to be
        # unlinked through source() above.
        if text == "" and 'PinType.PinCategory="real"' in node.pins[pin_name].body:
            return 0.0
        if text == "" and 'PinType.PinCategory="bool"' in node.pins[pin_name].body:
            return False
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
        if "K2Node_VariableGet" in node.node_class or "K2Node_VariableSet" in node.node_class:
            return self.state[variable(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name == "Index":
                return self.loop_values[node.name]
            raise RuntimeError(f"unsupported loop output {node.name}.{pin_name}")
        name = member(node)
        if "K2Node_GetArrayItem" in node.node_class:
            return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        if name == "Subtract_IntInt":
            return int(self.value(node, "A")) - int(self.value(node, "B"))
        if name == "EqualEqual_IntInt":
            return int(self.value(node, "A")) == int(self.value(node, "B"))
        if name == "Multiply_DoubleDouble":
            return self.value(node, "A") * self.value(node, "B")
        if name == "Subtract_DoubleDouble":
            return self.value(node, "A") - self.value(node, "B")
        if name == "LessEqual_DoubleDouble":
            return self.value(node, "A") <= self.value(node, "B")
        if name == "SelectFloat":
            return self.value(node, "A") if self.value(node, "bPickA") else self.value(node, "B")
        raise RuntimeError(f"unsupported output {node.name}:{name}.{pin_name}")

    def exec_target(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and target[1].name in ("execute", "Exec", "Execute", "Break"):
                return target[0], target[1].name
        return None

    def array_owner(self, node, pin_name):
        source = self.source(node, pin_name)
        if source is None or "K2Node_VariableGet" not in source[0].node_class:
            raise RuntimeError(f"array target is not explicit storage: {node.name}.{pin_name}")
        return variable(source[0])

    def apply_helper(self):
        self.state[RESULT_QUAT] = IDENTITY
        self.state[RESULT_RATE] = 0.0
        self.state[RESULT_LIMITED] = False
        self.state[RESULT_VALID] = False
        try:
            result = self.oracle.apply_airframe_angular_rate_limit(
                self.state[PREVIOUS], self.state[DESIRED], self.state[DELTA], self.state[MAXIMUM]
            )
        except self.oracle.AirframeGimbalPrebakeError:
            return
        self.state[RESULT_QUAT] = result.rotation
        self.state[RESULT_RATE] = result.angular_rate_degrees_per_second
        self.state[RESULT_LIMITED] = result.rate_limited
        self.state[RESULT_VALID] = True

    def execute_chain(self, current):
        visits = 0
        while current is not None:
            visits += 1
            if visits > 128:
                raise RuntimeError("execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = variable(current)
                self.state[name] = self.value(current, name)
                target = self.exec_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                target = self.exec_target(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_CallArrayFunction" in current.node_class and member(current) == "Array_Clear":
                self.state[self.array_owner(current, "TargetArray")] = []
                target = self.exec_target(current)
            elif "K2Node_CallArrayFunction" in current.node_class and member(current) == "Array_Add":
                self.state[self.array_owner(current, "TargetArray")].append(self.value(current, "NewItem"))
                target = self.exec_target(current)
            elif "K2Node_CallFunction" in current.node_class and member(current) == "ApplyAirframeAngularRateLimitV1":
                self.apply_helper()
                target = self.exec_target(current)
            elif "K2Node_MacroInstance" in current.node_class:
                first = int(self.value(current, "FirstIndex"))
                last = int(self.value(current, "LastIndex"))
                broke = False
                for index in range(first, last + 1):
                    self.loop_values[current.name] = index
                    body = self.exec_target(current, "LoopBody")
                    if body is not None and self.execute_chain(body[0]) == "break":
                        broke = True
                        break
                target = self.exec_target(current, "Completed")
                if broke and target is None:
                    return None
            else:
                raise RuntimeError(f"unsupported execution node {current.name}:{member(current)}")
            if target is None:
                return None
            if target[1] == "Break":
                return "break"
            current = target[0]
        return None

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            if len(entries) != 1:
                raise RuntimeError(f"entry count {len(entries)}")
            target = self.exec_target(entries[0])
        else:
            roots = [node for node in self.nodes.values() if "execute" in node.pins and not node.pins["execute"].links]
            if len(roots) != 1:
                raise RuntimeError(f"root count {len(roots)}")
            target = (roots[0], "execute")
        if target is not None:
            self.execute_chain(target[0])
        return self.state


def state_for(bodies, gimbals, rates, total, step, valid=True):
    return {
        BODY_INPUT: list(bodies), GIMBAL_INPUT: list(gimbals), RATE_INPUT: list(rates),
        TOTAL_INPUT: total, STEP_INPUT: step, STAGE_INDEX: 777, STAGE_VALID: valid,
        BODY: [IDENTITY], GIMBAL: [IDENTITY], BODY_RATE: [666.0], GIMBAL_RATE: [666.0],
        BODY_LIMITED: [True], GIMBAL_LIMITED: [True], PREVIOUS: IDENTITY, DESIRED: IDENTITY,
        DELTA: 0.0, MAXIMUM: 0.0, RESULT_QUAT: (9.0, 9.0, 9.0, 9.0),
        RESULT_RATE: 999.0, RESULT_LIMITED: True, RESULT_VALID: True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_prebake_samples_contract_base")
    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    oracle = load(args.project_root / "tools/trajectory/airframe_gimbal_prebake_reference.py", "edd_prebake_samples_oracle")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (80 if args.paste else 81), f"sample-builder node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "function entry count")
    text = "\n".join(node.text for node in nodes.values())
    contracts.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text, "unsafe graph form")
    pin_index = {}
    for node in nodes.values():
        for pin in node.pins.values():
            pin_id = re.search(r"PinId=([0-9A-F]{32})", pin.body)
            contracts.require(pin_id is not None, f"pin identity missing: {node.name}.{pin.name}")
            pin_index[(node.name, pin_id.group(1))] = (node, pin)
    for node in nodes.values():
        for pin in node.pins.values():
            source_is_output = 'Direction="EGPD_Output"' in pin.body
            for link in pin.links:
                contracts.require(link in pin_index, f"unresolved link: {node.name}.{pin.name} -> {link}")
                target_node, target_pin = pin_index[link]
                target_is_output = 'Direction="EGPD_Output"' in target_pin.body
                contracts.require(
                    source_is_output != target_is_output,
                    f"same-direction link: {node.name}.{pin.name} -> {target_node.name}.{target_pin.name}",
                )
                source_id = re.search(r"PinId=([0-9A-F]{32})", pin.body).group(1)
                contracts.require(
                    (node.name, source_id) in target_pin.links,
                    f"non-reciprocal link: {node.name}.{pin.name} -> {target_node.name}.{target_pin.name}",
                )
    contracts.require(text.count('MemberName="ApplyAirframeAngularRateLimitV1"') == 4, "four atomic helper calls")
    loops = [node for node in nodes.values() if "ForLoopWithBreak" in node.text]
    contracts.require(len(loops) == 1 and default(loops[0], "FirstIndex") == "1", "bounded loop starts at sample one")
    clears = [node for node in nodes.values() if member(node) == "Array_Clear"]
    adds = [node for node in nodes.values() if member(node) == "Array_Add"]
    contracts.require(len(clears) == 6 and len(adds) == 12, "six candidate resets and two six-channel appends")
    for candidate in CANDIDATES:
        getter = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and variable(node) == candidate)
        contracts.require(sum(contracts.linked(getter, candidate, node, "TargetArray") for node in clears) == 1, f"one clear for {candidate}")
        contracts.require(sum(contracts.linked(getter, candidate, node, "TargetArray") for node in adds) == 2, f"seed and loop append for {candidate}")
    for input_name in (BODY_INPUT, GIMBAL_INPUT, RATE_INPUT, TOTAL_INPUT, STEP_INPUT):
        contracts.require(not any("K2Node_VariableSet" in node.node_class and variable(node) == input_name for node in nodes.values()), f"input mutated: {input_name}")
    for forbidden in (
        "AirframePrebakeCompiledBodyQuatsV1", "AirframePrebakeCompiledGimbalQuatsV1",
        "AirframePrebakeCompileValidV1", "AirframePrebakeResultValidV1",
    ):
        contracts.require(f'MemberName="{forbidden}"' not in text, f"builder touched publication {forbidden}")
    stage_false = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and variable(node) == STAGE_VALID]
    contracts.require(len(stage_false) == 4 and all(default(node, STAGE_VALID) == "false" for node in stage_false), "four fail-closed helper exits")
    for node in stage_false[2:]:
        contracts.require(contracts.linked(node, "then", loops[0], "Break"), "loop helper rejection must break")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")

    cases = []
    directed = (
        (0.25, 0.25, (0.0, 30.0)),
        (1.0, 0.25, (0.0, 90.0, 90.0, 180.0, 180.0)),
        (1.0, 0.3, (0.0, 20.0, 50.0, 90.0, 130.0)),
    )
    for total, step, angles in directed:
        bodies = [axis_angle((1.0, 0.0, 0.0), angle) for angle in angles]
        gimbals = [axis_angle((0.0, 1.0, 0.0), -angle * 0.5) for angle in angles]
        cases.append((bodies, gimbals, [120.0] * len(angles), total, step))
    rng = random.Random(0xEDD_B017)
    for _ in range(100):
        total = rng.uniform(0.05, 2.0)
        step = rng.choice((1.0 / 120.0, 1.0 / 60.0, 1.0 / 30.0, 0.1, 0.3))
        times = oracle.fixed_sample_times(total, step)
        bodies = []
        gimbals = []
        for _time in times:
            body = axis_angle((rng.random() + 0.01, rng.random() + 0.01, rng.random() + 0.01), rng.uniform(-180.0, 180.0))
            gimbal = axis_angle((rng.random() + 0.01, rng.random() + 0.01, rng.random() + 0.01), rng.uniform(-180.0, 180.0))
            bodies.append(tuple(-v for v in body) if rng.random() < 0.5 else body)
            gimbals.append(tuple(-v for v in gimbal) if rng.random() < 0.5 else gimbal)
        cases.append((bodies, gimbals, [rng.uniform(0.001, 720.0) for _ in times], total, step))

    for index, case in enumerate(cases):
        bodies, gimbals, rates, total, step = case
        original = state_for(bodies, gimbals, rates, total, step)
        actual = Interpreter(nodes, original, oracle).run()
        expected = oracle.compile_airframe_gimbal_motion(*case)
        contracts.require(actual[STAGE_VALID] is True, f"valid case {index} rejected")
        contracts.require(actual[STAGE_INDEX] == len(bodies) - 1, f"valid case {index} terminal index")
        for sample_index, (left, right) in enumerate(zip(actual[BODY], expected.body_rotations)):
            contracts.require(close_quat(left, right), f"valid case {index} body sample {sample_index} mismatch: {left} != {right}")
        for sample_index, (left, right) in enumerate(zip(actual[GIMBAL], expected.gimbal_rotations)):
            contracts.require(close_quat(left, right), f"valid case {index} gimbal sample {sample_index} mismatch: {left} != {right}")
        # Angular diagnostics use acos near identity; long compositions amplify
        # harmless last-bit quaternion differences. Motion itself is checked
        # above at 2e-9/component, while diagnostic agreement stays at 1e-5.
        contracts.require(all(abs(a - b) <= 1.0e-5 for a, b in zip(actual[BODY_RATE], expected.body_angular_rates_degrees_per_second)), f"valid case {index} body rate mismatch: {actual[BODY_RATE]} != {expected.body_angular_rates_degrees_per_second}")
        contracts.require(all(abs(a - b) <= 1.0e-5 for a, b in zip(actual[GIMBAL_RATE], expected.gimbal_angular_rates_degrees_per_second)), f"valid case {index} gimbal rate mismatch: {actual[GIMBAL_RATE]} != {expected.gimbal_angular_rates_degrees_per_second}")
        contracts.require(tuple(actual[BODY_LIMITED]) == expected.body_rate_limited, f"valid case {index} body flags")
        contracts.require(tuple(actual[GIMBAL_LIMITED]) == expected.gimbal_rate_limited, f"valid case {index} gimbal flags")
        contracts.require(actual[BODY_INPUT] == bodies and actual[GIMBAL_INPUT] == gimbals and actual[RATE_INPUT] == rates, f"valid case {index} input mutation")

    positive = [IDENTITY] + [axis_angle((1.0, 0.0, 0.0), 180.0)] * 4
    negative = [tuple(-value for value in quaternion) for quaternion in positive]
    antipodal_left = Interpreter(nodes, state_for(positive, negative, [90.0] * 5, 1.0, 0.25), oracle).run()
    antipodal_right = Interpreter(nodes, state_for(negative, positive, [90.0] * 5, 1.0, 0.25), oracle).run()
    for channel in CANDIDATES:
        contracts.require(antipodal_left[channel] == antipodal_right[channel], f"antipodal stream changed {channel}")

    false_state = state_for([IDENTITY, IDENTITY], [IDENTITY, IDENTITY], [90.0, 90.0], 0.25, 0.25, False)
    false_result = Interpreter(nodes, false_state, oracle).run()
    contracts.require(all(false_result[name] == [] for name in CANDIDATES), "false stage must leave empty candidates")
    contracts.require(false_result[STAGE_VALID] is False and false_result[STAGE_INDEX] == 0, "false stage state")

    invalid_seed = state_for([(0.0, 0.0, 0.0, 0.0), IDENTITY], [IDENTITY, IDENTITY], [90.0, 90.0], 0.25, 0.25)
    invalid_seed_result = Interpreter(nodes, invalid_seed, oracle).run()
    contracts.require(invalid_seed_result[STAGE_VALID] is False, "invalid seed accepted")
    contracts.require(all(invalid_seed_result[name] == [] for name in CANDIDATES), "invalid seed leaked candidate")
    invalid_later = state_for([IDENTITY, (0.0, 0.0, 0.0, 0.0)], [IDENTITY, IDENTITY], [90.0, 90.0], 0.25, 0.25)
    invalid_later_result = Interpreter(nodes, invalid_later, oracle).run()
    contracts.require(invalid_later_result[STAGE_VALID] is False, "invalid loop body accepted")
    contracts.require(all(len(invalid_later_result[name]) == 1 for name in CANDIDATES), "invalid body must retain only complete seed")

    print(
        f"Airframe prebake sample-builder contracts passed ({'paste' if args.paste else 'full'}): "
        f"{len(cases)} valid, antipodal stream equivalence, false-stage no-op, 2 injected helper failures"
    )


if __name__ == "__main__":
    main()
