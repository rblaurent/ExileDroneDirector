"""Contracts for crash-safe Enhanced quaternion call-node reconstruction."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


BLOCK_RE = re.compile(r"(?ms)^Begin Object .*?^End Object\s*$")


def one_pin(block: str, name: str) -> str:
    pins = [line for line in block.splitlines() if f'PinName="{name}"' in line]
    assert len(pins) == 1, f"Expected one {name} pin; found {len(pins)}"
    return pins[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()
    blocks = BLOCK_RE.findall(args.forms.read_text(encoding="utf-8-sig"))
    assert len(blocks) == 5
    assert sum("K2Node_FunctionEntry" in block for block in blocks) == 1
    calls = {}
    for block in blocks:
        match = re.search(r'MemberName="(Quat_[^"]+)"', block)
        if match:
            calls[match.group(1)] = block
    assert set(calls) == {"Quat_IsFinite", "Quat_IsNormalized", "Quat_Normalized", "Quat_Slerp"}
    for block in calls.values():
        assert "bDefaultsToPureFunc=True" in block
        assert "bOrphanedPin=True" not in block
        assert "SubPins=(" not in block
        assert "ParentPin=" not in block
        assert "/Script/Engine.KismetMathLibrary" in block
    finite = calls["Quat_IsFinite"]
    assert "/Script/CoreUObject.Quat" in one_pin(finite, "Q")
    assert 'PinType.PinCategory="bool"' in one_pin(finite, "ReturnValue")
    is_normalized = calls["Quat_IsNormalized"]
    assert "/Script/CoreUObject.Quat" in one_pin(is_normalized, "Q")
    assert 'PinType.PinCategory="bool"' in one_pin(is_normalized, "ReturnValue")
    normalized = calls["Quat_Normalized"]
    assert 'PinType.PinSubCategory="float"' in one_pin(normalized, "Tolerance")
    assert 'DefaultValue="0.000100"' in one_pin(normalized, "Tolerance")
    assert "/Script/CoreUObject.Quat" in one_pin(normalized, "ReturnValue")
    slerp = calls["Quat_Slerp"]
    for name in ("A", "B"):
        pin = one_pin(slerp, name)
        assert "/Script/CoreUObject.Quat" in pin
        assert "PinType.bIsReference=True" in pin
        assert "PinType.bIsConst=True" in pin
    assert 'PinType.PinSubCategory="double"' in one_pin(slerp, "Alpha")
    assert "/Script/CoreUObject.Quat" in one_pin(slerp, "ReturnValue")
    print("Trajectory quaternion native node-form contracts passed")


if __name__ == "__main__":
    main()
