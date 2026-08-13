"""Structural and executable contracts for post-adapter discontinuity diagnostics."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


OUTPUTS = (
    "AirframeDocumentDiagnosticWaypointIdsV2",
    "AirframeDocumentDiagnosticPositionVelocityJumpsV2",
    "AirframeDocumentDiagnosticPositionAccelerationJumpsV2",
    "AirframeDocumentDiagnosticBodyAngularRateJumpsV2",
    "AirframeDocumentDiagnosticGimbalAngularRateJumpsV2",
    "AirframeDocumentDiagnosticDiscontinuousFlagsV2",
)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def yaw(degrees):
    half = math.radians(degrees) * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


def pitch(degrees):
    half = math.radians(degrees) * 0.5
    return (0.0, math.sin(half), 0.0, math.cos(half))


def make_case(reference, seed):
    rng = random.Random(seed)
    count = rng.randint(3, 8)
    ids = [100 + index * 3 for index in range(count)]
    waypoints = []
    x = 0.0
    for index, waypoint_id in enumerate(ids):
        if index:
            x += rng.uniform(30.0, 180.0)
        waypoints.append(reference.CompiledDocumentWaypointV2(
            waypoint_id,
            (x, rng.uniform(-40.0, 40.0), rng.uniform(-15.0, 15.0)),
            yaw(rng.uniform(-80.0, 80.0)),
            pitch(rng.uniform(-45.0, 45.0)),
        ))
    segments = []
    durations = []
    for index in range(count - 1):
        duration = rng.choice((0.25, 0.5, 0.75, 1.0, 1.5))
        durations.append(duration)
        segments.append(reference.CompiledDocumentSegmentV2(
            1000 + index,
            ids[index],
            ids[index + 1],
            duration,
            rng.choice(("linear", "auto_cinematic")),
            "linear",
            "",
        ))
    return reference.CompiledTrajectoryDocumentV2(tuple(waypoints), tuple(segments), sum(durations))


def blueprint_semantics(document, thresholds, cinematic, orientation):
    points = tuple(item.position for item in document.waypoints)
    durations = tuple(item.duration_seconds for item in document.segments)
    position = cinematic.compile_trajectory(points, tuple(
        cinematic.AuthoredSegment(item.duration_seconds, item.spatial_curve_type, item.time_profile)
        for item in document.segments
    ))
    body = orientation.compile_orientation_track(tuple(item.body_rotation for item in document.waypoints), durations)
    gimbal = orientation.compile_orientation_track(tuple(item.gimbal_rotation for item in document.waypoints), durations)
    rows = []
    count = 0
    for index in range(1, len(document.waypoints) - 1):
        left_velocity, left_acceleration = cinematic.evaluate_spatial_derivatives(position.segments[index - 1], 1.0)
        right_velocity, right_acceleration = cinematic.evaluate_spatial_derivatives(position.segments[index], 0.0)

        def magnitude(delta):
            return math.sqrt(sum(value * value for value in delta))

        velocity_jump = magnitude(tuple(right - left for left, right in zip(left_velocity, right_velocity)))
        acceleration_jump = magnitude(tuple(right - left for left, right in zip(left_acceleration, right_acceleration)))

        def rate(track, segment):
            delta = orientation.logarithmic_delta(track.waypoints[segment], track.waypoints[segment + 1])
            return tuple(value / durations[segment] for value in delta)

        body_left, body_right = rate(body, index - 1), rate(body, index)
        gimbal_left, gimbal_right = rate(gimbal, index - 1), rate(gimbal, index)
        body_jump = math.degrees(magnitude(tuple(right - left for left, right in zip(body_left, body_right))))
        gimbal_jump = math.degrees(magnitude(tuple(right - left for left, right in zip(gimbal_left, gimbal_right))))
        flagged = (
            velocity_jump > thresholds.position_velocity_jump_cm_per_second
            or acceleration_jump > thresholds.position_acceleration_jump_cm_per_second_squared
            or body_jump > thresholds.authored_angular_rate_jump_degrees_per_second
            or gimbal_jump > thresholds.authored_angular_rate_jump_degrees_per_second
        )
        rows.append((document.waypoints[index].waypoint_id, velocity_jump, acceleration_jump, body_jump, gimbal_jump, flagged))
        count += int(flagged)
    return tuple(rows), count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_document_diagnostics_graph_contracts")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (148 if args.paste else 149), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_CallArrayFunction_0"]
    contracts.require(member(root) == "Array_Clear", "diagnostic execution root")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to diagnostic root")
    contracts.require("CameraTransform" not in text and "DraftDocumentV1" not in text, "legacy authorship forbidden")
    contracts.require(text.count('MemberName="Array_Clear"') == 6, "six owned output clears")
    contracts.require(text.count('MemberName="Array_Add"') == 6, "six aligned output appends")
    contracts.require(text.count('MemberName="ComputeOrientationLogDeltaV1"') == 4, "four authored-rate deltas")
    contracts.require(text.count("StandardMacros:ForEachLoop") == 1, "one ordered waypoint loop")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("AirframeDocumentDiagnosticsValidV2") == 2, "validity false first and true last")
    contracts.require(writes.count("AirframeDocumentDiagnosticStageValidV2") == 6, "diagnostic-local sticky validity")
    contracts.require(writes.count("OrientationInputStartQuatV1") == 4 and writes.count("OrientationInputEndQuatV1") == 4, "four primitive pairs")
    forbidden_writes = [name for name in writes if name and (
        name == "AirframeDocumentAdapterCompileValidV2"
        or name.startswith("AirframeSource")
        or name.startswith("AirframeDesired")
        or name.startswith("AirframePrebake")
        or name.startswith("PositionRoute")
    )]
    contracts.require(not forbidden_writes, f"authoritative mutation {forbidden_writes}")
    for name in OUTPUTS:
        contracts.require(text.count(f'MemberName="{name}"') >= 1, f"diagnostic output {name}")
    item_nodes = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    for source in ("AirframeDocumentInputWaypointBodyQuatsV2", "AirframeDocumentInputWaypointGimbalQuatsV2"):
        getter = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == source)
        authored_items = [node for node in item_nodes if contracts.linked(getter, source, node, "Array")]
        contracts.require(len(authored_items) == 3, f"three independent {source} reads")
    contracts.require('MemberName="PositionRouteCompiledWaypointVelocitiesV1"' in text, "accepted position derivative source")
    primitive_valid = next(node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == "OrientationResultValidV1")
    primitive_guards = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class and contracts.linked(primitive_valid, "OrientationResultValidV1", node, "Condition")]
    contracts.require(len(primitive_guards) == 4, "every primitive call is fail-closed")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _pin in pin.links if target not in known}
    contracts.require(not external, f"external links {external}")

    trajectory_root = args.project_root / "tools/trajectory"
    sys.path.insert(0, str(trajectory_root))
    reference = load(trajectory_root / "compiled_document_source_adapter_reference.py", "edd_document_diagnostics_reference")
    cinematic = load(trajectory_root / "cinematic_reference.py", "edd_document_diagnostics_cinematic")
    orientation = load(trajectory_root / "orientation_reference.py", "edd_document_diagnostics_orientation")
    for index in range(60):
        document = make_case(reference, 0xEDD800 + index)
        rng = random.Random(0xEDD900 + index)
        thresholds = reference.DiscontinuityThresholdsV2(
            rng.choice((0.0, 1.0, 25.0, 1.0e9)),
            rng.choice((0.0, 1.0, 1.0e9)),
            rng.choice((0.0, 1.0, 30.0, 1.0e9)),
            1.0,
            1.0,
        )
        durations = tuple(item.duration_seconds for item in document.segments)
        position = cinematic.compile_trajectory(
            tuple(item.position for item in document.waypoints),
            tuple(cinematic.AuthoredSegment(item.duration_seconds, item.spatial_curve_type, item.time_profile) for item in document.segments),
        )
        body_track = orientation.compile_orientation_track(tuple(item.body_rotation for item in document.waypoints), durations)
        gimbal_track = orientation.compile_orientation_track(tuple(item.gimbal_rotation for item in document.waypoints), durations)
        expected = reference.build_discontinuity_diagnostics_v2(document, position, body_track, gimbal_track, thresholds)
        actual_rows, actual_count = blueprint_semantics(document, thresholds, cinematic, orientation)
        contracts.require(len(actual_rows) == len(expected.joins), f"row count {index}")
        for actual, wanted in zip(actual_rows, expected.joins):
            expected_row = (
                wanted.waypoint_id,
                wanted.position_velocity_jump_cm_per_second,
                wanted.position_acceleration_jump_cm_per_second_squared,
                wanted.authored_body_rate_jump_degrees_per_second,
                wanted.authored_gimbal_rate_jump_degrees_per_second,
                wanted.discontinuous,
            )
            contracts.require(actual[0] == expected_row[0] and actual[-1] == expected_row[-1], f"identity/flag {index}")
            contracts.require(all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12) for a, b in zip(actual[1:-1], expected_row[1:-1])), f"values {index}")
        contracts.require(actual_count == expected.discontinuity_count, f"discontinuity count {index}")
    print(f"Airframe document diagnostics contracts passed ({'paste' if args.paste else 'full'}): 60 seeded accepted documents, distinct authored rates, threshold-only warnings")


if __name__ == "__main__":
    main()
