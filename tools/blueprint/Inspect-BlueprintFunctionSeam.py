"""Inspect an exported Blueprint function's native-entry seam deterministically."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


def load_contracts(project_root: Path):
    path = project_root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_seam_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def position(node):
    x = re.search(r"(?m)^\s*NodePosX=(-?\d+)\s*$", node.text)
    y = re.search(r"(?m)^\s*NodePosY=(-?\d+)\s*$", node.text)
    return (int(x.group(1)) if x else 0, int(y.group(1)) if y else 0)


def pin_id(node, pin_name):
    match = re.search(r"PinId=([0-9A-F]{32})", node.pins[pin_name].body)
    if match is None:
        raise RuntimeError(f"{node.name}.{pin_name} has no PinId")
    return match.group(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--function", required=True)
    parser.add_argument("--root-marker", default="")
    args = parser.parse_args()

    contracts = load_contracts(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    entries = [
        node for node in nodes.values()
        if "K2Node_FunctionEntry" in node.node_class
        and f'MemberName="{args.function}"' in node.text
    ]
    contracts.require(len(entries) == 1, f"expected one native entry, found {len(entries)}")
    roots = [
        node for node in nodes.values()
        if args.root_marker in node.text
        and "execute" in node.pins
        and not node.pins["execute"].links
    ]
    contracts.require(len(roots) == 1, f"expected one exposed root, found {len(roots)}")

    entry = entries[0]
    root = roots[0]
    entry_x, entry_y = position(entry)
    root_x, root_y = position(root)
    print(json.dumps({
        "function": args.function,
        "entry": {
            "name": entry.name,
            "class": entry.node_class.rsplit(".", 1)[-1],
            "x": entry_x,
            "y": entry_y,
            "pin": pin_id(entry, "then"),
        },
        "root": {
            "name": root.name,
            "class": root.node_class.rsplit(".", 1)[-1],
            "x": root_x,
            "y": root_y,
            "pin": pin_id(root, "execute"),
        },
        "suggestedEntry": {"x": root_x - 256, "y": root_y},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
