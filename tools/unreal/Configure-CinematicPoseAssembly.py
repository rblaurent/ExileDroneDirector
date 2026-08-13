"""Create and verify the atomic cinematic-pose Blueprint transaction seam."""

from __future__ import annotations

import json
from pathlib import Path
import unreal


PREFIX = "EDD_CINEMATIC_POSE_CONFIG"
CLIENT = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/cinematic_pose_blueprint_schema.json").read_text(encoding="utf-8"))


def emit(label, value):
    unreal.log(f"{PREFIX}|{label}|{value}")


def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def blueprint_class():
    value = unreal.EditorAssetLibrary.load_blueprint_class(CLIENT)
    if value is None:
        raise RuntimeError(CLIENT)
    return value


def default_object():
    return unreal.get_default_object(blueprint_class())


def get_property(name):
    for candidate in variants(name):
        try:
            return default_object().get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError(f"missing generated property {name}")


def has_property(name):
    try:
        get_property(name)
        return True
    except RuntimeError:
        return False


def set_property(name, value):
    for candidate in variants(name):
        try:
            default_object().set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(f"could not set {name}")


blueprint = unreal.EditorAssetLibrary.load_asset(CLIENT)
if blueprint is None:
    raise RuntimeError(CLIENT)
vector = unreal.load_object(None, "/Script/CoreUObject.Vector")
quaternion = unreal.load_object(None, "/Script/CoreUObject.Quat")
if vector is None or quaternion is None:
    raise RuntimeError("native Vector/Quat unavailable")
types = {
    "Vector": unreal.BlueprintEditorLibrary.get_struct_type(vector),
    "Quat": unreal.BlueprintEditorLibrary.get_struct_type(quaternion),
    "Float": unreal.BlueprintEditorLibrary.get_basic_type_by_name("real"),
    "Integer": unreal.BlueprintEditorLibrary.get_basic_type_by_name("int"),
    "Boolean": unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool"),
}
created = set()
for spec in SCHEMA["variables"]:
    name = spec["name"]
    if has_property(name):
        emit("VARIABLE_ALREADY_PRESENT", name)
        continue
    pin_type = types[spec["type"]]
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, name, pin_type):
        raise RuntimeError(f"failed to add {name}")
    created.add(name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    emit("VARIABLE_CREATED", name)
for spec in SCHEMA["functions"]:
    name = spec["name"]
    if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(name)) is None:
        if unreal.BlueprintEditorLibrary.add_function_graph(blueprint, name) is None:
            raise RuntimeError(f"failed to add {name}")
        emit("FUNCTION_CREATED", name)
    else:
        emit("FUNCTION_ALREADY_PRESENT", name)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
for spec in SCHEMA["variables"]:
    name = spec["name"]
    if name not in created:
        emit("EXISTING_DEFAULT_PRESERVED", f"{name}|{get_property(name)}")
        continue
    default = spec["default"]
    if spec["type"] == "Vector":
        set_property(name, unreal.Vector(*(float(value) for value in default)))
    elif spec["type"] == "Quat":
        set_property(name, unreal.Quat(*(float(value) for value in default)))
    elif spec["type"] == "Boolean":
        set_property(name, bool(default))
    elif spec["type"] == "Integer":
        set_property(name, int(default))
    elif spec["type"] == "Float":
        set_property(name, float(default))
    emit("DEFAULT_VERIFIED", f"{name}|{get_property(name)}")
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT, only_if_is_dirty=False):
    raise RuntimeError("save failed")
for spec in SCHEMA["functions"]:
    if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(spec["name"])) is None:
        raise RuntimeError(spec["name"])
    emit("FUNCTION_VERIFIED", spec["name"])
emit("COMPLETE", True)
