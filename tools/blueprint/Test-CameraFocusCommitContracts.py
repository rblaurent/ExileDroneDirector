"""Atomic publication contracts for the complete focus-distance snapshot."""
from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from copy import deepcopy
from pathlib import Path


MODES = ("manual_distance", "fixed_world", "rack_fixed", "track_prebaked", "smoothed_autofocus")
READS = {"CameraFocusCandidateValidV1", "CameraFocusInputTimesSecondsV1", "CameraFocusCandidateDistancesCmV1", "CameraFocusInputModeV1", "CameraFocusInputDomainV1"}
WRITES = {"CameraFocusCompiledTimesSecondsV1", "CameraFocusCompiledDistancesCmV1", "CameraFocusCompiledModeV1", "CameraFocusCompiledDomainV1", "CameraFocusCompileValidV1", "CameraFocusFailureCodeV1"}
FORBIDDEN = ("CameraFocusTraceHit", "CameraFocusMarker", "CameraApply", "Airframe", "Document")


def load(path):
    spec = importlib.util.spec_from_file_location("edd_camera_focus_commit_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def commit(candidate_valid, times, distances, mode, domain, prior):
    result = deepcopy(prior)
    result["valid"] = False
    result["failure"] = "commit_failed"
    ready = candidate_valid and 2 <= len(times) <= 65536 and len(times) == len(distances) and mode in MODES and domain in ("linear", "reciprocal")
    if ready:
        result.update(times=list(times), distances=list(distances), mode=mode, domain=domain, failure="", valid=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (36 if args.paste else 37), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, "exact commit reads")
    contracts.require({member(node) for node in setters} == WRITES, "exact commit writes")
    contracts.require(sum(member(node) == "CameraFocusCompileValidV1" for node in setters) == 2, "validity invalidated then published")
    contracts.require(sum(member(node) == "CameraFocusFailureCodeV1" for node in setters) == 2, "failure staged then cleared")
    for name in ("CameraFocusCompiledTimesSecondsV1", "CameraFocusCompiledDistancesCmV1"):
        node = next(node for node in setters if member(node) == name)
        contracts.require("PinType.ContainerType=Array" in node.pins[name].body, f"{name} is whole-array publication")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(value in text for value in FORBIDDEN), "commit boundary isolation")
    contracts.require(sum(member(node) == "Array_Length" for node in nodes.values()) == 2, "two exact cardinalities")
    contracts.require(all(f'DefaultValue="{value}"' in text for value in (*MODES, "linear", "reciprocal")), "identity preflight")
    invalidator = next(node for node in setters if member(node) == "CameraFocusCompileValidV1" and 'DefaultValue="true"' not in node.text)
    publisher = next(node for node in setters if member(node) == "CameraFocusCompileValidV1" and 'DefaultValue="true"' in node.text)
    contracts.require(not publisher.pins["then"].links, "validity is last publication")
    if args.paste:
        contracts.require(not invalidator.pins["execute"].links, "paste root is unlinked")
    else:
        contracts.require_link(entries[0], "then", invalidator, "execute", "entry invalidates first")

    rng = random.Random(0xEDD6F3)
    prior = {"times": [0.0, 9.0], "distances": [9.0, 9.0], "mode": "manual_distance", "domain": "linear", "valid": True, "failure": "old"}
    valid_cases = 0
    for mode in MODES:
        for domain in ("linear", "reciprocal"):
            for _ in range(8):
                count = rng.randint(2, 128)
                times = [index * 0.125 for index in range(count)]
                distances = [rng.uniform(1.0, 100000.0) for _ in range(count)]
                before = (deepcopy(times), deepcopy(distances))
                result = commit(True, times, distances, mode, domain, prior)
                contracts.require(result == {"times": times, "distances": distances, "mode": mode, "domain": domain, "valid": True, "failure": ""}, "exact atomic publication")
                contracts.require((times, distances) == before and result["times"] is not times and result["distances"] is not distances, "input immutability and value snapshot")
                valid_cases += 1
    good_times = [0.0, 0.1, 0.2]
    good_distances = [100.0, 110.0, 120.0]
    failures = (
        (False, good_times, good_distances, "manual_distance", "linear"),
        (True, [0.0], [100.0], "manual_distance", "linear"),
        (True, list(range(65537)), list(range(65537)), "manual_distance", "linear"),
        (True, good_times, good_distances[:-1], "manual_distance", "linear"),
        (True, good_times, good_distances, "bad", "linear"),
        (True, good_times, good_distances, "manual_distance", "bad"),
    )
    for case in failures:
        result = commit(*case, prior)
        contracts.require(result["times"] == prior["times"] and result["distances"] == prior["distances"] and result["mode"] == prior["mode"] and result["domain"] == prior["domain"], "failure preserves compiled snapshot")
        contracts.require(not result["valid"] and result["failure"] == "commit_failed", "failure invalidates result")
    print(f"Camera focus commit contracts passed ({'paste' if args.paste else 'full'}): {valid_cases} snapshots, {len(failures)} failures")


if __name__ == "__main__":
    main()
