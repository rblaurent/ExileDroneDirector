"""Semantic contracts for the legacy-array to ST_EDD_Waypoint Blueprint bridge."""

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
    body: str
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
    nodes = {}
    for match in BLOCK_RE.finditer(path.read_text(encoding="utf-8")):
        pins = {}
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
            pins[name_match.group(1)] = Pin(id_match.group(1), body, links)
        nodes[match.group("name")] = Node(
            match.group("name"), match.group("class"), match.group(0), pins
        )
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


def assert_contract(nodes: dict[str, Node], has_entry: bool) -> None:
    require(len(nodes) == (40 if has_entry else 39), f"Unexpected node count: {len(nodes)}")
    entries = [n for n in nodes.values() if 'FunctionReference=(MemberName="SyncDraftWaypointsV1")' in n.text]
    require(len(entries) == (1 if has_entry else 0), "Function entry inclusion changed")
    if not has_entry:
        unknown = sorted(
            {target for node in nodes.values() for value in node.pins.values() for target, _ in value.links}
            - set(nodes)
        )
        require(not unknown, f"Paste graph contains external node links: {unknown}")

    legacy = [
        "DraftWaypointIds",
        "DraftWaypointTransforms",
        "DraftWaypointFocalLengths",
        "DraftWaypointApertures",
        "DraftWaypointFocusDistances",
        "DraftWaypointHoldSeconds",
    ]
    getters = {name: one(nodes, f'VariableReference=(MemberName="{name}"') for name in legacy}
    lengths = sorted(
        [n for n in nodes.values() if 'MemberName="Array_Length"' in n.text],
        key=lambda n: int(n.name.rsplit("_", 1)[1]),
    )
    equals = sorted(
        [n for n in nodes.values() if 'MemberName="EqualEqual_IntInt"' in n.text],
        key=lambda n: int(n.name.rsplit("_", 1)[1]),
    )
    branches = sorted(
        [n for n in nodes.values() if n.node_class.endswith("K2Node_IfThenElse")],
        key=lambda n: int(n.name.rsplit("_", 1)[1]),
    )
    require(len(lengths) == 6, "All six legacy channels need a length probe")
    require(len(equals) == 5 and len(branches) == 5, "Five exact length guards are required")

    for index, name in enumerate(legacy):
        require_link(getters[name], name, lengths[index], "TargetArray", f"{name} must feed its length probe")
    for index, name in enumerate(legacy[1:]):
        require_link(lengths[0], "ReturnValue", equals[index], "A", "ID length must be the canonical length")
        require_link(lengths[index + 1], "ReturnValue", equals[index], "B", f"{name} length must be compared")
        require_link(equals[index], "ReturnValue", branches[index], "Condition", "Equality must drive its branch")
        failure = one(nodes, f"[EDD] Waypoint struct sync rejected: {name} length mismatch")
        require_link(branches[index], "else", failure, "execute", "Mismatch must reject without mutation")

    if has_entry:
        require_link(entries[0], "then", branches[0], "execute", "Entry must begin validation")
    else:
        require(not branches[0].pins["execute"].links, "Paste graph entry pin must be intentionally unwired")
    for before, after in zip(branches, branches[1:]):
        require_link(before, "then", after, "execute", "Validation guards must be ordered before mutation")

    clear = one(nodes, 'MemberName="Array_Clear"')
    require("NewItem" not in clear.pins and "ReturnValue" not in clear.pins, "Array_Clear has stale Array_Add pins")
    require_link(branches[-1], "then", clear, "execute", "Only the fully valid path may clear typed waypoints")

    typed_getters = [n for n in nodes.values() if 'VariableReference=(MemberName="DraftWaypointsV1"' in n.text]
    require(len(typed_getters) == 2, "Typed array must have dedicated Clear and Add getters")
    clear_getter = next(n for n in typed_getters if (clear.name, clear.pins["TargetArray"].pin_id) in n.pins["DraftWaypointsV1"].links)
    require_link(clear_getter, "DraftWaypointsV1", clear, "TargetArray", "Clear must mutate DraftWaypointsV1")

    foreach = one(nodes, "StandardMacros:ForEachLoop")
    require_link(clear, "then", foreach, "Exec", "Typed rebuild must start after Clear")
    require_link(getters[legacy[0]], legacy[0], foreach, "Array", "IDs must drive stable source order")

    items = sorted(
        [n for n in nodes.values() if n.node_class.endswith("K2Node_GetArrayItem")],
        key=lambda n: int(n.name.rsplit("_", 1)[1]),
    )
    require(len(items) == 5, "Every non-ID legacy channel needs an indexed read")
    for index, name in enumerate(legacy[1:]):
        require_link(getters[name], name, items[index], "Array", f"{name} must feed its indexed read")
        require_link(foreach, "Array Index", items[index], "Dimension 1", "All channels must use the same index")

    make_nodes = [n for n in nodes.values() if n.node_class.endswith("K2Node_MakeStruct")]
    require(len(make_nodes) == 1, f"Expected one Make ST_EDD_Waypoint node; found {len(make_nodes)}")
    make = make_nodes[0]
    require_link(foreach, "Array Element", make, "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE", "ID must map exactly")
    make_pins = [
        "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9",
        "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B",
        "Aperture_10_949C579344F8DFA750F1948051A417B2",
        "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F",
        "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB",
    ]
    for item, make_pin in zip(items, make_pins):
        require_link(item, "Output", make, make_pin, f"{make_pin} must preserve its source value")

    add = one(nodes, 'MemberName="Array_Add"')
    add_getter = next(n for n in typed_getters if (add.name, add.pins["TargetArray"].pin_id) in n.pins["DraftWaypointsV1"].links)
    require_link(foreach, "LoopBody", add, "execute", "Each source index must append once")
    require_link(add_getter, "DraftWaypointsV1", add, "TargetArray", "Add must mutate DraftWaypointsV1")
    require_link(make, "ST_EDD_Waypoint", add, "NewItem", "The authored struct must be appended")
    success = one(nodes, "[EDD] Waypoint struct sync complete")
    require_link(foreach, "Completed", success, "execute", "Successful completion needs an explicit diagnostic")

    waypoint_marker = "ST_EDD_Waypoint.ST_EDD_Waypoint'"
    for node, pin_name in ((clear, "TargetArray"), (add, "TargetArray"), (add, "NewItem")):
        require(waypoint_marker in node.pins[pin_name].body, f"{node.name}.{pin_name} lost the waypoint struct type")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste-graph", type=Path)
    args = parser.parse_args()
    assert_contract(parse(args.graph), has_entry=True)
    if args.paste_graph is not None:
        assert_contract(parse(args.paste_graph), has_entry=False)
    print("Waypoint struct sync graph contracts passed.")


if __name__ == "__main__":
    main()
