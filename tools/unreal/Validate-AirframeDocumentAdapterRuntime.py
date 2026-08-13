"""Execute the live lossless document adapter against its independent oracle."""
from __future__ import annotations

import importlib
import json
import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_AIRFRAME_DOCUMENT_ADAPTER_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUTS = (
    "AirframeDocumentInputSchemaVersionV2",
    "AirframeDocumentInputTrajectoryEngineVersionV2",
    "AirframeDocumentInputDurationSecondsV2",
    "AirframeDocumentInputDefaultFlightProfileV2",
    "AirframeDocumentInputFixedStepSecondsV2",
    "AirframeDocumentInputWaypointIdsV2",
    "AirframeDocumentInputWaypointPositionsV2",
    "AirframeDocumentInputWaypointBodyQuatsV2",
    "AirframeDocumentInputWaypointGimbalQuatsV2",
    "AirframeDocumentInputSegmentIdsV2",
    "AirframeDocumentInputSegmentFromWaypointIdsV2",
    "AirframeDocumentInputSegmentToWaypointIdsV2",
    "AirframeDocumentInputSegmentDurationsV2",
    "AirframeDocumentInputSegmentSpatialCurveTypesV2",
    "AirframeDocumentInputSegmentTimeProfilesV2",
    "AirframeDocumentInputSegmentFlightProfileOverridesV2",
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
    raise RuntimeError("missing property:" + name)


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError("could not set property:" + name)


def vector(value):
    return unreal.Vector(*(float(component) for component in value))


def quat(value):
    return unreal.Quat(*(float(component) for component in value))


def vt(value):
    return float(value.x), float(value.y), float(value.z)


def qt(value):
    return float(value.x), float(value.y), float(value.z), float(value.w)


def yaw(degrees):
    half = math.radians(degrees) * 0.5
    return 0.0, 0.0, math.sin(half), math.cos(half)


def pitch(degrees):
    half = math.radians(degrees) * 0.5
    return 0.0, math.sin(half), 0.0, math.cos(half)


def close(left, right, tolerance=3.0e-4):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def same_rotation(left, right, tolerance=3.0e-4):
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if left_length <= 1.0e-12 or right_length <= 1.0e-12:
        return False
    dot = abs(sum(a * b for a, b in zip(left, right)) / (left_length * right_length))
    return dot >= 1.0 - tolerance


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools/trajectory"))
import compiled_document_source_adapter_reference as oracle

oracle = importlib.reload(oracle)
cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)

specs = {}
for schema_path in sorted((root / "tools/trajectory").glob("*_blueprint_schema.json")):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for spec in schema.get("variables", ()):
        specs.setdefault(spec["name"], spec)


def clone(name, value):
    spec = specs[name]
    kind = spec["type"]
    if spec.get("container") == "Array":
        if kind == "Vector":
            return [vector(vt(item)) for item in value]
        if kind == "Quat":
            return [quat(qt(item)) for item in value]
        return list(value)
    if kind == "Vector":
        return vector(vt(value))
    if kind == "Quat":
        return quat(qt(value))
    return value


def normalized(name, value):
    spec = specs[name]
    kind = spec["type"]
    if spec.get("container") == "Array":
        if kind == "Vector":
            return tuple(vt(item) for item in value)
        if kind == "Quat":
            return tuple(qt(item) for item in value)
        return tuple(value)
    if kind == "Vector":
        return vt(value)
    if kind == "Quat":
        return qt(value)
    return value


saved = {name: clone(name, get(obj, name)) for name in specs}


def make_case(seed, count=None, warning=False):
    rng = random.Random(seed)
    count = count or rng.randint(2, 7)
    durations = tuple(rng.choice((0.5, 0.75, 1.0, 1.25)) for _ in range(count - 1))
    speed = rng.uniform(25.0, 55.0)
    points = [(rng.uniform(-20.0, 20.0), rng.uniform(-10.0, 10.0), rng.uniform(-5.0, 5.0))]
    body_angles = [rng.uniform(-12.0, 12.0)]
    gimbal_angles = [rng.uniform(-8.0, 8.0)]
    body_rate = rng.uniform(1.0, 4.0)
    gimbal_rate = rng.uniform(-3.0, -0.5)
    for index, duration in enumerate(durations):
        previous = points[-1]
        # Keep the production-path fixture physically flyable.  Diagnostics
        # are exercised by the independently authored body/gimbal rate jumps
        # below; a one-segment lateral kink can violate the downstream profile
        # turn-radius limit before the adapter itself is reached.
        points.append((previous[0] + speed * duration, previous[1], previous[2]))
        body_angles.append(body_angles[-1] + body_rate * duration + (2.0 if warning and index == 1 else 0.0))
        gimbal_angles.append(gimbal_angles[-1] + gimbal_rate * duration - (1.5 if warning and index == 1 else 0.0))
    ids = tuple(100 + index * 7 for index in range(count))
    waypoints = tuple(
        oracle.CompiledDocumentWaypointV2(ids[index], tuple(points[index]), yaw(body_angles[index]), pitch(gimbal_angles[index]))
        for index in range(count)
    )
    segments = tuple(
        oracle.CompiledDocumentSegmentV2(
            1000 + index * 11, ids[index], ids[index + 1], durations[index], "linear", "linear", ""
        )
        for index in range(count - 1)
    )
    document = oracle.CompiledTrajectoryDocumentV2(waypoints, segments, sum(durations))
    return document, rng.choice((0.1, 0.2, 0.25))


