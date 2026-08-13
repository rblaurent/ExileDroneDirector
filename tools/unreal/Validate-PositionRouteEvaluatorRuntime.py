"""Execute compiled absolute-time position evaluation against the frozen oracle."""
from __future__ import annotations
import importlib, math, random, sys
from pathlib import Path
import unreal

PREFIX="EDD_POSITION_ROUTE_EVALUATOR_RUNTIME"
CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUT_ARRAYS=("PositionRouteInputWaypointPositionsV1","PositionRouteInputDurationsV1","PositionRouteInputSpatialCurveTypesV1","PositionRouteInputTimeProfilesV1")
INPUT_SCALARS=("PositionRouteInputArcToleranceV1","PositionRouteInputMaxArcDepthV1","PositionRouteInputMaxArcOperationsV1")
COMPILED_ARRAYS=("PositionRouteCompiledWaypointPositionsV1","PositionRouteCompiledDurationsV1","PositionRouteCompiledSpatialCurveTypesV1","PositionRouteCompiledTimeProfilesV1","PositionRouteCompiledWaypointVelocitiesV1","PositionRouteCompiledSegmentStartsV1","PositionRouteCompiledArcSampleStartsV1","PositionRouteCompiledArcSampleCountsV1","PositionRouteCompiledArcUsV1","PositionRouteCompiledArcDistancesV1","PositionRouteCompiledSegmentLengthsV1")
COMPILED_SCALARS=("PositionRouteCompiledTotalSecondsV1","PositionRouteCompiledTotalDistanceV1","PositionRouteCompileValidV1")
RESULTS=("PositionRouteInputElapsedSecondsV1","PositionRouteResultSegmentIndexV1","PositionRouteResultLocalTimeAlphaV1","PositionRouteResultDistanceAlphaV1","PositionRouteResultCurveUV1","PositionRouteResultPositionV1","PositionRouteResultCompleteV1","PositionRouteResultValidV1")
SCALAR_PRIMITIVE=("TrajectoryInputProfileV1","TrajectoryInputAlphaV1","TrajectoryResultValueV1","TrajectoryResultValidV1")
ARC_PRIMITIVE=("TrajectoryArcInputUsV1","TrajectoryArcInputDistancesV1","TrajectoryArcInputLengthV1","TrajectoryArcInputDistanceAlphaV1","TrajectoryArcResultUV1","TrajectoryArcResultValidV1","TrajectoryArcScratchUpperIndexV1","TrajectoryArcScratchValidV1")
VECTOR_PRIMITIVE=("TrajectoryInputStartPositionVectorV1","TrajectoryInputStartVelocityUVectorV1","TrajectoryInputStartAccelerationUVectorV1","TrajectoryInputEndPositionVectorV1","TrajectoryInputEndVelocityUVectorV1","TrajectoryInputEndAccelerationUVectorV1","TrajectoryResultPositionVectorV1","TrajectoryResultDerivativeUVectorV1","TrajectoryResultSecondDerivativeUVectorV1","TrajectoryResultVectorValidV1")

def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake="".join(("_"+c.lower()) if c.isupper() else c for c in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
    for candidate in variants(name):
        try:return obj.get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError(name)
def set_(obj,name,value):
    for candidate in variants(name):
        try:obj.set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError(name)
def vector(value):return unreal.Vector(*(float(x) for x in value))
def xyz(value):return float(value.x),float(value.y),float(value.z)
def close(a,b,tolerance=2.0e-6):return abs(float(a)-float(b))<=tolerance*max(1.0,abs(float(a)),abs(float(b)))
def vector_close(a,b,tolerance=2.0e-5):return all(close(x,y,tolerance) for x,y in zip(a,b))
def normalized(value):
    if isinstance(value,(list,tuple)):
        return tuple(normalized(item) for item in value)
    if hasattr(value,"x") and hasattr(value,"y") and hasattr(value,"z"):return xyz(value)
    if isinstance(value,float):return float(value)
    return value

root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/"tools/trajectory"));import cinematic_reference as oracle;importlib.reload(oracle)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls)
properties=INPUT_ARRAYS+INPUT_SCALARS+COMPILED_ARRAYS+COMPILED_SCALARS+RESULTS+SCALAR_PRIMITIVE+ARC_PRIMITIVE+VECTOR_PRIMITIVE
saved={name:get(obj,name) for name in properties}

