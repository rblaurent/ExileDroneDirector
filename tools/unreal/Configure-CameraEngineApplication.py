"""Idempotently configure the native camera engine-application ABI."""

from __future__ import annotations

import json
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_ENGINE_CONFIG"
CLIENT = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_engine_application_blueprint_schema.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / SCHEMA["capabilityManifest"]["path"]).read_text(encoding="utf-8"))
STRUCT_CLASSES = {
    "/Script/CinematicCamera.CameraFilmbackSettings": unreal.CameraFilmbackSettings,
    "/Script/CinematicCamera.CameraFocusSettings": unreal.CameraFocusSettings,
    "/Script/Engine.PostProcessSettings": unreal.PostProcessSettings,
}


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
basic_types = {
    "String": unreal.BlueprintEditorLibrary.get_basic_type_by_name("string"),
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
    if spec["type"] == "Struct":
        struct_class = STRUCT_CLASSES.get(spec["struct"])
        if struct_class is None:
            raise RuntimeError(f"unsupported native struct {spec['struct']}")
        pin_type = unreal.BlueprintEditorLibrary.get_struct_type(struct_class.static_struct())
    else:
        pin_type = basic_types[spec["type"]]
    if spec["container"] == "Array":
        pin_type = unreal.BlueprintEditorLibrary.get_array_type(pin_type)
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
    if name not in created or spec["type"] == "Struct":
        get_property(name)
        continue
    if spec["container"] == "Array":
        if len(get_property(name)) != 0:
            raise RuntimeError(f"new array not empty: {name}")
        continue
    value = spec["default"]
    if spec["type"] == "String":
        set_property(name, str(value))
    elif spec["type"] == "Boolean":
        set_property(name, bool(value))
    elif spec["type"] == "Integer":
        set_property(name, int(value))
    elif spec["type"] == "Float":
        set_property(name, float(value))

# Capability identity is generated evidence, not user-authored state. Always
# converge it to the reviewed manifest, including after a partial prior run.
set_property("CameraApplyCapabilityEngineVersionV1", MANIFEST["engineVersion"])
set_property("CameraApplyCapabilityManifestIdV1", MANIFEST["manifestId"])
set_property("CameraApplyCapabilityAvailableV1", list(MANIFEST["available"]))
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)

if str(get_property("CameraApplyCapabilityEngineVersionV1")) != MANIFEST["engineVersion"]:
    raise RuntimeError("engine version default mismatch")
if str(get_property("CameraApplyCapabilityManifestIdV1")) != MANIFEST["manifestId"]:
    raise RuntimeError("manifest id default mismatch")
if tuple(bool(value) for value in get_property("CameraApplyCapabilityAvailableV1")) != tuple(MANIFEST["available"]):
    raise RuntimeError("capability availability mismatch")
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
