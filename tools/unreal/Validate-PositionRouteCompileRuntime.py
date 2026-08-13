"""Execute the full position-route compiler against the frozen oracle."""
from __future__ import annotations

import importlib
import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_POSITION_ROUTE_COMPILE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUT_ARRAYS = (
    "PositionRouteInputWaypointPositionsV1",
    "PositionRouteInputDurationsV1",
    "PositionRouteInputSpatialCurveTypesV1",
    "PositionRouteInputTimeProfilesV1",
)
INPUT_SCALARS = (
    "PositionRouteInputArcToleranceV1",
    "PositionRouteInputMaxArcDepthV1",
    "PositionRouteInputMaxArcOperationsV1",
)
CANDIDATE_ARRAYS = (
    "PositionRouteCandidateWaypointVelocitiesV1",
    "PositionRouteCandidateSegmentStartsV1",
    "PositionRouteCandidateArcSampleStartsV1",
    "PositionRouteCandidateArcSampleCountsV1",
    "PositionRouteCandidateArcUsV1",
    "PositionRouteCandidateArcDistancesV1",
    "PositionRouteCandidateSegmentLengthsV1",
)
CANDIDATE_SCALARS = (
    "PositionRouteCandidateTotalSecondsV1",
    "PositionRouteCandidateTotalDistanceV1",
    "PositionRouteCandidateOperationCountV1",
    "PositionRouteStageValidV1",
)
COMPILED_ARRAYS = (
    "PositionRouteCompiledWaypointPositionsV1",
    "PositionRouteCompiledDurationsV1",
    "PositionRouteCompiledSpatialCurveTypesV1",
    "PositionRouteCompiledTimeProfilesV1",
    "PositionRouteCompiledWaypointVelocitiesV1",
    "PositionRouteCompiledSegmentStartsV1",
    "PositionRouteCompiledArcSampleStartsV1",
    "PositionRouteCompiledArcSampleCountsV1",
    "PositionRouteCompiledArcUsV1",
    "PositionRouteCompiledArcDistancesV1",
    "PositionRouteCompiledSegmentLengthsV1",
)
COMPILED_SCALARS = (
    "PositionRouteCompiledTotalSecondsV1",
    "PositionRouteCompiledTotalDistanceV1",
    "PositionRouteCompileValidV1",
)
EVALUATION = (
    "PositionRouteResultSegmentIndexV1",
    "PositionRouteResultLocalTimeAlphaV1",
    "PositionRouteResultDistanceAlphaV1",
    "PositionRouteResultCurveUV1",
    "PositionRouteResultPositionV1",
    "PositionRouteResultCompleteV1",
    "PositionRouteResultValidV1",
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


def xyz(value):
    return float(value.x), float(value.y), float(value.z)


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools/trajectory"))
import cinematic_reference as oracle
importlib.reload(oracle)


generated = unreal.load_class(None, CLASS)
require(generated is not None, "class")
obj = unreal.get_default_object(generated)
properties = INPUT_ARRAYS + INPUT_SCALARS + CANDIDATE_ARRAYS + CANDIDATE_SCALARS + COMPILED_ARRAYS + COMPILED_SCALARS + EVALUATION
saved = {name: get(obj, name) for name in properties}


def stage(fixture):
    points, durations, curves, profiles, tolerance, depth, operations = fixture
    values = {
        INPUT_ARRAYS[0]: [vector(point) for point in points],
        INPUT_ARRAYS[1]: [float(value) for value in durations],
        INPUT_ARRAYS[2]: list(curves),
        INPUT_ARRAYS[3]: list(profiles),
        INPUT_SCALARS[0]: float(tolerance),
        INPUT_SCALARS[1]: int(depth),
        INPUT_SCALARS[2]: int(operations),
    }
    for name, value in values.items():
        set_(obj, name, value)
    return values


def expected(fixture):
    points, durations, curves, profiles, tolerance, depth, operations = fixture
    authored = tuple(
        oracle.AuthoredSegment(float(duration), curve, profile)
        for duration, curve, profile in zip(durations, curves, profiles)
    )
    compiled = oracle.compile_trajectory(points, authored, arc_tolerance=tolerance, max_arc_depth=depth)
    velocities = oracle._auto_velocities(points, authored)
    starts = []
    arc_starts = []
    arc_counts = []
    arc_us = []
    arc_distances = []
    lengths = []
    operation_count = 0
    for segment in compiled.segments:
        table, segment_operations = oracle.trace_arc_table_iterative(segment, tolerance, depth, operations)
        starts.append(segment.start_seconds)
        arc_starts.append(len(arc_us))
        arc_counts.append(len(table))
        arc_us.extend(sample.u for sample in table)
        arc_distances.extend(sample.distance for sample in table)
        lengths.append(table[-1].distance)
        operation_count += segment_operations
    return {
        "points": points,
        "durations": durations,
        "curves": curves,
        "profiles": profiles,
        "velocities": velocities,
        "starts": starts,
        "arc_starts": arc_starts,
        "arc_counts": arc_counts,
        "arc_us": arc_us,
        "arc_distances": arc_distances,
        "lengths": lengths,
        "seconds": compiled.total_seconds,
        "distance": sum(lengths),
        "operations": operation_count,
    }


def poison():
    for index, name in enumerate(CANDIDATE_ARRAYS + COMPILED_ARRAYS):
        if "Positions" in name or "Velocities" in name:
            value = [vector((90 + index, 80 + index, 70 + index))]
        elif "CurveTypes" in name or "Profiles" in name:
            value = [f"stale-{index}"]
        else:
            value = [90 + index]
        set_(obj, name, value)
    set_(obj, CANDIDATE_SCALARS[0], 97.0)
    set_(obj, CANDIDATE_SCALARS[1], 96.0)
    set_(obj, CANDIDATE_SCALARS[2], 95)
    set_(obj, CANDIDATE_SCALARS[3], True)
    set_(obj, COMPILED_SCALARS[0], 94.0)
    set_(obj, COMPILED_SCALARS[1], 93.0)
    set_(obj, COMPILED_SCALARS[2], True)
    set_(obj, EVALUATION[0], 17)
    set_(obj, EVALUATION[1], 0.25)
    set_(obj, EVALUATION[2], 0.5)
    set_(obj, EVALUATION[3], 0.75)
    set_(obj, EVALUATION[4], vector((1, 2, 3)))
    set_(obj, EVALUATION[5], True)
    set_(obj, EVALUATION[6], True)


def close_array(name, wanted, label, tolerance=2.0e-9):
    actual = [float(value) for value in get(obj, name)]
    require(len(actual) == len(wanted), f"{label}:cardinality")
    require(all(abs(left - float(right)) <= tolerance for left, right in zip(actual, wanted)), f"{label}:values")


def require_success(wanted, label):
    require(bool(get(obj, CANDIDATE_SCALARS[3])) and bool(get(obj, COMPILED_SCALARS[2])), f"{label}:validity")
    input_positions = [xyz(value) for value in get(obj, INPUT_ARRAYS[0])]
    require(input_positions == [tuple(float(x) for x in value) for value in wanted["points"]], f"{label}:input positions")
    require([float(value) for value in get(obj, INPUT_ARRAYS[1])] == [float(value) for value in wanted["durations"]], f"{label}:input durations")
    require(list(get(obj, INPUT_ARRAYS[2])) == list(wanted["curves"]), f"{label}:input curves")
    require(list(get(obj, INPUT_ARRAYS[3])) == list(wanted["profiles"]), f"{label}:input profiles")

    expected_vectors = [tuple(float(x) for x in value) for value in wanted["velocities"]]
    require([xyz(value) for value in get(obj, CANDIDATE_ARRAYS[0])] == expected_vectors, f"{label}:candidate velocities")
    close_array(CANDIDATE_ARRAYS[1], wanted["starts"], f"{label}:candidate starts")
    require([int(value) for value in get(obj, CANDIDATE_ARRAYS[2])] == wanted["arc_starts"], f"{label}:candidate arc starts")
    require([int(value) for value in get(obj, CANDIDATE_ARRAYS[3])] == wanted["arc_counts"], f"{label}:candidate arc counts")
    close_array(CANDIDATE_ARRAYS[4], wanted["arc_us"], f"{label}:candidate arc us", 2.0e-5)
    close_array(CANDIDATE_ARRAYS[5], wanted["arc_distances"], f"{label}:candidate arc distances", 3.0e-4)
    close_array(CANDIDATE_ARRAYS[6], wanted["lengths"], f"{label}:candidate lengths", 3.0e-4)
    require(abs(float(get(obj, CANDIDATE_SCALARS[0])) - wanted["seconds"]) <= 2.0e-9, f"{label}:candidate seconds")
    require(abs(float(get(obj, CANDIDATE_SCALARS[1])) - wanted["distance"]) <= 3.0e-4 * max(1, len(wanted["lengths"])), f"{label}:candidate distance")
    require(int(get(obj, CANDIDATE_SCALARS[2])) == wanted["operations"], f"{label}:candidate operations")

    require([xyz(value) for value in get(obj, COMPILED_ARRAYS[0])] == [tuple(float(x) for x in value) for value in wanted["points"]], f"{label}:compiled positions")
    close_array(COMPILED_ARRAYS[1], wanted["durations"], f"{label}:compiled durations")
    require(list(get(obj, COMPILED_ARRAYS[2])) == list(wanted["curves"]), f"{label}:compiled curves")
    require(list(get(obj, COMPILED_ARRAYS[3])) == list(wanted["profiles"]), f"{label}:compiled profiles")
    require([xyz(value) for value in get(obj, COMPILED_ARRAYS[4])] == expected_vectors, f"{label}:compiled velocities")
    close_array(COMPILED_ARRAYS[5], wanted["starts"], f"{label}:compiled starts")
    require([int(value) for value in get(obj, COMPILED_ARRAYS[6])] == wanted["arc_starts"], f"{label}:compiled arc starts")
    require([int(value) for value in get(obj, COMPILED_ARRAYS[7])] == wanted["arc_counts"], f"{label}:compiled arc counts")
    close_array(COMPILED_ARRAYS[8], wanted["arc_us"], f"{label}:compiled arc us", 2.0e-5)
    close_array(COMPILED_ARRAYS[9], wanted["arc_distances"], f"{label}:compiled arc distances", 3.0e-4)
    close_array(COMPILED_ARRAYS[10], wanted["lengths"], f"{label}:compiled lengths", 3.0e-4)
    require(abs(float(get(obj, COMPILED_SCALARS[0])) - wanted["seconds"]) <= 2.0e-9, f"{label}:compiled seconds")
    require(abs(float(get(obj, COMPILED_SCALARS[1])) - wanted["distance"]) <= 3.0e-4 * max(1, len(wanted["lengths"])), f"{label}:compiled distance")
    require(int(get(obj, EVALUATION[0])) == -1, f"{label}:segment reset")
    require(all(float(get(obj, name)) == 0.0 for name in EVALUATION[1:4]), f"{label}:alpha reset")
    require(xyz(get(obj, EVALUATION[4])) == (0.0, 0.0, 0.0), f"{label}:position reset")
    require(not bool(get(obj, EVALUATION[5])) and not bool(get(obj, EVALUATION[6])), f"{label}:flags reset")


def require_failure(label):
    require(all(len(get(obj, name)) == 0 for name in CANDIDATE_ARRAYS + COMPILED_ARRAYS), f"{label}:arrays")
    require(float(get(obj, CANDIDATE_SCALARS[0])) == 0.0 and float(get(obj, CANDIDATE_SCALARS[1])) == 0.0, f"{label}:candidate totals")
    require(int(get(obj, CANDIDATE_SCALARS[2])) == 0 and not bool(get(obj, CANDIDATE_SCALARS[3])), f"{label}:candidate state")
    require(float(get(obj, COMPILED_SCALARS[0])) == 0.0 and float(get(obj, COMPILED_SCALARS[1])) == 0.0, f"{label}:compiled totals")
    require(not bool(get(obj, COMPILED_SCALARS[2])), f"{label}:compiled valid")
    require(int(get(obj, EVALUATION[0])) == -1, f"{label}:segment reset")
    require(all(float(get(obj, name)) == 0.0 for name in EVALUATION[1:4]), f"{label}:alpha reset")
    require(xyz(get(obj, EVALUATION[4])) == (0.0, 0.0, 0.0), f"{label}:position reset")
    require(not bool(get(obj, EVALUATION[5])) and not bool(get(obj, EVALUATION[6])), f"{label}:flags reset")


try:
    fixtures = [
        (((0, 0, 0), (10, 0, 0)), (2.0,), ("linear",), ("linear",), 0.01, 8, 8191),
        (((0, 0, 0), (10, 10, 0), (30, 5, 5)), (1.0, 2.0), ("auto_cinematic", "auto_cinematic"), ("smoothstep", "cinematic_s_curve"), 0.02, 8, 8191),
        (((0, 0, 0), (10, 0, 5), (20, 20, 0), (40, 25, -5)), (1.0, 3.0, 2.0), ("linear", "auto_cinematic", "auto_cinematic"), ("accelerate_through", "smootherstep", "brake_into"), 0.1, 8, 8191),
    ]
    rng = random.Random(0xEDD076)
    profiles = ("linear", "smoothstep", "smootherstep", "cinematic_s_curve", "accelerate_through", "brake_into")
    for fixture_index in range(20):
        count = rng.randint(2, 12)
        point = [rng.uniform(-250.0, 250.0) for _ in range(3)]
        points = [tuple(point)]
        for _ in range(count - 1):
            point = [component + rng.uniform(-120.0, 120.0) for component in point]
            points.append(tuple(point))
        durations = tuple(rng.uniform(0.1, 4.0) for _ in range(count - 1))
        curves = tuple("linear" if rng.random() < 0.3 else "auto_cinematic" for _ in range(count - 1))
        time_profiles = tuple(profiles[(fixture_index + index) % len(profiles)] for index in range(count - 1))
        fixtures.append((tuple(points), durations, curves, time_profiles, (0.02, 0.08, 0.25)[fixture_index % 3], 8, 8191))
    max_points = tuple((float(index * 3), float(index % 17), float((index * 11) % 29)) for index in range(512))
    fixtures.append((max_points, tuple(0.5 + (index % 5) for index in range(511)), tuple("linear" for _ in range(511)), tuple(profiles[index % len(profiles)] for index in range(511)), 0.01, 8, 8191))

    segments_proved = 0
    samples_proved = 0
    prior_compiled = None
    for index, fixture in enumerate(fixtures):
        input_values = stage(fixture)
        wanted = expected(fixture)
        poison()
        obj.call_method("CompilePositionRouteV1")
        require_success(wanted, f"valid:{index}")
        require([xyz(value) for value in get(obj, INPUT_ARRAYS[0])] == [xyz(value) for value in input_values[INPUT_ARRAYS[0]]], f"valid:{index}:inputs unchanged")
        current = tuple(float(value) for value in get(obj, COMPILED_ARRAYS[9]))
        if prior_compiled is not None and index == 1:
            require(current != prior_compiled, "replacement")
        prior_compiled = current
        segments_proved += len(wanted["starts"])
        samples_proved += len(wanted["arc_us"])

    base = fixtures[1]
    invalid = []

    def reject(label, fixture):
        invalid.append(label)
        stage(fixture)
        poison()
        obj.call_method("CompilePositionRouteV1")
        require_failure(label)

    points, durations, curves, time_profiles, tolerance, depth, operations = base
    reject("one-waypoint", ((points[0],), (), (), (), tolerance, depth, operations))
    reject("duration-cardinality", (points, durations[:-1], curves, time_profiles, tolerance, depth, operations))
    reject("curve-cardinality", (points, durations, curves[:-1], time_profiles, tolerance, depth, operations))
    reject("profile-cardinality", (points, durations, curves, time_profiles[:-1], tolerance, depth, operations))
    reject("tolerance-zero", (points, durations, curves, time_profiles, 0.0, depth, operations))
    reject("tolerance-nan", (points, durations, curves, time_profiles, math.nan, depth, operations))
    reject("depth-low", (points, durations, curves, time_profiles, tolerance, 0, operations))
    reject("depth-high", (points, durations, curves, time_profiles, tolerance, 13, operations))
    reject("operations-low", (points, durations, curves, time_profiles, tolerance, depth, 0))
    reject("operations-high", (points, durations, curves, time_profiles, tolerance, depth, 8192))
    reject("duration-zero", (points, (0.0,) + durations[1:], curves, time_profiles, tolerance, depth, operations))
    reject("duration-nan", (points, (math.nan,) + durations[1:], curves, time_profiles, tolerance, depth, operations))
    reject("curve-invalid", (points, durations, ("bad",) + curves[1:], time_profiles, tolerance, depth, operations))
    reject("profile-invalid", (points, durations, curves, ("bad",) + time_profiles[1:], tolerance, depth, operations))

    emit("VALID_ROUTES", len(fixtures))
    emit("SEGMENTS_PROVED", segments_proved)
    emit("ARC_SAMPLES_PROVED", samples_proved)
    emit("MAX_WAYPOINTS_PROVED", 512)
    emit("INVALID_CASES", len(invalid))
    emit("REPLACEMENT_CASES", 1)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
