"""Execute compiled cumulative arc-table inversion against the frozen oracle."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_ARC_TABLE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
PROPERTIES = (
    "TrajectoryArcInputUsV1",
    "TrajectoryArcInputDistancesV1",
    "TrajectoryArcInputLengthV1",
    "TrajectoryArcInputDistanceAlphaV1",
    "TrajectoryArcResultUV1",
    "TrajectoryArcResultValidV1",
    "TrajectoryArcScratchUpperIndexV1",
    "TrajectoryArcScratchValidV1",
)


def emit(name, value):
    unreal.log(f"{PREFIX}|{name}|{value}")


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
    raise RuntimeError(name)


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(name)


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import cinematic_reference as oracle


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
saved = {name: get(obj, name) for name in PROPERTIES}


def stage(us, distances, length, alpha):
    set_(obj, PROPERTIES[0], [float(value) for value in us])
    set_(obj, PROPERTIES[1], [float(value) for value in distances])
    set_(obj, PROPERTIES[2], float(length))
    set_(obj, PROPERTIES[3], float(alpha))
    # Poison every output/scratch field so stale success cannot satisfy a case.
    set_(obj, PROPERTIES[4], 0.875)
    set_(obj, PROPERTIES[5], True)
    set_(obj, PROPERTIES[6], 91)
    set_(obj, PROPERTIES[7], True)


def invoke(us, distances, length, alpha):
    stage(us, distances, length, alpha)
    staged = (
        tuple(float(value) for value in get(obj, PROPERTIES[0])),
        tuple(float(value) for value in get(obj, PROPERTIES[1])),
        float(get(obj, PROPERTIES[2])),
        float(get(obj, PROPERTIES[3])),
    )
    obj.call_method("InvertArcLengthTableV1")
    return staged, float(get(obj, PROPERTIES[4])), bool(get(obj, PROPERTIES[5]))


def assert_valid(label, us, distances, length, alpha):
    expected = oracle.invert_arc_table(us, distances, length, alpha)
    staged, actual, valid = invoke(us, distances, length, alpha)
    require(valid, label + ":valid")
    require(math.isfinite(actual), label + ":finite")
    require(-2.0e-12 <= actual <= 1.0 + 2.0e-12, label + ":bounds")
    error = abs(actual - expected)
    require(error <= 2.0e-9, f"{label}:value:{actual}:{expected}:{error}")
    return error, staged


def assert_invalid(label, us, distances, length, alpha):
    try:
        oracle.invert_arc_table(us, distances, length, alpha)
    except oracle.TrajectoryCompileError:
        pass
    else:
        raise RuntimeError(f"{PREFIX}|FAIL|oracle-accepted-invalid:{label}")
    staged, actual, valid = invoke(us, distances, length, alpha)
    # Native reflection can sanitize non-finite doubles. Only claim rejection
    # when the malformed value actually survives staging into Blueprint.
    sanitized = False
    authored = (tuple(us), tuple(distances), float(length), float(alpha))
    for authored_value, staged_value in zip(authored[0], staged[0]):
        sanitized = sanitized or (not math.isfinite(float(authored_value)) and math.isfinite(staged_value))
    for authored_value, staged_value in zip(authored[1], staged[1]):
        sanitized = sanitized or (not math.isfinite(float(authored_value)) and math.isfinite(staged_value))
    sanitized = sanitized or (not math.isfinite(authored[2]) and math.isfinite(staged[2]))
    sanitized = sanitized or (not math.isfinite(authored[3]) and math.isfinite(staged[3]))
    if sanitized:
        emit("REFLECTION_SANITIZED", label)
        return False
    require(not valid, label + ":valid")
    require(actual == 0.0, label + ":stale-result")
    return True


try:
    rng = random.Random(0xEDD067)
    maximum_error = 0.0
    valid_cases = 0

    fixed = (
        ((0.0, 1.0), (0.0, 10.0), 10.0),
        ((0.0, 0.2, 0.7, 1.0), (0.0, 1.0, 1.0, 9.0), 9.0),
        ((0.0, 0.25, 0.5, 1.0), (0.0, 0.0, 0.0, 0.0), 0.0),
    )
    for table_index, (us, distances, length) in enumerate(fixed):
        for alpha_index, alpha in enumerate((-2.0, 0.0, 1.0e-12, 0.125, 0.5, 0.999999999999, 1.0, 3.0)):
            error, _ = assert_valid(f"fixed:{table_index}:{alpha_index}", us, distances, length, alpha)
            maximum_error = max(maximum_error, error)
            valid_cases += 1

    # Random serialized tables include cumulative plateaus while preserving
    # strictly increasing u. This exercises the exact published-data boundary.
    for table_index in range(128):
        count = rng.randint(2, 96)
        u_steps = [rng.uniform(1.0e-5, 3.0) for _ in range(count - 1)]
        u_total = sum(u_steps)
        us = [0.0]
        for step in u_steps:
            us.append(us[-1] + step / u_total)
        us[-1] = 1.0
        d_steps = [0.0 if rng.random() < 0.18 else rng.uniform(1.0e-6, 40.0) for _ in range(count - 1)]
        distances = [0.0]
        for step in d_steps:
            distances.append(distances[-1] + step)
        length = distances[-1]
        for alpha_index, alpha in enumerate((-1.0, 0.0, 1.0, 2.0) + tuple(rng.uniform(-0.5, 1.5) for _ in range(20))):
            error, _ = assert_valid(f"random:{table_index}:{alpha_index}", us, distances, length, alpha)
            maximum_error = max(maximum_error, error)
            valid_cases += 1

    # Prove compatibility with actual adaptive tables from both spatial modes.
    compiled_segments = 0
    for trajectory_index in range(40):
        point_count = rng.randint(2, 12)
        points = [tuple(rng.uniform(-3000.0, 3000.0) for _ in range(3)) for _ in range(point_count)]
        authored = [
            oracle.AuthoredSegment(
                rng.uniform(0.05, 8.0),
                "linear" if rng.random() < 0.35 else "auto_cinematic",
                "cinematic_s_curve",
            )
            for _ in range(point_count - 1)
        ]
        trajectory = oracle.compile_trajectory(points, authored, arc_tolerance=0.01, max_arc_depth=12)
        for segment_index, segment in enumerate(trajectory.segments):
            us = tuple(sample.u for sample in segment.arc_table)
            distances = tuple(sample.distance for sample in segment.arc_table)
            for alpha_index, alpha in enumerate((0.0, 0.25, 0.5, 0.75, 1.0, rng.random())):
                error, _ = assert_valid(
                    f"compiled:{trajectory_index}:{segment_index}:{alpha_index}",
                    us, distances, segment.length, alpha,
                )
                maximum_error = max(maximum_error, error)
                valid_cases += 1
            compiled_segments += 1

    invalid = (
        ("empty", (), (), 0.0, 0.5),
        ("single", (0.0,), (0.0,), 0.0, 0.5),
        ("mismatch", (0.0, 1.0), (0.0,), 0.0, 0.5),
        ("first-u", (0.1, 1.0), (0.0, 2.0), 2.0, 0.5),
        ("first-distance", (0.0, 1.0), (0.1, 2.0), 2.0, 0.5),
        ("last-u", (0.0, 0.9), (0.0, 2.0), 2.0, 0.5),
        ("last-distance", (0.0, 1.0), (0.0, 1.0), 2.0, 0.5),
        ("u-duplicate", (0.0, 0.4, 0.4, 1.0), (0.0, 1.0, 2.0, 3.0), 3.0, 0.5),
        ("u-descending", (0.0, 0.7, 0.6, 1.0), (0.0, 1.0, 2.0, 3.0), 3.0, 0.5),
        ("distance-descending", (0.0, 0.4, 0.8, 1.0), (0.0, 2.0, 1.0, 3.0), 3.0, 0.5),
        ("negative-length", (0.0, 1.0), (0.0, -1.0), -1.0, 0.5),
        ("nan-u", (0.0, float("nan"), 1.0), (0.0, 1.0, 2.0), 2.0, 0.5),
        ("inf-distance", (0.0, 0.5, 1.0), (0.0, float("inf"), 2.0), 2.0, 0.5),
        ("nan-length", (0.0, 1.0), (0.0, 1.0), float("nan"), 0.5),
        ("inf-alpha", (0.0, 1.0), (0.0, 1.0), 1.0, float("inf")),
        ("nan-alpha", (0.0, 1.0), (0.0, 1.0), 1.0, float("nan")),
    )
    invalid_reached = sum(assert_invalid(*case) for case in invalid)

    # Repeated direct scrubs must not depend on the previous scan result.
    us = (0.0, 0.1, 0.4, 0.9, 1.0)
    distances = (0.0, 1.0, 1.0, 8.0, 10.0)
    first = invoke(us, distances, 10.0, 0.37)[1:]
    for alpha in (1.0, 0.0, 0.9, 0.1, 0.7, 0.2):
        invoke(us, distances, 10.0, alpha)
    second = invoke(us, distances, 10.0, 0.37)[1:]
    require(first == second, "direct-scrub-history")

    emit("VALID_TABLE_EVALUATIONS", valid_cases)
    emit("COMPILED_SEGMENTS", compiled_segments)
    emit("INVALID_CASES", len(invalid))
    emit("INVALID_REACHED_BLUEPRINT", invalid_reached)
    emit("DIRECT_SCRUB_CASES", 1)
    emit("MAX_U_ERROR", maximum_error)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
