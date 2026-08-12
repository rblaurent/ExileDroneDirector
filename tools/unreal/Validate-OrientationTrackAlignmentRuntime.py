"""Execute compiled orientation-key normalization/sign alignment against the oracle."""

from __future__ import annotations

import math, random, sys
from pathlib import Path
import unreal

PREFIX="EDD_ORIENTATION_TRACK_ALIGNMENT_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUT="OrientationTrackInputWaypointQuatsV1";OUTPUT="OrientationTrackCandidateAlignedQuatsV1";VALID="OrientationTrackStageValidV1"
def emit(a,b):unreal.log(f"{PREFIX}|{a}|{b}")
def require(c,m):
    if not c:raise RuntimeError(f"{PREFIX}|FAIL|{m}")
def names(v):
    snake="".join(("_"+c.lower()) if c.isupper() else c for c in v).lstrip("_");return v,unreal.Name(v),snake,unreal.Name(snake)
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
def q(v):return unreal.Quat(*(float(x) for x in v))
def t(v):return float(v.x),float(v.y),float(v.z),float(v.w)

root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/"tools/trajectory"));import orientation_reference as oracle
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");o=unreal.get_default_object(cls);saved={n:get(o,n) for n in (INPUT,OUTPUT,VALID)}
try:
    rng=random.Random(0xEDD061);fixtures=[((0,0,0,2),(0,0,0,-3)),((1,2,3,4),(-4,-3,-2,-1))]
    for _ in range(40):fixtures.append(tuple(tuple(rng.uniform(-4,4) for _ in range(4)) for _ in range(rng.randint(2,32))))
    maximum=0.0
    for index,values in enumerate(fixtures):
        expected=[]
        for value in values:
            current=oracle.normalize(value)
            if expected and sum(a*b for a,b in zip(expected[-1],current))<0:current=tuple(-x for x in current)
            expected.append(current)
        set_(o,INPUT,[q(x) for x in values]);set_(o,OUTPUT,[q((.1,.2,.3,.4))]);set_(o,VALID,True);o.call_method("AlignOrientationWaypointsV1")
        actual=[t(x) for x in get(o,OUTPUT)];require(len(actual)==len(expected),f"count:{index}")
        for a,e in zip(actual,expected):
            error=math.sqrt(sum(x*x for x in oracle.logarithmic_delta(a,e)));maximum=max(maximum,error);require(error<=2e-7,f"quat:{index}:{error}")
        require(all(sum(x*y for x,y in zip(a,b))>=-1e-12 for a,b in zip(actual,actual[1:])),f"sign:{index}")
    set_(o,INPUT,[q((0,0,0,1)),q((0,0,0,-1))]);set_(o,OUTPUT,[q((1,0,0,0))]);set_(o,VALID,False);o.call_method("AlignOrientationWaypointsV1");require(len(get(o,OUTPUT))==0,"invalid stage leaked")
    emit("VALID_TRACKS",len(fixtures));emit("MAX_ANGULAR_ERROR_RADIANS",maximum);emit("INVALID_STAGE_CASES",1);emit("COMPLETE","PASS")
finally:
    for n,v in saved.items():set_(o,n,v)
    emit("STATE_RESTORED",True)
