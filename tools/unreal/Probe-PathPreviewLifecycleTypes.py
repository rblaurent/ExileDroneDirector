"""Read-only probe for client preview lifecycle Blueprint metadata."""

from __future__ import annotations

import json

import unreal


PREFIX = "EDD_PATH_PREVIEW_LIFECYCLE_PROBE"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
PREVIEW_PATH = "/Game/Mods/ExileDroneDirector/Trajectory/BP_EDD_PathPreview"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{json.dumps(value, default=str, sort_keys=True)}")


client = unreal.EditorAssetLibrary.load_asset(CLIENT_PATH)
preview_class = unreal.EditorAssetLibrary.load_blueprint_class(PREVIEW_PATH)
if client is None or preview_class is None:
    raise RuntimeError("Required lifecycle assets could not be loaded")

emit("CLIENT_TYPE", type(client).__name__)
emit("CLIENT_SYMBOLS", [name for name in dir(client) if not name.startswith("_")])
emit(
    "VARIABLE_RELATED_SYMBOLS",
    [
        name
        for name in dir(unreal.BlueprintEditorLibrary)
        if any(token in name.lower() for token in ("variable", "member", "guid", "graph"))
    ],
)
for property_name in ("new_variables", "function_graphs", "ubergraph_pages"):
    try:
        value = client.get_editor_property(property_name)
        emit(f"PROPERTY_{property_name}", value)
    except Exception as error:
        emit(f"PROPERTY_ERROR_{property_name}", str(error))

client_class = unreal.EditorAssetLibrary.load_blueprint_class(CLIENT_PATH)
client_default = unreal.get_default_object(client_class)
preview_default = unreal.get_default_object(preview_class)
emit("CLIENT_DEFAULT_SYMBOLS", [name for name in dir(client_default) if "preview" in name.lower()])
emit("PREVIEW_DEFAULT_SYMBOLS", [name for name in dir(preview_default) if not name.startswith("_")])
emit("COMPLETE", True)
