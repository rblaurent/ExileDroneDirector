"""Execute the compiled orientation-control compiler against its frozen oracle."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_ORIENTATION_COMPILER_RUNTIME"
CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
TOUCHED = (
    "OrientationInputStartQuatV1", "OrientationInputEndQuatV1",
    "OrientationInputPreviousDeltaVectorV1", "OrientationInputNextDeltaVectorV1",
    "OrientationInputStartTangentRateVectorV1", "OrientationInputEndTangentRateVectorV1",
    "OrientationInputPreviousDurationV1", "OrientationInputNextDurationV1", "OrientationInputDurationV1",
    "OrientationResultDeltaVectorV1", "OrientationResultAlignedEndQuatV1",
    "OrientationResultTangentRateVectorV1", "OrientationResultStartControlQuatV1",
    "OrientationResultEndControlQuatV1", "OrientationResultValidV1",
    "OrientationScratchStartExponentQuatV1", "OrientationScratchEndExponentQuatV1",
)
IDENTITY = (0.0, 0.0, 0.0, 1.0)
ROTATION_TOLERANCE_RADIANS = 1e-6
VECTOR_TOLERANCE = 1e-6


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def candidates(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def get_prop(obj, name):
    for candidate in candidates(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"could not read {name}")


def set_prop(obj, name, value):
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception: pass
    raise RuntimeError(f"could not set {name}")


def quat(value): return unreal.Quat(*(float(component) for component in value))
def vec(value): return unreal.Vector(*(float(component) for component in value))
def tuple4(value): return (float(value.x), float(value.y), float(value.z), float(value.w))
def tuple3(value): return (float(value.x), float(value.y), float(value.z))
def distance3(a, b): return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "tools" / "trajectory"))
import orientation_reference as oracle  # noqa: E402

generated = unreal.load_class(None, CLASS_PATH)
require(generated is not None, "generated class missing")
component = unreal.get_default_object(generated)
saved = {name: get_prop(component, name) for name in TOUCHED}


def set_quat(name, value): set_prop(component, name, quat(value))
def set_vec(name, value): set_prop(component, name, vec(value))
def angle_error(a, b):
    delta = oracle.logarithmic_delta(a, b)
    return math.sqrt(sum(value * value for value in delta))


try:
    rng = random.Random(0xEDD059)
    valid = invalid = sanitized = 0
    maximum_log_error = maximum_tangent_error = maximum_control_error = 0.0

    pairs = [(IDENTITY, IDENTITY)] + [
        (oracle.normalize(tuple(rng.uniform(-1.0, 1.0) for _ in range(4))),
         oracle.normalize(tuple(rng.uniform(-1.0, 1.0) for _ in range(4))))
        for _ in range(40)
    ]
    for start, end in pairs:
        set_quat("OrientationInputStartQuatV1", start)
        set_quat("OrientationInputEndQuatV1", end)
        set_vec("OrientationResultDeltaVectorV1", (9, 9, 9))
        set_quat("OrientationResultAlignedEndQuatV1", (0.1, 0.2, 0.3, 0.4))
        set_prop(component, "OrientationResultValidV1", False)
        component.call_method("ComputeOrientationLogDeltaV1")
        require(bool(get_prop(component, "OrientationResultValidV1")), "log valid rejected")
        log_error = distance3(tuple3(get_prop(component, "OrientationResultDeltaVectorV1")), oracle.logarithmic_delta(start, end))
        maximum_log_error = max(maximum_log_error, log_error)
        require(log_error <= VECTOR_TOLERANCE, f"log mismatch:{log_error}")
        aligned = tuple4(get_prop(component, "OrientationResultAlignedEndQuatV1"))
        expected_aligned = end if sum(x * y for x, y in zip(start, end)) >= 0.0 else tuple(-x for x in end)
        aligned_error = angle_error(aligned, expected_aligned)
        maximum_control_error = max(maximum_control_error, aligned_error)
        require(aligned_error <= ROTATION_TOLERANCE_RADIANS, f"aligned end mismatch:{aligned_error}")
        valid += 1

    tangent_cases = [((0, 0, 0), (0, 0, 0), 1.0, 1.0)] + [
        (tuple(rng.uniform(-3, 3) for _ in range(3)), tuple(rng.uniform(-3, 3) for _ in range(3)),
         10 ** rng.uniform(-2, 1), 10 ** rng.uniform(-2, 1))
        for _ in range(50)
    ]
    for previous, following, previous_duration, next_duration in tangent_cases:
        set_vec("OrientationInputPreviousDeltaVectorV1", previous)
        set_vec("OrientationInputNextDeltaVectorV1", following)
        set_prop(component, "OrientationInputPreviousDurationV1", previous_duration)
        set_prop(component, "OrientationInputNextDurationV1", next_duration)
        set_vec("OrientationResultTangentRateVectorV1", (9, 9, 9))
        set_prop(component, "OrientationResultValidV1", False)
        component.call_method("ComputeOrientationTangentRateV1")
        left = tuple(value / previous_duration for value in previous)
        right = tuple(value / next_duration for value in following)
        expected = tuple((x + y) * 0.5 for x, y in zip(left, right))
        magnitude = math.sqrt(sum(value * value for value in expected))
        limit = 3.0 * min(math.sqrt(sum(value * value for value in left)), math.sqrt(sum(value * value for value in right)))
        if magnitude > limit and magnitude > 1e-12: expected = tuple(value * limit / magnitude for value in expected)
        require(bool(get_prop(component, "OrientationResultValidV1")), "tangent valid rejected")
        tangent_error = distance3(tuple3(get_prop(component, "OrientationResultTangentRateVectorV1")), expected)
        maximum_tangent_error = max(maximum_tangent_error, tangent_error)
        require(tangent_error <= VECTOR_TOLERANCE, f"tangent mismatch:{tangent_error}")
        valid += 1

    for _ in range(50):
        start, end = pairs[rng.randrange(len(pairs))]
        start_rate = tuple(rng.uniform(-2, 2) for _ in range(3))
        end_rate = tuple(rng.uniform(-2, 2) for _ in range(3))
        duration = 10 ** rng.uniform(-2, 1)
        set_quat("OrientationInputStartQuatV1", start); set_quat("OrientationInputEndQuatV1", end)
        set_vec("OrientationInputStartTangentRateVectorV1", start_rate); set_vec("OrientationInputEndTangentRateVectorV1", end_rate)
        set_prop(component, "OrientationInputDurationV1", duration)
        set_quat("OrientationResultStartControlQuatV1", (0.1, 0.2, 0.3, 0.4)); set_quat("OrientationResultEndControlQuatV1", (0.4, 0.3, 0.2, 0.1))
        set_prop(component, "OrientationResultValidV1", False)
        component.call_method("BuildOrientationSegmentControlsV1")
        expected_start = oracle.normalize(oracle.multiply(start, oracle._exp_vector(tuple(value * duration / 6.0 for value in start_rate))))
        expected_end = oracle.normalize(oracle.multiply(end, oracle._exp_vector(tuple(value * -duration / 6.0 for value in end_rate))))
        require(bool(get_prop(component, "OrientationResultValidV1")), "controls valid rejected")
        actual_start = tuple4(get_prop(component, "OrientationResultStartControlQuatV1"))
        actual_end = tuple4(get_prop(component, "OrientationResultEndControlQuatV1"))
        start_error = angle_error(actual_start, expected_start)
        end_error = angle_error(actual_end, expected_end)
        maximum_control_error = max(maximum_control_error, start_error, end_error)
        require(start_error <= ROTATION_TOLERANCE_RADIANS, f"start control mismatch:{start_error}:{start_rate}:{duration}:{actual_start}!={expected_start}")
        require(end_error <= ROTATION_TOLERANCE_RADIANS, f"end control mismatch:{end_error}:{end_rate}:{duration}:{actual_end}!={expected_end}")
        valid += 1
    emit("VALID_CASES", valid)
    emit("MAX_LOG_VECTOR_ERROR", maximum_log_error)
    emit("MAX_TANGENT_VECTOR_ERROR", maximum_tangent_error)
    emit("MAX_CONTROL_ANGULAR_ERROR_RADIANS", maximum_control_error)

    for duration in (0.0, -1.0, math.nan, math.inf):
        set_vec("OrientationInputPreviousDeltaVectorV1", (1, 0, 0)); set_vec("OrientationInputNextDeltaVectorV1", (1, 0, 0))
        set_prop(component, "OrientationInputPreviousDurationV1", duration); set_prop(component, "OrientationInputNextDurationV1", 1.0)
        set_vec("OrientationResultTangentRateVectorV1", (9, 9, 9)); set_prop(component, "OrientationResultValidV1", True)
        reflected = float(get_prop(component, "OrientationInputPreviousDurationV1"))
        component.call_method("ComputeOrientationTangentRateV1")
        if not math.isfinite(duration): require(not math.isfinite(reflected), f"duration sanitized:{duration}->{reflected}")
        require(not bool(get_prop(component, "OrientationResultValidV1")), f"bad duration accepted:{duration}")
        require(tuple3(get_prop(component, "OrientationResultTangentRateVectorV1")) == (0.0, 0.0, 0.0), "bad duration leaked output")
        invalid += 1

    invalid_quaternions = (
        (0.0, 0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0, 0.0),
    )
    for bad in invalid_quaternions:
        for bad_is_start in (True, False):
            set_quat("OrientationInputStartQuatV1", bad if bad_is_start else IDENTITY)
            set_quat("OrientationInputEndQuatV1", IDENTITY if bad_is_start else bad)
            set_vec("OrientationResultDeltaVectorV1", (9, 9, 9))
            set_quat("OrientationResultAlignedEndQuatV1", (0.1, 0.2, 0.3, 0.4))
            set_prop(component, "OrientationResultValidV1", True)
            component.call_method("ComputeOrientationLogDeltaV1")
            require(not bool(get_prop(component, "OrientationResultValidV1")), f"bad log quaternion accepted:{bad}:{bad_is_start}")
            require(tuple3(get_prop(component, "OrientationResultDeltaVectorV1")) == (0.0, 0.0, 0.0), "bad log quaternion leaked delta")
            require(tuple4(get_prop(component, "OrientationResultAlignedEndQuatV1")) == IDENTITY, "bad log quaternion leaked aligned end")
            invalid += 1

    for bad in invalid_quaternions:
        for bad_is_start in (True, False):
            set_quat("OrientationInputStartQuatV1", bad if bad_is_start else IDENTITY)
            set_quat("OrientationInputEndQuatV1", IDENTITY if bad_is_start else bad)
            set_vec("OrientationInputStartTangentRateVectorV1", (1, 0, 0))
            set_vec("OrientationInputEndTangentRateVectorV1", (1, 0, 0))
            set_prop(component, "OrientationInputDurationV1", 1.0)
            set_quat("OrientationResultStartControlQuatV1", (0.1, 0.2, 0.3, 0.4))
            set_quat("OrientationResultEndControlQuatV1", (0.4, 0.3, 0.2, 0.1))
            set_prop(component, "OrientationResultValidV1", True)
            component.call_method("BuildOrientationSegmentControlsV1")
            require(not bool(get_prop(component, "OrientationResultValidV1")), f"bad control quaternion accepted:{bad}:{bad_is_start}")
            require(tuple4(get_prop(component, "OrientationResultStartControlQuatV1")) == IDENTITY, "bad control quaternion leaked start")
            require(tuple4(get_prop(component, "OrientationResultEndControlQuatV1")) == IDENTITY, "bad control quaternion leaked end")
            invalid += 1

    for duration in (0.0, -1.0, math.nan, math.inf):
        set_quat("OrientationInputStartQuatV1", IDENTITY); set_quat("OrientationInputEndQuatV1", IDENTITY)
        set_vec("OrientationInputStartTangentRateVectorV1", (1, 0, 0)); set_vec("OrientationInputEndTangentRateVectorV1", (1, 0, 0))
        set_prop(component, "OrientationInputDurationV1", duration)
        set_quat("OrientationResultStartControlQuatV1", (0.1, 0.2, 0.3, 0.4)); set_quat("OrientationResultEndControlQuatV1", (0.4, 0.3, 0.2, 0.1))
        set_prop(component, "OrientationResultValidV1", True)
        component.call_method("BuildOrientationSegmentControlsV1")
        require(not bool(get_prop(component, "OrientationResultValidV1")), f"bad control duration accepted:{duration}")
        require(tuple4(get_prop(component, "OrientationResultStartControlQuatV1")) == IDENTITY, "bad control leaked start")
        require(tuple4(get_prop(component, "OrientationResultEndControlQuatV1")) == IDENTITY, "bad control leaked end")
        invalid += 1
    emit("INVALID_CASES", invalid)
    emit("REFLECTION_SANITIZED_CASES", sanitized)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items(): set_prop(component, name, value)
    emit("STATE_RESTORED", True)
