"""Exact contracts for fail-closed smoothed flight-profile sample staging."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


PARAMETERS = (
    "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
    "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
    "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_smoothed_profile_stage_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin: str):
    body = node.pins[pin].body
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', body)
    if match is not None:
        return match.group(1)
    return "" if 'PinType.PinCategory="string"' in body else None


def variable_nodes(nodes, name: str, node_class: str):
    return [
        node for node in nodes.values()
        if f'MemberName="{name}"' in node.text and node_class in node.node_class
    ]


def calls(nodes, member: str):
    return [node for node in nodes.values() if f'MemberName="{member}"' in node.text]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load(args.project_root)
    nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (118 if args.paste else 119), f"stage node count {len(nodes)}")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knots forbidden")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "stage entry count")

    requested = variable_nodes(nodes, "SmoothedFlightProfileInputSegmentIndexV1", "K2Node_VariableGet")
    alpha = variable_nodes(nodes, "SmoothedFlightProfileInputLocalTimeAlphaV1", "K2Node_VariableGet")
    c.require(len(requested) == 1 and len(alpha) == 1, "exact immutable smoothing input reads")
    c.require(not variable_nodes(nodes, "SmoothedFlightProfileInputSegmentIndexV1", "K2Node_VariableSet"), "segment input mutation forbidden")
    c.require(not variable_nodes(nodes, "SmoothedFlightProfileInputLocalTimeAlphaV1", "K2Node_VariableSet"), "alpha input mutation forbidden")
    requested, alpha = requested[0], alpha[0]

    compile_valid = c.one(nodes, 'MemberName="FlightProfileCompileValidV1"')
    compiled_ids = c.one(nodes, 'MemberName="FlightProfileCompiledIdsV1"')
    lengths = calls(nodes, "Array_Length")
    c.require(len(lengths) == 1, "one immutable compiled-ID length")
    length = lengths[0]
    c.require_link(compiled_ids, "FlightProfileCompiledIdsV1", length, "TargetArray", "neighbor bounds use compiled publication")
    c.require('PinType.ContainerType=Array' in compiled_ids.pins["FlightProfileCompiledIdsV1"].body, "compiled IDs remain an array")

    comparisons = {member: calls(nodes, member) for member in (
        "GreaterEqual_DoubleDouble", "LessEqual_DoubleDouble", "Greater_DoubleDouble",
        "GreaterEqual_IntInt", "LessEqual_IntInt", "Greater_IntInt", "Less_IntInt",
        "EqualEqual_IntInt", "BooleanAND",
    )}
    c.require(len(comparisons["GreaterEqual_DoubleDouble"]) == 2, "finite lower plus alpha lower")
    c.require(len(comparisons["LessEqual_DoubleDouble"]) == 2, "finite upper plus alpha upper")
    c.require(len(comparisons["Greater_DoubleDouble"]) == 1, "one right-half predicate")
    c.require(len(comparisons["GreaterEqual_IntInt"]) == 2, "count and index lower bounds")
    c.require(len(comparisons["LessEqual_IntInt"]) == 1, "count ceiling")
    c.require(len(comparisons["Greater_IntInt"]) == 1, "previous-neighbor predicate")
    c.require(len(comparisons["Less_IntInt"]) == 2, "index bound and next-neighbor predicate")
    c.require(len(comparisons["EqualEqual_IntInt"]) == 1, "self-neighbor equality")
    c.require(len(comparisons["BooleanAND"]) == 8, "finite and eight-way fail-closed guard conjunction")

    def has_default(collection, pin: str, value: str):
        return [node for node in collection if default(node, pin) == value]

    c.require(len(has_default(comparisons["GreaterEqual_DoubleDouble"], "B", "-1.7976931348623157e+308")) == 1, "explicit finite lower bound")
    c.require(len(has_default(comparisons["LessEqual_DoubleDouble"], "B", "1.7976931348623157e+308")) == 1, "explicit finite upper bound")
    c.require(len(has_default(comparisons["GreaterEqual_DoubleDouble"], "B", "0.0")) == 1, "alpha lower bound")
    c.require(len(has_default(comparisons["LessEqual_DoubleDouble"], "B", "1.0")) == 1, "alpha upper bound")
    c.require(len(has_default(comparisons["GreaterEqual_IntInt"], "B", "1")) == 1, "minimum compiled size")
    c.require(len(has_default(comparisons["LessEqual_IntInt"], "B", "511")) == 1, "maximum compiled size")
    c.require(len(has_default(comparisons["GreaterEqual_IntInt"], "B", "0")) == 1, "minimum requested index")

    # The helper boundary is called for current, neighbor, successful restore, and failed-neighbor restore.
    evaluator_calls = calls(nodes, "EvaluateCompiledFlightProfileV1")
    c.require(len(evaluator_calls) == 4, "current/neighbor/two restore evaluator calls")
    helper_sets = variable_nodes(nodes, "FlightProfileInputSegmentIndexV1", "K2Node_VariableSet")
    c.require(len(helper_sets) == 4, "requested/neighbor/two restore helper index writes")
    first_set = next((node for node in helper_sets if entries and c.linked(entries[0], "then", node, "execute")), None)
    if args.paste:
        roots = [node for node in helper_sets if not node.pins["execute"].links]
        c.require(len(roots) == 1, "paste exposes one helper-index root")
        first_set = roots[0]
    c.require(first_set is not None, "entry must set requested helper index")
    c.require_link(requested, "SmoothedFlightProfileInputSegmentIndexV1", first_set, "FlightProfileInputSegmentIndexV1", "helper starts at requested index")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 4, "guard/current/neighbor/restored branches")
    guard = next(node for node in branches if c.linked(first_set, "then", node, "execute"))
    first_call = next((node for node in evaluator_calls if c.linked(guard, "then", node, "execute")), None)
    c.require(first_call is not None, "guarded current evaluator call missing")
    c.require_link(guard, "then", first_call, "execute", "only valid inputs evaluate current")
    current_branch = next(node for node in branches if c.linked(first_call, "then", node, "execute"))
    current_valid_reads = variable_nodes(nodes, "FlightProfileResultValidV1", "K2Node_VariableGet")
    c.require(len(current_valid_reads) == 3, "current/neighbor/restored helper validity reads")
    c.require(any(c.linked(read, "FlightProfileResultValidV1", current_branch, "Condition") for read in current_valid_reads), "current helper validity guard")

    current_setters = []
    neighbor_setters = []
    for suffix, value in (("Id", "string"), *((name, "real") for name in PARAMETERS)):
        source_name = f"FlightProfileResult{suffix}V1"
        sources = variable_nodes(nodes, source_name, "K2Node_VariableGet")
        c.require(len(sources) == 2, f"current/neighbor source snapshots: {source_name}")
        for prefix, collection in (("Current", current_setters), ("Neighbor", neighbor_setters)):
            target_name = f"SmoothedFlightProfile{prefix}{suffix}V1"
            setters = variable_nodes(nodes, target_name, "K2Node_VariableSet")
            c.require(len(setters) == 1, f"one staged setter: {target_name}")
            setter = setters[0]
            c.require(any(c.linked(source, source_name, setter, target_name) for source in sources), f"exact helper snapshot: {target_name}")
            collection.append(setter)
    c.require_link(current_branch, "then", current_setters[0], "execute", "valid current begins complete snapshot")
    for left, right in zip(current_setters, current_setters[1:]):
        c.require_link(left, "then", right, "execute", "current snapshot order")

    # Three pure integer selects implement clamped previous/next/half choice.
    selects = [node for node in nodes.values() if "K2Node_Select" in node.node_class]
    int_selects = [node for node in selects if 'PinType.PinCategory="int"' in node.pins["ReturnValue"].body]
    real_selects = [node for node in selects if 'PinType.PinCategory="real"' in node.pins["ReturnValue"].body]
    c.require(len(int_selects) == 3 and len(real_selects) == 2, "three index selects and two weight selects")
    c.require(not calls(nodes, "Max_IntInt") and not calls(nodes, "Min_IntInt"), "DevKit-fragile integer min/max forbidden")
    subtract_int = calls(nodes, "Subtract_IntInt")
    add_int = calls(nodes, "Add_IntInt")
    c.require(len(subtract_int) == 2 and len(add_int) == 1, "previous/next/last integer arithmetic")
    c.require(sorted(default(node, "B") for node in subtract_int) == ["1", "1"] and default(add_int[0], "B") == "1", "neighbor arithmetic is exactly one segment")
    chosen_neighbor = next(node for node in int_selects if any(c.linked(node, "ReturnValue", setter, "FlightProfileInputSegmentIndexV1") for setter in helper_sets))
    neighbor_set = next(setter for setter in helper_sets if c.linked(chosen_neighbor, "ReturnValue", setter, "FlightProfileInputSegmentIndexV1"))
    c.require_link(current_setters[-1], "then", neighbor_set, "execute", "complete current snapshot precedes neighbor mutation")
    neighbor_call = next(node for node in evaluator_calls if c.linked(neighbor_set, "then", node, "execute"))
    neighbor_branch = next(node for node in branches if c.linked(neighbor_call, "then", node, "execute"))
    c.require(any(c.linked(read, "FlightProfileResultValidV1", neighbor_branch, "Condition") for read in current_valid_reads), "neighbor helper validity guard")

    # The two explicit quintic kernels are frozen by operation and coefficient multiplicity.
    multiplies = calls(nodes, "Multiply_DoubleDouble")
    subtracts = calls(nodes, "Subtract_DoubleDouble")
    adds = calls(nodes, "Add_DoubleDouble")
    c.require(len(multiplies) == 18 and len(subtracts) == 4 and len(adds) == 2, "two exact quintic half-kernels")
    coefficient_counts = {
        value: len([node for node in multiplies if default(node, "B") == value])
        for value in ("2.0", "10.0", "15.0", "6.0", "0.5")
    }
    c.require(coefficient_counts == {"2.0": 2, "10.0": 2, "15.0": 2, "6.0": 2, "0.5": 2}, f"quintic coefficients changed: {coefficient_counts}")
    c.require(len([node for node in subtracts if default(node, "A") == "1.0"]) == 1, "left weight is one minus smootherstep")
    c.require(len([node for node in subtracts if default(node, "B") == "1.0"]) == 1, "right half remaps two-alpha minus one")
    exact_zero = [node for node in real_selects if default(node, "Option 1") == "0.0"]
    c.require(len(exact_zero) == 1, "self-neighbor weight forced to exact zero")
    weight_setters = variable_nodes(nodes, "SmoothedFlightProfileNeighborWeightV1", "K2Node_VariableSet")
    c.require(len(weight_setters) == 1, "one neighbor-weight staging write")
    c.require_link(exact_zero[0], "ReturnValue", weight_setters[0], "SmoothedFlightProfileNeighborWeightV1", "clamped C2 weight staged")
    neighbor_setters.append(weight_setters[0])
    c.require_link(neighbor_branch, "then", neighbor_setters[0], "execute", "valid neighbor begins complete snapshot")
    for left, right in zip(neighbor_setters, neighbor_setters[1:]):
        c.require_link(left, "then", right, "execute", "neighbor snapshot order")

    restore_success = next(setter for setter in helper_sets if c.linked(neighbor_setters[-1], "then", setter, "execute"))
    c.require_link(requested, "SmoothedFlightProfileInputSegmentIndexV1", restore_success, "FlightProfileInputSegmentIndexV1", "success restores requested helper index")
    restore_success_call = next(node for node in evaluator_calls if c.linked(restore_success, "then", node, "execute"))
    restored_branch = next(node for node in branches if c.linked(restore_success_call, "then", node, "execute"))
    c.require(any(c.linked(read, "FlightProfileResultValidV1", restored_branch, "Condition") for read in current_valid_reads), "restored current must revalidate")
    stage_sets = variable_nodes(nodes, "SmoothedFlightProfileStageValidV1", "K2Node_VariableSet")
    c.require(len(stage_sets) == 1 and default(stage_sets[0], "SmoothedFlightProfileStageValidV1") == "true", "stage validity publishes once and true")
    c.require_link(restored_branch, "then", stage_sets[0], "execute", "stage validity is last on success")

    restore_failure = next(setter for setter in helper_sets if c.linked(neighbor_branch, "else", setter, "execute"))
    c.require_link(requested, "SmoothedFlightProfileInputSegmentIndexV1", restore_failure, "FlightProfileInputSegmentIndexV1", "neighbor failure restores requested helper index")
    c.require(any(c.linked(restore_failure, "then", call, "execute") for call in evaluator_calls), "neighbor failure refreshes restored helper result")

    for name in (
        "SmoothedFlightProfileResultCurrentIdV1", "SmoothedFlightProfileResultNeighborIdV1",
        "SmoothedFlightProfileResultNeighborWeightV1", "SmoothedFlightProfileResultValidV1",
        *(f"SmoothedFlightProfileResult{field}V1" for field in PARAMETERS),
    ):
        c.require(not variable_nodes(nodes, name, "K2Node_VariableSet"), f"staging must not publish {name}")
    c.require(not any('MemberName="Array_' in node.text and 'MemberName="Array_Length"' not in node.text for node in nodes.values()), "staging never mutates arrays")
    known = set(nodes)
    external = {
        target for node in nodes.values() for pin in node.pins.values()
        for target, _ in pin.links if target not in known
    }
    c.require(not external, f"external links {external}")
    print(f"Smoothed flight-profile stage contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
