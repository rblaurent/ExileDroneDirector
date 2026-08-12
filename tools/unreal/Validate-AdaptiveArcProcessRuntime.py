"""Execute bounded adaptive arc processing against the frozen Python oracle."""

from __future__ import annotations

import math
import random
import sys
import importlib
from pathlib import Path

import unreal


PREFIX = "EDD_ADAPTIVE_ARC_PROCESS_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
import cinematic_reference as _cinematic_reference  # noqa: E402
importlib.reload(_cinematic_reference)
from cinematic_reference import (  # noqa: E402
    CompiledSegment,
    TrajectoryCompileError,
    evaluate_spatial,
    trace_arc_table_iterative,
)

VECTOR_INPUTS = (
    "TrajectoryArcBuildInputStartPositionV1", "TrajectoryArcBuildInputEndPositionV1",
    "TrajectoryArcBuildInputStartVelocityUV1", "TrajectoryArcBuildInputEndVelocityUV1",
    "TrajectoryArcBuildInputStartAccelerationUV1", "TrajectoryArcBuildInputEndAccelerationUV1",
)
SCALAR_INPUTS = (
    "TrajectoryArcBuildInputLinearV1", "TrajectoryArcBuildInputToleranceV1",
    "TrajectoryArcBuildInputMaxDepthV1", "TrajectoryArcBuildInputMaxOperationsV1",
)
WORK = (
    "TrajectoryArcBuildWorkU0V1", "TrajectoryArcBuildWorkU1V1",
    "TrajectoryArcBuildWorkP0V1", "TrajectoryArcBuildWorkP1V1",
    "TrajectoryArcBuildWorkDepthV1",
)
CANDIDATE = (
    "TrajectoryArcBuildCandidateUsV1", "TrajectoryArcBuildCandidatePositionsV1",
    "TrajectoryArcBuildCandidateDistancesV1",
)
SCRATCH = (
    "TrajectoryArcBuildCurrentU0V1", "TrajectoryArcBuildCurrentU1V1",
    "TrajectoryArcBuildCurrentP0V1", "TrajectoryArcBuildCurrentP1V1",
    "TrajectoryArcBuildCurrentDepthV1", "TrajectoryArcBuildMidpointUV1",
    "TrajectoryArcBuildMidpointPositionV1", "TrajectoryArcBuildOperationCountV1",
    "TrajectoryArcBuildCandidateLengthV1", "TrajectoryArcBuildStageValidV1",
)
PRIMITIVE = (
    "TrajectoryInputStartPositionVectorV1", "TrajectoryInputEndPositionVectorV1",
    "TrajectoryInputStartVelocityUVectorV1", "TrajectoryInputEndVelocityUVectorV1",
    "TrajectoryInputStartAccelerationUVectorV1", "TrajectoryInputEndAccelerationUVectorV1",
    "TrajectoryInputAlphaV1", "TrajectoryResultPositionVectorV1",
    "TrajectoryResultDerivativeUVectorV1", "TrajectoryResultSecondDerivativeUVectorV1",
    "TrajectoryResultVectorValidV1",
)


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def names(value):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in value).lstrip("_")
    return value, unreal.Name(value), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in names(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(name)
def set_(obj, name, value):
    for candidate in names(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(name)
def vector(value): return unreal.Vector(*(float(item) for item in value))
def tuple3(value): return float(value.x), float(value.y), float(value.z)
def close(left, right, tolerance=2.0e-5): return abs(float(left) - float(right)) <= tolerance
def vector_close(left, right, tolerance=2.0e-4):
    return all(close(a, b, tolerance) for a, b in zip(tuple3(left), right))


generated = unreal.load_class(None, CLASS)
require(generated is not None, "class missing")
component = unreal.get_default_object(generated)
touched = tuple(dict.fromkeys((*VECTOR_INPUTS, *SCALAR_INPUTS, *WORK, *CANDIDATE, *SCRATCH, *PRIMITIVE)))
saved = {name: get(component, name) for name in touched}


def segment(vectors, linear):
    return CompiledSegment(
        0.0, 1.0, "linear" if linear else "auto_cinematic", "linear",
        *vectors, (), 0.0,
    )


def stage(vectors, linear, tolerance, depth, operations):
    for name, value in zip(VECTOR_INPUTS, vectors): set_(component, name, vector(value))
    set_(component, "TrajectoryArcBuildInputLinearV1", bool(linear))
    set_(component, "TrajectoryArcBuildInputToleranceV1", float(tolerance))
    set_(component, "TrajectoryArcBuildInputMaxDepthV1", int(depth))
    set_(component, "TrajectoryArcBuildInputMaxOperationsV1", int(operations))


def initialize(vectors, linear, tolerance, depth, operations):
    stage(vectors, linear, tolerance, depth, operations)
    component.call_method("ResetAdaptiveArcBuildV1")
    component.call_method("ValidateAdaptiveArcBuildInputsV1")
    require(bool(get(component, "TrajectoryArcBuildStageValidV1")), "valid input rejected")
    component.call_method("InitializeAdaptiveArcBuildV1")
    require(bool(get(component, "TrajectoryArcBuildStageValidV1")), "initialization failed")


def validate_success(vectors, linear, tolerance, depth, operations, label):
    expected, expected_operations = trace_arc_table_iterative(
        segment(vectors, linear), tolerance, depth, operations
    )
    initialize(vectors, linear, tolerance, depth, operations)
    component.call_method("ProcessAdaptiveArcBuildV1")
    require(bool(get(component, "TrajectoryArcBuildStageValidV1")), f"{label}:stage invalid")
    require(all(len(get(component, name)) == 0 for name in WORK), f"{label}:work remains")
    actual_u = list(get(component, CANDIDATE[0]))
    actual_positions = list(get(component, CANDIDATE[1]))
    actual_distances = list(get(component, CANDIDATE[2]))
    require(len(actual_u) == len(expected), f"{label}:sample count")
    require(len(actual_positions) == len(expected), f"{label}:position count")
    require(len(actual_distances) == len(expected), f"{label}:distance count")
    for index, sample in enumerate(expected):
        require(close(actual_u[index], sample.u), f"{label}:u:{index}")
        require(close(actual_distances[index], sample.distance, 3.0e-4), f"{label}:distance:{index}")
        expected_position = evaluate_spatial(segment(vectors, linear), sample.u)
        require(vector_close(actual_positions[index], expected_position), f"{label}:position:{index}")
    require(close(get(component, "TrajectoryArcBuildCandidateLengthV1"), expected[-1].distance, 3.0e-4), f"{label}:length")
    require(int(get(component, "TrajectoryArcBuildOperationCountV1")) == expected_operations, f"{label}:operations")
    return len(expected), expected_operations


def poison_cardinality(name):
    value = list(get(component, name))
    if "P0" in name or "P1" in name or "Positions" in name:
        value.append(vector((99.0, 98.0, 97.0)))
    elif "Depth" in name:
        value.append(99)
    else:
        value.append(99.0)
    set_(component, name, value)


try:
    rng = random.Random(0xEDD069)
    valid_cases = total_samples = max_operations_seen = 0
    fixed = (
        (((0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)), True, 0.01, 6),
        (((0, 0, 0), (3, 4, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)), True, 0.01, 6),
        (((0, 0, 0), (10, -4, 8), (25, 0, 5), (-8, 18, 0), (2, -3, 4), (-1, 2, -5)), False, 0.001, 8),
    )
    cases = list(fixed)
    for _index in range(20):
        vectors = tuple(tuple(rng.uniform(-250.0, 250.0) for _axis in range(3)) for _vector in range(6))
        cases.append((vectors, bool(rng.randrange(2)), 10 ** rng.uniform(-4.0, 0.5), rng.randint(1, 10)))
    for index, (vectors, linear, tolerance, depth) in enumerate(cases):
        _table, needed = trace_arc_table_iterative(segment(vectors, linear), tolerance, depth, 8191)
        samples, operations = validate_success(vectors, linear, tolerance, depth, needed, f"valid-{index}")
        total_samples += samples; max_operations_seen = max(max_operations_seen, operations); valid_cases += 1

    # One operation short must fail closed, consume exactly its budget, and
    # retain unfinished synchronized work rather than claiming completion.
    budget_vectors, budget_linear, budget_tolerance, budget_depth = fixed[2]
    _table, needed = trace_arc_table_iterative(segment(budget_vectors, budget_linear), budget_tolerance, budget_depth, 8191)
    require(needed > 1, "budget fixture too small")
    initialize(budget_vectors, budget_linear, budget_tolerance, budget_depth, needed - 1)
    component.call_method("ProcessAdaptiveArcBuildV1")
    require(not bool(get(component, "TrajectoryArcBuildStageValidV1")), "budget exhaustion accepted")
    require(int(get(component, "TrajectoryArcBuildOperationCountV1")) == needed - 1, "budget count")
    require(len(get(component, WORK[0])) > 0, "budget exhaustion lost unfinished work")
    require(len({len(get(component, name)) for name in WORK}) == 1, "budget work desynchronized")

    # Every preflight array participates in an exact-one cardinality boundary.
    malformed = 0
    base = fixed[2]
    for name in (*WORK, *CANDIDATE):
        initialize(*base, 8191)
        poison_cardinality(name)
        component.call_method("ProcessAdaptiveArcBuildV1")
        require(not bool(get(component, "TrajectoryArcBuildStageValidV1")), f"cardinality accepted:{name}")
        require(int(get(component, "TrajectoryArcBuildOperationCountV1")) == 0, f"cardinality executed:{name}")
        malformed += 1
    initialize(*base, 8191)
    set_(component, "TrajectoryArcBuildStageValidV1", False)
    component.call_method("ProcessAdaptiveArcBuildV1")
    require(not bool(get(component, "TrajectoryArcBuildStageValidV1")), "prior failure healed")
    require(int(get(component, "TrajectoryArcBuildOperationCountV1")) == 0, "prior failure executed")
    malformed += 1

    emit("VALID_CASES", valid_cases)
    emit("TOTAL_SAMPLES", total_samples)
    emit("MAX_OPERATIONS", max_operations_seen)
    emit("BUDGET_EXHAUSTION_CASES", 1)
    emit("MALFORMED_PREFLIGHT_CASES", malformed)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items(): set_(component, name, value)
    emit("STATE_RESTORED", True)
