"""Execute atomic position-route publication against valid and corrupted candidates."""
from __future__ import annotations

import importlib
import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_POSITION_ROUTE_COMMIT_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUT_ARRAYS = (
    "PositionRouteInputWaypointPositionsV1",
    "PositionRouteInputDurationsV1",
    "PositionRouteInputSpatialCurveTypesV1",
    "PositionRouteInputTimeProfilesV1",
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
)
CONTROL = "PositionRouteInputMaxArcOperationsV1"
STAGE = "PositionRouteStageValidV1"
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
properties = INPUT_ARRAYS + CANDIDATE_ARRAYS + CANDIDATE_SCALARS + (CONTROL, STAGE) + COMPILED_ARRAYS + COMPILED_SCALARS + EVALUATION
saved = {name: get(obj, name) for name in properties}


def prepare(points, durations, curves, profiles, tolerance=0.01, depth=8, max_operations=8191):
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
    operations = 0
    for segment in compiled.segments:
        table, segment_operations = oracle.trace_arc_table_iterative(segment, tolerance, depth, max_operations)
        starts.append(segment.start_seconds)
        arc_starts.append(len(arc_us))
        arc_counts.append(len(table))
        arc_us.extend(sample.u for sample in table)
        arc_distances.extend(sample.distance for sample in table)
        lengths.append(table[-1].distance)
        operations += segment_operations
    values = {
        INPUT_ARRAYS[0]: [vector(point) for point in points],
        INPUT_ARRAYS[1]: [float(value) for value in durations],
        INPUT_ARRAYS[2]: list(curves),
        INPUT_ARRAYS[3]: list(profiles),
        CANDIDATE_ARRAYS[0]: [vector(value) for value in velocities],
        CANDIDATE_ARRAYS[1]: starts,
        CANDIDATE_ARRAYS[2]: arc_starts,
        CANDIDATE_ARRAYS[3]: arc_counts,
        CANDIDATE_ARRAYS[4]: arc_us,
        CANDIDATE_ARRAYS[5]: arc_distances,
        CANDIDATE_ARRAYS[6]: lengths,
        CANDIDATE_SCALARS[0]: compiled.total_seconds,
        CANDIDATE_SCALARS[1]: sum(lengths),
        CANDIDATE_SCALARS[2]: operations,
        CONTROL: max_operations,
        STAGE: True,
    }
    for name, value in values.items():
        set_(obj, name, value)
    return values


def seed_stale_results():
    for index, name in enumerate(COMPILED_ARRAYS):
        if name in (COMPILED_ARRAYS[0], COMPILED_ARRAYS[4]):
            value = [vector((90 + index, 80 + index, 70 + index))]
        elif name in (COMPILED_ARRAYS[2], COMPILED_ARRAYS[3]):
            value = [f"stale-{index}"]
        else:
            value = [90 + index]
        set_(obj, name, value)
    set_(obj, COMPILED_SCALARS[0], 99.0)
    set_(obj, COMPILED_SCALARS[1], 98.0)
    set_(obj, COMPILED_SCALARS[2], True)
    set_(obj, EVALUATION[0], 17)
    set_(obj, EVALUATION[1], 0.25)
    set_(obj, EVALUATION[2], 0.5)
    set_(obj, EVALUATION[3], 0.75)
    set_(obj, EVALUATION[4], vector((1, 2, 3)))
    set_(obj, EVALUATION[5], True)
    set_(obj, EVALUATION[6], True)


