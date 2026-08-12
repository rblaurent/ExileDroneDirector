"""Execute compiled position-route velocity assembly against the frozen oracle."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_POSITION_ROUTE_VELOCITY_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
POSITIONS = "PositionRouteInputWaypointPositionsV1"
DURATIONS = "PositionRouteInputDurationsV1"
CURVES = "PositionRouteInputSpatialCurveTypesV1"
OUTPUT = "PositionRouteCandidateWaypointVelocitiesV1"
VALID = "PositionRouteStageValidV1"


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


def tuple3(value):
    return float(value.x), float(value.y), float(value.z)


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools/trajectory"))
import cinematic_reference as oracle

generated = unreal.load_class(None, CLASS)
require(generated is not None, "class")
obj = unreal.get_default_object(generated)
properties = (POSITIONS, DURATIONS, CURVES, OUTPUT, VALID)
saved = {name: get(obj, name) for name in properties}


def run(points, durations, curves, expected, label):
    set_(obj, POSITIONS, [vector(point) for point in points])
    set_(obj, DURATIONS, [float(duration) for duration in durations])
    set_(obj, CURVES, list(curves))
    set_(obj, OUTPUT, [vector((99.0, 98.0, 97.0))])
    set_(obj, VALID, True)
    obj.call_method("ComputePositionRouteVelocitiesV1")
    actual = [tuple3(value) for value in get(obj, OUTPUT)]
    require(bool(get(obj, VALID)), f"validity mutated:{label}")
    require(len(actual) == len(expected), f"cardinality:{label}:{len(actual)}!={len(expected)}")
    maximum = 0.0
    for index, (found, wanted) in enumerate(zip(actual, expected)):
        error = max(abs(left - right) for left, right in zip(found, wanted))
        maximum = max(maximum, error)
        require(error <= 2.0e-6, f"velocity:{label}:{index}:{error}:{found}:{wanted}")
    return maximum


try:
    fixtures = [
        (((0, 0, 0), (10, 20, 30)), (2.0,), ("auto_cinematic",)),
        (((0, 0, 0), (10, -20, 5), (30, -30, 25)), (1.0, 2.0), ("auto_cinematic", "auto_cinematic")),
        (((0, 0, 0), (10, 10, 10), (0, 20, 10)), (1.0, 1.0), ("auto_cinematic", "auto_cinematic")),
        (((0, 0, 0), (10, 0, 10), (20, 20, 0), (40, 40, -10)), (1.0, 3.0, 2.0), ("linear", "auto_cinematic", "auto_cinematic")),
    ]
    rng = random.Random(0xEDD073)
    for _ in range(96):
        count = rng.randint(2, 64)
        point = [rng.uniform(-1000.0, 1000.0) for _ in range(3)]
        points = [tuple(point)]
        for _index in range(count - 1):
            point = [component + rng.uniform(-500.0, 500.0) for component in point]
            points.append(tuple(point))
        durations = tuple(10.0 ** rng.uniform(-2.0, 2.0) for _ in range(count - 1))
        curves = tuple("linear" if rng.random() < 0.25 else "auto_cinematic" for _ in range(count - 1))
        fixtures.append((tuple(points), durations, curves))
    count = 512
    points = tuple((float(index), float(index * index % 101), float((index * 17) % 43)) for index in range(count))
    fixtures.append((points, tuple(0.5 + (index % 7) for index in range(count - 1)), tuple("auto_cinematic" for _ in range(count - 1))))

    maximum_error = 0.0
    axis_checks = 0
    for fixture_index, (points, durations, curves) in enumerate(fixtures):
        authored = tuple(oracle.AuthoredSegment(duration, curve, "linear") for duration, curve in zip(durations, curves))
        expected = oracle._auto_velocities(points, authored)
        maximum_error = max(maximum_error, run(points, durations, curves, expected, f"fixture-{fixture_index}"))
        axis_checks += len(points) * 3

    set_(obj, POSITIONS, [vector((0, 0, 0)), vector((1, 1, 1))])
    set_(obj, DURATIONS, [1.0])
    set_(obj, CURVES, ["auto_cinematic"])
    set_(obj, OUTPUT, [vector((99, 98, 97))])
    set_(obj, VALID, False)
    obj.call_method("ComputePositionRouteVelocitiesV1")
    require(len(get(obj, OUTPUT)) == 0, "prior-invalid stale output")
    require(not bool(get(obj, VALID)), "prior-invalid verdict healed")

    emit("VALID_ROUTES", len(fixtures))
    emit("AXIS_VALUES_PROVED", axis_checks)
    emit("MAX_COMPONENT_ERROR", maximum_error)
    emit("MAX_WAYPOINTS_PROVED", 512)
    emit("PRIOR_INVALID_CASES", 1)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
