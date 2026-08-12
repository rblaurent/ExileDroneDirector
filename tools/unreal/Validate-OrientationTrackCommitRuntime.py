"""Execute atomic compiled-orientation publication and failure clearing."""
from __future__ import annotations
import math,random,sys
from pathlib import Path
import unreal

PREFIX="EDD_ORIENTATION_TRACK_COMMIT_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
CANDIDATE=("OrientationTrackCandidateAlignedQuatsV1","OrientationTrackInputDurationsV1","OrientationTrackCandidateTangentRatesV1","OrientationTrackCandidateSegmentStartsV1","OrientationTrackCandidateStartControlsV1","OrientationTrackCandidateEndControlsV1","OrientationTrackCandidateTotalSecondsV1","OrientationTrackStageValidV1")
COMPILED=("OrientationTrackCompiledAlignedQuatsV1","OrientationTrackCompiledDurationsV1","OrientationTrackCompiledTangentRatesV1","OrientationTrackCompiledSegmentStartsV1","OrientationTrackCompiledStartControlsV1","OrientationTrackCompiledEndControlsV1","OrientationTrackCompiledTotalSecondsV1","OrientationTrackCompileValidV1")
RESULTS=("OrientationTrackResultSegmentIndexV1","OrientationTrackResultAlphaV1","OrientationTrackResultQuatV1","OrientationTrackResultCompleteV1","OrientationTrackResultValidV1")
def emit(n,v):unreal.log(f"{PREFIX}|{n}|{v}")
def require(c,m):
    if not c:raise RuntimeError(f"{PREFIX}|FAIL|{m}")
def variants(n):s="".join(("_"+c.lower()) if c.isupper() else c for c in n).lstrip("_");return n,unreal.Name(n),s,unreal.Name(s)
def get(o,n):
    for c in variants(n):
        try:return o.get_editor_property(c)
        except Exception:pass
    raise RuntimeError(n)
def set_(o,n,v):
    for c in variants(n):
        try:o.set_editor_property(c,v);return
        except Exception:pass
    raise RuntimeError(n)
def quat(v):return unreal.Quat(*(float(x) for x in v))
def vector(v):return unreal.Vector(*(float(x) for x in v))
def qtuple(v):return float(v.x),float(v.y),float(v.z),float(v.w)
def vtuple(v):return float(v.x),float(v.y),float(v.z)
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/"tools/trajectory"));import orientation_reference as oracle
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);properties=CANDIDATE+COMPILED+RESULTS;saved={n:get(obj,n) for n in properties}
def stage(track,durations,valid=True):
    set_(obj,CANDIDATE[0],[quat(v) for v in track.waypoints]);set_(obj,CANDIDATE[1],durations);set_(obj,CANDIDATE[2],[vector(v) for v in track.tangent_rates]);set_(obj,CANDIDATE[3],[s.start_seconds for s in track.segments]);set_(obj,CANDIDATE[4],[quat(s.start_control) for s in track.segments]);set_(obj,CANDIDATE[5],[quat(s.end_control) for s in track.segments]);set_(obj,CANDIDATE[6],track.total_seconds);set_(obj,CANDIDATE[7],valid)
def poison():
    set_(obj,COMPILED[0],[quat((1,0,0,0))]);set_(obj,COMPILED[1],[99.0]);set_(obj,COMPILED[2],[vector((9,8,7))]);set_(obj,COMPILED[3],[99.0]);set_(obj,COMPILED[4],[quat((1,0,0,0))]);set_(obj,COMPILED[5],[quat((1,0,0,0))]);set_(obj,COMPILED[6],99.0);set_(obj,COMPILED[7],True);set_(obj,RESULTS[0],99);set_(obj,RESULTS[1],.75);set_(obj,RESULTS[2],quat((1,0,0,0)));set_(obj,RESULTS[3],True);set_(obj,RESULTS[4],True)
def cleared(label):
    require(not get(obj,COMPILED[7]),label+":valid");require(all(len(get(obj,n))==0 for n in COMPILED[:6]),label+":arrays");require(float(get(obj,COMPILED[6]))==0.0,label+":total");require(int(get(obj,RESULTS[0]))==-1 and float(get(obj,RESULTS[1]))==0.0 and qtuple(get(obj,RESULTS[2]))==(0.0,0.0,0.0,1.0) and not get(obj,RESULTS[3]) and not get(obj,RESULTS[4]),label+":results")
