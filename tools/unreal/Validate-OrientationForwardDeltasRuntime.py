"""Execute compiled adjacent-key orientation deltas against the frozen oracle."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_ORIENTATION_FORWARD_DELTAS_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ALIGNED = "OrientationTrackCandidateAlignedQuatsV1"
DURATIONS = "OrientationTrackInputDurationsV1"
OUTPUT = "OrientationTrackCandidateForwardDeltasV1"
VALID = "OrientationTrackStageValidV1"
PRIMITIVE_START = "OrientationInputStartQuatV1"
PRIMITIVE_END = "OrientationInputEndQuatV1"
PRIMITIVE_RESULT = "OrientationResultDeltaVectorV1"
PRIMITIVE_VALID = "OrientationResultValidV1"


def emit(name, value):
    unreal.log(f"{PREFIX}|{name}|{value}")


def require(condition, message):
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def names(value):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in value).lstrip("_")
    return value, unreal.Name(value), snake, unreal.Name(snake)


def get(obj, name):
    for candidate in names(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError(name)


def set_(obj, name, value):
    for candidate in names(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(name)


def quat(value):
    return unreal.Quat(*(float(x) for x in value))


def vector_tuple(value):
    return float(value.x), float(value.y), float(value.z)


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools/trajectory"))
import orientation_reference as oracle

cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
properties = (
    ALIGNED, DURATIONS, OUTPUT, VALID, PRIMITIVE_START, PRIMITIVE_END,
    PRIMITIVE_RESULT, PRIMITIVE_VALID,
)
saved = {name: get(obj, name) for name in properties}
try:
    rng = random.Random(0xEDD062)
    fixtures = [
        ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 0.0)),
        ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    ]
    for _ in range(62):
        raw = [tuple(rng.uniform(-4.0, 4.0) for _ in range(4)) for _ in range(rng.randint(2, 64))]
        aligned = []
        for value in raw:
            current = oracle.normalize(value)
            if aligned and sum(a * b for a, b in zip(aligned[-1], current)) < 0.0:
                current = tuple(-x for x in current)
            aligned.append(current)
        fixtures.append(tuple(aligned))

    maximum = 0.0
    for index, values in enumerate(fixtures):
        expected = [oracle.logarithmic_delta(a, b) for a, b in zip(values, values[1:])]
        set_(obj, ALIGNED, [quat(value) for value in values])
        set_(obj, DURATIONS, [0.25 + i * 0.01 for i in range(len(values) - 1)])
        set_(obj, OUTPUT, [unreal.Vector(99.0, 98.0, 97.0)])
        set_(obj, VALID, True)
        obj.call_method("ComputeOrientationForwardDeltasV1")
        actual = [vector_tuple(value) for value in get(obj, OUTPUT)]
        require(get(obj, VALID), f"valid-stage:{index}")
        require(len(actual) == len(expected), f"count:{index}:{len(actual)}:{len(expected)}")
        for actual_value, expected_value in zip(actual, expected):
            error = math.sqrt(sum((a - e) ** 2 for a, e in zip(actual_value, expected_value)))
            maximum = max(maximum, error)
            require(error <= 3e-7, f"delta:{index}:{error}")

    set_(obj, ALIGNED, [quat((0, 0, 0, 1)), quat((0, 0, 1, 0))])
    set_(obj, DURATIONS, [1.0])
    set_(obj, OUTPUT, [unreal.Vector(7.0, 8.0, 9.0)])
    set_(obj, VALID, False)
    obj.call_method("ComputeOrientationForwardDeltasV1")
    require(len(get(obj, OUTPUT)) == 0, "prior-invalid leaked stale output")
    require(not get(obj, VALID), "prior-invalid healed")

    set_(obj, ALIGNED, [quat((0, 0, 0, 0)), quat((0, 0, 0, 1)), quat((0, 0, 1, 0))])
    set_(obj, DURATIONS, [1.0, 1.0])
    set_(obj, OUTPUT, [unreal.Vector(7.0, 8.0, 9.0)])
    set_(obj, VALID, True)
    obj.call_method("ComputeOrientationForwardDeltasV1")
    require(not get(obj, VALID), "primitive failure did not reject stage")
    require(len(get(obj, OUTPUT)) == 0, "later iteration healed first failure")

    set_(obj, ALIGNED, [quat((0, 0, 0, 1)), quat((0, 0, 1, 0)), quat((0, 0, 0, 0))])
    set_(obj, DURATIONS, [1.0, 1.0])
    set_(obj, OUTPUT, [unreal.Vector(7.0, 8.0, 9.0)])
    set_(obj, VALID, True)
    obj.call_method("ComputeOrientationForwardDeltasV1")
    require(not get(obj, VALID), "later primitive failure did not reject stage")
    require(len(get(obj, OUTPUT)) == 1, "transaction diagnostic prefix must be deterministic")

    emit("VALID_TRACKS", len(fixtures))
    emit("MAX_VECTOR_ERROR", maximum)
    emit("FAILURE_CASES", 3)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
