"""Execute compiled multi-key tangent-rate assembly against the frozen oracle."""
from __future__ import annotations
import math,random,sys
from pathlib import Path
import unreal
P="EDD_ORIENTATION_TRACK_TANGENT_RUNTIME";C="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
AL="OrientationTrackCandidateAlignedQuatsV1";DE="OrientationTrackCandidateForwardDeltasV1";DU="OrientationTrackInputDurationsV1";OUT="OrientationTrackCandidateTangentRatesV1";VA="OrientationTrackStageValidV1"
SCR=("OrientationInputPreviousDeltaVectorV1","OrientationInputNextDeltaVectorV1","OrientationInputPreviousDurationV1","OrientationInputNextDurationV1","OrientationResultTangentRateVectorV1","OrientationResultValidV1")
def emit(a,b):unreal.log(f"{P}|{a}|{b}")
def req(c,m):
    if not c:raise RuntimeError(f"{P}|FAIL|{m}")
def names(v):
    s="".join(("_"+c.lower()) if c.isupper() else c for c in v).lstrip("_");return v,unreal.Name(v),s,unreal.Name(s)
def get(o,n):
    for x in names(n):
        try:return o.get_editor_property(x)
        except Exception:pass
    raise RuntimeError(n)
def set_(o,n,v):
    for x in names(n):
        try:o.set_editor_property(x,v);return
        except Exception:pass
    raise RuntimeError(n)
def q(v):return unreal.Quat(*map(float,v))
def vec(v):return unreal.Vector(*map(float,v))
def tup(v):return float(v.x),float(v.y),float(v.z)
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/"tools/trajectory"));import orientation_reference as oracle
cls=unreal.load_class(None,C);req(cls is not None,"class");o=unreal.get_default_object(cls);props=(AL,DE,DU,OUT,VA)+SCR;saved={n:get(o,n) for n in props}
try:
    rng=random.Random(0xEDD063);fixtures=[(((0,0,0,1),(0,0,1,0)),(2.0,))]
    for _ in range(63):
        raw=[tuple(rng.uniform(-4,4) for _ in range(4)) for _ in range(rng.randint(2,48))];dur=tuple(rng.uniform(.05,8) for _ in range(len(raw)-1));fixtures.append((tuple(raw),dur))
    maximum=0.0
    for i,(raw,durations) in enumerate(fixtures):
        compiled=oracle.compile_orientation_track(raw,durations);aligned=compiled.waypoints;deltas=[oracle.logarithmic_delta(a,b) for a,b in zip(aligned,aligned[1:])]
        set_(o,AL,[q(x) for x in aligned]);set_(o,DE,[vec(x) for x in deltas]);set_(o,DU,list(durations));set_(o,OUT,[vec((99,98,97))]);set_(o,VA,True);o.call_method("ComputeOrientationTrackTangentRatesV1")
        actual=[tup(x) for x in get(o,OUT)];req(get(o,VA),f"valid:{i}");req(len(actual)==len(compiled.tangent_rates),f"count:{i}")
        for av,ev in zip(actual,compiled.tangent_rates):
            error=math.sqrt(sum((a-e)**2 for a,e in zip(av,ev)));maximum=max(maximum,error);req(error<=8e-7,f"rate:{i}:{error}")
    set_(o,AL,[q((0,0,0,1)),q((0,0,1,0))]);set_(o,DE,[vec((0,0,1))]);set_(o,DU,[1.0]);set_(o,OUT,[vec((7,8,9))]);set_(o,VA,False);o.call_method("ComputeOrientationTrackTangentRatesV1");req(len(get(o,OUT))==0 and not get(o,VA),"prior invalid")
    set_(o,AL,[q((0,0,0,1)),q((0,0,1,0)),q((0,1,0,0))]);set_(o,DE,[vec((0,0,1)),vec((0,1,0))]);set_(o,DU,[0.0,1.0]);set_(o,OUT,[vec((7,8,9))]);set_(o,VA,True);o.call_method("ComputeOrientationTrackTangentRatesV1");req(not get(o,VA) and len(get(o,OUT))==0,"early failure healed")
    set_(o,DU,[1.0,0.0]);set_(o,OUT,[vec((7,8,9))]);set_(o,VA,True);o.call_method("ComputeOrientationTrackTangentRatesV1");req(not get(o,VA) and len(get(o,OUT))==1,"late failure prefix")
    emit("VALID_TRACKS",len(fixtures));emit("MAX_VECTOR_ERROR",maximum);emit("FAILURE_CASES",3);emit("COMPLETE","PASS")
finally:
    for n,v in saved.items():set_(o,n,v)
    emit("STATE_RESTORED",True)
