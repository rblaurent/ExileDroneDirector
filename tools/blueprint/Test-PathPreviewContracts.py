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


def linked(left: Node, left_pin: str, right: Node, right_pin: str) -> bool:
    return (
        left_pin in left.pins
        and right_pin in right.pins
        and (right.name, right.pins[right_pin].pin_id) in left.pins[left_pin].links
    )


def linked_target(
    nodes: dict[str, Node],
    left: Node,
    left_pin: str,
    right_pin: str,
    marker: str | None = None,
) -> Node:
    matches = [
        node for node in nodes.values()
        if linked(left, left_pin, node, right_pin) and (marker is None or marker in node.text)
    ]
    require(
        len(matches) == 1,
        f"Expected one target from {left.name}.{left_pin} to {right_pin}"
        f" matching {marker!r}; found {[node.name for node in matches]}",
    )
    return matches[0]


def require_pin_default(node: Node, pin_name: str, value: str, message: str) -> None:
    require(pin_name in node.pins, f"{node.name} has no {pin_name} pin")
    pin_id = node.pins[pin_name].pin_id
    line = next(line for line in node.text.splitlines() if f"PinId={pin_id}" in line)
    require(f'DefaultValue="{value}"' in line, message)


def assert_marker_rebuild_contract(
    nodes: dict[str, Node],
    *,
    expected_nodes: int = 14,
    allow_segments: bool = False,
) -> None:
    require(
        len(nodes) == expected_nodes,
        f"Marker RebuildPreviewV1 must have {expected_nodes} nodes; found {len(nodes)}",
    )
    entry = one(nodes, 'FunctionReference=(MemberName="RebuildPreviewV1")')
    # Unreal inserts the resolved MemberGuid ahead of bSelfContext when a
    # same-Blueprint function call is pasted and exported again. Match the
    # stable function identity here; the reciprocal execution links below
    # still prove this is the intended call in the pipeline.
    clear = one(nodes, 'FunctionReference=(MemberName="ClearPreviewV1"')
    enabled = one(nodes, 'VariableReference=(MemberName="PreviewEnabled"')
    document = one(nodes, 'VariableReference=(MemberName="PreviewDocumentV1"')
    break_document = one(nodes, 'StructType="/Script/CoreUObject.UserDefinedStruct\'/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument')
    loop = one(nodes, 'StandardMacros:ForEachLoop')
    marker_scale = one(nodes, 'VariableReference=(MemberName="MarkerScaleV1"')
    marker = one(nodes, 'VariableReference=(MemberName="WaypointMarkersV1"')
    branch = linked_target(
        nodes, enabled, "PreviewEnabled", "Condition", "K2Node_IfThenElse"
    )
    break_waypoint = linked_target(
        nodes, loop, "Array Element", "ST_EDD_Waypoint", "ST_EDD_Waypoint"
    )
    camera_transform = pin_starting(break_waypoint, "CameraTransform_")
    break_transform = linked_target(
        nodes, break_waypoint, camera_transform, "InTransform", 'MemberName="BreakTransform"'
    )
    add_instance = linked_target(
        nodes, marker, "WaypointMarkersV1", "self", 'MemberName="AddInstance"'
    )
    make_transform = linked_target(
        nodes, add_instance, "InstanceTransform", "ReturnValue", 'MemberName="MakeTransform"'
    )
    make_scale = linked_target(
        nodes, make_transform, "Scale", "ReturnValue", 'MemberName="MakeVector"'
    )

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
    require_pin_default(add_instance, "bWorldSpace", "true", "Marker instances must be added in world space")
    if not allow_segments:
        require(not any('MemberName="SegmentLinesV1"' in node.text for node in nodes.values()), "Marker slice must not claim segment-line projection")


