"""Close and delete the disposable repository SaveGame node probe."""

from __future__ import annotations

import unreal


ASSET_PATH = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_SaveGameNodeProbe"
PREFIX = "EDD_SAVEGAME_NODE_PROBE"


asset = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if asset is not None and subsystem is not None:
    subsystem.close_all_editors_for_asset(asset)

# Enhanced's force-delete must unload the package. Keeping the loaded Blueprint
# in this Python frame roots it through GCObjectReferencer and makes deletion
# fail even after its editor closes.
asset = None
unreal.SystemLibrary.collect_garbage()

deleted = True
if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
    deleted = unreal.EditorAssetLibrary.delete_asset(ASSET_PATH)

unreal.log(f"{PREFIX}|DELETED|{deleted}")
if not deleted:
    raise RuntimeError(f"Could not delete {ASSET_PATH}")
