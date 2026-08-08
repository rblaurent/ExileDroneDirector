"""Read-only reflection probe for the Conan Exiles Enhanced DevKit.

This script intentionally creates, saves, or modifies no Unreal asset. Its output
is used to pin Blueprint parent classes and editor APIs before scaffold generation.
"""

from __future__ import annotations

import json
from pathlib import Path

import unreal


PREFIX = "EDD_PROBE"
MOD_NAME = "ExileDroneDirector"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{json.dumps(value, default=str, sort_keys=True)}")


def asset_record(asset_data: unreal.AssetData) -> dict[str, str]:
    return {
        "asset_name": str(asset_data.asset_name),
        "asset_class_path": str(asset_data.asset_class_path),
        "package_name": str(asset_data.package_name),
        "package_path": str(asset_data.package_path),
    }


emit("engine_version", unreal.SystemLibrary.get_engine_version())
emit("project_content_dir", unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()))
emit("project_saved_dir", unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))

physical_mod_root = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())) / "Mods" / MOD_NAME
emit(
    "mod_root",
    {
        "physical": str(physical_mod_root),
        "exists": physical_mod_root.exists(),
        "entries": sorted(path.name for path in physical_mod_root.iterdir()) if physical_mod_root.exists() else [],
    },
)

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.wait_for_completion()

all_assets = registry.get_all_assets()
needles = (
    "example_modcontroller",
    "modcontroller",
    "playercontroller",
    "baseplayer",
    "cinecamera",
    "spectator",
)

matches: dict[str, list[dict[str, str]]] = {needle: [] for needle in needles}
for asset in all_assets:
    haystack = f"{asset.package_name}/{asset.asset_name}".lower()
    for needle in needles:
        if needle in haystack and len(matches[needle]) < 80:
            matches[needle].append(asset_record(asset))

for needle, records in matches.items():
    emit(f"assets_{needle}", records)

python_symbols = (
    "AssetToolsHelpers",
    "BlueprintFactory",
    "BlueprintEditorLibrary",
    "CineCameraActor",
    "CineCameraComponent",
    "EditorAssetLibrary",
    "EnhancedInputComponent",
    "InputAction",
    "InputMappingContext",
    "SubobjectDataSubsystem",
)
emit("python_symbols", {name: hasattr(unreal, name) for name in python_symbols})

emit("complete", True)

