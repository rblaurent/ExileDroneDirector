"""Execute the live source-sampling bridge against the independent oracle.

The harness owns no editor state.  It snapshots the complete trajectory-schema
property union on the Client Director CDO, exercises the seven-function bridge
and its direct failure boundaries, and restores that union byte-for-value.
"""

from __future__ import annotations

import importlib
import json
import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_AIRFRAME_SOURCE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"

SOURCE_POSITIONS = "AirframeSourceCandidatePositionsV1"
SOURCE_BODY = "AirframeSourceCandidateBodyQuatsV1"
SOURCE_GIMBAL = "AirframeSourceCandidateGimbalQuatsV1"
SOURCE_TOTAL = "AirframeSourceTotalSecondsV1"
SOURCE_STEP = "AirframeSourceInputFixedStepSecondsV1"
SOURCE_STAGE = "AirframeSourceStageValidV1"
SOURCE_VALID = "AirframeSourceCompileValidV1"
SOURCE_COUNT = "AirframeSourceExpectedSampleCountV1"
DESIRED_VALID = "AirframeDesiredStreamCompileValidV1"
PREBAKE_VALID = "AirframePrebakeCompileValidV1"

PROFILE_FIELDS = (
    ("PathFollowWeights", "path_follow_weight"),
    ("HorizonStabilizationWeights", "horizon_stabilization_weight"),
    ("LookAheadSeconds", "look_ahead_seconds"),
    ("BankGains", "bank_gain"),
    ("MaxBankDegrees", "max_bank_degrees"),
    ("CameraUptiltDegrees", "camera_uptilt_degrees"),
    ("MaxAngularRatesDegreesPerSecond", "max_angular_rate_degrees_per_second"),
    ("MaxAccelerationsCmPerSecondSquared", "max_acceleration_cm_per_second_squared"),
    ("MaxJerksCmPerSecondCubed", "max_jerk_cm_per_second_cubed"),
    ("MinimumTurnRadiiCm", "minimum_turn_radius_cm"),
)
SOURCE_PROFILES = tuple(("AirframeSourceCandidate" + suffix + "V1", field) for suffix, field in PROFILE_FIELDS)
DESIRED_PROFILES = tuple(("AirframeDesiredStreamInput" + suffix + "V1", field) for suffix, field in PROFILE_FIELDS)

DESIRED_VECTORS = (
    ("AirframeDesiredStreamCandidateVelocitiesV1", "velocities"),
    ("AirframeDesiredStreamCandidateAccelerationsV1", "accelerations"),
    ("AirframeDesiredStreamCandidateJerksV1", "jerks"),
    ("AirframeDesiredStreamCandidateLookAheadVelocitiesV1", "look_ahead_velocities"),
)
DESIRED_QUATS = (
    ("AirframeDesiredStreamCandidateBodyQuatsV1", "desired_body_rotations"),
    ("AirframeDesiredStreamCandidateGimbalQuatsV1", "desired_gimbal_rotations"),
)

AUTHORED_INPUTS = (
    "PositionRouteInputWaypointPositionsV1",
    "PositionRouteInputDurationsV1",
    "PositionRouteInputSpatialCurveTypesV1",
    "PositionRouteInputTimeProfilesV1",
    "PositionRouteInputArcToleranceV1",
    "PositionRouteInputMaxArcDepthV1",
    "PositionRouteInputMaxArcOperationsV1",
    "FlightProfileInputDefaultIdV1",
    "FlightProfileInputSegmentOverrideIdsV1",
    "AirframeSourceInputBodyWaypointQuatsV1",
    "AirframeSourceInputGimbalWaypointQuatsV1",
    SOURCE_STEP,
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


def close(left, right, tolerance=2.5e-4):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def same_vector(left, right, tolerance=3.0e-4):
    return all(close(a, b, tolerance) for a, b in zip(left, right))


def same_rotation(left, right, tolerance=2.5e-4):
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if left_length <= 1.0e-12 or right_length <= 1.0e-12:
        return False
    dot = abs(sum(a * b for a, b in zip(left, right)) / (left_length * right_length))
    return dot >= 1.0 - tolerance


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import airframe_source_sampling_reference as source_oracle
import cinematic_reference as position_oracle
import flight_profile_reference as profile_oracle
import orientation_reference as orientation_oracle

source_oracle = importlib.reload(source_oracle)
position_oracle = importlib.reload(position_oracle)
profile_oracle = importlib.reload(profile_oracle)
orientation_oracle = importlib.reload(orientation_oracle)

cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)

