"""Report the Enhanced DevKit APIs needed for typed waypoint draft storage.

This probe is intentionally read-only. Run it through UnrealEditor-Cmd with
``-run=pythonscript`` before changing Blueprint member-variable schemas.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_WAYPOINT_TYPE_PROBE"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
WAYPOINT_PATH = "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Waypoint"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def public_names(value) -> list[str]:
    return sorted(name for name in dir(value) if not name.startswith("_"))


emit("UNREAL_VERSION", unreal.SystemLibrary.get_engine_version())
emit(
    "UNREAL_PIN_NAMES",
    [name for name in public_names(unreal) if "pin" in name.lower() or "container" in name.lower()],
)

for type_name in ("bool", "integer", "real", "string", "name", "transform"):
    try:
        pin_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name(type_name)
        emit(
            f"BASIC_TYPE_{type_name.upper()}",
            repr(pin_type),
        )
        emit(
            f"BASIC_TYPE_{type_name.upper()}_PROPERTIES",
            public_names(pin_type),
        )
        emit(f"BASIC_TYPE_{type_name.upper()}_TUPLE", pin_type.to_tuple())
        try:
            emit(
                f"ARRAY_TYPE_{type_name.upper()}_TUPLE",
                unreal.BlueprintEditorLibrary.get_array_type(pin_type).to_tuple(),
            )
        except Exception as array_error:
            emit(f"ARRAY_TYPE_{type_name.upper()}_ERROR", repr(array_error))
    except Exception as error:
        emit(f"BASIC_TYPE_{type_name.upper()}_ERROR", repr(error))

for candidate in (unreal.Transform, unreal.Vector, unreal.Rotator):
    try:
        pin_type = unreal.BlueprintEditorLibrary.get_struct_type(candidate)
        emit(f"STRUCT_TYPE_{candidate.__name__.upper()}", repr(pin_type))
    except Exception as error:
        emit(f"STRUCT_TYPE_{candidate.__name__.upper()}_ERROR", repr(error))

for object_path in (
    "/Script/CoreUObject.Transform",
    "/Script/CoreUObject.Vector",
    "/Script/CoreUObject.Rotator",
):
    label = object_path.rsplit(".", 1)[-1].upper()
    try:
        script_struct = unreal.load_object(None, object_path)
        emit(f"SCRIPT_STRUCT_{label}", repr(script_struct))
        pin_type = unreal.BlueprintEditorLibrary.get_struct_type(script_struct)
        emit(f"SCRIPT_STRUCT_{label}_PIN", pin_type.export_text())
        emit(
            f"SCRIPT_STRUCT_{label}_ARRAY_PIN",
            unreal.BlueprintEditorLibrary.get_array_type(pin_type).export_text(),
        )
    except Exception as error:
        emit(f"SCRIPT_STRUCT_{label}_ERROR", repr(error))

client = unreal.EditorAssetLibrary.load_asset(CLIENT_PATH)
waypoint = unreal.EditorAssetLibrary.load_asset(WAYPOINT_PATH)
emit("CLIENT_ASSET", repr(client))
emit("WAYPOINT_ASSET", repr(waypoint))

if client is not None:
    emit("BLUEPRINT_LIBRARY", public_names(unreal.BlueprintEditorLibrary))
    emit("CLIENT_METHODS", public_names(client))

if waypoint is not None:
    emit("WAYPOINT_CLASS", waypoint.get_class().get_path_name())
    emit("WAYPOINT_METHODS", public_names(waypoint))
    try:
        waypoint_pin = unreal.BlueprintEditorLibrary.get_struct_type(waypoint)
        emit("WAYPOINT_PIN_TUPLE", waypoint_pin.to_tuple())
        emit(
            "WAYPOINT_ARRAY_PIN_TUPLE",
            unreal.BlueprintEditorLibrary.get_array_type(waypoint_pin).to_tuple(),
        )
    except Exception as error:
        emit("WAYPOINT_PIN_ERROR", repr(error))
    try:
        editor_data = waypoint.get_editor_property("editor_data")
        emit("WAYPOINT_EDITOR_DATA", repr(editor_data))
        emit("WAYPOINT_EDITOR_DATA_METHODS", public_names(editor_data))
    except Exception as error:
        emit("WAYPOINT_EDITOR_DATA_ERROR", repr(error))

emit("COMPLETE", True)
