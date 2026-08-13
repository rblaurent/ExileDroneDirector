"""Execute the live stateless airframe/gimbal desired-pose Blueprint.

This is a semantic acceptance harness, not a graph-shape test.  It compares
the Blueprint CDO against the independent Python oracle, exercises the reset
and validation boundaries directly, proves fail-closed publication, and
restores every touched property even when an assertion fails.
"""

from __future__ import annotations

import math
import random
import sys
import importlib
from dataclasses import replace
from pathlib import Path

import unreal


PREFIX = "EDD_AIRFRAME_GIMBAL_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
IDENTITY = (0.0, 0.0, 0.0, 1.0)

VECTOR_INPUTS = (
    "AirframeGimbalInputCurrentVelocityV1",
    "AirframeGimbalInputLookAheadVelocityV1",
    "AirframeGimbalInputAccelerationV1",
    "AirframeGimbalInputJerkV1",
)
QUAT_INPUTS = (
    "AirframeGimbalInputAuthoredBodyQuatV1",
    "AirframeGimbalInputAuthoredGimbalQuatV1",
)
PROFILE_PARAMETERS = (
    ("AirframeGimbalInputPathFollowWeightV1", "path_follow_weight"),
    ("AirframeGimbalInputHorizonStabilizationWeightV1", "horizon_stabilization_weight"),
    ("AirframeGimbalInputLookAheadSecondsV1", "look_ahead_seconds"),
    ("AirframeGimbalInputBankGainV1", "bank_gain"),
    ("AirframeGimbalInputMaxBankDegreesV1", "max_bank_degrees"),
    ("AirframeGimbalInputCameraUptiltDegreesV1", "camera_uptilt_degrees"),
    ("AirframeGimbalInputMaxAngularRateDegreesPerSecondV1", "max_angular_rate_degrees_per_second"),
    ("AirframeGimbalInputMaxAccelerationCmPerSecondSquaredV1", "max_acceleration_cm_per_second_squared"),
    ("AirframeGimbalInputMaxJerkCmPerSecondCubedV1", "max_jerk_cm_per_second_cubed"),
    ("AirframeGimbalInputMinimumTurnRadiusCmV1", "minimum_turn_radius_cm"),
)
INPUTS = VECTOR_INPUTS + QUAT_INPUTS + tuple(name for name, _field in PROFILE_PARAMETERS)
STAGE = "AirframeGimbalStageValidV1"
QUAT_RESULTS = (
    "AirframeGimbalResultBodyQuatV1",
    "AirframeGimbalResultGimbalQuatV1",
    "AirframeGimbalResultPathQuatV1",
)
SCALAR_RESULTS = (
    "AirframeGimbalResultSpeedCmPerSecondV1",
    "AirframeGimbalResultLateralAccelerationCmPerSecondSquaredV1",
    "AirframeGimbalResultTurnRadiusCmV1",
    "AirframeGimbalResultBankDegreesV1",
)
RESULT_VALID = "AirframeGimbalResultValidV1"
RESULTS = QUAT_RESULTS + SCALAR_RESULTS + (RESULT_VALID,)
ALL_PROPERTIES = INPUTS + (STAGE,) + RESULTS


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


def xyz(value):
    return float(value.x), float(value.y), float(value.z)


