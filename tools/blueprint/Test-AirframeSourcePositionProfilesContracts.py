"""Exported-link contracts for position/profile compilation and schedule staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


STAGE = "AirframeSourceStageValidV1"
TOTAL_RESULT = "AirframeSourceTotalSecondsV1"
COUNT_RESULT = "AirframeSourceExpectedSampleCountV1"


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_components_contract_base", path)
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
    def __init__(self, nodes, state):
        self.nodes = nodes
        self.state = dict(state)
        self.pin_owner = {}
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
        if "K2Node_Select" in node.node_class:
            return self.value(node, "Option 1" if self.value(node, "Index") else "Option 0")
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "FFloor":
            return math.floor(self.value(node, "A"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name == "Divide_DoubleDouble":
            return left / right
        if name == "Multiply_DoubleDouble":
            return left * right
        if name == "Add_IntInt":
            return int(left) + int(right)
        if name in ("Greater_DoubleDouble",):
            return left > right
        if name in ("Less_DoubleDouble",):
            return left < right
        if name in ("GreaterEqual_IntInt", "GreaterEqual_DoubleDouble"):
            return left >= right
        if name in ("LessEqual_IntInt", "LessEqual_DoubleDouble"):
            return left <= right
        if name == "EqualEqual_IntInt":
            return left == right
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
            current = next(node for node in self.nodes.values() if "K2Node_IfThenElse" in node.node_class and not node.pins["execute"].links)
        while current is not None:
            name = member(current)
            if "K2Node_VariableSet" in current.node_class:
                self.state[name] = self.value(current, name)
                current = self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_CallFunction" in current.node_class and name in ("CompilePositionRouteV1", "CompileFlightProfilesV1"):
                self.calls.append(name)
                if name == "CompilePositionRouteV1":
                    self.state["PositionRouteCompileValidV1"] = self.state["__position_call_result__"]
                else:
                    self.state["FlightProfileCompileValidV1"] = self.state["__profile_call_result__"]
                current = self.next(current)
            else:
                raise RuntimeError(f"unsupported exec node {current.name}:{name}")
        return self.state


def make_case(total=1.0, step=0.25, segments=2):
    return {
        STAGE: True,
        TOTAL_RESULT: 91.0,
        COUNT_RESULT: 91,
        "PositionRouteInputDurationsV1": [total / segments] * segments,
        "PositionRouteCompileValidV1": False,
        "FlightProfileCompileValidV1": False,
        "PositionRouteCompiledTotalSecondsV1": total,
        "AirframeSourceInputFixedStepSecondsV1": step,
        "PositionRouteCompiledDurationsV1": [total / segments] * segments,
        "FlightProfileCompiledIdsV1": ["hybrid"] * segments,
        "FlightProfileInputSegmentCountV1": 91,
        "__position_call_result__": True,
        "__profile_call_result__": True,
    }


def expected_count(total, step):
    return math.ceil(total / step) + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (43 if args.paste else 44), f"component node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    for function in ("CompilePositionRouteV1", "CompileFlightProfilesV1"):
        calls = [node for node in nodes.values() if f'MemberName="{function}"' in node.text]
        contracts.require(len(calls) == 1 and 'bSelfContext=True' in calls[0].text, f"{function} call boundary")
    contracts.require(len([node for node in nodes.values() if 'MemberName="FFloor"' in node.text]) == 1, "one schedule floor")
    contracts.require(len([node for node in nodes.values() if "K2Node_Select" in node.node_class]) == 1, "one partial-terminal selection")
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in setters} == {
        STAGE, "FlightProfileInputSegmentCountV1", TOTAL_RESULT, COUNT_RESULT,
    }, "write boundary changed")
    contracts.require(sum(member(node) == STAGE for node in setters) == 2, "stage invalidation/publication count")
    text = args.graph.read_text(encoding="utf-8")
    for value in ("3600.0", "65536", "-1.7976931348623157e+308", "1.7976931348623157e+308"):
        contracts.require(f'DefaultValue="{value}"' in text, f"bound {value} missing")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knot forbidden")

    valid = [
        make_case(1.0, 0.25),
        make_case(1.0, 0.3),
        make_case(0.5, 0.5, 1),
        make_case(273.0625, 1.0 / 240.0, 5),
        make_case(3600.0, 0.5, 3),
    ]
    rng = random.Random(0xEDD5023)
    for _ in range(100):
        step = rng.uniform(1.0 / 240.0, 0.5)
        total = rng.uniform(step * 0.05, min(3600.0, step * 65000.0))
        valid.append(make_case(total, step, rng.randint(1, 12)))
    for index, case in enumerate(valid):
        result = Interpreter(nodes, case)
        state = result.run()
        contracts.require(result.calls == ["CompilePositionRouteV1", "CompileFlightProfilesV1"], f"valid call order {index}")
        contracts.require(state[STAGE] is True, f"valid stage {index}")
        contracts.require(state[TOTAL_RESULT] == case["PositionRouteCompiledTotalSecondsV1"], f"valid total {index}")
        contracts.require(state[COUNT_RESULT] == expected_count(case["PositionRouteCompiledTotalSecondsV1"], case["AirframeSourceInputFixedStepSecondsV1"]), f"valid count {index}")
        contracts.require(state["FlightProfileInputSegmentCountV1"] == len(case["PositionRouteInputDurationsV1"]), f"segment count staging {index}")

    false_stage = make_case()
    false_stage[STAGE] = False
    result = Interpreter(nodes, false_stage)
    state = result.run()
    contracts.require(result.calls == [], "false-stage invocation called components")
    contracts.require(state[TOTAL_RESULT] == 91.0 and state[COUNT_RESULT] == 91, "false-stage invocation mutated outputs")

    failures = []
    position_failure = make_case(); position_failure["__position_call_result__"] = False; failures.append((position_failure, ["CompilePositionRouteV1"]))
    profile_failure = make_case(); profile_failure["__profile_call_result__"] = False; failures.append((profile_failure, ["CompilePositionRouteV1", "CompileFlightProfilesV1"]))
    mismatch = make_case(); mismatch["FlightProfileCompiledIdsV1"] = ["hybrid"]; failures.append((mismatch, ["CompilePositionRouteV1", "CompileFlightProfilesV1"]))
    too_many = make_case(273.0626, 1.0 / 240.0); failures.append((too_many, ["CompilePositionRouteV1", "CompileFlightProfilesV1"]))
    for total in (0.0, 3600.1, math.inf, math.nan):
        case = make_case(1.0, 0.25); case["PositionRouteCompiledTotalSecondsV1"] = total; failures.append((case, ["CompilePositionRouteV1", "CompileFlightProfilesV1"]))
    for index, (case, calls) in enumerate(failures):
        result = Interpreter(nodes, case)
        state = result.run()
        contracts.require(result.calls == calls, f"failure call order {index}")
        contracts.require(state[STAGE] is False, f"failure stage {index}")
        contracts.require(state[TOTAL_RESULT] == 91.0 and state[COUNT_RESULT] == 91, f"failure publication {index}")
    print(f"Airframe source position/profile contracts passed ({'paste' if args.paste else 'full'}): {len(valid)} valid, false-stage no-op, {len(failures)} failures")


if __name__ == "__main__":
    main()
