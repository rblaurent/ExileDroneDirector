"""Execute absolute-time compiled orientation evaluation against the frozen oracle."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_ORIENTATION_TRACK_EVALUATOR_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUTS = ("OrientationTrackInputWaypointQuatsV1", "OrientationTrackInputDurationsV1")
COMPILED = (
    "OrientationTrackCompiledAlignedQuatsV1",
    "OrientationTrackCompiledDurationsV1",
    "OrientationTrackCompiledTangentRatesV1",
    "OrientationTrackCompiledSegmentStartsV1",
    "OrientationTrackCompiledStartControlsV1",
    "OrientationTrackCompiledEndControlsV1",
    "OrientationTrackCompiledTotalSecondsV1",
    "OrientationTrackCompileValidV1",
)
RESULTS = (
    "OrientationTrackInputElapsedSecondsV1",
    "OrientationTrackResultSegmentIndexV1",
    "OrientationTrackResultAlphaV1",
    "OrientationTrackResultQuatV1",
    "OrientationTrackResultCompleteV1",
    "OrientationTrackResultValidV1",
)
PRIMITIVE = (
    "TrajectoryInputOrientationStartQuatV1",
    "TrajectoryInputOrientationStartControlQuatV1",
    "TrajectoryInputOrientationEndControlQuatV1",
    "TrajectoryInputOrientationEndQuatV1",
    "TrajectoryInputAlphaV1",
    "TrajectoryResultOrientationQuatV1",
    "TrajectoryResultOrientationValidV1",
)


def emit(name, value):
    unreal.log(f"{PREFIX}|{name}|{value}")


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


def quat(value):
    return unreal.Quat(*(float(component) for component in value))


def qtuple(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def angular_error(left, right):
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    require(left_length > 1.0e-12 and right_length > 1.0e-12, "angular error received zero quaternion")
    dot = abs(sum(a * b for a, b in zip(left, right)) / (left_length * right_length))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import orientation_reference as oracle


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
properties = INPUTS + COMPILED + RESULTS + PRIMITIVE
saved = {name: get(obj, name) for name in properties}


def compile_track(rotations, durations):
    set_(obj, INPUTS[0], [quat(value) for value in rotations])
    set_(obj, INPUTS[1], [float(value) for value in durations])
    obj.call_method("CompileOrientationTrackV1")
    require(bool(get(obj, COMPILED[7])), "compile precondition")


def evaluate(elapsed):
    set_(obj, RESULTS[0], float(elapsed))
    obj.call_method("EvaluateCompiledOrientationTrackV1")
    return (
        int(get(obj, RESULTS[1])),
        float(get(obj, RESULTS[2])),
        qtuple(get(obj, RESULTS[3])),
        bool(get(obj, RESULTS[4])),
        bool(get(obj, RESULTS[5])),
    )


def prefill_stale():
    set_(obj, RESULTS[1], 91)
    set_(obj, RESULTS[2], 0.75)
    set_(obj, RESULTS[3], quat((1.0, 0.0, 0.0, 0.0)))
    set_(obj, RESULTS[4], True)
    set_(obj, RESULTS[5], True)
    set_(obj, PRIMITIVE[5], quat((1.0, 0.0, 0.0, 0.0)))
    set_(obj, PRIMITIVE[6], True)


def require_cleared(label):
    require(int(get(obj, RESULTS[1])) == -1, label + ":segment")
    require(float(get(obj, RESULTS[2])) == 0.0, label + ":alpha")
    require(qtuple(get(obj, RESULTS[3])) == (0.0, 0.0, 0.0, 1.0), label + ":quat")
    require(not bool(get(obj, RESULTS[4])) and not bool(get(obj, RESULTS[5])), label + ":flags")
    require(qtuple(get(obj, PRIMITIVE[5])) == (0.0, 0.0, 0.0, 1.0), label + ":primitive-quat")
    require(not bool(get(obj, PRIMITIVE[6])), label + ":primitive-valid")


try:
    rng = random.Random(0xEDD066)
    fixtures = []
    for _ in range(32):
        rotations = [tuple(rng.uniform(-4.0, 4.0) for _ in range(4)) for _ in range(rng.randint(2, 40))]
        durations = [rng.uniform(0.02, 8.0) for _ in range(len(rotations) - 1)]
        fixtures.append((rotations, durations, oracle.compile_orientation_track(rotations, durations)))

    maximum_angle = 0.0
    maximum_alpha = 0.0
    evaluations = 0
    scrub_cases = 0
    for fixture_index, (rotations, durations, track) in enumerate(fixtures):
        compile_track(rotations, durations)
        samples = [-3.0, 0.0, track.total_seconds, track.total_seconds + 3.0]
        for segment in track.segments:
            samples.extend((
                segment.start_seconds,
                segment.start_seconds + min(segment.duration_seconds * 0.5, 0.25),
                segment.start_seconds + segment.duration_seconds,
            ))
            if segment.duration_seconds > 2.0e-8:
                samples.append(segment.start_seconds + segment.duration_seconds - 1.0e-9)
        samples.extend(rng.uniform(-1.0, track.total_seconds + 1.0) for _ in range(12))
        for sample_index, elapsed in enumerate(samples):
            expected = oracle.evaluate_orientation(track, elapsed)
            segment, alpha, actual_quat, complete, valid = evaluate(elapsed)
            require(valid == expected.valid, f"valid:{fixture_index}:{sample_index}")
            require(complete == expected.complete, f"complete:{fixture_index}:{sample_index}")
            require(segment == expected.segment_index, f"segment:{fixture_index}:{sample_index}:{segment}:{expected.segment_index}")
            maximum_alpha = max(maximum_alpha, abs(alpha - expected.alpha))
            require(abs(alpha - expected.alpha) <= 2.0e-9, f"alpha:{fixture_index}:{sample_index}:{alpha}:{expected.alpha}")
            error = angular_error(actual_quat, expected.rotation)
            maximum_angle = max(maximum_angle, error)
            require(error <= 1.0e-6, f"quat:{fixture_index}:{sample_index}:{error}")
            evaluations += 1

        target = rng.uniform(0.0, track.total_seconds)
        first = evaluate(target)
        shuffled = list(samples)
        rng.shuffle(shuffled)
        for elapsed in shuffled[: min(20, len(shuffled))]:
            evaluate(elapsed)
        second = evaluate(target)
        require(first[0] == second[0] and first[3:] == second[3:], f"scrub metadata:{fixture_index}")
        require(abs(first[1] - second[1]) <= 2.0e-12, f"scrub alpha:{fixture_index}")
        require(angular_error(first[2], second[2]) <= 2.0e-8, f"scrub quat:{fixture_index}")
        scrub_cases += 1

    rotations, durations, _track = fixtures[0]
    compile_track(rotations, durations)
    invalid_cases = []

    invalid_cases.append(("compile-invalid", COMPILED[7], False, 0.0))
    for name in COMPILED[:6]:
        value = list(get(obj, name))
        invalid_cases.append(("cardinality-" + name, name, value[:-1], 0.0))
    invalid_cases.extend((
        ("total-zero", COMPILED[6], 0.0, 0.0),
        # A negative scrub selects segment zero before evaluation clamps alpha.
        ("selected-duration-zero", COMPILED[1], [0.0] + list(get(obj, COMPILED[1]))[1:], -1.0),
    ))
    for label, property_name, bad_value, elapsed in invalid_cases:
        compile_track(rotations, durations)
        prefill_stale()
        set_(obj, property_name, bad_value)
        evaluate(elapsed)
        require_cleared(label)

    nonfinite_cases = 0
    for label, elapsed in (("elapsed-nan", float("nan")), ("elapsed-inf", float("inf")), ("elapsed-negative-inf", float("-inf"))):
        compile_track(rotations, durations)
        prefill_stale()
        set_(obj, RESULTS[0], elapsed)
        staged = float(get(obj, RESULTS[0]))
        if math.isfinite(staged):
            emit("REFLECTION_SANITIZED", label)
            continue
        obj.call_method("EvaluateCompiledOrientationTrackV1")
        require_cleared(label)
        nonfinite_cases += 1

    emit("VALID_TRACKS", len(fixtures))
    emit("EVALUATIONS", evaluations)
    emit("DIRECT_SCRUB_CASES", scrub_cases)
    emit("INVALID_COMPILED_CASES", len(invalid_cases))
    emit("NONFINITE_REACHED_BLUEPRINT", nonfinite_cases)
    emit("MAX_ALPHA_ERROR", maximum_alpha)
    emit("MAX_ANGULAR_ERROR", maximum_angle)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
