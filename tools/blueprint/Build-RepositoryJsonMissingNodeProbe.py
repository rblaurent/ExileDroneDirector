"""Build probe nodes for PlayFab JSON functions hidden from the action menu.

Enhanced exposes these UFunctions to reflection, but the Blueprint action menu
does not list them reliably.  We derive their call-node shapes from harvested
native sibling functions, paste them into the disposable probe Blueprint, and
accept them only after Unreal compiles and exports them back verbatim.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Developer/Automation/"
    "BP_EDD_JsonNodeProbe.BP_EDD_JsonNodeProbe"
)
TARGET_GRAPH = "ProbeJsonNodesV1"


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_json_probe_graph_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.TARGET_ASSET = TARGET_ASSET
    module.TARGET_GRAPH = TARGET_GRAPH
    return module


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name)
    node.text = "\n".join(
        line for line in node.text.splitlines() if f"PinId={pin_id}" not in line
    )


def rename_pin(node, old_name: str, new_name: str) -> None:
    node.text = node.text.replace(f'PinName="{old_name}"', f'PinName="{new_name}"')
    node.pins[new_name] = node.pins.pop(old_name)


def retarget(node, function_name: str) -> None:
    node.text = re.sub(
        r'MemberName="[^"]+"', f'MemberName="{function_name}"', node.text, count=1
    )


def add_return_bool(node, bool_get, bp) -> None:
    return_id = bool_get.pins["ReturnValue"]
    return_line = next(
        line for line in bool_get.text.splitlines() if f"PinId={return_id}" in line
    )
    new_id = bp.new_id()
    return_line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={new_id}", return_line, count=1)
    node.text = node.text.replace("\nEnd Object", f"\n{return_line}\nEnd Object")
    node.pins["ReturnValue"] = new_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bp = load_helpers(args.project_root)
    forms_path = (
        args.project_root
        / "tools"
        / "blueprint"
        / "templates"
        / "repository-json-node-forms.eddgraph"
    )
    blocks = bp.read_blocks(forms_path)
    get_bool = bp.find_block(blocks, r'MemberName="GetBoolField"')
    get_string = bp.find_block(blocks, r'MemberName="GetStringField"')
    set_string = bp.find_block(blocks, r'MemberName="SetStringField"')

    has_field = bp.Node.clone(
        "has_field", get_bool, "K2Node_CallFunction_100", 4096, 0
    )
    retarget(has_field, "HasField")

    encode_json = bp.Node.clone(
        "encode_json", get_string, "K2Node_CallFunction_101", 4096, 256
    )
    retarget(encode_json, "EncodeJson")
    remove_pin(encode_json, "FieldName")

    decode_json = bp.Node.clone(
        "decode_json", set_string, "K2Node_CallFunction_102", 4096, 512
    )
    retarget(decode_json, "DecodeJson")
    remove_pin(decode_json, "FieldName")
    rename_pin(decode_json, "StringValue", "JsonString")
    bool_get = bp.Node.clone(
        "bool_return_source", get_bool, "K2Node_CallFunction_103", 0, 0
    )
    add_return_bool(decode_json, bool_get, bp)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(node.text for node in (has_field, encode_json, decode_json)) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
