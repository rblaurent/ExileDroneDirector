"""Exact atomic integrity and publication contracts for compiled flight profiles."""

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
BOUNDS = (("0.0", "1.0", True), ("0.0", "1.0", True), ("0.0", "5.0", True), ("0.0", "2.0", True), ("0.0", "85.0", True), ("-45.0", "45.0", True), ("0.0", "720.0", False), ("0.0", "10000.0", False), ("0.0", "50000.0", False), ("0.0", "100000.0", False))


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_commit_contract_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return None if match is None else match.group(1)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root); nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (154 if args.paste else 155), f"commit node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "entry count")
    compile_sets = [node for node in nodes.values() if 'MemberName="FlightProfileCompileValidV1"' in node.text]
    c.require(len(compile_sets) == 2, "compile invalidation/publication")
    invalidate = next(node for node in compile_sets if default(node, "FlightProfileCompileValidV1") == "false")
    publish = next(node for node in compile_sets if default(node, "FlightProfileCompileValidV1") == "true")
    if args.paste: c.require(not invalidate.pins["execute"].links, "paste root")
    else: c.require_link(entries[0], "then", invalidate, "execute", "entry invalidates publication")
    stage_nodes = [node for node in nodes.values() if 'MemberName="FlightProfileStageValidV1"' in node.text]
    stage = next(node for node in stage_nodes if "K2Node_VariableGet" in node.node_class)
    reject = next(node for node in stage_nodes if "K2Node_VariableSet" in node.node_class)
    c.require(default(reject, "FlightProfileStageValidV1") == "false", "sticky reject")
    count = c.one(nodes, 'MemberName="FlightProfileInputSegmentCountV1"')
    minimum = c.one(nodes, 'MemberName="GreaterEqual_IntInt"'); maximum = c.one(nodes, 'MemberName="LessEqual_IntInt"')
    c.require(default(minimum, "B") == "1" and default(maximum, "B") == "511", "segment bounds")
    c.require_link(count, "FlightProfileInputSegmentCountV1", minimum, "A", "minimum source"); c.require_link(count, "FlightProfileInputSegmentCountV1", maximum, "A", "maximum source")
    lengths = [node for node in nodes.values() if 'MemberName="Array_Length"' in node.text]
    integer_equals = [node for node in nodes.values() if 'MemberName="EqualEqual_IntInt"' in node.text]
    c.require(len(lengths) == len(integer_equals) == 11, "all candidate cardinalities")
    candidates = []
    for suffix, _result_suffix in CHANNELS:
        name = f"FlightProfileCandidate{suffix}V1"; candidate = c.one(nodes, f'MemberName="{name}"'); candidates.append(candidate)
        length = next(node for node in lengths if c.linked(candidate, name, node, "TargetArray"))
        c.require(any(c.linked(length, "ReturnValue", equal, "A") and c.linked(count, "FlightProfileInputSegmentCountV1", equal, "B") for equal in integer_equals), f"{name} cardinality")
    boolean_ands = [node for node in nodes.values() if 'MemberName="BooleanAND"' in node.text]
    c.require(len(boolean_ands) == 44, "pre/item sticky conjunctions")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 3, "pre/item/final guards")
    pre = next(node for node in branches if c.linked(invalidate, "then", node, "execute"))
    c.require_link(pre, "else", reject, "execute", "precondition failure rejects")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    c.require(len(loops) == 1, "one integrity loop"); loop = loops[0]
    c.require_link(candidates[0], "FlightProfileCandidateIdsV1", loop, "Array", "candidate ID loop"); c.require_link(pre, "then", loop, "Exec", "precondition starts loop")
    resolver_input = c.one(nodes, 'MemberName="FlightProfileResolveInputIdV1"')
    c.require_link(loop, "Array Element", resolver_input, "FlightProfileResolveInputIdV1", "resolver ID staging"); c.require_link(loop, "LoopBody", resolver_input, "execute", "each candidate staged")
    resolver = c.one(nodes, 'MemberName="ResolveFlightProfilePresetV1"'); c.require("bSelfContext=True" in resolver.text, "resolver self context"); c.require_link(resolver_input, "then", resolver, "execute", "staging invokes resolver")
    resolver_valid = c.one(nodes, 'MemberName="FlightProfileResolveResultValidV1"')
    resolver_id = c.one(nodes, 'MemberName="FlightProfileResolveResultIdV1"')
    id_equal = c.one(nodes, 'MemberName="EqualEqual_StrStr"')
    c.require('/Script/Engine.KismetStringLibrary' in id_equal.text, "string equality library")
    c.require('/Script/Engine.KismetMathLibrary' not in id_equal.text, "string equality has no stale MathLibrary self pin")
    c.require_link(resolver_id, "FlightProfileResolveResultIdV1", id_equal, "A", "resolved ID comparison"); c.require_link(loop, "Array Element", id_equal, "B", "candidate ID comparison")
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    real_equals = [node for node in nodes.values() if 'MemberName="EqualEqual_DoubleDouble"' in node.text]
    c.require(len(items) == len(real_equals) == 10, "ten parameter integrity comparisons")
    inclusive_lowers = [node for node in nodes.values() if 'MemberName="GreaterEqual_DoubleDouble"' in node.text]
    strict_lowers = [node for node in nodes.values() if 'MemberName="Greater_DoubleDouble"' in node.text]
    uppers = [node for node in nodes.values() if 'MemberName="LessEqual_DoubleDouble"' in node.text]
    c.require(len(inclusive_lowers) == 6 and len(strict_lowers) == 4 and len(uppers) == 10, "finite range guards")
    for index, ((suffix, result_suffix), candidate) in enumerate(zip(CHANNELS[1:], candidates[1:])):
        candidate_name = f"FlightProfileCandidate{suffix}V1"; resolver_name = f"FlightProfileResolveResult{result_suffix}V1"
        item = next(node for node in items if c.linked(candidate, candidate_name, node, "Array")); c.require_link(loop, "Array Index", item, "Dimension 1", f"{suffix} index")
        result = c.one(nodes, f'MemberName="{resolver_name}"')
        c.require(any(c.linked(item, "Output", equal, "A") and c.linked(result, resolver_name, equal, "B") for equal in real_equals), f"{suffix} canonical integrity")
        lower, upper, inclusive = BOUNDS[index]
        lower_nodes = inclusive_lowers if inclusive else strict_lowers
        c.require(any(c.linked(item, "Output", node, "A") and default(node, "B") == lower for node in lower_nodes), f"{suffix} finite lower bound")
        c.require(any(c.linked(item, "Output", node, "A") and default(node, "B") == upper for node in uppers), f"{suffix} finite upper bound")
    item_guard = next(node for node in branches if c.linked(resolver, "then", node, "execute")); c.require_link(item_guard, "else", reject, "execute", "item corruption rejects")
    final = next(node for node in branches if c.linked(loop, "Completed", node, "execute") and c.linked(stage, "FlightProfileStageValidV1", node, "Condition"))
    compiled_sets = []
    for (suffix, _result_suffix), candidate in zip(CHANNELS, candidates):
        candidate_name = f"FlightProfileCandidate{suffix}V1"; compiled_name = f"FlightProfileCompiled{suffix}V1"
        setter = c.one(nodes, f'MemberName="{compiled_name}"'); c.require_link(candidate, candidate_name, setter, compiled_name, f"{compiled_name} atomic source"); compiled_sets.append(setter)
    c.require_link(final, "then", compiled_sets[0], "execute", "final guard begins publication")
    for left, right in zip(compiled_sets, compiled_sets[1:]): c.require_link(left, "then", right, "execute", "compiled publication order")
    c.require_link(compiled_sets[-1], "then", publish, "execute", "validity publishes last")
    known = set(nodes); external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}; c.require(not external, f"external links {external}")
    print(f"Flight-profile commit contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__": main()
