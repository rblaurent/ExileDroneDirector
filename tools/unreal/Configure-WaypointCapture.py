"""Add and verify the first client-local waypoint draft-storage contract.

The Enhanced DevKit exposes typed Blueprint arrays but does not expose user-
defined-struct field editing to Python. The local draft therefore continues to
use the runtime-proven lockstep arrays until the separately validated
``DraftWaypointsV1`` adapter is wired. CaptureCurrentWaypoint is responsible for
appending every legacy channel atomically during this migration.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_WAYPOINT_CAPTURE"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
DRONE_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera"
FUNCTION_NAMES = (
    "CaptureCurrentWaypoint",
    "ReplaceSelectedWaypoint",
    "DeleteSelectedWaypoint",
)
ARRAY_VARIABLES = (
    ("DraftWaypointIds", "int", None),
    ("DraftWaypointTransforms", None, "/Script/CoreUObject.Transform"),
    ("DraftWaypointFocalLengths", "real", None),
    ("DraftWaypointApertures", "real", None),
    ("DraftWaypointFocusDistances", "real", None),
    ("DraftWaypointHoldSeconds", "real", None),
)
SCALAR_DEFAULTS = {
    "NextWaypointId": 1,
    "SelectedWaypointIndex": -1,
}
DRONE_LENS_DEFAULTS = {
    "FocalLength": 35.0,
    "Aperture": 2.8,
    "ManualFocusDistance": 1000.0,
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


def get_generated_property(variable_name: str):
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            return default_object.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


def set_generated_default(blueprint_path: str, variable_name: str, expected) -> None:
    default_object = unreal.get_default_object(require_class(blueprint_path))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            default_object.set_editor_property(candidate, expected)
            actual = default_object.get_editor_property(candidate)
            if abs(float(actual) - float(expected)) > 0.0001:
                raise RuntimeError(f"expected {expected}, received {actual}")
            emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not configure {variable_name}: {last_error}")


def has_generated_property(variable_name: str) -> bool:
    try:
        get_generated_property(variable_name)
        return True
    except Exception:
        return False


def basic_pin(type_name: str):
    return unreal.BlueprintEditorLibrary.get_basic_type_by_name(type_name)


def struct_pin(object_path: str):
    script_struct = unreal.load_object(None, object_path)
    if script_struct is None:
        raise RuntimeError(f"Could not resolve ScriptStruct: {object_path}")
    return unreal.BlueprintEditorLibrary.get_struct_type(script_struct)


def ensure_array_variable(
    blueprint,
    variable_name: str,
    basic_type_name: str | None,
    struct_path: str | None,
) -> None:
    if has_generated_property(variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        return
    element_pin = basic_pin(basic_type_name) if basic_type_name else struct_pin(struct_path)
    array_pin = unreal.BlueprintEditorLibrary.get_array_type(element_pin)
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint,
        variable_name,
        array_pin,
    ):
        raise RuntimeError(f"Failed to add Blueprint array variable: {variable_name}")
    emit("VARIABLE_CREATED", variable_name)


def ensure_scalar_variable(blueprint, variable_name: str, type_name: str) -> None:
    if has_generated_property(variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        return
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint,
        variable_name,
        basic_pin(type_name),
    ):
        raise RuntimeError(f"Failed to add Blueprint variable: {variable_name}")
    emit("VARIABLE_CREATED", variable_name)


def ensure_function_graph(blueprint, function_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(function_name))
    if graph is not None:
        emit("FUNCTION_ALREADY_PRESENT", function_name)
        return
    graph = unreal.BlueprintEditorLibrary.add_function_graph(blueprint, function_name)
    if graph is None:
        raise RuntimeError(f"Failed to add Blueprint function: {function_name}")
    emit("FUNCTION_CREATED", function_name)


client_blueprint = require_asset(CLIENT_PATH)
for variable_name, basic_type_name, struct_path in ARRAY_VARIABLES:
    ensure_array_variable(
        client_blueprint,
        variable_name,
        basic_type_name,
        struct_path,
    )
for variable_name in SCALAR_DEFAULTS:
    ensure_scalar_variable(client_blueprint, variable_name, "int")
for function_name in FUNCTION_NAMES:
    ensure_function_graph(client_blueprint, function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(client_blueprint)
for variable_name, expected in SCALAR_DEFAULTS.items():
    set_generated_default(CLIENT_PATH, variable_name, expected)

unreal.BlueprintEditorLibrary.compile_blueprint(client_blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")

for variable_name, _, _ in ARRAY_VARIABLES:
    value = get_generated_property(variable_name)
    if len(value) != 0:
        raise RuntimeError(f"{variable_name} default must be empty, received {len(value)} items")
    emit("EMPTY_ARRAY_VERIFIED", variable_name)
for function_name in FUNCTION_NAMES:
    if unreal.BlueprintEditorLibrary.find_graph(
        client_blueprint,
        unreal.Name(function_name),
    ) is None:
        raise RuntimeError(f"Blueprint is missing function: {function_name}")

unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client_blueprint)
for function_name in FUNCTION_NAMES:
    emit("FUNCTION_VERIFIED", function_name)

drone_blueprint = require_asset(DRONE_PATH)
for variable_name, expected in DRONE_LENS_DEFAULTS.items():
    set_generated_default(DRONE_PATH, variable_name, expected)
unreal.BlueprintEditorLibrary.compile_blueprint(drone_blueprint)
if not unreal.EditorAssetLibrary.save_asset(DRONE_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {DRONE_PATH}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(drone_blueprint)
emit("COMPLETE", True)
