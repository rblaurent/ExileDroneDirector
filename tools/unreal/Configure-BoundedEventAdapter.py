"""Create and verify the bounded event-adapter schema on Client Director."""

from __future__ import annotations

import json
from pathlib import Path
import unreal


PREFIX = "EDD_BOUNDED_EVENT_CONFIG"
CLIENT = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "tools/events/bounded_event_adapter_blueprint_schema.json").read_text(encoding="utf-8")
)


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
    raise RuntimeError("missing generated property " + name)


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
    raise RuntimeError("could not set " + name)


blueprint = unreal.EditorAssetLibrary.load_asset(CLIENT)
if blueprint is None:
    raise RuntimeError(CLIENT)
types = {
    "String": unreal.BlueprintEditorLibrary.get_basic_type_by_name("string"),
    "Real": unreal.BlueprintEditorLibrary.get_basic_type_by_name("real"),
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
    if spec["container"] == "Array":
        pin_type = unreal.BlueprintEditorLibrary.get_array_type(pin_type)
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, name, pin_type):
        raise RuntimeError("failed to add " + name)
    created.add(name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    emit("VARIABLE_CREATED", name)
for spec in SCHEMA["functions"]:
    name = spec["name"]
    if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(name)) is None:
        if unreal.BlueprintEditorLibrary.add_function_graph(blueprint, name) is None:
            raise RuntimeError("failed to add " + name)
        emit("FUNCTION_CREATED", name)
    else:
        emit("FUNCTION_ALREADY_PRESENT", name)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
for spec in SCHEMA["variables"]:
    name = spec["name"]
    if name not in created:
        current = get_property(name)
        emit(
            "EXISTING_DEFAULT_PRESERVED",
            f"{name}|COUNT|{len(current)}" if spec["container"] == "Array" else f"{name}|{current}",
        )
        continue
    if spec["container"] == "Array":
        if len(get_property(name)) != 0:
            raise RuntimeError("new array default is not empty: " + name)
        emit("ARRAY_DEFAULT_VERIFIED", name)
        continue
    value = spec["default"]
    if spec["type"] == "String":
        set_property(name, str(value))
    elif spec["type"] == "Boolean":
        set_property(name, bool(value))
    elif spec["type"] == "Integer":
        set_property(name, int(value))
    elif spec["type"] == "Real":
        set_property(name, float(value))
    else:
        raise RuntimeError("unsupported type " + spec["type"])
    emit("DEFAULT_VERIFIED", f"{name}|{get_property(name)}")
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT, only_if_is_dirty=False):
    raise RuntimeError("save failed")
for spec in SCHEMA["variables"]:
    get_property(spec["name"])
    emit("VARIABLE_VERIFIED", spec["name"])
for spec in SCHEMA["functions"]:
    if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(spec["name"])) is None:
        raise RuntimeError(spec["name"])
    emit("FUNCTION_VERIFIED", spec["name"])
emit("VARIABLE_COUNT", len(SCHEMA["variables"]))
emit("FUNCTION_COUNT", len(SCHEMA["functions"]))
emit("COMPLETE", True)
