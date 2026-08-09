"""Build the reviewed Blueprint graph for atomic draft-waypoint capture.

The generated function validates DroneCameraRef, appends ID, transform, lens,
focus, and hold channels in one ordered execution chain, then advances the
stable local ID.  Every serialized link is written reciprocally.
"""

from __future__ import annotations

import argparse
import re
import uuid
from dataclasses import dataclass
from pathlib import Path


BLOCK_RE = re.compile(
    r"^Begin Object Class=(?P<class>\S+) Name=\"(?P<name>[^\"]+)\".*?^End Object\r?$",
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r'^\s*CustomProperties Pin \(.*?PinName="(?P<name>[^"]+)".*\)$')
TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
)
TARGET_GRAPH = "CaptureCurrentWaypoint"


_id_counter = 0


def new_id() -> str:
    global _id_counter
    _id_counter += 1
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"exile-drone-director:waypoint-capture:{_id_counter}",
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
    def clone(
        cls,
        key: str,
        template: str,
        name: str,
        x: int,
        y: int,
    ) -> "Node":
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
        text = re.sub(r"^\s*NodePosX=.*\r?\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*NodePosY=.*\r?\n", "", text, flags=re.MULTILINE)
        text = text.replace("   NodeGuid=", f"   NodePosX={x}\n   NodePosY={y}\n   NodeGuid=", 1)
        text = re.sub(r"NodeGuid=[0-9A-F]{32}", f"NodeGuid={new_id()}", text)
        text = re.sub(r",LinkedTo=\([^)]*\)", "", text)

        pins: dict[str, str] = {}
        rebuilt: list[str] = []
        for line in text.splitlines():
            match = PIN_RE.match(line)
            if match:
                existing_pin = re.search(r"PinId=([0-9A-F]{32})", line)
                if existing_pin is None:
                    raise RuntimeError(f"Node {key} pin {match.group('name')} has no PinId")
                pin_id = existing_pin.group(1) if key == "entry" else new_id()
                line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={pin_id}", line, count=1)
                pins[match.group("name")] = pin_id
            rebuilt.append(line)
        return cls(key=key, text="\n".join(rebuilt), name=name, pins=pins)

    def mutate_pin(self, pin_name: str, mutate) -> None:
        pin_id = self.pins[pin_name]
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            if f"PinId={pin_id}" in line:
                lines[index] = mutate(line)
                self.text = "\n".join(lines)
                return
        raise RuntimeError(f"Could not mutate {self.key}.{pin_name}")

    def link(self, pin_name: str, other: "Node", other_pin_name: str) -> None:
        pin_id = self.pins[pin_name]
        other_pin_id = other.pins[other_pin_name]
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            if f"PinId={pin_id}" not in line:
                continue
            existing = re.search(r",LinkedTo=\((?P<links>[^)]*)\)", line)
            if existing:
                links = existing.group("links") + f"{other.name} {other_pin_id},"
                lines[index] = (
                    line[: existing.start()]
                    + f",LinkedTo=({links})"
                    + line[existing.end() :]
                )
            else:
                link = f",LinkedTo=({other.name} {other_pin_id},)"
                lines[index] = line.replace(",PersistentGuid=", f"{link},PersistentGuid=", 1)
            self.text = "\n".join(lines)
            return
        raise RuntimeError(f"Could not link {self.key}.{pin_name}")


def connect(a: Node, a_pin: str, b: Node, b_pin: str) -> None:
    a.link(a_pin, b, b_pin)
    b.link(b_pin, a, a_pin)


def set_pin_default(node: Node, pin_name: str, value: str) -> None:
    def mutate(line: str) -> str:
        if "DefaultValue=" in line:
            line = re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, count=1)
        else:
            line = line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1)
        return line

    node.mutate_pin(pin_name, mutate)