def stage(document, step, thresholds=(1.0, 1.0, 1.0)):
    set_(obj, "AirframeDocumentInputSchemaVersionV2", document.schema_version)
    set_(obj, "AirframeDocumentInputTrajectoryEngineVersionV2", document.trajectory_engine_version)
    set_(obj, "AirframeDocumentInputDurationSecondsV2", document.duration_seconds)
    set_(obj, "AirframeDocumentInputDefaultFlightProfileV2", document.default_flight_profile)
    set_(obj, "AirframeDocumentInputFixedStepSecondsV2", step)
    set_(obj, "AirframeDocumentInputWaypointIdsV2", [item.waypoint_id for item in document.waypoints])
    set_(obj, "AirframeDocumentInputWaypointPositionsV2", [vector(item.position) for item in document.waypoints])
    set_(obj, "AirframeDocumentInputWaypointBodyQuatsV2", [quat(item.body_rotation) for item in document.waypoints])
    set_(obj, "AirframeDocumentInputWaypointGimbalQuatsV2", [quat(item.gimbal_rotation) for item in document.waypoints])
    set_(obj, "AirframeDocumentInputSegmentIdsV2", [item.segment_id for item in document.segments])
    set_(obj, "AirframeDocumentInputSegmentFromWaypointIdsV2", [item.from_waypoint_id for item in document.segments])
    set_(obj, "AirframeDocumentInputSegmentToWaypointIdsV2", [item.to_waypoint_id for item in document.segments])
    set_(obj, "AirframeDocumentInputSegmentDurationsV2", [item.duration_seconds for item in document.segments])
    set_(obj, "AirframeDocumentInputSegmentSpatialCurveTypesV2", [item.spatial_curve_type for item in document.segments])
    set_(obj, "AirframeDocumentInputSegmentTimeProfilesV2", [item.time_profile for item in document.segments])
    set_(obj, "AirframeDocumentInputSegmentFlightProfileOverridesV2", [item.flight_profile_override for item in document.segments])
    set_(obj, "AirframeDocumentDiagnosticPositionVelocityThresholdV2", thresholds[0])
    set_(obj, "AirframeDocumentDiagnosticPositionAccelerationThresholdV2", thresholds[1])
    set_(obj, "AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2", thresholds[2])


def input_snapshot():
    return tuple(normalized(name, get(obj, name)) for name in INPUTS)


def downstream_snapshot():
    names = (
        "PositionRouteInputWaypointPositionsV1",
        "AirframeSourceInputBodyWaypointQuatsV1",
        "AirframeSourceInputGimbalWaypointQuatsV1",
        "AirframeDesiredStreamInputAuthoredBodyQuatsV1",
        "AirframeDesiredStreamInputAuthoredGimbalQuatsV1",
        "AirframePrebakeCompiledBodyQuatsV1",
        "AirframePrebakeCompiledGimbalQuatsV1",
    )
    return tuple(normalized(name, get(obj, name)) for name in names)


