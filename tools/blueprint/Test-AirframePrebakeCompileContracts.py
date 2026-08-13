"""Exact orchestration and end-to-end contracts for CompileAirframePrebakeV1."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


STAGES = (
    "ResetAirframePrebakeCandidateV1",
    "ValidateAirframePrebakeInputsV1",
    "BuildAirframePrebakeSamplesV1",
    "CommitCompiledAirframePrebakeV1",
)
COMPILED = (
    ("AirframePrebakeCompiledBodyQuatsV1", "body_rotations"),
    ("AirframePrebakeCompiledGimbalQuatsV1", "gimbal_rotations"),
    ("AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1", "body_angular_rates_degrees_per_second"),
    ("AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1", "gimbal_angular_rates_degrees_per_second"),
    ("AirframePrebakeCompiledBodyRateLimitedV1", "body_rate_limited"),
    ("AirframePrebakeCompiledGimbalRateLimitedV1", "gimbal_rate_limited"),
)
BODY_INPUT = "AirframePrebakeInputDesiredBodyQuatsV1"
GIMBAL_INPUT = "AirframePrebakeInputDesiredGimbalQuatsV1"
RATE_INPUT = "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"
TOTAL_INPUT = "AirframePrebakeInputTotalSecondsV1"
STEP_INPUT = "AirframePrebakeInputFixedStepSecondsV1"
COMPILE_VALID = "AirframePrebakeCompileValidV1"
COMPILED_STEP = "AirframePrebakeCompiledFixedStepSecondsV1"
COMPILED_TOTAL = "AirframePrebakeCompiledTotalSecondsV1"
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


def parse_default(text):
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
        return int(text) if re.fullmatch(r"-?\d+", text) else float(text)
    except ValueError:
        return text


def execute_reset(nodes, state):
    result = dict(state)
    pin_owner = {}
    for node in nodes.values():
        for pin in node.pins.values():
            match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
            if match:
                pin_owner[(node.name, match.group(1))] = (node, pin)

    def next_node(node):
        for link in node.pins.get("then", ()).links if "then" in node.pins else ():
            target = pin_owner.get(link)
            if target is not None and target[1].name == "execute":
                return target[0]
        return None

    def source(node, pin):
        for link in node.pins[pin].links:
            target = pin_owner.get(link)
            if target is not None and 'Direction="EGPD_Output"' in target[1].body:
                return target[0]
        return None

    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    if entries:
        current = next_node(entries[0])
    else:
        roots = [node for node in nodes.values() if "execute" in node.pins and not node.pins["execute"].links]
        if len(roots) != 1:
            raise RuntimeError(f"reset root count {len(roots)}")
        current = roots[0]
    while current is not None:
        if "K2Node_CallArrayFunction" in current.node_class and member(current) == "Array_Clear":
            getter = source(current, "TargetArray")
            if getter is None:
                raise RuntimeError("reset clear target")
            result[variable(getter)] = []
        elif "K2Node_VariableSet" in current.node_class:
            name = variable(current)
            result[name] = parse_default(default(current, name))
        else:
            raise RuntimeError(f"unsupported reset node {current.name}")
        current = next_node(current)
    return result


def axis_angle(axis, angle_degrees):
    magnitude = math.sqrt(sum(value * value for value in axis))
    unit = tuple(value / magnitude for value in axis)
    half = math.radians(angle_degrees) * 0.5
    sine = math.sin(half)
    return (unit[0] * sine, unit[1] * sine, unit[2] * sine, math.cos(half))


def close_quat(left, right, tolerance=2.0e-9):
    return max(abs(a - b) for a, b in zip(left, right)) <= tolerance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_prebake_compile_contract_base")
    validation = load(args.project_root / "tools/blueprint/Test-AirframePrebakeValidationContracts.py", "edd_prebake_compile_validation")
    samples = load(args.project_root / "tools/blueprint/Test-AirframePrebakeSamplesContracts.py", "edd_prebake_compile_samples")
    commit = load(args.project_root / "tools/blueprint/Test-AirframePrebakeCommitContracts.py", "edd_prebake_compile_commit")
    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    oracle = load(args.project_root / "tools/trajectory/airframe_gimbal_prebake_reference.py", "edd_prebake_compile_oracle")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (4 if args.paste else 5), f"compile node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    calls = []
    for name in STAGES:
        found = [node for node in nodes.values() if f'MemberName="{name}"' in node.text]
        contracts.require(len(found) == 1 and "bSelfContext=True" in found[0].text, f"one self call {name}")
        calls.append(found[0])
    for left, right in zip(calls, calls[1:]):
        contracts.require_link(left, "then", right, "execute", "compile stage order")
    if args.paste:
        contracts.require(not calls[0].pins["execute"].links, "paste root")
    else:
        contracts.require_link(entries[0], "then", calls[0], "execute", "entry reset seam")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")

    suffix = "-paste" if args.paste else ""
    snippet = args.project_root / "tools/blueprint/snippets"
    reset_nodes = contracts.parse_graph(snippet / f"reset-airframe-prebake-candidate-v1{suffix}.eddgraph")
    validation_nodes = contracts.parse_graph(snippet / f"validate-airframe-prebake-inputs-v1{suffix}.eddgraph")
    sample_nodes = contracts.parse_graph(snippet / f"build-airframe-prebake-samples-v1{suffix}.eddgraph")
    commit_nodes = contracts.parse_graph(snippet / f"commit-compiled-airframe-prebake-v1{suffix}.eddgraph")

    def execute(state):
        state = execute_reset(reset_nodes, state)
        validator = validation.Interpreter(contracts, validation_nodes, state)
        validator.run()
        state = validator.state
        state = samples.Interpreter(sample_nodes, state, oracle).run()
        return commit.Interpreter(commit_nodes, state).run()

    rng = random.Random(0xEDD_C011)
    cases = []
    for _ in range(30):
        total = rng.uniform(0.05, 2.0)
        step = rng.choice((1.0 / 120.0, 1.0 / 60.0, 1.0 / 30.0, 0.1, 0.3))
        count = len(oracle.fixed_sample_times(total, step))
        bodies = [axis_angle((rng.random() + 0.01, rng.random() + 0.01, rng.random() + 0.01), rng.uniform(-180.0, 180.0)) for _ in range(count)]
        gimbals = [axis_angle((rng.random() + 0.01, rng.random() + 0.01, rng.random() + 0.01), rng.uniform(-180.0, 180.0)) for _ in range(count)]
        rates = [rng.uniform(0.001, 720.0) for _ in range(count)]
        cases.append((bodies, gimbals, rates, total, step))

    for index, case in enumerate(cases):
        bodies, gimbals, rates, total, step = case
        state = samples.state_for(bodies, gimbals, rates, total, step)
        for name, _field in COMPILED:
            state[name] = ["poison"]
        state[COMPILED_STEP] = 999.0
        state[COMPILED_TOTAL] = 999.0
        state[COMPILE_VALID] = True
        originals = (state[BODY_INPUT], state[GIMBAL_INPUT], state[RATE_INPUT])
        actual = execute(state)
        expected = oracle.compile_airframe_gimbal_motion(*case)
        contracts.require(actual[COMPILE_VALID] is True, f"valid pipeline {index} rejected")
        for name, field in COMPILED:
            left, right = actual[name], getattr(expected, field)
            if "Quat" in name:
                contracts.require(len(left) == len(right) and all(close_quat(a, b) for a, b in zip(left, right)), f"valid pipeline {index} {name}")
            elif "AngularRates" in name:
                contracts.require(len(left) == len(right) and all(abs(a - b) <= 1.0e-5 for a, b in zip(left, right)), f"valid pipeline {index} {name}")
            else:
                contracts.require(tuple(left) == tuple(right), f"valid pipeline {index} {name}")
        contracts.require(actual[COMPILED_STEP] == step and actual[COMPILED_TOTAL] == total, f"valid pipeline {index} schedule")
        contracts.require((actual[BODY_INPUT], actual[GIMBAL_INPUT], actual[RATE_INPUT]) == originals, f"valid pipeline {index} input mutation")

    base = cases[0]
    invalids = []
    state = samples.state_for(*base); state[GIMBAL_INPUT] = state[GIMBAL_INPUT][:-1]; invalids.append(("cardinality", state))
    state = samples.state_for(*base); state[BODY_INPUT][0] = (0.0, 0.0, 0.0, 0.0); invalids.append(("quaternion", state))
    state = samples.state_for(*base); state[RATE_INPUT][0] = 0.0; invalids.append(("rate", state))
    state = samples.state_for(*base); state[TOTAL_INPUT] = 3601.0; invalids.append(("total", state))
    state = samples.state_for(*base); state[STEP_INPUT] = 0.001; invalids.append(("step", state))
    for label, state in invalids:
        for name, _field in COMPILED:
            state[name] = ["stale"]
        state[COMPILED_STEP] = state[COMPILED_TOTAL] = 42.0
        state[COMPILE_VALID] = True
        actual = execute(state)
        contracts.require(actual[COMPILE_VALID] is False, f"invalid {label} published")
        contracts.require(all(actual[name] == [] for name, _field in COMPILED), f"invalid {label} leaked payload")
        contracts.require(actual[COMPILED_STEP] == 0.0 and actual[COMPILED_TOTAL] == 0.0, f"invalid {label} leaked schedule")

    prior = execute(samples.state_for(*cases[1]))
    prior[BODY_INPUT] = []
    prior[GIMBAL_INPUT] = []
    prior[RATE_INPUT] = []
    again = execute(prior)
    contracts.require(again[COMPILE_VALID] is False and all(again[name] == [] for name, _ in COMPILED), "failed recompilation leaked prior success")
    print(
        f"Airframe prebake compile contracts passed ({'paste' if args.paste else 'full'}): "
        "30 oracle-equivalent streams, 5 invalid families, failed-recompile cleanup"
    )


if __name__ == "__main__":
    main()
