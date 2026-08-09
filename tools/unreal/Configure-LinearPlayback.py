"""Create and verify the state seam for absolute-time linear playback."""

from __future__ import annotations

import unreal


PREFIX = "EDD_LINEAR_PLAYBACK"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
VARIABLE_DEFAULTS = (
    ("PlaybackActive", "bool", False),
    ("PlaybackStartTimeSeconds", "real", 0.0),
    ("PlaybackSecondsPerSegment", "real", 3.0),
)
FUNCTION_NAMES = (
    "StartLinearPlayback",
    "UpdateLinearPlayback",
    "StopLinearPlayback",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


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


def get_generated_property(variable_name: str):
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            return default_object.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


def has_generated_property(variable_name: str) -> bool:
    try:
        get_generated_property(variable_name)
        return True
    except Exception:
        return False


def set_generated_default(variable_name: str, expected) -> None:
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            default_object.set_editor_property(candidate, expected)
            actual = default_object.get_editor_property(candidate)
            if isinstance(expected, float):
                if abs(float(actual) - expected) > 0.0001:
                    raise RuntimeError(f"expected {expected}, received {actual}")
            elif actual != expected:
                raise RuntimeError(f"expected {expected}, received {actual}")
            emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not configure {variable_name}: {last_error}")


blueprint = require_asset(CLIENT_PATH)
for variable_name, type_name, _ in VARIABLE_DEFAULTS:
    if has_generated_property(variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        continue
    pin_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name(type_name)
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint,
        variable_name,
        pin_type,
    ):
        raise RuntimeError(f"Failed to add Blueprint variable: {variable_name}")
    emit("VARIABLE_CREATED", variable_name)

for function_name in FUNCTION_NAMES:
    graph = unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(function_name))
    if graph is None:
        graph = unreal.BlueprintEditorLibrary.add_function_graph(blueprint, function_name)
        if graph is None:
            raise RuntimeError(f"Failed to add Blueprint function: {function_name}")
        emit("FUNCTION_CREATED", function_name)
    else:
        emit("FUNCTION_ALREADY_PRESENT", function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
for variable_name, _, expected in VARIABLE_DEFAULTS:
    set_generated_default(variable_name, expected)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")

for function_name in FUNCTION_NAMES:
    if unreal.BlueprintEditorLibrary.find_graph(
        blueprint,
        unreal.Name(function_name),
    ) is None:
        raise RuntimeError(f"Blueprint is missing function: {function_name}")
    emit("FUNCTION_VERIFIED", function_name)

unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
emit("COMPLETE", True)
