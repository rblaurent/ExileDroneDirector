"""Append ordered roll/horizon dispatch to the reviewed client EventGraph."""

from __future__ import annotations

import argparse
import re
import uuid
from pathlib import Path


BLOCK_RE = re.compile(
    r"^Begin Object Class=(?P<class>\S+) Name=\"(?P<name>[^\"]+)\".*?^End Object\r?$",
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r'^\s*CustomProperties Pin \(.*?PinName="(?P<name>[^"]+)".*\)$')


def new_id() -> str:
    return uuid.uuid4().hex.upper()


def pin_map(block: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in block.splitlines():
        match = PIN_RE.match(line)
        if match:
            pin_id = re.search(r"PinId=([0-9A-F]{32})", line)
            if pin_id is None:
                raise RuntimeError(f"Pin {match.group('name')} has no identifier")
            result[match.group("name")] = pin_id.group(1)
    return result


def add_link(block: str, pin_id: str, other_name: str, other_pin_id: str) -> str:
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if f"PinId={pin_id}" not in line:
            continue
        existing = re.search(r",LinkedTo=\((?P<links>[^)]*)\)", line)
        if existing:
            links = existing.group("links") + f"{other_name} {other_pin_id},"
            lines[index] = (
                line[: existing.start()]
                + f",LinkedTo=({links})"
                + line[existing.end() :]
            )
        else:
            lines[index] = line.replace(
                ",PersistentGuid=",
                f",LinkedTo=({other_name} {other_pin_id},),PersistentGuid=",
                1,
            )
        return "\n".join(lines)
    raise RuntimeError(f"Could not find pin {pin_id}")


def clone_roll_call(rotation: str, new_name: str) -> tuple[str, dict[str, str]]:
    old_name = BLOCK_RE.match(rotation).group("name")
    block = rotation.replace(f'Name="{old_name}"', f'Name="{new_name}"', 1)
    block = block.replace(f".{old_name}'\"", f".{new_name}'\"", 1)
    block = re.sub(
        r'MemberName="ApplyRotationInput",MemberGuid=[0-9A-F]{32}',
        'MemberName="ApplyRollAndHorizonInput"',
        block,
        count=1,
    )
    block = re.sub(r"NodePosX=\-?\d+", "NodePosX=4960", block, count=1)
    block = re.sub(r"NodePosY=\-?\d+", "NodePosY=320", block, count=1)
    block = re.sub(r"NodeGuid=[0-9A-F]{32}", f"NodeGuid={new_id()}", block, count=1)
    block = re.sub(r",LinkedTo=\([^)]*\)", "", block)

    pins: dict[str, str] = {}
    rebuilt: list[str] = []
    for line in block.splitlines():
        match = PIN_RE.match(line)
        if match:
            pin_id = new_id()
            line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={pin_id}", line, count=1)
            pins[match.group("name")] = pin_id
        rebuilt.append(line)
    return "\n".join(rebuilt), pins


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    existing_roll_calls = text.count('MemberName="ApplyRollAndHorizonInput"')
    if existing_roll_calls > 1:
        raise RuntimeError(
            f"Input already contains {existing_roll_calls} roll calls; expected at most one"
        )
    if existing_roll_calls == 1:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(args.input.read_bytes())
        print("Client graph already contains exactly one roll dispatch; output unchanged.")
        return

    blocks = [match.group(0) for match in BLOCK_RE.finditer(text)]
    rotation_index = next(
        index for index, block in enumerate(blocks) if 'MemberName="ApplyRotationInput"' in block
    )
    camera_index = next(
        index
        for index, block in enumerate(blocks)
        if 'Name="K2Node_VariableGet_2"' in block and 'MemberName="DroneCameraRef"' in block
    )

    call_indexes = [
        int(value)
        for value in re.findall(r'Name="K2Node_CallFunction_(\d+)"', text)
    ]
    new_name = f"K2Node_CallFunction_{max(call_indexes) + 1}"
    roll, roll_pins = clone_roll_call(blocks[rotation_index], new_name)
    rotation_pins = pin_map(blocks[rotation_index])
    camera_pins = pin_map(blocks[camera_index])

    blocks[rotation_index] = add_link(
        blocks[rotation_index], rotation_pins["then"], new_name, roll_pins["execute"]
    )
    roll = add_link(
        roll, roll_pins["execute"], BLOCK_RE.match(blocks[rotation_index]).group("name"), rotation_pins["then"]
    )
    blocks[camera_index] = add_link(
        blocks[camera_index], camera_pins["DroneCameraRef"], new_name, roll_pins["self"]
    )
    roll = add_link(
        roll, roll_pins["self"], BLOCK_RE.match(blocks[camera_index]).group("name"), camera_pins["DroneCameraRef"]
    )
    blocks.append(roll)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(blocks) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
