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
    require(len(nodes) == (84 if has_entry else 83), f"Unexpected node count: {len(nodes)}")
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
    all_branches = sorted(
        [n for n in nodes.values() if n.node_class.endswith("K2Node_IfThenElse")],
        key=lambda n: int(n.name.rsplit("_", 1)[1]),
    )
    branches = all_branches[:5]
    require(len(lengths) == 6, "All six legacy channels need a length probe")
    require(len(equals) == 6, "Five length equalities plus one uniqueness equality are required")
    require(len(all_branches) == 16, "Five length, ten item, and one result branch are required")
    length_equals = equals[:5]

    for index, name in enumerate(legacy):
        require_link(getters[name], name, lengths[index], "TargetArray", f"{name} must feed its length probe")
    for index, name in enumerate(legacy[1:]):
        require_link(lengths[0], "ReturnValue", length_equals[index], "A", "ID length must be the canonical length")
        require_link(lengths[index + 1], "ReturnValue", length_equals[index], "B", f"{name} length must be compared")
        require_link(length_equals[index], "ReturnValue", branches[index], "Condition", "Equality must drive its branch")
        failure = one(nodes, f"[EDD] Waypoint struct sync rejected: {name} length mismatch")
        require_link(branches[index], "else", failure, "execute", "Mismatch must reject without mutation")

    if has_entry:
        require_link(entries[0], "then", branches[0], "execute", "Entry must begin validation")
    else:
        require(not branches[0].pins["execute"].links, "Paste graph entry pin must be intentionally unwired")
    for before, after in zip(branches, branches[1:]):
        require_link(before, "then", after, "execute", "Validation guards must be ordered before mutation")

    preflight_setters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet")
        and 'MemberName="WaypointPreflightValid"' in node.text
    ]
    require(len(preflight_setters) == 11, "Preflight needs one true initializer and ten failure setters")
    true_setters = [node for node in preflight_setters if 'PinName="WaypointPreflightValid"' in node.text and 'DefaultValue="true"' in node.text]
    false_setters = sorted(
        [node for node in preflight_setters if node not in true_setters],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    require(len(true_setters) == 1 and len(false_setters) == 10, "Preflight setter defaults changed")
    preflight_set_true = true_setters[0]
    require_link(branches[-1], "then", preflight_set_true, "execute", "Shape validation must initialize preflight")

    foreach_nodes = [node for node in nodes.values() if "StandardMacros:ForEachLoop" in node.text]
    require(len(foreach_nodes) == 2, "Preflight and rebuild each require a ForEachLoop")
    preflight_foreach = next(
        node
        for node in foreach_nodes
        if (node.name, node.pins["Exec"].pin_id) in preflight_set_true.pins["then"].links
    )
    require_link(preflight_set_true, "then", preflight_foreach, "Exec", "Preflight must start after true initialization")
    require_link(getters[legacy[0]], legacy[0], preflight_foreach, "Array", "IDs must drive preflight source order")

    id_positive = one(nodes, 'MemberName="Greater_IntInt"')
    id_find = one(nodes, 'MemberName="Array_Find"')
    unique_equal = equals[-1]
    require_link(preflight_foreach, "Array Element", id_positive, "A", "Each ID must be checked for positivity")
    require('DefaultValue="0"' in id_positive.pins["B"].body, "ID positivity must compare against zero")
    require_link(getters[legacy[0]], legacy[0], id_find, "TargetArray", "Uniqueness search must use the ID array")
    require_link(preflight_foreach, "Array Element", id_find, "ItemToFind", "Uniqueness search must use the current ID")
    require_link(id_find, "ReturnValue", unique_equal, "A", "First ID index must feed uniqueness equality")
    require_link(preflight_foreach, "Array Index", unique_equal, "B", "Current index must feed uniqueness equality")

    preflight_items = {}
    for name in legacy[2:]:
        candidates = [
            node
            for node in nodes.values()
            if node.node_class.endswith("K2Node_GetArrayItem")
            and (node.name, node.pins["Array"].pin_id) in getters[name].pins[name].links
            and (node.name, node.pins["Dimension 1"].pin_id) in preflight_foreach.pins["Array Index"].links
        ]
        require(len(candidates) == 1, f"{name} needs one preflight indexed read")
        preflight_items[name] = candidates[0]

    subtracts = sorted(
        [node for node in nodes.values() if 'MemberName="Subtract_DoubleDouble"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    finite_equals = sorted(
        [node for node in nodes.values() if 'MemberName="EqualEqual_DoubleDouble"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    positive_domains = sorted(
        [node for node in nodes.values() if 'MemberName="Greater_DoubleDouble"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    non_negative_domains = sorted(
        [node for node in nodes.values() if 'MemberName="GreaterEqual_DoubleDouble"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    require(len(subtracts) == 4 and len(finite_equals) == 4, "Every scalar needs a finite-value probe")
    require(len(positive_domains) == 2 and len(non_negative_domains) == 2, "Scalar domain comparators changed")

    scalar_names = legacy[2:]
    domain_nodes = (positive_domains[0], positive_domains[1], non_negative_domains[0], non_negative_domains[1])
    condition_nodes = [id_positive, unique_equal]
    for index, name in enumerate(scalar_names):
        item = preflight_items[name]
        subtract = subtracts[index]
        finite_equal = finite_equals[index]
        domain = domain_nodes[index]
        require_link(item, "Output", subtract, "A", f"{name} must feed finite subtraction A")
        require_link(item, "Output", subtract, "B", f"{name} must feed finite subtraction B")
        require_link(subtract, "ReturnValue", finite_equal, "A", f"{name} finite delta must equal zero")
        require('DefaultValue="0.0"' in finite_equal.pins["B"].body, f"{name} finite comparison must use zero")
        require_link(item, "Output", domain, "A", f"{name} must feed its domain check")
        require('DefaultValue="0.0"' in domain.pins["B"].body, f"{name} domain must compare against zero")
        condition_nodes.extend((finite_equal, domain))

    validation_branches = all_branches[5:15]
    result_branch = all_branches[15]
    require_link(preflight_foreach, "LoopBody", validation_branches[0], "execute", "Each item must enter validation")
    for index, (condition, branch, failure_set) in enumerate(zip(condition_nodes, validation_branches, false_setters)):
        require_link(condition, "ReturnValue", branch, "Condition", f"Preflight condition {index} must drive its branch")
        require_link(branch, "else", failure_set, "execute", f"Preflight failure {index} must invalidate the scan")
        require('DefaultValue="false"' in failure_set.pins["WaypointPreflightValid"].body, "Failure setter must write false")
    for before, after in zip(validation_branches, validation_branches[1:]):
        require_link(before, "then", after, "execute", "Preflight checks must be ordered")

    preflight_get = next(
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableGet")
        and 'MemberName="WaypointPreflightValid"' in node.text
    )
    require_link(preflight_foreach, "Completed", result_branch, "execute", "Preflight completion must gate mutation")
    require_link(preflight_get, "WaypointPreflightValid", result_branch, "Condition", "Preflight result must drive mutation gate")
    preflight_failure = one(nodes, "ID or scalar preflight failed")
    require_link(result_branch, "else", preflight_failure, "execute", "Invalid preflight must reject without mutation")

    clear = one(nodes, 'MemberName="Array_Clear"')
    require("NewItem" not in clear.pins and "ReturnValue" not in clear.pins, "Array_Clear has stale Array_Add pins")
    require_link(result_branch, "then", clear, "execute", "Only the fully valid path may clear typed waypoints")

    typed_getters = [n for n in nodes.values() if 'VariableReference=(MemberName="DraftWaypointsV1"' in n.text]
    require(len(typed_getters) == 2, "Typed array must have dedicated Clear and Add getters")
    clear_getter = next(n for n in typed_getters if (clear.name, clear.pins["TargetArray"].pin_id) in n.pins["DraftWaypointsV1"].links)
    require_link(clear_getter, "DraftWaypointsV1", clear, "TargetArray", "Clear must mutate DraftWaypointsV1")

    foreach = next(node for node in foreach_nodes if node is not preflight_foreach)
    require_link(clear, "then", foreach, "Exec", "Typed rebuild must start after Clear")
    require_link(getters[legacy[0]], legacy[0], foreach, "Array", "IDs must drive stable source order")

    items = []
    for name in legacy[1:]:
        candidates = [
            node
            for node in nodes.values()
            if node.node_class.endswith("K2Node_GetArrayItem")
            and (node.name, node.pins["Array"].pin_id) in getters[name].pins[name].links
            and (node.name, node.pins["Dimension 1"].pin_id) in foreach.pins["Array Index"].links
        ]
        require(len(candidates) == 1, f"{name} needs one rebuild indexed read")
        items.append(candidates[0])
        require_link(getters[name], name, items[-1], "Array", f"{name} must feed its indexed read")
        require_link(foreach, "Array Index", items[-1], "Dimension 1", "All channels must use the same index")

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
