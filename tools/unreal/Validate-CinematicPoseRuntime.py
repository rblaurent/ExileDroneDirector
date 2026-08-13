"""Execute atomic cinematic-pose compile/evaluate transactions against the oracle."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_CINEMATIC_POSE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"

POSITION_INPUTS = (
    "PositionRouteInputWaypointPositionsV1",
    "PositionRouteInputDurationsV1",
    "PositionRouteInputSpatialCurveTypesV1",
    "PositionRouteInputTimeProfilesV1",
    "PositionRouteInputArcToleranceV1",
    "PositionRouteInputMaxArcDepthV1",
    "PositionRouteInputMaxArcOperationsV1",
)
ORIENTATION_INPUTS = (
    "OrientationTrackInputWaypointQuatsV1",
    "OrientationTrackInputDurationsV1",
)
POSITION_COMPILED = (
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
    "PositionRouteCompiledTotalSecondsV1",
    "PositionRouteCompiledTotalDistanceV1",
    "PositionRouteCompileValidV1",
)
ORIENTATION_COMPILED = (
    "OrientationTrackCompiledAlignedQuatsV1",
    "OrientationTrackCompiledDurationsV1",
    "OrientationTrackCompiledTangentRatesV1",
    "OrientationTrackCompiledSegmentStartsV1",
    "OrientationTrackCompiledStartControlsV1",
    "OrientationTrackCompiledEndControlsV1",
    "OrientationTrackCompiledTotalSecondsV1",
    "OrientationTrackCompileValidV1",
)
POSITION_RESULTS = (
    "PositionRouteInputElapsedSecondsV1",
    "PositionRouteResultSegmentIndexV1",
    "PositionRouteResultLocalTimeAlphaV1",
    "PositionRouteResultDistanceAlphaV1",
    "PositionRouteResultCurveUV1",
    "PositionRouteResultPositionV1",
    "PositionRouteResultCompleteV1",
    "PositionRouteResultValidV1",
)
ORIENTATION_RESULTS = (
    "OrientationTrackInputElapsedSecondsV1",
    "OrientationTrackResultSegmentIndexV1",
    "OrientationTrackResultAlphaV1",
    "OrientationTrackResultQuatV1",
    "OrientationTrackResultCompleteV1",
    "OrientationTrackResultValidV1",
)
POSE = (
    "CinematicPoseStageValidV1",
    "CinematicPoseCompiledTotalSecondsV1",
    "CinematicPoseCompileValidV1",
    "CinematicPoseInputElapsedSecondsV1",
    "CinematicPoseResultSegmentIndexV1",
    "CinematicPoseResultLocalTimeAlphaV1",
    "CinematicPoseResultDistanceAlphaV1",
    "CinematicPoseResultCurveUV1",
    "CinematicPoseResultPositionV1",
    "CinematicPoseResultQuatV1",
    "CinematicPoseResultCompleteV1",
    "CinematicPoseResultValidV1",
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


def quat(value):
    return unreal.Quat(*(float(component) for component in value))


def xyz(value):
    return float(value.x), float(value.y), float(value.z)


def qtuple(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def close(left, right, tolerance=2.0e-6):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def vector_close(left, right, tolerance=4.0e-5):
    return all(close(a, b, tolerance) for a, b in zip(left, right))


def angular_error(left, right):
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    require(left_length > 1.0e-12 and right_length > 1.0e-12, "zero quaternion")
    dot = abs(sum(a * b for a, b in zip(left, right)) / (left_length * right_length))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


def normalized(value):
    if isinstance(value, (list, tuple)):
        return tuple(normalized(item) for item in value)
    if hasattr(value, "w") and hasattr(value, "x"):
        return qtuple(value)
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return xyz(value)
    if isinstance(value, float):
        return float(value)
    return value


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import cinematic_pose_reference as pose_oracle
import cinematic_reference as position_oracle
import orientation_reference as orientation_oracle


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
properties = POSITION_INPUTS + ORIENTATION_INPUTS + POSITION_COMPILED + ORIENTATION_COMPILED + POSITION_RESULTS + ORIENTATION_RESULTS + POSE
saved = {name: get(obj, name) for name in properties}


def fixture(points, rotations, durations, curves, profiles, tolerance=0.01, depth=8, operations=8191):
    return (
        tuple(points),
        tuple(rotations),
        tuple(float(value) for value in durations),
        tuple(curves),
        tuple(profiles),
        float(tolerance),
        int(depth),
        int(operations),
    )


def stage(value):
    points, rotations, durations, curves, profiles, tolerance, depth, operations = value
    set_(obj, POSITION_INPUTS[0], [vector(item) for item in points])
    set_(obj, POSITION_INPUTS[1], list(durations))
    set_(obj, POSITION_INPUTS[2], list(curves))
    set_(obj, POSITION_INPUTS[3], list(profiles))
    set_(obj, POSITION_INPUTS[4], tolerance)
    set_(obj, POSITION_INPUTS[5], depth)
    set_(obj, POSITION_INPUTS[6], operations)
    set_(obj, ORIENTATION_INPUTS[0], [quat(item) for item in rotations])
    set_(obj, ORIENTATION_INPUTS[1], list(durations))


def compile_pose(value):
    stage(value)
    obj.call_method("CompileCinematicPoseV1")


def expected_pose(value):
    points, rotations, durations, curves, profiles, tolerance, depth, _operations = value
    authored = tuple(
        position_oracle.AuthoredSegment(duration, curve, profile)
        for duration, curve, profile in zip(durations, curves, profiles)
    )
    return pose_oracle.compile_cinematic_pose(
        points,
        rotations,
        authored,
        arc_tolerance=tolerance,
        max_arc_depth=depth,
    )


def compiled_snapshot():
    return {name: normalized(get(obj, name)) for name in POSITION_COMPILED + ORIENTATION_COMPILED}


def input_snapshot():
    return {name: normalized(get(obj, name)) for name in POSITION_INPUTS + ORIENTATION_INPUTS}


def pose_compile_snapshot():
    return (
        bool(get(obj, "CinematicPoseStageValidV1")),
        float(get(obj, "CinematicPoseCompiledTotalSecondsV1")),
        bool(get(obj, "CinematicPoseCompileValidV1")),
    )


def result_snapshot():
    return (
        int(get(obj, "CinematicPoseResultSegmentIndexV1")),
        float(get(obj, "CinematicPoseResultLocalTimeAlphaV1")),
        float(get(obj, "CinematicPoseResultDistanceAlphaV1")),
        float(get(obj, "CinematicPoseResultCurveUV1")),
        xyz(get(obj, "CinematicPoseResultPositionV1")),
        qtuple(get(obj, "CinematicPoseResultQuatV1")),
        bool(get(obj, "CinematicPoseResultCompleteV1")),
        bool(get(obj, "CinematicPoseResultValidV1")),
    )


def prefill_pose():
    values = (91, 0.91, 0.82, 0.73, vector((9, 8, 7)), quat((1, 0, 0, 0)), True, True)
    for name, value in zip(POSE[4:], values):
        set_(obj, name, value)


def require_result_cleared(label):
    result = result_snapshot()
    require(result[0] == -1, label + ":segment")
    require(result[1:4] == (0.0, 0.0, 0.0), label + ":alphas")
    require(result[4] == (0.0, 0.0, 0.0), label + ":position")
    require(result[5] == (0.0, 0.0, 0.0, 1.0), label + ":quat")
    require(result[6:] == (False, False), label + ":flags")


def require_compile_failed(label):
    stage_valid, total, compile_valid = pose_compile_snapshot()
    require(not stage_valid, label + ":stage")
    require(total == 0.0, label + ":total")
    require(not compile_valid, label + ":valid")
    require_result_cleared(label)


def evaluate(elapsed):
    set_(obj, "CinematicPoseInputElapsedSecondsV1", float(elapsed))
    obj.call_method("EvaluateCompiledCinematicPoseV1")
    return result_snapshot()


def mutate_list(name, mutate):
    value = list(get(obj, name))
    mutate(value)
    set_(obj, name, value)


try:
    rng = random.Random(0xEDD081)
    fixtures = [
        fixture(((0, 0, 0), (10, 0, 0)), ((0, 0, 0, 1), (0, 0, 1, 0)), (2.0,), ("linear",), ("linear",)),
        fixture(
            ((1, 2, 3), (5, 8, 1), (12, 3, 7), (20, 10, -2)),
            ((0, 0, 0, 1), (0.1, 0.3, 0.2, 0.9), (-0.2, 0.4, 0.1, 0.8), (0.4, -0.1, 0.2, 0.7)),
            (0.3, 2.7, 1.1),
            ("auto_cinematic",) * 3,
            ("accelerate_through", "brake_into", "smootherstep"),
            0.02,
        ),
    ]
    profiles = tuple(position_oracle.SUPPORTED_TIME_PROFILES)
    for _case in range(10):
        count = rng.randint(2, 18)
        points = []
        cursor = [0.0, 0.0, 0.0]
        for _index in range(count):
            cursor = [cursor[axis] + rng.uniform(-30, 30) for axis in range(3)]
            points.append(tuple(cursor))
        rotations = [tuple(rng.uniform(-3, 3) for _ in range(4)) for _ in range(count)]
        durations = [rng.uniform(0.04, 4.0) for _ in range(count - 1)]
        curves = [rng.choice(("linear", "auto_cinematic")) for _ in durations]
        time_profiles = [rng.choice(profiles) for _ in durations]
        fixtures.append(fixture(points, rotations, durations, curves, time_profiles, 0.02))
    fixtures.append(
        fixture(
            tuple((float(index), float(index % 7), 0.0) for index in range(512)),
            tuple((0.0, 0.0, 0.0, 1.0) for _ in range(512)),
            (0.05,) * 511,
            ("linear",) * 511,
            ("linear",) * 511,
        )
    )

    evaluations = 0
    scrub_cases = 0
    maximum_position_error = 0.0
    maximum_angular_error = 0.0
    maximum_alpha_error = 0.0
    for fixture_index, value in enumerate(fixtures):
        expected = expected_pose(value)
        stage(value)
        authored_before = input_snapshot()
        compile_pose(value)
        require(bool(get(obj, "CinematicPoseStageValidV1")), f"stage-valid:{fixture_index}")
        require(bool(get(obj, "CinematicPoseCompileValidV1")), f"compile-valid:{fixture_index}")
        require(close(get(obj, "CinematicPoseCompiledTotalSecondsV1"), expected.total_seconds, 2.0e-9), f"total:{fixture_index}")
        require(input_snapshot() == authored_before, f"authored mutation:{fixture_index}")
        compiled_before = compiled_snapshot()
        compile_pose(value)
        require(compiled_snapshot() == compiled_before, f"compile nondeterminism:{fixture_index}")

        samples = [-5.0, 0.0, expected.total_seconds, expected.total_seconds + 5.0]
        for segment in expected.position.segments:
            samples.extend((
                segment.start_seconds,
                segment.start_seconds + segment.duration_seconds * 0.25,
                segment.start_seconds + segment.duration_seconds * 0.5,
                segment.start_seconds + segment.duration_seconds - 1.0e-9,
                segment.start_seconds + segment.duration_seconds,
            ))
        samples.extend(rng.uniform(-1.0, expected.total_seconds + 1.0) for _ in range(12))
        for sample_index, elapsed in enumerate(samples):
            oracle = pose_oracle.evaluate_cinematic_pose(expected, elapsed)
            actual = evaluate(elapsed)
            require(actual[7], f"evaluate-valid:{fixture_index}:{sample_index}")
            require(actual[6] == oracle.complete, f"complete:{fixture_index}:{sample_index}")
            require(actual[0] == oracle.segment_index, f"segment:{fixture_index}:{sample_index}")
            maximum_alpha_error = max(maximum_alpha_error, abs(actual[1] - oracle.local_time_alpha))
            require(close(actual[1], oracle.local_time_alpha, 2.0e-8), f"local-alpha:{fixture_index}:{sample_index}")
            require(close(actual[2], oracle.distance_alpha, 2.0e-8), f"distance-alpha:{fixture_index}:{sample_index}")
            require(close(actual[3], oracle.curve_u, 4.0e-6), f"curve-u:{fixture_index}:{sample_index}")
            position_error = max(abs(a - b) for a, b in zip(actual[4], oracle.position))
            maximum_position_error = max(maximum_position_error, position_error)
            require(vector_close(actual[4], oracle.position), f"position:{fixture_index}:{sample_index}:{position_error}")
            angle = angular_error(actual[5], oracle.rotation)
            maximum_angular_error = max(maximum_angular_error, angle)
            require(angle <= 1.0e-6, f"rotation:{fixture_index}:{sample_index}:{angle}")
            require(compiled_snapshot() == compiled_before, f"evaluation source mutation:{fixture_index}:{sample_index}")
            evaluations += 1

        target = rng.uniform(0.0, expected.total_seconds)
        first = evaluate(target)
        shuffled = list(samples)
        rng.shuffle(shuffled)
        for elapsed in shuffled[: min(24, len(shuffled))]:
            evaluate(elapsed)
        second = evaluate(target)
        require(first == second, f"direct scrub:{fixture_index}")
        scrub_cases += 1

    base = fixtures[1]
    compile_invalid = []
    points, rotations, durations, curves, profiles, tolerance, depth, operations = base
    compile_invalid.extend((
        ("waypoint-count-mismatch", fixture(points, rotations[:-1], durations, curves, profiles, tolerance, depth, operations)),
        ("below-minimum", fixture(points[:1], rotations[:1], (), (), (), tolerance, depth, operations)),
        ("position-duration-shape", fixture(points, rotations, durations[:-1], curves, profiles, tolerance, depth, operations)),
        ("orientation-duration-shape", base),
        ("duration-value-mismatch", base),
        ("unknown-curve", fixture(points, rotations, durations, ("not_a_curve",) + curves[1:], profiles, tolerance, depth, operations)),
        ("unknown-profile", fixture(points, rotations, durations, curves, ("not_a_profile",) + profiles[1:], tolerance, depth, operations)),
    ))
    compile_failures = 0
    for label, value in compile_invalid:
        stage(value)
        if label == "orientation-duration-shape":
            set_(obj, ORIENTATION_INPUTS[1], list(durations[:-1]))
        elif label == "duration-value-mismatch":
            changed = list(durations)
            changed[0] += 0.125
            set_(obj, ORIENTATION_INPUTS[1], changed)
        prefill_pose()
        set_(obj, "CinematicPoseCompiledTotalSecondsV1", 99.0)
        set_(obj, "CinematicPoseCompileValidV1", True)
        obj.call_method("CompileCinematicPoseV1")
        require_compile_failed(label)
        compile_failures += 1

    too_many = fixture(
        tuple((float(index), 0.0, 0.0) for index in range(513)),
        tuple((0.0, 0.0, 0.0, 1.0) for _ in range(513)),
        (0.05,) * 512,
        ("linear",) * 512,
        ("linear",) * 512,
    )
    stage(too_many)
    prefill_pose()
    obj.call_method("CompileCinematicPoseV1")
    require_compile_failed("above-maximum")
    compile_failures += 1

    commit_failures = 0
    commit_cases = (
        ("position-invalid", "PositionRouteCompileValidV1", False),
        ("orientation-invalid", "OrientationTrackCompileValidV1", False),
        ("total-mismatch", "OrientationTrackCompiledTotalSecondsV1", 99.0),
        ("duration-cardinality", "OrientationTrackCompiledDurationsV1", lambda values: values[:-1]),
        ("start-cardinality", "OrientationTrackCompiledSegmentStartsV1", lambda values: values[:-1]),
        ("duration-mismatch", "OrientationTrackCompiledDurationsV1", lambda values: [values[0] + 0.125] + values[1:]),
        ("start-mismatch", "OrientationTrackCompiledSegmentStartsV1", lambda values: [values[0] + 0.125] + values[1:]),
    )
    for label, name, bad in commit_cases:
        compile_pose(base)
        require(bool(get(obj, "CinematicPoseCompileValidV1")), label + ":precondition")
        if callable(bad):
            set_(obj, name, bad(list(get(obj, name))))
        else:
            set_(obj, name, bad)
        component_before = compiled_snapshot()
        set_(obj, "CinematicPoseStageValidV1", True)
        set_(obj, "CinematicPoseCompiledTotalSecondsV1", 99.0)
        set_(obj, "CinematicPoseCompileValidV1", True)
        prefill_pose()
        obj.call_method("CommitCompiledCinematicPoseV1")
        require_compile_failed("commit-" + label)
        require(compiled_snapshot() == component_before, "commit source mutation:" + label)
        commit_failures += 1

    evaluate_failures = 0
    evaluate_cases = (
        ("combined-invalid", "CinematicPoseCompileValidV1", False),
        ("position-invalid", "PositionRouteCompileValidV1", False),
        ("orientation-invalid", "OrientationTrackCompileValidV1", False),
        ("combined-total-zero", "CinematicPoseCompiledTotalSecondsV1", 0.0),
        ("position-total-mismatch", "PositionRouteCompiledTotalSecondsV1", 99.0),
        ("orientation-total-mismatch", "OrientationTrackCompiledTotalSecondsV1", 99.0),
        ("orientation-duration-mismatch", "OrientationTrackCompiledDurationsV1", lambda values: [values[0] + 0.125] + values[1:]),
        ("orientation-start-mismatch", "OrientationTrackCompiledSegmentStartsV1", lambda values: [values[0] + 0.125] + values[1:]),
    )
    for label, name, bad in evaluate_cases:
        compile_pose(base)
        if callable(bad):
            set_(obj, name, bad(list(get(obj, name))))
        else:
            set_(obj, name, bad)
        component_before = compiled_snapshot()
        prefill_pose()
        evaluate(0.2)
        require_result_cleared("evaluate-" + label)
        require(compiled_snapshot() == component_before, "evaluate source mutation:" + label)
        evaluate_failures += 1

    nonfinite = 0
    for label, elapsed in (("elapsed-nan", float("nan")), ("elapsed-inf", float("inf")), ("elapsed-negative-inf", float("-inf"))):
        compile_pose(base)
        prefill_pose()
        set_(obj, "CinematicPoseInputElapsedSecondsV1", elapsed)
        staged = float(get(obj, "CinematicPoseInputElapsedSecondsV1"))
        if math.isfinite(staged):
            emit("REFLECTION_SANITIZED", label)
            continue
        component_before = compiled_snapshot()
        obj.call_method("EvaluateCompiledCinematicPoseV1")
        require_result_cleared(label)
        require(compiled_snapshot() == component_before, label + ":source mutation")
        nonfinite += 1

    emit("VALID_POSES", len(fixtures))
    emit("EVALUATIONS", evaluations)
    emit("DIRECT_SCRUB_CASES", scrub_cases)
    emit("MAX_WAYPOINTS", 512)
    emit("COMPILE_FAILURE_CASES", compile_failures)
    emit("COMMIT_FAILURE_CASES", commit_failures)
    emit("EVALUATE_FAILURE_CASES", evaluate_failures)
    emit("NONFINITE_REACHED_BLUEPRINT", nonfinite)
    emit("MAX_ALPHA_ERROR", maximum_alpha_error)
    emit("MAX_POSITION_ERROR", maximum_position_error)
    emit("MAX_ANGULAR_ERROR", maximum_angular_error)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