def assert_segment_rebuild_contract(nodes: dict[str, Node]) -> None:
    assert_marker_rebuild_contract(nodes, expected_nodes=34, allow_segments=True)

    break_document = one(nodes, 'StructType="/Script/CoreUObject.UserDefinedStruct\'/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument')
    loop = one(nodes, 'StandardMacros:ForEachLoop')
    marker = one(nodes, 'VariableReference=(MemberName="WaypointMarkersV1"')
    marker_add = linked_target(nodes, marker, "WaypointMarkersV1", "self", 'MemberName="AddInstance"')
    add_index = one(nodes, 'MemberName="Add_IntInt"')
    array_length = one(nodes, 'MemberName="Array_Length"')
    next_in_bounds = one(nodes, 'MemberName="GreaterEqual_IntInt"')
    bounds_branch = linked_target(nodes, marker_add, "then", "execute", "K2Node_IfThenElse")
    array_get = one(nodes, 'Class=/Script/BlueprintGraph.K2Node_GetArrayItem')
    next_waypoint = linked_target(nodes, array_get, "Output", "ST_EDD_Waypoint", "ST_EDD_Waypoint")
    next_camera = pin_starting(next_waypoint, "CameraTransform_")
    next_transform = linked_target(nodes, next_waypoint, next_camera, "InTransform", 'MemberName="BreakTransform"')

    current_waypoint = linked_target(nodes, loop, "Array Element", "ST_EDD_Waypoint", "ST_EDD_Waypoint")
    current_camera = pin_starting(current_waypoint, "CameraTransform_")
    current_transform = linked_target(nodes, current_waypoint, current_camera, "InTransform", 'MemberName="BreakTransform"')
    midpoint = one(nodes, 'MemberName="TLerp"')
    midpoint_transform = linked_target(nodes, midpoint, "ReturnValue", "InTransform", 'MemberName="BreakTransform"')
    look_at = one(nodes, 'MemberName="FindLookAtRotation"')
    distance = one(nodes, 'MemberName="Vector_Distance"')
    distance_positive = one(nodes, 'MemberName="Greater_DoubleDouble"')
    distance_branch = linked_target(nodes, distance_positive, "ReturnValue", "Condition", "K2Node_IfThenElse")
    source_extent = one(nodes, 'VariableReference=(MemberName="SourceCubeExtentV1"')
    normalized_length = one(nodes, 'MemberName="Divide_DoubleDouble"')
    thickness = one(nodes, 'VariableReference=(MemberName="LineThicknessV1"')
    segment_component = one(nodes, 'VariableReference=(MemberName="SegmentLinesV1"')
    segment_add = linked_target(nodes, segment_component, "SegmentLinesV1", "self", 'MemberName="AddInstance"')
    segment_transform = linked_target(nodes, segment_add, "InstanceTransform", "ReturnValue", 'MemberName="MakeTransform"')
    segment_scale = linked_target(nodes, segment_transform, "Scale", "ReturnValue", 'MemberName="MakeVector"')
    waypoints = pin_starting(break_document, "Waypoints_")

    for getter, member_name in (
        (source_extent, "SourceCubeExtentV1"),
        (thickness, "LineThicknessV1"),
        (segment_component, "SegmentLinesV1"),
    ):
        require('bSelfContext=True' in getter.text, f"{member_name} must remain a self-context getter")

    require_link(loop, "Array Index", add_index, "A", "Each loop index must derive its adjacent index")
    require_pin_default(add_index, "B", "1", "Adjacent index must be current index plus one")
    require_link(break_document, waypoints, array_length, "TargetArray", "Bounds check must use typed document waypoints")
    require_link(add_index, "ReturnValue", next_in_bounds, "A", "Adjacent index must drive the upper-bound comparison")
    require_link(array_length, "ReturnValue", next_in_bounds, "B", "Waypoint count must bound adjacent access")
    require_link(next_in_bounds, "ReturnValue", bounds_branch, "Condition", "Out-of-bounds adjacency must be guarded")
    require(not bounds_branch.pins["then"].links, "Last waypoint must skip segment construction")
    require_link(bounds_branch, "else", distance_branch, "execute", "Only in-bounds adjacency may continue")

    require_link(break_document, waypoints, array_get, "Array", "Adjacent lookup must use typed document waypoints")
    require_link(add_index, "ReturnValue", array_get, "Dimension 1", "Adjacent lookup must use current index plus one")
    require_link(array_get, "Output", next_waypoint, "ST_EDD_Waypoint", "Adjacent item must feed a typed waypoint break")
    require_link(next_waypoint, next_camera, next_transform, "InTransform", "Adjacent pose must originate from CameraTransform")
    require_link(current_waypoint, current_camera, midpoint, "A", "Current pose must feed midpoint interpolation")
    require_link(next_waypoint, next_camera, midpoint, "B", "Adjacent pose must feed midpoint interpolation")
    require_pin_default(midpoint, "Alpha", "0.5", "Segment midpoint interpolation must use alpha 0.5")
    require_link(midpoint, "ReturnValue", midpoint_transform, "InTransform", "Interpolated transform must expose midpoint location")

    require_link(current_transform, "Location", look_at, "Start", "Look-at rotation must start at current location")
    require_link(next_transform, "Location", look_at, "Target", "Look-at rotation must target adjacent location")
    require_link(current_transform, "Location", distance, "V1", "Segment length must start at current location")
    require_link(next_transform, "Location", distance, "V2", "Segment length must end at adjacent location")
    require_link(distance, "ReturnValue", distance_positive, "A", "Degenerate guard must inspect segment length")
    require_pin_default(distance_positive, "B", "0.001", "Degenerate threshold must be 0.001 cm")
    require_link(distance_positive, "ReturnValue", distance_branch, "Condition", "Only positive-length segments may render")
    require_link(distance_branch, "then", segment_add, "execute", "Positive-length adjacency must add one segment")
    require(not distance_branch.pins["else"].links, "Degenerate adjacency must skip segment construction")

    require_link(distance, "ReturnValue", normalized_length, "A", "Cube X scale must derive from world distance")
    require_link(source_extent, "SourceCubeExtentV1", normalized_length, "B", "Cube X scale must normalize by source extent")
    require_link(normalized_length, "ReturnValue", segment_scale, "X", "Normalized distance must drive local X scale")
    require_link(thickness, "LineThicknessV1", segment_scale, "Y", "Line thickness must drive local Y scale")
    require_link(thickness, "LineThicknessV1", segment_scale, "Z", "Line thickness must drive local Z scale")
    require_link(midpoint_transform, "Location", segment_transform, "Location", "Segment instance must be centred between waypoints")
    require_link(look_at, "ReturnValue", segment_transform, "Rotation", "Segment instance must point at the adjacent waypoint")
    require_link(segment_scale, "ReturnValue", segment_transform, "Scale", "Segment scale must feed the instance transform")
    require_link(segment_transform, "ReturnValue", segment_add, "InstanceTransform", "Constructed segment transform must feed AddInstance")
    require_link(segment_component, "SegmentLinesV1", segment_add, "self", "Segments must be pooled in SegmentLinesV1")
    require_pin_default(segment_add, "bWorldSpace", "true", "Segment instances must be added in world space")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", type=Path, required=True)
    parser.add_argument("--rebuild", type=Path)
    parser.add_argument("--segments", type=Path)
    args = parser.parse_args()
    assert_clear_contract(parse(args.clear))
    if args.rebuild is not None:
        assert_marker_rebuild_contract(parse(args.rebuild))
        print("Path-preview clear and marker-rebuild semantic contracts valid")
    elif args.segments is not None:
        assert_segment_rebuild_contract(parse(args.segments))
        print("Path-preview clear, marker, and segment-rebuild semantic contracts valid")
    else:
        print("Path-preview ClearPreviewV1 semantic contracts valid")


if __name__ == "__main__":
    main()
