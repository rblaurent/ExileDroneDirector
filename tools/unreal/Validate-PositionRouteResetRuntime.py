"""Execute the compiled position-route reset against poisoned state."""
from __future__ import annotations
import json
from pathlib import Path
import unreal

PREFIX="EDD_POSITION_ROUTE_RESET_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/"tools/trajectory/position_route_blueprint_schema.json").read_text(encoding="utf-8"))
INPUTS=tuple(v for v in SCHEMA["variables"] if v["role"] in ("input","evaluationInput"));OUTPUTS=tuple(v for v in SCHEMA["variables"] if v["role"] in ("candidate","result","evaluationResult"))
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
def comparable(value):
    if isinstance(value,unreal.Vector):return float(value.x),float(value.y),float(value.z)
    if isinstance(value,(list,tuple)):return tuple(comparable(item) for item in value)
    return value
def value(spec,seed):
    kind=spec["type"]
    if spec["container"]=="Array":return [value({**spec,"container":"None"},seed),value({**spec,"container":"None"},seed+1)]
    if kind=="Vector":return vector((seed+0.25,seed+0.5,seed+0.75))
    if kind=="Float":return float(seed)+0.375
    if kind=="Integer":return int(seed)+7
    if kind=="Boolean":return bool(seed%2)
    if kind=="String":return f"route-{seed}"
    raise RuntimeError(kind)
def expected(spec):
    default=spec.get("default")
    if spec["container"]=="Array":return ()
    if spec["type"]=="Vector":return tuple(float(x) for x in default)
    return default

generated=unreal.load_class(None,CLASS);require(generated is not None,"class");obj=unreal.get_default_object(generated);all_specs=INPUTS+OUTPUTS;saved={spec["name"]:get(obj,spec["name"]) for spec in all_specs}
try:
    authored={}
    for index,spec in enumerate(INPUTS):
        authored[spec["name"]]=value(spec,100+index*3);set_(obj,spec["name"],authored[spec["name"]])
    for index,spec in enumerate(OUTPUTS):set_(obj,spec["name"],value(spec,10+index*3))
    for repetition in range(2):
        obj.call_method("ResetPositionRouteCandidateV1")
        for spec in OUTPUTS:require(comparable(get(obj,spec["name"]))==expected(spec),f"output:{repetition}:{spec['name']}:{comparable(get(obj,spec['name']))}")
        for spec in INPUTS:require(comparable(get(obj,spec["name"]))==comparable(authored[spec["name"]]),f"input-mutated:{repetition}:{spec['name']}")
    emit("CLEARED_ARRAYS",sum(spec["container"]=="Array" for spec in OUTPUTS));emit("RESET_SCALARS",sum(spec["container"]=="None" for spec in OUTPUTS));emit("PRESERVED_INPUTS",len(INPUTS));emit("IDEMPOTENT_REPETITIONS",2);emit("COMPLETE","PASS")
finally:
    for name,old in saved.items():set_(obj,name,old)
    emit("STATE_RESTORED",True)
