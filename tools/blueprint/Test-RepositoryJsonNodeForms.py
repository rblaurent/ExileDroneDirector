"""Semantic contracts for the reviewed Enhanced PlayFab JSON node forms."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


BLOCK_RE = re.compile(r"(?ms)^Begin Object .*?^End Object\s*$")


EXPECTED_PINS = {
    "ConstructJsonObject": {"self", "WorldContextObject", "ReturnValue"},
    "SetStringField": {"execute", "then", "self", "FieldName", "StringValue"},
    "GetStringField": {"self", "FieldName", "ReturnValue"},
    "SetBoolField": {"execute", "then", "self", "FieldName", "InValue"},
    "GetBoolField": {"self", "FieldName", "ReturnValue"},
    "SetNumberField": {"execute", "then", "self", "FieldName", "Number"},
    "GetNumberField": {"self", "FieldName", "ReturnValue"},
    "SetStringArrayField": {"execute", "then", "self", "FieldName", "StringArray"},
    "GetStringArrayField": {"execute", "then", "self", "FieldName", "ReturnValue"},
    "SetNumberArrayField": {"execute", "then", "self", "FieldName", "NumberArray"},
    "GetNumberArrayField": {"execute", "then", "self", "FieldName", "ReturnValue"},
    "SetObjectField": {"execute", "then", "self", "FieldName", "JsonObject"},
    "GetObjectField": {"self", "FieldName", "ReturnValue"},
    "SetObjectArrayField": {"execute", "then", "self", "FieldName", "ObjectArray"},
    "GetObjectArrayField": {"execute", "then", "self", "FieldName", "ReturnValue"},
    "GetFieldNames": {"self", "ReturnValue"},
    "SetFieldNull": {"execute", "then", "self", "FieldName"},
    "GetField": {"self", "FieldName", "ReturnValue"},
    "HasField": {"self", "FieldName", "ReturnValue"},
    "IsNull": {"self", "ReturnValue"},
    "EncodeJson": {"self", "ReturnValue"},
    "DecodeJson": {"execute", "then", "self", "JsonString", "ReturnValue"},
}


PURE_FUNCTIONS = {
    "ConstructJsonObject",
    "GetStringField",
    "GetBoolField",
    "GetNumberField",
    "GetObjectField",
    "GetField",
    "GetFieldNames",
    "HasField",
    "IsNull",
    "EncodeJson",
}


def pin_line(block: str, name: str) -> str:
    matches = [
        line for line in block.splitlines() if f'PinName="{name}"' in line
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name} pin; found {len(matches)}")
    return matches[0]


def require_type(
    block: str,
    name: str,
    category: str,
    *,
    array: bool = False,
    subcategory: str | None = None,
) -> None:
    line = pin_line(block, name)
    assert f'PinType.PinCategory="{category}"' in line, (name, line)
    if subcategory is not None:
        assert f'PinType.PinSubCategory="{subcategory}"' in line, (name, line)
    expected_container = "Array" if array else "None"
    assert f"PinType.ContainerType={expected_container}" in line, (name, line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()
    text = args.forms.read_text(encoding="utf-8-sig")
    blocks = BLOCK_RE.findall(text)
    calls: dict[str, str] = {}
    for block in blocks:
        if "K2Node_CallFunction" not in block:
            continue
        match = re.search(r'MemberName="([^"]+)"', block)
        assert match is not None, "Call node has no native member"
        name = match.group(1)
        assert name not in calls, f"Duplicate native JSON form: {name}"
        calls[name] = block

    assert set(calls) == set(EXPECTED_PINS), (
        f"JSON node-form set changed; missing={sorted(set(EXPECTED_PINS) - set(calls))}, "
        f"extra={sorted(set(calls) - set(EXPECTED_PINS))}"
    )
    for name, expected_pins in EXPECTED_PINS.items():
        block = calls[name]
        actual_pins = set(re.findall(r'PinName="([^"]+)"', block))
        assert actual_pins == expected_pins, (name, actual_pins, expected_pins)
        assert "bOrphanedPin=True" not in block, f"{name} contains an orphaned pin"
        assert ("bDefaultsToPureFunc=True" in block) == (name in PURE_FUNCTIONS), name
        if name == "IsNull":
            assert "/Script/PlayFab.PlayFabJsonValue" in block, name
        elif name != "ConstructJsonObject":
            assert "/Script/PlayFab.PlayFabJsonObject" in block, name

    for name in ("GetStringField", "EncodeJson"):
        require_type(calls[name], "ReturnValue", "string")
    for name in ("GetBoolField", "HasField", "IsNull", "DecodeJson"):
        require_type(calls[name], "ReturnValue", "bool")
    for name in ("GetStringArrayField", "GetFieldNames"):
        require_type(calls[name], "ReturnValue", "string", array=True)
    for name in ("GetObjectField", "ConstructJsonObject"):
        require_type(calls[name], "ReturnValue", "object")
    require_type(calls["GetObjectArrayField"], "ReturnValue", "object", array=True)
    require_type(calls["SetNumberField"], "Number", "real", subcategory="float")
    require_type(calls["GetNumberField"], "ReturnValue", "real", subcategory="float")
    require_type(
        calls["SetNumberArrayField"],
        "NumberArray",
        "real",
        array=True,
        subcategory="float",
    )
    require_type(
        calls["GetNumberArrayField"],
        "ReturnValue",
        "real",
        array=True,
        subcategory="float",
    )
    require_type(calls["GetField"], "ReturnValue", "object")
    assert "/Script/PlayFab.PlayFabJsonValue" in pin_line(
        calls["GetField"], "ReturnValue"
    )
    require_type(calls["DecodeJson"], "JsonString", "string")
    print("Repository JSON native node-form contracts passed")


if __name__ == "__main__":
    main()
