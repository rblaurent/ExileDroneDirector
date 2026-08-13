"""Execute the compiled fixed-step airframe/gimbal Blueprint on its real CDO.

This is runtime acceptance, not graph-shape evidence.  It compares compiled
publication and arbitrary-order evaluation with the independent Python oracle,
proves failure cleanup and corrupt-publication rejection, and restores all
forty schema properties even if an assertion fails.
"""

from __future__ import annotations

import importlib
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

import unreal


PREFIX = "EDD_AIRFRAME_PREBAKE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
IDENTITY = (0.0, 0.0, 0.0, 1.0)
INPUT_BODY = "AirframePrebakeInputDesiredBodyQuatsV1"
INPUT_GIMBAL = "AirframePrebakeInputDesiredGimbalQuatsV1"
INPUT_RATE = "AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"
INPUT_TOTAL = "AirframePrebakeInputTotalSecondsV1"
INPUT_STEP = "AirframePrebakeInputFixedStepSecondsV1"
COMPILED_BODY = "AirframePrebakeCompiledBodyQuatsV1"
COMPILED_GIMBAL = "AirframePrebakeCompiledGimbalQuatsV1"
COMPILED_BODY_RATE = "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1"
COMPILED_GIMBAL_RATE = "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1"
COMPILED_BODY_LIMITED = "AirframePrebakeCompiledBodyRateLimitedV1"
COMPILED_GIMBAL_LIMITED = "AirframePrebakeCompiledGimbalRateLimitedV1"
COMPILED_STEP = "AirframePrebakeCompiledFixedStepSecondsV1"
COMPILED_TOTAL = "AirframePrebakeCompiledTotalSecondsV1"
COMPILE_VALID = "AirframePrebakeCompileValidV1"
ELAPSED = "AirframePrebakeInputElapsedSecondsV1"
RESULT_INDEX = "AirframePrebakeResultSegmentIndexV1"
RESULT_ALPHA = "AirframePrebakeResultAlphaV1"
RESULT_BODY = "AirframePrebakeResultBodyQuatV1"
RESULT_GIMBAL = "AirframePrebakeResultGimbalQuatV1"
RESULT_COMPLETE = "AirframePrebakeResultCompleteV1"
RESULT_VALID = "AirframePrebakeResultValidV1"


