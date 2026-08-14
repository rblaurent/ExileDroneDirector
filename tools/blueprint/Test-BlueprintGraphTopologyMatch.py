"""Compare an Unreal round-trip graph with its deterministic topology reference."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_contracts(path: Path):
    spec = importlib.util.spec_from_file_location("edd_graph_topology_contracts", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_id(pin) -> str:
    match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
    if match is None:
        raise AssertionError("pin identity missing")
    return match.group(1)


def topology(nodes):
    pin_index = {
        (node.name, pin_id(pin)): (node.name, pin.name)
        for node in nodes.values()
        for pin in node.pins.values()
    }
    result = {}
    for node in nodes.values():
        node_class = node.node_class.split(".")[-1]
        pins = {}
        for pin in node.pins.values():
            direction = "output" if 'Direction="EGPD_Output"' in pin.body else "input"
            links = tuple(sorted(pin_index[link] for link in pin.links))
            pins[pin.name] = (direction, links)
        result[node.name] = (node_class, pins)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    args = parser.parse_args()

    contracts = load_contracts(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    expected = topology(contracts.parse_graph(args.expected))
    actual = topology(contracts.parse_graph(args.actual))
    contracts.require(actual.keys() == expected.keys(), "node identities changed during Unreal round trip")
    mismatches = []
    for name in expected:
        expected_class, expected_pins = expected[name]
        actual_class, actual_pins = actual[name]
        contracts.require(actual_class == expected_class, f"node class changed: {name}")
        contracts.require(actual_pins.keys() == expected_pins.keys(), f"pin identities changed: {name}")
        for pin_name in expected_pins:
            if actual_pins[pin_name] != expected_pins[pin_name]:
                mismatches.append(f"{name}.{pin_name}: {actual_pins[pin_name]} != {expected_pins[pin_name]}")
    contracts.require(not mismatches, "topology changed:\n" + "\n".join(mismatches))
    print(f"Blueprint graph topology match passed: {len(actual)} nodes")


if __name__ == "__main__":
    main()
