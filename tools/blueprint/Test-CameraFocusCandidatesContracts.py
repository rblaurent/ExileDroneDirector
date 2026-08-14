"""Structural and executable contracts for chronological focus candidates."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from copy import deepcopy
from pathlib import Path


READS = {
    "CameraFocusInputModeV1", "CameraFocusInputDomainV1", "CameraFocusInputFixedStepSecondsV1",
    "CameraFocusInputTimesSecondsV1", "CameraFocusInputCameraPositionsV1",
    "CameraFocusInputManualDistancesCmV1", "CameraFocusInputTargetPositionsV1",
    "CameraFocusInputRackTargetAV1", "CameraFocusInputRackTargetBV1",
    "CameraFocusInputRackBlendWeightsV1", "CameraFocusInputSmoothingResponseSecondsV1",
    "CameraFocusCandidateDistancesCmV1", "CameraFocusCandidateValidV1",
}
WRITES = {"CameraFocusCandidateValidV1", "CameraFocusFailureCodeV1"}
FORBIDDEN = ("CameraFocusTraceHit", "CameraFocusMarker", "CameraFocusCompiled", "CameraApply", "Airframe", "Document")
MODES = ("manual_distance", "fixed_world", "rack_fixed", "track_prebaked", "smoothed_autofocus")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def finite_vector(value):
    return len(value) == 3 and all(math.isfinite(component) for component in value)


def vector_distance(left, right):
    try:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))
    except OverflowError:
        return math.inf


def interpret(case, prior=(991.0,), stage=True, failure="validation_failed"):
    """Execute the graph's synchronous private-prefix/final-count algorithm."""
    if not stage:
        return tuple(prior), False, failure
    built = []
    failure = "candidate_failed"
    times = case["times"]
    total = times[-1]
    for index, current in enumerate(times):
        expected = min(index * case["step"], total)
        camera = case["cameras"][index]
        common = (
            math.isfinite(current) and math.isfinite(total) and current == expected
            and (index == 0 or current > times[index - 1]) and finite_vector(camera)
        )
        if not common:
            break
        mode = case["mode"]
        if mode == "manual_distance":
            value = case["manual"][index]
        elif mode == "fixed_world":
            value = vector_distance(camera, case["targets"][0])
        elif mode == "rack_fixed":
            weight = case["weights"][index]
            left = vector_distance(camera, case["rack_a"])
            right = vector_distance(camera, case["rack_b"])
            if not (math.isfinite(weight) and 0.0 <= weight <= 1.0 and math.isfinite(left) and math.isfinite(right) and left >= 1.0 and right >= 1.0):
                break
            if case["domain"] == "reciprocal":
                value = 1.0 / ((1.0 - weight) / left + weight / right)
            else:
                value = left + (right - left) * weight
        else:
            value = vector_distance(camera, case["targets"][index])
            if mode == "smoothed_autofocus" and index:
                alpha = 1.0 - math.exp(-(current - times[index - 1]) / case["response"])
                value = built[-1] + (value - built[-1]) * alpha
        if not math.isfinite(value) or value < 1.0:
            break
        built.append(value)
    valid = len(built) == len(times)
    return tuple(built), valid, "" if valid else failure