# Every Blueprint variable touched by this bridge or its accepted dependencies
# is schema-owned.  Snapshot the full union so direct helper tests cannot leak
# scratch, result, or input state into the editor or a later warm invocation.
specs = {}
for schema_path in sorted((root / "tools" / "trajectory").glob("*_blueprint_schema.json")):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for spec in schema.get("variables", ()):
        specs.setdefault(spec["name"], spec)


def clone(name, value):
    spec = specs[name]
    container = spec.get("container")
    kind = spec["type"]
    if container == "Array":
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
    container = spec.get("container")
    kind = spec["type"]
    if container == "Array":
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


def make_case(durations, step, profile_offset, seed, all_profiles=False):
    rng = random.Random(seed)
    origin = (rng.uniform(-60.0, 60.0), rng.uniform(-30.0, 30.0), rng.uniform(-8.0, 8.0))
    direction = (rng.uniform(0.8, 1.0), rng.uniform(-0.12, 0.12), rng.uniform(-0.04, 0.04))
    speed = rng.uniform(25.0, 70.0)
    elapsed = 0.0
    points = [origin]
    for duration in durations:
        elapsed += duration
        points.append(tuple(origin[axis] + direction[axis] * speed * elapsed for axis in range(3)))
    bodies = tuple(yaw(-6.0 + 15.0 * index / max(1, len(points) - 1)) for index in range(len(points)))
    gimbals = tuple(pitch(4.0 - 11.0 * index / max(1, len(points) - 1)) for index in range(len(points)))
    order = tuple(profile_oracle.PROFILE_ORDER)
    if all_profiles:
        overrides = order
    else:
        overrides = tuple(order[(profile_offset + index) % len(order)] for index in range(len(durations)))
    return {
        "points": tuple(points),
        "durations": tuple(float(value) for value in durations),
        "curves": ("linear",) * len(durations),
        "time_profiles": ("linear",) * len(durations),
        "default": "cinematic_drone",
        "overrides": overrides,
        "body": bodies,
        "gimbal": gimbals,
        "step": float(step),
    }


def expected(case):
    authored = tuple(
        position_oracle.AuthoredSegment(duration, curve, profile)
        for duration, curve, profile in zip(case["durations"], case["curves"], case["time_profiles"])
    )
    position = position_oracle.compile_trajectory(case["points"], authored, arc_tolerance=0.01, max_arc_depth=12)
    body = orientation_oracle.compile_orientation_track(case["body"], case["durations"])
    gimbal = orientation_oracle.compile_orientation_track(case["gimbal"], case["durations"])
    profiles = profile_oracle.compile_flight_profiles(case["default"], case["overrides"], len(case["durations"]))
    return source_oracle.sample_and_compile_airframe_sources(position, body, gimbal, profiles, case["step"])


def stage(case):
    set_(obj, "PositionRouteInputWaypointPositionsV1", [vector(value) for value in case["points"]])
    set_(obj, "PositionRouteInputDurationsV1", list(case["durations"]))
    set_(obj, "PositionRouteInputSpatialCurveTypesV1", list(case["curves"]))
    set_(obj, "PositionRouteInputTimeProfilesV1", list(case["time_profiles"]))
    set_(obj, "PositionRouteInputArcToleranceV1", 0.01)
    set_(obj, "PositionRouteInputMaxArcDepthV1", 12)
    set_(obj, "PositionRouteInputMaxArcOperationsV1", 8191)
    set_(obj, "FlightProfileInputDefaultIdV1", case["default"])
    set_(obj, "FlightProfileInputSegmentOverrideIdsV1", list(case["overrides"]))
    set_(obj, "AirframeSourceInputBodyWaypointQuatsV1", [quat(value) for value in case["body"]])
    set_(obj, "AirframeSourceInputGimbalWaypointQuatsV1", [quat(value) for value in case["gimbal"]])
    set_(obj, SOURCE_STEP, case["step"])


def authored_snapshot():
    return tuple(normalized(name, get(obj, name)) for name in AUTHORED_INPUTS)


def require_vector_array(name, wanted, label):
    actual = tuple(vt(value) for value in get(obj, name))
    require(len(actual) == len(wanted), f"{label}:{name}:count")
    for index, (left, right) in enumerate(zip(actual, wanted)):
        require(same_vector(left, right), f"{label}:{name}:{index}:{left!r}:{right!r}")


def require_quat_array(name, wanted, label):
    actual = tuple(qt(value) for value in get(obj, name))
    require(len(actual) == len(wanted), f"{label}:{name}:count")
    for index, (left, right) in enumerate(zip(actual, wanted)):
        require(same_rotation(left, right), f"{label}:{name}:{index}:{left!r}:{right!r}")


