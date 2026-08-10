"""Create and verify the staged-input server Flypath repository actor seam."""

from __future__ import annotations

import json
from pathlib import Path
import unreal


PREFIX = "EDD_REPOSITORY_SERVICE_CONFIG"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "repository" / "blueprint_repository_service_schema.json"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def snake_name(value: str) -> str:
    return "".join(("_" + character.lower()) if character.isupper() else character for character in value).lstrip("_")


def candidates(name: str) -> tuple[object, ...]:
    snake = snake_name(name)
    return name, unreal.Name(name), snake, unreal.Name(snake)


def generated_class(asset_path: str):
    result = unreal.EditorAssetLibrary.load_blueprint_class(asset_path)
    if result is None:
        raise RuntimeError(f"Generated class missing: {asset_path}")
    return result


def generated_value(asset_path: str, name: str):
    default = unreal.get_default_object(generated_class(asset_path))
    last_error = None
    for candidate in candidates(name):
        try:
            return default.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {name}: {last_error}")


def set_generated_value(asset_path: str, name: str, value) -> None:
    default = unreal.get_default_object(generated_class(asset_path))
    last_error = None
    for candidate in candidates(name):
        try:
            default.set_editor_property(candidate, value)
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not set {name}: {last_error}")


schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
asset_path = schema["virtualPath"]
asset = unreal.EditorAssetLibrary.load_asset(asset_path) if unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
if asset is None:
    package_path, asset_name = asset_path.rsplit("/", 1)
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        if not unreal.EditorAssetLibrary.make_directory(package_path):
            raise RuntimeError(f"Could not create {package_path}")
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, unreal.Blueprint, factory)
    if asset is None:
        raise RuntimeError(f"Could not create {asset_path}")
    emit("ASSET_CREATED", asset_path)
else:
    emit("ASSET_REUSED", asset_path)

document = unreal.EditorAssetLibrary.load_asset(schema["dependencies"][0])
if document is None:
    raise RuntimeError("Flypath document struct dependency is missing")
types = {
    "Boolean": unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool"),
    "Integer": unreal.BlueprintEditorLibrary.get_basic_type_by_name("int"),
    "String": unreal.BlueprintEditorLibrary.get_basic_type_by_name("string"),
    "ST_EDD_FlypathDocument": unreal.BlueprintEditorLibrary.get_struct_type(document),
    "PlayFabJsonObject": unreal.BlueprintEditorLibrary.get_object_reference_type(unreal.PlayFabJsonObject),
}

for field in schema["variables"]:
    name = field["name"]
    try:
        generated_value(asset_path, name)
        emit("VARIABLE_REUSED", name)
    except RuntimeError:
        pin_type = types[field["type"]]
        if field["container"] == "Array":
            pin_type = unreal.BlueprintEditorLibrary.get_array_type(pin_type)
        if not unreal.BlueprintEditorLibrary.add_member_variable(asset, name, pin_type):
            raise RuntimeError(f"Could not add {name}")
        unreal.BlueprintEditorLibrary.compile_blueprint(asset)
        emit("VARIABLE_CREATED", name)
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(asset, name, True)

for function_name in schema["functions"]:
    graph = unreal.BlueprintEditorLibrary.find_graph(asset, unreal.Name(function_name))
    if graph is None:
        graph = unreal.BlueprintEditorLibrary.add_function_graph(asset, function_name)
        if graph is None:
            raise RuntimeError(f"Could not add function {function_name}")
        emit("FUNCTION_CREATED", function_name)
    else:
        emit("FUNCTION_REUSED", function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(asset)
for field in schema["variables"]:
    name = field["name"]
    actual = generated_value(asset_path, name)
    if field["container"] == "Array":
        expected = schema.get("arrayDefaults", {}).get(name, [])
        if list(actual) != expected:
            set_generated_value(asset_path, name, expected)
            actual = generated_value(asset_path, name)
        if list(actual) != expected:
            raise RuntimeError(f"{name} default mismatch: {actual!r}")
    elif "default" in field and actual != field["default"]:
        set_generated_value(asset_path, name, field["default"])
        actual = generated_value(asset_path, name)
        if actual != field["default"]:
            raise RuntimeError(f"{name} default mismatch: {actual!r}")
    emit("DEFAULT_VERIFIED", f"{name}={actual}")

default_actor = unreal.get_default_object(generated_class(asset_path))
default_actor.set_editor_property("replicates", False)
try:
    default_actor.set_editor_property("net_load_on_client", False)
except Exception:
    emit("NET_LOAD_ON_CLIENT_UNAVAILABLE", True)
if default_actor.get_editor_property("replicates"):
    raise RuntimeError("Repository actor must not replicate to clients")
try:
    net_load_on_client = default_actor.get_editor_property("net_load_on_client")
except Exception:
    net_load_on_client = None
if net_load_on_client is True:
    raise RuntimeError("Repository actor must not be net-loaded on clients")
emit("SERVER_ONLY_DEFAULTS_VERIFIED", True)

unreal.BlueprintEditorLibrary.compile_blueprint(asset)
if not unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False):
    raise RuntimeError(f"Could not save {asset_path}")

for function_name in schema["functions"]:
    if unreal.BlueprintEditorLibrary.find_graph(asset, unreal.Name(function_name)) is None:
        raise RuntimeError(f"Missing function {function_name}")
    emit("FUNCTION_VERIFIED", function_name)
emit("COMPLETE", True)
