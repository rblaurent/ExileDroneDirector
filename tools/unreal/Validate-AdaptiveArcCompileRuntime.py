"""Execute the full adaptive arc compiler against the frozen oracle."""
from __future__ import annotations
import random,sys
from pathlib import Path
import unreal

PREFIX="EDD_ADAPTIVE_ARC_COMPILE_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUTS=("TrajectoryArcBuildInputStartPositionV1","TrajectoryArcBuildInputEndPositionV1","TrajectoryArcBuildInputStartVelocityUV1","TrajectoryArcBuildInputEndVelocityUV1","TrajectoryArcBuildInputStartAccelerationUV1","TrajectoryArcBuildInputEndAccelerationUV1","TrajectoryArcBuildInputLinearV1","TrajectoryArcBuildInputToleranceV1","TrajectoryArcBuildInputMaxDepthV1","TrajectoryArcBuildInputMaxOperationsV1")
PUBLISHED=("TrajectoryArcBuiltUsV1","TrajectoryArcBuiltDistancesV1","TrajectoryArcBuiltLengthV1","TrajectoryArcBuildValidV1")
STAGE=("TrajectoryArcBuildStageValidV1","TrajectoryArcBuildOperationCountV1")
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/"tools"/"trajectory"));from cinematic_reference import CompiledSegment,trace_arc_table_iterative
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
def vector(v):return unreal.Vector(*(float(x) for x in v))
def close(left,right,tolerance=2.0e-5):return abs(float(left)-float(right))<=tolerance
def make_segment(rng,linear):
    start=tuple(rng.uniform(-250,250) for _ in range(3));end=tuple(rng.uniform(-250,250) for _ in range(3));zero=(0.,0.,0.)
    return CompiledSegment(0.,1.,"linear" if linear else "auto_cinematic","linear",start,end,zero if linear else tuple(rng.uniform(-500,500) for _ in range(3)),zero if linear else tuple(rng.uniform(-500,500) for _ in range(3)),zero if linear else tuple(rng.uniform(-800,800) for _ in range(3)),zero if linear else tuple(rng.uniform(-800,800) for _ in range(3)),(),0.)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls);props=INPUTS+PUBLISHED+STAGE;saved={n:get(obj,n) for n in props}
def run(segment,tolerance=.01,depth=8,budget=8191):
    values=(segment.start,segment.end,segment.start_velocity_u,segment.end_velocity_u,segment.start_acceleration_u,segment.end_acceleration_u)
    for name,value in zip(INPUTS[:6],values):set_(obj,name,vector(value))
    set_(obj,INPUTS[6],segment.spatial_curve_type=="linear");set_(obj,INPUTS[7],tolerance);set_(obj,INPUTS[8],depth);set_(obj,INPUTS[9],budget);obj.call_method("BuildAdaptiveArcTableV1")
def cleared(label):require(not get(obj,PUBLISHED[3]),label+":valid");require(len(get(obj,PUBLISHED[0]))==0 and len(get(obj,PUBLISHED[1]))==0,label+":arrays");require(float(get(obj,PUBLISHED[2]))==0,label+":length");require(not get(obj,STAGE[0]),label+":stage")
try:
    rng=random.Random(0xEDD070);fixtures=[];maximum_distance_error=0.0;maximum_length_error=0.0
    for i in range(32):
        segment=make_segment(rng,i%4==0);tolerance=(.002,.01,.05,.2)[i%4];table,operations=trace_arc_table_iterative(segment,tolerance,8,8191);fixtures.append((segment,tolerance,table,operations))
    for i,(segment,tolerance,table,operations) in enumerate(fixtures):
        run(segment,tolerance);require(get(obj,PUBLISHED[3]) and get(obj,STAGE[0]),f"valid:{i}")
        actual_us=[float(x) for x in get(obj,PUBLISHED[0])];actual_distances=[float(x) for x in get(obj,PUBLISHED[1])]
        require(len(actual_us)==len(table) and len(actual_distances)==len(table),f"cardinality:{i}")
        for sample_index,sample in enumerate(table):
            require(close(actual_us[sample_index],sample.u),f"u:{i}:{sample_index}")
            distance_error=abs(actual_distances[sample_index]-float(sample.distance));maximum_distance_error=max(maximum_distance_error,distance_error);require(distance_error<=3.0e-4,f"distance:{i}:{sample_index}:{distance_error}")
        length_error=abs(float(get(obj,PUBLISHED[2]))-float(table[-1].distance));maximum_length_error=max(maximum_length_error,length_error);require(length_error<=3.0e-4,f"length:{i}:{length_error}")
        require(int(get(obj,STAGE[1]))==operations,f"operations:{i}")
    first=fixtures[0]
    last=fixtures[-1]
    run(first[0],first[1])
    snapshot=list(get(obj,PUBLISHED[1]))
    run(last[0],last[1])
    require(snapshot!=list(get(obj,PUBLISHED[1])),"replacement")
    invalid=(("zero-tolerance",0.,8,8191),("negative-tolerance",-.1,8,8191),("depth-low",.01,0,8191),("depth-high",.01,13,8191),("budget-low",.01,8,0),("one-short",first[1],8,max(1,first[3]-1)))
    for label,tolerance,depth,budget in invalid:
        run(first[0],first[1])
        require(get(obj,PUBLISHED[3]),label+":precondition")
        run(first[0],tolerance,depth,budget)
        cleared(label)
    emit("VALID_TABLES",len(fixtures));emit("INVALID_CASES",len(invalid));emit("REPLACEMENT_CASES",1);emit("MAX_DISTANCE_ERROR",f"{maximum_distance_error:.9g}");emit("MAX_LENGTH_ERROR",f"{maximum_length_error:.9g}");emit("COMPLETE","PASS")
finally:
    for n,v in saved.items():set_(obj,n,v)
    emit("STATE_RESTORED",True)
