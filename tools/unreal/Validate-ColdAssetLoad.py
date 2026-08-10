"""Cold-load and compile the core EDD assets through Conan's active-mod mount.

Run this only in a fresh ``UnrealEditor-Cmd`` process with ``-ModDevKit``.  It
proves that the physical ``Content/Mods/ExileDroneDirector/Local`` source tree
is exposed at ``/Game/Mods/ExileDroneDirector`` and that no Blueprint depends
on a package which exists only in a previously warmed editor session.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_COLD_LOAD"
ASSET_PATHS = (
    "/Game/Mods/ExileDroneDirector/BP_EDD_ModController",
    "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Waypoint",
    "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Segment",
    "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument",
    "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera",
    "/Game/Mods/ExileDroneDirector/Trajectory/BP_EDD_PathPreview",
    "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


loaded_assets = []
for asset_path in ASSET_PATHS:
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Cold-load failed: {asset_path}")
    loaded_assets.append(asset)
    emit("LOADED", f"{asset_path}|{asset.get_path_name()}")

for asset in loaded_assets:
    if isinstance(asset, unreal.Blueprint):
        unreal.BlueprintEditorLibrary.compile_blueprint(asset)
        emit("COMPILED", asset.get_path_name())

emit("RESULT", "PASS")
