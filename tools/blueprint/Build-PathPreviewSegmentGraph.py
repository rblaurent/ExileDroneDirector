"""Build RebuildPreviewV1 with waypoint markers and linear segment instances.

The checked live marker graph is treated as the stable base.  This builder adds
one cube instance for every non-degenerate adjacent waypoint pair.  Each cube
is centred between the two camera locations, rotated so local X points at the
next waypoint, and scaled to the pair distance plus the configured line width.
"""

from __future__ import annotations

import argparse
import re
import uuid
from dataclasses import dataclass
from pathlib import Path


BLOCK_RE = re.compile(
    r'^Begin Object Class=(?P<class>\S+) Name="(?P<name>[^"]+)".*?^End Object\r?$',
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r'^\s*CustomProperties Pin \(.*?PinName="(?P<name>[^"]+)".*\)$')
TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Trajectory/"
    "BP_EDD_PathPreview.BP_EDD_PathPreview"
)
TARGET_GRAPH = "RebuildPreviewV1"
WAYPOINT_STRUCT = (
    "/Script/CoreUObject.UserDefinedStruct'"
    "/Game/Mods/ExileDroneDirector/Data/Structs/"
    "ST_EDD_Waypoint.ST_EDD_Waypoint'"
)


_id_counter = 0


def new_id() -> str:
    global _id_counter
    _id_counter += 1
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"exile-drone-director:path-preview-segment:{_id_counter}",
    ).hex.upper()


def read_blocks(path: Path) -> list[str]:
    return [match.group(0) for match in BLOCK_RE.finditer(path.read_text(encoding="utf-8"))]


def find_block(blocks: list[str], pattern: str) -> str:
    for block in blocks:
        if re.search(pattern, block, re.DOTALL):
            return block
    raise RuntimeError(f"No node template matched: {pattern}")


@dataclass
class Node:
    key: str
    text: str
    name: str
    pins: dict[str, str]

    @classmethod
    def existing(cls, key: str, text: str) -> "Node":
        header = BLOCK_RE.match(text)
        if header is None:
            raise RuntimeError(f"Invalid existing node for {key}")
        pins: dict[str, str] = {}
        for line in text.splitlines():
            match = PIN_RE.match(line)
            if match:
                pin_id = re.search(r'PinId=([0-9A-F]{32})', line)
                if pin_id is None:
                    raise RuntimeError(f"Node {key} pin {match.group('name')} has no PinId")
                pins[match.group('name')] = pin_id.group(1)
        return cls(key, text, header.group("name"), pins)

    @classmethod
    def clone(cls, key: str, template: str, name: str, x: int, y: int) -> "Node":
        header = BLOCK_RE.match(template)
        if header is None:
            raise RuntimeError(f"Invalid node template for {key}")
        old_name = header.group("name")
        text = template.replace(f'Name="{old_name}"', f'Name="{name}"', 1)
        export_class = header.group("class").rsplit(".", 1)[-1]
        text = re.sub(
            r'ExportPath="[^"]+"',
            f'ExportPath="/Script/BlueprintGraph.{export_class}'
            f"'{TARGET_ASSET}:{TARGET_GRAPH}.{name}'\"",
            text,
            count=1,
        )
        text = re.sub(r'^\s*NodePosX=.*\r?\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*NodePosY=.*\r?\n', '', text, flags=re.MULTILINE)
        text = text.replace('   NodeGuid=', f'   NodePosX={x}\n   NodePosY={y}\n   NodeGuid=', 1)
        text = re.sub(r'NodeGuid=[0-9A-F]{32}', f'NodeGuid={new_id()}', text)
        text = re.sub(r',LinkedTo=\([^)]*\)', '', text)

        pins: dict[str, str] = {}
        rebuilt: list[str] = []
        for line in text.splitlines():
            match = PIN_RE.match(line)
            if match:
                pin_id = new_id()
                line = re.sub(r'PinId=[0-9A-F]{32}', f'PinId={pin_id}', line, count=1)
                pins[match.group('name')] = pin_id
            rebuilt.append(line)
        return cls(key, '\n'.join(rebuilt), name, pins)

    def mutate_pin(self, pin_name: str, mutate) -> None:
        pin_id = self.pins[pin_name]
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            if f'PinId={pin_id}' in line:
                lines[index] = mutate(line)
                self.text = '\n'.join(lines)
                return
        raise RuntimeError(f"Could not mutate {self.key}.{pin_name}")

    def link(self, pin_name: str, other: "Node", other_pin: str) -> None:
        pin_id = self.pins[pin_name]
        other_id = other.pins[other_pin]
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            if f'PinId={pin_id}' not in line:
                continue
            match = re.search(r',LinkedTo=\((?P<links>[^)]*)\)', line)
            if match:
                links = match.group('links') + f'{other.name} {other_id},'
                lines[index] = line[:match.start()] + f',LinkedTo=({links})' + line[match.end():]
            else:
                link = f',LinkedTo=({other.name} {other_id},)'
                lines[index] = line.replace(',PersistentGuid=', f'{link},PersistentGuid=', 1)
            self.text = '\n'.join(lines)
            return
        raise RuntimeError(f"Could not link {self.key}.{pin_name}")


