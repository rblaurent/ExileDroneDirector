"""Semantic contracts for the live BP_EDD_PathPreview Blueprint graph slices."""

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


@dataclass(frozen=True)
class Pin:
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


def parse(path: Path) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    for match in BLOCK_RE.finditer(path.read_text(encoding="utf-8")):
        pins: dict[str, Pin] = {}
        for line in match.group(0).splitlines():
            pin_match = PIN_RE.match(line)
            if pin_match is None:
                continue
            body = pin_match.group("body")
            name_match = re.search(r'PinName="([^"]+)"', body)
            id_match = re.search(r'PinId=([0-9A-F]{32})', body)
            require(name_match is not None and id_match is not None, "Malformed serialized pin")
            links_match = re.search(r'LinkedTo=\(([^)]*)\)', body)
            links = tuple(re.findall(r'([A-Za-z0-9_]+) ([0-9A-F]{32}),', links_match.group(1))) if links_match else ()
            pins[name_match.group(1)] = Pin(id_match.group(1), links)
        nodes[match.group("name")] = Node(match.group("name"), match.group("class"), match.group(0), pins)
    return nodes


def one(nodes: dict[str, Node], marker: str) -> Node:
    matches = [node for node in nodes.values() if marker in node.text]
    require(len(matches) == 1, f"Expected one node matching {marker!r}; found {len(matches)}")
    return matches[0]


def require_link(left: Node, left_pin: str, right: Node, right_pin: str, message: str) -> None:
    require(left_pin in left.pins, f"{left.name} has no {left_pin} pin")
    require(right_pin in right.pins, f"{right.name} has no {right_pin} pin")
    require((right.name, right.pins[right_pin].pin_id) in left.pins[left_pin].links, message)
    require(
        (left.name, left.pins[left_pin].pin_id) in right.pins[right_pin].links,
        f"{message} (missing reciprocal link)",
    )


def assert_clear_contract(nodes: dict[str, Node]) -> None:
    require(len(nodes) == 5, f"ClearPreviewV1 must remain a five-node graph; found {len(nodes)}")
    entry = one(nodes, 'FunctionReference=(MemberName="ClearPreviewV1")')
    waypoint = one(nodes, 'VariableReference=(MemberName="WaypointMarkersV1"')
    segment = one(nodes, 'VariableReference=(MemberName="SegmentLinesV1"')
    clears = [node for node in nodes.values() if 'MemberName="ClearInstances"' in node.text]
    require(len(clears) == 2, f"Expected two ClearInstances calls; found {len(clears)}")

    waypoint_clear = next(node for node in clears if (node.name, node.pins["self"].pin_id) in waypoint.pins["WaypointMarkersV1"].links)
    segment_clear = next(node for node in clears if (node.name, node.pins["self"].pin_id) in segment.pins["SegmentLinesV1"].links)

    require_link(waypoint, "WaypointMarkersV1", waypoint_clear, "self", "Waypoint pool must target its own clear call")
    require_link(segment, "SegmentLinesV1", segment_clear, "self", "Segment pool must target its own clear call")
    require_link(entry, "then", waypoint_clear, "execute", "ClearPreviewV1 must clear waypoint markers first")
    require_link(waypoint_clear, "then", segment_clear, "execute", "Waypoint clear must flow into segment clear")
    require(not segment_clear.pins["then"].links, "ClearPreviewV1 must end after clearing segment lines")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", type=Path, required=True)
    args = parser.parse_args()
    assert_clear_contract(parse(args.clear))
    print("Path-preview ClearPreviewV1 semantic contracts valid")


if __name__ == "__main__":
    main()
