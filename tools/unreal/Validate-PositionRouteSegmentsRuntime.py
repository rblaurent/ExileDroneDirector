"""Execute candidate position-segment assembly against the frozen oracle."""
from __future__ import annotations

import importlib
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_POSITION_ROUTE_SEGMENTS_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
POSITIONS = "PositionRouteInputWaypointPositionsV1"
DURATIONS = "PositionRouteInputDurationsV1"
CURVES = "PositionRouteInputSpatialCurveTypesV1"
VELOCITIES = "PositionRouteCandidateWaypointVelocitiesV1"
TOLERANCE = "PositionRouteInputArcToleranceV1"
DEPTH = "PositionRouteInputMaxArcDepthV1"
BUDGET = "PositionRouteInputMaxArcOperationsV1"
OUTPUT_ARRAYS = (
    "PositionRouteCandidateSegmentStartsV1",
    "PositionRouteCandidateArcSampleStartsV1",
    "PositionRouteCandidateArcSampleCountsV1",
    "PositionRouteCandidateArcUsV1",
    "PositionRouteCandidateArcDistancesV1",
    "PositionRouteCandidateSegmentLengthsV1",
)
OUTPUT_SCALARS = (
    "PositionRouteCandidateTotalSecondsV1",
    "PositionRouteCandidateTotalDistanceV1",
    "PositionRouteCandidateOperationCountV1",
)
VALID = "PositionRouteStageValidV1"
PRIMITIVE = (
    "TrajectoryArcBuildInputStartPositionV1",
    "TrajectoryArcBuildInputEndPositionV1",
    "TrajectoryArcBuildInputStartVelocityUV1",
    "TrajectoryArcBuildInputEndVelocityUV1",
    "TrajectoryArcBuildInputStartAccelerationUV1",
    "TrajectoryArcBuildInputEndAccelerationUV1",
    "TrajectoryArcBuildInputLinearV1",
    "TrajectoryArcBuildInputToleranceV1",
    "TrajectoryArcBuildInputMaxDepthV1",
    "TrajectoryArcBuildInputMaxOperationsV1",
    "TrajectoryArcBuiltUsV1",
    "TrajectoryArcBuiltDistancesV1",
    "TrajectoryArcBuiltLengthV1",
    "TrajectoryArcBuildValidV1",
    "TrajectoryArcBuildOperationCountV1",
)


