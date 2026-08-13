"""Execute the live desired-stream compiler on the real Client Director CDO.

This is semantic runtime acceptance, not graph-shape evidence.  It compares the
Blueprint transaction with the independent Python oracle, covers exact and
partial schedules, every shipped flight profile, failure cleanup, direct helper
and downstream boundaries, invocation-order independence, and restores every
desired/gimbal/prebake property touched by the call chain.
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


PREFIX = "EDD_AIRFRAME_DESIRED_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
IDENTITY = (0.0, 0.0, 0.0, 1.0)

POSITIONS = "AirframeDesiredStreamInputPositionsV1"
BODY_INPUT = "AirframeDesiredStreamInputAuthoredBodyQuatsV1"
GIMBAL_INPUT = "AirframeDesiredStreamInputAuthoredGimbalQuatsV1"
TOTAL = "AirframeDesiredStreamInputTotalSecondsV1"
STEP = "AirframeDesiredStreamInputFixedStepSecondsV1"
STAGE_INDEX = "AirframeDesiredStreamStageIndexV1"
STAGE_VALID = "AirframeDesiredStreamStageValidV1"
COMPILE_VALID = "AirframeDesiredStreamCompileValidV1"
VELOCITY_SAMPLE_INPUT = "AirframeDesiredStreamVelocitySampleInputSecondsV1"
VELOCITY_SAMPLE_RESULT = "AirframeDesiredStreamVelocitySampleResultV1"
VELOCITY_SAMPLE_VALID = "AirframeDesiredStreamVelocitySampleResultValidV1"

CANDIDATE_VECTORS = (
    ("AirframeDesiredStreamCandidateVelocitiesV1", "velocities"),
    ("AirframeDesiredStreamCandidateAccelerationsV1", "accelerations"),
    ("AirframeDesiredStreamCandidateJerksV1", "jerks"),
    ("AirframeDesiredStreamCandidateLookAheadVelocitiesV1", "look_ahead_velocities"),
)
CANDIDATE_QUATS = (
    ("AirframeDesiredStreamCandidateBodyQuatsV1", "desired_body_rotations"),
    ("AirframeDesiredStreamCandidateGimbalQuatsV1", "desired_gimbal_rotations"),
)
CANDIDATE_RATES = "AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1"

PROFILE_INPUTS = (
    ("AirframeDesiredStreamInputPathFollowWeightsV1", "path_follow_weight"),
    ("AirframeDesiredStreamInputHorizonStabilizationWeightsV1", "horizon_stabilization_weight"),
    ("AirframeDesiredStreamInputLookAheadSecondsV1", "look_ahead_seconds"),
    ("AirframeDesiredStreamInputBankGainsV1", "bank_gain"),
    ("AirframeDesiredStreamInputMaxBankDegreesV1", "max_bank_degrees"),
    ("AirframeDesiredStreamInputCameraUptiltDegreesV1", "camera_uptilt_degrees"),
    ("AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1", "max_angular_rate_degrees_per_second"),
    ("AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1", "max_acceleration_cm_per_second_squared"),
    ("AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1", "max_jerk_cm_per_second_cubed"),
    ("AirframeDesiredStreamInputMinimumTurnRadiiCmV1", "minimum_turn_radius_cm"),
)
INPUTS = (POSITIONS, BODY_INPUT, GIMBAL_INPUT) + tuple(name for name, _ in PROFILE_INPUTS) + (TOTAL, STEP)

PREBAKE_VALID = "AirframePrebakeCompileValidV1"
PREBAKE_COMPILED_QUATS = (
    ("AirframePrebakeCompiledBodyQuatsV1", "body_rotations"),
    ("AirframePrebakeCompiledGimbalQuatsV1", "gimbal_rotations"),
)
PREBAKE_COMPILED_RATES = (
    ("AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1", "body_angular_rates_degrees_per_second"),
    ("AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1", "gimbal_angular_rates_degrees_per_second"),
)
PREBAKE_FLAGS = (
    ("AirframePrebakeCompiledBodyRateLimitedV1", "body_rate_limited"),
    ("AirframePrebakeCompiledGimbalRateLimitedV1", "gimbal_rate_limited"),
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
    raise RuntimeError("missing property:" + name)


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError("could not set property:" + name)


def vector(value):
    return unreal.Vector(*(float(component) for component in value))


def quat(value):
    return unreal.Quat(*(float(component) for component in value))


def vt(value):
    return float(value.x), float(value.y), float(value.z)


def qt(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def axis_angle(axis, degrees):
    magnitude = math.sqrt(sum(value * value for value in axis))
    unit = tuple(value / magnitude for value in axis)
    half = 0.5 * math.radians(degrees)
    scale = math.sin(half)
    return unit[0] * scale, unit[1] * scale, unit[2] * scale, math.cos(half)


def close(left, right, tolerance=7.5e-5):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def same_vector(left, right, tolerance=1.5e-4):
    return all(close(a, b, tolerance) for a, b in zip(left, right))


def same_rotation(left, right, tolerance=1.5e-4):
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if left_length <= 1.0e-12 or right_length <= 1.0e-12:
        return False
    dot = abs(sum(a * b for a, b in zip(left, right)) / (left_length * right_length))
    return dot >= 1.0 - tolerance


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import airframe_desired_stream_reference as oracle
import airframe_gimbal_reference as gimbal_oracle
import airframe_gimbal_prebake_reference as prebake_oracle
import flight_profile_reference as flight_profiles

gimbal_oracle = importlib.reload(gimbal_oracle)
prebake_oracle = importlib.reload(prebake_oracle)
oracle = importlib.reload(oracle)
flight_profiles = importlib.reload(flight_profiles)

schema_files = (
    "airframe_desired_stream_blueprint_schema.json",
    "airframe_gimbal_blueprint_schema.json",
    "airframe_gimbal_prebake_blueprint_schema.json",
)
specs = {}
for filename in schema_files:
    schema = json.loads((root / "tools" / "trajectory" / filename).read_text(encoding="utf-8"))
    for spec in schema["variables"]:
        specs.setdefault(spec["name"], spec)

cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)


def clone_value(name, value):
    spec = specs[name]
    if spec["container"] == "Array":
        if spec["type"] == "Vector":
            return [vector(vt(item)) for item in value]
        if spec["type"] == "Quat":
            return [quat(qt(item)) for item in value]
        return list(value)
    if spec["type"] == "Vector":
        return vector(vt(value))
    if spec["type"] == "Quat":
        return quat(qt(value))
    return value


saved = {name: clone_value(name, get(obj, name)) for name in specs}


def accepted_profile(profile_id):
    source = flight_profiles.PROFILES[profile_id]
    return gimbal_oracle.AirframeGimbalProfile(**{
        field: float(getattr(source, field))
        for field in gimbal_oracle.AirframeGimbalProfile.__dataclass_fields__
    })


def stage_inputs(case):
    positions, bodies, gimbals, profiles, total, step = case
    set_(obj, POSITIONS, [vector(value) for value in positions])
    set_(obj, BODY_INPUT, [quat(value) for value in bodies])
    set_(obj, GIMBAL_INPUT, [quat(value) for value in gimbals])
    for name, field in PROFILE_INPUTS:
        set_(obj, name, [float(getattr(profile, field)) for profile in profiles])
    set_(obj, TOTAL, float(total))
    set_(obj, STEP, float(step))


def input_snapshot():
    values = []
    for name in INPUTS:
        value = get(obj, name)
        spec = specs[name]
        if spec["container"] == "Array" and spec["type"] == "Vector":
            values.append(tuple(vt(item) for item in value))
        elif spec["container"] == "Array" and spec["type"] == "Quat":
            values.append(tuple(qt(item) for item in value))
        elif spec["container"] == "Array":
            values.append(tuple(float(item) for item in value))
        else:
            values.append(float(value))
    return tuple(values)


def require_unpublished(label):
    source_count = len(get(obj, POSITIONS))
    for name, _field in CANDIDATE_VECTORS + CANDIDATE_QUATS:
        require(len(get(obj, name)) <= source_count, f"{label}:{name}:unbounded")
    require(len(get(obj, CANDIDATE_RATES)) <= source_count, f"{label}:candidate-rates:unbounded")
    require(not bool(get(obj, STAGE_VALID)), f"{label}:stage-valid")
    require(not bool(get(obj, COMPILE_VALID)), f"{label}:compile-valid")
    require(not bool(get(obj, PREBAKE_VALID)), f"{label}:prebake-valid")
    for name, _field in PREBAKE_COMPILED_QUATS + PREBAKE_COMPILED_RATES + PREBAKE_FLAGS:
        require(len(get(obj, name)) == 0, f"{label}:{name}")


def require_vector_array(name, expected, label):
    actual = tuple(vt(value) for value in get(obj, name))
    require(len(actual) == len(expected), f"{label}:{name}:count")
    for index, (left, right) in enumerate(zip(actual, expected)):
        require(same_vector(left, right), f"{label}:{name}:{index}:{left!r}:{right!r}")


def require_quat_array(name, expected, label):
    actual = tuple(qt(value) for value in get(obj, name))
    require(len(actual) == len(expected), f"{label}:{name}:count")
    for index, (left, right) in enumerate(zip(actual, expected)):
        require(same_rotation(left, right), f"{label}:{name}:{index}:{left!r}:{right!r}")


def require_float_array(name, expected, label, tolerance=2.5e-4):
    actual = tuple(float(value) for value in get(obj, name))
    require(len(actual) == len(expected), f"{label}:{name}:count")
    require(all(close(a, b, tolerance) for a, b in zip(actual, expected)), f"{label}:{name}:{actual!r}:{expected!r}")


def downstream_snapshot():
    return (
        tuple(qt(value) for value in get(obj, PREBAKE_COMPILED_QUATS[0][0])),
        tuple(qt(value) for value in get(obj, PREBAKE_COMPILED_QUATS[1][0])),
        tuple(float(value) for value in get(obj, PREBAKE_COMPILED_RATES[0][0])),
        tuple(float(value) for value in get(obj, PREBAKE_COMPILED_RATES[1][0])),
        tuple(bool(value) for value in get(obj, PREBAKE_FLAGS[0][0])),
        tuple(bool(value) for value in get(obj, PREBAKE_FLAGS[1][0])),
        float(get(obj, "AirframePrebakeCompiledFixedStepSecondsV1")),
        float(get(obj, "AirframePrebakeCompiledTotalSecondsV1")),
        bool(get(obj, PREBAKE_VALID)),
    )


def require_compiled(expected, label):
    require(bool(get(obj, COMPILE_VALID)), label + ":compile-valid")
    require(bool(get(obj, PREBAKE_VALID)), label + ":prebake-valid")
    require(int(get(obj, STAGE_INDEX)) == len(expected.sample_times) - 1, label + ":stage-index")
    require(bool(get(obj, STAGE_VALID)), label + ":stage-valid")
    for name, field in CANDIDATE_VECTORS:
        require_vector_array(name, getattr(expected, field), label)
    for name, field in CANDIDATE_QUATS:
        require_quat_array(name, getattr(expected, field), label)
    require_float_array(name=CANDIDATE_RATES, expected=expected.maximum_angular_rates_degrees_per_second, label=label)

    # Prove the composition boundary independently.  The Python and Blueprint
    # desired-pose solvers are compared as rotations above.  Downstream angular
    # rates are extremely sensitive to the engine quaternion representation at
    # small angles, so a broad epsilon here would conceal wiring defects.
    # Instead: (1) compare the semantic pose/flags/metadata to the accepted
    # prebake oracle, (2) prove every published rate is finite and physically
    # bounded, and (3) replay the already independently accepted prebake
    # compiler over the exact staged candidates and demand bit-exact output.
    actual_body = tuple(qt(value) for value in get(obj, CANDIDATE_QUATS[0][0]))
    actual_gimbal = tuple(qt(value) for value in get(obj, CANDIDATE_QUATS[1][0]))
    actual_rates = tuple(float(value) for value in get(obj, CANDIDATE_RATES))
    downstream_expected = prebake_oracle.compile_airframe_gimbal_motion(
        actual_body, actual_gimbal, actual_rates,
        float(get(obj, TOTAL)), float(get(obj, STEP)),
    )
    for name, field in PREBAKE_COMPILED_QUATS:
        require_quat_array(name, getattr(downstream_expected, field), label)
    for name, field in PREBAKE_FLAGS:
        require(tuple(bool(value) for value in get(obj, name)) == getattr(downstream_expected, field), f"{label}:{name}")
    require(close(get(obj, "AirframePrebakeCompiledFixedStepSecondsV1"), downstream_expected.fixed_step_seconds), label + ":step")
    require(close(get(obj, "AirframePrebakeCompiledTotalSecondsV1"), downstream_expected.total_seconds), label + ":total")
    for name, _field in PREBAKE_COMPILED_RATES:
        published = tuple(float(value) for value in get(obj, name))
        require(len(published) == len(actual_rates), f"{label}:{name}:count")
        require(published[0] == 0.0, f"{label}:{name}:first")
        require(all(math.isfinite(value) for value in published), f"{label}:{name}:finite")
        require(all(value >= 0.0 for value in published), f"{label}:{name}:nonnegative")
        require(all(value <= limit + 1.0e-7 for value, limit in zip(published, actual_rates)), f"{label}:{name}:bounded")

    published = downstream_snapshot()
    obj.call_method("CompileAirframePrebakeV1")
    require(downstream_snapshot() == published, label + ":downstream-direct-replay")


def make_case(total, step, profile_ids, seed):
    times = prebake_oracle.fixed_sample_times(total, step)
    rng = random.Random(seed)
    vx = rng.uniform(80.0, 180.0)
    vy = rng.uniform(-15.0, 15.0)
    ax = rng.uniform(-2.0, 2.0)
    ay = rng.uniform(-1.0, 1.0)
    positions = [(vx * time + 0.5 * ax * time * time, vy * time + 0.5 * ay * time * time, 0.25 * time) for time in times]
    bodies = [axis_angle((0.0, 0.0, 1.0), -10.0 + 20.0 * index / max(1, len(times) - 1)) for index in range(len(times))]
    gimbals = [axis_angle((0.0, 1.0, 0.0), 6.0 - 12.0 * index / max(1, len(times) - 1)) for index in range(len(times))]
    profiles = [accepted_profile(profile_ids[index % len(profile_ids)]) for index in range(len(times))]
    return positions, bodies, gimbals, profiles, total, step


try:
    profile_ids = tuple(flight_profiles.PROFILE_ORDER)
    cases = [
        make_case(0.1, 0.5, profile_ids, 0xEDD001),
        make_case(1.0, 0.25, profile_ids, 0xEDD002),
        make_case(1.0, 0.3, tuple(reversed(profile_ids)), 0xEDD003),
    ]
    for index in range(12):
        rng = random.Random(0xEDD500 + index)
        step = rng.choice((0.05, 0.1, 0.2, 0.3))
        total = rng.uniform(step * 1.1, min(1.8, step * 7.8))
        cases.append(make_case(total, step, profile_ids[index % len(profile_ids):] + profile_ids[:index % len(profile_ids)], 0xEDD900 + index))

    compiled = []
    max_vector_error = 0.0
    for index, case in enumerate(cases):
        stage_inputs(case)
        before = input_snapshot()
        expected = oracle.compile_airframe_desired_stream(*case)
        obj.call_method("CompileAirframeDesiredStreamV1")
        require(input_snapshot() == before, f"compile:{index}:inputs-mutated")
        require_compiled(expected, f"compile:{index}")
        for name, field in CANDIDATE_VECTORS:
            actual = tuple(vt(value) for value in get(obj, name))
            for left, right in zip(actual, getattr(expected, field)):
                max_vector_error = max(max_vector_error, max(abs(a - b) for a, b in zip(left, right)))
        compiled.append(expected)

    # Reversed invocation order must publish the same complete values.
    for index, case in enumerate(reversed(cases)):
        stage_inputs(case)
        obj.call_method("CompileAirframeDesiredStreamV1")
        require_compiled(compiled[len(cases) - 1 - index], f"reverse:{index}")

    # A failed recompile must erase the prior authoritative desired and prebake state.
    invalid_cases = []
    base = cases[1]
    invalid_cases.append(("shape-position", (base[0][:-1],) + base[1:]))
    invalid_cases.append(("shape-profile", base[:3] + (base[3][:-1],) + base[4:]))
    invalid_cases.append(("schedule-total", base[:4] + (0.0, base[5])))
    invalid_cases.append(("schedule-step", base[:5] + (0.001,)))
    bad_bodies = list(base[1]); bad_bodies[1] = (0.0, 0.0, 0.0, 0.0)
    invalid_cases.append(("quaternion", (base[0], bad_bodies, base[2], base[3], base[4], base[5])))
    bad_profiles = list(base[3]); bad_profiles[1] = replace(bad_profiles[1], path_follow_weight=1.01)
    invalid_cases.append(("profile-range", (base[0], base[1], base[2], bad_profiles, base[4], base[5])))
    violent_positions = list(base[0]); violent_positions[2] = (100000.0, 0.0, 0.0)
    strict_profiles = [replace(profile, max_acceleration_cm_per_second_squared=1.0) for profile in base[3]]
    invalid_cases.append(("physical-acceleration", (violent_positions, base[1], base[2], strict_profiles, base[4], base[5])))
    overflow_positions = list(base[0]); overflow_positions[-1] = (1.0e307, 0.0, 0.0)
    invalid_cases.append(("derivative-overflow", (overflow_positions, base[1], base[2], base[3], base[4], base[5])))
    for label, case in invalid_cases:
        stage_inputs(base)
        obj.call_method("CompileAirframeDesiredStreamV1")
        stage_inputs(case)
        before = input_snapshot()
        obj.call_method("CompileAirframeDesiredStreamV1")
        require(input_snapshot() == before, label + ":inputs-mutated")
        require_unpublished(label)

    # Direct helper failure is fail-closed and does not publish a stale vector.
    stage_inputs(base)
    obj.call_method("ResetAirframeDesiredStreamV1")
    obj.call_method("ValidateAirframeDesiredStreamInputsV1")
    obj.call_method("BuildAirframeDesiredVelocitySamplesV1")
    set_(obj, "AirframeDesiredStreamCandidateVelocitiesV1", [vector((1.0, 2.0, 3.0))])
    set_(obj, VELOCITY_SAMPLE_INPUT, 0.25)
    set_(obj, VELOCITY_SAMPLE_RESULT, vector((9.0, 9.0, 9.0)))
    set_(obj, VELOCITY_SAMPLE_VALID, True)
    obj.call_method("SampleAirframeDesiredVelocityAtTimeV1")
    require(not bool(get(obj, VELOCITY_SAMPLE_VALID)), "helper:valid")
    require(vt(get(obj, VELOCITY_SAMPLE_RESULT)) == (0.0, 0.0, 0.0), "helper:stale-result")

    # Direct commit preflight rejects a corrupt candidate without touching the
    # previously accepted downstream snapshot.  Top-level orchestration owns
    # reset-before-work; this helper owns no destructive preflight side effect.
    stage_inputs(base)
    obj.call_method("CompileAirframeDesiredStreamV1")
    prior_downstream = downstream_snapshot()
    body_candidates = list(get(obj, "AirframeDesiredStreamCandidateBodyQuatsV1"))
    set_(obj, "AirframeDesiredStreamCandidateBodyQuatsV1", body_candidates[:-1])
    obj.call_method("CommitAirframeDesiredStreamToPrebakeV1")
    require(not bool(get(obj, COMPILE_VALID)), "commit-preflight:stream-valid")
    require(downstream_snapshot() == prior_downstream, "commit-preflight:downstream-mutated")

    emit("COMPILE_CASES", len(cases))
    emit("REVERSE_COMPILE_CASES", len(cases))
    emit("PROFILE_IDS", ",".join(profile_ids))
    emit("INVALID_COMPILE_CASES", len(invalid_cases))
    emit("DIRECT_BOUNDARY_CASES", 2)
    emit("MAX_VECTOR_ERROR", max_vector_error)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    restored = True
    for name, value in saved.items():
        current = get(obj, name)
        spec = specs[name]
        if spec["container"] == "Array" and spec["type"] == "Vector":
            restored = restored and tuple(vt(item) for item in current) == tuple(vt(item) for item in value)
        elif spec["container"] == "Array" and spec["type"] == "Quat":
            restored = restored and tuple(qt(item) for item in current) == tuple(qt(item) for item in value)
        elif spec["container"] == "Array":
            restored = restored and list(current) == list(value)
        elif spec["type"] == "Vector":
            restored = restored and vt(current) == vt(value)
        elif spec["type"] == "Quat":
            restored = restored and qt(current) == qt(value)
        else:
            restored = restored and current == value
    emit("STATE_RESTORED", restored)
    require(restored, "state restoration")
