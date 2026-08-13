"""Exact graph-shape and executable-domain contracts for desired-stream validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


ARRAYS = (
    ("AirframeDesiredStreamInputPositionsV1", "vector"),
    ("AirframeDesiredStreamInputAuthoredBodyQuatsV1", "quat"),
    ("AirframeDesiredStreamInputAuthoredGimbalQuatsV1", "quat"),
    ("AirframeDesiredStreamInputPathFollowWeightsV1", "real"),
    ("AirframeDesiredStreamInputHorizonStabilizationWeightsV1", "real"),
    ("AirframeDesiredStreamInputLookAheadSecondsV1", "real"),
    ("AirframeDesiredStreamInputBankGainsV1", "real"),
    ("AirframeDesiredStreamInputMaxBankDegreesV1", "real"),
    ("AirframeDesiredStreamInputCameraUptiltDegreesV1", "real"),
    ("AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1", "real"),
    ("AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1", "real"),
    ("AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1", "real"),
    ("AirframeDesiredStreamInputMinimumTurnRadiiCmV1", "real"),
)
PROFILE_BOUNDS = (
    (ARRAYS[3][0], 0.0, 1.0, True),
    (ARRAYS[4][0], 0.0, 1.0, True),
    (ARRAYS[5][0], 0.0, 5.0, True),
    (ARRAYS[6][0], 0.0, 2.0, True),
    (ARRAYS[7][0], 0.0, 85.0, True),
    (ARRAYS[8][0], -45.0, 45.0, True),
    (ARRAYS[9][0], 0.0, 720.0, False),
    (ARRAYS[10][0], 0.0, 10000.0, False),
    (ARRAYS[11][0], 0.0, 50000.0, False),
    (ARRAYS[12][0], 0.0, 100000.0, False),
)
TOTAL = "AirframeDesiredStreamInputTotalSecondsV1"
STEP = "AirframeDesiredStreamInputFixedStepSecondsV1"
STAGE = "AirframeDesiredStreamStageValidV1"
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_validation_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def members(nodes, name):
    return [node for node in nodes.values() if f'MemberName="{name}"' in node.text]


def explicit_default(pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', pin.body)
    return None if match is None else match.group(1)


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, pin_name):
    value = explicit_default(node.pins[pin_name])
    return "" if value is None else value


class Interpreter:
    """Execute the exported validation graph, including every foreach rejection."""

    def __init__(self, nodes, state):
        self.nodes = nodes
        self.state = dict(state)
        self.loop_values = {}
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
        text = default(node, pin_name)
        if text == "":
            body = node.pins[pin_name].body
            if 'PinType.PinCategory="int"' in body: return 0
            if 'PinType.PinCategory="real"' in body: return 0.0
            if 'PinType.PinCategory="bool"' in body: return False
        if text == "true":
            return True
        if text == "false":
            return False
        try:
            return float(text)
        except ValueError:
            return text

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[member(node)]
        if "K2Node_MacroInstance" in node.node_class:
            if pin_name == "Array Element":
                return self.loop_values[node.name]
            raise RuntimeError(f"unsupported loop output {pin_name}")
        name = member(node)
        if name == "Array_Length":
            return len(self.value(node, "TargetArray"))
        if name == "Conv_IntToDouble":
            return float(self.value(node, "InInt"))
        if name == "BreakVector":
            return self.value(node, "InVec")[("X", "Y", "Z").index(pin_name)]
        if name == "Quat_IsFinite":
            return all(math.isfinite(float(value)) for value in self.value(node, "Q"))
        if name == "Quat_Size":
            return math.sqrt(sum(float(value) * float(value) for value in self.value(node, "Q")))
        if name == "BooleanAND":
            return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        left, right = self.value(node, "A"), self.value(node, "B")
        if name in ("GreaterEqual_IntInt", "GreaterEqual_DoubleDouble"):
            return left >= right
        if name in ("LessEqual_IntInt", "LessEqual_DoubleDouble"):
            return left <= right
        if name == "EqualEqual_IntInt":
            return left == right
        if name == "Greater_DoubleDouble":
            return left > right
        if name == "Less_DoubleDouble":
            return left < right
        if name == "Subtract_IntInt":
            return int(left) - int(right)
        if name == "Multiply_DoubleDouble":
            return left * right
        raise RuntimeError(f"unsupported node {node.name}:{name}")

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
            setters = [
                node for node in self.nodes.values()
                if "K2Node_VariableSet" in node.node_class and member(node) == STAGE
            ]
            current = next(node for node in setters if not node.pins["execute"].links)
        while current is not None:
            if "K2Node_VariableSet" in current.node_class:
                self.state[member(current)] = self.value(current, member(current))
                current = self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                values = self.value(current, "Array")
                body = self.next(current, "LoopBody")
                if body is None or "K2Node_IfThenElse" not in body.node_class:
                    raise RuntimeError("loop body contract")
                for value in values:
                    self.loop_values[current.name] = value
                    if not self.value(body, "Condition"):
                        reject = self.next(body, "else")
                        if reject is None or member(reject) != STAGE:
                            raise RuntimeError("missing sticky rejection")
                        self.state[STAGE] = self.value(reject, STAGE)
                current = self.next(current, "Completed")
            else:
                raise RuntimeError(f"unsupported exec node {current.name}:{member(current)}")
        return self.state[STAGE]


def is_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def validates(case):
    positions = case[ARRAYS[0][0]]
    count = len(positions)
    if not 2 <= count <= 65536:
        return False
    if any(len(case[name]) != count for name, _kind in ARRAYS[1:]):
        return False
    total, step = case[TOTAL], case[STEP]
    if not is_number(total) or not 0.0 < float(total) <= 3600.0:
        return False
    if not is_number(step) or not 1.0 / 240.0 <= float(step) <= 0.5:
        return False
    if not (float(count - 2) * float(step) < float(total) <= float(count - 1) * float(step)):
        return False
    for value in positions:
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return False
        if any(not is_number(component) for component in value):
            return False
    for name in (ARRAYS[1][0], ARRAYS[2][0]):
        for value in case[name]:
            if not isinstance(value, (tuple, list)) or len(value) != 4:
                return False
            if any(not is_number(component) for component in value):
                return False
            magnitude = math.sqrt(sum(float(component) ** 2 for component in value))
            if not 0.999999 <= magnitude <= 1.000001:
                return False
    for name, lower, upper, inclusive in PROFILE_BOUNDS:
        for value in case[name]:
            if not is_number(value):
                return False
            if not ((float(value) >= lower if inclusive else float(value) > lower) and float(value) <= upper):
                return False
    return True


def make_case(total=1.0, step=0.25):
    count = math.ceil(total / step) + 1
    case = {
        ARRAYS[0][0]: [(float(index), float(index * index), 0.0) for index in range(count)],
        ARRAYS[1][0]: [IDENTITY] * count,
        ARRAYS[2][0]: [IDENTITY] * count,
        TOTAL: total,
        STEP: step,
    }
    defaults = (0.5, 0.5, 0.25, 1.0, 45.0, 0.0, 180.0, 1000.0, 5000.0, 100.0)
    for (name, _lower, _upper, _inclusive), value in zip(PROFILE_BOUNDS, defaults):
        case[name] = [value] * count
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (217 if args.paste else 218), f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "validation entry count")
    contracts.require(len(members(nodes, "Array_Length")) == 13, "all source cardinalities must be measured")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 13, "all source arrays must be scanned")
    contracts.require(len(members(nodes, "BreakVector")) == 1, "position vector must split once")
    contracts.require(len(members(nodes, "Quat_IsFinite")) == 2, "both quaternion arrays need finite guards")
    contracts.require(len(members(nodes, "Quat_Size")) == 2, "both quaternion arrays need unit guards")

    getters = []
    source_loops = []
    for name, _kind in ARRAYS:
        getter = next((node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and f'MemberName="{name}"' in node.text), None)
        contracts.require(getter is not None, f"{name} getter missing")
        getters.append(getter)
        length = next((node for node in members(nodes, "Array_Length") if any(target == getter.name for pin in node.pins.values() for target, _pin in pin.links)), None)
        loop = next((node for node in loops if any(target == getter.name for pin in node.pins.values() for target, _pin in pin.links)), None)
        contracts.require(length is not None, f"{name} length link missing")
        contracts.require(loop is not None, f"{name} scan link missing")
        contracts.require_link(getter, name, length, "TargetArray", f"{name} length source changed")
        contracts.require_link(getter, name, loop, "Array", f"{name} scan source changed")
        source_loops.append(loop)

    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(setters and all(f'MemberName="{STAGE}"' in node.text for node in setters), "validation may only write stage validity")
    true_setters = [node for node in setters if explicit_default(node.pins[STAGE]) == "true"]
    false_setters = [node for node in setters if explicit_default(node.pins[STAGE]) == "false"]
    contracts.require(len(true_setters) == 1 and len(false_setters) == 14, "sticky stage publication changed")
    accept = true_setters[0]
    contracts.require_link(accept, "then", source_loops[0], "Exec", "position scan must start after acceptance")
    for left, right in zip(source_loops, source_loops[1:]):
        contracts.require_link(left, "Completed", right, "Exec", "source scan order changed")
    contracts.require(len(members(nodes, "EqualEqual_IntInt")) == 12, "all secondary cardinalities must equal position count")
    contracts.require(len(members(nodes, "Subtract_IntInt")) == 2, "exact schedule integer bounds changed")
    contracts.require(len(members(nodes, "Conv_IntToDouble")) == 2, "exact schedule conversion changed")
    contracts.require(len(members(nodes, "Multiply_DoubleDouble")) == 2, "exact schedule products changed")
    for required in ("0.004166666666666667", "0.5", "3600.0", "0.999999", "1.000001", "720.0", "10000.0", "50000.0", "100000.0"):
        contracts.require(f'DefaultValue="{required}"' in args.graph.read_text(encoding="utf-8"), f"required bound {required} missing")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knot forbidden")

    directed = [make_case(0.1, 0.5), make_case(1.0, 0.25), make_case(1.0, 0.3)]
    rng = random.Random(0xEDD57EA)
    valid_cases = directed + [
        make_case(rng.uniform(0.05, 3.0), rng.choice((0.05, 0.1, 0.2, 0.3, 0.5)))
        for _ in range(100)
    ]
    contracts.require(all(validates(case) for case in valid_cases), "valid reference case rejected")
    for index, case in enumerate(valid_cases):
        contracts.require(Interpreter(nodes, case).run() is True, f"valid executable case {index}")
    invalid = []
    base = make_case()
    for name, _kind in ARRAYS[1:]:
        case = {key: list(value) if isinstance(value, list) else value for key, value in base.items()}
        case[name] = case[name][:-1]
        invalid.append(case)
    for name, values in ((TOTAL, (0.0, 3600.1, math.nan, math.inf)), (STEP, (0.0, 1.0 / 241.0, 0.501, math.inf))):
        for value in values:
            case = dict(base); case[name] = value; invalid.append(case)
    for name, bad in (
        (ARRAYS[0][0], (math.nan, 0.0, 0.0)),
        (ARRAYS[1][0], (0.0, 0.0, 0.0, 0.0)),
        (ARRAYS[2][0], (0.0, 0.0, 0.0, 1.0000011)),
    ):
        case = {key: list(value) if isinstance(value, list) else value for key, value in base.items()}
        case[name][1] = bad
        invalid.append(case)
    for name, lower, upper, inclusive in PROFILE_BOUNDS:
        for bad in ((lower - 1.0) if inclusive else lower, upper + 1.0, math.nan):
            case = {key: list(value) if isinstance(value, list) else value for key, value in base.items()}
            case[name][1] = bad
            invalid.append(case)
    schedule = dict(base); schedule[TOTAL] = 1.1; invalid.append(schedule)
    contracts.require(all(not validates(case) for case in invalid), "invalid reference family accepted")
    for index, case in enumerate(invalid):
        contracts.require(Interpreter(nodes, case).run() is False, f"invalid executable case {index}")
    print(f"Airframe desired-stream validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid_cases)} valid, {len(invalid)} invalid")


if __name__ == "__main__":
    main()
