"""Semantic contracts for repository SaveGame slot-read adapter graphs."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


STORAGE_CLASS = (
    "/Script/Engine.BlueprintGeneratedClass'"
    "/Game/Mods/ExileDroneDirector/Server/Persistence/"
    "SG_EDD_RepositoryStorage.SG_EDD_RepositoryStorage_C'"
)
SAVEGAME_CLASS = "/Script/CoreUObject.Class'/Script/Engine.SaveGame'"
FIELDS = (
    ("RepositorySchemaVersion", "SchemaVersion", "int", False),
    ("Generation", "Generation", "int", False),
    ("Committed", "Committed", "bool", False),
    ("SnapshotHash", "SnapshotHash", "string", False),
    ("RecordEnvelopes", "RecordEnvelopes", "string", True),
    ("TombstoneFlypathIds", "TombstoneFlypathIds", "string", True),
)


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_savegame_adapter_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nodes_with(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def one(c, nodes, marker: str):
    matches = nodes_with(nodes, marker)
    c.require(len(matches) == 1, f"Expected one node containing {marker!r}; found {len(matches)}")
    return matches[0]


def variable(c, nodes, name: str, node_class: str):
    matches = [
        node for node in nodes.values()
        if node_class in node.node_class
        and f'VariableReference=(MemberName="{name}"' in node.text
    ]
    c.require(len(matches) == 1, f"Expected one {node_class} for {name}; found {len(matches)}")
    return matches[0]


def exact_default(c, node, pin_name: str, expected: str) -> None:
    body = c.pin(node, pin_name).body
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', body)
    c.require(match is not None and match.group(1) == expected, f"{node.name}.{pin_name} default changed")


def pin_type(c, node, pin_name: str, category: str, *, array: bool = False, output: bool = False):
    body = c.pin(node, pin_name).body
    c.require(f'PinType.PinCategory="{category}"' in body, f"{node.name}.{pin_name} category changed")
    container = "Array" if array else "None"
    c.require(f"PinType.ContainerType={container}" in body, f"{node.name}.{pin_name} container changed")
    c.require(('Direction="EGPD_Output"' in body) == output, f"{node.name}.{pin_name} direction changed")
    return body


def assert_closed(c, nodes, expected: int, function: str, paste: bool) -> None:
    c.require(len(nodes) == expected, f"{function}: expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for item in node.pins.values()
        for target, _ in item.links
        if target not in known
    }
    c.require(not external, f"{function}: external links {sorted(external)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), f"{function}: entry count changed")
    if not paste:
        c.require(f'MemberName="{function}"' in entries[0].text, f"{function}: wrong entry")
    text = "\n".join(node.text for node in nodes.values())
    c.require("bOrphanedPin=True" not in text, f"{function}: orphaned pin")
    c.require("ErrorType=" not in text, f"{function}: retained Blueprint error metadata")


def assert_slot_reader(c, nodes, prefix: str, paste: bool) -> None:
    function = f"ReadRepositoryStorageSlot{prefix}V1"
    assert_closed(c, nodes, 18 if paste else 19, function, paste)
    slot = f"EDD_Repository_{prefix}"
    exists = one(c, nodes, 'MemberName="DoesSaveGameExist"')
    load = one(c, nodes, 'MemberName="LoadGameFromSlot"')
    for native in (exists, load):
        c.require("/Script/Engine.GameplayStatics" in native.text, "SaveGame read parent changed")
        pin_type(c, native, "execute", "exec")
        pin_type(c, native, "then", "exec", output=True)
        exact_default(c, native, "SlotName", slot)
        exact_default(c, native, "UserIndex", "0")
        c.require("PinType.bIsConst=True" in c.pin(native, "UserIndex").body, "UserIndex must remain const")
    pin_type(c, exists, "ReturnValue", "bool", output=True)
    load_result = pin_type(c, load, "ReturnValue", "object", output=True)
    c.require(SAVEGAME_CLASS in load_result, "Load return must remain base SaveGame")

    exists_set = variable(c, nodes, f"ScratchStorage{prefix}ExistsV1", "K2Node_VariableSet")
    branch_nodes = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branch_nodes) == 1, "Slot read needs one existence branch")
    branch = branch_nodes[0]
    if paste:
        c.require(not c.pin(exists, "execute").links, "Slot-reader paste root changed")
    else:
        entry = one(c, nodes, f'FunctionReference=(MemberName="{function}")')
        c.require_link(entry, "then", exists, "execute", "Slot-reader entry changed")
    c.require_link(exists, "then", exists_set, "execute", "Existence result must be staged first")
    c.require_link(exists, "ReturnValue", exists_set, f"ScratchStorage{prefix}ExistsV1", "Existence state source changed")
    c.require_link(exists_set, "then", branch, "execute", "Existence branch order changed")
    c.require_link(exists, "ReturnValue", branch, "Condition", "Existence branch condition changed")
    c.require_link(branch, "then", load, "execute", "Only existing slots may load")
    c.require(not c.pin(branch, "else").links, "Missing slot must terminate without load")

    casts = [node for node in nodes.values() if "K2Node_DynamicCast" in node.node_class]
    c.require(len(casts) == 1, "Slot read needs one typed storage cast")
    cast = casts[0]
    c.require(f'TargetType="{STORAGE_CLASS}"' in cast.text, "Storage cast target changed")
    c.require_link(load, "then", cast, "execute", "Load completion must execute cast")
    c.require_link(load, "ReturnValue", cast, "Object", "Loaded object must feed cast")
    c.require(not c.pin(cast, "CastFailed").links, "Cast failure must terminate invalid slot staging")
    cast_outputs = [name for name, item in cast.pins.items() if name.startswith("AsSG") and STORAGE_CLASS in item.body]
    c.require(len(cast_outputs) == 1, "Cast typed output changed")

    storage_set = variable(c, nodes, f"ScratchStorage{prefix}V1", "K2Node_VariableSet")
    storage_input = pin_type(c, storage_set, f"ScratchStorage{prefix}V1", "object")
    storage_output = pin_type(c, storage_set, "Output_Get", "object", output=True)
    c.require(STORAGE_CLASS in storage_input and STORAGE_CLASS in storage_output, "Scratch storage type changed")
    c.require_link(cast, "then", storage_set, "execute", "Successful cast must stage typed object")
    c.require_link(cast, cast_outputs[0], storage_set, f"ScratchStorage{prefix}V1", "Cast output must stage typed object")

    chain = [storage_set]
    for storage_name, scratch_suffix, category, is_array in FIELDS:
        props = [
            node for node in nodes.values()
            if "K2Node_VariableGet" in node.node_class
            and f'MemberParent="{STORAGE_CLASS}"' in node.text
            and f'MemberName="{storage_name}"' in node.text
        ]
        c.require(len(props) == 1, f"Expected one typed storage getter for {storage_name}")
        prop = props[0]
        value = pin_type(c, prop, storage_name, category, array=is_array, output=True)
        target = pin_type(c, prop, "self", "object")
        c.require(STORAGE_CLASS in target, f"{storage_name} target type changed")
        c.require_link(storage_set, "Output_Get", prop, "self", f"{storage_name} must read staged storage")
        scratch_name = f"ScratchStorage{prefix}{scratch_suffix}V1"
        setter = variable(c, nodes, scratch_name, "K2Node_VariableSet")
        pin_type(c, setter, scratch_name, category, array=is_array)
        c.require_link(prop, storage_name, setter, scratch_name, f"{storage_name} staging source changed")
        chain.append(setter)
    for left, right in zip(chain, chain[1:]):
        c.require_link(left, "then", right, "execute", "Slot field staging order changed")
    c.require(not c.pin(chain[-1], "then").links, "Slot reader must terminate after complete staging")


def assert_coordinator(c, nodes, paste: bool) -> None:
    function = "ReadRepositoryStorageSlotsV1"
    assert_closed(c, nodes, 4 if paste else 5, function, paste)
    names = (
        "ResetRepositoryStateV1",
        "ReadRepositoryStorageSlotAV1",
        "ReadRepositoryStorageSlotBV1",
        "ValidateStorageHeadersV1",
    )
    calls = [one(c, nodes, f'MemberName="{name}"') for name in names]
    for node, name in zip(calls, names):
        c.require('bSelfContext=True' in node.text, f"{name} must remain a self call")
    if paste:
        c.require(not c.pin(calls[0], "execute").links, "Coordinator paste root changed")
    else:
        entry = one(c, nodes, f'FunctionReference=(MemberName="{function}")')
        c.require_link(entry, "then", calls[0], "execute", "Coordinator entry changed")
    for left, right in zip(calls, calls[1:]):
        c.require_link(left, "then", right, "execute", "Coordinator A/B/header order changed")
    c.require(not c.pin(calls[-1], "then").links, "Coordinator must stop before recovery")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument(
        "--only",
        choices=("all", "a", "b", "coordinator"),
        default="all",
    )
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    if args.only in {"all", "a"}:
        assert_slot_reader(c, c.parse_graph(args.input_dir / f"read-repository-storage-slot-a-v1{suffix}.eddgraph"), "A", args.paste)
    if args.only in {"all", "b"}:
        assert_slot_reader(c, c.parse_graph(args.input_dir / f"read-repository-storage-slot-b-v1{suffix}.eddgraph"), "B", args.paste)
    if args.only in {"all", "coordinator"}:
        assert_coordinator(c, c.parse_graph(args.input_dir / f"read-repository-storage-slots-v1{suffix}.eddgraph"), args.paste)
    print("Repository SaveGame adapter graph contracts passed")


if __name__ == "__main__":
    main()
