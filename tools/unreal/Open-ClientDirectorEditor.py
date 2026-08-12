"""Open the client-director Blueprint in the controlled Enhanced editor."""

import unreal

PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
asset = unreal.load_asset(PATH)
if asset is None:
    raise RuntimeError(PATH)
subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if subsystem is None:
    raise RuntimeError("AssetEditorSubsystem unavailable")
opened = subsystem.open_editor_for_assets([asset])
unreal.log(f"EDD_CLIENT_EDITOR|OPENED|{opened}")
