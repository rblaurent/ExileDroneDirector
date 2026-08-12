"""Execute compiled adaptive arc reset and validation edge cases."""

from __future__ import annotations

import math, random
import unreal


PREFIX = "EDD_ADAPTIVE_ARC_BOUNDARY_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
VECTOR_INPUTS = (
    "TrajectoryArcBuildInputStartPositionV1", "TrajectoryArcBuildInputEndPositionV1",
    "TrajectoryArcBuildInputStartVelocityUV1", "TrajectoryArcBuildInputEndVelocityUV1",
    "TrajectoryArcBuildInputStartAccelerationUV1", "TrajectoryArcBuildInputEndAccelerationUV1",
)
SCALAR_INPUTS = (
    "TrajectoryArcBuildInputLinearV1", "TrajectoryArcBuildInputToleranceV1",
    "TrajectoryArcBuildInputMaxDepthV1", "TrajectoryArcBuildInputMaxOperationsV1",
)
RESET_ARRAYS = (
    "TrajectoryArcBuildWorkU0V1", "TrajectoryArcBuildWorkU1V1",
    "TrajectoryArcBuildWorkP0V1", "TrajectoryArcBuildWorkP1V1",
    "TrajectoryArcBuildWorkDepthV1", "TrajectoryArcBuildCandidateUsV1",
    "TrajectoryArcBuildCandidatePositionsV1", "TrajectoryArcBuildCandidateDistancesV1",
    "TrajectoryArcBuiltUsV1", "TrajectoryArcBuiltDistancesV1",
)
RESET_SCALARS = (
    "TrajectoryArcBuildCurrentU0V1", "TrajectoryArcBuildCurrentU1V1",
    "TrajectoryArcBuildCurrentP0V1", "TrajectoryArcBuildCurrentP1V1",
    "TrajectoryArcBuildCurrentDepthV1", "TrajectoryArcBuildMidpointUV1",
    "TrajectoryArcBuildMidpointPositionV1", "TrajectoryArcBuildOperationCountV1",
    "TrajectoryArcBuildCandidateLengthV1", "TrajectoryArcBuildStageValidV1",
    "TrajectoryArcBuiltLengthV1", "TrajectoryArcBuildValidV1",
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
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in value).lstrip("_"); return value, unreal.Name(value), snake, unreal.Name(snake)
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
def vector(values): return unreal.Vector(*(float(value) for value in values))
def vector_tuple(value): return float(value.x), float(value.y), float(value.z)
def finite_vector(value): return all(math.isfinite(item) for item in vector_tuple(value))


generated = unreal.load_class(None, CLASS); require(generated is not None, "class missing"); component = unreal.get_default_object(generated)
all_touched = tuple(dict.fromkeys((*VECTOR_INPUTS, *SCALAR_INPUTS, *RESET_ARRAYS, *RESET_SCALARS, *PRIMITIVE)))
saved = {name: get(component, name) for name in all_touched}


def stage(vectors, linear, tolerance, depth, operations):
    for name, values in zip(VECTOR_INPUTS, vectors): set_(component, name, vector(values))
    set_(component, "TrajectoryArcBuildInputLinearV1", bool(linear))
    set_(component, "TrajectoryArcBuildInputToleranceV1", float(tolerance))
    set_(component, "TrajectoryArcBuildInputMaxDepthV1", int(depth))
    set_(component, "TrajectoryArcBuildInputMaxOperationsV1", int(operations))


def validate(expected, label):
    set_(component, "TrajectoryArcBuildStageValidV1", not expected)
    component.call_method("ValidateAdaptiveArcBuildInputsV1")
    actual = bool(get(component, "TrajectoryArcBuildStageValidV1"))
    require(actual is expected, f"{label}:{actual}!={expected}")


try:
    # Poison every reset-owned field, then prove one executable call clears it.
    for name in RESET_ARRAYS:
        if "P0" in name or "P1" in name or "Positions" in name:
            set_(component, name, [vector((1, 2, 3)), vector((-4, 5, -6))])
        elif "Depth" in name:
            set_(component, name, [7, 9])
        else:
            set_(component, name, [1.25, 9.5])
    for name in RESET_SCALARS:
        if "P0" in name or "P1" in name or "Position" in name:
            set_(component, name, vector((7, -8, 9)))
        elif "Valid" in name:
            set_(component, name, True)
        elif "Depth" in name or "Count" in name:
            set_(component, name, 77)
        else:
            set_(component, name, 123.5)
    component.call_method("ResetAdaptiveArcBuildV1")
    require(all(len(get(component, name)) == 0 for name in RESET_ARRAYS), "reset arrays retained stale values")
    for name in RESET_SCALARS:
        value = get(component, name)
        if "P0" in name or "P1" in name or "Position" in name:
            require(vector_tuple(value) == (0.0, 0.0, 0.0), f"{name} not zero")
        elif "Valid" in name:
            require(value is False, f"{name} not false")
        else:
            require(float(value) == 0.0, f"{name} not zero")
    emit("RESET_FIELDS", len(RESET_ARRAYS) + len(RESET_SCALARS))

    rng = random.Random(0xEDD067)
    valid = invalid = sanitized = 0
    for index in range(64):
        vectors = tuple(tuple(rng.uniform(-1e6, 1e6) for _ in range(3)) for _ in range(6))
        stage(vectors, index % 2 == 0, 10 ** rng.uniform(-6, 2), rng.randint(1, 12), rng.randint(1, 8191))
        validate(True, f"valid-{index}"); valid += 1
    base = ((0, 0, 0), (10, 20, 30), (1, 2, 3), (4, 5, 6), (-1, -2, -3), (-4, -5, -6))
    for tolerance, depth, operations, label in (
        (0.0, 12, 8191, "zero-tolerance"), (-1.0, 12, 8191, "negative-tolerance"),
        (math.nan, 12, 8191, "nan-tolerance"), (math.inf, 12, 8191, "inf-tolerance"),
        (0.01, 0, 8191, "depth-low"), (0.01, 13, 8191, "depth-high"),
        (0.01, 12, 0, "operations-low"), (0.01, 12, 8192, "operations-high"),
    ):
        stage(base, False, tolerance, depth, operations); validate(False, label); invalid += 1
    for vector_index in range(6):
        for component_index in range(3):
            malformed = [list(value) for value in base]; malformed[vector_index][component_index] = math.nan
            stage(malformed, False, 0.01, 12, 8191)
            reflected = get(component, VECTOR_INPUTS[vector_index])
            if finite_vector(reflected):
                sanitized += 1
            else:
                validate(False, f"nonfinite-vector-{vector_index}-{component_index}"); invalid += 1
    emit("VALID_CASES", valid); emit("INVALID_CASES", invalid); emit("REFLECTION_SANITIZED_VECTOR_CASES", sanitized)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items(): set_(component, name, value)
    emit("STATE_RESTORED", True)