try:
    rng=random.Random(0xEDD064);fixtures=[]
    for _ in range(48):
        rotations=[tuple(rng.uniform(-3,3) for _ in range(4)) for _ in range(rng.randint(2,48))];durations=[rng.uniform(.05,6) for _ in range(len(rotations)-1)];fixtures.append((oracle.compile_orientation_track(rotations,durations),durations))
    maximum=0.0
    for i,(track,durations) in enumerate(fixtures):
        stage(track,durations);expected_quats=[qtuple(x) for x in get(obj,CANDIDATE[0])];expected_start=[qtuple(x) for x in get(obj,CANDIDATE[4])];expected_end=[qtuple(x) for x in get(obj,CANDIDATE[5])];poison();obj.call_method("CommitCompiledOrientationTrackV1");require(get(obj,COMPILED[7]),f"valid:{i}");require(len(get(obj,COMPILED[0]))==len(track.waypoints) and len(get(obj,COMPILED[1]))==len(track.segments),f"count:{i}")
        require(len(get(obj,COMPILED[4]))==len(track.segments) and len(get(obj,COMPILED[5]))==len(track.segments),f"control count:{i}")
        actual_quats=[qtuple(x) for x in get(obj,COMPILED[0])];actual_start=[qtuple(x) for x in get(obj,COMPILED[4])];actual_end=[qtuple(x) for x in get(obj,COMPILED[5])]
        require(actual_quats==expected_quats,f"waypoint copy:{i}");require(actual_start==expected_start,f"start control copy:{i}");require(actual_end==expected_end,f"end control copy:{i}")
        maximum=max(maximum,max(abs(a-b) for actual,expected in zip(actual_quats+actual_start+actual_end,expected_quats+expected_start+expected_end) for a,b in zip(actual,expected)))
        require([float(x) for x in get(obj,COMPILED[1])]==[float(x) for x in durations],f"durations:{i}");require([vtuple(x) for x in get(obj,COMPILED[2])]==[tuple(float(y) for y in x) for x in track.tangent_rates],f"tangents:{i}");require([float(x) for x in get(obj,COMPILED[3])]==[s.start_seconds for s in track.segments],f"starts:{i}");require(abs(float(get(obj,COMPILED[6]))-track.total_seconds)<=2e-9,f"total:{i}");require(int(get(obj,RESULTS[0]))==-1 and not get(obj,RESULTS[4]),f"result reset:{i}")
        require(float(get(obj,RESULTS[1]))==0.0 and qtuple(get(obj,RESULTS[2]))==(0.0,0.0,0.0,1.0) and not get(obj,RESULTS[3]),f"complete result reset:{i}")
    track,durations=fixtures[0];cases=[]
    cases.append(("stage-false",lambda:stage(track,durations,False)))
    cases.append(("duration-cardinality",lambda:(stage(track,durations),set_(obj,CANDIDATE[1],durations[:-1]))))
    cases.append(("tangent-cardinality",lambda:(stage(track,durations),set_(obj,CANDIDATE[2],[vector(v) for v in track.tangent_rates[:-1]]))))
    cases.append(("start-cardinality",lambda:(stage(track,durations),set_(obj,CANDIDATE[3],[s.start_seconds for s in track.segments[:-1]]))))
    cases.append(("start-control-cardinality",lambda:(stage(track,durations),set_(obj,CANDIDATE[4],[quat(s.start_control) for s in track.segments[:-1]]))))
    cases.append(("end-control-cardinality",lambda:(stage(track,durations),set_(obj,CANDIDATE[5],[quat(s.end_control) for s in track.segments[:-1]]))))
    cases.append(("bad-first-start",lambda:(stage(track,durations),set_(obj,CANDIDATE[3],[1.0]+[s.start_seconds for s in track.segments[1:]]))))
    cases.append(("bad-late-start",lambda:(stage(track,durations),set_(obj,CANDIDATE[3],[s.start_seconds+(0.25 if i==len(track.segments)-1 else 0) for i,s in enumerate(track.segments)]))))
    cases.append(("bad-total",lambda:(stage(track,durations),set_(obj,CANDIDATE[6],track.total_seconds+1))))
    cases.append(("nonfinite-total",lambda:(stage(track,durations),set_(obj,CANDIDATE[6],float("nan")))))
    cases.append(("zero-duration",lambda:(stage(track,durations),set_(obj,CANDIDATE[1],[0.0]+durations[1:]))))
    for label,prepare in cases:prepare();poison();obj.call_method("CommitCompiledOrientationTrackV1");cleared(label);require(not get(obj,CANDIDATE[7]),label+":stage")
    emit("VALID_TRACKS",len(fixtures));emit("MAX_PUBLICATION_COMPONENT_ERROR",maximum);emit("FAILURE_CASES",len(cases));emit("COMPLETE","PASS")
finally:
    for n,v in saved.items():set_(obj,n,v)
    emit("STATE_RESTORED",True)
