"""Add and verify the client director's camera-lifecycle references."""

from __future__ import annotations

import unreal


PREFIX = "EDD_CLIENT_VARIABLES"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
DRONE_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera"
REQUIRED_FUNCTIONS = (
    "EnterDroneMode",
    "CacheOriginalPawn",
    "PlaceDroneAtCurrentView",
    "ActivateDroneView",
    "PossessDroneCamera",
    "SwitchToDroneView",
    "RestoreOriginalPossession",
    "ExitDroneMode",
    "EmergencyExitDroneMode",
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


def has_generated_property(blueprint_path: str, variable_name: str) -> bool:
    generated_class = unreal.EditorAssetLibrary.load_blueprint_class(blueprint_path)
    if generated_class is None:
        return False
    default_object = unreal.get_default_object(generated_class)
    try:
        default_object.get_editor_property(variable_name)
        return True
    except Exception:
        return False


def ensure_object_reference(
    blueprint,
    blueprint_path: str,
    variable_name: str,
    target_class,
) -> None:
    if has_generated_property(blueprint_path, variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        return
    pin_type = unreal.BlueprintEditorLibrary.get_object_reference_type(target_class)
    created = unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint,
        variable_name,
        pin_type,
    )
    if not created:
        raise RuntimeError(f"Failed to add Blueprint variable: {variable_name}")
    emit("VARIABLE_CREATED", variable_name)


def require_generated_property(default_object, variable_name: str) -> None:
    candidates = (
        variable_name,
        unreal.Name(variable_name),
        variable_name[0].lower() + variable_name[1:],
    )
    last_error = None
    for candidate in candidates:
        try:
            default_object.get_editor_property(candidate)
            emit("PROPERTY_VERIFIED", variable_name)
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(
        f"Generated class is missing property {variable_name}: {last_error}"
    )


def ensure_function_graph(blueprint, function_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(
        blueprint,
        unreal.Name(function_name),
    )
    if graph is not None:
        emit("FUNCTION_ALREADY_PRESENT", function_name)
        return
    graph = unreal.BlueprintEditorLibrary.add_function_graph(
        blueprint,
        function_name,
    )
    if graph is None:
        raise RuntimeError(f"Failed to add Blueprint function: {function_name}")
    emit("FUNCTION_CREATED", function_name)


client_blueprint = require_asset(CLIENT_PATH)
drone_class = require_class(DRONE_PATH)

ensure_object_reference(client_blueprint, CLIENT_PATH, "DroneCameraRef", drone_class)
ensure_object_reference(
    client_blueprint,
    CLIENT_PATH,
    "OriginalViewTargetRef",
    unreal.Actor,
)
ensure_object_reference(
    client_blueprint,
    CLIENT_PATH,
    "OriginalPawnRef",
    unreal.Pawn,
)
for required_function in REQUIRED_FUNCTIONS:
    ensure_function_graph(client_blueprint, required_function)

unreal.BlueprintEditorLibrary.compile_blueprint(client_blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")

client_class = require_class(CLIENT_PATH)
client_default = unreal.get_default_object(client_class)
require_generated_property(client_default, "DroneCameraRef")
require_generated_property(client_default, "OriginalViewTargetRef")
require_generated_property(client_default, "OriginalPawnRef")
for required_function in REQUIRED_FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(
        client_blueprint,
        unreal.Name(required_function),
    ) is None:
        raise RuntimeError(f"Blueprint is missing function: {required_function}")
    emit("FUNCTION_VERIFIED", required_function)

unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client_blueprint)
emit("COMPILED", client_class.get_path_name())
emit("COMPLETE", True)