def require_reset(label):
    require(all(len(get(obj, name)) == 0 for name in COMPILED_ARRAYS), f"{label}:compiled arrays")
    require(float(get(obj, COMPILED_SCALARS[0])) == 0.0, f"{label}:compiled seconds")
    require(float(get(obj, COMPILED_SCALARS[1])) == 0.0, f"{label}:compiled distance")
    require(not bool(get(obj, COMPILED_SCALARS[2])), f"{label}:compile valid")
    require(int(get(obj, EVALUATION[0])) == -1, f"{label}:result segment")
    require(float(get(obj, EVALUATION[1])) == 0.0, f"{label}:local alpha")
    require(float(get(obj, EVALUATION[2])) == 0.0, f"{label}:distance alpha")
    require(float(get(obj, EVALUATION[3])) == 0.0, f"{label}:curve u")
    require(xyz(get(obj, EVALUATION[4])) == (0.0, 0.0, 0.0), f"{label}:result position")
    require(not bool(get(obj, EVALUATION[5])) and not bool(get(obj, EVALUATION[6])), f"{label}:result flags")
    require(not bool(get(obj, STAGE)), f"{label}:sticky stage")


def require_real_array(name, expected, label, tolerance=2.0e-9):
    actual = [float(value) for value in get(obj, name)]
    require(len(actual) == len(expected), f"{label}:cardinality")
    require(all(abs(left - float(right)) <= tolerance for left, right in zip(actual, expected)), f"{label}:values")


def require_success(values, label):
    require(bool(get(obj, COMPILED_SCALARS[2])), f"{label}:compile valid")
    require(bool(get(obj, STAGE)), f"{label}:stage retained")
    actual_positions = [xyz(value) for value in get(obj, COMPILED_ARRAYS[0])]
    expected_positions = [xyz(value) for value in values[INPUT_ARRAYS[0]]]
    require(actual_positions == expected_positions, f"{label}:positions")
    require_real_array(COMPILED_ARRAYS[1], values[INPUT_ARRAYS[1]], f"{label}:durations")
    require(list(get(obj, COMPILED_ARRAYS[2])) == values[INPUT_ARRAYS[2]], f"{label}:curves")
    require(list(get(obj, COMPILED_ARRAYS[3])) == values[INPUT_ARRAYS[3]], f"{label}:profiles")
    actual_velocities = [xyz(value) for value in get(obj, COMPILED_ARRAYS[4])]
    expected_velocities = [xyz(value) for value in values[CANDIDATE_ARRAYS[0]]]
    require(actual_velocities == expected_velocities, f"{label}:velocities")
    require_real_array(COMPILED_ARRAYS[5], values[CANDIDATE_ARRAYS[1]], f"{label}:starts")
    require([int(value) for value in get(obj, COMPILED_ARRAYS[6])] == values[CANDIDATE_ARRAYS[2]], f"{label}:arc starts")
    require([int(value) for value in get(obj, COMPILED_ARRAYS[7])] == values[CANDIDATE_ARRAYS[3]], f"{label}:arc counts")
    require_real_array(COMPILED_ARRAYS[8], values[CANDIDATE_ARRAYS[4]], f"{label}:arc us", 2.0e-5)
    require_real_array(COMPILED_ARRAYS[9], values[CANDIDATE_ARRAYS[5]], f"{label}:arc distances", 3.0e-4)
    require_real_array(COMPILED_ARRAYS[10], values[CANDIDATE_ARRAYS[6]], f"{label}:lengths", 3.0e-4)
    require(abs(float(get(obj, COMPILED_SCALARS[0])) - float(values[CANDIDATE_SCALARS[0]])) <= 2.0e-9, f"{label}:total seconds")
    require(abs(float(get(obj, COMPILED_SCALARS[1])) - float(values[CANDIDATE_SCALARS[1]])) <= 3.0e-4 * max(1, len(values[CANDIDATE_ARRAYS[6]])), f"{label}:total distance")
    require(int(get(obj, EVALUATION[0])) == -1, f"{label}:result segment reset")
    require(float(get(obj, EVALUATION[1])) == 0.0 and float(get(obj, EVALUATION[2])) == 0.0 and float(get(obj, EVALUATION[3])) == 0.0, f"{label}:alphas reset")
    require(xyz(get(obj, EVALUATION[4])) == (0.0, 0.0, 0.0), f"{label}:position reset")
    require(not bool(get(obj, EVALUATION[5])) and not bool(get(obj, EVALUATION[6])), f"{label}:flags reset")


