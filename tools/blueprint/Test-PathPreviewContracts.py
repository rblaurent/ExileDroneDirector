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


def pin_starting(node: Node, prefix: str) -> str:
    matches = [name for name in node.pins if name.startswith(prefix)]
    require(len(matches) == 1, f"Expected one {node.name} pin starting {prefix!r}; found {matches}")
    return matches[0]


def assert_marker_rebuild_contract(nodes: dict[str, Node]) -> None:
    require(len(nodes) == 14, f"Marker RebuildPreviewV1 must have 14 nodes; found {len(nodes)}")
    entry = one(nodes, 'FunctionReference=(MemberName="RebuildPreviewV1")')
    # Unreal inserts the resolved MemberGuid ahead of bSelfContext when a
    # same-Blueprint function call is pasted and exported again. Match the
    # stable function identity here; the reciprocal execution links below
    # still prove this is the intended call in the pipeline.
    clear = one(nodes, 'FunctionReference=(MemberName="ClearPreviewV1"')
    branch = one(nodes, 'Class=/Script/BlueprintGraph.K2Node_IfThenElse')
    enabled = one(nodes, 'VariableReference=(MemberName="PreviewEnabled"')
    document = one(nodes, 'VariableReference=(MemberName="PreviewDocumentV1"')
    break_document = one(nodes, 'StructType="/Script/CoreUObject.UserDefinedStruct\'/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument')
    loop = one(nodes, 'StandardMacros:ForEachLoop')
    break_waypoint = one(nodes, 'StructType="/Script/CoreUObject.UserDefinedStruct\'/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Waypoint')
    break_transform = one(nodes, 'MemberName="BreakTransform"')
    marker_scale = one(nodes, 'VariableReference=(MemberName="MarkerScaleV1"')
    make_scale = one(nodes, 'MemberName="MakeVector"')
    make_transform = one(nodes, 'MemberName="MakeTransform"')
    marker = one(nodes, 'VariableReference=(MemberName="WaypointMarkersV1"')
    add_instance = one(nodes, 'MemberName="AddInstance"')

    require('bSelfContext=True' in clear.text, "ClearPreviewV1 must remain a same-Blueprint call")
    for getter, member_name in (
        (enabled, "PreviewEnabled"),
        (document, "PreviewDocumentV1"),
        (marker_scale, "MarkerScaleV1"),
        (marker, "WaypointMarkersV1"),
    ):
        require('bSelfContext=True' in getter.text, f"{member_name} must remain a self-context getter")

    require_link(entry, "then", clear, "execute", "RebuildPreviewV1 must clear stale instances first")
    require_link(clear, "then", branch, "execute", "Clear must precede the enabled guard")
    require_link(enabled, "PreviewEnabled", branch, "Condition", "PreviewEnabled must guard projection")
    require_link(branch, "then", loop, "Exec", "Only the enabled branch may execute the waypoint loop")
    require(not branch.pins["else"].links, "Disabled preview must stop after clearing both pools")

    waypoints = pin_starting(break_document, "Waypoints_")
    camera_transform = pin_starting(break_waypoint, "CameraTransform_")
    require_link(document, "PreviewDocumentV1", break_document, "ST_EDD_FlypathDocument", "Typed document must feed its native break")
    require_link(break_document, waypoints, loop, "Array", "Typed document waypoints must feed the loop")
    require_link(loop, "Array Element", break_waypoint, "ST_EDD_Waypoint", "Each typed waypoint must feed its native break")
    require_link(loop, "LoopBody", add_instance, "execute", "Every waypoint must add exactly one marker")
    require_link(break_waypoint, camera_transform, break_transform, "InTransform", "Marker pose must originate from CameraTransform")
    require_link(break_transform, "Location", make_transform, "Location", "Marker must preserve authored world location")
    require_link(break_transform, "Rotation", make_transform, "Rotation", "Marker must preserve authored camera rotation")

    for axis in ("X", "Y", "Z"):
        require_link(marker_scale, "MarkerScaleV1", make_scale, axis, f"Marker scale must drive {axis}")
    require_link(make_scale, "ReturnValue", make_transform, "Scale", "Uniform marker scale must feed the instance transform")
    require_link(make_transform, "ReturnValue", add_instance, "InstanceTransform", "Constructed marker transform must feed AddInstance")
    require_link(marker, "WaypointMarkersV1", add_instance, "self", "Markers must be pooled in WaypointMarkersV1")
    require('PinName="bWorldSpace"' in add_instance.text and 'DefaultValue="true"' in add_instance.text, "Marker instances must be added in world space")
    require(not any('MemberName="SegmentLinesV1"' in node.text for node in nodes.values()), "Marker slice must not claim segment-line projection")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", type=Path, required=True)
    parser.add_argument("--rebuild", type=Path)
    args = parser.parse_args()
    assert_clear_contract(parse(args.clear))
    if args.rebuild is not None:
        assert_marker_rebuild_contract(parse(args.rebuild))
        print("Path-preview clear and marker-rebuild semantic contracts valid")
    else:
        print("Path-preview ClearPreviewV1 semantic contracts valid")


if __name__ == "__main__":
    main()
