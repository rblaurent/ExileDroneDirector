"""Exact contracts for canonical, atomic smoothed flight-profile publication."""

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
BOUNDS = (
    ("0.0", "1.0", True), ("0.0", "1.0", True), ("0.0", "5.0", True),
    ("0.0", "2.0", True), ("0.0", "85.0", True), ("-45.0", "45.0", True),
    ("0.0", "720.0", False), ("0.0", "10000.0", False),
    ("0.0", "50000.0", False), ("0.0", "100000.0", False),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_smoothed_profile_publish_contract_base", path)
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


def variables(nodes, name: str, node_class: str):
    return [node for node in nodes.values() if f'MemberName="{name}"' in node.text and node_class in node.node_class]


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
    c.require(len(nodes) == (195 if args.paste else 196), f"publish node count {len(nodes)}")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "reroute knots forbidden")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "publish entry count")

    validity_sets = variables(nodes, "SmoothedFlightProfileResultValidV1", "K2Node_VariableSet")
    c.require(len(validity_sets) == 2, "exact invalidate/accept result-valid writes")
    invalidate = next(node for node in validity_sets if default(node, "SmoothedFlightProfileResultValidV1") == "false")
    accept = next(node for node in validity_sets if default(node, "SmoothedFlightProfileResultValidV1") == "true")
    if args.paste:
        c.require(not invalidate.pins["execute"].links, "paste exposes invalidation root")
    else:
        c.require_link(entries[0], "then", invalidate, "execute", "entry invalidates first")

    stage_valid = c.one(nodes, 'MemberName="SmoothedFlightProfileStageValidV1"')
    weight = c.one(nodes, 'MemberName="SmoothedFlightProfileNeighborWeightV1"')
    ge = calls(nodes, "GreaterEqual_DoubleDouble")
    le = calls(nodes, "LessEqual_DoubleDouble")
    gt = calls(nodes, "Greater_DoubleDouble")
    c.require(len(ge) == 8 and len(le) == 12 and len(gt) == 4, "finite, weight, and ten result domains")
    c.require(len([node for node in ge if default(node, "B") == "-1.7976931348623157e+308"]) == 1, "weight finite lower")
    c.require(len([node for node in le if default(node, "B") == "1.7976931348623157e+308"]) == 1, "weight finite upper")
    weight_lower = next(node for node in ge if default(node, "B") == "0.0" and c.linked(weight, "SmoothedFlightProfileNeighborWeightV1", node, "A"))
    weight_upper = next(node for node in le if default(node, "B") == "0.5")
    c.require_link(weight, "SmoothedFlightProfileNeighborWeightV1", weight_upper, "A", "neighbor weight ceiling source")
    bool_ands = calls(nodes, "BooleanAND")
    c.require(len(bool_ands) == 45, "finite/pre/two canonical/result guard conjunctions")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 4, "pre/current/neighbor/result branches")
    pre = next(node for node in branches if c.linked(invalidate, "then", node, "execute"))
    c.require(any(c.linked(node, "ReturnValue", pre, "Condition") for node in bool_ands), "precondition conjunction gates publication")

    current_id = c.one(nodes, 'MemberName="SmoothedFlightProfileCurrentIdV1"')
    neighbor_id = c.one(nodes, 'MemberName="SmoothedFlightProfileNeighborIdV1"')
    resolver_inputs = variables(nodes, "FlightProfileResolveInputIdV1", "K2Node_VariableSet")
    resolver_calls = calls(nodes, "ResolveFlightProfilePresetV1")
    c.require(len(resolver_inputs) == 2 and len(resolver_calls) == 2, "current and neighbor canonical resolver calls")
    current_input = next(node for node in resolver_inputs if c.linked(current_id, "SmoothedFlightProfileCurrentIdV1", node, "FlightProfileResolveInputIdV1"))
    neighbor_input = next(node for node in resolver_inputs if c.linked(neighbor_id, "SmoothedFlightProfileNeighborIdV1", node, "FlightProfileResolveInputIdV1"))
    c.require_link(pre, "then", current_input, "execute", "preconditions begin current resolution")
    current_call = next(node for node in resolver_calls if c.linked(current_input, "then", node, "execute"))
    current_branch = next(node for node in branches if c.linked(current_call, "then", node, "execute"))
    c.require_link(current_branch, "then", neighbor_input, "execute", "valid current begins neighbor resolution")
    neighbor_call = next(node for node in resolver_calls if c.linked(neighbor_input, "then", node, "execute"))
    neighbor_branch = next(node for node in branches if c.linked(neighbor_call, "then", node, "execute"))

    string_equals = calls(nodes, "EqualEqual_StrStr")
    double_equals = calls(nodes, "EqualEqual_DoubleDouble")
    c.require(len(string_equals) == 3 and len(double_equals) == 21, "two canonical IDs, identity normalization, twenty canonical values, zero weight")
    for node in string_equals:
        c.require("/Script/Engine.KismetStringLibrary" in node.text, "string equality uses StringLibrary")
        c.require("/Script/Engine.KismetMathLibrary" not in node.text, "string equality has no stale MathLibrary self pin")
    resolve_valid = c.one(nodes, 'MemberName="FlightProfileResolveResultValidV1"')
    resolve_id = c.one(nodes, 'MemberName="FlightProfileResolveResultIdV1"')
    canonical_id_equalities = [node for node in string_equals if c.linked(resolve_id, "FlightProfileResolveResultIdV1", node, "A")]
    c.require(len(canonical_id_equalities) == 2, "both staged IDs equal canonical resolver ID")
    c.require(any(c.linked(current_id, "SmoothedFlightProfileCurrentIdV1", node, "B") for node in canonical_id_equalities), "current canonical identity")
    c.require(any(c.linked(neighbor_id, "SmoothedFlightProfileNeighborIdV1", node, "B") for node in canonical_id_equalities), "neighbor canonical identity")

    current_values = []
    neighbor_values = []
    for name in PARAMETERS:
        current = c.one(nodes, f'MemberName="SmoothedFlightProfileCurrent{name}V1"')
        neighbor = c.one(nodes, f'MemberName="SmoothedFlightProfileNeighbor{name}V1"')
        resolved = variables(nodes, f"FlightProfileResolveResult{name}V1", "K2Node_VariableGet")
        c.require(len(resolved) == 2, f"two resolver reads for {name}")
        c.require(any(c.linked(current, f"SmoothedFlightProfileCurrent{name}V1", equal, "A") and any(c.linked(r, f"FlightProfileResolveResult{name}V1", equal, "B") for r in resolved) for equal in double_equals), f"current canonical value {name}")
        c.require(any(c.linked(neighbor, f"SmoothedFlightProfileNeighbor{name}V1", equal, "A") and any(c.linked(r, f"FlightProfileResolveResult{name}V1", equal, "B") for r in resolved) for equal in double_equals), f"neighbor canonical value {name}")
        current_values.append(current)
        neighbor_values.append(neighbor)
    c.require(any(c.linked(resolve_valid, "FlightProfileResolveResultValidV1", node, "A") or c.linked(resolve_valid, "FlightProfileResolveResultValidV1", node, "B") for node in bool_ands), "resolver validity participates in canonical gates")

    zero_equal = next(node for node in double_equals if default(node, "B") == "0.0" and c.linked(weight, "SmoothedFlightProfileNeighborWeightV1", node, "A"))
    same_id = next(node for node in string_equals if node not in canonical_id_equalities)
    c.require_link(current_id, "SmoothedFlightProfileCurrentIdV1", same_id, "A", "same-ID normalization current")
    c.require_link(neighbor_id, "SmoothedFlightProfileNeighborIdV1", same_id, "B", "same-ID normalization neighbor")
    bool_or = calls(nodes, "BooleanOR")
    c.require(len(bool_or) == 1, "zero-weight or same-ID normalization")
    c.require_link(zero_equal, "ReturnValue", bool_or[0], "A", "zero weight normalization")
    c.require_link(same_id, "ReturnValue", bool_or[0], "B", "same ID normalization")
    selects = [node for node in nodes.values() if "K2Node_Select" in node.node_class]
    c.require(len(selects) == 2, "effective ID and effective weight selects")
    id_select = next(node for node in selects if 'PinType.PinCategory="string"' in node.pins["ReturnValue"].body)
    weight_select = next(node for node in selects if 'PinType.PinCategory="real"' in node.pins["ReturnValue"].body)
    c.require_link(bool_or[0], "ReturnValue", id_select, "Index", "metadata normalization condition")
    c.require_link(neighbor_id, "SmoothedFlightProfileNeighborIdV1", id_select, "Option 0", "non-normalized neighbor ID")
    c.require_link(current_id, "SmoothedFlightProfileCurrentIdV1", id_select, "Option 1", "normalized neighbor ID is current")
    c.require_link(bool_or[0], "ReturnValue", weight_select, "Index", "weight normalization condition")
    c.require_link(weight, "SmoothedFlightProfileNeighborWeightV1", weight_select, "Option 0", "non-normalized neighbor weight")
    c.require(default(weight_select, "Option 1") == "0.0", "normalized neighbor weight is exact zero")

    subtracts = calls(nodes, "Subtract_DoubleDouble")
    multiplies = calls(nodes, "Multiply_DoubleDouble")
    adds = calls(nodes, "Add_DoubleDouble")
    c.require(len(subtracts) == len(multiplies) == len(adds) == 10, "ten exact convex interpolation triplets")
    blended = []
    for index, (name, current, neighbor, bounds) in enumerate(zip(PARAMETERS, current_values, neighbor_values, BOUNDS)):
        delta = next(node for node in subtracts if c.linked(neighbor, f"SmoothedFlightProfileNeighbor{name}V1", node, "A") and c.linked(current, f"SmoothedFlightProfileCurrent{name}V1", node, "B"))
        scaled = next(node for node in multiplies if c.linked(delta, "ReturnValue", node, "A") and c.linked(weight_select, "ReturnValue", node, "B"))
        value = next(node for node in adds if c.linked(current, f"SmoothedFlightProfileCurrent{name}V1", node, "A") and c.linked(scaled, "ReturnValue", node, "B"))
        blended.append(value)
        lower, upper, inclusive = bounds
        lowers = ge if inclusive else gt
        c.require(any(c.linked(value, "ReturnValue", node, "A") and default(node, "B") == lower for node in lowers), f"result lower domain {name}")
        c.require(any(c.linked(value, "ReturnValue", node, "A") and default(node, "B") == upper for node in le), f"result upper domain {name}")
    result_branch = next(node for node in branches if c.linked(neighbor_branch, "then", node, "execute"))
    c.require(any(c.linked(node, "ReturnValue", result_branch, "Condition") for node in bool_ands), "all blended domains gate publication")

    publication_specs = (
        ("SmoothedFlightProfileResultCurrentIdV1", current_id, "SmoothedFlightProfileCurrentIdV1"),
        ("SmoothedFlightProfileResultNeighborIdV1", id_select, "ReturnValue"),
        ("SmoothedFlightProfileResultNeighborWeightV1", weight_select, "ReturnValue"),
        *((f"SmoothedFlightProfileResult{name}V1", value, "ReturnValue") for name, value in zip(PARAMETERS, blended)),
    )
    publications = []
    for target, source, source_pin in publication_specs:
        setters = variables(nodes, target, "K2Node_VariableSet")
        c.require(len(setters) == 1, f"one atomic publication setter: {target}")
        c.require_link(source, source_pin, setters[0], target, f"publication source: {target}")
        publications.append(setters[0])
    c.require_link(result_branch, "then", publications[0], "execute", "validated publication begins with current ID")
    for left, right in zip(publications, publications[1:]):
        c.require_link(left, "then", right, "execute", "atomic result publication order")
    c.require_link(publications[-1], "then", accept, "execute", "result validity publishes last")

    c.require(not variables(nodes, "SmoothedFlightProfileStageValidV1", "K2Node_VariableSet"), "publish never mutates stage validity")
    c.require(not any('MemberName="Array_' in node.text for node in nodes.values()), "publish owns no array operation")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Smoothed flight-profile publish contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
