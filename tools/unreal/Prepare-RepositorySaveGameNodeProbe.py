"""Create and open a disposable Blueprint for native SaveGame node harvesting.

The probe is editor-only source below Developer/Automation. It must never be a
runtime dependency and is deleted after the reviewed node forms are captured.
"""

from __future__ import annotations

import unreal


ASSET_PATH = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_SaveGameNodeProbe"
FUNCTION_NAME = "ProbeSaveGameNodesV1"
PREFIX = "EDD_SAVEGAME_NODE_PROBE"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


asset = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
if asset is None:
    package_path, asset_name = ASSET_PATH.rsplit("/", 1)
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        if not unreal.EditorAssetLibrary.make_directory(package_path):
            raise RuntimeError(f"Could not create {package_path}")
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, factory
    )
    if asset is None:
        raise RuntimeError(f"Could not create {ASSET_PATH}")
    emit("ASSET_CREATED", ASSET_PATH)
else:
    emit("ASSET_REUSED", ASSET_PATH)

graph = unreal.BlueprintEditorLibrary.find_graph(asset, unreal.Name(FUNCTION_NAME))
if graph is None:
    graph = unreal.BlueprintEditorLibrary.add_function_graph(asset, FUNCTION_NAME)
    if graph is None:
        raise RuntimeError(f"Could not create {FUNCTION_NAME}")
    emit("FUNCTION_CREATED", FUNCTION_NAME)
else:
    emit("FUNCTION_REUSED", FUNCTION_NAME)

storage_class = unreal.EditorAssetLibrary.load_blueprint_class(
    "/Game/Mods/ExileDroneDirector/Server/Persistence/SG_EDD_RepositoryStorage"
)
if storage_class is None:
    raise RuntimeError("Repository SaveGame generated class is missing")
try:
    asset.generated_class().get_default_object().get_editor_property("ProbeStorageV1")
    emit("VARIABLE_REUSED", "ProbeStorageV1")
except Exception:
    pin_type = unreal.BlueprintEditorLibrary.get_object_reference_type(storage_class)
    if not unreal.BlueprintEditorLibrary.add_member_variable(asset, "ProbeStorageV1", pin_type):
        raise RuntimeError("Could not add ProbeStorageV1")
    emit("VARIABLE_CREATED", "ProbeStorageV1")

unreal.BlueprintEditorLibrary.compile_blueprint(asset)
if not unreal.EditorAssetLibrary.save_asset(ASSET_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Could not save {ASSET_PATH}")

subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if subsystem is None or not subsystem.open_editor_for_assets([asset]):
    raise RuntimeError("Could not open SaveGame node probe editor")

emit("ASSET", asset.get_path_name())
emit("FUNCTION", FUNCTION_NAME)
emit("READY", True)