def require_float_array(name, wanted, label):
    actual = tuple(float(value) for value in get(obj, name))
    require(len(actual) == len(wanted), f"{label}:{name}:count")
    require(all(close(left, right) for left, right in zip(actual, wanted)), f"{label}:{name}:values")


def require_success(wanted, label, expected_step):
    require(bool(get(obj, SOURCE_STAGE)), label + ":stage")
    require(bool(get(obj, SOURCE_VALID)), label + ":source-valid")
    require(bool(get(obj, DESIRED_VALID)), label + ":desired-valid")
    require(bool(get(obj, PREBAKE_VALID)), label + ":prebake-valid")
    require(int(get(obj, SOURCE_COUNT)) == len(wanted.sample_times), label + ":sample-count")
    require(close(get(obj, SOURCE_TOTAL), wanted.sample_times[-1]), label + ":total")
    require(close(get(obj, SOURCE_STEP), expected_step), label + ":step")
    require_vector_array(SOURCE_POSITIONS, wanted.positions, label)
    require_quat_array(SOURCE_BODY, wanted.authored_body_rotations, label)
    require_quat_array(SOURCE_GIMBAL, wanted.authored_gimbal_rotations, label)
    require(any(not same_rotation(body, gimbal, 1.0e-6) for body, gimbal in zip(wanted.authored_body_rotations, wanted.authored_gimbal_rotations)), label + ":distinct-authorship")
    for name, field in SOURCE_PROFILES:
        require_float_array(name, tuple(getattr(profile, field) for profile in wanted.profiles), label)

    # Commit must copy the complete thirteen-channel source transaction into
    # the accepted desired compiler without aliasing the two authored tracks.
    require_vector_array("AirframeDesiredStreamInputPositionsV1", wanted.positions, label)
    require_quat_array("AirframeDesiredStreamInputAuthoredBodyQuatsV1", wanted.authored_body_rotations, label)
    require_quat_array("AirframeDesiredStreamInputAuthoredGimbalQuatsV1", wanted.authored_gimbal_rotations, label)
    for name, field in DESIRED_PROFILES:
        require_float_array(name, tuple(getattr(profile, field) for profile in wanted.profiles), label)
    for name, field in DESIRED_VECTORS:
        require_vector_array(name, getattr(wanted.desired_stream, field), label)
    for name, field in DESIRED_QUATS:
        require_quat_array(name, getattr(wanted.desired_stream, field), label)
    require_float_array(
        "AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1",
        wanted.desired_stream.maximum_angular_rates_degrees_per_second,
        label,
    )


def poison():
    set_(obj, SOURCE_POSITIONS, [vector((999.0, 998.0, 997.0))])
    set_(obj, SOURCE_BODY, [quat((0.0, 0.0, 1.0, 0.0))])
    set_(obj, SOURCE_GIMBAL, [quat((0.0, 1.0, 0.0, 0.0))])
    for name, _field in SOURCE_PROFILES:
        set_(obj, name, [999.0])
    set_(obj, SOURCE_VALID, True)
    set_(obj, DESIRED_VALID, True)
    set_(obj, PREBAKE_VALID, True)


def require_failed(label):
    require(not bool(get(obj, SOURCE_VALID)), label + ":source-valid")
    require(not bool(get(obj, DESIRED_VALID)), label + ":desired-valid")
    require(not bool(get(obj, PREBAKE_VALID)), label + ":prebake-valid")
    bound = max(0, int(get(obj, SOURCE_COUNT)))
    for name in (SOURCE_POSITIONS, SOURCE_BODY, SOURCE_GIMBAL) + tuple(item[0] for item in SOURCE_PROFILES):
        require(len(get(obj, name)) <= bound, label + ":unbounded:" + name)
    require(len(get(obj, "AirframePrebakeCompiledBodyQuatsV1")) == 0, label + ":body-publication")
    require(len(get(obj, "AirframePrebakeCompiledGimbalQuatsV1")) == 0, label + ":gimbal-publication")


def downstream_snapshot():
    names = (
        "AirframeDesiredStreamInputPositionsV1",
        "AirframeDesiredStreamInputAuthoredBodyQuatsV1",
        "AirframeDesiredStreamInputAuthoredGimbalQuatsV1",
        "AirframePrebakeCompiledBodyQuatsV1",
        "AirframePrebakeCompiledGimbalQuatsV1",
        "AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1",
        "AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1",
        DESIRED_VALID,
        PREBAKE_VALID,
    )
    return tuple(normalized(name, get(obj, name)) for name in names)


