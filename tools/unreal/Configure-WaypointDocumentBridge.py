"""Bind the authored waypoint struct into the client draft without migration.

The six runtime-proven legacy arrays remain authoritative until a separately
validated adapter writes ``DraftWaypointsV1`` atomically.  This script creates
only that typed seam, compiles it, verifies the generated empty-array default,
and saves the client Blueprint.  It is intentionally idempotent.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_WAYPOINT_DOCUMENT_BRIDGE"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
WAYPOINT_PATH = "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Waypoint"
VARIABLE_NAME = "DraftWaypointsV1"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require_asset(path: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset could not be loaded: {path}")
    return asset


def require_class(path: str):
    generated_class = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if generated_class is None:
        raise RuntimeError(f"Required Blueprint class could not be loaded: {path}")
    return generated_class


def property_candidates(variable_name: str) -> tuple[object, ...]:
    snake = "".join(
        ("_" + character.lower()) if character.isupper() else character
        for character in variable_name
    ).lstrip("_")
    return variable_name, unreal.Name(variable_name), snake, unreal.Name(snake)


def generated_value(variable_name: str):
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            return default_object.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


client = require_asset(CLIENT_PATH)
waypoint = require_asset(WAYPOINT_PATH)
try:
    existing = generated_value(VARIABLE_NAME)
    emit("VARIABLE_ALREADY_PRESENT", VARIABLE_NAME)
except RuntimeError:
    element_type = unreal.BlueprintEditorLibrary.get_struct_type(waypoint)
    array_type = unreal.BlueprintEditorLibrary.get_array_type(element_type)
    if not unreal.BlueprintEditorLibrary.add_member_variable(client, VARIABLE_NAME, array_type):
        raise RuntimeError(f"Failed to add {VARIABLE_NAME}")
    emit("VARIABLE_CREATED", VARIABLE_NAME)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
value = generated_value(VARIABLE_NAME)
if len(value) != 0:
    raise RuntimeError(f"{VARIABLE_NAME} default must be empty, received {len(value)} items")
emit("EMPTY_TYPED_ARRAY_VERIFIED", len(value))

if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client)
emit("COMPLETE", True)
