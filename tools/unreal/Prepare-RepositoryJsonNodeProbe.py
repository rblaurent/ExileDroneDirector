"""Create and open a disposable Blueprint used to harvest PlayFab JSON nodes.

The probe lives below Developer/Automation and is never a runtime dependency.
Delete it with Delete-RepositoryJsonNodeProbe.py after the reviewed node forms
have been copied into tools/blueprint/templates.
"""

from __future__ import annotations

import unreal


ASSET_PATH = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_JsonNodeProbe"
FUNCTION_NAME = "ProbeJsonNodesV1"
PREFIX = "EDD_JSON_NODE_PROBE"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


asset = None
if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
    asset = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if asset is None:
        raise RuntimeError(f"Asset registry reported {ASSET_PATH}, but it could not be loaded")

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

unreal.BlueprintEditorLibrary.compile_blueprint(asset)
if not unreal.EditorAssetLibrary.save_asset(ASSET_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Could not save {ASSET_PATH}")

subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if subsystem is None or not subsystem.open_editor_for_assets([asset]):
    raise RuntimeError("Could not open JSON node probe editor")

emit("ASSET", asset.get_path_name())
emit("FUNCTION", FUNCTION_NAME)
emit("READY", True)
