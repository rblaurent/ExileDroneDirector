#!/usr/bin/env python3
"""Relocate only an entryless Blueprint body's exposed exec root near its bounds center.

Enhanced centers a pasted selection beneath the cursor. Large deterministic graphs
therefore place a left-edge root thousands of graph units away from the immutable
native function entry. This installation-only transform preserves every node and
pin identity and every link; it changes only the exposed root's grid-aligned visual
position so the native seam can be connected without long mouse-driven relocation.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_prepare_paste_contracts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def position(text: str) -> tuple[int, int]:
    x = re.search(r"(?m)^\s*NodePosX=(-?\d+)\s*$", text)
    y = re.search(r"(?m)^\s*NodePosY=(-?\d+)\s*$", text)
    return (int(x.group(1)) if x else 0, int(y.group(1)) if y else 0)


def replace_position(text: str, x: int, y: int) -> str:
    lines = text.splitlines()
    lines = [line for line in lines if not re.match(r"^\s*NodePos[XY]=-?\d+\s*$", line)]
    insert_at = next(
        (index + 1 for index, line in enumerate(lines) if "ExportPath=" in line),
        1,
    )
    lines[insert_at:insert_at] = [f"   NodePosX={x}", f"   NodePosY={y}"]
    return "\r\n".join(lines) + "\r\n"


def round_grid(value: float) -> int:
    return int(round(value / 16.0) * 16)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--root-offset-x", type=int, default=0)
    parser.add_argument("--root-offset-y", type=int, default=0)
    args = parser.parse_args()

    contracts = load_contracts(args.project_root.resolve())
    source = args.source.resolve()
    nodes = contracts.parse_graph(source)
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(not entries, "installation paste source must not contain a function entry")
    roots = [
        node
        for node in nodes.values()
        if "execute" in node.pins and not node.pins["execute"].links
    ]
    contracts.require(len(roots) == 1, f"expected one exposed execution root, found {len(roots)}")

    positions = [position(node.text) for node in nodes.values()]
    center_x = round_grid((min(x for x, _ in positions) + max(x for x, _ in positions)) / 2.0)
    center_y = round_grid((min(y for _, y in positions) + max(y for _, y in positions)) / 2.0)
    target_x = center_x + args.root_offset_x
    target_y = center_y + args.root_offset_y
    contracts.require(target_x % 16 == 0 and target_y % 16 == 0, "root target must be grid aligned")
    root = roots[0]
    old_x, old_y = position(root.text)

    source_text = source.read_text(encoding="utf-8-sig")
    replacement = replace_position(root.text, target_x, target_y).rstrip("\r\n")
    if source_text.count(root.text) != 1:
        raise RuntimeError("exposed root block is not unique in source text")
    output = source_text.replace(root.text, replacement, 1)
    destination = args.destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output, encoding="utf-8", newline="")

    transformed = contracts.parse_graph(destination)
    contracts.require(len(transformed) == len(nodes), "node count changed during root relocation")
    contracts.require(set(transformed) == set(nodes), "node identities changed during root relocation")
    transformed_root = transformed[root.name]
    contracts.require(position(transformed_root.text) == (target_x, target_y), "root relocation failed")
    for name, node in nodes.items():
        if name == root.name:
            continue
        contracts.require(transformed[name].text == node.text, f"non-root node changed: {name}")

    print(
        "EDD_BLUEPRINT_PASTE_PREPARED|"
        f"NODES:{len(nodes)}|ROOT:{root.name}|FROM:{old_x},{old_y}|TO:{target_x},{target_y}|"
        f"DESTINATION:{destination}"
    )


if __name__ == "__main__":
    main()
