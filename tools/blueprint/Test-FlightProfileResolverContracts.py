"""Exact canonical preset-resolution contracts for flight profiles."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FIELDS = (
    ("Id", "profile_id"),
    ("PathFollowWeight", "path_follow_weight"),
    ("HorizonStabilizationWeight", "horizon_stabilization_weight"),
    ("LookAheadSeconds", "look_ahead_seconds"),
    ("BankGain", "bank_gain"),
    ("MaxBankDegrees", "max_bank_degrees"),
    ("CameraUptiltDegrees", "camera_uptilt_degrees"),
    ("MaxAngularRateDegreesPerSecond", "max_angular_rate_degrees_per_second"),
    ("MaxAccelerationCmPerSecondSquared", "max_acceleration_cm_per_second_squared"),
    ("MaxJerkCmPerSecondCubed", "max_jerk_cm_per_second_cubed"),
    ("MinimumTurnRadiusCm", "minimum_turn_radius_cm"),
    ("Valid", None),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_resolver_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return None if match is None else match.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.project_root / "tools" / "trajectory"))
    from flight_profile_reference import PROFILE_ORDER, PROFILES

    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (83 if args.paste else 84), f"resolver node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    source = contracts.one(nodes, 'MemberName="FlightProfileResolveInputIdV1"')
    comparisons = [node for node in nodes.values() if 'MemberName="EqualEqual_StrStr"' in node.text]
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(comparisons) == len(branches) == 5, "five preset branches")
    by_id = {default(node, "B"): node for node in comparisons}
    contracts.require(tuple(by_id) == PROFILE_ORDER, "preset comparison order changed")
    for comparison in comparisons:
        contracts.require_link(source, "FlightProfileResolveInputIdV1", comparison, "A", "resolver identity source")
    setters_by_field = {}
    for field, _attribute in FIELDS:
        name = f"FlightProfileResolveResult{field}V1"
        setters_by_field[field] = [node for node in nodes.values() if f'MemberName="{name}"' in node.text]
        contracts.require(len(setters_by_field[field]) == 6, f"{field} must own reset plus five preset writes")
    resets = []
    for field, _attribute in FIELDS:
        name = f"FlightProfileResolveResult{field}V1"
        expected = "false" if field == "Valid" else ("" if field == "Id" else "0.0")
        matches = [node for node in setters_by_field[field] if default(node, name) == expected]
        contracts.require(matches, f"{field} reset missing")
        if field in ("Id", "Valid"):
            contracts.require(len(matches) == 1, f"{field} reset ambiguous")
        resets.append(matches[0])
    if args.paste:
        contracts.require(not resets[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", resets[0], "execute", "entry reset seam")
    for left, right in zip(resets, resets[1:]):
        contracts.require_link(left, "then", right, "execute", "resolver reset order")
    ordered_branches = []
    for profile_id in PROFILE_ORDER:
        comparison = by_id[profile_id]
        branch = next(branch for branch in branches if contracts.linked(comparison, "ReturnValue", branch, "Condition"))
        ordered_branches.append(branch)
        profile = PROFILES[profile_id]
        chain = []
        for field, attribute in FIELDS:
            name = f"FlightProfileResolveResult{field}V1"
            raw = True if attribute is None else getattr(profile, attribute)
            expected = "true" if raw is True else (raw if isinstance(raw, str) else repr(float(raw)))
            candidates = [node for node in setters_by_field[field] if default(node, name) == expected]
            if field != "Id" and len(candidates) > 1:
                if not chain:
                    raise RuntimeError("numeric chain cannot begin before ID")
                candidates = [node for node in candidates if contracts.linked(chain[-1], "then", node, "execute")]
            contracts.require(len(candidates) == 1, f"{profile_id} {field} write missing or ambiguous")
            chain.append(candidates[0])
        contracts.require_link(branch, "then", chain[0], "execute", f"{profile_id} branch")
        for left, right in zip(chain, chain[1:]):
            contracts.require_link(left, "then", right, "execute", f"{profile_id} setter order")
    contracts.require_link(resets[-1], "then", ordered_branches[0], "execute", "reset to first branch")
    for left, right in zip(ordered_branches, ordered_branches[1:]):
        contracts.require_link(left, "else", right, "execute", "unknown-ID branch order")
    contracts.require(not ordered_branches[-1].pins["else"].links, "unknown ID must retain reset invalid result")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Flight-profile resolver contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
