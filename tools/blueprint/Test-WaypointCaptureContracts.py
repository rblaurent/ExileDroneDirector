"""Semantic contracts for the client-local waypoint capture vertical slice."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


BLOCK_RE = re.compile(
    r"^Begin Object Class=(?P<class>\S+) Name=\"(?P<name>[^\"]+)\".*?^End Object\r?$",
    re.MULTILINE | re.DOTALL,
)
PIN_LINE_RE = re.compile(r'^\s*CustomProperties Pin \((?P<body>.*)\)$')


@dataclass(frozen=True)
class Pin:
    name: str
    body: str
    links: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Node:
    name: str
    node_class: str
    text: str
    pins: dict[str, Pin]


def parse_graph(path: Path) -> dict[str, Node]:
    text = path.read_text(encoding="utf-8")
    nodes: dict[str, Node] = {}
    for match in BLOCK_RE.finditer(text):
        pins: dict[str, Pin] = {}
        for line in match.group(0).splitlines():
            pin_match = PIN_LINE_RE.match(line)
            if pin_match is None:
                continue
            body = pin_match.group("body")
            name_match = re.search(r'PinName="([^"]+)"', body)
            id_match = re.search(r"PinId=([0-9A-F]{32})", body)
            if name_match is None or id_match is None:
                fail(f"Malformed pin in {match.group('name')}")
            links_match = re.search(r"LinkedTo=\(([^)]*)\)", body)
            links = tuple(
                re.findall(r"([A-Za-z0-9_]+) ([0-9A-F]{32}),", links_match.group(1))
            ) if links_match else ()
            pins[name_match.group(1)] = Pin(name_match.group(1), body, links)
        name = match.group("name")
        nodes[name] = Node(name, match.group("class"), match.group(0), pins)
    return nodes


def fail(message: str) -> None:
    raise RuntimeError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def one(nodes: dict[str, Node], marker: str) -> Node:
    matches = [node for node in nodes.values() if marker in node.text]
    require(len(matches) == 1, f"Expected one node containing {marker!r}; found {len(matches)}")
    return matches[0]


def pin(node: Node, name: str) -> Pin:
    require(name in node.pins, f"{node.name} is missing pin {name}")
    return node.pins[name]


def linked(left: Node, left_pin: str, right: Node, right_pin: str) -> bool:
    right_id_match = re.search(r"PinId=([0-9A-F]{32})", pin(right, right_pin).body)
    require(right_id_match is not None, f"{right.name}.{right_pin} has no id")
    return (right.name, right_id_match.group(1)) in pin(left, left_pin).links


def require_link(left: Node, left_pin: str, right: Node, right_pin: str, message: str) -> None:
    require(linked(left, left_pin, right, right_pin), message)
    require(linked(right, right_pin, left, left_pin), f"{message} (missing reciprocal link)")


def assert_capture(nodes: dict[str, Node]) -> None:
    require(len(nodes) in {24, 25}, f"CaptureCurrentWaypoint expected 24 or 25 nodes; found {len(nodes)}")
    entries = [node for node in nodes.values() if 'FunctionReference=(MemberName="CaptureCurrentWaypoint")' in node.text]
    require(len(entries) <= 1, "Capture may contain at most one function entry")
    branch = one(nodes, "/Script/BlueprintGraph.K2Node_IfThenElse")
    camera = one(nodes, 'VariableReference=(MemberName="DroneCameraRef"')
    valid = one(nodes, 'MemberName="IsValid"')
    transform = one(nodes, 'MemberName="GetTransform"')
    increment = one(nodes, 'MemberName="Add_IntInt"')
    # Disambiguate the getter and setter selected by the shared variable marker.
    next_nodes = [node for node in nodes.values() if 'VariableReference=(MemberName="NextWaypointId"' in node.text]
    require(len(next_nodes) == 2, "NextWaypointId must have exactly one getter and one setter")
    next_get = one({n.name: n for n in next_nodes}, "K2Node_VariableGet")
    next_set = one({n.name: n for n in next_nodes}, "K2Node_VariableSet")
    selected_set = one(
        nodes,
        'K2Node_VariableSet Name="K2Node_VariableSet_0"',
    )
    require(
        'MemberName="SelectedWaypointIndex",MemberGuid=23B9561944904F583A9AAE8770F8810B'
        in selected_set.text,
        "Capture must commit the newly appended index to SelectedWaypointIndex",
    )
    print_node = one(nodes, 'MemberName="PrintString"')
    require('DefaultValue="[EDD] Waypoint captured"' in print_node.text, "Capture diagnostic text changed")

    array_adds = sorted(
        [node for node in nodes.values() if 'MemberName="Array_Add"' in node.text],
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    require(len(array_adds) == 6, f"Capture must append six lockstep channels; found {len(array_adds)}")
    if entries:
        require_link(entries[0], "then", branch, "execute", "Function entry must reach the validity branch")
    else:
        require(
            ("K2Node_FunctionEntry_0", "279859644842DE772AC782B3D54B3ACB")
            in pin(branch, "execute").links,
            "Paste graph must retain the exact live CaptureCurrentWaypoint entry link",
        )
    require_link(camera, "DroneCameraRef", valid, "Object", "DroneCameraRef must drive IsValid")
    require_link(valid, "ReturnValue", branch, "Condition", "IsValid must guard every append")

    exec_chain = [branch, *array_adds, selected_set, next_set, print_node]
    for left, right in zip(exec_chain, exec_chain[1:]):
        left_pin = "then"
        right_pin = "execute"
        require_link(left, left_pin, right, right_pin, f"Atomic exec chain broke between {left.name} and {right.name}")

    channels = (
        ("DraftWaypointIds", "int", "", next_get, "NextWaypointId"),
        ("DraftWaypointTransforms", "struct", "", transform, "ReturnValue"),
        ("DraftWaypointFocalLengths", "real", "double", one(nodes, 'MemberName="FocalLength",MemberGuid='), "FocalLength"),
        ("DraftWaypointApertures", "real", "double", one(nodes, 'MemberName="Aperture",MemberGuid='), "Aperture"),
        ("DraftWaypointFocusDistances", "real", "double", one(nodes, 'MemberName="ManualFocusDistance",MemberGuid='), "ManualFocusDistance"),
        ("DraftWaypointHoldSeconds", "real", "double", None, None),
    )
    for (variable, category, subcategory, source, source_pin), add in zip(channels, array_adds):
        getter = one(nodes, f'VariableReference=(MemberName="{variable}"')
        require_link(getter, variable, add, "TargetArray", f"{variable} must feed only its Array_Add")
        target = pin(add, "TargetArray").body
        item = pin(add, "NewItem").body
        require(f'PinType.PinCategory="{category}"' in target, f"{variable} array type changed")
        require(f'PinType.PinCategory="{category}"' in item, f"{variable} item type changed")
        if subcategory:
            require(f'PinType.PinSubCategory="{subcategory}"' in target, f"{variable} precision changed")
            require(f'PinType.PinSubCategory="{subcategory}"' in item, f"{variable} item precision changed")
        if source is None:
            require(not pin(add, "NewItem").links, "New waypoint hold must use its zero default")
            hold_default = re.search(r'(?:^|,)DefaultValue="([^"]*)"', pin(add, "NewItem").body)
            require(
                hold_default is None or float(hold_default.group(1)) == 0.0,
                "New waypoint hold must default to zero seconds",
            )
        else:
            require_link(source, source_pin, add, "NewItem", f"{variable} must snapshot its exact source")

    require_link(camera, "DroneCameraRef", transform, "self", "Transform must come from DroneCameraRef")
    for marker, value_pin in (
        ('MemberName="FocalLength",MemberGuid=', "FocalLength"),
        ('MemberName="Aperture",MemberGuid=', "Aperture"),
        ('MemberName="ManualFocusDistance",MemberGuid=', "ManualFocusDistance"),
    ):
        source = one(nodes, marker)
        require_link(camera, "DroneCameraRef", source, "self", f"{value_pin} must come from DroneCameraRef")
    require_link(next_get, "NextWaypointId", increment, "A", "Waypoint ID must feed increment input A")
    require('DefaultValue="1"' in pin(increment, "B").body, "Waypoint ID increment must be exactly one")
    require_link(
        array_adds[0],
        "ReturnValue",
        selected_set,
        "SelectedWaypointIndex",
        "Capture must select the exact index returned by the ID append",
    )
    require_link(increment, "ReturnValue", next_set, "NextWaypointId", "Incremented ID must be committed after all appends")


def assert_dispatch(nodes: dict[str, Node]) -> None:
    require(len(nodes) in {37, 43, 51}, f"Client EventGraph expected 37, 43, or 51 total nodes; found {len(nodes)}")
    roll = one(nodes, 'MemberName="ApplyRollAndHorizonInput"')
    capture = one(nodes, 'MemberName="CaptureCurrentWaypoint"')

    def key_poll(default_value: str) -> Node:
        matches = [
            node
            for node in nodes.values()
            if 'MemberName="WasInputKeyJustPressed"' in node.text
            and 'PinName="Key"' in node.text
            and f'DefaultValue="{default_value}"' in node.text
        ]
        require(len(matches) == 1, f"Expected one {default_value} edge poll; found {len(matches)}")
        return matches[0]

    def driven_branch(key: Node, label: str) -> Node:
        matches = [
            node
            for node in nodes.values()
            if node.node_class.endswith("K2Node_IfThenElse")
            and linked(key, "ReturnValue", node, "Condition")
        ]
        require(len(matches) == 1, f"{label} edge result must drive exactly one branch")
        return matches[0]

    key_k = key_poll("K")
    branch_k = driven_branch(key_k, "K")
    controllers = [
        node for node in nodes.values()
        if 'MemberName="GetPlayerController"' in node.text
        and linked(node, "ReturnValue", key_k, "self")
    ]
    require(len(controllers) == 1, "Waypoint polling must use local Player Controller 0")
    require('DefaultValue="0"' in pin(controllers[0], "PlayerIndex").body, "Waypoint poll controller index must remain zero")
    require_link(roll, "then", branch_k, "execute", "Capture polling must run after roll/horizon processing")
    require_link(key_k, "ReturnValue", branch_k, "Condition", "K must use edge-triggered branch gating")
    require_link(branch_k, "then", capture, "execute", "Only the true K edge may capture a waypoint")
    if len(nodes) != 51:
        require(not pin(capture, "then").links, "Waypoint capture must terminate the active-input tick")

    replace_nodes = [node for node in nodes.values() if 'MemberName="ReplaceSelectedWaypoint"' in node.text]
    delete_nodes = [node for node in nodes.values() if 'MemberName="DeleteSelectedWaypoint"' in node.text]
    if len(nodes) == 37:
        require(not replace_nodes and not delete_nodes, "The 37-node capture slice must not contain a partial edit dispatch")
        require(not pin(branch_k, "else").links, "A tick without K must terminate without mutation")
        require('ErrorType=' not in "".join(node.text for node in nodes.values()), "EventGraph retains compiler error metadata")
        return

    require(len(replace_nodes) == 1 and len(delete_nodes) == 1, "The edit slice needs one replace and one delete call")
    replace = replace_nodes[0]
    delete = delete_nodes[0]
    key_r = key_poll("R")
    key_delete = key_poll("Delete")
    branch_r = driven_branch(key_r, "R")
    branch_delete = driven_branch(key_delete, "Delete")
    require_link(controllers[0], "ReturnValue", key_r, "self", "R polling must share local Player Controller 0")
    require_link(controllers[0], "ReturnValue", key_delete, "self", "Delete polling must share local Player Controller 0")
    require_link(branch_k, "else", branch_r, "execute", "A tick without K must continue to replace polling")
    require_link(key_r, "ReturnValue", branch_r, "Condition", "R must use edge-triggered branch gating")
    require_link(branch_r, "then", replace, "execute", "Only the true R edge may replace the selection")
    require_link(branch_r, "else", branch_delete, "execute", "A tick without R must continue to delete polling")
    require_link(key_delete, "ReturnValue", branch_delete, "Condition", "Delete must use edge-triggered branch gating")
    require_link(branch_delete, "then", delete, "execute", "Only the true Delete edge may remove the selection")
    require(not pin(branch_delete, "else").links, "A tick without an authoring key must terminate without mutation")
    if len(nodes) == 43:
        require(not pin(capture, "then").links, "Waypoint capture must terminate the active-input tick")
        require(not pin(replace, "then").links, "Waypoint replacement must terminate the active-input tick")
        require(not pin(delete, "then").links, "Waypoint deletion must terminate the active-input tick")
    else:
        require(pin(capture, "then").links, "Feedback slice must continue after capture")
        require(pin(replace, "then").links, "Feedback slice must continue after replacement")
        require(pin(delete, "then").links, "Feedback slice must continue after deletion")
    require('ErrorType=' not in "".join(node.text for node in nodes.values()), "EventGraph retains compiler error metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--event", type=Path, required=True)
    args = parser.parse_args()
    assert_capture(parse_graph(args.capture))
    assert_dispatch(parse_graph(args.event))
    print("Waypoint authoring contracts valid: atomic capture and guarded available shortcut dispatch")


if __name__ == "__main__":
    main()
