"""Executable exported-graph contracts for desired pose sample composition."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


PROFILE = (
    ("AirframeDesiredStreamInputPathFollowWeightsV1", "AirframeGimbalInputPathFollowWeightV1", "path_follow_weight"),
    ("AirframeDesiredStreamInputHorizonStabilizationWeightsV1", "AirframeGimbalInputHorizonStabilizationWeightV1", "horizon_stabilization_weight"),
    ("AirframeDesiredStreamInputLookAheadSecondsV1", "AirframeGimbalInputLookAheadSecondsV1", "look_ahead_seconds"),
    ("AirframeDesiredStreamInputBankGainsV1", "AirframeGimbalInputBankGainV1", "bank_gain"),
    ("AirframeDesiredStreamInputMaxBankDegreesV1", "AirframeGimbalInputMaxBankDegreesV1", "max_bank_degrees"),
    ("AirframeDesiredStreamInputCameraUptiltDegreesV1", "AirframeGimbalInputCameraUptiltDegreesV1", "camera_uptilt_degrees"),
    ("AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1", "AirframeGimbalInputMaxAngularRateDegreesPerSecondV1", "max_angular_rate_degrees_per_second"),
    ("AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1", "AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1", "max_acceleration_cm_per_second_squared"),
    ("AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1", "AirframeGimbalInputMaxJerkCmPerSecondCubedV1", "max_jerk_cm_per_second_cubed"),
    ("AirframeDesiredStreamInputMinimumTurnRadiiCmV1", "AirframeGimbalInputMinimumTurnRadiusCmV1", "minimum_turn_radius_cm"),
)
VELOCITIES = "AirframeDesiredStreamCandidateVelocitiesV1"
ACCELERATIONS = "AirframeDesiredStreamCandidateAccelerationsV1"
JERKS = "AirframeDesiredStreamCandidateJerksV1"
BODY_INPUT = "AirframeDesiredStreamInputAuthoredBodyQuatsV1"
GIMBAL_INPUT = "AirframeDesiredStreamInputAuthoredGimbalQuatsV1"
TOTAL = "AirframeDesiredStreamInputTotalSecondsV1"
STEP = "AirframeDesiredStreamInputFixedStepSecondsV1"
STAGE = "AirframeDesiredStreamStageValidV1"
INDEX = "AirframeDesiredStreamStageIndexV1"
OUTPUTS = (
    ("AirframeDesiredStreamCandidateLookAheadVelocitiesV1", "vector"),
    ("AirframeDesiredStreamCandidateBodyQuatsV1", "quat"),
    ("AirframeDesiredStreamCandidateGimbalQuatsV1", "quat"),
    ("AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1", "real"),
)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def default(node, pin_name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body); return "" if match is None else match.group(1)


class Interpreter:
    def __init__(self, nodes, state, desired_reference, gimbal_reference, fail_sampler=None, fail_solver=None):
        self.nodes, self.state = nodes, dict(state); self.desired_reference, self.gimbal_reference = desired_reference, gimbal_reference
        self.fail_sampler, self.fail_solver = fail_sampler, fail_solver; self.loop_indices = {}; self.cache = {}; self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match: self.pin_owner[(node.name, match.group(1))] = (node, pin)
    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in target[1].body: return target[0], target[1].name
        return None
    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        if source: return self.output(*source)
        text = default(node, pin_name)
        if text == "true": return True
        if text == "false": return False
        if text in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"): return (0.0, 0.0, 0.0)
        try: return float(text)
        except ValueError: return text
    def output(self, node, pin_name):
        key = (node.name, pin_name)
        if key not in self.cache: self.cache[key] = self._output(node, pin_name)
        return self.cache[key]
    def _output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class or "K2Node_VariableSet" in node.node_class: return self.state[member(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name == "Index": return self.loop_indices[node.name]
            raise RuntimeError(pin_name)
        if "K2Node_GetArrayItem" in node.node_class: return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        name = member(node)
        if name == "Array_Length": return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble": return float(self.value(node, "InInt"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "Subtract_IntInt": return int(left) - int(right)
        if name == "Multiply_DoubleDouble": return left * right
        if name == "Add_DoubleDouble": return left + right
        if name == "Min_DoubleDouble": return min(left, right)
        raise RuntimeError(f"unsupported pure {node.name}:{name}")
    def next_target(self, node, pin_name="then"):
        if pin_name not in node.pins: return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec", "Execute", "Break"): return target[0], target[1].name
        return None
    def invoke(self, name):
        index = int(self.state[INDEX])
        if name == "SampleAirframeDesiredVelocityAtTimeV1":
            if self.fail_sampler == index:
                self.state["AirframeDesiredStreamVelocitySampleResultValidV1"] = False; return
            times = tuple(min(i * self.state[STEP], self.state[TOTAL]) for i in range(len(self.state[VELOCITIES])))
            try:
                result = self.desired_reference.sample_vector_track_linear(self.state[VELOCITIES], times, self.state["AirframeDesiredStreamVelocitySampleInputSecondsV1"])
            except Exception:
                self.state["AirframeDesiredStreamVelocitySampleResultValidV1"] = False
            else:
                self.state["AirframeDesiredStreamVelocitySampleResultV1"] = result; self.state["AirframeDesiredStreamVelocitySampleResultValidV1"] = True
            return
        if name == "SolveAirframeGimbalV1":
            if self.fail_solver == index:
                self.state["AirframeGimbalResultValidV1"] = False; return
            profile = self.gimbal_reference.AirframeGimbalProfile(**{field: self.state[target] for _source, target, field in PROFILE})
            try:
                result = self.gimbal_reference.solve_airframe_gimbal(
                    self.state["AirframeGimbalInputCurrentVelocityV1"], self.state["AirframeGimbalInputLookAheadVelocityV1"],
                    self.state["AirframeGimbalInputAccelerationV1"], self.state["AirframeGimbalInputJerkV1"],
                    self.state["AirframeGimbalInputAuthoredBodyQuatV1"], self.state["AirframeGimbalInputAuthoredGimbalQuatV1"], profile,
                )
            except Exception:
                self.state["AirframeGimbalResultValidV1"] = False
            else:
                self.state["AirframeGimbalResultBodyQuatV1"] = result.body_rotation; self.state["AirframeGimbalResultGimbalQuatV1"] = result.gimbal_rotation; self.state["AirframeGimbalResultValidV1"] = True
            return
        raise RuntimeError(name)
    def execute_chain(self, current, enclosing_loop=None):
        while current is not None:
            name = member(current)
            if "K2Node_VariableSet" in current.node_class:
                self.state[name] = self.value(current, name); self.cache.clear(); target = self.next_target(current)
            elif name == "Array_Clear":
                source = self.source(current, "TargetArray"); self.state[member(source[0])] = []; self.cache.clear(); target = self.next_target(current)
            elif name == "Array_Add":
                source = self.source(current, "TargetArray"); self.state[member(source[0])].append(self.value(current, "NewItem")); self.cache.clear(); target = self.next_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                target = self.next_target(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                first, last = int(self.value(current, "FirstIndex")), int(self.value(current, "LastIndex")); body = self.next_target(current, "LoopBody")
                for index in range(first, last + 1):
                    self.loop_indices[current.name] = index; self.cache.clear()
                    if body and self.execute_chain(body[0], current): break
                target = self.next_target(current, "Completed")
            elif name in ("SampleAirframeDesiredVelocityAtTimeV1", "SolveAirframeGimbalV1"):
                self.invoke(name); self.cache.clear(); target = self.next_target(current)
            else: raise RuntimeError(f"unsupported exec {current.name}:{name}")
            if target is None: return False
            if enclosing_loop is not None and target[0] is enclosing_loop and target[1] == "Break": return True
            current = target[0]
        return False
    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries: start = self.next_target(entries[0])[0]
        else: start = next(node for node in self.nodes.values() if member(node) == "Array_Clear" and not node.pins["execute"].links)
        self.execute_chain(start); return self.state


def make_state(desired, gimbal, total, step, seed):
    times = tuple(min(i * step, total) for i in range(math.ceil(total / step) + 1)); rng = random.Random(seed)
    positions = [(120.0 * t, 25.0 * t * t, 5.0 * t) for t in times]
    velocities = desired.differentiate_sampled_vectors(positions, times); accelerations = desired.differentiate_sampled_vectors(velocities, times); jerks = desired.differentiate_sampled_vectors(accelerations, times)
    bodies = [(0.0, 0.0, math.sin(0.05 * i), math.cos(0.05 * i)) for i in range(len(times))]
    gimbals = [(0.0, math.sin(-0.03 * i), 0.0, math.cos(-0.03 * i)) for i in range(len(times))]
    defaults = (0.7, 0.4, 0.2, 0.8, 35.0, 3.0, 180.0, 5000.0, 20000.0, 0.01)
    state = {VELOCITIES: list(velocities), ACCELERATIONS: list(accelerations), JERKS: list(jerks), BODY_INPUT: bodies, GIMBAL_INPUT: gimbals, TOTAL: total, STEP: step, STAGE: True, INDEX: 999}
    for (source, _target, _field), value in zip(PROFILE, defaults): state[source] = [value + (rng.uniform(-0.01, 0.01) if source.endswith("WeightsV1") else 0.0) for _ in times]
    for name, _kind in OUTPUTS: state[name] = ["poison"]
    state.update({"AirframeDesiredStreamVelocitySampleResultV1": (9.0, 9.0, 9.0), "AirframeDesiredStreamVelocitySampleResultValidV1": False, "AirframeGimbalResultBodyQuatV1": (0,0,0,1), "AirframeGimbalResultGimbalQuatV1": (0,0,0,1), "AirframeGimbalResultValidV1": False})
    return state, times


def expected(state, times, desired, gimbal):
    look, bodies, gimbals, rates = [], [], [], []
    for i, time in enumerate(times):
        profile = gimbal.AirframeGimbalProfile(**{field: state[source][i] for source, _target, field in PROFILE})
        ahead = desired.sample_vector_track_linear(state[VELOCITIES], times, time + profile.look_ahead_seconds)
        result = gimbal.solve_airframe_gimbal(state[VELOCITIES][i], ahead, state[ACCELERATIONS][i], state[JERKS][i], state[BODY_INPUT][i], state[GIMBAL_INPUT][i], profile)
        look.append(ahead); bodies.append(result.body_rotation); gimbals.append(result.gimbal_rotation); rates.append(profile.max_angular_rate_degrees_per_second)
    return look, bodies, gimbals, rates


def close_nested(actual, expected, tolerance=2e-9):
    return len(actual) == len(expected) and all(math.isclose(float(a), float(e), rel_tol=tolerance, abs_tol=tolerance) for av, ev in zip(actual, expected) for a, e in zip(av if isinstance(av, (tuple,list)) else (av,), ev if isinstance(ev, (tuple,list)) else (ev,)))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    contracts = load_module(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_pose_samples_contract_base")
    trajectory = str(args.project_root / "tools/trajectory"); sys.path.insert(0, trajectory) if trajectory not in sys.path else None
    desired = load_module(args.project_root / "tools/trajectory/airframe_desired_stream_reference.py", "edd_pose_samples_desired_reference")
    gimbal = sys.modules["airframe_gimbal_reference"]
    nodes = contracts.parse_graph(args.graph); contracts.require(len(nodes) == (83 if args.paste else 84), f"node count {len(nodes)}")
    contracts.require(len([n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class]) == 1, "one loop")
    contracts.require(len([n for n in nodes.values() if "K2Node_GetArrayItem" in n.node_class]) == 15, "15 source items")
    contracts.require(len([n for n in nodes.values() if member(n) == "Array_Clear"]) == 4, "four candidate clears")
    contracts.require(len([n for n in nodes.values() if member(n) == "Array_Add"]) == 4, "four aligned appends")
    contracts.require(len([n for n in nodes.values() if member(n) == "SampleAirframeDesiredVelocityAtTimeV1"]) == 1, "one sampler call")
    contracts.require(len([n for n in nodes.values() if member(n) == "SolveAirframeGimbalV1"]) == 1, "one solver call")
    known = set(nodes); contracts.require(not {t for n in nodes.values() for p in n.pins.values() for t,_ in p.links if t not in known}, "external links")
    contracts.require(not any("K2Node_Knot" in n.node_class for n in nodes.values()), "reroute forbidden")

    cases = [(0.1, 0.5), (1.0, 0.25), (1.0, 0.3), (1.7, 0.2)]
    rng = random.Random(0xEDD_905E)
    for _ in range(40):
        step = rng.choice((0.05, 0.1, 0.2, 0.3, 0.5))
        cases.append((rng.uniform(max(0.01, step * 0.1), 2.5), step))
    for index, (total, step) in enumerate(cases):
        state, times = make_state(desired, gimbal, total, step, index); wanted = expected(state, times, desired, gimbal)
        result = Interpreter(nodes, state, desired, gimbal).run(); contracts.require(result[STAGE] is True, f"valid stage {index}")
        for (name, _kind), values in zip(OUTPUTS, wanted): contracts.require(close_nested(result[name], values), f"valid {index}:{name}")
        repeat = Interpreter(nodes, {**state, **{name: list(reversed(values)) for (name,_), values in zip(OUTPUTS,wanted)}}, desired, gimbal).run()
        for (name, _kind), values in zip(OUTPUTS, wanted): contracts.require(close_nested(repeat[name], values), f"repeat {index}:{name}")

    state, times = make_state(desired, gimbal, 1.0, 0.25, 99)
    for label, sampler_fail, solver_fail, prefix in (("sampler", 2, None, 2), ("solver", None, 3, 3)):
        result = Interpreter(nodes, state, desired, gimbal, sampler_fail, solver_fail).run(); contracts.require(result[STAGE] is False, f"{label} failure validity")
        contracts.require(all(len(result[name]) == prefix for name,_ in OUTPUTS), f"{label} aligned prefix")
    guarded = Interpreter(nodes, {**state, STAGE: False, VELOCITIES: object()}, desired, gimbal).run()
    contracts.require(all(guarded[name] == [] for name,_ in OUTPUTS) and guarded[STAGE] is False, "false-stage guarded clear")
    physical = {**state, PROFILE[7][0]: list(state[PROFILE[7][0]])}; physical[PROFILE[7][0]][2] = 0.0001
    result = Interpreter(nodes, physical, desired, gimbal).run(); contracts.require(result[STAGE] is False and all(len(result[name]) == 2 for name,_ in OUTPUTS), "physical failure prefix")
    print(f"Airframe desired pose-sample contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} valid, helper/solver/physical failures, guarded no-op")


if __name__ == "__main__": main()
