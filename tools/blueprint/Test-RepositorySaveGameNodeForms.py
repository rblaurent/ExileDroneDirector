"""Contracts for native Enhanced DevKit SaveGame and typed-storage node forms."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


BLOCK_RE = re.compile(
    r'^Begin Object Class=(?P<class>\S+) Name="(?P<name>[^"]+)".*?^End Object\r?$',
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r'^\s*CustomProperties Pin \((?P<body>.*)\)$')
STORAGE_CLASS = (
    "/Script/Engine.BlueprintGeneratedClass'"
    "/Game/Mods/ExileDroneDirector/Server/Persistence/"
    "SG_EDD_RepositoryStorage.SG_EDD_RepositoryStorage_C'"
)
STORAGE_OBJECT = (
    "/Game/Mods/ExileDroneDirector/Server/Persistence/"
    "SG_EDD_RepositoryStorage.SG_EDD_RepositoryStorage_C"
)
SAVEGAME_CLASS = "/Script/CoreUObject.Class'/Script/Engine.SaveGame'"


@dataclass(frozen=True)
class Pin:
    body: str
    pin_id: str
    links: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Node:
    name: str
    node_class: str
    text: str
    pins: dict[str, Pin]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_graph(path: Path) -> dict[str, Node]:
    text = path.read_text(encoding="utf-8")
    nodes: dict[str, Node] = {}
    for match in BLOCK_RE.finditer(text):
        pins: dict[str, Pin] = {}
        for line in match.group(0).splitlines():
            pin_match = PIN_RE.match(line)
            if pin_match is None:
                continue
            body = pin_match.group("body")
            name_match = re.search(r'PinName="([^"]+)"', body)
            id_match = re.search(r"PinId=([0-9A-F]{32})", body)
            require(name_match is not None and id_match is not None, f"Malformed pin in {match.group('name')}")
            links_match = re.search(r"LinkedTo=\(([^)]*)\)", body)
            links = tuple(re.findall(r"([A-Za-z0-9_]+) ([0-9A-F]{32}),", links_match.group(1))) if links_match else ()
            pins[name_match.group(1)] = Pin(body, id_match.group(1), links)
        nodes[match.group("name")] = Node(
            match.group("name"), match.group("class"), match.group(0), pins
        )
    require("ErrorType=" not in text, f"{path.name} retains Blueprint error metadata")
    return nodes


def one(nodes: dict[str, Node], marker: str) -> Node:
    matches = [node for node in nodes.values() if marker in node.text]
    require(len(matches) == 1, f"Expected one node containing {marker!r}; found {len(matches)}")
    return matches[0]


def pin(node: Node, name: str) -> Pin:
    require(name in node.pins, f"{node.name} is missing pin {name!r}")
    return node.pins[name]


def require_pin(node: Node, name: str, category: str, output: bool = False) -> Pin:
    result = pin(node, name)
    require(f'PinType.PinCategory="{category}"' in result.body, f"{node.name}.{name} must be {category}")
    direction = 'Direction="EGPD_Output"' in result.body
    require(direction == output, f"{node.name}.{name} direction changed")
    return result


def require_link(left: Node, left_pin: str, right: Node, right_pin: str, message: str) -> None:
    require((right.name, pin(right, right_pin).pin_id) in pin(left, left_pin).links, message)
    require((left.name, pin(left, left_pin).pin_id) in pin(right, right_pin).links, f"{message} (missing reciprocal link)")


def native_calls(nodes: dict[str, Node], expected_count: int) -> dict[str, Node]:
    require(len(nodes) == expected_count, f"Expected {expected_count} harvested nodes; found {len(nodes)}")
    entries = [node for node in nodes.values() if node.node_class.endswith("K2Node_FunctionEntry")]
    require(len(entries) == 1, "Harvest must retain exactly one function entry")
    calls: dict[str, Node] = {}
    for name in ("DoesSaveGameExist", "LoadGameFromSlot", "CreateSaveGameObject", "SaveGameToSlot"):
        node = one(nodes, f'MemberName="{name}"')
        require(node.node_class.endswith("K2Node_CallFunction"), f"{name} must be a native function call")
        require("/Script/Engine.GameplayStatics" in node.text, f"{name} parent must remain GameplayStatics")
        require_pin(node, "execute", "exec")
        require_pin(node, "then", "exec", output=True)
        calls[name] = node

    for name in ("DoesSaveGameExist", "LoadGameFromSlot", "SaveGameToSlot"):
        node = calls[name]
        require_pin(node, "SlotName", "string")
        user = require_pin(node, "UserIndex", "int")
        require('PinType.bIsConst=True' in user.body, f"{name}.UserIndex must remain const")
        require('DefaultValue="0"' in user.body, f"{name}.UserIndex must default to local user 0")

    require_pin(calls["DoesSaveGameExist"], "ReturnValue", "bool", output=True)
    require_pin(calls["SaveGameToSlot"], "SaveGameObject", "object")
    require(SAVEGAME_CLASS in pin(calls["SaveGameToSlot"], "SaveGameObject").body, "Save input must accept base SaveGame")
    require_pin(calls["SaveGameToSlot"], "ReturnValue", "bool", output=True)
    load_result = require_pin(calls["LoadGameFromSlot"], "ReturnValue", "object", output=True)
    require(SAVEGAME_CLASS in load_result.body, "Load must return base SaveGame and remain explicitly cast")
    create_class = require_pin(calls["CreateSaveGameObject"], "SaveGameClass", "class")
    require(SAVEGAME_CLASS in create_class.body, "Create class pin must accept a SaveGame subclass")
    require_pin(calls["CreateSaveGameObject"], "ReturnValue", "object", output=True)
    return calls


def assert_native(path: Path) -> None:
    nodes = parse_graph(path)
    calls = native_calls(nodes, 5)
    require("DefaultObject=" not in pin(calls["CreateSaveGameObject"], "SaveGameClass").body, "Unconfigured native form must not silently select a storage class")
    require(SAVEGAME_CLASS in pin(calls["CreateSaveGameObject"], "ReturnValue").body, "Unconfigured Create return must remain base SaveGame")


def assert_storage(path: Path) -> None:
    nodes = parse_graph(path)
    calls = native_calls(nodes, 9)

    create_class = pin(calls["CreateSaveGameObject"], "SaveGameClass")
    create_result = pin(calls["CreateSaveGameObject"], "ReturnValue")
    require(f'DefaultObject="{STORAGE_OBJECT}"' in create_class.body, "Create must select SG_EDD_RepositoryStorage")
    require(STORAGE_CLASS in create_result.body, "Configured Create return must specialize to repository storage")

    casts = [node for node in nodes.values() if node.node_class.endswith("K2Node_DynamicCast")]
    require(len(casts) == 1, f"Expected one storage cast; found {len(casts)}")
    cast = casts[0]
    require(f'TargetType="{STORAGE_CLASS}"' in cast.text, "Load cast target must be repository storage")
    require_link(calls["LoadGameFromSlot"], "then", cast, "execute", "Load completion must execute the cast")
    require_link(calls["LoadGameFromSlot"], "ReturnValue", cast, "Object", "Loaded SaveGame must be the cast object")
    cast_outputs = [
        (name, value) for name, value in cast.pins.items()
        if name.startswith("AsSG") and STORAGE_CLASS in value.body
    ]
    require(len(cast_outputs) == 1, "Cast must expose exactly one typed repository-storage output")

    storage_get = one(nodes, 'VariableReference=(MemberName="ProbeStorageV1"')
    storage_output = require_pin(storage_get, "ProbeStorageV1", "object", output=True)
    require(STORAGE_CLASS in storage_output.body, "Typed probe member must remain repository storage")
    property_nodes = [node for node in nodes.values() if 'MemberName="RepositorySchemaVersion"' in node.text]
    require(len(property_nodes) == 2, "RepositorySchemaVersion requires exactly one getter and setter form")
    getter = next(node for node in property_nodes if node.node_class.endswith("K2Node_VariableGet"))
    setter = next(node for node in property_nodes if node.node_class.endswith("K2Node_VariableSet"))
    require_pin(getter, "RepositorySchemaVersion", "int", output=True)
    require_pin(setter, "RepositorySchemaVersion", "int")
    require_pin(setter, "execute", "exec")
    require_pin(setter, "then", "exec", output=True)
    for node in (getter, setter):
        target = require_pin(node, "self", "object")
        require(STORAGE_CLASS in target.body, f"{node.name}.self must require typed repository storage")
        require_link(storage_get, "ProbeStorageV1", node, "self", f"Typed storage must target {node.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--storage", required=True, type=Path)
    args = parser.parse_args()
    assert_native(args.native)
    assert_storage(args.storage)
    print("Repository SaveGame node-form contracts passed.")


if __name__ == "__main__":
    main()
