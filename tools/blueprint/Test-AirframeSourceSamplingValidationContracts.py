"""Exact graph and exported-link execution contracts for source validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


ARRAYS = (
    "PositionRouteInputWaypointPositionsV1",
    "PositionRouteInputDurationsV1",
    "PositionRouteInputSpatialCurveTypesV1",
    "PositionRouteInputTimeProfilesV1",
    "AirframeSourceInputBodyWaypointQuatsV1",
    "AirframeSourceInputGimbalWaypointQuatsV1",
    "FlightProfileInputSegmentOverrideIdsV1",
)
STEP = "AirframeSourceInputFixedStepSecondsV1"
STAGE = "AirframeSourceStageValidV1"


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_validation_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def explicit_default(pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', pin.body)
    return None if match is None else match.group(1)


class Interpreter:
    """Evaluate the actual exported links; no parallel validation shortcut."""

    def __init__(self, nodes, state):
        self.nodes = nodes
        self.state = dict(state)
        self.pin_owner = {}
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
        text = explicit_default(node.pins[pin_name])
        if text in ("true", "false"):
            return text == "true"
        if text is None:
            body = node.pins[pin_name].body
            if 'PinType.PinCategory="int"' in body:
                return 0
            if 'PinType.PinCategory="real"' in body:
                return 0.0
            if 'PinType.PinCategory="bool"' in body:
                return False
            return ""
        try:
            return float(text)
        except ValueError:
            return text

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[member(node)]
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name in ("GreaterEqual_IntInt", "GreaterEqual_DoubleDouble"):
            return left >= right
        if name in ("LessEqual_IntInt", "LessEqual_DoubleDouble"):
            return left <= right
        if name == "EqualEqual_IntInt":
            return left == right
        if name == "Subtract_IntInt":
            return int(left) - int(right)
        raise RuntimeError(f"unsupported value node {node.name}:{name}:{pin_name}")

    def next(self, node, pin_name="then"):
        if pin_name not in node.pins:
            return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner[link]
            if target[1].name in ("execute", "Exec"):
                return target[0]
        return None

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.next(entries[0])
        else:
            setters = [node for node in self.nodes.values() if "K2Node_VariableSet" in node.node_class]
            current = next(node for node in setters if not node.pins["execute"].links)
        while current is not None:
            if "K2Node_VariableSet" in current.node_class:
                self.state[member(current)] = self.value(current, member(current))
                current = self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next(current, "then" if self.value(current, "Condition") else "else")
            else:
                raise RuntimeError(f"unsupported exec node {current.name}:{member(current)}")
        return self.state[STAGE]


def make_case(count=3, step=1.0 / 60.0):
    segment_count = count - 1
    return {
        ARRAYS[0]: [(float(index), 0.0, 0.0) for index in range(count)],
        ARRAYS[1]: [1.0] * segment_count,
        ARRAYS[2]: ["cinematic"] * segment_count,
        ARRAYS[3]: ["ease"] * segment_count,
        ARRAYS[4]: [(0.0, 0.0, 0.0, 1.0)] * count,
        ARRAYS[5]: [(0.0, 0.0, 0.0, 1.0)] * count,
        ARRAYS[6]: [""] * segment_count,
        STEP: step,
    }


def clone(case):
    return {key: list(value) if isinstance(value, list) else value for key, value in case.items()}


def validates(case):
    count = len(case[ARRAYS[0]])
    segment_count = count - 1
    return (
        2 <= count <= 512
        and len(case[ARRAYS[1]]) == segment_count
        and len(case[ARRAYS[2]]) == segment_count
        and len(case[ARRAYS[3]]) == segment_count
        and len(case[ARRAYS[4]]) == count
        and len(case[ARRAYS[5]]) == count
        and len(case[ARRAYS[6]]) == segment_count
        and not isinstance(case[STEP], bool)
        and isinstance(case[STEP], (int, float))
        and math.isfinite(float(case[STEP]))
        and 1.0 / 240.0 <= float(case[STEP]) <= 0.5
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (42 if args.paste else 43), f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    lengths = [node for node in nodes.values() if 'MemberName="Array_Length"' in node.text]
    contracts.require(len(lengths) == 7, "every authored array cardinality must be measured")
    for name in ARRAYS:
        getter = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and f'MemberName="{name}"' in node.text)
        length = next((node for node in lengths if any(target == getter.name for pin in node.pins.values() for target, _pin in pin.links)), None)
        contracts.require(length is not None, f"{name} length missing")
        contracts.require_link(getter, name, length, "TargetArray", f"{name} length link changed")
    step_getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and f'MemberName="{STEP}"' in node.text]
    contracts.require(len(step_getters) == 1, "fixed-step getter count")
    contracts.require('PinType.ContainerType=None' in step_getters[0].pins[STEP].body, "fixed step must be scalar")
    contracts.require(len([node for node in nodes.values() if 'MemberName="EqualEqual_IntInt"' in node.text]) == 6, "shape equality count")
    contracts.require(len([node for node in nodes.values() if 'MemberName="Subtract_IntInt"' in node.text]) == 1, "segment derivation count")
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(len(setters) == 2 and all(f'MemberName="{STAGE}"' in node.text for node in setters), "validation may write only stage validity")
    contracts.require(sorted(explicit_default(node.pins[STAGE]) for node in setters) == ["false", "true"], "stage defaults")
    text = args.graph.read_text(encoding="utf-8")
    for bound in ("2", "512", "0.004166666666666667", "0.5", "-1.7976931348623157e+308", "1.7976931348623157e+308"):
        contracts.require(f'DefaultValue="{bound}"' in text, f"bound {bound} missing")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knot forbidden")

    directed = [make_case(2, 1.0 / 240.0), make_case(512, 0.5), make_case(7, 0.1)]
    rng = random.Random(0xEDD5012)
    valid = directed + [make_case(rng.randint(2, 512), rng.uniform(1.0 / 240.0, 0.5)) for _ in range(100)]
    contracts.require(all(validates(case) for case in valid), "reference valid family")
    for index, case in enumerate(valid):
        contracts.require(Interpreter(nodes, case).run() is True, f"valid executable case {index}")

    invalid = []
    for count in (0, 1, 513):
        invalid.append(make_case(max(count, 1)) if count else {**make_case(2), ARRAYS[0]: [], ARRAYS[4]: [], ARRAYS[5]: []})
    base = make_case(5)
    for name in ARRAYS[1:]:
        case = clone(base)
        case[name] = case[name][:-1]
        invalid.append(case)
    for step in (0.0, 1.0 / 241.0, 0.500001, math.nan, math.inf, -math.inf):
        case = clone(base)
        case[STEP] = step
        invalid.append(case)
    contracts.require(all(not validates(case) for case in invalid), "reference invalid family")
    for index, case in enumerate(invalid):
        contracts.require(Interpreter(nodes, case).run() is False, f"invalid executable case {index}")
    print(f"Airframe source validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid)} valid, {len(invalid)} invalid")


if __name__ == "__main__":
    main()
