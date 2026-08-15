"""Execute the saved carrier-frame family against its independent oracle."""
from __future__ import annotations
import importlib,json,math,random,sys
from pathlib import Path
import unreal

PREFIX="EDD_CARRIER_FRAME_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/carrier_frame_transport_blueprint_schema.json").read_text(encoding="utf-8"))
UPSTREAM=("AirframeDesiredStreamCompileValidV1","AirframeDesiredStreamInputPositionsV1","AirframeDesiredStreamInputTotalSecondsV1","AirframeDesiredStreamInputFixedStepSecondsV1")
AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1")
DOWNSTREAM=("CameraOperatorInputCarrierFrameQuatV1","CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1")
COMPILED=("CarrierFrameCompiledTangentsV1","CarrierFrameCompiledQuatsV1","CarrierFrameCompiledTotalSecondsV1","CarrierFrameCompiledFixedStepSecondsV1","CarrierFrameCompileValidV1")
RESULT=("CarrierFrameResultSegmentIndexV1","CarrierFrameResultAlphaV1","CarrierFrameResultQuatV1","CarrierFrameResultCompleteV1","CarrierFrameResultValidV1")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
    for candidate in variants(name):
        try:return obj.get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError("missing property:"+name)
def set_(obj,name,value):
    for candidate in variants(name):
        try:obj.set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError("could not set property:"+name)
def vector(value):return unreal.Vector(*(float(v) for v in value))
def quat(value):return unreal.Quat(*(float(v) for v in value))
def clone(value):
    if isinstance(value,(list,tuple)):return [clone(item) for item in value]
    return value.copy() if hasattr(value,"copy") else value
def normalized(value):
    if isinstance(value,(list,tuple)):return tuple(normalized(item) for item in value)
    if isinstance(value,unreal.Vector):return float(value.x),float(value.y),float(value.z)
    if isinstance(value,unreal.Quat):return float(value.x),float(value.y),float(value.z),float(value.w)
    return value
def snapshot(obj,names):return tuple(normalized(get(obj,name)) for name in names)
def close(left,right,tolerance=5e-4):return abs(float(left)-float(right))<=tolerance*max(1.,abs(float(left)),abs(float(right)))
def vector_close(left,right,tolerance=5e-4):return all(close(a,b,tolerance) for a,b in zip(normalized(left),right))
def same_rotation(left,right,tolerance=5e-4):
    a=normalized(left);b=tuple(right);al=math.sqrt(sum(v*v for v in a));bl=math.sqrt(sum(v*v for v in b));return al>0. and bl>0. and abs(sum(x*y for x,y in zip(a,b))/(al*bl))>=1.-tolerance

sys.path.insert(0,str(ROOT/"tools/trajectory"));import carrier_frame_transport_reference as oracle;oracle=importlib.reload(oracle)
cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls)
owned=tuple(spec["name"] for spec in SCHEMA["variables"]);saved={name:clone(get(obj,name)) for name in owned+UPSTREAM};external_before=snapshot(obj,AUTHORSHIP+DOWNSTREAM)

def make_case(total,step,seed,mode):
    times=oracle.fixed_sample_times_v1(total,step);rng=random.Random(seed);points=[(rng.uniform(-20.,20.),rng.uniform(-20.,20.),rng.uniform(-20.,20.))]
    for index in range(1,len(times)):
        previous=points[-1]
        if mode=="vertical":delta=(0.,0.,rng.uniform(.5,4.))
        elif mode=="reverse":delta=((2. if index%3 else -3.),rng.uniform(-1.,1.),rng.uniform(-.5,.5))
        else:delta=(rng.uniform(.5,4.),rng.uniform(-2.,2.),rng.uniform(-2.,2.))
        points.append(previous if index%13==0 else tuple(previous[axis]+delta[axis] for axis in range(3)))
    return tuple(points),float(total),float(step)
def stage(case,valid=True):
    positions,total,step=case;set_(obj,UPSTREAM[0],bool(valid));set_(obj,UPSTREAM[1],[vector(value) for value in positions]);set_(obj,UPSTREAM[2],total);set_(obj,UPSTREAM[3],step)
def verify_compile(track,label):
    require(bool(get(obj,"CarrierFrameCompileValidV1")),label+":compile-valid");require(str(get(obj,"CarrierFrameFailureCodeV1"))=="",label+":failure")
    tangents=get(obj,"CarrierFrameCompiledTangentsV1");rotations=get(obj,"CarrierFrameCompiledQuatsV1");require(len(tangents)==len(track.tangents) and len(rotations)==len(track.rotations),label+":count")
    for index,(actual,wanted) in enumerate(zip(tangents,track.tangents)):require(vector_close(actual,wanted),f"{label}:tangent:{index}")
    for index,(actual,wanted) in enumerate(zip(rotations,track.rotations)):require(same_rotation(actual,wanted),f"{label}:quat:{index}")
    require(close(get(obj,"CarrierFrameCompiledTotalSecondsV1"),track.total_seconds),label+":total");require(close(get(obj,"CarrierFrameCompiledFixedStepSecondsV1"),track.fixed_step_seconds),label+":step")