def snapshot(name):
    value = get(obj, name)
    if name in (INPUT_ARRAYS[0], CANDIDATE_ARRAYS[0]):
        return tuple(xyz(item) for item in value)
    if name in (INPUT_ARRAYS[2], INPUT_ARRAYS[3]):
        return tuple(str(item) for item in value)
    if name in (CANDIDATE_ARRAYS[2], CANDIDATE_ARRAYS[3]):
        return tuple(int(item) for item in value)
    if name in INPUT_ARRAYS + CANDIDATE_ARRAYS:
        return tuple(float(item) for item in value)
    if name == CANDIDATE_SCALARS[2]:
        return int(value)
    return float(value)


def fail_case(label, base, mutate):
    values = prepare(*base)
    mutate(values)
    seed_stale_results()
    obj.call_method("CommitCompiledPositionRouteV1")
    require_reset(label)


try:
    fixtures = [
        (((0, 0, 0), (10, 0, 0)), (2.0,), ("linear",), ("linear",)),
        (((0, 0, 0), (10, 10, 0), (30, 5, 5)), (1.0, 2.0), ("auto_cinematic", "auto_cinematic"), ("smoothstep", "cinematic_s_curve")),
        (((0, 0, 0), (10, 0, 5), (20, 20, 0), (40, 25, -5)), (1.0, 3.0, 2.0), ("linear", "auto_cinematic", "auto_cinematic"), ("accelerate_through", "smootherstep", "brake_into")),
    ]
    rng = random.Random(0xEDD075)
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
        fixtures.append((tuple(points), durations, curves, time_profiles))
    max_points = tuple((float(index * 3), float(index % 17), float((index * 11) % 29)) for index in range(512))
    fixtures.append((max_points, tuple(0.5 + (index % 5) for index in range(511)), tuple("linear" for _ in range(511)), tuple(profiles[index % len(profiles)] for index in range(511))))

    segments_proved = 0
    samples_proved = 0
    for index, fixture in enumerate(fixtures):
        values = prepare(*fixture)
        candidate_snapshot = {name: snapshot(name) for name in INPUT_ARRAYS + CANDIDATE_ARRAYS + CANDIDATE_SCALARS}
        seed_stale_results()
        obj.call_method("CommitCompiledPositionRouteV1")
        require_success(values, f"valid:{index}")
        for name, expected in candidate_snapshot.items():
            require(snapshot(name) == expected, f"valid:{index}:candidate unchanged:{name}")
        segments_proved += len(values[CANDIDATE_ARRAYS[1]])
        samples_proved += len(values[CANDIDATE_ARRAYS[4]])

    base = fixtures[1]
    failures = []

    def register(label, mutate):
        failures.append(label)
        fail_case(label, base, mutate)

    register("prior-invalid", lambda values: set_(obj, STAGE, False))
    for name in INPUT_ARRAYS + CANDIDATE_ARRAYS:
        register(f"cardinality:{name}", lambda values, field=name: set_(obj, field, list(get(obj, field))[:-1]))
    register("minimum-waypoints", lambda values: set_(obj, INPUT_ARRAYS[0], [vector((0, 0, 0))]))
    register("maximum-waypoints", lambda values: set_(obj, INPUT_ARRAYS[0], list(get(obj, INPUT_ARRAYS[0])) + [vector((99, 99, 99))] * 511))
    register("seconds-nan", lambda values: set_(obj, CANDIDATE_SCALARS[0], math.nan))
    register("seconds-zero", lambda values: set_(obj, CANDIDATE_SCALARS[0], 0.0))
    register("seconds-mismatch", lambda values: set_(obj, CANDIDATE_SCALARS[0], float(get(obj, CANDIDATE_SCALARS[0])) + 1.0))
    register("distance-nan", lambda values: set_(obj, CANDIDATE_SCALARS[1], math.nan))
    register("distance-negative", lambda values: set_(obj, CANDIDATE_SCALARS[1], -1.0))
    register("distance-mismatch", lambda values: set_(obj, CANDIDATE_SCALARS[1], float(get(obj, CANDIDATE_SCALARS[1])) + 1.0))
    register("operations-low", lambda values: set_(obj, CANDIDATE_SCALARS[2], 0))
    register("operations-high", lambda values: set_(obj, CANDIDATE_SCALARS[2], len(get(obj, INPUT_ARRAYS[1])) * int(get(obj, CONTROL)) + 1))
    register("segment-start", lambda values: set_(obj, CANDIDATE_ARRAYS[1], [1.0] + list(get(obj, CANDIDATE_ARRAYS[1]))[1:]))
    register("duration-zero", lambda values: set_(obj, INPUT_ARRAYS[1], [0.0] + list(get(obj, INPUT_ARRAYS[1]))[1:]))
    register("duration-nan", lambda values: set_(obj, INPUT_ARRAYS[1], [math.nan] + list(get(obj, INPUT_ARRAYS[1]))[1:]))
    register("arc-start", lambda values: set_(obj, CANDIDATE_ARRAYS[2], [1] + list(get(obj, CANDIDATE_ARRAYS[2]))[1:]))
    register("arc-count-small", lambda values: set_(obj, CANDIDATE_ARRAYS[3], [1] + list(get(obj, CANDIDATE_ARRAYS[3]))[1:]))
    register("arc-count-bounds", lambda values: set_(obj, CANDIDATE_ARRAYS[3], [len(get(obj, CANDIDATE_ARRAYS[4])) + 1] + list(get(obj, CANDIDATE_ARRAYS[3]))[1:]))
    register("segment-length-nan", lambda values: set_(obj, CANDIDATE_ARRAYS[6], [math.nan] + list(get(obj, CANDIDATE_ARRAYS[6]))[1:]))
    register("segment-length-negative", lambda values: set_(obj, CANDIDATE_ARRAYS[6], [-1.0] + list(get(obj, CANDIDATE_ARRAYS[6]))[1:]))
    register("u-start", lambda values: set_(obj, CANDIDATE_ARRAYS[4], [0.25] + list(get(obj, CANDIDATE_ARRAYS[4]))[1:]))
    first_end = int(prepare(*base)[CANDIDATE_ARRAYS[3]][0]) - 1
    register("u-end", lambda values: set_(obj, CANDIDATE_ARRAYS[4], list(get(obj, CANDIDATE_ARRAYS[4]))[:first_end] + [0.75] + list(get(obj, CANDIDATE_ARRAYS[4]))[first_end + 1:]))
    register("distance-start", lambda values: set_(obj, CANDIDATE_ARRAYS[5], [0.25] + list(get(obj, CANDIDATE_ARRAYS[5]))[1:]))
    register("distance-end", lambda values: set_(obj, CANDIDATE_ARRAYS[5], list(get(obj, CANDIDATE_ARRAYS[5]))[:first_end] + [float(get(obj, CANDIDATE_ARRAYS[5])[first_end]) + 1.0] + list(get(obj, CANDIDATE_ARRAYS[5]))[first_end + 1:]))
    def add_trailing_sample(_values):
        set_(obj, CANDIDATE_ARRAYS[4], list(get(obj, CANDIDATE_ARRAYS[4])) + [1.0])
        set_(obj, CANDIDATE_ARRAYS[5], list(get(obj, CANDIDATE_ARRAYS[5])) + [float(get(obj, CANDIDATE_ARRAYS[5])[-1])])

    register("flat-trailing-sample", add_trailing_sample)

    emit("VALID_ROUTES", len(fixtures))
    emit("SEGMENTS_PROVED", segments_proved)
    emit("ARC_SAMPLES_PROVED", samples_proved)
    emit("MAX_WAYPOINTS_PROVED", 512)
    emit("FAILURE_CASES", len(failures))
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
