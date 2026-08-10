"""Add the client-owned path-preview reference and lifecycle function seams.

Graph bodies are installed separately from reviewed native Blueprint clipboard
text.  This script only establishes the typed asset contract, compiles it, and
verifies the safe empty default before any graph is pasted.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PATH_PREVIEW_LIFECYCLE"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
PREVIEW_PATH = "/Game/Mods/ExileDroneDirector/Trajectory/BP_EDD_PathPreview"
REFERENCE_NAME = "PathPreviewActorV1"
FUNCTIONS = ("RefreshPathPreviewV1", "DestroyPathPreviewV1")


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


def ensure_reference(client, preview_class) -> None:
    try:
        generated_value(REFERENCE_NAME)
        emit("VARIABLE_ALREADY_PRESENT", REFERENCE_NAME)
        return
    except RuntimeError:
        pass

    pin_type = unreal.BlueprintEditorLibrary.get_object_reference_type(preview_class)
    if not unreal.BlueprintEditorLibrary.add_member_variable(client, REFERENCE_NAME, pin_type):
        raise RuntimeError(f"Failed to add {REFERENCE_NAME}")
    emit("VARIABLE_CREATED", REFERENCE_NAME)
    unreal.BlueprintEditorLibrary.compile_blueprint(client)


def ensure_function(client, function_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(function_name))
    if graph is not None:
        emit("FUNCTION_ALREADY_PRESENT", function_name)
        return
    graph = unreal.BlueprintEditorLibrary.add_function_graph(client, function_name)
    if graph is None:
        raise RuntimeError(f"Failed to add {function_name}")
    emit("FUNCTION_CREATED", function_name)


client = require_asset(CLIENT_PATH)
preview_class = require_class(PREVIEW_PATH)
ensure_reference(client, preview_class)
for function_name in FUNCTIONS:
    ensure_function(client, function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
if generated_value(REFERENCE_NAME) is not None:
    raise RuntimeError(f"{REFERENCE_NAME} default must be None")
emit("EMPTY_REFERENCE_VERIFIED", True)

for function_name in FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(function_name)) is None:
        raise RuntimeError(f"Blueprint is missing {function_name}")
    emit("FUNCTION_VERIFIED", function_name)

if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client)
emit("COMPLETE", True)
