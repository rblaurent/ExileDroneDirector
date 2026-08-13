"""Structural and executable contracts for EvaluateCompiledAirframePrebakeV1."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


ARRAYS = (
    "AirframePrebakeCompiledBodyQuatsV1",
    "AirframePrebakeCompiledGimbalQuatsV1",
    "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1",
    "AirframePrebakeCompiledBodyRateLimitedV1",
    "AirframePrebakeCompiledGimbalRateLimitedV1",
)
ELAPSED = "AirframePrebakeInputElapsedSecondsV1"
STEP = "AirframePrebakeCompiledFixedStepSecondsV1"
TOTAL = "AirframePrebakeCompiledTotalSecondsV1"
COMPILE_VALID = "AirframePrebakeCompileValidV1"
SEGMENT = "AirframePrebakeResultSegmentIndexV1"
ALPHA = "AirframePrebakeResultAlphaV1"
BODY = "AirframePrebakeResultBodyQuatV1"
GIMBAL = "AirframePrebakeResultGimbalQuatV1"
COMPLETE = "AirframePrebakeResultCompleteV1"
VALID = "AirframePrebakeResultValidV1"
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
        raise RuntimeError(f"variable missing: {node.name}")
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


def axis_angle(axis, angle_degrees):
    magnitude = math.sqrt(sum(value * value for value in axis))
    unit = tuple(value / magnitude for value in axis)
    half = math.radians(angle_degrees) * 0.5
    sine = math.sin(half)
    return (unit[0] * sine, unit[1] * sine, unit[2] * sine, math.cos(half))


def close_quat(left, right, tolerance=3.0e-9):
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
        return self.output(*source) if source is not None else parse_default(default(node, pin_name))

    def output(self, node, pin_name):
        if "K2Node_Variable" in node.node_class:
            return self.state[variable(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name == "Array Element":
                return self.loop_values[node.name]
            raise RuntimeError(f"loop output {node.name}.{pin_name}")
        name = member(node)
        if "K2Node_GetArrayItem" in node.node_class:
            return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "IsFinite":
            return math.isfinite(self.value(node, "A"))
        if name == "Quat_IsFinite":
            return all(math.isfinite(value) for value in self.value(node, "Q"))
        if name == "Quat_Size":
            return math.sqrt(sum(value * value for value in self.value(node, "Q")))
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        if name == "FFloor":
            return math.floor(self.value(node, "A"))
        if name == "FClamp":
            return min(max(self.value(node, "Value"), self.value(node, "Min")), self.value(node, "Max"))
        if name == "SelectFloat":
            return self.value(node, "A") if self.value(node, "bPickA") else self.value(node, "B")
        if name == "Quat_Slerp":
            return self.oracle.slerp(self.value(node, "A"), self.value(node, "B"), self.value(node, "Alpha"))
        left, right = self.value(node, "A"), self.value(node, "B")
        operations = {
            "GreaterEqual_IntInt": lambda: int(left) >= int(right),
            "LessEqual_IntInt": lambda: int(left) <= int(right),
            "EqualEqual_IntInt": lambda: int(left) == int(right),
            "Greater_DoubleDouble": lambda: left > right,
            "GreaterEqual_DoubleDouble": lambda: left >= right,
            "Less_DoubleDouble": lambda: left < right,
            "LessEqual_DoubleDouble": lambda: left <= right,
            "EqualEqual_DoubleDouble": lambda: left == right,
            "EqualEqual_BoolBool": lambda: bool(left) == bool(right),
            "Subtract_IntInt": lambda: int(left) - int(right),
            "Add_IntInt": lambda: int(left) + int(right),
            "Multiply_DoubleDouble": lambda: left * right,
            "Subtract_DoubleDouble": lambda: left - right,
            "Divide_DoubleDouble": lambda: left / right,
        }
        if name in operations:
            return operations[name]()
        raise RuntimeError(f"unsupported output {node.name}:{name}.{pin_name}")

    def exec_target(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def execute_chain(self, current):
        visits = 0
        while current is not None:
            visits += 1
            if visits > 64:
                raise RuntimeError("execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = variable(current)
                self.state[name] = self.value(current, name)
                current = self.exec_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.exec_target(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                for value in self.value(current, "Array"):
                    self.loop_values[current.name] = value
                    body = self.exec_target(current, "LoopBody")
                    if body is not None:
                        self.execute_chain(body)
                current = self.exec_target(current, "Completed")
            else:
                raise RuntimeError(f"unsupported execution {current.name}:{member(current)}")

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.exec_target(entries[0])
        else:
            roots = [node for node in self.nodes.values() if "execute" in node.pins and not node.pins["execute"].links]
            if len(roots) != 1:
                raise RuntimeError(f"paste root count {len(roots)}")
            current = roots[0]
        self.execute_chain(current)
        return self.state


def state_from(track, elapsed):
    return {
        ARRAYS[0]: list(track.body_rotations), ARRAYS[1]: list(track.gimbal_rotations),
        ARRAYS[2]: list(track.body_angular_rates_degrees_per_second),
        ARRAYS[3]: list(track.gimbal_angular_rates_degrees_per_second),
        ARRAYS[4]: list(track.body_rate_limited), ARRAYS[5]: list(track.gimbal_rate_limited),
        STEP: track.fixed_step_seconds, TOTAL: track.total_seconds, COMPILE_VALID: True, ELAPSED: elapsed,
        SEGMENT: 777, ALPHA: 777.0, BODY: (7.0, 7.0, 7.0, 7.0), GIMBAL: (7.0, 7.0, 7.0, 7.0),
        COMPLETE: True, VALID: True,
    }


def assert_invalid(contracts, nodes, oracle, state, label):
    result = Interpreter(nodes, state, oracle).run()
    contracts.require(result[VALID] is False and result[COMPLETE] is False, f"{label}: validity")
    contracts.require(result[SEGMENT] == -1 and result[ALPHA] == 0.0, f"{label}: scalar reset")
    contracts.require(result[BODY] == IDENTITY and result[GIMBAL] == IDENTITY, f"{label}: quaternion reset")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_prebake_eval_contract_base")
    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    oracle = load(args.project_root / "tools/trajectory/airframe_gimbal_prebake_reference.py", "edd_prebake_eval_oracle")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (154 if args.paste else 155), f"evaluator node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    text = "\n".join(node.text for node in nodes.values())
    contracts.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text, "unsafe graph form")
    contracts.require(len([node for node in nodes.values() if member(node) == "Array_Length"]) == 6, "six lengths")
    contracts.require(len([node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]) == 4, "four content scans")
    contracts.require(len([node for node in nodes.values() if member(node) == "Quat_Slerp"]) == 2, "independent body/gimbal slerp")
    contracts.require(len([node for node in nodes.values() if member(node) == "FFloor"]) == 1, "absolute-time segment floor")
    for name in (*ARRAYS, STEP, TOTAL, COMPILE_VALID, ELAPSED):
        contracts.require(not any("K2Node_VariableSet" in node.node_class and variable(node) == name for node in nodes.values()), f"immutable input/publication mutated: {name}")
    true_valid = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and variable(node) == VALID and default(node, VALID) == "true"]
    contracts.require(len(true_valid) == 3, "shape staging and two terminal validity publications")
    for publication in true_valid[1:]:
        contracts.require(not publication.pins["then"].links, "result validity must publish last")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")

    rng = random.Random(0xEDD_EA11)
    tracks = []
    for _ in range(20):
        total = rng.uniform(0.05, 2.0)
        step = rng.choice((1.0 / 120.0, 1.0 / 60.0, 1.0 / 30.0, 0.1, 0.3))
        count = len(oracle.fixed_sample_times(total, step))
        bodies = [axis_angle((rng.random() + 0.01, rng.random() + 0.01, rng.random() + 0.01), rng.uniform(-180.0, 180.0)) for _ in range(count)]
        gimbals = [axis_angle((rng.random() + 0.01, rng.random() + 0.01, rng.random() + 0.01), rng.uniform(-180.0, 180.0)) for _ in range(count)]
        rates = [rng.uniform(0.001, 720.0) for _ in range(count)]
        tracks.append(oracle.compile_airframe_gimbal_motion(bodies, gimbals, rates, total, step))
    evaluations = 0
    for track_index, track in enumerate(tracks):
        times = [-1.0, 0.0, track.total_seconds, track.total_seconds + 1.0]
        times.extend(index * track.fixed_step_seconds for index in range(min(len(track.body_rotations) - 1, 6)))
        times.append(math.nextafter(track.total_seconds, 0.0))
        times.extend(rng.uniform(0.0, track.total_seconds) for _ in range(10))
        canonical = {}
        for elapsed in times:
            actual = Interpreter(nodes, state_from(track, elapsed), oracle).run()
            expected = oracle.evaluate_airframe_gimbal_motion(track, elapsed)
            contracts.require(actual[VALID] == expected.valid and actual[COMPLETE] == expected.complete, f"track {track_index} time {elapsed}: flags")
            contracts.require(actual[SEGMENT] == expected.segment_index and abs(actual[ALPHA] - expected.alpha) <= 2.0e-9, f"track {track_index} time {elapsed}: coordinates")
            contracts.require(close_quat(actual[BODY], expected.body_rotation) and close_quat(actual[GIMBAL], expected.gimbal_rotation), f"track {track_index} time {elapsed}: pose")
            canonical[elapsed] = (actual[SEGMENT], actual[ALPHA], actual[BODY], actual[GIMBAL], actual[COMPLETE], actual[VALID])
            evaluations += 1
        poisoned = state_from(track, 0.0)
        for elapsed in reversed(times):
            poisoned[ELAPSED] = elapsed
            poisoned.update({SEGMENT: 999, ALPHA: 999.0, BODY: (9.0, 9.0, 9.0, 9.0), GIMBAL: (9.0, 9.0, 9.0, 9.0), COMPLETE: not canonical[elapsed][4], VALID: False})
            poisoned = Interpreter(nodes, poisoned, oracle).run()
            actual = (poisoned[SEGMENT], poisoned[ALPHA], poisoned[BODY], poisoned[GIMBAL], poisoned[COMPLETE], poisoned[VALID])
            contracts.require(actual == canonical[elapsed], f"track {track_index} time {elapsed}: history dependence")

    baseline = tracks[0]
    invalids = []
    state = state_from(baseline, 0.1); state[COMPILE_VALID] = False; invalids.append(("compile validity", state))
    state = state_from(baseline, float("nan")); invalids.append(("elapsed finite", state))
    state = state_from(baseline, 0.1)
    for name in ARRAYS: state[name] = []
    invalids.append(("empty publication", state))
    for index, name in enumerate(ARRAYS[1:]):
        state = state_from(baseline, 0.1); state[name] = state[name][:-1]; invalids.append((f"cardinality {index}", state))
    state = state_from(baseline, 0.1); state[ARRAYS[0]][0] = (0.0, 0.0, 0.0, 0.0); invalids.append(("body quaternion", state))
    state = state_from(baseline, 0.1); state[ARRAYS[1]][0] = (float("nan"), 0.0, 0.0, 1.0); invalids.append(("gimbal quaternion", state))
    state = state_from(baseline, 0.1); state[ARRAYS[2]][1] = 721.0; invalids.append(("body rate", state))
    state = state_from(baseline, 0.1); state[ARRAYS[3]][1] = float("inf"); invalids.append(("gimbal rate", state))
    state = state_from(baseline, 0.1); state[ARRAYS[2]][0] = 0.1; invalids.append(("body seed rate", state))
    state = state_from(baseline, 0.1); state[ARRAYS[3]][0] = 0.1; invalids.append(("gimbal seed rate", state))
    state = state_from(baseline, 0.1); state[ARRAYS[4]][0] = True; invalids.append(("body seed flag", state))
    state = state_from(baseline, 0.1); state[ARRAYS[5]][0] = True; invalids.append(("gimbal seed flag", state))
    state = state_from(baseline, 0.1); state[STEP] = 0.001; invalids.append(("fixed step", state))
    state = state_from(baseline, 0.1); state[TOTAL] = 3601.0; invalids.append(("total", state))
    state = state_from(baseline, 0.1); state[TOTAL] += state[STEP] * 2.0; invalids.append(("schedule", state))
    for label, state in invalids:
        assert_invalid(contracts, nodes, oracle, state, label)

    print(
        f"Airframe prebake evaluator contracts passed ({'paste' if args.paste else 'full'}): "
        f"{evaluations} oracle-equivalent evaluations, arbitrary-order replay, {len(invalids)} corrupt states"
    )


if __name__ == "__main__":
    main()
