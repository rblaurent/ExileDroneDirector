"""Read-only inspection of Blueprint graph construction APIs in the Enhanced DevKit."""

from __future__ import annotations

import json

import unreal


PREFIX = "EDD_GRAPH_API"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{json.dumps(value, default=str, sort_keys=True)}")


def public_symbols(value) -> list[str]:
    return sorted(name for name in dir(value) if not name.startswith("_"))


blueprint = unreal.load_asset("/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector")
if blueprint is None:
    raise RuntimeError("Could not load BPC_EDD_ClientDirector")

event_graph = unreal.BlueprintEditorLibrary.find_event_graph(blueprint)
emit("blueprint", blueprint.get_path_name())
emit("event_graph_type", type(event_graph).__name__ if event_graph else None)
emit("event_graph_symbols", public_symbols(event_graph) if event_graph else [])

candidate_names = [
    name
    for name in dir(unreal)
    if (
        name.startswith("K2Node")
        or "EdGraph" in name
        or "GraphEditor" in name
        or "KismetEditor" in name
        or "BlueprintNode" in name
    )
]
emit("candidate_names", candidate_names)

for name in candidate_names:
    if name in {
        "EdGraph",
        "EdGraphNode",
        "EdGraphPin",
        "EdGraphSchema_K2",
        "K2Node",
        "K2Node_CallFunction",
        "K2Node_CustomEvent",
        "K2Node_Event",
        "K2Node_IfThenElse",
        "K2Node_InputAction",
        "K2Node_VariableGet",
        "K2Node_VariableSet",
    }:
        symbol = getattr(unreal, name)
        emit(
            f"symbol_{name}",
            {
                "doc": getattr(symbol, "__doc__", None),
                "symbols": public_symbols(symbol),
            },
        )

emit("blueprint_library_symbols", public_symbols(unreal.BlueprintEditorLibrary))

pin_library = getattr(unreal, "BlueprintGraphPinLibrary", None)
emit("pin_library_present", pin_library is not None)
if pin_library is not None:
    emit("pin_library_symbols", public_symbols(pin_library))

try:
    graph_nodes = event_graph.get_editor_property("nodes") if event_graph else None
    emit("graph_nodes_property", [value.get_path_name() for value in graph_nodes] if graph_nodes else [])
except Exception as error:
    emit("graph_nodes_property_error", str(error))
emit("complete", True)

