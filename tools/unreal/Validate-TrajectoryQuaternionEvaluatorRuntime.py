"""Execute the compiled quaternion evaluator against the frozen oracle."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_TRAJECTORY_QUATERNION_RUNTIME"
CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUTS = (
    "TrajectoryInputOrientationStartQuatV1",
    "TrajectoryInputOrientationStartControlQuatV1",
    "TrajectoryInputOrientationEndControlQuatV1",
    "TrajectoryInputOrientationEndQuatV1",
)
OUTPUT = "TrajectoryResultOrientationQuatV1"
VALID = "TrajectoryResultOrientationValidV1"
TOUCHED = (*INPUTS, "TrajectoryInputAlphaV1", OUTPUT, VALID)


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
def tuple4(value): return (float(value.x), float(value.y), float(value.z), float(value.w))


project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "tools" / "trajectory"))
import orientation_reference as oracle  # noqa: E402

generated = unreal.load_class(None, CLASS_PATH)
require(generated is not None, "generated class missing")
component = unreal.get_default_object(generated)
saved = {name: get_prop(component, name) for name in TOUCHED}
identity = (0.0, 0.0, 0.0, 1.0)


def stage(quats, alpha):
    for name, value in zip(INPUTS, quats): set_prop(component, name, quat(value))
    set_prop(component, "TrajectoryInputAlphaV1", alpha)
    set_prop(component, OUTPUT, quat((0.1, 0.2, 0.3, 0.4)))
    set_prop(component, VALID, True)


try:
    rng = random.Random(0xEDD058)
    fixtures = [(identity, identity, identity, identity)]
    fixtures += [
        tuple(oracle.normalize(tuple(rng.uniform(-1.0, 1.0) for _ in range(4))) for _ in range(4))
        for _ in range(100)
    ]
    valid = 0
    for quats in fixtures:
        segment = oracle.CompiledOrientationSegment(0, 1, *quats)
        for alpha in (-1.0, 0.0, 0.125, 0.5, 0.875, 1.0, 2.0):
            stage(quats, alpha)
            component.call_method("EvaluateSphericalBezierQuaternionV1")
            require(bool(get_prop(component, VALID)), f"valid rejected:{alpha}")
            actual = tuple4(get_prop(component, OUTPUT))
            expected = oracle._spherical_bezier(segment, max(0.0, min(1.0, alpha)))
            error = math.sqrt(sum(value * value for value in oracle.logarithmic_delta(actual, expected)))
            require(error <= 2e-7, f"rotation mismatch:{error}:{actual}!={expected}")
            require(abs(sum(value * value for value in actual) - 1.0) <= 2e-6, "nonunit output")
            valid += 1
    emit("VALID_CASES", valid)

    invalid = 0
    sanitized = 0
    for alpha in (math.nan, math.inf, -math.inf):
        stage((identity,) * 4, alpha)
        reflected = float(get_prop(component, "TrajectoryInputAlphaV1"))
        component.call_method("EvaluateSphericalBezierQuaternionV1")
        require(not math.isfinite(reflected), f"scalar nonfinite sanitized:{alpha}->{reflected}")
        require(not bool(get_prop(component, VALID)), f"bad alpha accepted:{alpha}")
        require(tuple4(get_prop(component, OUTPUT)) == identity, "bad alpha leaked stale output")
        invalid += 1

    for index in range(4):
        for bad in ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 2.0),
                    (math.nan, 0.0, 0.0, 1.0), (math.inf, 0.0, 0.0, 1.0)):
            values = [identity] * 4
            values[index] = bad
            stage(tuple(values), 0.5)
            reflected = tuple4(get_prop(component, INPUTS[index]))
            component.call_method("EvaluateSphericalBezierQuaternionV1")
            if all(math.isfinite(value) for value in reflected) and not all(math.isfinite(value) for value in bad):
                sanitized += 1
                require(bool(get_prop(component, VALID)), f"sanitized quaternion rejected:{index}:{bad}->{reflected}")
                continue
            require(not bool(get_prop(component, VALID)), f"bad quaternion accepted:{index}:{bad}->{reflected}")
            require(tuple4(get_prop(component, OUTPUT)) == identity, "bad quaternion leaked stale output")
            invalid += 1
    emit("INVALID_CASES", invalid)
    emit("REFLECTION_SANITIZED_QUATERNION_CASES", sanitized)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items(): set_prop(component, name, value)
    emit("STATE_RESTORED", True)