def set_array_add_element_type(node: Node, kind: str) -> None:
    def mutate_real(line: str) -> str:
        line = line.replace('PinType.PinCategory="int"', 'PinType.PinCategory="real"')
        return line.replace('PinType.PinSubCategory=""', 'PinType.PinSubCategory="double"', 1)

    def mutate_transform(line: str) -> str:
        line = line.replace('PinType.PinCategory="int"', 'PinType.PinCategory="struct"')
        return line.replace(
            "PinType.PinSubCategoryObject=None",
            "PinType.PinSubCategoryObject=\"/Script/CoreUObject.ScriptStruct'"
            "/Script/CoreUObject.Transform'\"",
            1,
        )

    if kind == "real":
        node.mutate_pin("TargetArray", mutate_real)
        node.mutate_pin("NewItem", mutate_real)
    elif kind == "transform":
        node.mutate_pin("TargetArray", mutate_transform)
        node.mutate_pin("NewItem", mutate_transform)
    elif kind != "int":
        raise RuntimeError(f"Unsupported array element type: {kind}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    snippets = args.project_root / "tools" / "blueprint" / "snippets"
    forms = read_blocks(
        args.project_root
        / "tools"
        / "blueprint"
        / "templates"
        / "waypoint-capture-node-forms.eddgraph"
    )
    enter = read_blocks(snippets / "enter-drone-mode.eddgraph")

    templates = {
        "entry": find_block(forms, r"K2Node_FunctionEntry"),
        "ids": find_block(forms, r'MemberName="DraftWaypointIds"'),
        "transforms": find_block(forms, r'MemberName="DraftWaypointTransforms"'),
        "focals": find_block(forms, r'MemberName="DraftWaypointFocalLengths"'),
        "apertures": find_block(forms, r'MemberName="DraftWaypointApertures"'),
        "focuses": find_block(forms, r'MemberName="DraftWaypointFocusDistances"'),
        "holds": find_block(forms, r'MemberName="DraftWaypointHoldSeconds"'),
        "next_get": find_block(
            forms, r"K2Node_VariableGet.*?MemberName=\"NextWaypointId\""
        ),
        "next_set": find_block(
            forms, r"K2Node_VariableSet.*?MemberName=\"NextWaypointId\""
        ),
        "drone": find_block(forms, r'MemberName="DroneCameraRef"'),
        "focal": find_block(forms, r'MemberName="FocalLength"'),
        "aperture": find_block(forms, r'MemberName="Aperture"'),
        "focus": find_block(forms, r'MemberName="ManualFocusDistance"'),
        "transform": find_block(forms, r'MemberName="GetTransform"'),
        "array_add": find_block(forms, r'MemberName="Array_Add"'),
        "int_add": find_block(forms, r'OperationName="Add".*?Add_IntInt'),
        "valid": find_block(enter, r'MemberName="IsValid"'),
        "branch": find_block(
            enter,
            r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse\b",
        ),
        "print": find_block(enter, r'MemberName="PrintString"'),
    }

    nodes: dict[str, Node] = {}

    def add(key: str, template_key: str, name: str, x: int, y: int) -> Node:
        node = Node.clone(key, templates[template_key], name, x, y)
        nodes[key] = node
        return node

    entry = add("entry", "entry", "K2Node_FunctionEntry_0", 0, 0)
    branch = add("branch", "branch", "K2Node_IfThenElse_0", 256, 0)
    drone = add("drone", "drone", "K2Node_VariableGet_0", 0, 240)
    valid = add("valid", "valid", "K2Node_CallFunction_0", 256, 208)

    ids = add("ids", "ids", "K2Node_VariableGet_1", 432, 240)
    next_get = add("next_get", "next_get", "K2Node_VariableGet_2", 432, 336)
    add_id = add("add_id", "array_add", "K2Node_CallArrayFunction_0", 672, 0)

    transforms = add("transforms", "transforms", "K2Node_VariableGet_3", 816, 240)
    transform = add("transform", "transform", "K2Node_CallFunction_1", 816, 336)
    add_transform = add(
        "add_transform", "array_add", "K2Node_CallArrayFunction_1", 1104, 0
    )
    set_array_add_element_type(add_transform, "transform")

    focals = add("focals", "focals", "K2Node_VariableGet_4", 1248, 240)
    focal = add("focal", "focal", "K2Node_VariableGet_5", 1248, 336)
    add_focal = add("add_focal", "array_add", "K2Node_CallArrayFunction_2", 1536, 0)
    set_array_add_element_type(add_focal, "real")

    apertures = add("apertures", "apertures", "K2Node_VariableGet_6", 1680, 240)
    aperture = add("aperture", "aperture", "K2Node_VariableGet_7", 1680, 336)
    add_aperture = add(
        "add_aperture", "array_add", "K2Node_CallArrayFunction_3", 1968, 0
    )
    set_array_add_element_type(add_aperture, "real")

    focuses = add("focuses", "focuses", "K2Node_VariableGet_8", 2112, 240)
    focus = add("focus", "focus", "K2Node_VariableGet_9", 2112, 336)
    add_focus = add("add_focus", "array_add", "K2Node_CallArrayFunction_4", 2400, 0)
    set_array_add_element_type(add_focus, "real")

    holds = add("holds", "holds", "K2Node_VariableGet_10", 2544, 240)
    add_hold = add("add_hold", "array_add", "K2Node_CallArrayFunction_5", 2832, 0)
    set_array_add_element_type(add_hold, "real")
    set_pin_default(add_hold, "NewItem", "0.0")

    int_add = add("int_add", "int_add", "K2Node_PromotableOperator_0", 2832, 336)
    set_pin_default(int_add, "B", "1")
    next_set = add("next_set", "next_set", "K2Node_VariableSet_0", 3264, 0)
    print_node = add("print", "print", "K2Node_CallFunction_2", 3648, 0)
    set_pin_default(print_node, "InString", "[EDD] Waypoint captured")

    connect(entry, "then", branch, "execute")
    connect(drone, "DroneCameraRef", valid, "Object")
    connect(valid, "ReturnValue", branch, "Condition")

    exec_chain = [
        branch,
        add_id,
        add_transform,
        add_focal,
        add_aperture,
        add_focus,
        add_hold,
        next_set,
        print_node,
    ]
    connect(exec_chain[0], "then", exec_chain[1], "execute")
    for before, after in zip(exec_chain[1:], exec_chain[2:]):
        connect(before, "then", after, "execute")

    connect(ids, "DraftWaypointIds", add_id, "TargetArray")
    connect(next_get, "NextWaypointId", add_id, "NewItem")
    connect(next_get, "NextWaypointId", int_add, "A")
    connect(int_add, "ReturnValue", next_set, "NextWaypointId")

    connect(transforms, "DraftWaypointTransforms", add_transform, "TargetArray")
    connect(drone, "DroneCameraRef", transform, "self")
    connect(transform, "ReturnValue", add_transform, "NewItem")

    connect(focals, "DraftWaypointFocalLengths", add_focal, "TargetArray")
    connect(drone, "DroneCameraRef", focal, "self")
    connect(focal, "FocalLength", add_focal, "NewItem")

    connect(apertures, "DraftWaypointApertures", add_aperture, "TargetArray")
    connect(drone, "DroneCameraRef", aperture, "self")
    connect(aperture, "Aperture", add_aperture, "NewItem")

    connect(focuses, "DraftWaypointFocusDistances", add_focus, "TargetArray")
    connect(drone, "DroneCameraRef", focus, "self")
    connect(focus, "ManualFocusDistance", add_focus, "NewItem")
    connect(holds, "DraftWaypointHoldSeconds", add_hold, "TargetArray")

    ordered = list(nodes.values())
    full_text = "\n".join(node.text for node in ordered) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full_text, encoding="utf-8")
    if args.paste_output:
        paste_text = "\n".join(node.text for node in ordered if node.key != "entry") + "\n"
        paste_text = re.sub(
            r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)",
            "",
            paste_text,
            count=1,
        )
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste_text, encoding="utf-8")


if __name__ == "__main__":
    main()
