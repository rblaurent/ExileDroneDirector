"""Structural and executable contracts for carrier-frame staged-input validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CarrierFrameInputPositionsV1",
    "CarrierFrameInputTotalSecondsV1",
    "CarrierFrameInputFixedStepSecondsV1",
    "CarrierFrameStageValidV1",
    "CarrierFrameScratchValidV1",
    "CarrierFrameScratchForwardV1",
}
WRITES = {
    "CarrierFrameScratchValidV1",
    "CarrierFrameScratchForwardV1",
    "CarrierFrameFailureCodeV1",
}
FORBIDDEN = (
    "AirframeDesired",
    "AuthoredBody",
    "AuthoredGimbal",
    "CameraTransform",
    "CarrierFrameCandidate",
    "CarrierFrameCompiled",
    "CarrierFrameResult",
    "CameraOperator",
    "PlaybackTime",
    "Event",
    "Repository",
    "Server",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_validation_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, pin_name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
    return "" if match is None else match.group(1)


def validate(state: dict) -> tuple[bool, str]:
    """Execute the graph's frozen validation phases against a value snapshot."""
    scratch_valid = False
    failure = ""
    positions = state["CarrierFrameInputPositionsV1"]
    total = state["CarrierFrameInputTotalSecondsV1"]
    step = state["CarrierFrameInputFixedStepSecondsV1"]
    numeric = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    count = len(positions) if isinstance(positions, (tuple, list)) else -1
    shape_valid = (
        state["CarrierFrameStageValidV1"] is True
        and 2 <= count <= 65536
        and numeric(total) and 0.0 < float(total) <= 3600.0
        and numeric(step) and 1.0 / 240.0 <= float(step) <= 0.5
        and (count - 2) * float(step) < float(total) <= (count - 1) * float(step)
    )
    if not shape_valid:
        return scratch_valid, "input_invalid"

    scratch_valid = True
    for position in positions:
        if not isinstance(position, (tuple, list)) or len(position) != 3 or not all(numeric(component) for component in position):
            scratch_valid = False
            failure = "position_not_finite"
    if not scratch_valid:
        return False, failure

    first = positions[0]
    scratch_valid = False
    for position in positions:
        squared = sum((float(component) - float(origin)) ** 2 for component, origin in zip(position, first))
        if squared > 1.0e-18:
            scratch_valid = True
    if not scratch_valid:
        return False, "path_has_no_direction"
    return True, ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (73 if args.paste else 74), f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "validation entry count")
    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in getters} == READS, "exact validation reads")
    contracts.require({member(node) for node in setters} == WRITES, "exact validation writes")
    contracts.require(sum(member(node) == "CarrierFrameScratchValidV1" for node in setters) == 6, "scratch validity phase count")
    contracts.require(sum(member(node) == "CarrierFrameFailureCodeV1" for node in setters) == 5, "diagnostic phase count")
    contracts.require(sum(member(node) == "CarrierFrameScratchForwardV1" for node in setters) == 1, "first-position scratch count")

    functions = [
        member(node) for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class or "K2Node_CallArrayFunction" in node.node_class
    ]
    for name, expected in {
        "Array_Length": 1,
        "BreakVector": 1,
        "Conv_IntToDouble": 2,
        "Subtract_VectorVector": 1,
        "Dot_VectorVector": 1,
    }.items():
        contracts.require(functions.count(name) == expected, f"{name} count")
    contracts.require(sum("K2Node_MacroInstance" in node.node_class for node in nodes.values()) == 2, "finite and direction loops")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 1, "first position read")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 5, "five validation phase branches")

    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "upstream/authored/external ownership forbidden")
    for token in (
        'DefaultValue="2"', 'DefaultValue="65536"', 'DefaultValue="3600.0"',
        'DefaultValue="0.004166666666666667"', 'DefaultValue="0.5"', 'DefaultValue="1e-18"',
        'DefaultValue="input_invalid"', 'DefaultValue="position_not_finite"',
        'DefaultValue="path_has_no_direction"',
    ):
        contracts.require(token in text, f"frozen validation token missing: {token}")

    invalidators = [node for node in setters if member(node) == "CarrierFrameScratchValidV1" and default(node, "CarrierFrameScratchValidV1") == "false"]
    publishers = [node for node in setters if member(node) == "CarrierFrameScratchValidV1" and default(node, "CarrierFrameScratchValidV1") == "true"]
    root = invalidators[0]
    publisher = publishers[-1]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry invalidates validation first")
    success_clear = next(node for node in setters if member(node) == "CarrierFrameFailureCodeV1" and default(node, "CarrierFrameFailureCodeV1") == "" and any(target == publisher.name for pin in node.pins.values() for target, _ in pin.links))
    contracts.require_link(success_clear, "then", publisher, "execute", "validation publishes success last")
    positions = next(node for node in getters if member(node) == "CarrierFrameInputPositionsV1")
    contracts.require(len(positions.pins["CarrierFrameInputPositionsV1"].links) >= 4, "positions feed length, both loops, and first item")

    randomizer = random.Random(0xCA221DA7)
    protected_names = (
        "CarrierFrameInputPositionsV1",
        "CarrierFrameInputTotalSecondsV1",
        "CarrierFrameInputFixedStepSecondsV1",
        "CarrierFrameCandidateTangentsV1",
        "CarrierFrameCompiledQuatsV1",
        "CameraOperatorInputCarrierFrameQuatV1",
    )
    valid_cases = [
        ([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)], 1.0, 0.5),
        ([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 2.0)], 1.0, 0.5),
        ([(1.0, 1.0, 1.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)], 1.0, 0.5),
        ([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)], 1.0, 0.4),
    ]
    for _index in range(80):
        count = randomizer.randint(2, 80)
        step = randomizer.uniform(1.0 / 240.0, 0.5)
        total = (count - 2 + randomizer.uniform(0.001, 1.0)) * step
        total = min(total, 3600.0)
        points = [(0.0, 0.0, 0.0)]
        for sample in range(1, count):
            if sample % 13 == 0:
                points.append(points[-1])
            else:
                points.append(tuple(value + randomizer.uniform(-10.0, 10.0) for value in points[-1]))
        valid_cases.append((points, total, step))
    for index, (points, total, step) in enumerate(valid_cases):
        state = {
            "CarrierFrameInputPositionsV1": points,
            "CarrierFrameInputTotalSecondsV1": total,
            "CarrierFrameInputFixedStepSecondsV1": step,
            "CarrierFrameStageValidV1": True,
        }
        snapshots = {name: state.get(name, object()) for name in protected_names}
        contracts.require(validate(state) == (True, ""), f"valid case {index}")
        contracts.require(all(state.get(name, snapshots[name]) is value for name, value in snapshots.items()), f"valid immutable state {index}")

    base = {
        "CarrierFrameInputPositionsV1": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        "CarrierFrameInputTotalSecondsV1": 1.0,
        "CarrierFrameInputFixedStepSecondsV1": 0.5,
        "CarrierFrameStageValidV1": True,
    }
    invalid_cases = (
        ({**base, "CarrierFrameStageValidV1": False}, "input_invalid"),
        ({**base, "CarrierFrameInputPositionsV1": base["CarrierFrameInputPositionsV1"][:1]}, "input_invalid"),
        ({**base, "CarrierFrameInputPositionsV1": [(0.0, 0.0, 0.0)] * 65537, "CarrierFrameInputTotalSecondsV1": 273.066}, "input_invalid"),
        ({**base, "CarrierFrameInputTotalSecondsV1": 0.0}, "input_invalid"),
        ({**base, "CarrierFrameInputTotalSecondsV1": math.nan}, "input_invalid"),
        ({**base, "CarrierFrameInputTotalSecondsV1": 3600.1}, "input_invalid"),
        ({**base, "CarrierFrameInputFixedStepSecondsV1": 0.0}, "input_invalid"),
        ({**base, "CarrierFrameInputFixedStepSecondsV1": math.inf}, "input_invalid"),
        ({**base, "CarrierFrameInputFixedStepSecondsV1": 0.5001}, "input_invalid"),
        ({**base, "CarrierFrameInputPositionsV1": base["CarrierFrameInputPositionsV1"][:2]}, "input_invalid"),
        ({**base, "CarrierFrameInputPositionsV1": base["CarrierFrameInputPositionsV1"] + [(3.0, 0.0, 0.0)]}, "input_invalid"),
        ({**base, "CarrierFrameInputPositionsV1": [(0.0, 0.0, 0.0), (math.nan, 0.0, 0.0), (2.0, 0.0, 0.0)]}, "position_not_finite"),
        ({**base, "CarrierFrameInputPositionsV1": [(0.0, 0.0, 0.0), (1.0, math.inf, 0.0), (2.0, 0.0, 0.0)]}, "position_not_finite"),
        ({**base, "CarrierFrameInputPositionsV1": [(1.0, 2.0, 3.0)] * 3}, "path_has_no_direction"),
    )
    for index, (state, expected) in enumerate(invalid_cases):
        before = {name: state.get(name) for name in state}
        contracts.require(validate(state) == (False, expected), f"invalid case {index}:{expected}")
        contracts.require(state == before, f"invalid state mutation {index}")
    print(f"Carrier-frame validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid_cases)} valid, {len(invalid_cases)} failures")


if __name__ == "__main__":
    main()
