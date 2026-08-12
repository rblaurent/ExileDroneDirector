"""Execute the compiled vector wrapper and nested scalar kernel."""

from __future__ import annotations

import math
import random
import unreal


PREFIX = "EDD_TRAJECTORY_VECTOR_RUNTIME"
CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
VECTOR_INPUTS = (
    "TrajectoryInputStartPositionVectorV1",
    "TrajectoryInputStartVelocityUVectorV1",
    "TrajectoryInputStartAccelerationUVectorV1",
    "TrajectoryInputEndPositionVectorV1",
    "TrajectoryInputEndVelocityUVectorV1",
    "TrajectoryInputEndAccelerationUVectorV1",
)
VECTOR_OUTPUTS = (
    "TrajectoryResultPositionVectorV1",
    "TrajectoryResultDerivativeUVectorV1",
    "TrajectoryResultSecondDerivativeUVectorV1",
)
SCALAR_NAMES = (
    "TrajectoryInputAlphaV1", "TrajectoryInputStartValueV1",
    "TrajectoryInputStartVelocityUV1", "TrajectoryInputStartAccelerationUV1",
    "TrajectoryInputEndValueV1", "TrajectoryInputEndVelocityUV1",
    "TrajectoryInputEndAccelerationUV1", "TrajectoryResultValueV1",
    "TrajectoryResultDerivativeUV1", "TrajectoryResultSecondDerivativeUV1",
    "TrajectoryResultValidV1",
)
SCRATCH = tuple(
    f"TrajectoryVectorScratch{channel}{axis}V1"
    for axis in "XYZ"
    for channel in ("Value", "Derivative", "SecondDerivative")
)
TOUCHED = (*VECTOR_INPUTS, *VECTOR_OUTPUTS, "TrajectoryResultVectorValidV1", *SCALAR_NAMES, *SCRATCH)


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def candidates(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def get_prop(obj, name):
    for candidate in candidates(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"could not read {name}")


def set_prop(obj, name, value):
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception: pass
    raise RuntimeError(f"could not set {name}")


def vector(value): return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))
def tuple3(value): return (float(value.x), float(value.y), float(value.z))


def quintic(values, alpha):
    p0,v0,a0,p1,v1,a1 = values
    x=max(0.0,min(1.0,float(alpha))); x2=x*x; x3=x2*x; x4=x3*x; x5=x4*x
    weights=(
        (1-10*x3+15*x4-6*x5,x-6*x3+8*x4-3*x5,.5*(x2-3*x3+3*x4-x5),10*x3-15*x4+6*x5,-4*x3+7*x4-3*x5,.5*(x3-2*x4+x5)),
        (-30*x2+60*x3-30*x4,1-18*x2+32*x3-15*x4,x-4.5*x2+6*x3-2.5*x4,30*x2-60*x3+30*x4,-12*x2+28*x3-15*x4,1.5*x2-4*x3+2.5*x4),
        (-60*x+180*x2-120*x3,-36*x+96*x2-60*x3,1-9*x+18*x2-10*x3,60*x-180*x2+120*x3,-24*x+84*x2-60*x3,3*x-12*x2+10*x3),
    )
    return tuple(sum(a*b for a,b in zip(row,values)) for row in weights)


generated = unreal.load_class(None, CLASS_PATH)
require(generated is not None, "generated class missing")
component = unreal.get_default_object(generated)
saved = {name: get_prop(component, name) for name in TOUCHED}
try:
    fixtures = [
        (((0,0,0),(0,0,0),(0,0,0),(10,20,30),(0,0,0),(0,0,0)),-2.0),
        (((0,1,2),(3,4,5),(6,7,8),(9,10,11),(12,13,14),(15,16,17)),0.5),
        (((0,1,2),(3,4,5),(6,7,8),(9,10,11),(12,13,14),(15,16,17)),2.0),
    ]
    rng=random.Random(0xEDD056)
    fixtures += [(tuple(tuple(rng.uniform(-100,100) for _ in range(3)) for _ in range(6)),rng.uniform(-1,2)) for _ in range(64)]
    for vectors,alpha in fixtures:
        for name,value in zip(VECTOR_INPUTS,vectors): set_prop(component,name,vector(value))
        set_prop(component,"TrajectoryInputAlphaV1",alpha)
        for name in VECTOR_OUTPUTS: set_prop(component,name,vector((123,456,789)))
        set_prop(component,"TrajectoryResultVectorValidV1",True)
        component.call_method("EvaluateQuinticVectorV1")
        require(bool(get_prop(component,"TrajectoryResultVectorValidV1")),"valid fixture rejected")
        axes=[quintic(tuple(item[index] for item in vectors),alpha) for index in range(3)]
        expected=tuple(tuple(axis[channel] for axis in axes) for channel in range(3))
        for name,wanted in zip(VECTOR_OUTPUTS,expected):
            actual=tuple3(get_prop(component,name))
            require(all(abs(a-b)<=2e-9*max(1,abs(b)) for a,b in zip(actual,wanted)),f"{name}:{actual}!={wanted}")
    emit("VALID_CASES",len(fixtures))
    invalid=0
    sanitized=0
    for nonfinite in (math.nan,math.inf,-math.inf):
        for bad in range(19):
            flat=[1.0]*19; flat[bad]=nonfinite
            set_prop(component,"TrajectoryInputAlphaV1",flat[0])
            vectors=tuple(tuple(flat[1+i*3+j] for j in range(3)) for i in range(6))
            for name,value in zip(VECTOR_INPUTS,vectors): set_prop(component,name,vector(value))
            reflected_vectors = tuple(tuple3(get_prop(component, name)) for name in VECTOR_INPUTS)
            reflected_flat = (float(get_prop(component, "TrajectoryInputAlphaV1")),) + tuple(
                component_value
                for reflected_vector in reflected_vectors
                for component_value in reflected_vector
            )
            for name in VECTOR_OUTPUTS: set_prop(component,name,vector((123,456,789)))
            set_prop(component,"TrajectoryResultVectorValidV1",True)
            component.call_method("EvaluateQuinticVectorV1")
            if math.isfinite(reflected_flat[bad]):
                require(bad > 0, f"scalar nonfinite was unexpectedly sanitized:{bad}/{nonfinite}")
                require(bool(get_prop(component,"TrajectoryResultVectorValidV1")),f"sanitized valid vector rejected:{bad}/{nonfinite}")
                sanitized += 1
                continue
            if bool(get_prop(component,"TrajectoryResultVectorValidV1")):
                reflected_scalar = tuple(get_prop(component, name) for name in SCALAR_NAMES)
                raise RuntimeError(
                    f"{PREFIX}|FAIL|invalid accepted:{bad}/{nonfinite}|"
                    f"vectors={reflected_vectors}|scalar={reflected_scalar}"
                )
            require(all(tuple3(get_prop(component,name))==(0.0,0.0,0.0) for name in VECTOR_OUTPUTS),"invalid leaked stale vector")
            invalid += 1
    emit("INVALID_CASES",invalid)
    emit("REFLECTION_SANITIZED_VECTOR_CASES",sanitized)
    emit("COMPLETE","PASS")
finally:
    for name,value in saved.items(): set_prop(component,name,value)
    emit("STATE_RESTORED",True)
