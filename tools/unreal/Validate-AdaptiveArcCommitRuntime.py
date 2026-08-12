"""Execute atomic adaptive arc-table publication and failure clearing."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_ADAPTIVE_ARC_COMMIT_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
WORK = (
    "TrajectoryArcBuildWorkU0V1", "TrajectoryArcBuildWorkU1V1",
    "TrajectoryArcBuildWorkP0V1", "TrajectoryArcBuildWorkP1V1",
    "TrajectoryArcBuildWorkDepthV1",
)
CANDIDATE = (
    "TrajectoryArcBuildCandidateUsV1", "TrajectoryArcBuildCandidatePositionsV1",
    "TrajectoryArcBuildCandidateDistancesV1", "TrajectoryArcBuildCandidateLengthV1",
    "TrajectoryArcBuildStageValidV1",
)
PUBLISHED = (
    "TrajectoryArcBuiltUsV1", "TrajectoryArcBuiltDistancesV1",
    "TrajectoryArcBuiltLengthV1", "TrajectoryArcBuildValidV1",
)
INPUTS = (
    "TrajectoryArcBuildInputStartPositionV1", "TrajectoryArcBuildInputEndPositionV1",
    "TrajectoryArcBuildInputStartVelocityUV1", "TrajectoryArcBuildInputEndVelocityUV1",
    "TrajectoryArcBuildInputStartAccelerationUV1", "TrajectoryArcBuildInputEndAccelerationUV1",
    "TrajectoryArcBuildInputLinearV1", "TrajectoryArcBuildInputToleranceV1",
    "TrajectoryArcBuildInputMaxDepthV1", "TrajectoryArcBuildInputMaxOperationsV1",
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "trajectory"))
from cinematic_reference import CompiledSegment, trace_arc_table_iterative  # noqa: E402


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
    return unreal.Vector(*(float(item) for item in value))


def tuple3(value):
    return float(value.x), float(value.y), float(value.z)


def segment(rng):
    start = tuple(rng.uniform(-300.0, 300.0) for _ in range(3))
    end = tuple(rng.uniform(-300.0, 300.0) for _ in range(3))
    return CompiledSegment(
        start_seconds=0.0,
        duration_seconds=1.0,
        spatial_curve_type="auto_cinematic",
        time_profile="linear",
        start=start,
        end=end,
        start_velocity_u=tuple(rng.uniform(-600.0, 600.0) for _ in range(3)),
        end_velocity_u=tuple(rng.uniform(-600.0, 600.0) for _ in range(3)),
        start_acceleration_u=tuple(rng.uniform(-1000.0, 1000.0) for _ in range(3)),
        end_acceleration_u=tuple(rng.uniform(-1000.0, 1000.0) for _ in range(3)),
        length=0.0,
        arc_table=(),
    )


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
properties = INPUTS + WORK + CANDIDATE + PUBLISHED
saved = {name: get(obj, name) for name in properties}


def poison_publication():
    set_(obj, PUBLISHED[0], [9.0, 10.0])
    set_(obj, PUBLISHED[1], [0.0, 99.0])
    set_(obj, PUBLISHED[2], 99.0)
    set_(obj, PUBLISHED[3], True)


def require_cleared(label):
    require(len(get(obj, PUBLISHED[0])) == 0, label + ":us")
    require(len(get(obj, PUBLISHED[1])) == 0, label + ":distances")
    require(float(get(obj, PUBLISHED[2])) == 0.0, label + ":length")
    require(not get(obj, PUBLISHED[3]), label + ":valid")
    require(not get(obj, CANDIDATE[4]), label + ":sticky-stage")


def stage(table, valid=True):
    set_(obj, WORK[0], [])
    set_(obj, WORK[1], [])
    set_(obj, WORK[2], [])
    set_(obj, WORK[3], [])
    set_(obj, WORK[4], [])
    set_(obj, CANDIDATE[0], [float(sample.u) for sample in table])
    # Candidate positions are diagnostic processing state; publication owns
    # only u/distance/length. Exact cardinality remains part of the boundary.
    set_(obj, CANDIDATE[1], [vector((0.0, 0.0, 0.0)) for _sample in table])
    set_(obj, CANDIDATE[2], [float(sample.distance) for sample in table])
    set_(obj, CANDIDATE[3], float(table[-1].distance))
    set_(obj, CANDIDATE[4], valid)


try:
    rng = random.Random(0xEDD069)
    tables = []
    for index in range(32):
        current = segment(rng)
        tolerance = (0.002, 0.01, 0.05, 0.2)[index % 4]
        table, _operations = trace_arc_table_iterative(current, tolerance, 8, 8191)
        tables.append(table)

    for index, table in enumerate(tables):
        stage(table)
        expected_us = [float(sample.u) for sample in table]
        expected_distances = [float(sample.distance) for sample in table]
        poison_publication()
        obj.call_method("CommitAdaptiveArcBuildV1")
        require(get(obj, PUBLISHED[3]), f"valid:{index}")
        require([float(value) for value in get(obj, PUBLISHED[0])] == expected_us, f"us:{index}")
        require([float(value) for value in get(obj, PUBLISHED[1])] == expected_distances, f"distances:{index}")
        require(float(get(obj, PUBLISHED[2])) == expected_distances[-1], f"length:{index}")

    base = tables[0]
    def replace_candidate(name, value):
        stage(base)
        set_(obj, name, value)

    def replace_candidate_item(name, index, value):
        stage(base)
        values = list(get(obj, name))
        values[index] = value
        set_(obj, name, values)

    cases = []
    cases.append(("stage-false", lambda: stage(base, False)))
    for work_name in WORK:
        cases.append(("nonempty-" + work_name, lambda name=work_name: (stage(base), set_(obj, name, [vector((1, 2, 3))] if "WorkP" in name else [1]))))
    cases.extend((
        ("too-short", lambda: stage(base[:1])),
        ("position-cardinality", lambda: replace_candidate(CANDIDATE[1], [vector((0.0, 0.0, 0.0)) for _sample in base[:-1]])),
        ("distance-cardinality", lambda: replace_candidate(CANDIDATE[2], [float(sample.distance) for sample in base[:-1]])),
        ("bad-first-u", lambda: replace_candidate_item(CANDIDATE[0], 0, 0.1)),
        ("bad-first-distance", lambda: replace_candidate_item(CANDIDATE[2], 0, 0.1)),
        ("bad-last-u", lambda: replace_candidate_item(CANDIDATE[0], -1, 0.9)),
        ("bad-length", lambda: replace_candidate(CANDIDATE[3], float(base[-1].distance) + 1.0)),
        ("negative-length", lambda: replace_candidate(CANDIDATE[3], -1.0)),
        ("duplicate-u", lambda: replace_candidate_item(CANDIDATE[0], 1, float(base[0].u))),
        ("decreasing-distance", lambda: replace_candidate_item(CANDIDATE[2], 1, -1.0)),
        ("nan-u", lambda: replace_candidate_item(CANDIDATE[0], 1, float("nan"))),
        ("nan-distance", lambda: replace_candidate_item(CANDIDATE[2], 1, float("nan"))),
        ("nan-length", lambda: replace_candidate(CANDIDATE[3], float("nan"))),
    ))
    for label, prepare in cases:
        prepare()
        poison_publication()
        obj.call_method("CommitAdaptiveArcBuildV1")
        require_cleared(label)

    emit("VALID_TABLES", len(tables))
    emit("FAILURE_CASES", len(cases))
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
