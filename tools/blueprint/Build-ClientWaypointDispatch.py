"""Append guarded K-key waypoint capture dispatch to the reviewed client EventGraph."""

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


_id_counter = 0


def new_id() -> str:
    global _id_counter
    _id_counter += 1
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"exile-drone-director:client-waypoint-dispatch:{_id_counter}",
    ).hex.upper()


def block_name(block: str) -> str:
    match = BLOCK_RE.match(block)
    if match is None:
        raise RuntimeError("Malformed Blueprint node block")
    return match.group("name")


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


def clone_node(template: str, new_name: str, x: int, y: int) -> str:
    old_name = block_name(template)
    block = template.replace(f'Name="{old_name}"', f'Name="{new_name}"', 1)
    block = block.replace(f".{old_name}'\"", f".{new_name}'\"", 1)
    block = re.sub(r"NodePosX=\-?\d+", f"NodePosX={x}", block, count=1)
    block = re.sub(r"NodePosY=\-?\d+", f"NodePosY={y}", block, count=1)
    block = re.sub(r"NodeGuid=[0-9A-F]{32}", f"NodeGuid={new_id()}", block, count=1)
    block = re.sub(r",LinkedTo=\([^)]*\)", "", block)

    rebuilt: list[str] = []
    for line in block.splitlines():
        if PIN_RE.match(line):
            line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={new_id()}", line, count=1)
        rebuilt.append(line)
    return "\n".join(rebuilt)


def next_name(text: str, prefix: str) -> str:
    indexes = [int(value) for value in re.findall(rf'Name="{re.escape(prefix)}_(\d+)"', text)]
    return f"{prefix}_{max(indexes, default=-1) + 1}"


def find_one(blocks: list[str], marker: str) -> str:
    matches = [block for block in blocks if marker in block]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one node containing {marker!r}; found {len(matches)}")
    return matches[0]


def connect(
    blocks: dict[str, str],
    left_name: str,
    left_pin: str,
    right_name: str,
    right_pin: str,
) -> None:
    left_pins = pin_map(blocks[left_name])
    right_pins = pin_map(blocks[right_name])
    blocks[left_name] = add_link(
        blocks[left_name], left_pins[left_pin], right_name, right_pins[right_pin]
    )
    blocks[right_name] = add_link(
        blocks[right_name], right_pins[right_pin], left_name, left_pins[left_pin]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    capture_calls = text.count('MemberName="CaptureCurrentWaypoint"')
    if capture_calls > 1:
        raise RuntimeError(f"Input contains {capture_calls} capture calls; expected at most one")
    if capture_calls == 1:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(args.input.read_bytes())
        print("Client graph already contains exactly one waypoint dispatch; output unchanged.")
        return

    source_blocks = [match.group(0) for match in BLOCK_RE.finditer(text)]
    template_text = args.templates.read_text(encoding="utf-8")
    template_blocks = [match.group(0) for match in BLOCK_RE.finditer(template_text)]

    roll = find_one(source_blocks, 'MemberName="ApplyRollAndHorizonInput"')
    enter = find_one(source_blocks, 'MemberName="EnterDroneMode"')
    get_controller_template = find_one(template_blocks, 'MemberName="GetPlayerController"')
    key_template = find_one(template_blocks, 'MemberName="WasInputKeyJustPressed"')
    branch_matches = [
        block
        for block in template_blocks
        if block.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_IfThenElse ")
    ]
    if len(branch_matches) != 1:
        raise RuntimeError(
            f"Expected exactly one branch template; found {len(branch_matches)}"
        )
    branch_template = branch_matches[0]

    get_controller_name = next_name(text, "K2Node_CallFunction")
    staged_text = text + f' Name="{get_controller_name}"'
    key_name = next_name(staged_text, "K2Node_CallFunction")
    staged_text += f' Name="{key_name}"'
    capture_name = next_name(staged_text, "K2Node_CallFunction")
    branch_name = next_name(text, "K2Node_IfThenElse")

    new_blocks = {
        block_name(roll): roll,
        get_controller_name: clone_node(get_controller_template, get_controller_name, 5888, 656),
        key_name: clone_node(key_template, key_name, 5888, 512),
        branch_name: clone_node(branch_template, branch_name, 6208, 384),
        capture_name: clone_node(enter, capture_name, 6432, 384),
    }
    new_blocks[key_name] = new_blocks[key_name].replace(
        'DefaultValue="{{INPUT_KEY}}"', 'DefaultValue="K"', 1
    )
    new_blocks[capture_name] = re.sub(
        r'FunctionReference=\([^\n]*MemberName="EnterDroneMode"[^\n]*\)',
        'FunctionReference=(MemberName="CaptureCurrentWaypoint",bSelfContext=True)',
        new_blocks[capture_name],
        count=1,
    )

    roll_name = block_name(roll)
    connect(new_blocks, roll_name, "then", branch_name, "execute")
    connect(new_blocks, get_controller_name, "ReturnValue", key_name, "self")
    connect(new_blocks, key_name, "ReturnValue", branch_name, "Condition")
    connect(new_blocks, branch_name, "then", capture_name, "execute")

    replacements = {roll_name: new_blocks.pop(roll_name)}
    output_blocks = [replacements.get(block_name(block), block) for block in source_blocks]
    output_blocks.extend(new_blocks.values())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(output_blocks) + "\n", encoding="utf-8")
    print("Added K-key waypoint capture dispatch after roll/horizon processing.")


if __name__ == "__main__":
    main()
