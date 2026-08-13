"""Exact authored shape and identity contracts for flight profiles."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


PROFILE_IDS = {"cinematic_drone", "hybrid", "fpv_cinewhoop", "fpv_freestyle", "fpv_long_range"}


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_validation_contract_base", path)
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
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    expected = 36 if args.paste else 37
    contracts.require(len(nodes) == expected, f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    default_id = contracts.one(nodes, 'MemberName="FlightProfileInputDefaultIdV1"')
    overrides = contracts.one(nodes, 'MemberName="FlightProfileInputSegmentOverrideIdsV1"')
    count = contracts.one(nodes, 'MemberName="FlightProfileInputSegmentCountV1"')
    length = contracts.one(nodes, 'MemberName="Array_Length"')
    contracts.require_link(overrides, "FlightProfileInputSegmentOverrideIdsV1", length, "TargetArray", "override length")
    minimum = contracts.one(nodes, 'MemberName="GreaterEqual_IntInt"')
    maximum = contracts.one(nodes, 'MemberName="LessEqual_IntInt"')
    equal_count = contracts.one(nodes, 'MemberName="EqualEqual_IntInt"')
    contracts.require(default(minimum, "B") == "1", "minimum changed")
    contracts.require(default(maximum, "B") == "511", "maximum changed")
    contracts.require_link(count, "FlightProfileInputSegmentCountV1", minimum, "A", "minimum count")
    contracts.require_link(count, "FlightProfileInputSegmentCountV1", maximum, "A", "maximum count")
    contracts.require_link(length, "ReturnValue", equal_count, "A", "override shape")
    contracts.require_link(count, "FlightProfileInputSegmentCountV1", equal_count, "B", "segment shape")
    string_equals = [node for node in nodes.values() if 'MemberName="EqualEqual_StrStr"' in node.text]
    contracts.require(len(string_equals) == 11, "default plus override identity comparisons")
    default_checks = [node for node in string_equals if contracts.linked(default_id, "FlightProfileInputDefaultIdV1", node, "A")]
    contracts.require({default(node, "B") for node in default_checks} == PROFILE_IDS, "default IDs changed")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 1, "one override loop")
    loop = loops[0]
    contracts.require_link(overrides, "FlightProfileInputSegmentOverrideIdsV1", loop, "Array", "override loop source")
    override_checks = [node for node in string_equals if contracts.linked(loop, "Array Element", node, "A")]
    contracts.require({default(node, "B") for node in override_checks} == PROFILE_IDS | {""}, "override IDs changed")
    stage_sets = [node for node in nodes.values() if 'MemberName="FlightProfileStageValidV1"' in node.text]
    contracts.require(len(stage_sets) == 3, "reset accept reject writes")
    values = [default(node, "FlightProfileStageValidV1") for node in stage_sets]
    contracts.require(values.count("true") == 1 and values.count("false") == 2, "sticky validity writes changed")
    if args.paste:
        contracts.require(any(not node.pins["execute"].links for node in stage_sets if default(node, "FlightProfileStageValidV1") == "false"), "paste root exposed")
    else:
        contracts.require(any(contracts.linked(entries[0], "then", node, "execute") for node in stage_sets), "entry reset seam")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Flight-profile validation contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
