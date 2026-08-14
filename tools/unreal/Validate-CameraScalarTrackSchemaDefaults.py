"""Read-only proof that camera scalar-track defaults survive Blueprint regeneration."""
from __future__ import annotations

import json
from pathlib import Path

import unreal


PREFIX="EDD_CAMERA_SCALAR_SCHEMA_DEFAULTS"
CLIENT="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/"tools/trajectory/camera_scalar_track_blueprint_schema.json").read_text(encoding="utf-8"))


def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def variants(name):
    snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
    for candidate in variants(name):
        try:return obj.get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError("missing property:"+name)
def expected(spec):
    if spec["container"]=="Array":return ()
    value=spec["default"]
    if spec["type"]=="String":return str(value)
    if spec["type"]=="Boolean":return bool(value)
    if spec["type"]=="Integer":return int(value)
    if spec["type"]=="Float":return float(value)
    raise RuntimeError("unsupported type:"+spec["type"])
def normalized(spec,value):return tuple(value) if spec["container"]=="Array" else value
def default_object():
    generated=unreal.EditorAssetLibrary.load_blueprint_class(CLIENT)
    if generated is None:raise RuntimeError(CLIENT+"_C")
    return unreal.get_default_object(generated)
def verify(stage):
    obj=default_object()
    for spec in SCHEMA["variables"]:
        actual=normalized(spec,get(obj,spec["name"]));wanted=expected(spec)
        if actual!=wanted:raise RuntimeError(f"{stage}:{spec['name']}:{actual}:{wanted}")
    emit(stage,len(SCHEMA["variables"]))


blueprint=unreal.EditorAssetLibrary.load_asset(CLIENT)
if blueprint is None:raise RuntimeError(CLIENT)
verify("BEFORE_COMPILE")
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
verify("AFTER_COMPILE")
emit("COMPLETE",True)