def emit(label, value):
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition, message):
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def variants(name):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def get(obj, name):
    for candidate in variants(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError("missing property:" + name)


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError("could not set property:" + name)


def q(value):
    return unreal.Quat(*(float(component) for component in value))


def qt(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def axis_angle(axis, angle):
    magnitude = math.sqrt(sum(value * value for value in axis))
    unit = tuple(value / magnitude for value in axis)
    half = math.radians(angle) * 0.5
    sine = math.sin(half)
    return unit[0] * sine, unit[1] * sine, unit[2] * sine, math.cos(half)


def close(left, right, tolerance=5.0e-5):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def same_quat(left, right, tolerance=5.0e-5):
    return max(abs(a - b) for a, b in zip(left, right)) <= tolerance


root = Path(__file__).resolve().parents[2]
schema = json.loads((root / "tools/trajectory/airframe_gimbal_prebake_blueprint_schema.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(root / "tools" / "trajectory"))
import airframe_gimbal_prebake_reference as oracle
oracle = importlib.reload(oracle)

specs = {item["name"]: item for item in schema["variables"]}
names = tuple(specs)
cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)


def clone_value(name, value):
    spec = specs[name]
    if spec["container"] == "Array":
        if spec["type"] == "Quat":
            return [q(qt(item)) for item in value]
        return list(value)
    if spec["type"] == "Quat":
        return q(qt(value))
    return value


saved = {name: clone_value(name, get(obj, name)) for name in names}


def stage_inputs(bodies, gimbals, rates, total, step):
    set_(obj, INPUT_BODY, [q(value) for value in bodies])
    set_(obj, INPUT_GIMBAL, [q(value) for value in gimbals])
    set_(obj, INPUT_RATE, [float(value) for value in rates])
    set_(obj, INPUT_TOTAL, float(total))
    set_(obj, INPUT_STEP, float(step))


def input_snapshot():
    return (
        tuple(qt(value) for value in get(obj, INPUT_BODY)),
        tuple(qt(value) for value in get(obj, INPUT_GIMBAL)),
        tuple(float(value) for value in get(obj, INPUT_RATE)),
        float(get(obj, INPUT_TOTAL)),
        float(get(obj, INPUT_STEP)),
    )


def require_compile_cleared(label):
    for name in (COMPILED_BODY, COMPILED_GIMBAL, COMPILED_BODY_RATE, COMPILED_GIMBAL_RATE,
                 COMPILED_BODY_LIMITED, COMPILED_GIMBAL_LIMITED):
        require(len(get(obj, name)) == 0, f"{label}:{name}:not-empty")
    require(float(get(obj, COMPILED_STEP)) == 0.0, label + ":step")
    require(float(get(obj, COMPILED_TOTAL)) == 0.0, label + ":total")
    require(not bool(get(obj, COMPILE_VALID)), label + ":valid")


def require_compiled(expected, label):
    require(bool(get(obj, COMPILE_VALID)), label + ":valid")
    actual_quats = (
        tuple(qt(value) for value in get(obj, COMPILED_BODY)),
        tuple(qt(value) for value in get(obj, COMPILED_GIMBAL)),
    )
    expected_quats = (expected.body_rotations, expected.gimbal_rotations)
    for channel, (actual, wanted) in enumerate(zip(actual_quats, expected_quats)):
        require(len(actual) == len(wanted), f"{label}:quat-count:{channel}")
        for index, (left, right) in enumerate(zip(actual, wanted)):
            require(same_quat(left, right), f"{label}:quat:{channel}:{index}:{left!r}:{right!r}")
    actual_rate_channels = {}
    for name, wanted in (
        (COMPILED_BODY_RATE, expected.body_angular_rates_degrees_per_second),
        (COMPILED_GIMBAL_RATE, expected.gimbal_angular_rates_degrees_per_second),
    ):
        actual = tuple(float(value) for value in get(obj, name))
        actual_rate_channels[name] = actual
        require(len(actual) == len(wanted), f"{label}:{name}:count")
        require(all(close(a, b, 2.0e-4) for a, b in zip(actual, wanted)), f"{label}:{name}:{actual!r}:{wanted!r}")
    actual_body_flags = tuple(bool(value) for value in get(obj, COMPILED_BODY_LIMITED))
    actual_gimbal_flags = tuple(bool(value) for value in get(obj, COMPILED_GIMBAL_LIMITED))
    require(
        actual_body_flags == expected.body_rate_limited,
        f"{label}:body-flags:{actual_body_flags!r}:{expected.body_rate_limited!r}:"
        f"rates={actual_rate_channels[COMPILED_BODY_RATE]!r}:"
        f"expected-rates={expected.body_angular_rates_degrees_per_second!r}",
    )
    require(
        actual_gimbal_flags == expected.gimbal_rate_limited,
        f"{label}:gimbal-flags:{actual_gimbal_flags!r}:{expected.gimbal_rate_limited!r}:"
        f"rates={actual_rate_channels[COMPILED_GIMBAL_RATE]!r}:"
        f"expected-rates={expected.gimbal_angular_rates_degrees_per_second!r}",
    )
    require(close(get(obj, COMPILED_STEP), expected.fixed_step_seconds), label + ":step")
    require(close(get(obj, COMPILED_TOTAL), expected.total_seconds), label + ":total")


def current_track():
    return oracle.CompiledAirframeGimbalMotion(
        tuple(qt(value) for value in get(obj, COMPILED_BODY)),
        tuple(qt(value) for value in get(obj, COMPILED_GIMBAL)),
        tuple(float(value) for value in get(obj, COMPILED_BODY_RATE)),
        tuple(float(value) for value in get(obj, COMPILED_GIMBAL_RATE)),
        tuple(bool(value) for value in get(obj, COMPILED_BODY_LIMITED)),
        tuple(bool(value) for value in get(obj, COMPILED_GIMBAL_LIMITED)),
        float(get(obj, COMPILED_STEP)), float(get(obj, COMPILED_TOTAL)),
    )


def require_evaluation(expected, label):
    actual_summary = (
        bool(get(obj, RESULT_VALID)),
        bool(get(obj, RESULT_COMPLETE)),
        int(get(obj, RESULT_INDEX)),
        float(get(obj, RESULT_ALPHA)),
        qt(get(obj, RESULT_BODY)),
        qt(get(obj, RESULT_GIMBAL)),
    )
    require(
        actual_summary[0] is expected.valid,
        f"{label}:valid:actual={actual_summary!r}:expected={expected!r}",
    )
    require(bool(get(obj, RESULT_COMPLETE)) is expected.complete, label + ":complete")
    require(int(get(obj, RESULT_INDEX)) == expected.segment_index, label + ":index")
    require(close(get(obj, RESULT_ALPHA), expected.alpha), label + ":alpha")
    if expected.valid:
        require(same_quat(qt(get(obj, RESULT_BODY)), expected.body_rotation), label + ":body")
        require(same_quat(qt(get(obj, RESULT_GIMBAL)), expected.gimbal_rotation), label + ":gimbal")
    else:
        require(int(get(obj, RESULT_INDEX)) == -1 and float(get(obj, RESULT_ALPHA)) == 0.0, label + ":reset-scalars")
        require(same_quat(qt(get(obj, RESULT_BODY)), IDENTITY, 1.0e-7), label + ":reset-body")
        require(same_quat(qt(get(obj, RESULT_GIMBAL)), IDENTITY, 1.0e-7), label + ":reset-gimbal")


try:
    rng = random.Random(0xEDD_BA5E)
    cases = []
    for total, step, angles in (
        (0.25, 0.25, (0.0, 30.0)),
        (1.0, 0.25, (0.0, 90.0, 90.0, 180.0, 180.0)),
        (1.0, 0.3, (0.0, 20.0, 50.0, 90.0, 130.0)),
    ):
        bodies = [axis_angle((1.0, 0.0, 0.0), angle) for angle in angles]
        gimbals = [axis_angle((0.0, 1.0, 0.0), -0.5 * angle) for angle in angles]
        cases.append((bodies, gimbals, [120.0] * len(angles), total, step))
    for _ in range(24):
        total = rng.uniform(0.05, 1.5)
        step = rng.choice((1.0 / 60.0, 1.0 / 30.0, 0.1, 0.3))
        count = len(oracle.fixed_sample_times(total, step))
        bodies = [axis_angle((rng.random() + .01, rng.random() + .01, rng.random() + .01), rng.uniform(-180, 180)) for _ in range(count)]
        gimbals = [axis_angle((rng.random() + .01, rng.random() + .01, rng.random() + .01), rng.uniform(-180, 180)) for _ in range(count)]
        rates = [rng.uniform(1.0, 720.0) for _ in range(count)]
        cases.append((bodies, gimbals, rates, total, step))

    compiled = []
    for index, case in enumerate(cases):
        stage_inputs(*case)
        before = input_snapshot()
        expected = oracle.compile_airframe_gimbal_motion(*case)
        obj.call_method("CompileAirframePrebakeV1")
        require(input_snapshot() == before, f"compile:{index}:inputs-mutated")
        require_compiled(expected, f"compile:{index}")
        compiled.append(expected)

    # Invocation order must not affect publication.
    for index, case in enumerate(reversed(cases)):
        stage_inputs(*case)
        obj.call_method("CompileAirframePrebakeV1")
        require_compiled(compiled[len(cases) - 1 - index], f"reverse:{index}")

    # A failed recompile after success must erase the prior authoritative track.
    stage_inputs(*cases[0])
    obj.call_method("CompileAirframePrebakeV1")
    bad = list(cases[0][2]); bad[0] = 0.0
    stage_inputs(cases[0][0], cases[0][1], bad, cases[0][3], cases[0][4])
    obj.call_method("CompileAirframePrebakeV1")
    require_compile_cleared("failed-recompile-rate")
    stage_inputs(cases[0][0][:-1], cases[0][1], cases[0][2], cases[0][3], cases[0][4])
    obj.call_method("CompileAirframePrebakeV1")
    require_compile_cleared("invalid-cardinality")

    stage_inputs(*cases[2])
    obj.call_method("CompileAirframePrebakeV1")
    track = current_track()
    track_times = oracle.fixed_sample_times(track.total_seconds, track.fixed_step_seconds)
    body_rate_errors = []
    gimbal_rate_errors = []
    for index in range(1, len(track_times)):
        delta = track_times[index] - track_times[index - 1]
        body_rate_errors.append(abs(
            oracle._angle_degrees(track.body_rotations[index - 1], track.body_rotations[index]) / delta
            - track.body_angular_rates_degrees_per_second[index]
        ))
        gimbal_rate_errors.append(abs(
            oracle._angle_degrees(track.gimbal_rotations[index - 1], track.gimbal_rotations[index]) / delta
            - track.gimbal_angular_rates_degrees_per_second[index]
        ))
    emit("TRACK_RATE_ERROR_MAX", (max(body_rate_errors), max(gimbal_rate_errors)))
    queries = (-10.0, 0.0, 0.11, 0.3, 0.87, 0.95, 1.0, 10.0)
    forward = {}
    for elapsed in queries:
        set_(obj, ELAPSED, elapsed)
        obj.call_method("EvaluateCompiledAirframePrebakeV1")
        expected = oracle.evaluate_airframe_gimbal_motion(track, elapsed)
        require_evaluation(expected, f"evaluate:{elapsed}")
        forward[elapsed] = (int(get(obj, RESULT_INDEX)), float(get(obj, RESULT_ALPHA)), qt(get(obj, RESULT_BODY)), qt(get(obj, RESULT_GIMBAL)), bool(get(obj, RESULT_COMPLETE)), bool(get(obj, RESULT_VALID)))
    for elapsed in reversed(queries):
        set_(obj, ELAPSED, elapsed)
        obj.call_method("EvaluateCompiledAirframePrebakeV1")
        actual = (int(get(obj, RESULT_INDEX)), float(get(obj, RESULT_ALPHA)), qt(get(obj, RESULT_BODY)), qt(get(obj, RESULT_GIMBAL)), bool(get(obj, RESULT_COMPLETE)), bool(get(obj, RESULT_VALID)))
        require(actual == forward[elapsed], f"evaluate-history:{elapsed}")

    # Evaluator independently rejects corrupt immutable publication.
    valid_gimbals = list(get(obj, COMPILED_GIMBAL))
    set_(obj, COMPILED_GIMBAL, valid_gimbals[:-1])
    set_(obj, ELAPSED, 0.5)
    obj.call_method("EvaluateCompiledAirframePrebakeV1")
    require_evaluation(oracle.AirframeGimbalMotionEvaluation(False, False, -1, 0.0, None, None, 0.0), "corrupt-shape")
    set_(obj, COMPILED_GIMBAL, valid_gimbals)
    body_rates = list(get(obj, COMPILED_BODY_RATE)); body_rates[0] = 1.0
    set_(obj, COMPILED_BODY_RATE, body_rates)
    obj.call_method("EvaluateCompiledAirframePrebakeV1")
    require_evaluation(oracle.AirframeGimbalMotionEvaluation(False, False, -1, 0.0, None, None, 0.0), "corrupt-seed-rate")

    emit("COMPILE_CASES", len(cases))
    emit("REVERSE_COMPILE_CASES", len(cases))
    emit("EVALUATION_CASES", len(queries) * 2)
    emit("INVALID_COMPILE_CASES", 2)
    emit("CORRUPT_EVALUATION_CASES", 2)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    restored = True
    for name, value in saved.items():
        current = get(obj, name)
        if specs[name]["container"] == "Array":
            if specs[name]["type"] == "Quat":
                restored = restored and tuple(qt(item) for item in current) == tuple(qt(item) for item in value)
            else:
                restored = restored and list(current) == list(value)
        elif specs[name]["type"] == "Quat":
            restored = restored and qt(current) == qt(value)
        else:
            restored = restored and current == value
    emit("STATE_RESTORED", restored)
    require(restored, "state restoration")
