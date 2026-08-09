"""Build the native Unreal clipboard graph for smooth manual drone roll.

This tool clones node forms that were exported from compiled mod-owned graphs,
assigns fresh node and pin identifiers, and writes every link reciprocally.  It
does not edit a .uasset; the resulting text is pasted into the intended
Blueprint function and then exported back out for contract validation.
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
    "/Game/Mods/ExileDroneDirector/Core/Camera/"
    "BP_EDD_DroneCamera.BP_EDD_DroneCamera"
)
TARGET_GRAPH = "ApplyRollAndHorizonInput"


def new_id() -> str:
    return uuid.uuid4().hex.upper()


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
        replacements: dict[str, str] | None = None,
    ) -> "Node":
        header = BLOCK_RE.match(template)
        if header is None:
            raise RuntimeError(f"Invalid node template for {key}")
        old_name = header.group("name")
        text = template.replace(f'Name="{old_name}"', f'Name="{name}"', 1)
        text = re.sub(
            r'ExportPath="[^"]+"',
            f'ExportPath="/Script/BlueprintGraph.{header.group("class").rsplit(".", 1)[-1]}'
            f"'{TARGET_ASSET}:{TARGET_GRAPH}.{name}'\"",
            text,
            count=1,
        )
        text = re.sub(r"^\s*NodePosX=.*\r?\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*NodePosY=.*\r?\n", "", text, flags=re.MULTILINE)
        text = text.replace("   NodeGuid=", f"   NodePosX={x}\n   NodePosY={y}\n   NodeGuid=", 1)
        text = re.sub(r"NodeGuid=[0-9A-F]{32}", f"NodeGuid={new_id()}", text)
        text = re.sub(r",LinkedTo=\([^)]*\)", "", text)
        if replacements:
            for old, new in replacements.items():
                text = text.replace(old, new)

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    snippets = args.project_root / "tools" / "blueprint" / "snippets"
    seed_blocks = read_blocks(args.seed)
    translation = read_blocks(snippets / "apply-translation-input.eddgraph")
    rotation = read_blocks(snippets / "apply-rotation-input.eddgraph")
    speed = read_blocks(snippets / "update-speed-controls.eddgraph")

    templates = {
        "entry": find_block(seed_blocks, r"K2Node_FunctionEntry"),
        "manual": find_block(seed_blocks, r'MemberName="ManualRollSpeed"'),
        "current": find_block(seed_blocks, r'MemberName="CurrentRollSpeed"'),
        "response": find_block(seed_blocks, r'MemberName="RollInputResponse"'),
        "setter": find_block(speed, r"K2Node_VariableSet.*?MemberName=\"CurrentMoveSpeed\""),
        "controller": find_block(translation, r'MemberName="GetPlayerController"'),
        "analog": find_block(translation, r'MemberName="GetInputAnalogKeyState"'),
        "subtract": find_block(translation, r'OperationName="Subtract"'),
        "multiply": find_block(speed, r'OperationName="Multiply".*?Multiply_DoubleDouble'),
        "delta": find_block(speed, r'MemberName="GetWorldDeltaSeconds"'),
        "interp": find_block(speed, r'MemberName="FInterpTo"'),
        "rotator": find_block(rotation, r'MemberName="MakeRotator"'),
        "rotate": find_block(rotation, r'MemberName="K2_AddActorLocalRotation"'),
    }

    current_guid = re.search(
        r'MemberName="CurrentRollSpeed",MemberGuid=([0-9A-F]{32})', templates["current"]
    )
    if current_guid is None:
        raise RuntimeError("CurrentRollSpeed seed has no member GUID")

    counts: dict[str, int] = {}

    def make(key: str, template_key: str, x: int, y: int, replacements=None) -> Node:
        node_class = BLOCK_RE.match(templates[template_key]).group("class").rsplit(".", 1)[-1]
        index = counts.get(node_class, 0)
        counts[node_class] = index + 1
        return Node.clone(
            key,
            templates[template_key],
            f"{node_class}_{index}",
            x,
            y,
            replacements,
        )

    nodes = {
        "entry": make("entry", "entry", 0, 0),
        "setter": make(
            "setter",
            "setter",
            1450,
            0,
            {
                'MemberName="CurrentMoveSpeed",MemberGuid=7B898E994928FE7FABF311838CD1AFAE':
                    f'MemberName="CurrentRollSpeed",MemberGuid={current_guid.group(1)}',
                'PinName="CurrentMoveSpeed"': 'PinName="CurrentRollSpeed"',
            },
        ),
        "controller": make("controller", "controller", 0, 450),
        "c": make(
            "c",
            "analog",
            300,
            300,
            {'DefaultValue="W"': 'DefaultValue="C"'},
        ),
        "z": make(
            "z",
            "analog",
            300,
            550,
            {'DefaultValue="W"': 'DefaultValue="Z"'},
        ),
        "subtract": make("subtract", "subtract", 600, 400),
        "manual": make("manual", "manual", 600, 650),
        "target": make("target", "multiply", 850, 450),
        "current": make("current", "current", 900, 50),
        "delta": make("delta", "delta", 900, 200),
        "response": make("response", "response", 900, 300),
        "interp": make("interp", "interp", 1150, 100),
        "roll_delta": make("roll_delta", "multiply", 1700, 250),
        "rotator": make("rotator", "rotator", 1950, 150),
        "rotate": make("rotate", "rotate", 2200, 0),
    }

    connect(nodes["entry"], "then", nodes["setter"], "execute")
    connect(nodes["setter"], "then", nodes["rotate"], "execute")
    connect(nodes["controller"], "ReturnValue", nodes["c"], "self")
    connect(nodes["controller"], "ReturnValue", nodes["z"], "self")
    connect(nodes["c"], "ReturnValue", nodes["subtract"], "A")
    connect(nodes["z"], "ReturnValue", nodes["subtract"], "B")
    connect(nodes["subtract"], "ReturnValue", nodes["target"], "A")
    connect(nodes["manual"], "ManualRollSpeed", nodes["target"], "B")
    connect(nodes["current"], "CurrentRollSpeed", nodes["interp"], "Current")
    connect(nodes["target"], "ReturnValue", nodes["interp"], "Target")
    connect(nodes["delta"], "ReturnValue", nodes["interp"], "DeltaTime")
    connect(nodes["response"], "RollInputResponse", nodes["interp"], "InterpSpeed")
    connect(nodes["interp"], "ReturnValue", nodes["setter"], "CurrentRollSpeed")
    connect(nodes["setter"], "Output_Get", nodes["roll_delta"], "A")
    connect(nodes["delta"], "ReturnValue", nodes["roll_delta"], "B")
    connect(nodes["roll_delta"], "ReturnValue", nodes["rotator"], "Roll")
    connect(nodes["rotator"], "ReturnValue", nodes["rotate"], "DeltaRotation")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in nodes.values()) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        paste_nodes: list[str] = []
        for key, node in nodes.items():
            if key == "entry":
                continue
            node_text = node.text
            if key == "setter":
                node_text = re.sub(
                    r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)",
                    "",
                    node_text,
                    count=1,
                )
            paste_nodes.append(node_text)
        args.paste_output.write_text(
            "\n".join(paste_nodes) + "\n",
            encoding="utf-8",
        )
        print(
            "Paste output intentionally leaves the first exec pin unlinked; "
            "connect the existing function entry in Unreal, then export and "
            "contract the complete live graph."
        )


if __name__ == "__main__":
    main()
