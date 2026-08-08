"""Read-only inspection of Blueprint construction APIs and Conan parent classes."""

from __future__ import annotations

import json

import unreal


PREFIX = "EDD_BLUEPRINT_API"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{json.dumps(value, default=str, sort_keys=True)}")


def public_symbols(value) -> list[str]:
    return sorted(name for name in dir(value) if not name.startswith("_"))


example = unreal.load_asset("/Game/Items/Example_modcontroller")
if example is None:
    raise RuntimeError("Could not load /Game/Items/Example_modcontroller")

emit("example_type", type(example).__name__)
emit("example_path", example.get_path_name())
emit("example_symbols", public_symbols(example))

generated_class = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Items/Example_modcontroller")
emit("example_generated_class", generated_class.get_path_name() if generated_class else None)
parent_class = generated_class.get_super_class() if generated_class and hasattr(generated_class, "get_super_class") else None
emit("example_parent_class", parent_class.get_path_name() if parent_class else None)

if generated_class:
    default_object = unreal.get_default_object(generated_class)
    emit("example_cdo_type", type(default_object).__name__)
    for property_name in ("additional_class_components", "additional_gameplay_tag_tables", "replicates"):
        try:
            value = default_object.get_editor_property(property_name)
            emit(f"example_cdo_property_{property_name}", {"type": type(value).__name__, "value": value})
        except Exception as error:
            emit(f"example_cdo_property_error_{property_name}", str(error))
    emit(
        "example_cdo_relevant_symbols",
        [
            name
            for name in public_symbols(default_object)
            if any(token in name.lower() for token in ("component", "mod", "table", "player", "replic", "save"))
        ],
    )

classes = (
    "ActorComponent",
    "Blueprint",
    "BlueprintFactory",
    "CineCameraActor",
    "CineCameraComponent",
    "DataAssetFactory",
    "EnhancedInputComponent",
    "FloatingPawnMovement",
    "InputAction",
    "InputMappingContext",
    "Pawn",
    "SceneComponent",
    "SpectatorPawn",
    "SplineComponent",
    "StructureFactory",
    "SubobjectDataBlueprintFunctionLibrary",
    "SubobjectDataSubsystem",
    "UserDefinedStruct",
    "WidgetBlueprintFactory",
)
emit("class_availability", {name: hasattr(unreal, name) for name in classes})

additional_component_symbols = [name for name in dir(unreal) if "additionalclass" in name.lower() or "classcomponent" in name.lower()]
emit("additional_component_symbols", additional_component_symbols)
for symbol_name in additional_component_symbols:
    symbol = getattr(unreal, symbol_name)
    emit(f"additional_component_symbol_{symbol_name}", {"doc": getattr(symbol, "__doc__", None), "symbols": public_symbols(symbol)})

for symbol_name in (
    "AssetToolsHelpers",
    "BlueprintEditorLibrary",
    "SubobjectDataBlueprintFunctionLibrary",
    "SubobjectDataSubsystem",
):
    symbol = getattr(unreal, symbol_name, None)
    if symbol is not None:
        emit(f"symbols_{symbol_name}", public_symbols(symbol))

emit("complete", True)

