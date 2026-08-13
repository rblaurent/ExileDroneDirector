"""Execute the live camera scalar-track compiler/evaluator against its oracle."""
from __future__ import annotations

import importlib
import json
import math
import random
import sys
from pathlib import Path

import unreal


PREFIX="EDD_CAMERA_SCALAR_RUNTIME"
CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/"tools/trajectory/camera_scalar_track_blueprint_schema.json").read_text(encoding="utf-8"))
INPUTS=tuple(spec["name"] for spec in SCHEMA["variables"] if spec["role"] in ("input","query"))


def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
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
def clone(value):return list(value) if isinstance(value,(list,tuple)) else value
def normalized(value):return tuple(value) if isinstance(value,(list,tuple)) else value
def close(left,right,tolerance=3.0e-5):return abs(float(left)-float(right))<=tolerance*max(1.0,abs(float(left)),abs(float(right)))


sys.path.insert(0,str(ROOT/"tools/trajectory"));import camera_scalar_track_reference as oracle
oracle=importlib.reload(oracle);cls=unreal.load_class(None,CLASS);require(cls is not None,"class");obj=unreal.get_default_object(cls)
saved={spec["name"]:clone(get(obj,spec["name"])) for spec in SCHEMA["variables"]}


def stage(track_keys,duration,domain,minimum=None,maximum=None,clamp=False):
    set_(obj,"CameraScalarTrackInputDurationV1",duration);set_(obj,"CameraScalarTrackInputKeyTimesV1",[key.time_seconds for key in track_keys]);set_(obj,"CameraScalarTrackInputKeyValuesV1",[key.value for key in track_keys]);set_(obj,"CameraScalarTrackInputInterpolationModesV1",[key.interpolation_out for key in track_keys[:-1]]);set_(obj,"CameraScalarTrackInputArriveTangentsV1",[key.arrive_tangent for key in track_keys]);set_(obj,"CameraScalarTrackInputLeaveTangentsV1",[key.leave_tangent for key in track_keys]);set_(obj,"CameraScalarTrackInputDomainV1",domain);set_(obj,"CameraScalarTrackInputHasMinimumV1",minimum is not None);set_(obj,"CameraScalarTrackInputMinimumV1",0.0 if minimum is None else minimum);set_(obj,"CameraScalarTrackInputHasMaximumV1",maximum is not None);set_(obj,"CameraScalarTrackInputMaximumV1",0.0 if maximum is None else maximum);set_(obj,"CameraScalarTrackInputClampOutputV1",clamp)


def input_snapshot():return tuple(normalized(get(obj,name)) for name in INPUTS)


def evaluate(track,query,label):
    before=input_snapshot();set_(obj,"CameraScalarTrackQueryTimeV1",query);before=input_snapshot();obj.call_method("EvaluateCameraScalarTrackV1");require(input_snapshot()==before,label+":inputs-mutated");wanted=oracle.evaluate_camera_scalar_track(track,query)
    require(bool(get(obj,"CameraScalarTrackResultValidV1")),label+":valid");require(close(get(obj,"CameraScalarTrackResultValueV1"),wanted.value),label+":value");require(close(get(obj,"CameraScalarTrackResultVelocityV1"),wanted.velocity),label+":velocity");require(close(get(obj,"CameraScalarTrackResultAccelerationV1"),wanted.acceleration),label+":acceleration");require(int(get(obj,"CameraScalarTrackResultSegmentIndexV1"))==wanted.segment_index,label+":segment");require(close(get(obj,"CameraScalarTrackResultLocalAlphaV1"),wanted.local_alpha),label+":alpha");require(bool(get(obj,"CameraScalarTrackResultCompleteV1"))==wanted.complete,label+":complete)")


