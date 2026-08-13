"""Execute the complete flight-profile compile/evaluate contract against its oracle."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import unreal


PREFIX = "EDD_FLIGHT_PROFILE_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"

INPUTS = (
    "FlightProfileInputDefaultIdV1",
    "FlightProfileInputSegmentOverrideIdsV1",
    "FlightProfileInputSegmentCountV1",
)
RESOLVER = (
    "FlightProfileResolveInputIdV1",
    "FlightProfileResolveResultIdV1",
    "FlightProfileResolveResultPathFollowWeightV1",
    "FlightProfileResolveResultHorizonStabilizationWeightV1",
    "FlightProfileResolveResultLookAheadSecondsV1",
    "FlightProfileResolveResultBankGainV1",
    "FlightProfileResolveResultMaxBankDegreesV1",
    "FlightProfileResolveResultCameraUptiltDegreesV1",
    "FlightProfileResolveResultMaxAngularRateDegreesPerSecondV1",
    "FlightProfileResolveResultMaxAccelerationCmPerSecondSquaredV1",
    "FlightProfileResolveResultMaxJerkCmPerSecondCubedV1",
    "FlightProfileResolveResultMinimumTurnRadiusCmV1",
    "FlightProfileResolveResultValidV1",
)
CHANNELS = (
    ("PathFollowWeight", "path_follow_weight", "FlightProfileCandidatePathFollowWeightsV1", "FlightProfileCompiledPathFollowWeightsV1", "FlightProfileResultPathFollowWeightV1"),
    ("HorizonStabilizationWeight", "horizon_stabilization_weight", "FlightProfileCandidateHorizonStabilizationWeightsV1", "FlightProfileCompiledHorizonStabilizationWeightsV1", "FlightProfileResultHorizonStabilizationWeightV1"),
    ("LookAheadSeconds", "look_ahead_seconds", "FlightProfileCandidateLookAheadSecondsV1", "FlightProfileCompiledLookAheadSecondsV1", "FlightProfileResultLookAheadSecondsV1"),
    ("BankGain", "bank_gain", "FlightProfileCandidateBankGainsV1", "FlightProfileCompiledBankGainsV1", "FlightProfileResultBankGainV1"),
    ("MaxBankDegrees", "max_bank_degrees", "FlightProfileCandidateMaxBankDegreesV1", "FlightProfileCompiledMaxBankDegreesV1", "FlightProfileResultMaxBankDegreesV1"),
    ("CameraUptiltDegrees", "camera_uptilt_degrees", "FlightProfileCandidateCameraUptiltDegreesV1", "FlightProfileCompiledCameraUptiltDegreesV1", "FlightProfileResultCameraUptiltDegreesV1"),
    ("MaxAngularRateDegreesPerSecond", "max_angular_rate_degrees_per_second", "FlightProfileCandidateMaxAngularRatesDegreesPerSecondV1", "FlightProfileCompiledMaxAngularRatesDegreesPerSecondV1", "FlightProfileResultMaxAngularRateDegreesPerSecondV1"),
    ("MaxAccelerationCmPerSecondSquared", "max_acceleration_cm_per_second_squared", "FlightProfileCandidateMaxAccelerationsCmPerSecondSquaredV1", "FlightProfileCompiledMaxAccelerationsCmPerSecondSquaredV1", "FlightProfileResultMaxAccelerationCmPerSecondSquaredV1"),
    ("MaxJerkCmPerSecondCubed", "max_jerk_cm_per_second_cubed", "FlightProfileCandidateMaxJerksCmPerSecondCubedV1", "FlightProfileCompiledMaxJerksCmPerSecondCubedV1", "FlightProfileResultMaxJerkCmPerSecondCubedV1"),
    ("MinimumTurnRadiusCm", "minimum_turn_radius_cm", "FlightProfileCandidateMinimumTurnRadiiCmV1", "FlightProfileCompiledMinimumTurnRadiiCmV1", "FlightProfileResultMinimumTurnRadiusCmV1"),
)
CANDIDATES = ("FlightProfileCandidateIdsV1",) + tuple(item[2] for item in CHANNELS)
COMPILED = ("FlightProfileCompiledIdsV1",) + tuple(item[3] for item in CHANNELS)
RESULTS = ("FlightProfileResultIdV1",) + tuple(item[4] for item in CHANNELS) + ("FlightProfileResultValidV1",)
SCRATCH = (
    "FlightProfileStageValidV1",
    "FlightProfileCompileValidV1",
    "FlightProfileInputSegmentIndexV1",
    "FlightProfileEvaluationStageValidV1",
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


def normalized(value):
    if isinstance(value, (list, tuple)) or type(value).__name__ == "Array":
        return tuple(normalized(item) for item in value)
    if isinstance(value, float):
        return float(value)
    return value


def close(left, right, tolerance=2.0e-6):
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(left)), abs(float(right)))


def equivalent(left, right):
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(equivalent(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and isinstance(right, float) and math.isnan(left) and math.isnan(right):
        return True
    return left == right


root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools" / "trajectory"))
import flight_profile_reference as oracle


cls = unreal.load_class(None, CLASS)
require(cls is not None, "class")
obj = unreal.get_default_object(cls)
all_properties = INPUTS + RESOLVER + CANDIDATES + COMPILED + RESULTS + SCRATCH
saved = {}
for name in all_properties:
    value = get(obj, name)
    saved[name] = list(value) if name in CANDIDATES + COMPILED + ("FlightProfileInputSegmentOverrideIdsV1",) else value


def stage(default_id, overrides, count=None):
    set_(obj, "FlightProfileInputDefaultIdV1", default_id)
    set_(obj, "FlightProfileInputSegmentOverrideIdsV1", list(overrides))
    set_(obj, "FlightProfileInputSegmentCountV1", len(overrides) if count is None else int(count))


def authored_snapshot():
    return tuple(normalized(get(obj, name)) for name in INPUTS)


def candidate_snapshot():
    return tuple(normalized(get(obj, name)) for name in CANDIDATES)


def compiled_snapshot():
    return tuple(normalized(get(obj, name)) for name in COMPILED) + (bool(get(obj, "FlightProfileCompileValidV1")),)


def result_snapshot():
    return tuple(normalized(get(obj, name)) for name in RESULTS) + (bool(get(obj, "FlightProfileEvaluationStageValidV1")),)


def compile_profiles(default_id, overrides, count=None):
    stage(default_id, overrides, count)
    before = authored_snapshot()
    obj.call_method("CompileFlightProfilesV1")
    require(authored_snapshot() == before, "compile mutated authored inputs")


def evaluate(index):
    set_(obj, "FlightProfileInputSegmentIndexV1", int(index))
    before = compiled_snapshot()
    obj.call_method("EvaluateCompiledFlightProfileV1")
    require(equivalent(compiled_snapshot(), before), f"evaluation mutated compiled state:{index}")
    return result_snapshot()


def expected_channels(compiled):
    return (
        tuple(profile.profile_id for profile in compiled.profiles),
        *(tuple(float(getattr(profile, attribute)) for profile in compiled.profiles) for _label, attribute, _candidate, _compiled, _result in CHANNELS),
    )


def require_compiled(expected, label):
    require(bool(get(obj, "FlightProfileCompileValidV1")), label + ":compile-valid")
    actual = tuple(normalized(get(obj, name)) for name in COMPILED)
    wanted = expected_channels(expected)
    require(actual[0] == wanted[0], label + ":ids")
    for channel_index, (_name, _attribute, _candidate, compiled_name, _result) in enumerate(CHANNELS, start=1):
        require(len(actual[channel_index]) == len(wanted[channel_index]), label + ":cardinality:" + compiled_name)
        require(all(close(left, right) for left, right in zip(actual[channel_index], wanted[channel_index])), label + ":values:" + compiled_name)


def require_profile_result(expected, label):
    result = result_snapshot()
    diagnostics = (
        result,
        bool(get(obj, "FlightProfileCompileValidV1")),
        bool(get(obj, "FlightProfileResolveResultValidV1")),
        get(obj, "FlightProfileResolveResultIdV1"),
        get(obj, "FlightProfileInputSegmentIndexV1"),
    )
    require(result[-2] is True and result[-1] is True, label + ":valid:" + repr(diagnostics))
    require(result[0] == expected.profile_id, label + ":id")
    for index, (_name, attribute, _candidate, _compiled, result_name) in enumerate(CHANNELS, start=1):
        require(close(result[index], getattr(expected, attribute)), label + ":" + result_name)


def prefill_result():
    set_(obj, "FlightProfileResultIdV1", "dirty")
    for _label, _attribute, _candidate, _compiled, result_name in CHANNELS:
        set_(obj, result_name, 123.5)
    set_(obj, "FlightProfileResultValidV1", True)
    set_(obj, "FlightProfileEvaluationStageValidV1", True)


def require_result_cleared(label):
    result = result_snapshot()
    require(result[0] == "", label + ":id")
    require(all(float(value) == 0.0 for value in result[1:-2]), label + ":parameters")
    require(result[-2:] == (False, False), label + ":flags")


def require_compile_cleared(label):
    require(not bool(get(obj, "FlightProfileCompileValidV1")), label + ":compile-valid")
    require(not bool(get(obj, "FlightProfileStageValidV1")), label + ":stage-valid")
    require(all(len(get(obj, name)) == 0 for name in COMPILED), label + ":compiled-arrays")
    require_result_cleared(label)


def mutate_array(name, mutation):
    values = list(get(obj, name))
    mutation(values)
    set_(obj, name, values)


try:
    resolver_cases = 0
    for profile_id in oracle.PROFILE_ORDER:
        set_(obj, "FlightProfileResolveInputIdV1", profile_id)
        obj.call_method("ResolveFlightProfilePresetV1")
        profile = oracle.PROFILES[profile_id]
        require(bool(get(obj, "FlightProfileResolveResultValidV1")), "resolver-valid:" + profile_id)
        require(get(obj, "FlightProfileResolveResultIdV1") == profile_id, "resolver-id:" + profile_id)
        for _label, attribute, _candidate, _compiled, result_name in CHANNELS:
            resolver_name = result_name.replace("FlightProfileResult", "FlightProfileResolveResult")
            require(close(get(obj, resolver_name), getattr(profile, attribute)), "resolver-value:" + profile_id + ":" + resolver_name)
        resolver_cases += 1
    for bad in ("", "unknown", " cinematic_drone", "cinematic_drone "):
        set_(obj, "FlightProfileResolveInputIdV1", bad)
        obj.call_method("ResolveFlightProfilePresetV1")
        require(not bool(get(obj, "FlightProfileResolveResultValidV1")), "resolver accepted:" + repr(bad))
        require(get(obj, "FlightProfileResolveResultIdV1") == "", "resolver stale id:" + repr(bad))
        require(all(float(get(obj, name)) == 0.0 for name in RESOLVER[2:-1]), "resolver stale parameter:" + repr(bad))
        resolver_cases += 1

    fixtures = [(profile_id, ("",)) for profile_id in oracle.PROFILE_ORDER]
    fixtures.append(("hybrid", ("", "fpv_freestyle", "cinematic_drone", "", "fpv_long_range")))
    cycle = ("",) + oracle.PROFILE_ORDER
    fixtures.append(("cinematic_drone", tuple(cycle[index % len(cycle)] for index in range(511))))
    valid_compiles = 0
    evaluations = 0
    for fixture_index, (default_id, overrides) in enumerate(fixtures):
        expected = oracle.compile_flight_profiles(default_id, overrides, len(overrides))
        compile_profiles(default_id, overrides)
        require_compiled(expected, f"fixture:{fixture_index}")
        first = compiled_snapshot()
        compile_profiles(default_id, overrides)
        require(compiled_snapshot() == first, f"nondeterministic:{fixture_index}")
        require_compiled(expected, f"repeat:{fixture_index}")
        indices = range(len(overrides)) if len(overrides) <= 8 else (0, 1, 255, 510)
        for index in indices:
            evaluate(index)
            require_profile_result(expected.profiles[index], f"fixture:{fixture_index}:index:{index}")
            evaluations += 1
        valid_compiles += 1

    invalid_compile_cases = (
        ("zero-count", "cinematic_drone", (), 0),
        ("negative-count", "cinematic_drone", (), -1),
        ("above-maximum", "cinematic_drone", ("",) * 512, 512),
        ("count-shape-low", "cinematic_drone", ("", ""), 1),
        ("count-shape-high", "cinematic_drone", ("",), 2),
        ("unknown-default", "unknown", ("",), 1),
        ("empty-default", "", ("",), 1),
        ("trim-default-left", " cinematic_drone", ("",), 1),
        ("trim-default-right", "cinematic_drone ", ("",), 1),
        ("unknown-override", "cinematic_drone", ("unknown",), 1),
        ("trim-override-left", "cinematic_drone", (" hybrid",), 1),
        ("trim-override-right", "cinematic_drone", ("hybrid ",), 1),
    )
    compile_failures = 0
    for label, default_id, overrides, count in invalid_compile_cases:
        compile_profiles("hybrid", ("",))
        prefill_result()
        compile_profiles(default_id, overrides, count)
        require_compile_cleared(label)
        compile_failures += 1

    base_default = "cinematic_drone"
    base_overrides = ("", "hybrid", "fpv_freestyle")
    candidate_failures = 0
    reflection_sanitized = 0
    candidate_cases = []
    candidate_cases.append(("id-value", "FlightProfileCandidateIdsV1", lambda values: values.__setitem__(0, "hybrid")))
    candidate_cases.append(("id-unknown", "FlightProfileCandidateIdsV1", lambda values: values.__setitem__(0, "unknown")))
    for name in CANDIDATES:
        candidate_cases.append(("cardinality:" + name, name, lambda values: values.pop()))
    for _label, _attribute, candidate_name, _compiled, _result in CHANNELS:
        candidate_cases.append(("value:" + candidate_name, candidate_name, lambda values: values.__setitem__(0, values[0] + 0.125)))
    candidate_cases.append(("nonfinite", CHANNELS[0][2], lambda values: values.__setitem__(0, float("nan"))))
    for label, name, mutation in candidate_cases:
        compile_profiles(base_default, base_overrides)
        require(bool(get(obj, "FlightProfileCompileValidV1")), "candidate precondition:" + label)
        compiled_before = tuple(normalized(get(obj, item)) for item in COMPILED)
        original = list(get(obj, name))
        mutate_array(name, mutation)
        if label == "nonfinite" and math.isfinite(float(list(get(obj, name))[0])) and equivalent(list(get(obj, name)), original):
            emit("REFLECTION_SANITIZED", "candidate")
            reflection_sanitized += 1
            continue
        candidate_before = candidate_snapshot()
        set_(obj, "FlightProfileStageValidV1", True)
        obj.call_method("CommitCompiledFlightProfilesV1")
        candidate_diagnostics = (
            normalized(get(obj, name)),
            get(obj, "FlightProfileResolveResultPathFollowWeightV1"),
            normalized(get(obj, "FlightProfileCompiledPathFollowWeightsV1")),
        )
        require(not bool(get(obj, "FlightProfileCompileValidV1")), "candidate accepted:" + label + ":" + repr(candidate_diagnostics))
        require(not bool(get(obj, "FlightProfileStageValidV1")), "candidate stage remained valid:" + label)
        require(equivalent(tuple(normalized(get(obj, item)) for item in COMPILED), compiled_before), "candidate changed compiled source:" + label)
        require(equivalent(candidate_snapshot(), candidate_before), "commit mutated candidate:" + label)
        candidate_failures += 1

    compiled_failures = 0
    compiled_cases = []
    compiled_cases.append(("id-value", "FlightProfileCompiledIdsV1", lambda values: values.__setitem__(0, "hybrid")))
    compiled_cases.append(("id-unknown", "FlightProfileCompiledIdsV1", lambda values: values.__setitem__(0, "unknown")))
    for name in COMPILED:
        compiled_cases.append(("cardinality:" + name, name, lambda values: values.pop()))
    for _label, _attribute, _candidate, compiled_name, _result in CHANNELS:
        compiled_cases.append(("value:" + compiled_name, compiled_name, lambda values: values.__setitem__(0, values[0] + 0.125)))
    compiled_cases.append(("nonfinite", CHANNELS[0][3], lambda values: values.__setitem__(0, float("nan"))))
    for label, name, mutation in compiled_cases:
        compile_profiles(base_default, base_overrides)
        original = list(get(obj, name))
        mutate_array(name, mutation)
        if label == "nonfinite" and math.isfinite(float(list(get(obj, name))[0])) and equivalent(list(get(obj, name)), original):
            emit("REFLECTION_SANITIZED", "compiled")
            reflection_sanitized += 1
            continue
        corrupted = compiled_snapshot()
        prefill_result()
        evaluate(0)
        require_result_cleared("compiled:" + label)
        require(equivalent(compiled_snapshot(), corrupted), "evaluator repaired corruption:" + label)
        compiled_failures += 1

    bad_index_cases = 0
    compile_profiles(base_default, base_overrides)
    for index in (-2_147_483_648, -1, len(base_overrides), len(base_overrides) + 1, 2_147_483_647):
        prefill_result()
        evaluate(index)
        require_result_cleared("index:" + str(index))
        bad_index_cases += 1

    emit("RESOLVER_CASES", resolver_cases)
    emit("VALID_COMPILES", valid_compiles)
    emit("MAX_SEGMENTS", 511)
    emit("EVALUATIONS", evaluations)
    emit("COMPILE_FAILURE_CASES", compile_failures)
    emit("CANDIDATE_FAILURE_CASES", candidate_failures)
    emit("COMPILED_FAILURE_CASES", compiled_failures)
    emit("BAD_INDEX_CASES", bad_index_cases)
    emit("REFLECTION_SANITIZED_CASES", reflection_sanitized)
    emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items():
        set_(obj, name, value)
    emit("STATE_RESTORED", True)
