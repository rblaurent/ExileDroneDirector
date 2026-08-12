"""Execute the compiled scalar trajectory kernels on the generated-class CDO.

The kernels only read and write their explicitly staged component properties,
so the class default object is a deterministic compiled Blueprint instance for
this test.  Every touched property is restored even when an assertion fails.
The same script is suitable for live remote execution and a fresh headless
Unreal process, which gives us both bytecode and cold-load evidence.
"""

from __future__ import annotations

import math
import random

import unreal


PREFIX = "EDD_TRAJECTORY_SCALAR_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
)
PROFILES = (
    "linear",
    "smoothstep",
    "smootherstep",
    "cinematic_s_curve",
    "accelerate_through",
    "brake_into",
)
INPUT_NAMES = (
    "TrajectoryInputStartValueV1",
    "TrajectoryInputStartVelocityUV1",
    "TrajectoryInputStartAccelerationUV1",
    "TrajectoryInputEndValueV1",
    "TrajectoryInputEndVelocityUV1",
    "TrajectoryInputEndAccelerationUV1",
)
TOUCHED_NAMES = (
    "TrajectoryInputProfileV1",
    "TrajectoryInputAlphaV1",
    *INPUT_NAMES,
    "TrajectoryResultValueV1",
    "TrajectoryResultDerivativeUV1",
    "TrajectoryResultSecondDerivativeUV1",
    "TrajectoryResultValidV1",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def candidates(name: str):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return (name, unreal.Name(name), snake, unreal.Name(snake))


def get_prop(obj, name: str):
    errors = []
    for candidate in candidates(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not read {name}: {'; '.join(errors)}")


def set_prop(obj, name: str, value) -> None:
    errors = []
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not set {name}: {'; '.join(errors)}")


def close(actual, expected: float, label: str, relative: float = 2.0e-9) -> None:
    actual_value = float(actual)
    tolerance = relative * max(1.0, abs(float(expected)))
    require(abs(actual_value - float(expected)) <= tolerance, f"{label}:{actual_value}!={expected}")


def time_reference(name: str, alpha: float) -> float:
    x = max(0.0, min(1.0, float(alpha)))
    if name == "linear":
        return x
    if name == "smoothstep":
        return x * x * (3.0 - 2.0 * x)
    if name == "smootherstep":
        return x**3 * (x * (x * 6.0 - 15.0) + 10.0)
    if name == "cinematic_s_curve":
        return 35.0 * x**4 - 84.0 * x**5 + 70.0 * x**6 - 20.0 * x**7
    if name == "accelerate_through":
        return x * x
    if name == "brake_into":
        return 1.0 - (1.0 - x) ** 2
    raise RuntimeError(name)


def quintic_reference(values, alpha: float):
    p0, v0, a0, p1, v1, a1 = values
    x = max(0.0, min(1.0, float(alpha)))
    x2, x3, x4, x5 = x * x, x**3, x**4, x**5
    basis = (
        1.0 - 10.0*x3 + 15.0*x4 - 6.0*x5,
        x - 6.0*x3 + 8.0*x4 - 3.0*x5,
        0.5*(x2 - 3.0*x3 + 3.0*x4 - x5),
        10.0*x3 - 15.0*x4 + 6.0*x5,
        -4.0*x3 + 7.0*x4 - 3.0*x5,
        0.5*(x3 - 2.0*x4 + x5),
    )
    derivative = (
        -30.0*x2 + 60.0*x3 - 30.0*x4,
        1.0 - 18.0*x2 + 32.0*x3 - 15.0*x4,
        x - 4.5*x2 + 6.0*x3 - 2.5*x4,
        30.0*x2 - 60.0*x3 + 30.0*x4,
        -12.0*x2 + 28.0*x3 - 15.0*x4,
        1.5*x2 - 4.0*x3 + 2.5*x4,
    )
    second = (
        -60.0*x + 180.0*x2 - 120.0*x3,
        -36.0*x + 96.0*x2 - 60.0*x3,
        1.0 - 9.0*x + 18.0*x2 - 10.0*x3,
        60.0*x - 180.0*x2 + 120.0*x3,
        -24.0*x + 84.0*x2 - 60.0*x3,
        3.0*x - 12.0*x2 + 10.0*x3,
    )
    return tuple(sum(weight * value for weight, value in zip(weights, values)) for weights in (basis, derivative, second))


def seed_stale_results(component) -> None:
    set_prop(component, "TrajectoryResultValueV1", 123.0)
    set_prop(component, "TrajectoryResultDerivativeUV1", 456.0)
    set_prop(component, "TrajectoryResultSecondDerivativeUV1", 789.0)
    set_prop(component, "TrajectoryResultValidV1", True)


generated_class = unreal.load_class(None, CLASS_PATH)
require(generated_class is not None, f"generated class missing:{CLASS_PATH}")
component = unreal.get_default_object(generated_class)
require(component is not None, "generated-class CDO missing")
saved = {name: get_prop(component, name) for name in TOUCHED_NAMES}

try:
    # All supported time profiles, clamping, endpoints, and representative
    # interior points execute through compiled Blueprint bytecode.
    time_cases = 0
    for profile in PROFILES:
        previous = -1.0
        for alpha in (-2.0, 0.0, 0.125, 0.25, 0.5, 0.875, 1.0, 2.0):
            seed_stale_results(component)
            set_prop(component, "TrajectoryInputProfileV1", profile)
            set_prop(component, "TrajectoryInputAlphaV1", alpha)
            component.call_method("EvaluateTimeProfileV1")
            require(bool(get_prop(component, "TrajectoryResultValidV1")), f"valid time rejected:{profile}/{alpha}")
            actual = float(get_prop(component, "TrajectoryResultValueV1"))
            expected = time_reference(profile, alpha)
            close(actual, expected, f"time:{profile}/{alpha}")
            if alpha >= 0.0:
                require(actual + 2.0e-12 >= previous, f"time nonmonotonic:{profile}/{alpha}")
                previous = actual
            time_cases += 1
    emit("TIME_VALID_CASES", time_cases)

    for profile, alpha in (("", 0.5), ("bounce", 0.5), ("linear", math.nan), ("linear", math.inf), ("linear", -math.inf)):
        seed_stale_results(component)
        set_prop(component, "TrajectoryInputProfileV1", profile)
        set_prop(component, "TrajectoryInputAlphaV1", alpha)
        component.call_method("EvaluateTimeProfileV1")
        require(not bool(get_prop(component, "TrajectoryResultValidV1")), f"invalid time accepted:{profile}/{alpha}")
        close(get_prop(component, "TrajectoryResultValueV1"), 0.0, "invalid time stale value", 0.0)
        close(get_prop(component, "TrajectoryResultDerivativeUV1"), 0.0, "invalid time stale derivative", 0.0)
        close(get_prop(component, "TrajectoryResultSecondDerivativeUV1"), 0.0, "invalid time stale second", 0.0)
    emit("TIME_INVALID_CASES", 5)

    randomizer = random.Random(0xEDD054)
    fixtures = [
        ((0.0, 0.0, 0.0, 10.0, 0.0, 0.0), -2.0),
        ((0.0, 4.0, 0.0, 10.0, 7.0, 0.0), 0.0),
        ((0.0, 4.0, 2.0, 10.0, 7.0, -3.0), 0.5),
        ((0.0, 4.0, 0.0, 10.0, 7.0, 0.0), 1.0),
        ((0.0, 4.0, 2.0, 10.0, 7.0, -3.0), 2.0),
    ]
    fixtures.extend(
        (tuple(randomizer.uniform(-100.0, 100.0) for _ in range(6)), randomizer.uniform(-1.0, 2.0))
        for _ in range(64)
    )
    for values, alpha in fixtures:
        seed_stale_results(component)
        set_prop(component, "TrajectoryInputAlphaV1", alpha)
        for name, value in zip(INPUT_NAMES, values):
            set_prop(component, name, value)
        component.call_method("EvaluateQuinticScalarV1")
        require(bool(get_prop(component, "TrajectoryResultValidV1")), f"valid quintic rejected:{values}/{alpha}")
        expected = quintic_reference(values, alpha)
        for name, wanted in zip(
            ("TrajectoryResultValueV1", "TrajectoryResultDerivativeUV1", "TrajectoryResultSecondDerivativeUV1"),
            expected,
        ):
            close(get_prop(component, name), wanted, f"quintic:{name}/{values}/{alpha}")
    emit("QUINTIC_VALID_CASES", len(fixtures))

    invalid_cases = 0
    for nonfinite in (math.nan, math.inf, -math.inf):
        for bad_index in range(7):
            values = [1.0] * 7
            values[bad_index] = nonfinite
            seed_stale_results(component)
            set_prop(component, "TrajectoryInputAlphaV1", values[0])
            for name, value in zip(INPUT_NAMES, values[1:]):
                set_prop(component, name, value)
            component.call_method("EvaluateQuinticScalarV1")
            require(not bool(get_prop(component, "TrajectoryResultValidV1")), f"nonfinite quintic accepted:{bad_index}/{nonfinite}")
            for name in ("TrajectoryResultValueV1", "TrajectoryResultDerivativeUV1", "TrajectoryResultSecondDerivativeUV1"):
                close(get_prop(component, name), 0.0, f"invalid quintic stale:{bad_index}/{name}", 0.0)
            invalid_cases += 1
    emit("QUINTIC_INVALID_CASES", invalid_cases)
    emit("COMPLETE", "PASS")
finally:
    for property_name, value in saved.items():
        set_prop(component, property_name, value)
    emit("STATE_RESTORED", True)