def emit(label, value):
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition, message):
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def get(obj, name):
    for candidate in variants(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError(name)


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(name)


def vector(value):
    return unreal.Vector(*(float(component) for component in value))


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools/trajectory"))
import cinematic_reference as oracle
importlib.reload(oracle)


generated = unreal.load_class(None, CLASS)
require(generated is not None, "class")
obj = unreal.get_default_object(generated)
properties = (POSITIONS, DURATIONS, CURVES, VELOCITIES, TOLERANCE, DEPTH, BUDGET) + OUTPUT_ARRAYS + OUTPUT_SCALARS + (VALID,) + PRIMITIVE
saved = {name: get(obj, name) for name in properties}


def prepare(points, durations, curves, tolerance, depth, budget, stage=True, velocities=None):
    authored = tuple(oracle.AuthoredSegment(float(duration), curve, "linear") for duration, curve in zip(durations, curves))
    if velocities is None:
        velocities = oracle._auto_velocities(points, authored)
    set_(obj, POSITIONS, [vector(point) for point in points])
    set_(obj, DURATIONS, [float(value) for value in durations])
    set_(obj, CURVES, list(curves))
    set_(obj, VELOCITIES, [vector(value) for value in velocities])
    set_(obj, TOLERANCE, float(tolerance))
    set_(obj, DEPTH, int(depth))
    set_(obj, BUDGET, int(budget))
    for name in OUTPUT_ARRAYS:
        set_(obj, name, [99])
    set_(obj, OUTPUT_SCALARS[0], 99.0)
    set_(obj, OUTPUT_SCALARS[1], 99.0)
    set_(obj, OUTPUT_SCALARS[2], 99)
    set_(obj, VALID, bool(stage))
    return authored


def require_cleared(label):
    require(not bool(get(obj, VALID)), f"{label}:valid")
    require(all(len(get(obj, name)) == 0 for name in OUTPUT_ARRAYS), f"{label}:arrays")
    require(float(get(obj, OUTPUT_SCALARS[0])) == 0.0, f"{label}:seconds")
    require(float(get(obj, OUTPUT_SCALARS[1])) == 0.0, f"{label}:distance")
    require(int(get(obj, OUTPUT_SCALARS[2])) == 0, f"{label}:operations")


try:
    fixtures = [
        (((0, 0, 0), (10, 0, 0)), (2.0,), ("linear",), 0.01, 8),
        (((0, 0, 0), (10, 10, 0), (30, 5, 5)), (1.0, 2.0), ("auto_cinematic", "auto_cinematic"), 0.02, 8),
        (((0, 0, 0), (10, 0, 5), (20, 20, 0), (40, 25, -5)), (1.0, 3.0, 2.0), ("linear", "auto_cinematic", "auto_cinematic"), 0.1, 8),
    ]
    rng = random.Random(0xEDD074)
    for index in range(28):
        count = rng.randint(2, 12)
        point = [rng.uniform(-250.0, 250.0) for _ in range(3)]
        points = [tuple(point)]
        for _ in range(count - 1):
            point = [component + rng.uniform(-120.0, 120.0) for component in point]
            points.append(tuple(point))
        durations = tuple(rng.uniform(0.1, 4.0) for _ in range(count - 1))
        curves = tuple("linear" if rng.random() < 0.3 else "auto_cinematic" for _ in range(count - 1))
        tolerance = (0.02, 0.08, 0.25, 0.75)[index % 4]
        fixtures.append((tuple(points), durations, curves, tolerance, 8))
    max_count = 512
    max_points = tuple((float(index * 3), float(index % 17), float((index * 11) % 29)) for index in range(max_count))
    fixtures.append((max_points, tuple(0.5 + (index % 5) for index in range(max_count - 1)), tuple("linear" for _ in range(max_count - 1)), 0.01, 8))

    maximum_u_error = 0.0
    maximum_distance_error = 0.0
    maximum_length_error = 0.0
    segments_proved = 0
    samples_proved = 0
    for fixture_index, (points, durations, curves, tolerance, depth) in enumerate(fixtures):
        authored = prepare(points, durations, curves, tolerance, depth, 8191)
        compiled = oracle.compile_trajectory(points, authored, arc_tolerance=tolerance, max_arc_depth=depth)
        expected_starts = []
        expected_counts = []
        expected_us = []
        expected_distances = []
        expected_lengths = []
        expected_operations = 0
        flat_start = 0
        for segment in compiled.segments:
            table, operations = oracle.trace_arc_table_iterative(segment, tolerance, depth, 8191)
            expected_starts.append(flat_start)
            expected_counts.append(len(table))
            expected_us.extend(sample.u for sample in table)
            expected_distances.extend(sample.distance for sample in table)
            expected_lengths.append(table[-1].distance)
            expected_operations += operations
            flat_start += len(table)
        obj.call_method("BuildPositionRouteSegmentsV1")
        require(bool(get(obj, VALID)), f"valid:{fixture_index}")
        actual_segment_starts = [float(value) for value in get(obj, OUTPUT_ARRAYS[0])]
        actual_arc_starts = [int(value) for value in get(obj, OUTPUT_ARRAYS[1])]
        actual_counts = [int(value) for value in get(obj, OUTPUT_ARRAYS[2])]
        actual_us = [float(value) for value in get(obj, OUTPUT_ARRAYS[3])]
        actual_distances = [float(value) for value in get(obj, OUTPUT_ARRAYS[4])]
        actual_lengths = [float(value) for value in get(obj, OUTPUT_ARRAYS[5])]
        require(len(actual_segment_starts) == len(compiled.segments), f"segment starts count:{fixture_index}")
        require(actual_arc_starts == expected_starts, f"arc starts:{fixture_index}")
        require(actual_counts == expected_counts, f"arc counts:{fixture_index}")
        require(len(actual_us) == len(expected_us) and len(actual_distances) == len(expected_distances), f"flat cardinality:{fixture_index}")
        require(len(actual_lengths) == len(expected_lengths), f"length cardinality:{fixture_index}")
        for index, (actual, segment) in enumerate(zip(actual_segment_starts, compiled.segments)):
            require(abs(actual - segment.start_seconds) <= 2.0e-9, f"segment start:{fixture_index}:{index}")
        for index, (actual, expected) in enumerate(zip(actual_us, expected_us)):
            error = abs(actual - expected)
            maximum_u_error = max(maximum_u_error, error)
            require(error <= 2.0e-5, f"u:{fixture_index}:{index}:{error}")
        for index, (actual, expected) in enumerate(zip(actual_distances, expected_distances)):
            error = abs(actual - expected)
            maximum_distance_error = max(maximum_distance_error, error)
            require(error <= 3.0e-4, f"distance:{fixture_index}:{index}:{error}")
        for index, (actual, expected) in enumerate(zip(actual_lengths, expected_lengths)):
            error = abs(actual - expected)
            maximum_length_error = max(maximum_length_error, error)
            require(error <= 3.0e-4, f"length:{fixture_index}:{index}:{error}")
        require(abs(float(get(obj, OUTPUT_SCALARS[0])) - compiled.total_seconds) <= 2.0e-9, f"total seconds:{fixture_index}")
        total_distance_error = abs(float(get(obj, OUTPUT_SCALARS[1])) - sum(expected_lengths))
        require(total_distance_error <= max(3.0e-4, len(expected_lengths) * 3.0e-4), f"total distance:{fixture_index}:{total_distance_error}")
        require(int(get(obj, OUTPUT_SCALARS[2])) == expected_operations, f"operations:{fixture_index}")
        segments_proved += len(compiled.segments)
        samples_proved += len(expected_us)

    baseline = fixtures[0]
    prepare(*baseline, 8191, stage=False)
    obj.call_method("BuildPositionRouteSegmentsV1")
    require_cleared("prior-invalid")

    authored = tuple(oracle.AuthoredSegment(value, curve, "linear") for value, curve in zip(baseline[1], baseline[2]))
    malformed_velocities = oracle._auto_velocities(baseline[0], authored)[:-1]
    prepare(*baseline, 8191, stage=True, velocities=malformed_velocities)
    obj.call_method("BuildPositionRouteSegmentsV1")
    require_cleared("velocity-cardinality")

    early_points = ((0, 0, 0), (10, 10, 0), (30, 5, 0))
    early_durations = (1.0, 1.0)
    early_curves = ("auto_cinematic", "auto_cinematic")
    early_authored = prepare(early_points, early_durations, early_curves, 0.01, 8, 1)
    early_compiled = oracle.compile_trajectory(early_points, early_authored, arc_tolerance=0.01, max_arc_depth=8)
    require(oracle.trace_arc_table_iterative(early_compiled.segments[0], 0.01, 8, 8191)[1] > 1, "early failure fixture")
    obj.call_method("BuildPositionRouteSegmentsV1")
    require_cleared("early-primitive-failure")

    # The exact linear fast path consumes one operation and publishes two arc
    # endpoints. Follow it with a sharply curved segment that provably needs
    # more work. This exercises deterministic prefix publication at the new
    # resource boundary without weakening the nonlinear budget contract.
    late_points = ((0, 0, 0), (10, 0, 0), (20, 1000, 0), (30, -1000, 0))
    late_durations = (1.0, 1.0, 1.0)
    late_curves = ("linear", "auto_cinematic", "auto_cinematic")
    late_tolerance = 0.00001
    late_authored = prepare(late_points, late_durations, late_curves, late_tolerance, 8, 8191)
    late_compiled = oracle.compile_trajectory(
        late_points, late_authored, arc_tolerance=late_tolerance, max_arc_depth=8
    )
    late_prefix, late_budget = oracle.trace_arc_table_iterative(
        late_compiled.segments[0], late_tolerance, 8, 8191
    )
    _late_failure, late_needed = oracle.trace_arc_table_iterative(
        late_compiled.segments[1], late_tolerance, 8, 8191
    )
    require(late_needed > late_budget, "late failure fixture")
    set_(obj, BUDGET, late_budget)
    obj.call_method("BuildPositionRouteSegmentsV1")
    require(not bool(get(obj, VALID)), "late failure validity")
    require([float(value) for value in get(obj, OUTPUT_ARRAYS[0])] == [0.0], "late segment prefix")
    require([int(value) for value in get(obj, OUTPUT_ARRAYS[1])] == [0], "late arc-start prefix")
    require([int(value) for value in get(obj, OUTPUT_ARRAYS[2])] == [len(late_prefix)], "late arc-count prefix")
    actual_late_us = [float(value) for value in get(obj, OUTPUT_ARRAYS[3])]
    actual_late_distances = [float(value) for value in get(obj, OUTPUT_ARRAYS[4])]
    require(len(actual_late_us) == len(late_prefix), "late u cardinality")
    require(len(actual_late_distances) == len(late_prefix), "late distance cardinality")
    require(
        all(abs(actual - expected.u) <= 2.0e-5 for actual, expected in zip(actual_late_us, late_prefix)),
        "late u prefix",
    )
    require(
        all(abs(actual - expected.distance) <= 3.0e-4 for actual, expected in zip(actual_late_distances, late_prefix)),
        "late distance prefix",
    )
    require(abs(float(get(obj, OUTPUT_ARRAYS[5])[0]) - late_prefix[-1].distance) <= 3.0e-4, "late length prefix")
    require(float(get(obj, OUTPUT_SCALARS[0])) == 1.0, "late seconds prefix")
    require(abs(float(get(obj, OUTPUT_SCALARS[1])) - late_prefix[-1].distance) <= 3.0e-4, "late total-distance prefix")
    require(int(get(obj, OUTPUT_SCALARS[2])) == late_budget, "late operation prefix")

    emit("VALID_ROUTES", len(fixtures))
    emit("SEGMENTS_PROVED", segments_proved)
    emit("ARC_SAMPLES_PROVED", samples_proved)
    emit("MAX_WAYPOINTS_PROVED", 512)
    emit("MAX_U_ERROR", maximum_u_error)
    emit("MAX_DISTANCE_ERROR", maximum_distance_error)
    emit("MAX_LENGTH_ERROR", maximum_length_error)
    emit("FAILURE_CASES", 4)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
