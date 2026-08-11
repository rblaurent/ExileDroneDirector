"""Structural contracts for the native nodes required by JSON decoders."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_decoder_native_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()

    c = load_contracts(args.project_root)
    nodes = c.parse_graph(args.forms)
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(nodes) in (3, 4), f"Decoder native fixture must contain 3 forms and optional entry; found {len(nodes)}")
    c.require(len(entries) <= 1, "Decoder native fixture contains multiple function entries")
    if entries:
        c.require('MemberName="ProbeJsonNodesV1"' in entries[0].text, "Accepted fixture entry changed")
    text = "\n".join(node.text for node in nodes.values())
    c.require("bOrphanedPin=True" not in text, "Decoder native fixture contains orphaned pins")
    c.require(not any(pin.links for node in nodes.values() for pin in node.pins.values()), "Probe forms must be unlinked")

    item = c.one(nodes, "/Script/BlueprintGraph.K2Node_GetArrayItem")
    array_body = c.pin(item, "Array").body
    output_body = c.pin(item, "Output").body
    c.require("PinType.ContainerType=Array" in array_body, "Array input lost its container")
    typed_float = (
        'PinType.PinCategory="real"' in array_body
        and 'PinType.PinSubCategory="float"' in array_body
        and 'PinType.PinCategory="real"' in output_body
        and 'PinType.PinSubCategory="float"' in output_body
    )
    canonical_wildcard = (
        'PinType.PinCategory="wildcard"' in array_body
        and 'PinType.PinCategory="wildcard"' in output_body
    )
    c.require(typed_float or canonical_wildcard, "Array item input/output specialization diverged")
    c.require('DefaultValue="0"' in c.pin(item, "Dimension 1").body, "Probe index must be deterministic")

    equal = c.one(nodes, 'MemberName="EqualEqual_StrStr"')
    c.require("/Script/Engine.KismetStringLibrary" in equal.text, "String equality parent changed")
    for name in ("A", "B"):
        c.require('PinType.PinCategory="string"' in c.pin(equal, name).body, f"{name} must be string")
    c.require('PinType.PinCategory="bool"' in c.pin(equal, "ReturnValue").body, "String equality result must be bool")

    quat = c.one(nodes, 'MemberName="Quat_Rotator"')
    q = c.pin(quat, "Q").body
    c.require("/Script/CoreUObject.Quat" in q, "Quat_Rotator Q pin changed")
    c.require("bIsReference=True" in q and "bIsConst=True" in q, "Quat_Rotator Q must remain const-ref")
    c.require("SubPins=(" in q, "Quat_Rotator input must remain explicitly split")
    subpins_match = re.search(r"SubPins=\(([^)]*)\)", q)
    c.require(subpins_match is not None, "Quat_Rotator Q sub-pin list is malformed")
    serialized_subpins = set(re.findall(rf"{re.escape(quat.name)} ([0-9A-F]{{32}})", subpins_match.group(1)))
    expected_subpins = {
        re.search(r"PinId=([0-9A-F]{32})", c.pin(quat, name).body).group(1)
        for name in ("Q_X", "Q_Y", "Q_Z", "Q_W")
    }
    c.require(serialized_subpins == expected_subpins, "Quat_Rotator Q contains stale sub-pin GUIDs")
    for name in ("Q_X", "Q_Y", "Q_Z", "Q_W"):
        body = c.pin(quat, name).body
        c.require('PinType.PinSubCategory="float"' in body, f"{name} must be float")
        parent_match = re.search(rf"ParentPin={re.escape(quat.name)} ([0-9A-F]{{32}})", body)
        c.require(parent_match is not None, f"{name} parent reference is malformed")
        q_id = re.search(r"PinId=([0-9A-F]{32})", q).group(1)
        c.require(parent_match.group(1) == q_id, f"{name} contains a stale parent GUID")
    c.require("/Script/CoreUObject.Rotator" in c.pin(quat, "ReturnValue").body, "Quat_Rotator result changed")

    print("Repository decoder native node-form contracts passed")


if __name__ == "__main__":
    main()
