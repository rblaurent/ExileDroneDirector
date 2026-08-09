"""Add and verify the drone actor's local flight-control contracts."""

from __future__ import annotations

import unreal


PREFIX = "EDD_DRONE_MOVEMENT"
DRONE_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera"
REQUIRED_FUNCTIONS = ("ApplyTranslationInput", "ApplyRotationInput")
DEFAULTS = {
    "BaseMoveSpeed": 600.0,
    "BoostMultiplier": 3.0,
    "LookSensitivity": 0.12,
}
MOVEMENT_COMPONENT_DEFAULTS = {
    "max_speed": DEFAULTS["BaseMoveSpeed"],
}


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


def set_and_verify_default(default_object, variable_name: str, value: float) -> None:
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            default_object.set_editor_property(candidate, value)
            actual = float(default_object.get_editor_property(candidate))
            if abs(actual - value) > 0.0001:
                raise RuntimeError(f"expected {value}, received {actual}")
            emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not configure {variable_name}: {last_error}")


def set_and_verify_component_default(
    default_object,
    property_name: str,
    value: float,
) -> None:
    movement_component = default_object.get_editor_property("movement_component")
    if movement_component is None:
        raise RuntimeError("Drone class default has no movement_component")
    movement_component.set_editor_property(property_name, value)
    actual = float(movement_component.get_editor_property(property_name))
    if abs(actual - value) > 0.0001:
        raise RuntimeError(
            f"movement_component.{property_name}: expected {value}, received {actual}"
        )
    emit("COMPONENT_DEFAULT_VERIFIED", f"{property_name}|{actual}")


def ensure_function_graph(blueprint, function_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(function_name))
    if graph is not None:
        emit("FUNCTION_ALREADY_PRESENT", function_name)
        return
    graph = unreal.BlueprintEditorLibrary.add_function_graph(blueprint, function_name)
    if graph is None:
        raise RuntimeError(f"Failed to add Blueprint function: {function_name}")
    emit("FUNCTION_CREATED", function_name)


drone_blueprint = require_asset(DRONE_PATH)
for required_function in REQUIRED_FUNCTIONS:
    ensure_function_graph(drone_blueprint, required_function)

unreal.BlueprintEditorLibrary.compile_blueprint(drone_blueprint)
drone_class = require_class(DRONE_PATH)
drone_default = unreal.get_default_object(drone_class)
for variable_name, value in DEFAULTS.items():
    set_and_verify_default(drone_default, variable_name, value)
for property_name, value in MOVEMENT_COMPONENT_DEFAULTS.items():
    set_and_verify_component_default(drone_default, property_name, value)

unreal.BlueprintEditorLibrary.compile_blueprint(drone_blueprint)
if not unreal.EditorAssetLibrary.save_asset(DRONE_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {DRONE_PATH}")

for required_function in REQUIRED_FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(
        drone_blueprint,
        unreal.Name(required_function),
    ) is None:
        raise RuntimeError(f"Blueprint is missing function: {required_function}")
    emit("FUNCTION_VERIFIED", required_function)

unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(drone_blueprint)
emit("COMPILED", drone_class.get_path_name())
emit("COMPLETE", True)
