"""Execute bounded compiled position-route arc-slice staging in Unreal."""
from __future__ import annotations

import math
import random

import unreal


PREFIX = "EDD_POSITION_ROUTE_ARC_SLICE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
COMPILED = (
    "PositionRouteCompiledArcSampleStartsV1",
    "PositionRouteCompiledArcSampleCountsV1",
    "PositionRouteCompiledArcUsV1",
    "PositionRouteCompiledArcDistancesV1",
    "PositionRouteCompiledSegmentLengthsV1",
    "PositionRouteCompileValidV1",
)
SELECTED = ("PositionRouteResultSegmentIndexV1", "PositionRouteResultDistanceAlphaV1")
ARC = (
    "TrajectoryArcInputUsV1",
    "TrajectoryArcInputDistancesV1",
    "TrajectoryArcInputLengthV1",
    "TrajectoryArcInputDistanceAlphaV1",
    "TrajectoryArcResultUV1",
    "TrajectoryArcResultValidV1",
)


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


generated = unreal.load_class(None, CLASS)
require(generated is not None, "class")
obj = unreal.get_default_object(generated)
properties = COMPILED + SELECTED + ARC
saved = {name: get(obj, name) for name in properties}


def stage(starts, counts, us, distances, lengths, compile_valid, selected, alpha):
    values = (starts, counts, us, distances, lengths)
    for name, value in zip(COMPILED[:5], values):
        set_(obj, name, list(value))
    set_(obj, COMPILED[5], bool(compile_valid))
    set_(obj, SELECTED[0], int(selected))
    set_(obj, SELECTED[1], float(alpha))
    # Poison all primitive destination/output state. A no-op or stale success
    # therefore fails every valid and invalid case deterministically.
    set_(obj, ARC[0], [91.0, 92.0, 93.0])
    set_(obj, ARC[1], [81.0, 82.0, 83.0])
    set_(obj, ARC[2], 71.0)
    set_(obj, ARC[3], 0.71)
    set_(obj, ARC[4], 0.61)
    set_(obj, ARC[5], True)


def invoke(case):
    stage(*case)
    staged_before = tuple(get(obj, name) for name in COMPILED + SELECTED)
    obj.call_method("StagePositionRouteArcSliceV1")
    return staged_before, tuple(get(obj, name) for name in ARC)


def expect_valid(label, starts, counts, us, distances, lengths, selected, alpha):
    authored = (starts, counts, us, distances, lengths, True, selected, alpha)
    staged_before, result = invoke(authored)
    actual_us, actual_distances, actual_length, actual_alpha, actual_u, valid = result
    start = int(starts[selected])
    stop = start + int(counts[selected])
    require(bool(valid), f"{label}:valid")
    require(tuple(float(value) for value in actual_us) == tuple(float(value) for value in us[start:stop]), f"{label}:us")
    require(tuple(float(value) for value in actual_distances) == tuple(float(value) for value in distances[start:stop]), f"{label}:distances")
    require(float(actual_length) == float(lengths[selected]), f"{label}:length")
    require(float(actual_alpha) == float(alpha), f"{label}:alpha")
    require(float(actual_u) == 0.0, f"{label}:u-reset")
    # The helper is read-only with respect to the compiled publication.
    require(staged_before == tuple(get(obj, name) for name in COMPILED + SELECTED), f"{label}:source-mutated")


def expect_invalid(label, case):
    staged_before, result = invoke(case)
    actual_us, actual_distances, actual_length, actual_alpha, actual_u, valid = result
    # Unreal reflection can sanitize non-finite doubles. Only claim rejection
    # when the malformed authored value survives the reflection boundary.
    authored_length = float(case[4][case[6]]) if case[4] and 0 <= case[6] < len(case[4]) else 0.0
    authored_alpha = float(case[7])
    staged_lengths = tuple(float(value) for value in staged_before[4])
    staged_alpha = float(staged_before[7])
    sanitized = (not math.isfinite(authored_length) and all(math.isfinite(value) for value in staged_lengths)) or (not math.isfinite(authored_alpha) and math.isfinite(staged_alpha))
    if sanitized:
        emit("REFLECTION_SANITIZED", label)
        return False
    require(not bool(valid), f"{label}:valid")
    require(len(actual_us) == 0 and len(actual_distances) == 0, f"{label}:arrays-reset")
    require(float(actual_length) == 0.0, f"{label}:length-reset")
    require(float(actual_alpha) == 0.0, f"{label}:alpha-reset")
    require(float(actual_u) == 0.0, f"{label}:u-reset")
    return True


