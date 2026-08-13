"""Executable contracts for aligned position/body/profile source sampling."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


STAGE = "AirframeSourceStageValidV1"
INDEX = "AirframeSourceSampleIndexV1"
TOTAL = "AirframeSourceTotalSecondsV1"
STEP = "AirframeSourceInputFixedStepSecondsV1"
PROFILE = (
    ("PathFollowWeight", "path_follow_weight", "AirframeSourceCandidatePathFollowWeightsV1"),
    ("HorizonStabilizationWeight", "horizon_stabilization_weight", "AirframeSourceCandidateHorizonStabilizationWeightsV1"),
    ("LookAheadSeconds", "look_ahead_seconds", "AirframeSourceCandidateLookAheadSecondsV1"),
    ("BankGain", "bank_gain", "AirframeSourceCandidateBankGainsV1"),
    ("MaxBankDegrees", "max_bank_degrees", "AirframeSourceCandidateMaxBankDegreesV1"),
    ("CameraUptiltDegrees", "camera_uptilt_degrees", "AirframeSourceCandidateCameraUptiltDegreesV1"),
    ("MaxAngularRateDegreesPerSecond", "max_angular_rate_degrees_per_second", "AirframeSourceCandidateMaxAngularRatesDegreesPerSecondV1"),
    ("MaxAccelerationCmPerSecondSquared", "max_acceleration_cm_per_second_squared", "AirframeSourceCandidateMaxAccelerationsCmPerSecondSquaredV1"),
    ("MaxJerkCmPerSecondCubed", "max_jerk_cm_per_second_cubed", "AirframeSourceCandidateMaxJerksCmPerSecondCubedV1"),
    ("MinimumTurnRadiusCm", "minimum_turn_radius_cm", "AirframeSourceCandidateMinimumTurnRadiiCmV1"),
)
OUTPUTS = (
    ("AirframeSourceCandidatePositionsV1", "vector"),
    ("AirframeSourceCandidateBodyQuatsV1", "quat"),
    *((candidate, "real") for _field, _attribute, candidate in PROFILE),
)
CALLS = (
    "CompileOrientationTrackV1",
    "EvaluateCompiledPositionRouteV1",
    "EvaluateCompiledOrientationTrackV1",
    "EvaluateSmoothedFlightProfileV1",
)


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


def explicit_default(node, pin_name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
    return None if match is None else match.group(1)


class Interpreter:
    def __init__(self, nodes, state, modules, failures=None, timeline_mutation=None):
        self.nodes = nodes
        self.state = copy.deepcopy(state)
        self.modules = modules
        self.failures = failures or {}
        self.timeline_mutation = timeline_mutation or {}
        self.loop_indices = {}
        self.loop_elements = {}
        self.pin_owner = {}
        self.cache = {}
        self.calls = []
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
        text = explicit_default(node, pin_name)
        if text is None or text == "":
            body = node.pins[pin_name].body
            if 'PinType.PinCategory="int"' in body:
                return 0
            if 'PinType.PinCategory="real"' in body:
                return 0.0
            if 'PinType.PinCategory="bool"' in body:
                return False
            return ""
        if text == "true":
            return True
        if text == "false":
            return False
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
        if "K2Node_VariableGet" in node.node_class or "K2Node_VariableSet" in node.node_class:
            return self.state[member(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name in ("Index", "Array Index"):
                return self.loop_indices[node.name]
            if pin_name == "Array Element":
                return self.loop_elements[node.name]
            raise RuntimeError(pin_name)
        if "K2Node_GetArrayItem" in node.node_class:
            return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "Subtract_IntInt":
            return int(left) - int(right)
        if name == "Multiply_DoubleDouble":
            return left * right
        if name == "FMin":
            return min(left, right)
        if name == "Greater_IntInt":
            return int(left) > int(right)
        if name in ("EqualEqual_IntInt", "EqualEqual_DoubleDouble", "EqualEqual_BoolBool"):
            return left == right
        if name == "BooleanAND":
            return bool(left) and bool(right)
        raise RuntimeError(f"unsupported pure {node.name}:{name}:{pin_name}")

    def next_target(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec", "Execute", "Break"):
                return target[0], target[1].name
        return None

    def invoke(self, name):
        self.calls.append(name)
        sample_index = int(self.state.get(INDEX, -1))
        orientation = self.modules["orientation"]
        if name == "CompileOrientationTrackV1":
            if self.failures.get("compile"):
                self.state["OrientationTrackCompileValidV1"] = False
                return
            try:
                track = orientation.compile_orientation_track(
                    tuple(self.state["OrientationTrackInputWaypointQuatsV1"]),
                    tuple(self.state["OrientationTrackInputDurationsV1"]),
                )
            except Exception:
                self.state["OrientationTrackCompileValidV1"] = False
                return
            self.state["__orientation_track__"] = track
            self.state["OrientationTrackCompiledTotalSecondsV1"] = track.total_seconds
            self.state["OrientationTrackCompiledDurationsV1"] = [segment.duration_seconds for segment in track.segments]
            self.state["OrientationTrackCompiledSegmentStartsV1"] = [segment.start_seconds for segment in track.segments]
            self.state["OrientationTrackCompileValidV1"] = True
            for key, value in self.timeline_mutation.items():
                self.state[key] = copy.deepcopy(value)
            return
        if name == "EvaluateCompiledPositionRouteV1":
            if self.failures.get("position") == sample_index:
                self.state["PositionRouteResultValidV1"] = False
                return
            try:
                result = self.modules["cinematic"].evaluate_position(
                    self.state["__position_track__"], self.state["PositionRouteInputElapsedSecondsV1"]
                )
            except Exception:
                self.state["PositionRouteResultValidV1"] = False
                return
            self.state.update({
                "PositionRouteResultSegmentIndexV1": result.segment_index,
                "PositionRouteResultLocalTimeAlphaV1": result.local_time_alpha,
                "PositionRouteResultPositionV1": result.position,
                "PositionRouteResultCompleteV1": result.complete,
                "PositionRouteResultValidV1": True,
            })
            return
        if name == "EvaluateCompiledOrientationTrackV1":
            if self.failures.get("orientation") == sample_index:
                self.state["OrientationTrackResultValidV1"] = False
                return
            try:
                result = orientation.evaluate_orientation(
                    self.state["__orientation_track__"], self.state["OrientationTrackInputElapsedSecondsV1"]
                )
            except Exception:
                self.state["OrientationTrackResultValidV1"] = False
                return
            self.state.update({
                "OrientationTrackResultSegmentIndexV1": result.segment_index,
                "OrientationTrackResultAlphaV1": result.alpha,
                "OrientationTrackResultQuatV1": result.rotation,
                "OrientationTrackResultCompleteV1": result.complete,
                "OrientationTrackResultValidV1": result.valid,
            })
            mismatch = self.failures.get("agreement")
            if mismatch == sample_index:
                self.state["OrientationTrackResultAlphaV1"] += 0.125
            return
        if name == "EvaluateSmoothedFlightProfileV1":
            if self.failures.get("profile") == sample_index:
                self.state["SmoothedFlightProfileResultValidV1"] = False
                return
            try:
                result = self.modules["smoothed"].evaluate_smoothed_flight_profile(
                    self.state["__profile_track__"],
                    self.state["SmoothedFlightProfileInputSegmentIndexV1"],
                    self.state["SmoothedFlightProfileInputLocalTimeAlphaV1"],
                )
            except Exception:
                self.state["SmoothedFlightProfileResultValidV1"] = False
                return
            for field, attribute, _candidate in PROFILE:
                self.state[f"SmoothedFlightProfileResult{field}V1"] = getattr(result.parameters, attribute)
            self.state["SmoothedFlightProfileResultValidV1"] = True
            return
        raise RuntimeError(name)

    def execute_chain(self, current, enclosing_loop=None):
        while current is not None:
            name = member(current)
            if "K2Node_VariableSet" in current.node_class:
                value = self.value(current, name)
                if 'PinType.ContainerType=Array' in current.pins[name].body:
                    value = list(value)
                self.state[name] = value
                self.cache.clear()
                target = self.next_target(current)
            elif name == "Array_Clear":
                source = self.source(current, "TargetArray")
                self.state[member(source[0])] = []
                self.cache.clear()
                target = self.next_target(current)
            elif name == "Array_Add":
                source = self.source(current, "TargetArray")
                self.state[member(source[0])].append(self.value(current, "NewItem"))
                self.cache.clear()
                target = self.next_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                target = self.next_target(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                if "Array" in current.pins:
                    values = list(self.value(current, "Array"))
                    body = self.next_target(current, "LoopBody")
                    for index, value in enumerate(values):
                        self.loop_indices[current.name] = index
                        self.loop_elements[current.name] = value
                        self.cache.clear()
                        if body:
                            self.execute_chain(body[0], current)
                    target = self.next_target(current, "Completed")
                else:
                    first = int(self.value(current, "FirstIndex"))
                    last = int(self.value(current, "LastIndex"))
                    body = self.next_target(current, "LoopBody")
                    for index in range(first, last + 1):
                        self.loop_indices[current.name] = index
                        self.cache.clear()
                        if body and self.execute_chain(body[0], current):
                            break
                    target = self.next_target(current, "Completed")
            elif "K2Node_CallFunction" in current.node_class and name in CALLS:
                self.invoke(name)
                self.cache.clear()
                target = self.next_target(current)
            else:
                raise RuntimeError(f"unsupported exec {current.name}:{name}")
            if target is None:
                return False
            if enclosing_loop is not None and target[0] is enclosing_loop and target[1] == "Break":
                return True
            current = target[0]
        return False

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            start = self.next_target(entries[0])[0]
        else:
            start = next(node for node in self.nodes.values() if member(node) == "Array_Clear" and not node.pins["execute"].links)
        self.execute_chain(start)
        return self.state


def yaw(degrees):
    half = math.radians(degrees) * 0.5
    return 0.0, 0.0, math.sin(half), math.cos(half)


def make_case(modules, durations=(0.4, 0.6), step=0.3, overrides=None, seed=0):
    rng = random.Random(0xEDD5300 + seed)
    elapsed = 0.0
    origin = (rng.uniform(-10.0, 10.0), rng.uniform(-10.0, 10.0), rng.uniform(-3.0, 3.0))
    velocity = (rng.uniform(20.0, 60.0), rng.uniform(-8.0, 8.0), rng.uniform(-2.0, 2.0))
    points = [origin]
    for duration in durations:
        elapsed += duration
        points.append(tuple(origin[axis] + velocity[axis] * elapsed for axis in range(3)))
    segments = tuple(modules["cinematic"].AuthoredSegment(value, "linear", "linear") for value in durations)
    position = modules["cinematic"].compile_trajectory(tuple(points), segments)
    authored_body = tuple(yaw(index * 11.0 + seed * 0.25) for index in range(len(points)))
    body = modules["orientation"].compile_orientation_track(authored_body, tuple(durations))
    override_values = tuple(overrides) if overrides is not None else ("",) * len(durations)
    profiles = modules["profiles"].compile_flight_profiles("cinematic_drone", override_values, len(durations))
    times = modules["prebake"].fixed_sample_times(position.total_seconds, step)
    state = {
        STAGE: True,
        INDEX: 991,
        TOTAL: position.total_seconds,
        STEP: step,
        "AirframeSourceExpectedSampleCountV1": len(times),
        "AirframeSourceSampleElapsedSecondsV1": 991.0,
        "AirframeSourceInputBodyWaypointQuatsV1": list(authored_body),
        "PositionRouteInputDurationsV1": list(durations),
        "PositionRouteCompiledTotalSecondsV1": position.total_seconds,
        "PositionRouteCompiledDurationsV1": [segment.duration_seconds for segment in position.segments],
        "PositionRouteCompiledSegmentStartsV1": [segment.start_seconds for segment in position.segments],
        "PositionRouteInputElapsedSecondsV1": 991.0,
        "PositionRouteResultValidV1": False,
        "OrientationTrackInputWaypointQuatsV1": ["poison"],
        "OrientationTrackInputDurationsV1": ["poison"],
        "OrientationTrackCompileValidV1": False,
        "OrientationTrackCompiledTotalSecondsV1": 991.0,
        "OrientationTrackCompiledDurationsV1": [991.0],
        "OrientationTrackCompiledSegmentStartsV1": [991.0],
        "OrientationTrackInputElapsedSecondsV1": 991.0,
        "OrientationTrackResultValidV1": False,
        "SmoothedFlightProfileInputSegmentIndexV1": -991,
        "SmoothedFlightProfileInputLocalTimeAlphaV1": 991.0,
        "SmoothedFlightProfileResultValidV1": False,
        "__position_track__": position,
        "__profile_track__": profiles,
    }
    for name, _kind in OUTPUTS:
        state[name] = ["poison", "poison"]
    return state, position, body, profiles, times


def expected(modules, position, body, profiles, times):
    result = {name: [] for name, _kind in OUTPUTS}
    for elapsed in times:
        position_value = modules["cinematic"].evaluate_position(position, elapsed)
        body_value = modules["orientation"].evaluate_orientation(body, elapsed)
        profile_value = modules["smoothed"].evaluate_smoothed_flight_profile(
            profiles, position_value.segment_index, position_value.local_time_alpha
        )
        result["AirframeSourceCandidatePositionsV1"].append(position_value.position)
        result["AirframeSourceCandidateBodyQuatsV1"].append(body_value.rotation)
        for _field, attribute, candidate in PROFILE:
            result[candidate].append(getattr(profile_value.parameters, attribute))
    return result


def close_nested(actual, wanted, tolerance=2e-9):
    if len(actual) != len(wanted):
        return False
    for left, right in zip(actual, wanted):
        left_values = left if isinstance(left, (tuple, list)) else (left,)
        right_values = right if isinstance(right, (tuple, list)) else (right,)
        if len(left_values) != len(right_values):
            return False
        if not all(math.isclose(float(a), float(b), rel_tol=tolerance, abs_tol=tolerance) for a, b in zip(left_values, right_values)):
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load_module(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_source_body_contract_base")
    trajectory = str(args.project_root / "tools/trajectory")
    if trajectory not in sys.path:
        sys.path.insert(0, trajectory)
    modules = {
        "cinematic": load_module(args.project_root / "tools/trajectory/cinematic_reference.py", "edd_source_body_cinematic"),
        "orientation": load_module(args.project_root / "tools/trajectory/orientation_reference.py", "orientation_reference"),
        "profiles": load_module(args.project_root / "tools/trajectory/flight_profile_reference.py", "flight_profile_reference"),
        "smoothed": load_module(args.project_root / "tools/trajectory/smoothed_flight_profile_reference.py", "smoothed_flight_profile_reference"),
        "prebake": load_module(args.project_root / "tools/trajectory/airframe_gimbal_prebake_reference.py", "airframe_gimbal_prebake_reference"),
    }
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (129 if args.paste else 130), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    contracts.require(len([node for node in nodes.values() if member(node) == "Array_Clear"]) == 12, "twelve owned clears")
    contracts.require(len([node for node in nodes.values() if member(node) == "Array_Add"]) == 12, "twelve aligned appends")
    macros = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(macros) == 2, "timeline and sample loops")
    contracts.require(sum("Array" in node.pins for node in macros) == 1, "one foreach timeline loop")
    contracts.require(sum("FirstIndex" in node.pins for node in macros) == 1, "one bounded breakable sample loop")
    for name in CALLS:
        calls = [node for node in nodes.values() if member(node) == name]
        contracts.require(len(calls) == 1 and "bSelfContext=True" in calls[0].text, f"one self call {name}")
    contracts.require(len([node for node in nodes.values() if member(node) == "FMin"]) == 1, "terminal elapsed clamp")
    contracts.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 3, "three timeline item reads")
    stage_sets = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == STAGE]
    contracts.require(len(stage_sets) == 4 and all(explicit_default(node, STAGE) == "false" for node in stage_sets), "four sticky failure writes")
    candidate_setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) in {name for name, _kind in OUTPUTS}]
    contracts.require(not candidate_setters, "candidate publication is append-only")
    text = args.graph.read_text(encoding="utf-8")
    for name in ("OrientationTrackInputWaypointQuatsV1", "OrientationTrackInputDurationsV1"):
        setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == name]
        contracts.require(len(setters) == 1 and "PinType.ContainerType=Array" in setters[0].pins[name].body, f"array staging {name}")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute forbidden")
    contracts.require("Min_DoubleDouble" not in text, "unsupported minimum identity")

    directed = [
        ((1.0,), 0.25, None),
        ((1.0,), 0.3, None),
        ((0.4, 0.6), 0.2, ("hybrid", "fpv_cinewhoop")),
        ((0.5,) * 5, 0.25, tuple(modules["profiles"].PROFILE_ORDER)),
    ]
    cases = [make_case(modules, durations, step, overrides, index) for index, (durations, step, overrides) in enumerate(directed)]
    rng = random.Random(0xEDD5307)
    for seed in range(40):
        count = rng.randint(2, 7)
        durations = tuple(rng.choice((0.2, 0.3, 0.5)) for _ in range(count - 1))
        overrides = tuple(modules["profiles"].PROFILE_ORDER[(seed + index) % 5] for index in range(count - 1))
        cases.append(make_case(modules, durations, rng.choice((0.1, 0.2)), overrides, seed + 20))
    forward = []
    for index, (state, position, body, profiles, times) in enumerate(cases):
        immutable = copy.deepcopy({key: state[key] for key in (
            "AirframeSourceInputBodyWaypointQuatsV1", "PositionRouteInputDurationsV1",
            "PositionRouteCompiledDurationsV1", "PositionRouteCompiledSegmentStartsV1",
        )})
        wanted = expected(modules, position, body, profiles, times)
        result = Interpreter(nodes, state, modules).run()
        contracts.require(result[STAGE] is True, f"valid stage {index}")
        contracts.require(result[INDEX] == len(times) - 1, f"terminal sample index {index}")
        contracts.require(result["AirframeSourceSampleElapsedSecondsV1"] == times[-1], f"terminal elapsed {index}")
        for name, _kind in OUTPUTS:
            contracts.require(close_nested(result[name], wanted[name]), f"valid output {index}:{name}")
        contracts.require({key: result[key] for key in immutable} == immutable, f"source mutation {index}")
        forward.append(tuple(tuple(result[name]) for name, _kind in OUTPUTS))
        poisoned = copy.deepcopy(state)
        for name, _kind in OUTPUTS:
            poisoned[name] = list(reversed(wanted[name])) + ["stale"]
        repeat = Interpreter(nodes, poisoned, modules).run()
        for name, _kind in OUTPUTS:
            contracts.require(close_nested(repeat[name], wanted[name]), f"poisoned repeat {index}:{name}")
    reverse = []
    for state, _position, _body, _profiles, _times in reversed(cases):
        result = Interpreter(nodes, state, modules).run()
        reverse.append(tuple(tuple(result[name]) for name, _kind in OUTPUTS))
    contracts.require(forward == list(reversed(reverse)), "forward/reverse history independence")

    base, _position, _body, _profiles, _times = make_case(modules, (0.4, 0.6), 0.2, ("hybrid", "fpv_cinewhoop"), 99)
    for label, failures, prefix in (
        ("position", {"position": 2}, 2),
        ("orientation", {"orientation": 3}, 3),
        ("agreement", {"agreement": 2}, 2),
        ("profile", {"profile": 1}, 1),
    ):
        result = Interpreter(nodes, base, modules, failures).run()
        contracts.require(result[STAGE] is False, f"{label} failure stage")
        contracts.require(all(len(result[name]) == prefix for name, _kind in OUTPUTS), f"{label} aligned prefix")
    compile_failure = Interpreter(nodes, base, modules, {"compile": True}).run()
    contracts.require(compile_failure[STAGE] is False and all(not compile_failure[name] for name, _kind in OUTPUTS), "compile rejection")
    timeline_failures = (
        {"OrientationTrackCompiledTotalSecondsV1": 9.0},
        {"OrientationTrackCompiledDurationsV1": [0.3, 0.7]},
        {"OrientationTrackCompiledSegmentStartsV1": [0.0, 0.5]},
        {"OrientationTrackCompiledDurationsV1": [1.0]},
    )
    for index, mutation in enumerate(timeline_failures):
        result = Interpreter(nodes, base, modules, timeline_mutation=mutation).run()
        contracts.require(result[STAGE] is False and all(not result[name] for name, _kind in OUTPUTS), f"timeline rejection {index}")
    guarded = copy.deepcopy(base)
    guarded[STAGE] = False
    guarded["AirframeSourceInputBodyWaypointQuatsV1"] = object()
    result = Interpreter(nodes, guarded, modules).run()
    contracts.require(result[STAGE] is False and all(not result[name] for name, _kind in OUTPUTS), "false-stage clear-only guard")
    print(f"Airframe source position/body/profile contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} valid, poisoned repeats, helper/timeline failures")


if __name__ == "__main__":
    main()