def require_success(expected, label):
    require(
        bool(get(obj, "AirframeDocumentAdapterStageValidV2")),
        label
        + ":stage:failure="
        + str(get(obj, "AirframeDocumentAdapterFailureCodeV2"))
        + ":duration="
        + repr(float(get(obj, "AirframeDocumentInputDurationSecondsV2")))
        + ":accumulator="
        + repr(float(get(obj, "AirframeDocumentAdapterDurationAccumulatorV2"))),
    )
    require(bool(get(obj, "AirframeDocumentAdapterCompileValidV2")), label + ":adapter")
    require(bool(get(obj, "AirframeSourceCompileValidV1")), label + ":source")
    require(bool(get(obj, "AirframeDesiredStreamCompileValidV1")), label + ":desired")
    require(bool(get(obj, "AirframePrebakeCompileValidV1")), label + ":prebake")
    require(bool(get(obj, "AirframeDocumentDiagnosticsValidV2")), label + ":diagnostics")
    require(str(get(obj, "AirframeDocumentAdapterFailureCodeV2")) == "", label + ":failure-code")
    actual_body = tuple(qt(item) for item in get(obj, "AirframeSourceInputBodyWaypointQuatsV1"))
    actual_gimbal = tuple(qt(item) for item in get(obj, "AirframeSourceInputGimbalWaypointQuatsV1"))
    require(len(actual_body) == len(expected.body_rotations), label + ":body-count")
    require(len(actual_gimbal) == len(expected.gimbal_rotations), label + ":gimbal-count")
    require(all(same_rotation(a, b) for a, b in zip(actual_body, expected.body_rotations)), label + ":body-values")
    require(all(same_rotation(a, b) for a, b in zip(actual_gimbal, expected.gimbal_rotations)), label + ":gimbal-values")
    require(any(not same_rotation(a, b, 1.0e-6) for a, b in zip(actual_body, actual_gimbal)), label + ":distinct-authorship")
    diagnostics = expected.diagnostics
    require(tuple(int(value) for value in get(obj, "AirframeDocumentDiagnosticWaypointIdsV2")) == tuple(row.waypoint_id for row in diagnostics.joins), label + ":diagnostic-ids")
    fields = (
        ("AirframeDocumentDiagnosticPositionVelocityJumpsV2", "position_velocity_jump_cm_per_second"),
        ("AirframeDocumentDiagnosticPositionAccelerationJumpsV2", "position_acceleration_jump_cm_per_second_squared"),
        ("AirframeDocumentDiagnosticBodyAngularRateJumpsV2", "authored_body_rate_jump_degrees_per_second"),
        ("AirframeDocumentDiagnosticGimbalAngularRateJumpsV2", "authored_gimbal_rate_jump_degrees_per_second"),
    )
    for name, field in fields:
        actual = tuple(float(value) for value in get(obj, name))
        wanted = tuple(getattr(row, field) for row in diagnostics.joins)
        require(len(actual) == len(wanted) and all(close(a, b) for a, b in zip(actual, wanted)), label + ":" + name)
    flags = tuple(bool(value) for value in get(obj, "AirframeDocumentDiagnosticDiscontinuousFlagsV2"))
    require(flags == tuple(row.discontinuous for row in diagnostics.joins), label + ":flags")
    require(int(get(obj, "AirframeDocumentDiagnosticCountV2")) == diagnostics.discontinuity_count, label + ":diagnostic-count")


def require_top_level_failure(label):
    require(not bool(get(obj, "AirframeDocumentAdapterStageValidV2")), label + ":stage")
    require(not bool(get(obj, "AirframeDocumentAdapterCompileValidV2")), label + ":adapter")
    require(not bool(get(obj, "AirframeSourceCompileValidV1")), label + ":source")
    require(not bool(get(obj, "AirframeDesiredStreamCompileValidV1")), label + ":desired")
    require(not bool(get(obj, "AirframePrebakeCompileValidV1")), label + ":prebake")
    require(not bool(get(obj, "AirframeDocumentDiagnosticsValidV2")), label + ":diagnostics")