def connect(left: Node, left_pin: str, right: Node, right_pin: str) -> None:
    left.link(left_pin, right, right_pin)
    right.link(right_pin, left, left_pin)


def set_default(node: Node, pin_name: str, value: str) -> None:
    def mutate(line: str) -> str:
        if 'DefaultValue=' in line:
            return re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, count=1)
        return line.replace(',PersistentGuid=', f',DefaultValue="{value}",PersistentGuid=', 1)

    node.mutate_pin(pin_name, mutate)


def retarget_getter(node: Node, old_name: str, new_name: str, kind: str) -> None:
    node.text = re.sub(
        r'VariableReference=\([^)]*\)',
        f'VariableReference=(MemberName="{new_name}",bSelfContext=True)',
        node.text,
        count=1,
    )
    node.text = node.text.replace(f'PinName="{old_name}"', f'PinName="{new_name}"')
    node.pins[new_name] = node.pins.pop(old_name)

    def mutate(line: str) -> str:
        if kind == 'real':
            line = re.sub(r'PinType\.PinCategory="[^"]+"', 'PinType.PinCategory="real"', line, count=1)
            line = re.sub(r'PinType\.PinSubCategory="[^"]*"', 'PinType.PinSubCategory="double"', line, count=1)
            line = re.sub(r'PinType\.PinSubCategoryObject=[^,]+', 'PinType.PinSubCategoryObject=None', line, count=1)
        elif kind != 'object':
            raise RuntimeError(f"Unsupported getter kind: {kind}")
        return line

    node.mutate_pin(new_name, mutate)


def type_waypoint_pin(node: Node, pin_name: str, container: str) -> None:
    def mutate(line: str) -> str:
        line = re.sub(r'PinType\.PinCategory="[^"]+"', 'PinType.PinCategory="struct"', line, count=1)
        line = re.sub(r'PinType\.PinSubCategory="[^"]*"', 'PinType.PinSubCategory=""', line, count=1)
        line = re.sub(
            r'PinType\.PinSubCategoryObject=[^,]+',
            f'PinType.PinSubCategoryObject="{WAYPOINT_STRUCT}"',
            line,
            count=1,
        )
        line = re.sub(r'PinType\.ContainerType=\w+', f'PinType.ContainerType={container}', line, count=1)
        return line

    node.mutate_pin(pin_name, mutate)


