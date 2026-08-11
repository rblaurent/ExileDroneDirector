"""Contracts for the editor-compiled float Make Array codec node form."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


BLOCK_RE = re.compile(r"(?ms)^Begin Object .*?^End Object\s*$")


def one_pin(block: str, name: str) -> str:
    matches = [line for line in block.splitlines() if f'PinName="{name}"' in line]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name} pin; found {len(matches)}")
    return matches[0]


def require_float(pin: str, *, array: bool, output: bool) -> None:
    assert 'PinType.PinCategory="real"' in pin
    assert 'PinType.PinSubCategory="float"' in pin
    assert f'PinType.ContainerType={"Array" if array else "None"}' in pin
    assert ('Direction="EGPD_Output"' in pin) == output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()
    text = args.forms.read_text(encoding="utf-8-sig")
    blocks = BLOCK_RE.findall(text)
    assert len(blocks) == 1
    block = blocks[0]
    assert "K2Node_MakeArray" in block
    assert "NumInputs=4" in block
    assert "bOrphanedPin=True" not in block

    pin_names = re.findall(r'PinName="([^"]+)"', block)
    assert pin_names == ["Array", "[0]", "[1]", "[2]", "[3]"]

    output = one_pin(block, "Array")
    require_float(output, array=True, output=True)
    assert "PinType.bIsReference=True" in output
    assert "PinType.bIsConst=True" in output

    for index in range(4):
        item = one_pin(block, f"[{index}]")
        require_float(item, array=False, output=False)
        assert "PinType.bIsReference=False" in item
        assert "PinType.bIsConst=False" in item

    print("Repository codec Make Array node-form contracts passed")


if __name__ == "__main__":
    main()