try:
    cases = [make_case(0xEDDA00 + index, warning=(index == 3)) for index in range(10)]
    expected = [oracle.compile_document_to_airframe_sources_v2(document, step) for document, step in cases]
    for index, ((document, step), wanted) in enumerate(zip(cases, expected)):
        stage(document, step)
        before = input_snapshot()
        obj.call_method("CompileAirframeDocumentSourceAdapterV2")
        require(input_snapshot() == before, f"forward:{index}:inputs-mutated")
        require_success(wanted, f"forward:{index}")
    for reverse_index, index in enumerate(reversed(range(len(cases)))):
        document, step = cases[index]
        stage(document, step)
        before = input_snapshot()
        obj.call_method("CompileAirframeDocumentSourceAdapterV2")
        require(input_snapshot() == before, f"reverse:{reverse_index}:inputs-mutated")
        require_success(expected[index], f"reverse:{reverse_index}")

    base, step = cases[2]
    invalid = []
    invalid.append(("schema", oracle.CompiledTrajectoryDocumentV2(base.waypoints, base.segments, base.duration_seconds, schema_version=1), step))
    invalid.append(("duration", oracle.CompiledTrajectoryDocumentV2(base.waypoints, base.segments, base.duration_seconds + 0.25), step))
    duplicate = (base.waypoints[0], oracle.CompiledDocumentWaypointV2(base.waypoints[0].waypoint_id, base.waypoints[1].position, base.waypoints[1].body_rotation, base.waypoints[1].gimbal_rotation), *base.waypoints[2:])
    invalid.append(("waypoint-id", oracle.CompiledTrajectoryDocumentV2(tuple(duplicate), base.segments, base.duration_seconds), step))
    wrong = (oracle.CompiledDocumentSegmentV2(base.segments[0].segment_id, base.segments[0].from_waypoint_id, -1, base.segments[0].duration_seconds, "linear", "linear", ""), *base.segments[1:])
    invalid.append(("adjacency", oracle.CompiledTrajectoryDocumentV2(base.waypoints, tuple(wrong), base.duration_seconds), step))
    invalid.append(("fixed-step", base, 0.001))
    for label, document, invalid_step in invalid:
        stage(document, invalid_step)
        before = input_snapshot()
        obj.call_method("CompileAirframeDocumentSourceAdapterV2")
        require(input_snapshot() == before, label + ":inputs-mutated")
        require_top_level_failure(label)

    # A malformed/missing gimbal channel has no fallback to the body channel.
    stage(base, step)
    set_(obj, "AirframeDocumentInputWaypointGimbalQuatsV2", [])
    body_before = normalized("AirframeDocumentInputWaypointBodyQuatsV2", get(obj, "AirframeDocumentInputWaypointBodyQuatsV2"))
    obj.call_method("CompileAirframeDocumentSourceAdapterV2")
    require_top_level_failure("missing-gimbal")
    require(normalized("AirframeDocumentInputWaypointBodyQuatsV2", get(obj, "AirframeDocumentInputWaypointBodyQuatsV2")) == body_before, "missing-gimbal:body-mutated")

    # Diagnostic thresholds change warnings only; motion remains accepted and
    # exactly identical. Invalid thresholds disable diagnostics, not motion.
    warning_document, warning_step = make_case(0xEDDA99, count=4, warning=True)
    stage(warning_document, warning_step, (0.0, 0.0, 0.0))
    obj.call_method("CompileAirframeDocumentSourceAdapterV2")
    require(bool(get(obj, "AirframeDocumentAdapterCompileValidV2")), "tight:adapter")
    tight_motion = downstream_snapshot()
    tight_count = int(get(obj, "AirframeDocumentDiagnosticCountV2"))
    require(tight_count > 0, "tight:no-warning")
    stage(warning_document, warning_step, (1.0e9, 1.0e9, 1.0e9))
    obj.call_method("CompileAirframeDocumentSourceAdapterV2")
    require(bool(get(obj, "AirframeDocumentAdapterCompileValidV2")), "loose:adapter")
    require(downstream_snapshot() == tight_motion, "thresholds:motion-mutated")
    require(int(get(obj, "AirframeDocumentDiagnosticCountV2")) == 0, "loose:warning")
    stage(warning_document, warning_step, (-1.0, 1.0, 1.0))
    obj.call_method("CompileAirframeDocumentSourceAdapterV2")
    require(bool(get(obj, "AirframeDocumentAdapterCompileValidV2")), "invalid-threshold:adapter")
    require(bool(get(obj, "AirframeSourceCompileValidV1")), "invalid-threshold:source")
    require(not bool(get(obj, "AirframeDocumentDiagnosticsValidV2")), "invalid-threshold:diagnostics")

    # Direct commit with a false adapter stage invalidates only adapter result;
    # it neither calls the source compiler nor alters an accepted snapshot.
    stage(base, step)
    obj.call_method("CompileAirframeDocumentSourceAdapterV2")
    accepted = downstream_snapshot()
    set_(obj, "AirframeDocumentAdapterStageValidV2", False)
    obj.call_method("CommitAirframeDocumentSourceAdapterV2")
    require(not bool(get(obj, "AirframeDocumentAdapterCompileValidV2")), "direct-commit:adapter")
    require(downstream_snapshot() == accepted, "direct-commit:downstream-mutated")

    emit("FORWARD_CASES", len(cases))
    emit("REVERSE_CASES", len(cases))
    emit("INVALID_DOCUMENT_CASES", len(invalid) + 1)
    emit("DIAGNOSTIC_POLICY_CASES", 3)
    emit("DIRECT_BOUNDARY_CASES", 1)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    restored = all(normalized(name, get(obj, name)) == normalized(name, value) for name, value in saved.items())
    emit("STATE_UNION_COUNT", len(saved))
    emit("STATE_RESTORED", restored)
    require(restored, "state restoration")