def qtuple(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def normalized(value):
    if hasattr(value, "w") and hasattr(value, "x"):
        return qtuple(value)
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return xyz(value)
    if isinstance(value, float):
        return float(value)
    return value


def close(left, right, tolerance=4.0e-5):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def same_rotation(left, right, tolerance=4.0e-5):
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if left_length <= 1.0e-12 or right_length <= 1.0e-12:
        return False
    dot = abs(sum(a * b for a, b in zip(left, right)) / (left_length * right_length))
    return dot >= 1.0 - tolerance


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import airframe_gimbal_reference as oracle
import flight_profile_reference as profiles
oracle = importlib.reload(oracle)
profiles = importlib.reload(profiles)


def profile(name):
    source = profiles.PROFILES[name]
    return oracle.AirframeGimbalProfile(**{
        field: float(getattr(source, field))
        for field in oracle.AirframeGimbalProfile.__dataclass_fields__
    })


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
saved = {name: get(obj, name) for name in ALL_PROPERTIES}


def input_snapshot():
    return tuple(normalized(get(obj, name)) for name in INPUTS)


def result_snapshot():
    return tuple(normalized(get(obj, name)) for name in RESULTS)


def stage_inputs(current, look, acceleration, jerk, body, gimbal, selected):
    set_(obj, VECTOR_INPUTS[0], vector(current))
    set_(obj, VECTOR_INPUTS[1], vector(look))
    set_(obj, VECTOR_INPUTS[2], vector(acceleration))
    set_(obj, VECTOR_INPUTS[3], vector(jerk))
    set_(obj, QUAT_INPUTS[0], quat(body))
    set_(obj, QUAT_INPUTS[1], quat(gimbal))
    for name, field in PROFILE_PARAMETERS:
        set_(obj, name, float(getattr(selected, field)))


def poison_results():
    for name in QUAT_RESULTS:
        set_(obj, name, quat((0.5, 0.5, 0.5, 0.5)))
    for index, name in enumerate(SCALAR_RESULTS, start=1):
        set_(obj, name, 100.0 + index)
    set_(obj, RESULT_VALID, True)


def require_cleared(label):
    actual = result_snapshot()
    for index, value in enumerate(actual[:3]):
        require(same_rotation(value, IDENTITY, 1.0e-7), f"{label}:quat:{index}:{value!r}")
    require(all(float(value) == 0.0 for value in actual[3:7]), f"{label}:scalars:{actual[3:7]!r}")
    require(actual[7] is False, f"{label}:valid")


def require_result(expected, label):
    actual = result_snapshot()
    require(actual[-1] is True, f"{label}:valid:{actual!r}")
    require(same_rotation(actual[0], expected.body_rotation), f"{label}:body:{actual[0]!r}:{expected.body_rotation!r}")
    require(same_rotation(actual[1], expected.gimbal_rotation), f"{label}:gimbal:{actual[1]!r}:{expected.gimbal_rotation!r}")
    require(same_rotation(actual[2], expected.path_rotation), f"{label}:path:{actual[2]!r}:{expected.path_rotation!r}")
    expected_scalars = (
        expected.speed_cm_per_second,
        expected.lateral_acceleration_cm_per_second_squared,
        expected.turn_radius_cm,
        expected.bank_degrees,
    )
    for name, actual_value, expected_value in zip(SCALAR_RESULTS, actual[3:7], expected_scalars):
        require(close(actual_value, expected_value), f"{label}:{name}:{actual_value!r}:{expected_value!r}")


def solve_case(label, selected, current=(1000.0, 0.0, 0.0), look=(900.0, 300.0, 0.0),
               acceleration=(0.0, 300.0, 0.0), jerk=(0.0, 0.0, 0.0), body=IDENTITY, gimbal=IDENTITY):
    stage_inputs(current, look, acceleration, jerk, body, gimbal, selected)
    before = input_snapshot()
    expected = oracle.solve_airframe_gimbal(current, look, acceleration, jerk, body, gimbal, selected)
    obj.call_method("SolveAirframeGimbalV1")
    require(bool(get(obj, STAGE)), label + ":stage")
    require(input_snapshot() == before, label + ":inputs-mutated")
    require_result(expected, label)
    return result_snapshot()


def invalid_solve(label, mutate, expected_stage=False):
    stage_inputs((1000.0, 0.0, 0.0), (900.0, 300.0, 0.0), (0.0, 300.0, 0.0),
                 (0.0, 0.0, 0.0), IDENTITY, IDENTITY, profile("hybrid"))
    mutate()
    before = input_snapshot()
    poison_results()
    set_(obj, STAGE, True)
    obj.call_method("SolveAirframeGimbalV1")
    require(bool(get(obj, STAGE)) is expected_stage, label + ":stage")
    require(input_snapshot() == before, label + ":inputs-mutated")
    require_cleared(label)


try:
    # Reset clears all staging/publication while preserving every input.
    nondefault = replace(profile("hybrid"), camera_uptilt_degrees=-12.5)
    stage_inputs((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0),
                 (10.0, 11.0, 12.0), (0.0, 0.0, 1.0, 0.0), IDENTITY, nondefault)
    reset_inputs = input_snapshot()
    set_(obj, STAGE, True)
    poison_results()
    obj.call_method("ResetAirframeGimbalV1")
    require(input_snapshot() == reset_inputs, "reset:inputs-mutated")
    require(not bool(get(obj, STAGE)), "reset:stage")
    require_cleared("reset")

    # Validation is independently callable and only owns StageValid.
    stage_inputs((1000.0, 0.0, 0.0), (900.0, 300.0, 0.0), (0.0, 300.0, 0.0),
                 (0.0, 0.0, 0.0), IDENTITY, IDENTITY, profile("hybrid"))
    validation_inputs = input_snapshot()
    poison_results()
    validation_results = result_snapshot()
    set_(obj, STAGE, False)
    obj.call_method("ValidateAirframeGimbalInputsV1")
    require(bool(get(obj, STAGE)), "validate-valid:stage")
    require(input_snapshot() == validation_inputs, "validate-valid:inputs-mutated")
    require(result_snapshot() == validation_results, "validate-valid:results-mutated")

    set_(obj, PROFILE_PARAMETERS[0][0], 1.001)
    invalid_validation_inputs = input_snapshot()
    invalid_validation_results = result_snapshot()
    set_(obj, STAGE, True)
    obj.call_method("ValidateAirframeGimbalInputsV1")
    require(not bool(get(obj, STAGE)), "validate-invalid:stage")
    require(input_snapshot() == invalid_validation_inputs, "validate-invalid:inputs-mutated")
    require(result_snapshot() == invalid_validation_results, "validate-invalid:results-mutated")

    valid_cases = 0
    canonical = {}
    for name in ("cinematic_drone", "hybrid", "fpv_freestyle"):
        canonical[name] = solve_case("canonical:" + name, profile(name))
        valid_cases += 1
    require(abs(canonical["cinematic_drone"][6]) < abs(canonical["hybrid"][6]) < abs(canonical["fpv_freestyle"][6]),
            "canonical character ordering")

    base = profile("hybrid")
    body_lock = replace(base, path_follow_weight=0.0, horizon_stabilization_weight=0.0,
                        camera_uptilt_degrees=0.0)
    solve_case("endpoint:body-lock", body_lock, look=(1000.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
    quarter_turn = (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
    solve_case("endpoint:horizon", replace(body_lock, horizon_stabilization_weight=1.0),
               look=(1000.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0), gimbal=quarter_turn)
    valid_cases += 2

    solve_case("fallback:lookahead", base, look=(0.0, 1000.0, 0.0), acceleration=(0.0, 0.0, 0.0))
    solve_case("fallback:current", base, look=(0.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
    solve_case("fallback:authored", base, current=(0.0, 0.0, 0.0), look=(0.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
    solve_case("diagnostic:vertical", base, current=(0.0, 0.0, 100.0), look=(0.0, 0.0, 100.0), acceleration=(0.0, 0.0, 0.0))
    solve_case("diagnostic:straight", base, current=(1000.0, 0.0, 0.0), look=(1000.0, 0.0, 0.0), acceleration=(10.0, 0.0, 0.0))
    valid_cases += 5

    permissive = replace(profile("fpv_freestyle"), minimum_turn_radius_cm=1.0)
    right = solve_case("bank:right-clamped", permissive, acceleration=(0.0, 3500.0, 0.0))
    left = solve_case("bank:left-clamped", permissive, acceleration=(0.0, -3500.0, 0.0))
    require(close(right[6], -70.0) and close(left[6], 70.0), "signed bank clamp")
    solve_case("uptilt:positive", replace(permissive, path_follow_weight=0.0, horizon_stabilization_weight=0.0),
               look=(1000.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
    valid_cases += 3

    boundary = replace(base, minimum_turn_radius_cm=250.0)
    solve_case("physical:exact-boundary", boundary,
               current=(math.sqrt(250.0 * 900.0), 0.0, 0.0), look=(1000.0, 0.0, 0.0),
               acceleration=(0.0, 900.0, 0.0), jerk=(1800.0, 0.0, 0.0))
    valid_cases += 1

    positive = solve_case("quaternion-sign:positive", base)
    negative = solve_case("quaternion-sign:negative", base, body=tuple(-v for v in IDENTITY),
                          gimbal=tuple(-v for v in IDENTITY))
    require(all(same_rotation(a, b) for a, b in zip(positive[:3], negative[:3])), "quaternion sign invariance")
    valid_cases += 2

    invalid_cases = 0
    failures = (
        ("physical:acceleration", lambda: set_(obj, VECTOR_INPUTS[2], vector((0.0, 900.001, 0.0))), True),
        ("physical:jerk", lambda: set_(obj, VECTOR_INPUTS[3], vector((1800.001, 0.0, 0.0))), True),
        ("physical:radius", lambda: (set_(obj, VECTOR_INPUTS[0], vector((100.0, 0.0, 0.0))), set_(obj, VECTOR_INPUTS[2], vector((0.0, 100.0, 0.0)))), True),
        ("quat:body-zero", lambda: set_(obj, QUAT_INPUTS[0], quat((0.0, 0.0, 0.0, 0.0)))),
        ("quat:body-nonunit", lambda: set_(obj, QUAT_INPUTS[0], quat((0.0, 0.0, 0.0, 2.0)))),
        ("quat:gimbal-zero", lambda: set_(obj, QUAT_INPUTS[1], quat((0.0, 0.0, 0.0, 0.0)))),
        ("profile:path-low", lambda: set_(obj, PROFILE_PARAMETERS[0][0], -0.001)),
        ("profile:path-high", lambda: set_(obj, PROFILE_PARAMETERS[0][0], 1.001)),
        ("profile:horizon-low", lambda: set_(obj, PROFILE_PARAMETERS[1][0], -0.001)),
        ("profile:horizon-high", lambda: set_(obj, PROFILE_PARAMETERS[1][0], 1.001)),
        ("profile:lookahead-low", lambda: set_(obj, PROFILE_PARAMETERS[2][0], -0.001)),
        ("profile:lookahead-high", lambda: set_(obj, PROFILE_PARAMETERS[2][0], 5.001)),
        ("profile:bankgain-low", lambda: set_(obj, PROFILE_PARAMETERS[3][0], -0.001)),
        ("profile:bankgain-high", lambda: set_(obj, PROFILE_PARAMETERS[3][0], 2.001)),
        ("profile:maxbank-low", lambda: set_(obj, PROFILE_PARAMETERS[4][0], -0.001)),
        ("profile:maxbank-high", lambda: set_(obj, PROFILE_PARAMETERS[4][0], 85.001)),
        ("profile:uptilt-low", lambda: set_(obj, PROFILE_PARAMETERS[5][0], -45.001)),
        ("profile:uptilt-high", lambda: set_(obj, PROFILE_PARAMETERS[5][0], 45.001)),
        ("profile:angular-zero", lambda: set_(obj, PROFILE_PARAMETERS[6][0], 0.0)),
        ("profile:angular-high", lambda: set_(obj, PROFILE_PARAMETERS[6][0], 720.001)),
        ("profile:accel-zero", lambda: set_(obj, PROFILE_PARAMETERS[7][0], 0.0)),
        ("profile:accel-high", lambda: set_(obj, PROFILE_PARAMETERS[7][0], 10000.001)),
        ("profile:jerk-zero", lambda: set_(obj, PROFILE_PARAMETERS[8][0], 0.0)),
        ("profile:jerk-high", lambda: set_(obj, PROFILE_PARAMETERS[8][0], 50000.001)),
        ("profile:radius-zero", lambda: set_(obj, PROFILE_PARAMETERS[9][0], 0.0)),
        ("profile:radius-high", lambda: set_(obj, PROFILE_PARAMETERS[9][0], 100000.001)),
        ("overflow:motion", lambda: set_(obj, VECTOR_INPUTS[0], vector((1.0e308, 1.0e308, 0.0))), True),
    )
    for failure in failures:
        label, mutation, *stage = failure
        invalid_solve(label, mutation, stage[0] if stage else False)
        invalid_cases += 1

    reflection_sanitized = 0
    nonfinite_reached = 0
    for label, property_name, maker in (
        ("vector-nan", VECTOR_INPUTS[0], lambda value: vector((value, 0.0, 0.0))),
        ("vector-inf", VECTOR_INPUTS[1], lambda value: vector((value, 0.0, 0.0))),
        ("quat-nan", QUAT_INPUTS[0], lambda value: quat((0.0, 0.0, 0.0, value))),
        ("profile-inf", PROFILE_PARAMETERS[3][0], lambda value: value),
    ):
        for nonfinite in ((float("nan"),) if "nan" in label else (float("inf"), float("-inf"))):
            stage_inputs((1000.0, 0.0, 0.0), (900.0, 300.0, 0.0), (0.0, 300.0, 0.0),
                         (0.0, 0.0, 0.0), IDENTITY, IDENTITY, base)
            prior = normalized(get(obj, property_name))
            set_(obj, property_name, maker(nonfinite))
            reflected = normalized(get(obj, property_name))
            flattened = reflected if isinstance(reflected, tuple) else (reflected,)
            if all(math.isfinite(float(value)) for value in flattened):
                emit("REFLECTION_SANITIZED", label + ":" + repr(nonfinite))
                require(reflected == prior, label + ":unexpected finite replacement")
                reflection_sanitized += 1
                continue
            before = input_snapshot()
            poison_results()
            set_(obj, STAGE, True)
            obj.call_method("SolveAirframeGimbalV1")
            require(not bool(get(obj, STAGE)), label + ":stage")
            require(input_snapshot() == before, label + ":inputs-mutated")
            require_cleared(label)
            nonfinite_reached += 1

    rng = random.Random(0xEDD_A1)
    seeded = []
    for _index in range(160):
        selected = profile(rng.choice(tuple(profiles.PROFILES)))
        speed = rng.uniform(0.0, 2500.0)
        lateral = rng.uniform(-200.0, 200.0)
        if abs(lateral) > 1.0e-9 and speed * speed / abs(lateral) < selected.minimum_turn_radius_cm:
            lateral = 0.0
        seeded.append((selected, (speed, 0.0, 0.0),
                       (speed, rng.uniform(-500.0, 500.0), rng.uniform(-200.0, 200.0)),
                       (0.0, lateral, 0.0)))
    forward = [solve_case("seed-forward:" + str(index), *case) for index, case in enumerate(seeded)]
    for index, case in enumerate(reversed(seeded)):
        require(solve_case("seed-reverse:" + str(index), *case) == forward[len(seeded) - 1 - index],
                "history dependence:" + str(index))

    emit("VALID_CASES", valid_cases)
    emit("INVALID_FAIL_CLOSED_CASES", invalid_cases)
    emit("DETERMINISTIC_REPLAY_CASES", len(seeded))
    emit("NONFINITE_REACHED_BLUEPRINT", nonfinite_reached)
    emit("REFLECTION_SANITIZED_CASES", reflection_sanitized)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
