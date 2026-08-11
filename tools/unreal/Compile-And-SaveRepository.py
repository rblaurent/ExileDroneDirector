"""Compile and save the live repository Blueprint with stable log markers."""

from __future__ import annotations

import unreal


ASSET_PATH = "/Game/Mods/ExileDroneDirector/Server/Repository/BP_EDD_FlypathRepository"
PREFIX = "EDD_REPOSITORY_COMPILE"


asset = unreal.load_asset(ASSET_PATH)
if asset is None:
    raise RuntimeError(f"Repository Blueprint missing: {ASSET_PATH}")

unreal.log(f"{PREFIX}|BEGIN")
unreal.BlueprintEditorLibrary.compile_blueprint(asset)
saved = unreal.EditorAssetLibrary.save_asset(ASSET_PATH, only_if_is_dirty=False)
unreal.log(f"{PREFIX}|SAVED|{saved}")
if not saved:
    raise RuntimeError(f"Could not save {ASSET_PATH}")
unreal.log(f"{PREFIX}|END")
