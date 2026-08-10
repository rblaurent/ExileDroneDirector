"""Create and verify the first server-owned repository SaveGame adapter."""

from __future__ import annotations

import json
from pathlib import Path
import unreal


PREFIX = "EDD_REPOSITORY_SAVEGAME_CONFIG"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "persistence" / "repository_savegame_schema.json"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def snake_name(value: str) -> str:
    return "".join(("_" + character.lower()) if character.isupper() else character for character in value).lstrip("_")


def generated_value(asset_path: str, variable_name: str):
    generated_class = unreal.EditorAssetLibrary.load_blueprint_class(asset_path)
    if generated_class is None:
        raise RuntimeError(f"Generated class missing: {asset_path}")
    default_object = unreal.get_default_object(generated_class)
    last_error = None
    for candidate in (variable_name, unreal.Name(variable_name), snake_name(variable_name), unreal.Name(snake_name(variable_name))):
        try:
            return default_object.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


def set_generated_value(default_object, variable_name: str, value) -> None:
    last_error = None
    for candidate in (variable_name, unreal.Name(variable_name), snake_name(variable_name), unreal.Name(snake_name(variable_name))):
        try:
            default_object.set_editor_property(candidate, value)
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not set {variable_name}: {last_error}")


def pin_type(field: dict):
    basic_names = {
        "Integer": "int",
        "Boolean": "bool",
        "String": "string",
    }
    result = unreal.BlueprintEditorLibrary.get_basic_type_by_name(basic_names[field["type"]])
    if field["container"] == "Array":
        result = unreal.BlueprintEditorLibrary.get_array_type(result)
    return result


schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
asset_path = schema["virtualPath"]
asset = (
    unreal.EditorAssetLibrary.load_asset(asset_path)
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path)
    else None
)
if asset is None:
    package_path, asset_name = asset_path.rsplit("/", 1)
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        if not unreal.EditorAssetLibrary.make_directory(package_path):
            raise RuntimeError(f"Could not create {package_path}")
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.SaveGame)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        package_path,
        unreal.Blueprint,
        factory,
    )
    if asset is None:
        raise RuntimeError(f"Could not create {asset_path}")
    emit("ASSET_CREATED", asset_path)
else:
    emit("ASSET_REUSED", asset_path)

for field in schema["fields"]:
    name = field["name"]
    try:
        generated_value(asset_path, name)
        emit("VARIABLE_REUSED", name)
    except RuntimeError:
        if not unreal.BlueprintEditorLibrary.add_member_variable(asset, name, pin_type(field)):
            raise RuntimeError(f"Could not add {name}")
        unreal.BlueprintEditorLibrary.compile_blueprint(asset)
        emit("VARIABLE_CREATED", name)
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(asset, name, True)
    emit("VARIABLE_INSTANCE_EDITABLE", name)

unreal.BlueprintEditorLibrary.compile_blueprint(asset)
generated_class = unreal.EditorAssetLibrary.load_blueprint_class(asset_path)
if generated_class is None:
    raise RuntimeError("SaveGame generated class missing after compile")
default_object = unreal.get_default_object(generated_class)
for field in schema["fields"]:
    name = field["name"]
    value = generated_value(asset_path, name)
    if field["container"] == "Array":
        if len(value) != 0:
            raise RuntimeError(f"{name} must default to an empty array")
    elif name == "RepositorySchemaVersion" and value != schema["schemaVersion"]:
        set_generated_value(default_object, name, schema["schemaVersion"])
        emit("DEFAULT_SET", f"{name}={schema['schemaVersion']}")

unreal.BlueprintEditorLibrary.compile_blueprint(asset)
if not unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False):
    raise RuntimeError(f"Could not save {asset_path}")

for field in schema["fields"]:
    emit("VERIFIED", f"{field['name']}={generated_value(asset_path, field['name'])}")
emit("COMPLETE", True)
