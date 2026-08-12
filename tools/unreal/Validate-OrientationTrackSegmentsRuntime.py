"""Execute compiled orientation segment assembly against the frozen oracle."""
from __future__ import annotations
import math, random, sys
from pathlib import Path
import unreal

PREFIX = "EDD_ORIENTATION_TRACK_SEGMENTS_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ALIGNED = "OrientationTrackCandidateAlignedQuatsV1"; TANGENTS = "OrientationTrackCandidateTangentRatesV1"; DURATIONS = "OrientationTrackInputDurationsV1"
STARTS = "OrientationTrackCandidateSegmentStartsV1"; START_CONTROLS = "OrientationTrackCandidateStartControlsV1"; END_CONTROLS = "OrientationTrackCandidateEndControlsV1"; TOTAL = "OrientationTrackCandidateTotalSecondsV1"; VALID = "OrientationTrackStageValidV1"
PRIMITIVE = ("OrientationInputStartQuatV1", "OrientationInputEndQuatV1", "OrientationInputStartTangentRateVectorV1", "OrientationInputEndTangentRateVectorV1", "OrientationInputDurationV1", "OrientationResultStartControlQuatV1", "OrientationResultEndControlQuatV1", "OrientationResultValidV1")

def emit(name, value): unreal.log(f"{PREFIX}|{name}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_"); return name, unreal.Name(name), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in variants(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(name)
def set_(obj, name, value):
    for candidate in variants(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(name)
def quat(value): return unreal.Quat(*(float(x) for x in value))
def vector(value): return unreal.Vector(*(float(x) for x in value))
def tuple4(value): return float(value.x), float(value.y), float(value.z), float(value.w)
def angle(left, right):
    dot = abs(sum(a * b for a, b in zip(left, right))); return 2.0 * math.acos(max(-1.0, min(1.0, dot)))

root = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(root / "tools/trajectory")); import orientation_reference as oracle
cls = unreal.load_class(None, CLASS); require(cls is not None, "class"); obj = unreal.get_default_object(cls)
properties = (ALIGNED, TANGENTS, DURATIONS, STARTS, START_CONTROLS, END_CONTROLS, TOTAL, VALID) + PRIMITIVE
saved = {name: get(obj, name) for name in properties}
try:
    rng = random.Random(0xEDD063); fixtures = []
    for _ in range(64):
        rotations = [tuple(rng.uniform(-4.0, 4.0) for _ in range(4)) for _ in range(rng.randint(2, 64))]; durations = [rng.uniform(0.05, 8.0) for _ in range(len(rotations) - 1)]; fixtures.append((rotations, durations))
    maximum = 0.0
    for index, (rotations, durations) in enumerate(fixtures):
        expected = oracle.compile_orientation_track(rotations, durations)
        set_(obj, ALIGNED, [quat(v) for v in expected.waypoints]); set_(obj, TANGENTS, [vector(v) for v in expected.tangent_rates]); set_(obj, DURATIONS, durations)
        set_(obj, STARTS, [99.0]); set_(obj, START_CONTROLS, [quat((1, 0, 0, 0))]); set_(obj, END_CONTROLS, [quat((1, 0, 0, 0))]); set_(obj, TOTAL, 99.0); set_(obj, VALID, True)
        obj.call_method("BuildOrientationTrackSegmentsV1")
        actual_starts = [float(v) for v in get(obj, STARTS)]; actual_start_controls = [tuple4(v) for v in get(obj, START_CONTROLS)]; actual_end_controls = [tuple4(v) for v in get(obj, END_CONTROLS)]
        require(get(obj, VALID), f"valid-stage:{index}"); require(len(actual_starts) == len(expected.segments), f"start-count:{index}"); require(len(actual_start_controls) == len(expected.segments) and len(actual_end_controls) == len(expected.segments), f"control-count:{index}")
        for segment, actual_start, actual_sc, actual_ec in zip(expected.segments, actual_starts, actual_start_controls, actual_end_controls):
            require(abs(actual_start - segment.start_seconds) <= 2e-9, f"start:{index}"); error_sc = angle(actual_sc, segment.start_control); error_ec = angle(actual_ec, segment.end_control); maximum = max(maximum, error_sc, error_ec); require(error_sc <= 8e-7 and error_ec <= 8e-7, f"control:{index}:{error_sc}:{error_ec}")
        require(abs(float(get(obj, TOTAL)) - expected.total_seconds) <= 2e-9, f"total:{index}")

    identity = quat((0, 0, 0, 1)); zero = quat((0, 0, 0, 0)); axis = quat((0, 0, math.sin(0.4), math.cos(0.4)))
    set_(obj, ALIGNED, [identity, axis]); set_(obj, TANGENTS, [vector((0, 0, .8)), vector((0, 0, .8))]); set_(obj, DURATIONS, [1.0]); set_(obj, STARTS, [99.0]); set_(obj, START_CONTROLS, [axis]); set_(obj, END_CONTROLS, [axis]); set_(obj, TOTAL, 99.0); set_(obj, VALID, False); obj.call_method("BuildOrientationTrackSegmentsV1")
    require(not get(obj, VALID) and len(get(obj, STARTS)) == 0 and len(get(obj, START_CONTROLS)) == 0 and len(get(obj, END_CONTROLS)) == 0 and float(get(obj, TOTAL)) == 0.0, "prior-invalid clearing")
    set_(obj, ALIGNED, [zero, identity, axis]); set_(obj, TANGENTS, [vector((0,0,0)), vector((0,0,.4)), vector((0,0,.8))]); set_(obj, DURATIONS, [1.0, 2.0]); set_(obj, VALID, True); obj.call_method("BuildOrientationTrackSegmentsV1")
    require(not get(obj, VALID) and len(get(obj, STARTS)) == 0 and float(get(obj, TOTAL)) == 0.0, "early primitive failure")
    set_(obj, ALIGNED, [identity, axis, zero]); set_(obj, TANGENTS, [vector((0,0,.8)), vector((0,0,.8)), vector((0,0,0))]); set_(obj, DURATIONS, [1.0, 2.0]); set_(obj, VALID, True); obj.call_method("BuildOrientationTrackSegmentsV1")
    require(not get(obj, VALID) and len(get(obj, STARTS)) == 1 and len(get(obj, START_CONTROLS)) == 1 and len(get(obj, END_CONTROLS)) == 1 and abs(float(get(obj, TOTAL)) - 1.0) <= 1e-12, "late failure prefix")
    emit("VALID_TRACKS", len(fixtures)); emit("MAX_ANGULAR_ERROR", maximum); emit("FAILURE_CASES", 3); emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items(): set_(obj, name, value)
    emit("STATE_RESTORED", True)
