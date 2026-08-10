"""Create the live SyncDraftWaypointsV1 Blueprint function seam.

Graph nodes are installed separately from a reviewed native Blueprint clipboard
snippet.  This configurator is idempotent and refuses to create the function
until the authored struct array is present on the generated client component.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_WAYPOINT_STRUCT_SYNC"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
VARIABLE_NAME = "DraftWaypointsV1"
FUNCTION_NAME = "SyncDraftWaypointsV1"


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


def generated_value(variable_name: str):
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    snake = "".join(
        ("_" + character.lower()) if character.isupper() else character
        for character in variable_name
    ).lstrip("_")
    last_error = None
    for candidate in (variable_name, unreal.Name(variable_name), snake, unreal.Name(snake)):
        try:
            return default_object.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


client = require_asset(CLIENT_PATH)
typed_default = generated_value(VARIABLE_NAME)
if len(typed_default) != 0:
    raise RuntimeError(f"{VARIABLE_NAME} default must be empty")
emit("TYPED_ARRAY_VERIFIED", len(typed_default))

graph = unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(FUNCTION_NAME))
if graph is None:
    graph = unreal.BlueprintEditorLibrary.add_function_graph(client, FUNCTION_NAME)
    if graph is None:
        raise RuntimeError(f"Failed to create {FUNCTION_NAME}")
    emit("FUNCTION_CREATED", FUNCTION_NAME)
else:
    emit("FUNCTION_ALREADY_PRESENT", FUNCTION_NAME)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client)
emit("COMPLETE", True)