try:
    rng = random.Random(0xEDD078)
    valid_cases = 0
    segments = 0
    samples = 0

    # Fixed publication includes a zero-length segment and unequal table sizes.
    starts = (0, 2, 6)
    counts = (2, 4, 3)
    us = (0.0, 1.0, 0.0, 0.2, 0.8, 1.0, 0.0, 0.5, 1.0)
    distances = (0.0, 10.0, 0.0, 1.0, 8.0, 9.0, 0.0, 0.0, 0.0)
    lengths = (10.0, 9.0, 0.0)
    for selected in range(len(starts)):
        for alpha in (0.0, 1.0e-12, 0.125, 0.5, 0.999999999999, 1.0):
            expect_valid(f"fixed:{selected}:{alpha}", starts, counts, us, distances, lengths, selected, alpha)
            valid_cases += 1
    segments += len(starts)
    samples += len(us)

    # Random serialized publications exercise arbitrary contiguous flat slices.
    for route_index in range(64):
        route_segments = rng.randint(1, 48)
        route_starts = []
        route_counts = []
        route_us = []
        route_distances = []
        route_lengths = []
        for _segment in range(route_segments):
            count = rng.randint(2, 32)
            route_starts.append(len(route_us))
            route_counts.append(count)
            u_steps = [rng.uniform(1.0e-6, 3.0) for _ in range(count - 1)]
            u_total = sum(u_steps)
            local_us = [0.0]
            for step in u_steps:
                local_us.append(local_us[-1] + step / u_total)
            local_us[-1] = 1.0
            d_steps = [0.0 if rng.random() < 0.15 else rng.uniform(1.0e-6, 50.0) for _ in range(count - 1)]
            local_distances = [0.0]
            for step in d_steps:
                local_distances.append(local_distances[-1] + step)
            route_us.extend(local_us)
            route_distances.extend(local_distances)
            route_lengths.append(local_distances[-1])
        for selected in sorted({0, route_segments // 2, route_segments - 1, rng.randrange(route_segments)}):
            for alpha in (0.0, rng.random(), 1.0):
                expect_valid(f"random:{route_index}:{selected}:{alpha}", route_starts, route_counts, route_us, route_distances, route_lengths, selected, alpha)
                valid_cases += 1
        segments += route_segments
        samples += len(route_us)

    # Maximum route cardinality: 512 waypoints / 511 selected segments.
    max_segments = 511
    max_starts = tuple(index * 2 for index in range(max_segments))
    max_counts = (2,) * max_segments
    max_us = tuple(value for _ in range(max_segments) for value in (0.0, 1.0))
    max_distances = tuple(value for index in range(max_segments) for value in (0.0, float(index + 1)))
    max_lengths = tuple(float(index + 1) for index in range(max_segments))
    for selected in (0, 255, 510):
        expect_valid(f"maximum:{selected}", max_starts, max_counts, max_us, max_distances, max_lengths, selected, 0.375)
        valid_cases += 1
    segments += max_segments
    samples += len(max_us)

    base = (starts, counts, us, distances, lengths, True, 1, 0.5)
    invalid = (
        ("compile-invalid", base[:5] + (False,) + base[6:]),
        ("negative-index", base[:6] + (-1, 0.5)),
        ("index-at-count", base[:6] + (len(starts), 0.5)),
        ("counts-cardinality", (starts, counts[:-1], us, distances, lengths, True, 1, 0.5)),
        ("lengths-cardinality", (starts, counts, us, distances, lengths[:-1], True, 1, 0.5)),
        ("flat-cardinality", (starts, counts, us, distances[:-1], lengths, True, 1, 0.5)),
        ("count-underflow", (starts, (2, 1, 3), us, distances, lengths, True, 1, 0.5)),
        ("negative-start", ((0, -1, 6), counts, us, distances, lengths, True, 1, 0.5)),
        ("end-overflow", ((0, 7, 6), counts, us, distances, lengths, True, 1, 0.5)),
        ("integer-add-overflow", ((0, 2147483647, 6), counts, us, distances, lengths, True, 1, 0.5)),
        ("negative-length", (starts, counts, us, distances, (10.0, -1.0, 0.0), True, 1, 0.5)),
        ("nan-length", (starts, counts, us, distances, (10.0, float("nan"), 0.0), True, 1, 0.5)),
        ("alpha-underflow", base[:7] + (-1.0,)),
        ("alpha-overflow", base[:7] + (2.0,)),
        ("nan-alpha", base[:7] + (float("nan"),)),
    )
    invalid_reached = sum(expect_invalid(label, case) for label, case in invalid)

    # Repeated random access must not depend on a previous selected slice.
    sequence = (2, 0, 1, 2, 1, 0)
    snapshots = {}
    for selected in sequence:
        expect_valid(f"direct:{selected}", starts, counts, us, distances, lengths, selected, 0.25)
        current = (tuple(get(obj, ARC[0])), tuple(get(obj, ARC[1])), float(get(obj, ARC[2])))
        if selected in snapshots:
            require(snapshots[selected] == current, f"direct-history:{selected}")
        snapshots[selected] = current

    emit("VALID_CASES", valid_cases)
    emit("ROUTE_SEGMENTS", segments)
    emit("FLAT_SAMPLES", samples)
    emit("MAX_WAYPOINTS", 512)
    emit("INVALID_CASES", len(invalid))
    emit("INVALID_REACHED_BLUEPRINT", invalid_reached)
    emit("DIRECT_SCRUB_CASES", len(sequence))
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
