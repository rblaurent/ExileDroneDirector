"""Exact helper-staging and candidate-publication contracts for flight profiles."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


CHANNELS = (
    ("Ids", "Id"), ("PathFollowWeights", "PathFollowWeight"),
    ("HorizonStabilizationWeights", "HorizonStabilizationWeight"),
    ("LookAheadSeconds", "LookAheadSeconds"), ("BankGains", "BankGain"),
    ("MaxBankDegrees", "MaxBankDegrees"), ("CameraUptiltDegrees", "CameraUptiltDegrees"),
    ("MaxAngularRatesDegreesPerSecond", "MaxAngularRateDegreesPerSecond"),
    ("MaxAccelerationsCmPerSecondSquared", "MaxAccelerationCmPerSecondSquared"),
    ("MaxJerksCmPerSecondCubed", "MaxJerkCmPerSecondCubed"),
    ("MinimumTurnRadiiCm", "MinimumTurnRadiusCm"),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_candidates_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin):
    body = node.pins[pin].body
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', body)
    if match is not None:
        return match.group(1)
    return "" if 'PinType.PinCategory="string"' in body else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (57 if args.paste else 58), f"candidate node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clears = [node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text]
    adds = [node for node in nodes.values() if 'MemberName="Array_Add"' in node.text]
    contracts.require(len(clears) == len(adds) == 11, "eleven candidate clear/add nodes")
    candidate_getters = []
    for candidate_suffix, result_suffix in CHANNELS:
        candidate_name = f"FlightProfileCandidate{candidate_suffix}V1"
        result_name = f"FlightProfileResolveResult{result_suffix}V1"
        candidate = contracts.one(nodes, f'MemberName="{candidate_name}"')
        result = contracts.one(nodes, f'MemberName="{result_name}"')
        clear = next(node for node in clears if contracts.linked(candidate, candidate_name, node, "TargetArray"))
        add = next(node for node in adds if contracts.linked(candidate, candidate_name, node, "TargetArray"))
        contracts.require_link(result, result_name, add, "NewItem", f"{candidate_name} source")
        candidate_getters.append((candidate, clear, add))
    ordered_clears = [value[1] for value in candidate_getters]
    ordered_adds = [value[2] for value in candidate_getters]
    if args.paste:
        contracts.require(not ordered_clears[0].pins["execute"].links, "paste root")
    else:
        contracts.require_link(entries[0], "then", ordered_clears[0], "execute", "entry clear seam")
    for left, right in zip(ordered_clears, ordered_clears[1:]):
        contracts.require_link(left, "then", right, "execute", "candidate clear order")
    stage_nodes = [node for node in nodes.values() if 'MemberName="FlightProfileStageValidV1"' in node.text]
    stage = next(node for node in stage_nodes if "K2Node_VariableGet" in node.node_class)
    reject = next(node for node in stage_nodes if "K2Node_VariableSet" in node.node_class)
    contracts.require(default(reject, "FlightProfileStageValidV1") == "false", "sticky reject")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 3, "stage/inherit/resolver guards")
    outer = next(node for node in branches if contracts.linked(stage, "FlightProfileStageValidV1", node, "Condition"))
    contracts.require_link(ordered_clears[-1], "then", outer, "execute", "clears before stage guard")
    overrides = contracts.one(nodes, 'MemberName="FlightProfileInputSegmentOverrideIdsV1"')
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 1, "one override loop")
    loop = loops[0]
    contracts.require_link(overrides, "FlightProfileInputSegmentOverrideIdsV1", loop, "Array", "override loop")
    contracts.require_link(outer, "then", loop, "Exec", "valid stage starts loop")
    empty = contracts.one(nodes, 'MemberName="EqualEqual_StrStr"')
    contracts.require(default(empty, "B") == "", "empty inheritance discriminator")
    contracts.require_link(loop, "Array Element", empty, "A", "override element discriminator")
    inherit = next(node for node in branches if contracts.linked(empty, "ReturnValue", node, "Condition"))
    default_id = contracts.one(nodes, 'MemberName="FlightProfileInputDefaultIdV1"')
    resolve_sets = [node for node in nodes.values() if 'MemberName="FlightProfileResolveInputIdV1"' in node.text]
    contracts.require(len(resolve_sets) == 2, "default and override resolver staging")
    default_set = next(node for node in resolve_sets if contracts.linked(default_id, "FlightProfileInputDefaultIdV1", node, "FlightProfileResolveInputIdV1"))
    override_set = next(node for node in resolve_sets if contracts.linked(loop, "Array Element", node, "FlightProfileResolveInputIdV1"))
    contracts.require_link(inherit, "then", default_set, "execute", "empty inherits default")
    contracts.require_link(inherit, "else", override_set, "execute", "nonempty uses override")
    resolver = contracts.one(nodes, 'MemberName="ResolveFlightProfilePresetV1"')
    contracts.require("bSelfContext=True" in resolver.text, "resolver self context")
    contracts.require_link(default_set, "then", resolver, "execute", "default invokes resolver")
    contracts.require_link(override_set, "then", resolver, "execute", "override invokes resolver")
    valid = contracts.one(nodes, 'MemberName="FlightProfileResolveResultValidV1"')
    result_guard = next(node for node in branches if contracts.linked(valid, "FlightProfileResolveResultValidV1", node, "Condition"))
    contracts.require_link(resolver, "then", result_guard, "execute", "resolver result guard")
    contracts.require_link(result_guard, "else", reject, "execute", "resolver failure sticky false")
    contracts.require_link(result_guard, "then", ordered_adds[0], "execute", "valid resolver publishes candidates")
    for left, right in zip(ordered_adds, ordered_adds[1:]):
        contracts.require_link(left, "then", right, "execute", "candidate publication order")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Flight-profile candidate contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
