"""Append guarded R/Delete waypoint edit dispatch after the reviewed K capture gate."""

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
        f"exile-drone-director:client-waypoint-edit-dispatch:{_id_counter}",
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
            lines[index] = line[: existing.start()] + f",LinkedTo=({links})" + line[existing.end() :]
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


def connect(blocks: dict[str, str], left_name: str, left_pin: str, right_name: str, right_pin: str) -> None:
    left_pins = pin_map(blocks[left_name])
    right_pins = pin_map(blocks[right_name])
    blocks[left_name] = add_link(blocks[left_name], left_pins[left_pin], right_name, right_pins[right_pin])
    blocks[right_name] = add_link(blocks[right_name], right_pins[right_pin], left_name, left_pins[left_pin])


def key_value(block: str) -> str | None:
    match = re.search(r'PinName="Key"[^\r\n]*DefaultValue="([^"]+)"', block)
    return match.group(1) if match else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    replace_count = text.count('MemberName="ReplaceSelectedWaypoint"')
    delete_count = text.count('MemberName="DeleteSelectedWaypoint"')
    if replace_count == 1 and delete_count == 1:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(args.input.read_bytes())
        print("Client graph already contains exactly one replace and delete dispatch; output unchanged.")
        return
    if replace_count or delete_count:
        raise RuntimeError(
            f"Input has a partial edit dispatch: replace={replace_count}, delete={delete_count}"
        )

    source_blocks = [match.group(0) for match in BLOCK_RE.finditer(text)]
    capture = find_one(source_blocks, 'MemberName="CaptureCurrentWaypoint"')
    key_k = find_one(
        [block for block in source_blocks if 'MemberName="WasInputKeyJustPressed"' in block],
        'DefaultValue="K"',
    )
    capture_branches = [
        block
        for block in source_blocks
        if block.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_IfThenElse ")
        and block_name(key_k) in block
    ]
    if len(capture_branches) != 1:
        raise RuntimeError(f"Expected one K capture branch; found {len(capture_branches)}")
    capture_branch = capture_branches[0]

    controller_names = re.findall(
        r"LinkedTo=\((K2Node_CallFunction_\d+) [0-9A-F]{32},\)",
        next(line for line in key_k.splitlines() if 'PinName="self"' in line),
    )
    if len(controller_names) != 1:
        raise RuntimeError("K edge poll must have exactly one Player Controller source")
    controller = find_one(source_blocks, f'Name="{controller_names[0]}"')

    staged = text
    key_r_name = next_name(staged, "K2Node_CallFunction")
    staged += f' Name="{key_r_name}"'
    replace_name = next_name(staged, "K2Node_CallFunction")
    staged += f' Name="{replace_name}"'
    key_delete_name = next_name(staged, "K2Node_CallFunction")
    staged += f' Name="{key_delete_name}"'
    delete_name = next_name(staged, "K2Node_CallFunction")
    staged += f' Name="{delete_name}"'
    replace_branch_name = next_name(staged, "K2Node_IfThenElse")
    staged += f' Name="{replace_branch_name}"'
    delete_branch_name = next_name(staged, "K2Node_IfThenElse")

    blocks = {
        block_name(controller): controller,
        block_name(capture_branch): capture_branch,
        key_r_name: clone_node(key_k, key_r_name, 7168, 704),
        replace_branch_name: clone_node(capture_branch, replace_branch_name, 7488, 576),
        replace_name: clone_node(capture, replace_name, 7712, 576),
        key_delete_name: clone_node(key_k, key_delete_name, 7168, 960),
        delete_branch_name: clone_node(capture_branch, delete_branch_name, 7488, 832),
        delete_name: clone_node(capture, delete_name, 7712, 832),
    }
    blocks[key_r_name] = re.sub(
        r'(PinName="Key"[^\r\n]*?,DefaultValue=")[^"]+', r'\1R', blocks[key_r_name], count=1
    )
    blocks[key_delete_name] = re.sub(
        r'(PinName="Key"[^\r\n]*?,DefaultValue=")[^"]+', r'\1Delete', blocks[key_delete_name], count=1
    )
    blocks[replace_name] = re.sub(
        r'FunctionReference=\([^\n]*MemberName="CaptureCurrentWaypoint"[^\n]*\)',
        'FunctionReference=(MemberName="ReplaceSelectedWaypoint",bSelfContext=True)',
        blocks[replace_name],
        count=1,
    )
    blocks[delete_name] = re.sub(
        r'FunctionReference=\([^\n]*MemberName="CaptureCurrentWaypoint"[^\n]*\)',
        'FunctionReference=(MemberName="DeleteSelectedWaypoint",bSelfContext=True)',
        blocks[delete_name],
        count=1,
    )

    controller_name = block_name(controller)
    capture_branch_name = block_name(capture_branch)
    connect(blocks, capture_branch_name, "else", replace_branch_name, "execute")
    connect(blocks, controller_name, "ReturnValue", key_r_name, "self")
    connect(blocks, key_r_name, "ReturnValue", replace_branch_name, "Condition")
    connect(blocks, replace_branch_name, "then", replace_name, "execute")
    connect(blocks, replace_branch_name, "else", delete_branch_name, "execute")
    connect(blocks, controller_name, "ReturnValue", key_delete_name, "self")
    connect(blocks, key_delete_name, "ReturnValue", delete_branch_name, "Condition")
    connect(blocks, delete_branch_name, "then", delete_name, "execute")

    replacements = {
        controller_name: blocks.pop(controller_name),
        capture_branch_name: blocks.pop(capture_branch_name),
    }
    output_blocks = [replacements.get(block_name(block), block) for block in source_blocks]
    output_blocks.extend(blocks.values())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(output_blocks) + "\n", encoding="utf-8")
    print("Added guarded R replace and Delete removal dispatch after K capture polling.")


if __name__ == "__main__":
    main()
