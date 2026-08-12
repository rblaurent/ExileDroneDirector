"""Execute the compiled orientation-track input boundary and edge cases."""

from __future__ import annotations

import math
import unreal


PREFIX="EDD_ORIENTATION_TRACK_VALIDATION_RUNTIME"
CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
QUATS="OrientationTrackInputWaypointQuatsV1";DURATIONS="OrientationTrackInputDurationsV1";VALID="OrientationTrackStageValidV1"


def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def names(value):
    snake="".join(("_"+c.lower()) if c.isupper() else c for c in value).lstrip("_");return value,unreal.Name(value),snake,unreal.Name(snake)
def get(obj,name):
    for candidate in names(name):
        try:return obj.get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError(name)
def set_(obj,name,value):
    for candidate in names(name):
        try:obj.set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError(name)
def quat(value):return unreal.Quat(*(float(x) for x in value))


generated=unreal.load_class(None,CLASS);require(generated is not None,"class missing");component=unreal.get_default_object(generated)
saved={name:get(component,name) for name in (QUATS,DURATIONS,VALID)}
identity=(0.0,0.0,0.0,1.0)


def run(quats,durations,expected,label):
    set_(component,QUATS,[quat(value) for value in quats]);set_(component,DURATIONS,[float(value) for value in durations]);set_(component,VALID,not expected)
    reflected_durations=[float(value) for value in get(component,DURATIONS)]
    component.call_method("ValidateOrientationTrackInputsV1")
    actual=bool(get(component,VALID));require(actual is expected,f"{label}:{actual}!={expected}:{reflected_durations}")


try:
    valid=invalid=0
    for quats,durations in (
        ((identity,identity),(1.0,)),
        (((0,0,0,2),identity),(0.001,)),
        ((identity,(0,0,1,1),identity),(0.5,7.25)),
        (tuple(identity for _ in range(512)),tuple(1.0 for _ in range(511))),
    ):
        run(quats,durations,True,f"valid-{valid}");valid+=1
    invalid_cases=(
        ((),()),((identity,),()),((identity,identity),()),((identity,identity),(1.0,2.0)),
        ((identity,(0,0,0,0)),(1.0,)),((identity,(0,0,0,1e-20)),(1.0,)),
        ((identity,identity),(0.0,)),((identity,identity),(-1.0,)),
        ((identity,identity),(math.nan,)),((identity,identity),(math.inf,)),
        (tuple(identity for _ in range(513)),tuple(1.0 for _ in range(512))),
    )
    for quats,durations in invalid_cases:
        run(quats,durations,False,f"invalid-{invalid}");invalid+=1
    # A prior invalid element must remain rejected even when the final element is valid.
    run((identity,(0,0,0,0),identity),(1.0,1.0),False,"monotonic-quat-failure");invalid+=1
    run((identity,identity,identity),(-1.0,1.0),False,"monotonic-duration-failure");invalid+=1
    emit("VALID_CASES",valid);emit("INVALID_CASES",invalid);emit("COMPLETE","PASS")
finally:
    for name,value in saved.items():set_(component,name,value)
    emit("STATE_RESTORED",True)