def fixture(points,durations,curves,profiles,tolerance=.01,depth=8,operations=8191):return (tuple(points),tuple(durations),tuple(curves),tuple(profiles),float(tolerance),int(depth),int(operations))
def compile_route(value):
    points,durations,curves,profiles,tolerance,depth,operations=value
    set_(obj,INPUT_ARRAYS[0],[vector(p) for p in points]);set_(obj,INPUT_ARRAYS[1],[float(x) for x in durations]);set_(obj,INPUT_ARRAYS[2],list(curves));set_(obj,INPUT_ARRAYS[3],list(profiles));set_(obj,INPUT_SCALARS[0],tolerance);set_(obj,INPUT_SCALARS[1],depth);set_(obj,INPUT_SCALARS[2],operations);obj.call_method("CompilePositionRouteV1");require(bool(get(obj,"PositionRouteCompileValidV1")),"compile precondition")
    authored=tuple(oracle.AuthoredSegment(d,c,p) for d,c,p in zip(durations,curves,profiles));return oracle.compile_trajectory(points,authored,arc_tolerance=tolerance,max_arc_depth=depth)
def compiled_snapshot():return {name:normalized(get(obj,name)) for name in COMPILED_ARRAYS+COMPILED_SCALARS}
def evaluate(elapsed):
    set_(obj,RESULTS[0],float(elapsed));obj.call_method("EvaluateCompiledPositionRouteV1");return (int(get(obj,RESULTS[1])),float(get(obj,RESULTS[2])),float(get(obj,RESULTS[3])),float(get(obj,RESULTS[4])),xyz(get(obj,RESULTS[5])),bool(get(obj,RESULTS[6])),bool(get(obj,RESULTS[7])))
def prefill_stale():
    values=(73,.73,.64,.55,vector((9,8,7)),True,True)
    for name,value in zip(RESULTS[1:],values):set_(obj,name,value)
    set_(obj,"TrajectoryResultValidV1",True);set_(obj,"TrajectoryArcResultUV1",.44);set_(obj,"TrajectoryArcResultValidV1",True);set_(obj,"TrajectoryResultPositionVectorV1",vector((6,5,4)));set_(obj,"TrajectoryResultVectorValidV1",True)
def require_cleared(label):
    actual=evaluate_result()
    require(actual[0]==-1,label+":segment");require(actual[1:4]==(0.0,0.0,0.0),label+":alphas");require(actual[4]==(0.0,0.0,0.0),label+":position");require(actual[5:]==(False,False),label+":flags")
    require(not bool(get(obj,"TrajectoryResultValidV1")),label+":time-valid");require(not bool(get(obj,"TrajectoryArcResultValidV1")),label+":arc-valid");require(not bool(get(obj,"TrajectoryResultVectorValidV1")),label+":vector-valid")
def evaluate_result():return (int(get(obj,RESULTS[1])),float(get(obj,RESULTS[2])),float(get(obj,RESULTS[3])),float(get(obj,RESULTS[4])),xyz(get(obj,RESULTS[5])),bool(get(obj,RESULTS[6])),bool(get(obj,RESULTS[7])))

