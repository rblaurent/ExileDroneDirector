"""Create and verify camera channel-assembly variables/functions on Client Director."""
from __future__ import annotations
import json
from pathlib import Path
import unreal
PREFIX="EDD_CAMERA_CHANNEL_CONFIG";CLIENT="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector";ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/camera_channel_assembly_blueprint_schema.json").read_text(encoding="utf-8"))
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def variants(name):snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def cls():
 value=unreal.EditorAssetLibrary.load_blueprint_class(CLIENT)
 if value is None:raise RuntimeError(CLIENT)
 return value
def obj():return unreal.get_default_object(cls())
def get(name):
 for candidate in variants(name):
  try:return obj().get_editor_property(candidate)
  except Exception:pass
 raise RuntimeError("missing property:"+name)
def has(name):
 try:get(name);return True
 except RuntimeError:return False
def set_(name,value):
 for candidate in variants(name):
  try:obj().set_editor_property(candidate,value);return
  except Exception:pass
 raise RuntimeError("could not set:"+name)
blueprint=unreal.EditorAssetLibrary.load_asset(CLIENT)
if blueprint is None:raise RuntimeError(CLIENT)
types={"String":unreal.BlueprintEditorLibrary.get_basic_type_by_name("string"),"Float":unreal.BlueprintEditorLibrary.get_basic_type_by_name("real"),"Integer":unreal.BlueprintEditorLibrary.get_basic_type_by_name("int"),"Boolean":unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool")};created=set()
for spec in SCHEMA["variables"]:
 name=spec["name"]
 if has(name):emit("VARIABLE_ALREADY_PRESENT",name);continue
 pin=types[spec["type"]]
 if spec["container"]=="Array":pin=unreal.BlueprintEditorLibrary.get_array_type(pin)
 if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint,name,pin):raise RuntimeError("failed variable:"+name)
 created.add(name);unreal.BlueprintEditorLibrary.compile_blueprint(blueprint);emit("VARIABLE_CREATED",name)
for spec in SCHEMA["functions"]:
 name=spec["name"]
 if unreal.BlueprintEditorLibrary.find_graph(blueprint,unreal.Name(name)) is None:
  if unreal.BlueprintEditorLibrary.add_function_graph(blueprint,name) is None:raise RuntimeError("failed function:"+name)
  emit("FUNCTION_CREATED",name)
 else:emit("FUNCTION_ALREADY_PRESENT",name)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
for spec in SCHEMA["variables"]:
 name=spec["name"]
 if name not in created:continue
 if spec["container"]=="Array":
  if len(get(name))!=0:raise RuntimeError("new array not empty:"+name)
  continue
 value=spec["default"]
 if spec["type"]=="String":value=str(value)
 elif spec["type"]=="Boolean":value=bool(value)
 elif spec["type"]=="Integer":value=int(value)
 else:value=float(value)
 set_(name,value)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT,only_if_is_dirty=False):raise RuntimeError("save failed")
for spec in SCHEMA["variables"]:get(spec["name"]);emit("VARIABLE_VERIFIED",spec["name"])
for spec in SCHEMA["functions"]:
 if unreal.BlueprintEditorLibrary.find_graph(blueprint,unreal.Name(spec["name"])) is None:raise RuntimeError(spec["name"])
 emit("FUNCTION_VERIFIED",spec["name"])
emit("VARIABLE_COUNT",len(SCHEMA["variables"]));emit("FUNCTION_COUNT",len(SCHEMA["functions"]));emit("COMPLETE",True)

