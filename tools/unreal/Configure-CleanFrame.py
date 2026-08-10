"""Create and verify the client-local Clean Frame state seam.

The graph bodies are installed from reviewed Blueprint clipboard artifacts.
This script deliberately creates only typed state and named function contracts;
it never edits Conan-owned assets.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_CLEAN_FRAME_CONFIG"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
BOOL_DEFAULTS = {
    "CleanFrameActiveV1": False,
    "CleanFrameRestoreHUDCategoryV1": True,
    "CleanFrameRestorePopupCategoryV1": True,
}
FUNCTIONS = (
    "EnterCleanFrameV1",
    "ExitCleanFrameV1",
    "ToggleCleanFrameV1",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require_asset(path: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset could not be loaded: {path}")
    return asset


def require_class(path: str):
    value = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if value is None:
        raise RuntimeError(f"Required Blueprint class could not be loaded: {path}")
    return value


def property_candidates(variable_name: str) -> tuple[object, ...]:
    snake = "".join(
        ("_" + character.lower()) if character.isupper() else character
        for character in variable_name
    ).lstrip("_")
    return variable_name, unreal.Name(variable_name), snake, unreal.Name(snake)


def generated_value(variable_name: str):
    defaults = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            return defaults.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


def has_variable(variable_name: str) -> bool:
    try:
        generated_value(variable_name)
        return True
    except RuntimeError:
        return False


def ensure_variable(blueprint, variable_name: str, pin_type) -> None:
    if has_variable(variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        return
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, variable_name, pin_type):
        raise RuntimeError(f"Failed to add {variable_name}")
    emit("VARIABLE_CREATED", variable_name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)


def set_default(variable_name: str, expected: bool) -> None:
    defaults = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            defaults.set_editor_property(candidate, expected)
            actual = bool(defaults.get_editor_property(candidate))
            if actual is not expected:
                raise RuntimeError(f"expected {expected}, received {actual}")
            emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not set {variable_name}: {last_error}")


def ensure_function(blueprint, function_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(function_name))
    if graph is not None:
        emit("FUNCTION_ALREADY_PRESENT", function_name)
        return
    graph = unreal.BlueprintEditorLibrary.add_function_graph(blueprint, function_name)
    if graph is None:
        raise RuntimeError(f"Failed to add {function_name}")
    emit("FUNCTION_CREATED", function_name)


client = require_asset(CLIENT_PATH)
bool_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool")

for name in BOOL_DEFAULTS:
    ensure_variable(client, name, bool_type)
for function_name in FUNCTIONS:
    ensure_function(client, function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
for name, expected in BOOL_DEFAULTS.items():
    set_default(name, expected)
for function_name in FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(function_name)) is None:
        raise RuntimeError(f"Blueprint is missing {function_name}")
    emit("FUNCTION_VERIFIED", function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client)
emit("COMPLETE", True)
