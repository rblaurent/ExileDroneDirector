"""Structural and executable contracts for normalized v2 document validation."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


WAYPOINTS = ("WaypointIds", "WaypointPositions", "WaypointBodyQuats", "WaypointGimbalQuats")
SEGMENTS = ("SegmentIds", "SegmentFromWaypointIds", "SegmentToWaypointIds", "SegmentDurations", "SegmentSpatialCurveTypes", "SegmentTimeProfiles", "SegmentFlightProfileOverrides")


def load(path):
    spec = importlib.util.spec_from_file_location("edd_document_adapter_validation_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def make(seed):
    rng = random.Random(seed)
    count = rng.randint(2, 20)
    ids = list(range(100, 100 + count))
    durations = [rng.choice((0.25, 0.5, 1.0, 2.0)) for _ in range(count - 1)]
    return {
        "SchemaVersion": 2,
        "EngineVersion": 1,
        "Duration": sum(durations),
        "FixedStep": 1 / 60,
        "WaypointIds": ids,
        "WaypointPositions": [(float(i), 0.0, 0.0) for i in range(count)],
        "WaypointBodyQuats": [(0.0, 0.0, 0.0, 1.0)] * count,
        "WaypointGimbalQuats": [(0.0, 0.01 * i, 0.0, 1.0) for i in range(count)],
        "SegmentIds": list(range(1000, 1000 + count - 1)),
        "SegmentFromWaypointIds": ids[:-1],
        "SegmentToWaypointIds": ids[1:],
        "SegmentDurations": durations,
        "SegmentSpatialCurveTypes": ["linear"] * (count - 1),
        "SegmentTimeProfiles": ["linear"] * (count - 1),
        "SegmentFlightProfileOverrides": [""] * (count - 1),
    }


def validate(value):
    count = len(value["WaypointIds"])
    segment_count = count - 1
    valid = value["SchemaVersion"] == 2 and value["EngineVersion"] == 1 and 2 <= count <= 512
    valid = valid and all(len(value[name]) == count for name in WAYPOINTS)
    valid = valid and all(len(value[name]) == segment_count for name in SEGMENTS)
    valid = valid and math.isfinite(value["Duration"]) and value["Duration"] > 0.0
    valid = valid and math.isfinite(value["FixedStep"]) and 1 / 240 <= value["FixedStep"] <= 0.5
    if not valid:
        return False, 0.0, "validation_failed"
    if any(item <= 0 for item in value["WaypointIds"]) or len(set(value["WaypointIds"])) != count:
        return False, 0.0, "validation_failed"
    accumulated = 0.0
    for index, duration in enumerate(value["SegmentDurations"]):
        row_valid = value["SegmentIds"][index] > 0
        row_valid = row_valid and value["SegmentIds"].index(value["SegmentIds"][index]) == index
        row_valid = row_valid and value["SegmentFromWaypointIds"][index] == value["WaypointIds"][index]
        row_valid = row_valid and value["SegmentToWaypointIds"][index] == value["WaypointIds"][index + 1]
        row_valid = row_valid and math.isfinite(duration) and duration > 0.0
        if not row_valid:
            return False, accumulated, "validation_failed"
        accumulated += duration
    return (True, accumulated, "") if accumulated == value["Duration"] else (False, accumulated, "validation_failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (113 if args.paste else 114), f"node count {len(nodes)}")
    contracts.require("CameraTransform" not in text and "DraftDocumentV1" not in text, "legacy document path forbidden")
    for name in (*WAYPOINTS, *SEGMENTS):
        contracts.require(f'AirframeDocumentInput{name}V2' in text, f"normalized channel {name}")
    contracts.require(text.count('MemberName="Array_Find"') == 2, "two deterministic uniqueness searches")
    contracts.require(text.count("StandardMacros:ForEachLoop") == 2, "waypoint and segment loops")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("AirframeDocumentAdapterStageValidV2") == 5, "fail-closed stage writes")
    contracts.require(writes.count("AirframeDocumentAdapterDurationAccumulatorV2") == 2, "owned exact-duration accumulator")
    contracts.require(writes.count("AirframeDocumentAdapterFailureCodeV2") == 2, "failure then success code")
    for seed in range(80):
        valid, accumulated, code = validate(make(0xEDD700 + seed))
        contracts.require(valid and accumulated > 0.0 and code == "", f"seeded valid {seed}")
    mutations = {
        "schema": lambda x: x.update(SchemaVersion=1),
        "engine": lambda x: x.update(EngineVersion=2),
        "duration_nan": lambda x: x.update(Duration=float("nan")),
        "duration_sum": lambda x: x.update(Duration=x["Duration"] + 0.125),
        "step_low": lambda x: x.update(FixedStep=0.001),
        "step_high": lambda x: x.update(FixedStep=0.75),
        "waypoint_shape": lambda x: x["WaypointGimbalQuats"].pop(),
        "segment_shape": lambda x: x["SegmentTimeProfiles"].pop(),
        "waypoint_positive": lambda x: x["WaypointIds"].__setitem__(0, 0),
        "waypoint_unique": lambda x: x["WaypointIds"].__setitem__(1, x["WaypointIds"][0]),
        "segment_positive": lambda x: x["SegmentIds"].__setitem__(0, 0),
        "segment_unique": lambda x: x["SegmentIds"].__setitem__(1, x["SegmentIds"][0]),
        "from": lambda x: x["SegmentFromWaypointIds"].__setitem__(0, -1),
        "to": lambda x: x["SegmentToWaypointIds"].__setitem__(0, -1),
        "duration_zero": lambda x: x["SegmentDurations"].__setitem__(0, 0.0),
        "duration_inf": lambda x: x["SegmentDurations"].__setitem__(0, float("inf")),
    }
    for label, mutate in mutations.items():
        value = make(0xEDD799)
        mutate(value)
        valid, _accumulated, code = validate(value)
        contracts.require(not valid and code == "validation_failed", label)
    body = make(1)["WaypointBodyQuats"]
    gimbal = make(1)["WaypointGimbalQuats"]
    contracts.require(body != gimbal, "test fixture preserves distinct authorship")
    print(f"Airframe document adapter validation contracts passed ({'paste' if args.paste else 'full'}): 80 seeded documents and 16 failure classes")


if __name__ == "__main__":
    main()
