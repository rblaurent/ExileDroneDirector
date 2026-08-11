"""Delete the disposable PlayFab JSON Blueprint node-form probe."""

from __future__ import annotations

import unreal


ASSET_PATH = "/Game/Mods/ExileDroneDirector/Developer/Automation/BP_EDD_JsonNodeProbe"
PREFIX = "EDD_JSON_NODE_PROBE_DELETE"


if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
    if not unreal.EditorAssetLibrary.delete_asset(ASSET_PATH):
        raise RuntimeError(f"Could not delete {ASSET_PATH}")
    unreal.log(f"{PREFIX}:DELETED:True")
else:
    unreal.log(f"{PREFIX}:ALREADY_ABSENT:True")

unreal.log(f"{PREFIX}:COMPLETE:True")
