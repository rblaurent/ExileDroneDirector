"""Execute compiled adaptive arc initialization against its exact transaction contract."""

from __future__ import annotations

import random
import unreal


PREFIX = "EDD_ADAPTIVE_ARC_INITIALIZATION_RUNTIME"
CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ARRAYS = (
    "TrajectoryArcBuildWorkU0V1", "TrajectoryArcBuildWorkU1V1",
    "TrajectoryArcBuildWorkP0V1", "TrajectoryArcBuildWorkP1V1",
    "TrajectoryArcBuildWorkDepthV1", "TrajectoryArcBuildCandidateUsV1",
    "TrajectoryArcBuildCandidatePositionsV1", "TrajectoryArcBuildCandidateDistancesV1",
)
SCALARS = ("TrajectoryArcBuildOperationCountV1", "TrajectoryArcBuildCandidateLengthV1", "TrajectoryArcBuildStageValidV1")
INPUTS = ("TrajectoryArcBuildInputStartPositionV1", "TrajectoryArcBuildInputEndPositionV1")


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def names(value):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in value).lstrip("_"); return value, unreal.Name(value), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in names(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(name)
def set_(obj, name, value):
    for candidate in names(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(name)
def vector(value): return unreal.Vector(*(float(item) for item in value))
def tuple3(value): return float(value.x), float(value.y), float(value.z)


generated = unreal.load_class(None, CLASS); require(generated is not None, "class missing"); component = unreal.get_default_object(generated)
touched = (*ARRAYS, *SCALARS, *INPUTS); saved = {name: get(component, name) for name in touched}
try:
    rng = random.Random(0xEDD068); valid = 0
    for index in range(64):
        start = tuple(rng.uniform(-1e6, 1e6) for _ in range(3)); end = tuple(rng.uniform(-1e6, 1e6) for _ in range(3))
        set_(component, INPUTS[0], vector(start)); set_(component, INPUTS[1], vector(end)); set_(component, "TrajectoryArcBuildStageValidV1", True)
        for name in ARRAYS:
            if "P0" in name or "P1" in name or "Positions" in name: set_(component, name, [vector((7, 8, 9)), vector((-1, -2, -3))])
            elif "Depth" in name: set_(component, name, [7, 8])
            else: set_(component, name, [7.0, 8.0])
        set_(component, "TrajectoryArcBuildOperationCountV1", 77); set_(component, "TrajectoryArcBuildCandidateLengthV1", 99.0)
        component.call_method("InitializeAdaptiveArcBuildV1")
        require(list(get(component, "TrajectoryArcBuildWorkU0V1")) == [0.0], f"u0:{index}")
        require(list(get(component, "TrajectoryArcBuildWorkU1V1")) == [1.0], f"u1:{index}")
        require([tuple3(item) for item in get(component, "TrajectoryArcBuildWorkP0V1")] == [start], f"p0:{index}")
        require([tuple3(item) for item in get(component, "TrajectoryArcBuildWorkP1V1")] == [end], f"p1:{index}")
        require(list(get(component, "TrajectoryArcBuildWorkDepthV1")) == [0], f"depth:{index}")
        require(list(get(component, "TrajectoryArcBuildCandidateUsV1")) == [0.0], f"candidate-u:{index}")
        require([tuple3(item) for item in get(component, "TrajectoryArcBuildCandidatePositionsV1")] == [start], f"candidate-position:{index}")
        require(list(get(component, "TrajectoryArcBuildCandidateDistancesV1")) == [0.0], f"candidate-distance:{index}")
        require(int(get(component, "TrajectoryArcBuildOperationCountV1")) == 0, f"operations:{index}")
        require(float(get(component, "TrajectoryArcBuildCandidateLengthV1")) == 0.0, f"length:{index}")
        require(bool(get(component, "TrajectoryArcBuildStageValidV1")), f"validity:{index}"); valid += 1
    set_(component, INPUTS[0], vector((1, 2, 3))); set_(component, INPUTS[1], vector((4, 5, 6))); set_(component, "TrajectoryArcBuildStageValidV1", False)
    for name in ARRAYS:
        if "P0" in name or "P1" in name or "Positions" in name: set_(component, name, [vector((9, 9, 9))])
        elif "Depth" in name: set_(component, name, [9])
        else: set_(component, name, [9.0])
    set_(component, "TrajectoryArcBuildOperationCountV1", 9); set_(component, "TrajectoryArcBuildCandidateLengthV1", 9.0)
    component.call_method("InitializeAdaptiveArcBuildV1")
    require(all(len(get(component, name)) == 0 for name in ARRAYS), "invalid prior stage retained arrays")
    require(int(get(component, "TrajectoryArcBuildOperationCountV1")) == 0, "invalid prior stage retained operations")
    require(float(get(component, "TrajectoryArcBuildCandidateLengthV1")) == 0.0, "invalid prior stage retained length")
    require(get(component, "TrajectoryArcBuildStageValidV1") is False, "invalid prior stage healed")
    emit("VALID_CASES", valid); emit("INVALID_PRIOR_STAGE_CASES", 1); emit("COMPLETE", "PASS")
finally:
    for name, value in saved.items(): set_(component, name, value)
    emit("STATE_RESTORED", True)
