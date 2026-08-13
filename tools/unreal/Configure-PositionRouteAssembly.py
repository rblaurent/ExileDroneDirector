"""Create and verify the typed multi-segment position-route transaction seam."""
from __future__ import annotations
import json
from pathlib import Path
import unreal

PREFIX="EDD_POSITION_ROUTE_CONFIG";CLIENT="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector";ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/"tools/trajectory/position_route_blueprint_schema.json").read_text(encoding="utf-8"))
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def variants(name):
    snake="".join(("_"+c.lower()) if c.isupper() else c for c in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def cls():
    value=unreal.EditorAssetLibrary.load_blueprint_class(CLIENT)
    if value is None:raise RuntimeError(CLIENT)
    return value
def obj():return unreal.get_default_object(cls())
def get(name):
    for candidate in variants(name):
        try:return obj().get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError(f"missing generated property {name}")
def has(name):
    try:get(name);return True
    except RuntimeError:return False
def set_(name,value):
    for candidate in variants(name):
        try:obj().set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError(f"could not set {name}")

blueprint=unreal.EditorAssetLibrary.load_asset(CLIENT)
if blueprint is None:raise RuntimeError(CLIENT)
vector=unreal.load_object(None,"/Script/CoreUObject.Vector")
if vector is None:raise RuntimeError("native Vector unavailable")
types={"Vector":unreal.BlueprintEditorLibrary.get_struct_type(vector),"Float":unreal.BlueprintEditorLibrary.get_basic_type_by_name("real"),"Integer":unreal.BlueprintEditorLibrary.get_basic_type_by_name("int"),"Boolean":unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool"),"String":unreal.BlueprintEditorLibrary.get_basic_type_by_name("string")}
created_variables=set()
for spec in SCHEMA["variables"]:
    name=spec["name"]
    if has(name):emit("VARIABLE_ALREADY_PRESENT",name);continue
    pin_type=types[spec["type"]]
    if spec["container"]=="Array":pin_type=unreal.BlueprintEditorLibrary.get_array_type(pin_type)
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint,name,pin_type):raise RuntimeError(f"failed to add {name}")
    created_variables.add(name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint);emit("VARIABLE_CREATED",name)
for spec in SCHEMA["functions"]:
    name=spec["name"]
    if unreal.BlueprintEditorLibrary.find_graph(blueprint,unreal.Name(name)) is None:
        if unreal.BlueprintEditorLibrary.add_function_graph(blueprint,name) is None:raise RuntimeError(f"failed to add {name}")
        emit("FUNCTION_CREATED",name)
    else:emit("FUNCTION_ALREADY_PRESENT",name)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
for spec in SCHEMA["variables"]:
    name=spec["name"]
    if name not in created_variables:
        emit("EXISTING_DEFAULT_PRESERVED",f"{name}|{get(name)}")
        continue
    if spec["container"]=="Array":
        if len(get(name))!=0:raise RuntimeError(f"array default not empty: {name}")
        emit("ARRAY_DEFAULT_VERIFIED",name);continue
    default=spec.get("default")
    if spec["type"]=="Vector":set_(name,unreal.Vector(*(float(x) for x in default)))
    elif spec["type"]=="Boolean":set_(name,bool(default))
    elif spec["type"]=="Integer":set_(name,int(default))
    elif spec["type"]=="Float":set_(name,float(default))
    elif spec["type"]=="String":set_(name,str(default))
    emit("DEFAULT_VERIFIED",f"{name}|{get(name)}")
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT,only_if_is_dirty=False):raise RuntimeError("save failed")
for spec in SCHEMA["functions"]:
    if unreal.BlueprintEditorLibrary.find_graph(blueprint,unreal.Name(spec["name"])) is None:raise RuntimeError(spec["name"])
    emit("FUNCTION_VERIFIED",spec["name"])
emit("COMPLETE",True)