try:
    rng=random.Random(0xEDD5CA);cases=[]
    for index,(mode,domain) in enumerate((mode,domain) for mode in oracle.MODES for domain in oracle.DOMAINS):
        duration=0.75+index*0.125;left=100.0+index*7.0 if domain=="reciprocal" else -10.0+index;right=250.0+index*9.0 if domain=="reciprocal" else 20.0-index
        leave=rng.uniform(-.002,.002) if mode=="hermite" and domain=="reciprocal" else (rng.uniform(-5,5) if mode=="hermite" else 0.0);arrive=rng.uniform(-.002,.002) if mode=="hermite" and domain=="reciprocal" else (rng.uniform(-5,5) if mode=="hermite" else 0.0)
        keys=(oracle.CameraScalarKey(0.0,left,mode,0.0,leave),oracle.CameraScalarKey(duration,right,"cinematic",arrive,0.0));track=oracle.compile_camera_scalar_track(keys,duration,domain=domain);cases.append((keys,track))
    for order_name,order in (("forward",cases),("reverse",list(reversed(cases)))):
        for case_index,(keys,track) in enumerate(order):
            stage(keys,track.duration_seconds,track.domain);before=input_snapshot();obj.call_method("CompileCameraScalarTrackV1");require(input_snapshot()==before,f"{order_name}:{case_index}:compile-mutated-inputs");require(bool(get(obj,"CameraScalarTrackCompileValidV1")),f"{order_name}:{case_index}:compile")
            for query_index,query in enumerate((-1.0,0.0,track.duration_seconds*.2,track.duration_seconds*.5,track.duration_seconds,track.duration_seconds+1.0)):evaluate(track,query,f"{order_name}:{case_index}:{query_index}")
    constant_keys=(oracle.CameraScalarKey(0.0,35.0),);constant=oracle.compile_camera_scalar_track(constant_keys,0.0);stage(constant_keys,0.0,"linear");obj.call_method("CompileCameraScalarTrackV1");evaluate(constant,-10.0,"constant-negative")
    invalid=(
        ((oracle.CameraScalarKey(0.0,1.0),),0.0,"linear",[0.0,1.0]),
        ((oracle.CameraScalarKey(0.0,1e-320),),0.0,"reciprocal",None),
        ((oracle.CameraScalarKey(0.0,1.0,"bad"),oracle.CameraScalarKey(1.0,2.0)),1.0,"linear",None),
    )
    for index,(keys,duration,domain,override_times) in enumerate(invalid):
        stage(keys,duration,domain)
        if override_times is not None:set_(obj,"CameraScalarTrackInputKeyTimesV1",override_times)
        set_(obj,"CameraScalarTrackCompileValidV1",True);set_(obj,"CameraScalarTrackResultValidV1",True);obj.call_method("CompileCameraScalarTrackV1");require(not bool(get(obj,"CameraScalarTrackCompileValidV1")),f"invalid:{index}:compile");require(not bool(get(obj,"CameraScalarTrackResultValidV1")),f"invalid:{index}:result")
    stage(constant_keys,0.0,"linear");obj.call_method("CompileCameraScalarTrackV1")
    for query in (math.nan,math.inf,-math.inf):
        set_(obj,"CameraScalarTrackQueryTimeV1",query);set_(obj,"CameraScalarTrackResultValidV1",True);obj.call_method("EvaluateCameraScalarTrackV1");require(not bool(get(obj,"CameraScalarTrackResultValidV1")),f"nonfinite-query:{query}")
    set_(obj,"CameraScalarTrackScratchDomainValueV1",0.0);set_(obj,"CameraScalarTrackScratchDomainVelocityV1",1.0);set_(obj,"CameraScalarTrackScratchDomainAccelerationV1",1.0);set_(obj,"CameraScalarTrackScratchValidV1",True);set_(obj,"CameraScalarTrackInputDomainV1","reciprocal");set_(obj,"CameraScalarTrackResultValidV1",True);obj.call_method("PublishCameraScalarTrackSampleV1");require(not bool(get(obj,"CameraScalarTrackResultValidV1")),"direct-reciprocal-boundary")
    emit("FORWARD_TRACKS",len(cases));emit("REVERSE_TRACKS",len(cases));emit("QUERY_EVALUATIONS",len(cases)*12+1);emit("INVALID_FAMILIES",7);emit("RESULT","PASS")
finally:
    for name,value in saved.items():set_(obj,name,value)
    emit("DEFAULTS_RESTORED",all(normalized(get(obj,name))==normalized(value) for name,value in saved.items()))