def make_case(rng, mode, domain):
    count = rng.randint(2, 18)
    # Binary-exact steps keep ceil(total / step) stable at the frozen boundary.
    step = rng.choice((0.03125, 0.0625, 0.125, 0.25))
    total = step * (count - 1)
    times = [min(index * step, total) for index in range(count)]
    cameras = [(rng.uniform(-500, 500), rng.uniform(-500, 500), rng.uniform(-500, 500)) for _ in times]
    case = {
        "mode": mode, "domain": domain, "step": step, "times": times, "cameras": cameras,
        "manual": [], "targets": [], "rack_a": (900.0, -300.0, 100.0),
        "rack_b": (-700.0, 800.0, 300.0), "weights": [], "response": 0.0,
    }
    if mode == "manual_distance":
        case["manual"] = [rng.uniform(10, 5000) for _ in times]
    elif mode == "fixed_world":
        case["targets"] = [(1200.0, 400.0, -100.0)]
    elif mode == "rack_fixed":
        case["weights"] = [index / (count - 1) for index in range(count)]
    else:
        case["targets"] = [(1000.0 + index * 20.0, 500.0 - index * 9.0, 250.0) for index in range(count)]
        if mode == "smoothed_autofocus":
            case["response"] = rng.uniform(0.05, 1.5)
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_focus_candidate_graph_contracts")
    reference = load(args.project_root / "tools/trajectory/camera_focus_helper_reference.py", "edd_focus_candidate_reference")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (331 if args.paste else 332), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact candidate reads")
    contracts.require(setters == WRITES, "exact candidate scalar writes")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(value in text for value in FORBIDDEN), "authorship boundaries")
    for function, count in {
        "Array_Clear": 1, "Array_Add": 6, "Array_Length": 6, "Vector_Distance": 5,
        "BreakVector": 5, "Exp": 1, "FMin": 5, "SelectInt": 5,
    }.items():
        contracts.require(sum(member(node) == function for node in nodes.values()) == count, f"{count} {function} nodes")
    loops = [node for node in nodes.values() if "ForLoopWithBreak" in node.text]
    contracts.require(len(loops) == 5, "one bounded loop per exclusive mode")
    contracts.require(text.count('DefaultValue="candidate_failed"') == 1, "bounded private-prefix failure")
    contracts.require(text.count('DefaultValue="true"') >= 5, "success published after five completion checks")
    if not args.paste:
        invalidators = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == "CameraFocusCandidateValidV1" and 'DefaultValue="true"' not in node.text]
        contracts.require(len(invalidators) == 1, "one initial invalidation")
        contracts.require(any(any(link[0] == entries[0].name for link in node.pins["execute"].links) for node in nodes.values() if "K2Node_IfThenElse" in node.node_class), "native entry reaches stage guard")

    rng = random.Random(0xEDD6F2)
    valid_cases = [make_case(rng, mode, domain) for mode in MODES for domain in ("linear", "reciprocal") for _ in range(8)]
    for case in valid_cases:
        before = deepcopy(case)
        built, valid, failure = interpret(case)
        expected = reference.compile_focus_distance_samples_v1(
            case["mode"], case["domain"], case["times"], case["step"], case["cameras"],
            manual_distances_cm=case["manual"], target_positions=case["targets"],
            rack_target_a=case["rack_a"], rack_target_b=case["rack_b"],
            rack_blend_weights=case["weights"], smoothing_response_seconds=case["response"],
        )
        contracts.require(valid and failure == "" and len(built) == len(case["times"]), "valid publication")
        contracts.require(all(abs(left - right) <= 1e-9 * max(1.0, abs(left), abs(right)) for left, right in zip(built, expected.distances_cm)), "reference-equivalent candidates")
        contracts.require(case == before, "authored input immutability")

    base = make_case(rng, "manual_distance", "linear")
    failures = []
    def poison(edit):
        case = deepcopy(base); edit(case); failures.append(case)
    poison(lambda case: case["times"].__setitem__(1, math.nan))
    poison(lambda case: case["times"].__setitem__(1, case["times"][0]))
    poison(lambda case: case["times"].__setitem__(1, case["times"][1] + 0.001))
    poison(lambda case: case["cameras"].__setitem__(1, (math.inf, 0.0, 0.0)))
    poison(lambda case: case["manual"].__setitem__(1, math.nan))
    poison(lambda case: case["manual"].__setitem__(1, 0.5))
    rack = make_case(rng, "rack_fixed", "reciprocal"); rack["weights"][1] = 1.1; failures.append(rack)
    rack = make_case(rng, "rack_fixed", "linear"); rack["weights"][1] = math.nan; failures.append(rack)
    track = make_case(rng, "track_prebaked", "linear"); track["targets"][1] = track["cameras"][1]; failures.append(track)
    fixed = make_case(rng, "fixed_world", "linear"); fixed["targets"][0] = fixed["cameras"][0]; failures.append(fixed)
    smooth = make_case(rng, "smoothed_autofocus", "linear"); smooth["targets"][2] = (math.nan, 0.0, 0.0); failures.append(smooth)
    for case in failures:
        before = deepcopy(case)
        built, valid, failure = interpret(case)
        contracts.require(not valid and failure == "candidate_failed" and len(built) < len(case["times"]), "failure leaves bounded private prefix")
        contracts.require(case == before, "failure input immutability")
    untouched = interpret(base, prior=(17.0, 19.0), stage=False, failure="validation_failed")
    contracts.require(untouched == ((17.0, 19.0), False, "validation_failed"), "invalid preflight is a zero-mutation no-op")
    print(f"Camera focus candidate contracts passed ({'paste' if args.paste else 'full'}): {len(valid_cases)} valid, {len(failures)} failures")


if __name__ == "__main__":
    main()
