"""Require every serialized Blueprint graph link to be resolved and reciprocal."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_contracts(path: Path):
    spec = importlib.util.spec_from_file_location("edd_graph_link_contracts", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    args = parser.parse_args()

    contracts = load_contracts(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    pin_index = {}
    for node in nodes.values():
        for pin in node.pins.values():
            match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
            contracts.require(match is not None, f"pin identity missing: {node.name}.{pin.name}")
            pin_index[(node.name, match.group(1))] = (node, pin)

    directed_links = 0
    for node in nodes.values():
        for pin in node.pins.values():
            source_is_output = 'Direction="EGPD_Output"' in pin.body
            source_id = re.search(r"PinId=([0-9A-F]{32})", pin.body).group(1)
            for link in pin.links:
                directed_links += 1
                contracts.require(link in pin_index, f"unresolved link: {node.name}.{pin.name} -> {link}")
                target_node, target_pin = pin_index[link]
                target_is_output = 'Direction="EGPD_Output"' in target_pin.body
                contracts.require(
                    source_is_output != target_is_output,
                    f"same-direction link: {node.name}.{pin.name} -> {target_node.name}.{target_pin.name}",
                )
                contracts.require(
                    (node.name, source_id) in target_pin.links,
                    f"non-reciprocal link: {node.name}.{pin.name} -> {target_node.name}.{target_pin.name}",
                )

    contracts.require(directed_links % 2 == 0, "directed link count must describe reciprocal pairs")
    print(f"Blueprint graph link integrity passed: {len(nodes)} nodes, {directed_links // 2} reciprocal links")


if __name__ == "__main__":
    main()
