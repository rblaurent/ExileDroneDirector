"""Execute the live C2 smoothed flight-profile assembly against its oracle.

The harness is deliberately transactional: it snapshots every touched Client
Director CDO property, exercises valid and fail-closed paths, and restores the
exact prior state even when an assertion fails.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_SMOOTHED_FLIGHT_PROFILE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"

PARAMETERS = (
    ("PathFollowWeight", "path_follow_weight", "FlightProfileCompiledPathFollowWeightsV1"),
    ("HorizonStabilizationWeight", "horizon_stabilization_weight", "FlightProfileCompiledHorizonStabilizationWeightsV1"),
    ("LookAheadSeconds", "look_ahead_seconds", "FlightProfileCompiledLookAheadSecondsV1"),
    ("BankGain", "bank_gain", "FlightProfileCompiledBankGainsV1"),
    ("MaxBankDegrees", "max_bank_degrees", "FlightProfileCompiledMaxBankDegreesV1"),
    ("CameraUptiltDegrees", "camera_uptilt_degrees", "FlightProfileCompiledCameraUptiltDegreesV1"),
    ("MaxAngularRateDegreesPerSecond", "max_angular_rate_degrees_per_second", "FlightProfileCompiledMaxAngularRatesDegreesPerSecondV1"),
    ("MaxAccelerationCmPerSecondSquared", "max_acceleration_cm_per_second_squared", "FlightProfileCompiledMaxAccelerationsCmPerSecondSquaredV1"),
    ("MaxJerkCmPerSecondCubed", "max_jerk_cm_per_second_cubed", "FlightProfileCompiledMaxJerksCmPerSecondCubedV1"),
    ("MinimumTurnRadiusCm", "minimum_turn_radius_cm", "FlightProfileCompiledMinimumTurnRadiiCmV1"),
)

CANDIDATE_PROPERTIES = (
    "FlightProfileCandidatePathFollowWeightsV1",
    "FlightProfileCandidateHorizonStabilizationWeightsV1",
    "FlightProfileCandidateLookAheadSecondsV1",
    "FlightProfileCandidateBankGainsV1",
    "FlightProfileCandidateMaxBankDegreesV1",
    "FlightProfileCandidateCameraUptiltDegreesV1",
    "FlightProfileCandidateMaxAngularRatesDegreesPerSecondV1",
    "FlightProfileCandidateMaxAccelerationsCmPerSecondSquaredV1",
    "FlightProfileCandidateMaxJerksCmPerSecondCubedV1",
    "FlightProfileCandidateMinimumTurnRadiiCmV1",
)

FLIGHT_INPUTS = (
    "FlightProfileInputDefaultIdV1",
    "FlightProfileInputSegmentOverrideIdsV1",
    "FlightProfileInputSegmentCountV1",
)
FLIGHT_RESOLVER = (
    "FlightProfileResolveInputIdV1",
    "FlightProfileResolveResultIdV1",
    *("FlightProfileResolveResult" + suffix + "V1" for suffix, _attribute, _compiled in PARAMETERS),
    "FlightProfileResolveResultValidV1",
)
FLIGHT_COMPILED = (
    "FlightProfileCompiledIdsV1",
    *(compiled for _suffix, _attribute, compiled in PARAMETERS),
)
FLIGHT_CANDIDATES = ("FlightProfileCandidateIdsV1",) + CANDIDATE_PROPERTIES
FLIGHT_HELPER = (
    "FlightProfileStageValidV1",
    "FlightProfileCompileValidV1",
    "FlightProfileInputSegmentIndexV1",
    "FlightProfileEvaluationStageValidV1",
    "FlightProfileResultIdV1",
    *("FlightProfileResult" + suffix + "V1" for suffix, _attribute, _compiled in PARAMETERS),
    "FlightProfileResultValidV1",
)

SMOOTH_INPUTS = (
    "SmoothedFlightProfileInputSegmentIndexV1",
    "SmoothedFlightProfileInputLocalTimeAlphaV1",
)
SMOOTH_CURRENT = (
    "SmoothedFlightProfileCurrentIdV1",
    *("SmoothedFlightProfileCurrent" + suffix + "V1" for suffix, _attribute, _compiled in PARAMETERS),
)
SMOOTH_NEIGHBOR = (
    "SmoothedFlightProfileNeighborIdV1",
    *("SmoothedFlightProfileNeighbor" + suffix + "V1" for suffix, _attribute, _compiled in PARAMETERS),
    "SmoothedFlightProfileNeighborWeightV1",
)
SMOOTH_RESULT = (
    "SmoothedFlightProfileResultCurrentIdV1",
    "SmoothedFlightProfileResultNeighborIdV1",
    "SmoothedFlightProfileResultNeighborWeightV1",
    *("SmoothedFlightProfileResult" + suffix + "V1" for suffix, _attribute, _compiled in PARAMETERS),
    "SmoothedFlightProfileResultValidV1",
)
SMOOTH_SCRATCH = ("SmoothedFlightProfileStageValidV1",) + SMOOTH_CURRENT + SMOOTH_NEIGHBOR
ALL_PROPERTIES = tuple(dict.fromkeys(
    FLIGHT_INPUTS + FLIGHT_RESOLVER + FLIGHT_CANDIDATES + FLIGHT_COMPILED + FLIGHT_HELPER
    + SMOOTH_INPUTS + SMOOTH_SCRATCH + SMOOTH_RESULT
))
ARRAY_PROPERTIES = {
    "FlightProfileInputSegmentOverrideIdsV1",
    *FLIGHT_CANDIDATES,
    *FLIGHT_COMPILED,
}


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
    raise RuntimeError(f"missing property:{name}")


def set_(obj, name, value):
    for candidate in variants(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(f"could not set property:{name}")


def normalized(value):
    if isinstance(value, (list, tuple)) or type(value).__name__ == "Array":
        return tuple(normalized(item) for item in value)
    if isinstance(value, float):
        return float(value)
    return value


def equivalent(left, right):
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(equivalent(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and isinstance(right, float) and math.isnan(left) and math.isnan(right):
        return True
    return left == right


def close(left, right, tolerance=3.0e-6):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import flight_profile_reference as flight_oracle
import smoothed_flight_profile_reference as smooth_oracle


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
saved = {
    name: list(get(obj, name)) if name in ARRAY_PROPERTIES else get(obj, name)
    for name in ALL_PROPERTIES
}


def compiled_snapshot():
    return tuple(normalized(get(obj, name)) for name in FLIGHT_COMPILED) + (
        bool(get(obj, "FlightProfileCompileValidV1")),
    )


def smooth_stage_snapshot():
    return tuple(normalized(get(obj, name)) for name in SMOOTH_SCRATCH)


def smooth_result_snapshot():
    return tuple(normalized(get(obj, name)) for name in SMOOTH_RESULT)


def compile_profiles(default_id, overrides):
    set_(obj, "FlightProfileInputDefaultIdV1", default_id)
    set_(obj, "FlightProfileInputSegmentOverrideIdsV1", list(overrides))
    set_(obj, "FlightProfileInputSegmentCountV1", len(overrides))
    obj.call_method("CompileFlightProfilesV1")
    require(bool(get(obj, "FlightProfileCompileValidV1")), "compile precondition")
    return flight_oracle.compile_flight_profiles(default_id, tuple(overrides), len(overrides))


def poison_public():
    set_(obj, "SmoothedFlightProfileResultCurrentIdV1", "dirty-current")
    set_(obj, "SmoothedFlightProfileResultNeighborIdV1", "dirty-neighbor")
    set_(obj, "SmoothedFlightProfileResultNeighborWeightV1", 0.25)
    for suffix, _attribute, _compiled in PARAMETERS:
        set_(obj, "SmoothedFlightProfileResult" + suffix + "V1", 123.5)
    set_(obj, "SmoothedFlightProfileResultValidV1", True)


def require_public_cleared(label):
    actual = smooth_result_snapshot()
    require(actual[0:2] == ("", ""), label + ":ids:" + repr(actual[0:2]))
    require(all(float(value) == 0.0 for value in actual[2:-1]), label + ":values:" + repr(actual[2:-1]))
    require(actual[-1] is False, label + ":valid")


def require_result(expected, label):
    actual = smooth_result_snapshot()
    require(actual[-1] is True, label + ":valid:" + repr(actual))
    require(actual[0] == expected.current_profile_id, label + ":current-id")
    require(actual[1] == expected.neighbor_profile_id, label + ":neighbor-id")
    require(close(actual[2], expected.neighbor_weight), label + ":neighbor-weight")
    for index, (_suffix, attribute, _compiled) in enumerate(PARAMETERS, start=3):
        require(close(actual[index], getattr(expected.parameters, attribute)), label + ":" + attribute)


def evaluate(compiled, index, alpha, label):
    set_(obj, "SmoothedFlightProfileInputSegmentIndexV1", int(index))
    set_(obj, "SmoothedFlightProfileInputLocalTimeAlphaV1", float(alpha))
    before = compiled_snapshot()
    obj.call_method("EvaluateSmoothedFlightProfileV1")
    require(equivalent(compiled_snapshot(), before), label + ":compiled-mutated")
    require(int(get(obj, "FlightProfileInputSegmentIndexV1")) == int(index), label + ":helper-not-restored")
    if not bool(get(obj, "SmoothedFlightProfileResultValidV1")):
        emit("UNEXPECTED_INVALID", label + "|STAGE|" + repr(smooth_stage_snapshot()))
    expected = smooth_oracle.evaluate_smoothed_flight_profile(compiled, int(index), float(alpha))
    require_result(expected, label)
    return smooth_result_snapshot()


def set_stage_from_profiles(current, neighbor, weight):
    set_(obj, "SmoothedFlightProfileStageValidV1", True)
    set_(obj, "SmoothedFlightProfileCurrentIdV1", current.profile_id)
    set_(obj, "SmoothedFlightProfileNeighborIdV1", neighbor.profile_id)
    for suffix, attribute, _compiled in PARAMETERS:
        set_(obj, "SmoothedFlightProfileCurrent" + suffix + "V1", float(getattr(current, attribute)))
        set_(obj, "SmoothedFlightProfileNeighbor" + suffix + "V1", float(getattr(neighbor, attribute)))
    set_(obj, "SmoothedFlightProfileNeighborWeightV1", float(weight))


def mutate_array(name, mutation):
    values = list(get(obj, name))
    mutation(values)
    set_(obj, name, values)


try:
    # Reset is a real behavioral boundary, not merely a graph-shape assertion.
    set_(obj, "SmoothedFlightProfileInputSegmentIndexV1", 17)
    set_(obj, "SmoothedFlightProfileInputLocalTimeAlphaV1", 0.375)
    for name in SMOOTH_SCRATCH + SMOOTH_RESULT:
        value = get(obj, name)
        if isinstance(value, bool):
            set_(obj, name, True)
        elif isinstance(value, str):
            set_(obj, name, "dirty")
        else:
            set_(obj, name, 123.5)
    obj.call_method("ResetSmoothedFlightProfileV1")
    require(int(get(obj, SMOOTH_INPUTS[0])) == 17, "reset mutated index input")
    require(close(get(obj, SMOOTH_INPUTS[1]), 0.375), "reset mutated alpha input")
    require_public_cleared("reset")
    require(not bool(get(obj, "SmoothedFlightProfileStageValidV1")), "reset stage-valid")
    require(all(get(obj, name) == "" for name in SMOOTH_CURRENT[:1] + SMOOTH_NEIGHBOR[:1]), "reset scratch ids")
    require(all(float(get(obj, name)) == 0.0 for name in SMOOTH_CURRENT[1:] + SMOOTH_NEIGHBOR[1:]), "reset scratch values")

    valid_cases = 0
    boundary_cases = 0
    deterministic_cases = 0

    # Every canonical preset is exact for a single-segment path at every phase.
    for profile_id in flight_oracle.PROFILE_ORDER:
        compiled = compile_profiles(profile_id, ("",))
        for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
            evaluate(compiled, 0, alpha, "single:" + profile_id + ":" + repr(alpha))
            valid_cases += 1

    sequence = tuple(flight_oracle.PROFILE_ORDER)
    compiled = compile_profiles(sequence[0], sequence)
    samples = (0.0, 1.0e-6, 0.25, 0.499999, 0.5, 0.500001, 0.75, 0.999999, 1.0)
    observed = {}
    for index in range(len(sequence)):
        for alpha in samples:
            observed[(index, alpha)] = evaluate(compiled, index, alpha, f"sequence:{index}:{alpha}")
            valid_cases += 1

    # Adjacent boundaries publish the same numeric state. Identity remains
    # segment-relative by design: current/neighbor swap across the waypoint.
    for index in range(len(sequence) - 1):
        left = observed[(index, 1.0)]
        right = observed[(index + 1, 0.0)]
        require(left[0:2] == (sequence[index], sequence[index + 1]), f"left boundary identity:{index}")
        require(right[0:2] == (sequence[index + 1], sequence[index]), f"right boundary identity:{index}")
        require(left[2] == right[2] == 0.5, f"boundary weight:{index}")
        require(left[3:] == right[3:], f"boundary values:{index}")
        boundary_cases += 1

    # Direct scrubbing must be independent of query history and order.
    rng = random.Random(0xEDD_C2)
    queries = tuple((rng.randrange(len(sequence)), rng.random()) for _ in range(160))
    forward = {query: evaluate(compiled, *query, "scrub-forward:" + repr(query)) for query in queries}
    for query in reversed(queries):
        require(evaluate(compiled, *query, "scrub-reverse:" + repr(query)) == forward[query], "history dependence:" + repr(query))
        deterministic_cases += 1

    # Prove the accepted 511-segment ceiling with widely separated samples.
    cycle = ("",) + sequence
    maximum_overrides = tuple(cycle[index % len(cycle)] for index in range(511))
    maximum = compile_profiles("cinematic_drone", maximum_overrides)
    require(maximum.segment_count == 511, "maximum compile count")
    for index, alpha in ((0, 0.0), (1, 1.0), (255, 0.125), (255, 0.875), (510, 1.0)):
        evaluate(maximum, index, alpha, f"maximum:{index}:{alpha}")
        valid_cases += 1

    # Invalid indices and finite alphas must clear every poisoned public field.
    compiled = compile_profiles(sequence[0], sequence)
    invalid_input_cases = 0
    for index, alpha in (
        (-2_147_483_648, 0.5), (-1, 0.5), (len(sequence), 0.5),
        (len(sequence) + 1, 0.5), (2_147_483_647, 0.5),
        (0, -1.0), (0, -1.0e-9), (0, 1.000000001), (0, 2.0),
    ):
        set_(obj, SMOOTH_INPUTS[0], index)
        set_(obj, SMOOTH_INPUTS[1], alpha)
        poison_public()
        before = compiled_snapshot()
        obj.call_method("EvaluateSmoothedFlightProfileV1")
        require_public_cleared(f"invalid-input:{index}:{alpha}")
        require(equivalent(compiled_snapshot(), before), f"invalid input mutated compiled:{index}:{alpha}")
        require(int(get(obj, "FlightProfileInputSegmentIndexV1")) == int(index), f"invalid helper index:{index}")
        invalid_input_cases += 1

    reflection_sanitized = 0
    for label, value in (("nan", float("nan")), ("positive-inf", float("inf")), ("negative-inf", float("-inf"))):
        set_(obj, SMOOTH_INPUTS[0], 0)
        previous = float(get(obj, SMOOTH_INPUTS[1]))
        set_(obj, SMOOTH_INPUTS[1], value)
        reflected = float(get(obj, SMOOTH_INPUTS[1]))
        if math.isfinite(reflected) and reflected == previous:
            emit("REFLECTION_SANITIZED", label)
            reflection_sanitized += 1
            continue
        poison_public()
        before = compiled_snapshot()
        obj.call_method("EvaluateSmoothedFlightProfileV1")
        require_public_cleared("nonfinite:" + label)
        require(equivalent(compiled_snapshot(), before), "nonfinite mutated compiled:" + label)
        invalid_input_cases += 1

    # Corrupt immutable compiled publications. Evaluation must fail closed and
    # must not repair or otherwise mutate the corrupt source.
    compiled_failure_cases = 0
    corruptions = (
        ("compile-valid", "FlightProfileCompileValidV1", lambda: set_(obj, "FlightProfileCompileValidV1", False)),
        ("id-cardinality", "FlightProfileCompiledIdsV1", lambda: mutate_array("FlightProfileCompiledIdsV1", lambda values: values.pop())),
        ("unknown-id", "FlightProfileCompiledIdsV1", lambda: mutate_array("FlightProfileCompiledIdsV1", lambda values: values.__setitem__(0, "unknown"))),
        ("value-cardinality", PARAMETERS[0][2], lambda: mutate_array(PARAMETERS[0][2], lambda values: values.pop())),
        ("canonical-value", PARAMETERS[0][2], lambda: mutate_array(PARAMETERS[0][2], lambda values: values.__setitem__(0, values[0] + 0.125))),
    )
    for label, _name, mutation in corruptions:
        compile_profiles(sequence[0], sequence)
        mutation()
        corrupted = compiled_snapshot()
        set_(obj, SMOOTH_INPUTS[0], 0)
        set_(obj, SMOOTH_INPUTS[1], 0.5)
        poison_public()
        obj.call_method("EvaluateSmoothedFlightProfileV1")
        require_public_cleared("compiled:" + label)
        require(equivalent(compiled_snapshot(), corrupted), "compiled source repaired:" + label)
        compiled_failure_cases += 1

    # Publication re-resolves both staged records. Every corrupt stage and
    # weight fails before a public write and publication never mutates staging.
    publish_failure_cases = 0
    current = flight_oracle.PROFILES["hybrid"]
    neighbor = flight_oracle.PROFILES["fpv_freestyle"]
    stage_corruptions = (
        ("stage-invalid", lambda: set_(obj, "SmoothedFlightProfileStageValidV1", False)),
        ("current-id", lambda: set_(obj, "SmoothedFlightProfileCurrentIdV1", "unknown")),
        ("neighbor-id", lambda: set_(obj, "SmoothedFlightProfileNeighborIdV1", "unknown")),
        ("current-value", lambda: set_(obj, "SmoothedFlightProfileCurrentPathFollowWeightV1", current.path_follow_weight + 0.125)),
        ("neighbor-value", lambda: set_(obj, "SmoothedFlightProfileNeighborPathFollowWeightV1", neighbor.path_follow_weight + 0.125)),
        ("negative-weight", lambda: set_(obj, "SmoothedFlightProfileNeighborWeightV1", -0.001)),
        ("large-weight", lambda: set_(obj, "SmoothedFlightProfileNeighborWeightV1", 0.500001)),
    )
    for label, mutation in stage_corruptions:
        set_stage_from_profiles(current, neighbor, 0.25)
        mutation()
        stage_before = smooth_stage_snapshot()
        poison_public()
        obj.call_method("PublishSmoothedFlightProfileV1")
        require_public_cleared("publish:" + label)
        require(equivalent(smooth_stage_snapshot(), stage_before), "publish mutated stage:" + label)
        publish_failure_cases += 1

    emit("VALID_EVALUATIONS", valid_cases)
    emit("BOUNDARY_CASES", boundary_cases)
    emit("DETERMINISTIC_SCRUB_CASES", deterministic_cases)
    emit("MAX_SEGMENTS", 511)
    emit("INVALID_INPUT_CASES", invalid_input_cases)
    emit("COMPILED_FAILURE_CASES", compiled_failure_cases)
    emit("PUBLISH_FAILURE_CASES", publish_failure_cases)
    emit("REFLECTION_SANITIZED_CASES", reflection_sanitized)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
