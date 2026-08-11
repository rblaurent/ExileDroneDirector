"""Build the inactive-slot two-phase repository persistence writer graphs.

The caller owns candidate preparation and mutation.  These graphs only perform
the physical transaction: create a canonical storage object, save it once with
Committed=false, save the same object again with Committed=true, and promote
the candidate to authoritative memory only after the second save succeeds.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


FIELDS = (
    ("RepositorySchemaVersion", "int", False, None, "1"),
    ("Generation", "int", False, "CandidateGenerationV1", None),
    ("Committed", "bool", False, None, "false"),
    ("SnapshotHash", "string", False, "CandidateSnapshotHashV1", None),
    ("RecordEnvelopes", "string", True, "CandidateRecordEnvelopesV1", None),
    ("TombstoneFlypathIds", "string", True, "CandidateTombstoneFlypathIdsV1", None),
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def retarget_storage_property(enc, node, name: str, kind: str, *, array: bool) -> None:
    match = re.search(r'MemberName="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"{node.key} has no storage-property reference")
    old = match.group(1)
    node.text = re.sub(
        r'VariableReference=\(MemberParent="[^"]+",MemberName="[^"]+"(?:,MemberGuid=[0-9A-F]{32})?\)',
        f'VariableReference=(MemberParent="{enc.STORAGE_CLASS}",MemberName="{name}")',
        node.text,
        count=1,
    )
    enc.rename_pin(node, old, name)
    enc.set_pin_type(node, name, kind, array=array)
    if "Output_Get" in node.pins:
        enc.set_pin_type(node, "Output_Get", kind, array=array)


def set_failure(bp, enc, b, source, x: int, detail: str):
    code = b.setter("ResultCodeV1", "string", x, 128)
    text = b.setter("ResultDetailV1", "string", x + 256, 128)
    enc.set_default(code, "ResultCodeV1", "PersistenceUnavailable")
    enc.set_default(text, "ResultDetailV1", detail)
    bp.connect(source, "else", code, "execute")
    bp.connect(code, "then", text, "execute")
    return code, text


def build_reset(bp, enc, templates):
    b = enc.Builder(bp, templates, "ResetPersistenceWriteV1")
    reset = b.call("ResetRepositoryResultV1", 256, 0)
    created = b.setter("ScratchPersistenceStorageCreatedV1", "bool", 512, 0)
    staged = b.setter("ScratchPersistenceStageSavedV1", "bool", 768, 0)
    committed = b.setter("ScratchPersistenceCommitSavedV1", "bool", 1024, 0)
    for node, name in (
        (created, "ScratchPersistenceStorageCreatedV1"),
        (staged, "ScratchPersistenceStageSavedV1"),
        (committed, "ScratchPersistenceCommitSavedV1"),
    ):
        enc.set_default(node, name, "false")
    chain = (b.entry, reset, created, staged, committed)
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    return b.nodes


def build_storage(bp, enc, templates):
    b = enc.Builder(bp, templates, "BuildPersistenceWriteStorageV1")
    create = b.add("create", "save_create", 256, 0)
    store = b.setter("ScratchWriteStorageV1", "storage", 512, 0)
    valid = b.add("valid", "is_valid", 512, 224)
    created = b.setter("ScratchPersistenceStorageCreatedV1", "bool", 768, 0)
    branch = b.add("branch", "branch", 1024, 0)
    bp.connect(b.entry, "then", create, "execute")
    bp.connect(create, "then", store, "execute")
    bp.connect(create, "ReturnValue", store, "ScratchWriteStorageV1")
    bp.connect(create, "ReturnValue", valid, "Object")
    bp.connect(store, "then", created, "execute")
    bp.connect(valid, "ReturnValue", created, "ScratchPersistenceStorageCreatedV1")
    bp.connect(created, "then", branch, "execute")
    bp.connect(created, "Output_Get", branch, "Condition")

    previous = branch
    storage_get = b.getter("ScratchWriteStorageV1", "storage", 1024, 352)
    for index, (field, kind, array, source_name, constant) in enumerate(FIELDS):
        x = 1280 + index * 384
        setter = b.add(f"set_storage_{field}", "storage_property_set", x, -128)
        retarget_storage_property(enc, setter, field, kind, array=array)
        bp.connect(storage_get, "ScratchWriteStorageV1", setter, "self")
        if source_name is not None:
            source = b.getter(source_name, kind, x, 224, array=array)
            bp.connect(source, source_name, setter, field)
        else:
            enc.set_default(setter, field, constant or "")
        bp.connect(previous, "then", setter, "execute")
        previous = setter
    set_failure(bp, enc, b, branch, 1280, "CreateStorageFailed")
    return b.nodes


def build_stage(bp, enc, templates):
    b = enc.Builder(bp, templates, "StagePersistenceWriteV1")
    storage = b.getter("ScratchWriteStorageV1", "storage", 0, 224)
    slot = b.getter("CandidateTargetSlotV1", "string", 0, 352)
    save = b.add("save", "save_to_slot", 256, 0)
    saved = b.setter("ScratchPersistenceStageSavedV1", "bool", 512, 0)
    branch = b.add("branch", "branch", 768, 0)
    bp.connect(storage, "ScratchWriteStorageV1", save, "SaveGameObject")
    bp.connect(slot, "CandidateTargetSlotV1", save, "SlotName")
    bp.connect(b.entry, "then", save, "execute")
    bp.connect(save, "then", saved, "execute")
    bp.connect(save, "ReturnValue", saved, "ScratchPersistenceStageSavedV1")
    bp.connect(saved, "then", branch, "execute")
    bp.connect(saved, "Output_Get", branch, "Condition")
    set_failure(bp, enc, b, branch, 1024, "StageWriteFailed")
    return b.nodes


def build_commit(bp, enc, templates):
    b = enc.Builder(bp, templates, "CommitPersistenceWriteV1")
    storage = b.getter("ScratchWriteStorageV1", "storage", 0, 256)
    mark = b.add("mark_committed", "storage_property_set", 256, 0)
    retarget_storage_property(enc, mark, "Committed", "bool", array=False)
    enc.set_default(mark, "Committed", "true")
    slot = b.getter("CandidateTargetSlotV1", "string", 256, 256)
    save = b.add("save", "save_to_slot", 512, 0)
    saved = b.setter("ScratchPersistenceCommitSavedV1", "bool", 768, 0)
    branch = b.add("branch", "branch", 1024, 0)
    promote = b.call("CommitPersistenceCandidateV1", 1280, -128)
    bp.connect(storage, "ScratchWriteStorageV1", mark, "self")
    bp.connect(storage, "ScratchWriteStorageV1", save, "SaveGameObject")
    bp.connect(slot, "CandidateTargetSlotV1", save, "SlotName")
    bp.connect(b.entry, "then", mark, "execute")
    bp.connect(mark, "then", save, "execute")
    bp.connect(save, "then", saved, "execute")
    bp.connect(save, "ReturnValue", saved, "ScratchPersistenceCommitSavedV1")
    bp.connect(saved, "then", branch, "execute")
    bp.connect(saved, "Output_Get", branch, "Condition")
    bp.connect(branch, "then", promote, "execute")
    set_failure(bp, enc, b, branch, 1280, "CommitWriteFailed")
    return b.nodes


def build_coordinator(bp, enc, templates):
    b = enc.Builder(bp, templates, "PersistRepositoryV1")
    reset = b.call("ResetPersistenceWriteV1", 256, 0)
    build = b.call("BuildPersistenceWriteStorageV1", 512, 0)
    created = b.getter("ScratchPersistenceStorageCreatedV1", "bool", 512, 256)
    created_branch = b.add("created_branch", "branch", 768, 0)
    stage = b.call("StagePersistenceWriteV1", 1024, -128)
    staged = b.getter("ScratchPersistenceStageSavedV1", "bool", 1024, 256)
    staged_branch = b.add("staged_branch", "branch", 1280, -128)
    commit = b.call("CommitPersistenceWriteV1", 1536, -256)
    bp.connect(b.entry, "then", reset, "execute")
    bp.connect(reset, "then", build, "execute")
    bp.connect(build, "then", created_branch, "execute")
    bp.connect(created, "ScratchPersistenceStorageCreatedV1", created_branch, "Condition")
    bp.connect(created_branch, "then", stage, "execute")
    bp.connect(stage, "then", staged_branch, "execute")
    bp.connect(staged, "ScratchPersistenceStageSavedV1", staged_branch, "Condition")
    bp.connect(staged_branch, "then", commit, "execute")
    return b.nodes


def load_templates(project_root: Path, bp, enc, validation):
    templates = validation.load_templates(project_root, bp, enc)
    root = project_root / "tools" / "blueprint"
    forms = bp.read_blocks(root / "templates" / "repository-savegame-storage-node-forms.eddgraph")
    valid_forms = bp.read_blocks(root / "snippets" / "enter-drone-mode.eddgraph")
    templates.update({
        "save_create": bp.find_block(forms, r'MemberName="CreateSaveGameObject"'),
        "save_to_slot": bp.find_block(forms, r'MemberName="SaveGameToSlot"'),
        "storage_property_set": bp.find_block(forms, r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_VariableSet\b.*MemberName="RepositorySchemaVersion"'),
        "is_valid": bp.find_block(valid_forms, r'MemberName="IsValid"'),
    })
    return templates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py", "edd_writer_encoder")
    validation = load_module(args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py", "edd_writer_validation")
    bp = enc.load_helpers(args.project_root)
    templates = load_templates(args.project_root, bp, enc, validation)
    graphs = {
        "reset-persistence-write-v1.eddgraph": build_reset(bp, enc, templates),
        "build-persistence-write-storage-v1.eddgraph": build_storage(bp, enc, templates),
        "stage-persistence-write-v1.eddgraph": build_stage(bp, enc, templates),
        "commit-persistence-write-v1.eddgraph": build_commit(bp, enc, templates),
        "persist-repository-v1.eddgraph": build_coordinator(bp, enc, templates),
    }
    for filename, nodes in graphs.items():
        enc.write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            enc.write(validation.fold_paste_layout(nodes), args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"), paste=True)


if __name__ == "__main__":
    main()