try:
    order = tuple(profile_oracle.PROFILE_ORDER)
    cases = [
        make_case((1.0,), 0.25, 0, 0xEDD101),
        make_case((0.4, 0.6), 0.3, 1, 0xEDD102),
        make_case((0.5,) * 5, 0.25, 0, 0xEDD103, all_profiles=True),
    ]
    for index in range(7):
        rng = random.Random(0xEDD200 + index)
        count = rng.randint(2, 5)
        durations = tuple(rng.choice((0.2, 0.3, 0.5)) for _ in range(count - 1))
        cases.append(make_case(durations, rng.choice((0.1, 0.2, 0.3)), index, 0xEDD300 + index))

    wanted = [expected(case) for case in cases]
    for index, (case, result) in enumerate(zip(cases, wanted)):
        stage(case)
        before = authored_snapshot()
        obj.call_method("CompileAirframeSourceSamplingV1")
        require(authored_snapshot() == before, f"forward:{index}:inputs-mutated")
        require_success(result, f"forward:{index}", case["step"])

    for reverse_index, index in enumerate(reversed(range(len(cases)))):
        stage(cases[index])
        before = authored_snapshot()
        obj.call_method("CompileAirframeSourceSamplingV1")
        require(authored_snapshot() == before, f"reverse:{reverse_index}:inputs-mutated")
        require_success(wanted[index], f"reverse:{reverse_index}", cases[index]["step"])

    base = cases[1]
    invalid = []
    broken = dict(base); broken["body"] = broken["body"][:-1]; invalid.append(("body-shape", broken))
    broken = dict(base); values = list(broken["gimbal"]); values[1] = (0.0, 0.0, 0.0, 0.0); broken["gimbal"] = tuple(values); invalid.append(("gimbal-authorship", broken))
    broken = dict(base); broken["step"] = 0.001; invalid.append(("fixed-step", broken))
    broken = dict(base); broken["durations"] = (0.0,) + broken["durations"][1:]; invalid.append(("component-duration", broken))
    broken = dict(base); broken["overrides"] = ("not-a-profile",) + broken["overrides"][1:]; invalid.append(("component-profile", broken))
    violent = make_case((0.05, 0.05), 0.05, 0, 0xEDD999)
    violent["points"] = ((0.0, 0.0, 0.0), (100000.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    invalid.append(("physical-downstream", violent))
    for label, case in invalid:
        stage(base)
        obj.call_method("CompileAirframeSourceSamplingV1")
        poison()
        stage(case)
        before = authored_snapshot()
        obj.call_method("CompileAirframeSourceSamplingV1")
        require(authored_snapshot() == before, label + ":inputs-mutated")
        require_failed(label)

    # Direct evaluator corruption: compile valid components, invalidate the
    # accepted position payload, and prove the body/profile sampler cannot
    # publish a stale or unbounded private prefix.
    stage(base)
    obj.call_method("ResetAirframeSourceSamplingV1")
    obj.call_method("ValidateAirframeSourceSamplingInputsV1")
    obj.call_method("CompileAirframeSourcePositionProfilesV1")
    require(bool(get(obj, SOURCE_STAGE)), "evaluator:precondition")
    set_(obj, "PositionRouteCompiledWaypointPositionsV1", [])
    obj.call_method("BuildAirframeSourcePositionBodyProfileSamplesV1")
    require(not bool(get(obj, SOURCE_VALID)), "evaluator:source-valid")
    require(len(get(obj, SOURCE_POSITIONS)) < int(get(obj, SOURCE_COUNT)), "evaluator:unexpected-publication")

    # Direct commit preflight must invalidate only the source result and leave
    # the already accepted desired/prebake snapshot untouched.
    stage(base)
    obj.call_method("CompileAirframeSourceSamplingV1")
    accepted = downstream_snapshot()
    set_(obj, SOURCE_GIMBAL, list(get(obj, SOURCE_GIMBAL))[:-1])
    obj.call_method("CommitAirframeSourceSamplesToDesiredV1")
    require(not bool(get(obj, SOURCE_VALID)), "commit-preflight:source-valid")
    require(downstream_snapshot() == accepted, "commit-preflight:downstream-mutated")

    emit("FORWARD_CASES", len(cases))
    emit("REVERSE_CASES", len(cases))
    emit("PROFILE_IDS", ",".join(order))
    emit("INVALID_CASES", len(invalid))
    emit("DIRECT_BOUNDARY_CASES", 2)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    restored = all(normalized(name, get(obj, name)) == normalized(name, value) for name, value in saved.items())
    emit("STATE_UNION_COUNT", len(saved))
    emit("STATE_RESTORED", restored)
    require(restored, "state restoration")
