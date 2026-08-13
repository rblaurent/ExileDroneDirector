"""Exact authored-shape and shared-duration contracts for cinematic pose."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_validation_contract_base", path)
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
    contracts.require(len(nodes) == (26 if args.paste else 27), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    positions = contracts.one(nodes, 'MemberName="PositionRouteInputWaypointPositionsV1"')
    quats = contracts.one(nodes, 'MemberName="OrientationTrackInputWaypointQuatsV1"')
    position_durations = contracts.one(nodes, 'MemberName="PositionRouteInputDurationsV1"')
    orientation_durations = contracts.one(nodes, 'MemberName="OrientationTrackInputDurationsV1"')
    lengths = [node for node in nodes.values() if 'MemberName="Array_Length"' in node.text]
    contracts.require(len(lengths) == 4, "four array lengths")
    position_count = next(node for node in lengths if contracts.linked(positions, "PositionRouteInputWaypointPositionsV1", node, "TargetArray"))
    quat_count = next(node for node in lengths if contracts.linked(quats, "OrientationTrackInputWaypointQuatsV1", node, "TargetArray"))
    position_duration_count = next(node for node in lengths if contracts.linked(position_durations, "PositionRouteInputDurationsV1", node, "TargetArray"))
    orientation_duration_count = next(node for node in lengths if contracts.linked(orientation_durations, "OrientationTrackInputDurationsV1", node, "TargetArray"))
    minimum = contracts.one(nodes, 'MemberName="GreaterEqual_IntInt"')
    maximum = contracts.one(nodes, 'MemberName="LessEqual_IntInt"')
    subtract = contracts.one(nodes, 'MemberName="Subtract_IntInt"')
    contracts.require(default(minimum, "B") == "2", "minimum changed")
    contracts.require(default(maximum, "B") == "512", "maximum changed")
    contracts.require(default(subtract, "B") == "1", "shape subtraction changed")
    contracts.require_link(position_count, "ReturnValue", minimum, "A", "minimum position count")
    contracts.require_link(position_count, "ReturnValue", maximum, "A", "maximum position count")
    contracts.require_link(position_count, "ReturnValue", subtract, "A", "position minus one")
    integer_equals = [node for node in nodes.values() if 'MemberName="EqualEqual_IntInt"' in node.text]
    contracts.require(len(integer_equals) == 3, "three integer shape checks")
    contracts.require(any(contracts.linked(position_count, "ReturnValue", node, "A") and contracts.linked(quat_count, "ReturnValue", node, "B") for node in integer_equals), "waypoint count equality")
    contracts.require(any(contracts.linked(position_duration_count, "ReturnValue", node, "A") and contracts.linked(subtract, "ReturnValue", node, "B") for node in integer_equals), "position duration shape")
    contracts.require(any(contracts.linked(position_duration_count, "ReturnValue", node, "A") and contracts.linked(orientation_duration_count, "ReturnValue", node, "B") for node in integer_equals), "duration count equality")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 1, "one duration comparison loop")
    loop = loops[0]
    contracts.require_link(position_durations, "PositionRouteInputDurationsV1", loop, "Array", "position durations drive loop")
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    contracts.require(len(items) == 1, "one indexed orientation duration")
    item = items[0]
    contracts.require_link(orientation_durations, "OrientationTrackInputDurationsV1", item, "Array", "orientation duration lookup")
    contracts.require_link(loop, "Array Index", item, "Dimension 1", "shared duration index")
    real_equal = contracts.one(nodes, 'MemberName="EqualEqual_DoubleDouble"')
    contracts.require_link(loop, "Array Element", real_equal, "A", "position duration comparison")
    contracts.require_link(item, "Output", real_equal, "B", "orientation duration comparison")
    stage_sets = [node for node in nodes.values() if 'MemberName="CinematicPoseStageValidV1"' in node.text]
    contracts.require(len(stage_sets) == 3, "reset accept reject writes")
    values = [default(node, "CinematicPoseStageValidV1") for node in stage_sets]
    contracts.require(values.count("true") == 1 and values.count("false") == 2, "sticky stage writes changed")
    if args.paste:
        contracts.require(any(not node.pins["execute"].links for node in stage_sets if default(node, "CinematicPoseStageValidV1") == "false"), "paste root exposed")
    else:
        contracts.require(any(contracts.linked(entries[0], "then", node, "execute") for node in stage_sets), "entry reset seam")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")
    print(f"Cinematic pose validation contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
