"""Build the first visible RebuildPreviewV1 Blueprint graph.

The generated graph clears both HISM pools through ClearPreviewV1, honors the
PreviewEnabled switch, then projects every typed waypoint into one world-space
sphere instance with the authored camera pose and uniform MarkerScaleV1.
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
TARGET_CLASS = (
    "/Script/Engine.BlueprintGeneratedClass'"
    "/Game/Mods/ExileDroneDirector/Trajectory/"
    "BP_EDD_PathPreview.BP_EDD_PathPreview_C'"
)


_id_counter = 0


def new_id() -> str:
    global _id_counter
    _id_counter += 1
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"exile-drone-director:path-preview-marker:{_id_counter}",
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
                old_pin = re.search(r'PinId=([0-9A-F]{32})', line)
                if old_pin is None:
                    raise RuntimeError(f"Node {key} pin {match.group('name')} has no PinId")
                pin_id = old_pin.group(1) if key == 'entry' else new_id()
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


def retarget_self_call(node: Node, function_name: str) -> None:
    node.text = re.sub(
        r'FunctionReference=\([^)]*\)',
        f'FunctionReference=(MemberName="{function_name}",bSelfContext=True)',
        node.text,
        count=1,
    )
    node.text = re.sub(
        r'PinType\.PinSubCategoryObject="/Script/Engine\.BlueprintGeneratedClass\'[^\"]+"',
        f'PinType.PinSubCategoryObject="{TARGET_CLASS}"',
        node.text,
    )


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
        if kind == 'bool':
            line = re.sub(r'PinType\.PinCategory="[^"]+"', 'PinType.PinCategory="bool"', line, count=1)
            line = re.sub(r'PinType\.PinSubCategory="[^"]*"', 'PinType.PinSubCategory=""', line, count=1)
            line = re.sub(r'PinType\.PinSubCategoryObject=[^,]+', 'PinType.PinSubCategoryObject=None', line, count=1)
        elif kind == 'real':
            line = re.sub(r'PinType\.PinCategory="[^"]+"', 'PinType.PinCategory="real"', line, count=1)
            line = re.sub(r'PinType\.PinSubCategory="[^"]*"', 'PinType.PinSubCategory="double"', line, count=1)
            line = re.sub(r'PinType\.PinSubCategoryObject=[^,]+', 'PinType.PinSubCategoryObject=None', line, count=1)
        else:
            raise RuntimeError(f"Unsupported getter kind: {kind}")
        return line

    node.mutate_pin(new_name, mutate)


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
    forms = read_blocks(blueprint / 'templates' / 'path-preview-marker-node-forms.eddgraph')
    enter = read_blocks(blueprint / 'snippets' / 'enter-drone-mode.eddgraph')
    event = read_blocks(blueprint / 'snippets' / 'client-director-event-graph.eddgraph')
    templates = {
        'entry': find_block(forms, r'K2Node_FunctionEntry'),
        'marker': find_block(forms, r'MemberName="WaypointMarkersV1"'),
        'add_instance': find_block(forms, r'MemberName="AddInstance"'),
        'document': find_block(forms, r'MemberName="PreviewDocumentV1"'),
        'break_document': find_block(forms, r'(?m)^   StructType="[^"]*ST_EDD_FlypathDocument'),
        'loop': find_block(forms, r'StandardMacros:ForEachLoop'),
        'break_waypoint': find_block(forms, r'(?m)^   StructType="[^"]*ST_EDD_Waypoint'),
        'break_transform': find_block(forms, r'MemberName="BreakTransform"'),
        'make_vector': find_block(forms, r'MemberName="MakeVector"'),
        'make_transform': find_block(enter, r'MemberName="MakeTransform"'),
        'branch': find_block(enter, r'Class=/Script/BlueprintGraph.K2Node_IfThenElse'),
        'self_call': find_block(event, r'MemberName="StopLinearPlayback"'),
    }
    nodes: dict[str, Node] = {}

    def add(key: str, template_key: str, name: str, x: int, y: int) -> Node:
        node = Node.clone(key, templates[template_key], name, x, y)
        nodes[key] = node
        return node

    entry = add('entry', 'entry', 'K2Node_FunctionEntry_0', 0, 0)
    clear = add('clear', 'self_call', 'K2Node_CallFunction_0', 256, 0)
    retarget_self_call(clear, 'ClearPreviewV1')
    branch = add('branch', 'branch', 'K2Node_IfThenElse_0', 528, 0)
    enabled = add('enabled', 'document', 'K2Node_VariableGet_0', 272, 208)
    retarget_getter(enabled, 'PreviewDocumentV1', 'PreviewEnabled', 'bool')

    document = add('document', 'document', 'K2Node_VariableGet_1', 528, 256)
    break_document = add('break_document', 'break_document', 'K2Node_BreakStruct_0', 768, 208)
    loop = add('loop', 'loop', 'K2Node_MacroInstance_0', 1200, 0)
    break_waypoint = add('break_waypoint', 'break_waypoint', 'K2Node_BreakStruct_1', 1440, 288)
    break_transform = add('break_transform', 'break_transform', 'K2Node_CallFunction_1', 1776, 288)

    marker_scale = add('marker_scale', 'document', 'K2Node_VariableGet_2', 1776, 512)
    retarget_getter(marker_scale, 'PreviewDocumentV1', 'MarkerScaleV1', 'real')
    make_scale = add('make_scale', 'make_vector', 'K2Node_CallFunction_2', 2016, 512)
    make_transform = add('make_transform', 'make_transform', 'K2Node_CallFunction_3', 2208, 256)
    marker = add('marker', 'marker', 'K2Node_VariableGet_3', 2208, 608)
    add_instance = add('add_instance', 'add_instance', 'K2Node_CallFunction_4', 2496, 0)
    set_default(add_instance, 'bWorldSpace', 'true')

    waypoint_transform = pin_starting(break_waypoint, 'CameraTransform_')
    waypoints = pin_starting(break_document, 'Waypoints_')

    connect(entry, 'then', clear, 'execute')
    connect(clear, 'then', branch, 'execute')
    connect(enabled, 'PreviewEnabled', branch, 'Condition')
    connect(branch, 'then', loop, 'Exec')
    connect(document, 'PreviewDocumentV1', break_document, 'ST_EDD_FlypathDocument')
    connect(break_document, waypoints, loop, 'Array')
    connect(loop, 'Array Element', break_waypoint, 'ST_EDD_Waypoint')
    connect(loop, 'LoopBody', add_instance, 'execute')
    connect(break_waypoint, waypoint_transform, break_transform, 'InTransform')
    connect(break_transform, 'Location', make_transform, 'Location')
    connect(break_transform, 'Rotation', make_transform, 'Rotation')
    for axis in ('X', 'Y', 'Z'):
        connect(marker_scale, 'MarkerScaleV1', make_scale, axis)
    connect(make_scale, 'ReturnValue', make_transform, 'Scale')
    connect(make_transform, 'ReturnValue', add_instance, 'InstanceTransform')
    connect(marker, 'WaypointMarkersV1', add_instance, 'self')

    ordered = list(nodes.values())
    full = '\n'.join(node.text for node in ordered) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding='utf-8')
    if args.paste_output:
        paste = []
        for node in ordered:
            if node.key == 'entry':
                continue
            paste.append(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', '', node.text))
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text('\n'.join(paste) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
