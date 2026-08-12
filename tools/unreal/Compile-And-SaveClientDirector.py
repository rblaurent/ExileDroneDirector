"""Compile and save the live client director with stable markers."""

import unreal

PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
asset = unreal.load_asset(PATH)
if asset is None:
    raise RuntimeError(PATH)
unreal.log("EDD_CLIENT_COMPILE|BEGIN")
unreal.BlueprintEditorLibrary.compile_blueprint(asset)
saved = unreal.EditorAssetLibrary.save_asset(PATH, only_if_is_dirty=False)
unreal.log(f"EDD_CLIENT_COMPILE|SAVED|{saved}")
if not saved:
    raise RuntimeError("Client director save failed")
unreal.log("EDD_CLIENT_COMPILE|END")
