"""Contracts for the editor-compiled Transform codec node forms."""

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


def require_struct(pin: str, struct_name: str, *, output: bool) -> None:
    assert 'PinType.PinCategory="struct"' in pin
    assert f"/Script/CoreUObject.{struct_name}" in pin
    assert ('Direction="EGPD_Output"' in pin) == output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()
    text = args.forms.read_text(encoding="utf-8-sig")
    blocks = BLOCK_RE.findall(text)
    assert len(blocks) == 3
    calls = {}
    for block in blocks:
        if "K2Node_CallFunction" not in block:
            continue
        match = re.search(r'MemberName="([^"]+)"', block)
        assert match is not None
        calls[match.group(1)] = block
    assert set(calls) == {"BreakTransform", "MakeTransform"}
    assert all("bDefaultsToPureFunc=True" in block for block in calls.values())
    assert all("bOrphanedPin=True" not in block for block in calls.values())
    assert all("/Script/Engine.KismetMathLibrary" in block for block in calls.values())

    split = calls["BreakTransform"]
    input_pin = one_pin(split, "InTransform")
    require_struct(input_pin, "Transform", output=False)
    assert "PinType.bIsReference=True" in input_pin
    assert "PinType.bIsConst=True" in input_pin
    require_struct(one_pin(split, "Location"), "Vector", output=True)
    require_struct(one_pin(split, "Rotation"), "Rotator", output=True)
    require_struct(one_pin(split, "Scale"), "Vector", output=True)

    make = calls["MakeTransform"]
    require_struct(one_pin(make, "Location"), "Vector", output=False)
    require_struct(one_pin(make, "Rotation"), "Rotator", output=False)
    scale = one_pin(make, "Scale")
    require_struct(scale, "Vector", output=False)
    assert 'DefaultValue="1.000000,1.000000,1.000000"' in scale
    require_struct(one_pin(make, "ReturnValue"), "Transform", output=True)
    print("Repository codec Transform node-form contracts passed")


if __name__ == "__main__":
    main()