try:
    rng=random.Random(0xEDD078);profiles=tuple(oracle.SUPPORTED_TIME_PROFILES);fixtures=[
        fixture(((0,0,0),(10,0,0)),(2.0,),('linear',),('linear',)),
        fixture(((1,2,3),(1,2,3),(9,-4,2)),(1.0,3.0),('linear','auto_cinematic'),('smoothstep','cinematic_s_curve')),
        fixture(((0,0,0),(5,8,1),(12,3,7),(20,10,-2)),(.3,2.7,1.1),('auto_cinematic',)*3,('accelerate_through','brake_into','smootherstep')),
    ]
    for _ in range(13):
        count=rng.randint(2,18);points=[];cursor=[0.0,0.0,0.0]
        for _index in range(count):
            cursor=[cursor[axis]+rng.uniform(-30,30) for axis in range(3)];points.append(tuple(cursor))
        durations=[rng.uniform(.04,5.0) for _ in range(count-1)];curves=[rng.choice(('linear','auto_cinematic')) for _ in durations];time=[rng.choice(profiles) for _ in durations];fixtures.append(fixture(points,durations,curves,time,.02,8,8191))
    fixtures.append(fixture(tuple((float(i),float(i%7),0.0) for i in range(512)),(0.05,)*511,('linear',)*511,('linear',)*511,.01,8,8191))
    evaluations=0;scrubs=0;max_local=max_distance=max_u=max_position=0.0
    for fi,value in enumerate(fixtures):
        compiled=compile_route(value);source=compiled_snapshot();samples=[-5.0,0.0,compiled.total_seconds,compiled.total_seconds+5.0]
        for segment in compiled.segments:
            samples.extend((segment.start_seconds,segment.start_seconds+segment.duration_seconds*.25,segment.start_seconds+segment.duration_seconds*.5,segment.start_seconds+segment.duration_seconds-1.0e-9,segment.start_seconds+segment.duration_seconds))
        samples.extend(rng.uniform(-1.0,compiled.total_seconds+1.0) for _ in range(16))
        for si,elapsed in enumerate(samples):
            expected=oracle.evaluate_position(compiled,elapsed);actual=evaluate(elapsed);require(actual[6],f"valid:{fi}:{si}");require(actual[5]==expected.complete,f"complete:{fi}:{si}");require(actual[0]==expected.segment_index,f"segment:{fi}:{si}:{actual[0]}:{expected.segment_index}")
            max_local=max(max_local,abs(actual[1]-expected.local_time_alpha));max_distance=max(max_distance,abs(actual[2]-expected.distance_alpha));max_u=max(max_u,abs(actual[3]-expected.curve_u));max_position=max(max_position,max(abs(a-b) for a,b in zip(actual[4],expected.position)))
            require(close(actual[1],expected.local_time_alpha,2e-8),f"local:{fi}:{si}");require(close(actual[2],expected.distance_alpha,2e-8),f"distance:{fi}:{si}");require(close(actual[3],expected.curve_u,3e-6),f"u:{fi}:{si}:{actual[3]}:{expected.curve_u}");require(vector_close(actual[4],expected.position,4e-5),f"position:{fi}:{si}:{actual[4]}:{expected.position}");require(compiled_snapshot()==source,f"source mutation:{fi}:{si}");evaluations+=1
        target=rng.uniform(0.0,compiled.total_seconds);first=evaluate(target);shuffled=list(samples);rng.shuffle(shuffled)
        for elapsed in shuffled[:min(24,len(shuffled))]:evaluate(elapsed)
        second=evaluate(target);require(first==second,f"direct scrub:{fi}");scrubs+=1

    base=fixtures[2];compile_route(base);invalid=[]
    invalid.append(("compile-invalid","PositionRouteCompileValidV1",False,0.0))
    for name in COMPILED_ARRAYS:
        value=list(get(obj,name));invalid.append(("cardinality-"+name,name,value[:-1],0.0))
    invalid.extend((("total-zero","PositionRouteCompiledTotalSecondsV1",0.0,0.0),("selected-duration-zero","PositionRouteCompiledDurationsV1",[0.0]+list(get(obj,"PositionRouteCompiledDurationsV1"))[1:],-1.0),("unknown-profile","PositionRouteCompiledTimeProfilesV1",['not_a_profile']+list(get(obj,"PositionRouteCompiledTimeProfilesV1"))[1:],0.1),("unknown-curve","PositionRouteCompiledSpatialCurveTypesV1",['not_a_curve']+list(get(obj,"PositionRouteCompiledSpatialCurveTypesV1"))[1:],0.1),("slice-overflow","PositionRouteCompiledArcSampleStartsV1",[2147483647]+list(get(obj,"PositionRouteCompiledArcSampleStartsV1"))[1:],0.1)))
    invalid_reached=0
    for label,name,bad,elapsed in invalid:
        compile_route(base);prefill_stale();set_(obj,name,bad);before=compiled_snapshot();set_(obj,RESULTS[0],elapsed);obj.call_method("EvaluateCompiledPositionRouteV1");require_cleared(label);require(compiled_snapshot()==before,label+":source mutation");invalid_reached+=1
    nonfinite=0
    for label,elapsed in (("elapsed-nan",float('nan')),("elapsed-inf",float('inf')),("elapsed-negative-inf",float('-inf'))):
        compile_route(base);prefill_stale();set_(obj,RESULTS[0],elapsed);staged=float(get(obj,RESULTS[0]))
        if math.isfinite(staged):emit("REFLECTION_SANITIZED",label);continue
        before=compiled_snapshot();obj.call_method("EvaluateCompiledPositionRouteV1");require_cleared(label);require(compiled_snapshot()==before,label+":source mutation");nonfinite+=1
    emit("VALID_ROUTES",len(fixtures));emit("EVALUATIONS",evaluations);emit("DIRECT_SCRUB_CASES",scrubs);emit("MAX_WAYPOINTS",512);emit("INVALID_COMPILED_CASES",invalid_reached);emit("NONFINITE_REACHED_BLUEPRINT",nonfinite);emit("MAX_LOCAL_ERROR",max_local);emit("MAX_DISTANCE_ERROR",max_distance);emit("MAX_U_ERROR",max_u);emit("MAX_POSITION_ERROR",max_position);emit("COMPLETE","PASS")
finally:
    for name,value in saved.items():set_(obj,name,value)
    emit("STATE_RESTORED",True)