def verify_evaluation(expected,label):
    require(bool(get(obj,"CarrierFrameResultValidV1"))==expected.valid,label+":valid");require(bool(get(obj,"CarrierFrameResultCompleteV1"))==expected.complete,label+":complete")
    require(int(get(obj,"CarrierFrameResultSegmentIndexV1"))==expected.segment_index,label+":segment");require(close(get(obj,"CarrierFrameResultAlphaV1"),expected.alpha),label+":alpha")
    require(same_rotation(get(obj,"CarrierFrameResultQuatV1"),expected.rotation),label+":quat")

rng=random.Random(0xC4A11E);cases=[make_case(1.,.25,1,"general"),make_case(.65,.2,2,"vertical"),make_case(1.05,.2,3,"reverse")]
for index in range(7):
    step=rng.choice((1/120,1/60,1/30,.1,.3));intervals=rng.randint(2,30);total=(intervals-1)*step+rng.uniform(.1*step,step);cases.append(make_case(total,step,0xEDD400+index,"general" if index%2 else "reverse"))
tracks=[oracle.compile_carrier_frame_transport_v1(*case) for case in cases];evaluations=0
try:
    for order_name,order in (("forward",range(len(cases))),("reverse",reversed(range(len(cases))))):
        for run_index,index in enumerate(order):
            case=cases[index];track=tracks[index];stage(case);upstream_before=snapshot(obj,UPSTREAM);outside_before=snapshot(obj,AUTHORSHIP+DOWNSTREAM);obj.call_method("CompileCarrierFrameTransportV1")
            require(snapshot(obj,UPSTREAM)==upstream_before,f"{order_name}:{run_index}:upstream-mutated");require(snapshot(obj,AUTHORSHIP+DOWNSTREAM)==outside_before,f"{order_name}:{run_index}:external-mutated");verify_compile(track,f"{order_name}:{run_index}")
            compiled_before=snapshot(obj,COMPILED);times=(-1.,0.,track.total_seconds,track.total_seconds+1.,math.nextafter(track.total_seconds,0.),track.total_seconds*.37)
            for time_index,elapsed in enumerate(times):
                set_(obj,"CarrierFrameInputElapsedSecondsV1",elapsed);obj.call_method("EvaluateCompiledCarrierFrameTransportV1");verify_evaluation(oracle.evaluate_carrier_frame_transport_v1(track,elapsed),f"{order_name}:{run_index}:time:{time_index}")
                require(snapshot(obj,COMPILED)==compiled_before,f"{order_name}:{run_index}:compiled-mutated");require(snapshot(obj,AUTHORSHIP+DOWNSTREAM)==outside_before,f"{order_name}:{run_index}:evaluation-external");evaluations+=1

    stage(cases[0],False);obj.call_method("CompileCarrierFrameTransportV1");require(not bool(get(obj,"CarrierFrameCompileValidV1")),"invalid-source:compile");require(not bool(get(obj,"CarrierFrameResultValidV1")),"invalid-source:result");require(len(get(obj,"CarrierFrameCompiledTangentsV1"))==0 and len(get(obj,"CarrierFrameCompiledQuatsV1"))==0,"invalid-source:publication")
    stage(cases[1]);obj.call_method("CompileCarrierFrameTransportV1");values=list(get(obj,"CarrierFrameCompiledQuatsV1"));values[-1]=unreal.Quat(float("nan"),0.,0.,1.);set_(obj,"CarrierFrameCompiledQuatsV1",values);set_(obj,"CarrierFrameInputElapsedSecondsV1",0.);corrupt=snapshot(obj,COMPILED);obj.call_method("EvaluateCompiledCarrierFrameTransportV1");require(not bool(get(obj,"CarrierFrameResultValidV1")),"tampered-track:accepted");require(snapshot(obj,COMPILED)==corrupt,"tampered-track:mutated")
    require(snapshot(obj,AUTHORSHIP+DOWNSTREAM)==external_before,"final external mutation")
    emit("FORWARD_CASES",len(cases));emit("REVERSE_CASES",len(cases));emit("EVALUATION_CASES",evaluations);emit("PARTIAL_TERMINAL_INTERVAL","PASS");emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("CARRIER_FRAME_INDEPENDENT",True);emit("EXTERNAL_STATE_PRESERVED",True);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,clone(value))
    restored=all(normalized(get(obj,name))==normalized(value) for name,value in saved.items());emit("DEFAULTS_RESTORED",restored);require(restored,"state restoration")