def pin_starting(node: Node, prefix: str) -> str:
    matches = [name for name in node.pins if name.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {node.key} pin starting {prefix!r}; found {matches}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--paste-output', type=Path)
    args = parser.parse_args()

    blueprint = args.project_root / 'tools' / 'blueprint'
    base_blocks = read_blocks(blueprint / 'snippets' / 'rebuild-path-preview-markers-v1.eddgraph')
    linear = read_blocks(blueprint / 'templates' / 'linear-playback-node-forms.eddgraph')
    waypoint = read_blocks(blueprint / 'templates' / 'waypoint-edit-node-forms.eddgraph')
    segment = read_blocks(blueprint / 'templates' / 'path-preview-segment-node-forms.eddgraph')
    sync = read_blocks(blueprint / 'snippets' / 'sync-draft-waypoints-v1.eddgraph')

    nodes: dict[str, Node] = {}
    base_keys = (
        'entry', 'clear', 'enabled_branch', 'enabled', 'document', 'break_document',
        'loop', 'current_waypoint', 'current_transform', 'marker_scale', 'marker_vector',
        'marker_transform', 'marker_component', 'marker_add',
    )
    if len(base_blocks) != len(base_keys):
        raise RuntimeError(f"Expected {len(base_keys)} marker-base nodes; found {len(base_blocks)}")
    for key, block in zip(base_keys, base_blocks):
        nodes[key] = Node.existing(key, block)

    templates = {
        'branch': nodes['enabled_branch'].text,
        'break_waypoint': nodes['current_waypoint'].text,
        'break_transform': nodes['current_transform'].text,
        'make_vector': nodes['marker_vector'].text,
        'make_transform': nodes['marker_transform'].text,
        'component_getter': nodes['marker_component'].text,
        'real_getter': nodes['marker_scale'].text,
        'add_instance': nodes['marker_add'].text,
        'array_length': find_block(waypoint, r'MemberName="Array_Length"'),
        'array_get': find_block(linear, r'Name="ProbeArrayGet"'),
        'add_int': find_block(linear, r'MemberName="Add_IntInt"'),
        'greater_equal_int': find_block(linear, r'MemberName="GreaterEqual_IntInt"'),
        'tlerp': find_block(linear, r'MemberName="TLerp"'),
        'divide': find_block(linear, r'MemberName="Divide_DoubleDouble"'),
        'greater': find_block(sync, r'MemberName="Greater_DoubleDouble"'),
        'look_at': find_block(segment, r'MemberName="FindLookAtRotation"'),
        'distance': find_block(segment, r'MemberName="Vector_Distance"'),
    }

    def add(key: str, template_key: str, name: str, x: int, y: int) -> Node:
        node = Node.clone(key, templates[template_key], name, x, y)
        nodes[key] = node
        return node

    add_index = add('add_index', 'add_int', 'K2Node_CallFunction_5', 1456, 800)
    set_default(add_index, 'B', '1')
    array_length = add('array_length', 'array_length', 'K2Node_CallArrayFunction_0', 1184, 992)
    type_waypoint_pin(array_length, 'TargetArray', 'Array')
    next_in_bounds = add('next_in_bounds', 'greater_equal_int', 'K2Node_CallFunction_6', 1728, 800)
    bounds_branch = add('bounds_branch', 'branch', 'K2Node_IfThenElse_1', 2784, 0)

    array_get = add('array_get', 'array_get', 'K2Node_GetArrayItem_0', 1728, 1104)
    type_waypoint_pin(array_get, 'Array', 'Array')
    type_waypoint_pin(array_get, 'Output', 'None')
    next_waypoint = add('next_waypoint', 'break_waypoint', 'K2Node_BreakStruct_2', 1984, 1088)
    next_transform = add('next_transform', 'break_transform', 'K2Node_CallFunction_7', 2304, 1088)

    midpoint = add('midpoint', 'tlerp', 'K2Node_CallFunction_8', 2592, 896)
    set_default(midpoint, 'Alpha', '0.5')
    midpoint_transform = add('midpoint_transform', 'break_transform', 'K2Node_CallFunction_9', 2880, 896)
    look_at = add('look_at', 'look_at', 'K2Node_CallFunction_10', 2592, 1280)
    distance = add('distance', 'distance', 'K2Node_CallFunction_11', 2592, 1504)
    distance_positive = add('distance_positive', 'greater', 'K2Node_CallFunction_12', 2880, 1504)
    set_default(distance_positive, 'B', '0.001')
    distance_branch = add('distance_branch', 'branch', 'K2Node_IfThenElse_2', 3072, 96)

    source_extent = add('source_extent', 'real_getter', 'K2Node_VariableGet_4', 2880, 1744)
    retarget_getter(source_extent, 'MarkerScaleV1', 'SourceCubeExtentV1', 'real')
    normalized_length = add('normalized_length', 'divide', 'K2Node_CallFunction_13', 3168, 1504)
    thickness = add('thickness', 'real_getter', 'K2Node_VariableGet_5', 3168, 1808)
    retarget_getter(thickness, 'MarkerScaleV1', 'LineThicknessV1', 'real')
    segment_scale = add('segment_scale', 'make_vector', 'K2Node_CallFunction_14', 3456, 1504)
    segment_transform = add('segment_transform', 'make_transform', 'K2Node_CallFunction_15', 3712, 1120)
    segment_component = add('segment_component', 'component_getter', 'K2Node_VariableGet_6', 3712, 1664)
    retarget_getter(segment_component, 'WaypointMarkersV1', 'SegmentLinesV1', 'object')
    segment_add = add('segment_add', 'add_instance', 'K2Node_CallFunction_16', 4000, 96)
    set_default(segment_add, 'bWorldSpace', 'true')

    break_document = nodes['break_document']
    loop = nodes['loop']
    current_waypoint = nodes['current_waypoint']
    current_transform = nodes['current_transform']
    marker_add = nodes['marker_add']
    waypoints = pin_starting(break_document, 'Waypoints_')
    current_camera = pin_starting(current_waypoint, 'CameraTransform_')
    next_camera = pin_starting(next_waypoint, 'CameraTransform_')

    connect(marker_add, 'then', bounds_branch, 'execute')
    connect(loop, 'Array Index', add_index, 'A')
    connect(break_document, waypoints, array_length, 'TargetArray')
    connect(add_index, 'ReturnValue', next_in_bounds, 'A')
    connect(array_length, 'ReturnValue', next_in_bounds, 'B')
    connect(next_in_bounds, 'ReturnValue', bounds_branch, 'Condition')

    connect(break_document, waypoints, array_get, 'Array')
    connect(add_index, 'ReturnValue', array_get, 'Dimension 1')
    connect(array_get, 'Output', next_waypoint, 'ST_EDD_Waypoint')
    connect(next_waypoint, next_camera, next_transform, 'InTransform')
    connect(current_waypoint, current_camera, midpoint, 'A')
    connect(next_waypoint, next_camera, midpoint, 'B')
    connect(midpoint, 'ReturnValue', midpoint_transform, 'InTransform')

    connect(current_transform, 'Location', look_at, 'Start')
    connect(next_transform, 'Location', look_at, 'Target')
    connect(current_transform, 'Location', distance, 'V1')
    connect(next_transform, 'Location', distance, 'V2')
    connect(distance, 'ReturnValue', distance_positive, 'A')
    connect(bounds_branch, 'else', distance_branch, 'execute')
    connect(distance_positive, 'ReturnValue', distance_branch, 'Condition')
    connect(distance_branch, 'then', segment_add, 'execute')

    connect(distance, 'ReturnValue', normalized_length, 'A')
    connect(source_extent, 'SourceCubeExtentV1', normalized_length, 'B')
    connect(normalized_length, 'ReturnValue', segment_scale, 'X')
    connect(thickness, 'LineThicknessV1', segment_scale, 'Y')
    connect(thickness, 'LineThicknessV1', segment_scale, 'Z')
    connect(midpoint_transform, 'Location', segment_transform, 'Location')
    connect(look_at, 'ReturnValue', segment_transform, 'Rotation')
    connect(segment_scale, 'ReturnValue', segment_transform, 'Scale')
    connect(segment_transform, 'ReturnValue', segment_add, 'InstanceTransform')
    connect(segment_component, 'SegmentLinesV1', segment_add, 'self')

    ordered = list(nodes.values())
    full = '\n'.join(node.text for node in ordered) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding='utf-8')
    if args.paste_output:
        paste: list[str] = []
        for node in ordered:
            if node.key == 'entry':
                continue
            paste.append(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', '', node.text))
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text('\n'.join(paste) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
