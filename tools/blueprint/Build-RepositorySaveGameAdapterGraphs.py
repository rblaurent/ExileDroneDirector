"""Build native SaveGame read/staging graphs for repository slots A and B.

These helpers stop at raw typed storage staging and header validation. They do
not select authoritative records or mark the repository loaded; recovery owns
that later transaction boundary.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


SLOT_FIELDS = (
    ("RepositorySchemaVersion", "SchemaVersion", "int", False),
    ("Generation", "Generation", "int", False),
    ("Committed", "Committed", "bool", False),
    ("SnapshotHash", "SnapshotHash", "string", False),
    ("RecordEnvelopes", "RecordEnvelopes", "string", True),
    ("TombstoneFlypathIds", "TombstoneFlypathIds", "string", True),
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def retarget_storage_property(enc, node, new_name: str, kind: str, *, array: bool) -> None:
    match = re.search(r'MemberName="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"{node.key} has no storage-property reference")
    old_name = match.group(1)
    node.text = re.sub(
        r'VariableReference=\(MemberParent="[^"]+",MemberName="[^"]+"(?:,MemberGuid=[0-9A-F]{32})?\)',
        f'VariableReference=(MemberParent="{enc.STORAGE_CLASS}",MemberName="{new_name}")',
        node.text,
        count=1,
    )
    enc.rename_pin(node, old_name, new_name)
    enc.set_pin_type(node, new_name, kind, array=array)
    if "Output_Get" in node.pins:
        enc.set_pin_type(node, "Output_Get", kind, array=array)


def cast_output(node) -> str:
    matches = [name for name in node.pins if name.startswith("AsSG")]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one typed storage cast output; found {matches}")
    return matches[0]


def build_slot_reader(bp, enc, validation, templates, prefix: str):
    function = f"ReadRepositoryStorageSlot{prefix}V1"
    slot = f"EDD_Repository_{prefix}"
    b = enc.Builder(bp, templates, function)
    exists = b.add("save_exists", "save_exists", 256, 0)
    enc.set_default(exists, "SlotName", slot)
    exists_set = b.setter(f"ScratchStorage{prefix}ExistsV1", "bool", 512, 0)
    branch = b.add("exists_branch", "branch", 768, 0)
    load = b.add("save_load", "save_load", 1024, -128)
    enc.set_default(load, "SlotName", slot)
    cast = b.add("storage_cast", "storage_cast", 1280, -128)
    storage_set = b.setter(f"ScratchStorage{prefix}V1", "storage", 1536, -128)

    bp.connect(b.entry, "then", exists, "execute")
    bp.connect(exists, "then", exists_set, "execute")
    bp.connect(exists, "ReturnValue", exists_set, f"ScratchStorage{prefix}ExistsV1")
    bp.connect(exists_set, "then", branch, "execute")
    bp.connect(exists, "ReturnValue", branch, "Condition")
    bp.connect(branch, "then", load, "execute")
    bp.connect(load, "then", cast, "execute")
    bp.connect(load, "ReturnValue", cast, "Object")
    bp.connect(cast, "then", storage_set, "execute")
    bp.connect(cast, cast_output(cast), storage_set, f"ScratchStorage{prefix}V1")

    previous = storage_set
    for index, (storage_name, scratch_suffix, kind, array) in enumerate(SLOT_FIELDS):
        x = 1792 + index * 384
        prop = b.add(f"get_{storage_name}", "storage_property_get", x, 192)
        retarget_storage_property(enc, prop, storage_name, kind, array=array)
        scratch_name = f"ScratchStorage{prefix}{scratch_suffix}V1"
        setter = b.setter(scratch_name, kind, x, -128, array=array)
        bp.connect(storage_set, "Output_Get", prop, "self")
        bp.connect(prop, storage_name, setter, scratch_name)
        bp.connect(previous, "then", setter, "execute")
        previous = setter
    return b.nodes


def build_coordinator(bp, enc, templates):
    b = enc.Builder(bp, templates, "ReadRepositoryStorageSlotsV1")
    reset = b.call("ResetRepositoryStateV1", 256, 0)
    read_a = b.call("ReadRepositoryStorageSlotAV1", 512, 0)
    read_b = b.call("ReadRepositoryStorageSlotBV1", 768, 0)
    validate = b.call("ValidateStorageHeadersV1", 1024, 0)
    chain = (b.entry, reset, read_a, read_b, validate)
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    return b.nodes


def load_templates(project_root: Path, bp, enc, validation):
    templates = validation.load_templates(project_root, bp, enc)
    forms = bp.read_blocks(
        project_root / "tools" / "blueprint" / "templates" /
        "repository-savegame-storage-node-forms.eddgraph"
    )
    templates.update(
        {
            "save_exists": bp.find_block(forms, r'MemberName="DoesSaveGameExist"'),
            "save_load": bp.find_block(forms, r'MemberName="LoadGameFromSlot"'),
            "storage_cast": bp.find_block(
                forms,
                r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_DynamicCast\b",
            ),
            "storage_property_get": bp.find_block(
                forms,
                r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_VariableGet\b'
                r'.*MemberName="RepositorySchemaVersion"',
            ),
            "branch": bp.find_block(
                bp.read_blocks(
                    project_root / "tools" / "blueprint" / "snippets" /
                    "enter-drone-mode.eddgraph"
                ),
                r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse\b",
            ),
        }
    )
    return templates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" /
        "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_savegame_adapter_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" /
        "Build-RepositoryValidationGraphs.py",
        "edd_savegame_adapter_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = load_templates(args.project_root, bp, enc, validation)
    graphs = {
        "read-repository-storage-slot-a-v1.eddgraph": build_slot_reader(
            bp, enc, validation, templates, "A"
        ),
        "read-repository-storage-slot-b-v1.eddgraph": build_slot_reader(
            bp, enc, validation, templates, "B"
        ),
        "read-repository-storage-slots-v1.eddgraph": build_coordinator(
            bp, enc, templates
        ),
    }
    for filename, nodes in graphs.items():
        enc.write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            enc.write(
                validation.fold_paste_layout(nodes),
                args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"),
                paste=True,
            )


if __name__ == "__main__":
    main()
