"""Open the mod-owned repository Blueprint in the interactive Enhanced editor."""

from __future__ import annotations

import unreal


ASSET_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository"
)
PREFIX = "EDD_REPOSITORY_EDITOR"


asset = unreal.load_asset(ASSET_PATH)
if asset is None:
    raise RuntimeError(f"Could not load {ASSET_PATH}")

subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if subsystem is None:
    raise RuntimeError("AssetEditorSubsystem is unavailable")

opened = subsystem.open_editor_for_assets([asset])
unreal.log(f"{PREFIX}:ASSET:{asset.get_path_name()}")
unreal.log(f"{PREFIX}:OPENED:{opened}")
unreal.log(f"{PREFIX}:READY:True")
