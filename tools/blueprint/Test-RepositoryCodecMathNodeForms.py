"""Contracts for the editor-compiled quaternion codec node forms."""

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
    assert len(blocks) == 3, f"Expected entry plus two math calls; found {len(blocks)}"
    assert sum("K2Node_FunctionEntry" in block for block in blocks) == 1

    calls: dict[str, str] = {}
    for block in blocks:
        if "K2Node_CallFunction" not in block:
            continue
        match = re.search(r'MemberName="([^"]+)"', block)
        assert match is not None
        calls[match.group(1)] = block

    assert set(calls) == {"Conv_RotatorToQuaternion", "Quat_Rotator"}
    assert all("bDefaultsToPureFunc=True" in block for block in calls.values())
    assert all("bOrphanedPin=True" not in block for block in calls.values())
    assert all("/Script/Engine.KismetMathLibrary" in block for block in calls.values())

    encode = calls["Conv_RotatorToQuaternion"]
    assert "/Script/CoreUObject.Rotator" in one_pin(encode, "InRot")
    encode_parent = one_pin(encode, "ReturnValue")
    assert "/Script/CoreUObject.Quat" in encode_parent
    assert "bHidden=True" in encode_parent
    assert "SubPins=(" in encode_parent
    for axis in "XYZW":
        pin = one_pin(encode, f"ReturnValue_{axis}")
        assert 'Direction="EGPD_Output"' in pin
        assert 'PinType.PinCategory="real"' in pin
        assert 'PinType.PinSubCategory="float"' in pin
        assert "ParentPin=" in pin

    decode = calls["Quat_Rotator"]
    decode_parent = one_pin(decode, "Q")
    assert "/Script/CoreUObject.Quat" in decode_parent
    assert "PinType.bIsReference=True" in decode_parent
    assert "PinType.bIsConst=True" in decode_parent
    assert "bHidden=True" in decode_parent
    assert "SubPins=(" in decode_parent
    for axis in "XYZW":
        pin = one_pin(decode, f"Q_{axis}")
        assert 'Direction="EGPD_Output"' not in pin
        assert 'PinType.PinCategory="real"' in pin
        assert 'PinType.PinSubCategory="float"' in pin
        assert "ParentPin=" in pin
    assert "/Script/CoreUObject.Rotator" in one_pin(decode, "ReturnValue")

    print("Repository codec quaternion node-form contracts passed")


if __name__ == "__main__":
    main()
