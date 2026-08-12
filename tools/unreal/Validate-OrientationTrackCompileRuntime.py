"""Execute the complete ordered orientation compiler against the frozen oracle."""
from __future__ import annotations
import math,random,sys
from pathlib import Path
import unreal

PREFIX="EDD_ORIENTATION_TRACK_COMPILE_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUTS=("OrientationTrackInputWaypointQuatsV1","OrientationTrackInputDurationsV1")
COMPILED=("OrientationTrackCompiledAlignedQuatsV1","OrientationTrackCompiledDurationsV1","OrientationTrackCompiledTangentRatesV1","OrientationTrackCompiledSegmentStartsV1","OrientationTrackCompiledStartControlsV1","OrientationTrackCompiledEndControlsV1","OrientationTrackCompiledTotalSecondsV1","OrientationTrackCompileValidV1")
CANDIDATES=("OrientationTrackCandidateAlignedQuatsV1","OrientationTrackCandidateForwardDeltasV1","OrientationTrackCandidateTangentRatesV1","OrientationTrackCandidateSegmentStartsV1","OrientationTrackCandidateStartControlsV1","OrientationTrackCandidateEndControlsV1","OrientationTrackCandidateTotalSecondsV1","OrientationTrackStageValidV1")
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
def qtuple(v):return float(v.x),float(v.y),float(v.z),float(v.w)
def vtuple(v):return float(v.x),float(v.y),float(v.z)
def angle(a,b):return 2*math.acos(max(-1,min(1,abs(sum(x*y for x,y in zip(a,b))))))
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/"tools/trajectory"));import orientation_reference as oracle
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);properties=INPUTS+CANDIDATES+COMPILED+RESULTS;saved={n:get(obj,n) for n in properties}
def run(rotations,durations):set_(obj,INPUTS[0],[quat(v) for v in rotations]);set_(obj,INPUTS[1],durations);obj.call_method("CompileOrientationTrackV1")
def cleared(label):require(not get(obj,COMPILED[7]),label+":valid");require(all(len(get(obj,n))==0 for n in COMPILED[:6]),label+":arrays");require(float(get(obj,COMPILED[6]))==0,label+":total");require(int(get(obj,RESULTS[0]))==-1 and float(get(obj,RESULTS[1]))==0 and qtuple(get(obj,RESULTS[2]))==(0,0,0,1) and not get(obj,RESULTS[3]) and not get(obj,RESULTS[4]),label+":results")
try:
    rng=random.Random(0xEDD065);fixtures=[]
    for _ in range(64):
        rotations=[tuple(rng.uniform(-4,4) for _ in range(4)) for _ in range(rng.randint(2,64))];durations=[rng.uniform(.02,8) for _ in range(len(rotations)-1)];fixtures.append((rotations,durations,oracle.compile_orientation_track(rotations,durations)))
    maximum=0.0;maximum_tangent_error=0.0
    for i,(rotations,durations,track) in enumerate(fixtures):
        run(rotations,durations);require(get(obj,COMPILED[7]),f"valid:{i}");require(get(obj,CANDIDATES[7]),f"stage:{i}");require(len(get(obj,COMPILED[0]))==len(track.waypoints),f"keys:{i}")
        for actual,expected in zip(get(obj,COMPILED[0]),track.waypoints):maximum=max(maximum,angle(qtuple(actual),expected))
        for actual,expected in zip(get(obj,COMPILED[4]),(s.start_control for s in track.segments)):maximum=max(maximum,angle(qtuple(actual),expected))
        for actual,expected in zip(get(obj,COMPILED[5]),(s.end_control for s in track.segments)):maximum=max(maximum,angle(qtuple(actual),expected))
        require(len(get(obj,COMPILED[2]))==len(track.tangent_rates),f"tangents:{i}")
        for actual,expected in zip(get(obj,COMPILED[2]),track.tangent_rates):
            maximum_tangent_error=max(maximum_tangent_error,max(abs(a-b) for a,b in zip(vtuple(actual),expected)))
        require([float(x) for x in get(obj,COMPILED[1])]==[float(x) for x in durations],f"durations:{i}");require([float(x) for x in get(obj,COMPILED[3])]==[s.start_seconds for s in track.segments],f"starts:{i}");require(abs(float(get(obj,COMPILED[6]))-track.total_seconds)<=2e-9,f"total:{i}")
    first=fixtures[0];second=fixtures[-1];run(first[0],first[1]);first_snapshot=[qtuple(x) for x in get(obj,COMPILED[0])];run(second[0],second[1]);second_snapshot=[qtuple(x) for x in get(obj,COMPILED[0])];require(first_snapshot!=second_snapshot,"replacement changed");require(len(second_snapshot)==len(second[2].waypoints),"replacement count")
    cases=(("empty",[],[]),("one",[(0,0,0,1)],[]),("duration-count",[(0,0,0,1),(0,0,1,0)],[]),("zero-quat",[(0,0,0,1),(0,0,0,0)],[1]),("zero-duration",[(0,0,0,1),(0,0,1,0)],[0]),("negative-duration",[(0,0,0,1),(0,0,1,0)],[-1]),("nan-duration",[(0,0,0,1),(0,0,1,0)],[float("nan")]),("inf-duration",[(0,0,0,1),(0,0,1,0)],[float("inf")]))
    for label,rotations,durations in cases:run(first[0],first[1]);require(get(obj,COMPILED[7]),label+":precondition");run(rotations,durations);cleared(label);require(not get(obj,CANDIDATES[7]),label+":stage")
    emit("MAX_TANGENT_COMPONENT_ERROR",maximum_tangent_error);require(maximum_tangent_error<=2e-6,"tangent oracle error")
    emit("VALID_TRACKS",len(fixtures));emit("MAX_ANGULAR_ERROR",maximum);emit("REPLACEMENT_CASES",1);emit("INVALID_CASES",len(cases));emit("COMPLETE","PASS")
finally:
    for n,v in saved.items():set_(obj,n,v)
    emit("STATE_RESTORED",True)
