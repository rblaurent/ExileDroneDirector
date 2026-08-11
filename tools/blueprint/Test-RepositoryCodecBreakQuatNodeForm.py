"""Contracts for the editor-harvested native BreakQuat node form."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()

    text = args.forms.read_text(encoding="utf-8-sig")
    blocks = BLOCK_RE.findall(text)
    assert len(blocks) == 2, f"Expected entry plus BreakQuat; found {len(blocks)}"
    assert sum("K2Node_FunctionEntry" in block for block in blocks) == 1

    calls = [block for block in blocks if "K2Node_CallFunction" in block]
    assert len(calls) == 1, f"Expected one function call; found {len(calls)}"
    node = calls[0]
    assert 'MemberName="BreakQuat"' in node
    assert 'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetMathLibrary\'"' in node
    assert "bDefaultsToPureFunc=True" in node
    assert "bOrphanedPin=True" not in node

    quat = one_pin(node, "InQuat")
    assert "/Script/CoreUObject.Quat" in quat
    assert "PinType.bIsReference=True" in quat
    assert "PinType.bIsConst=True" in quat
    assert 'Direction="EGPD_Output"' not in quat

    for axis in "XYZW":
        pin = one_pin(node, axis)
        assert 'Direction="EGPD_Output"' in pin
        assert 'PinType.PinCategory="real"' in pin
        assert 'PinType.PinSubCategory="float"' in pin

    pin_lines = [line for line in node.splitlines() if "CustomProperties Pin" in line]
    assert len(pin_lines) == 6, f"Expected self plus five BreakQuat pins; found {len(pin_lines)}"
    print("Repository codec BreakQuat node-form contracts passed")


if __name__ == "__main__":
    main()
