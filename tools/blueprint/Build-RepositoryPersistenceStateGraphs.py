"""Build pure transaction-state graphs for alternating repository persistence.

These helpers intentionally contain no GameplayStatics nodes. They isolate the
deterministic transitions around the physical adapter so candidate construction
and authoritative commit can be proven before the native SaveGame seam.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_reset(bp, enc, templates):
    b = enc.Builder(bp, templates, "ResetRepositoryStateV1")
    scalars = (
        ("RepositoryLoadedV1", "bool", "false"),
        ("ActiveGenerationV1", "int", "0"),
        ("ActiveSlotV1", "string", ""),
        ("CandidateGenerationV1", "int", "0"),
        ("CandidateTargetSlotV1", "string", ""),
        ("CandidateSnapshotHashV1", "string", ""),
        ("ScratchStorageAHeaderValidV1", "bool", "false"),
        ("ScratchStorageBHeaderValidV1", "bool", "false"),
    )
    arrays = (
        "ActiveRecordEnvelopesV1",
        "ActiveTombstoneFlypathIdsV1",
        "ActiveFlypathIdsV1",
        "ActiveOwnerAccountIdsV1",
        "ActiveVisibilitiesV1",
        "ActiveUpdatedUtcV1",
        "CandidateRecordEnvelopesV1",
        "CandidateTombstoneFlypathIdsV1",
    )
    chain = []
    for index, (name, kind, default) in enumerate(scalars):
        setter = b.setter(name, kind, 256 * (index + 1), 0)
        enc.set_default(setter, name, default)
        chain.append(setter)
    x = 256 * (len(chain) + 1)
    for index, name in enumerate(arrays):
        getter = b.getter(name, "string", x + index * 384, 256, array=True)
        clear = b.array_clear("string", x + index * 384, 0)
        bp.connect(getter, name, clear, "TargetArray")
        chain.append(clear)
    bp.connect(b.entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    return b.nodes


def header_conditions(v, prefix: str, x: int, y: int):
    b = v.b
    exists = b.getter(f"ScratchStorage{prefix}ExistsV1", "bool", x, y)
    exists_ok = v.bool_math("EqualEqual_BoolBool", x + 224, y)
    v.enc.set_default(exists_ok, "B", "true")
    schema = b.getter(f"ScratchStorage{prefix}SchemaVersionV1", "int", x, y + 144)
    schema_ok = v.int_math("EqualEqual_IntInt", x + 224, y + 144, b_default="1")
    generation = b.getter(f"ScratchStorage{prefix}GenerationV1", "int", x, y + 288)
    generation_ok = v.int_math("Greater_IntInt", x + 224, y + 288, b_default="0")
    committed = b.getter(f"ScratchStorage{prefix}CommittedV1", "bool", x, y + 432)
    committed_ok = v.bool_math("EqualEqual_BoolBool", x + 224, y + 432)
    v.enc.set_default(committed_ok, "B", "true")
    digest = b.getter(f"ScratchStorage{prefix}SnapshotHashV1", "string", x, y + 576)
    digest_ok = v.string_math("EqualEqual_StrStr", x + 224, y + 576, b_default="")
    v.bp.connect(exists, f"ScratchStorage{prefix}ExistsV1", exists_ok, "A")
    v.bp.connect(schema, f"ScratchStorage{prefix}SchemaVersionV1", schema_ok, "A")
    v.bp.connect(generation, f"ScratchStorage{prefix}GenerationV1", generation_ok, "A")
    v.bp.connect(committed, f"ScratchStorage{prefix}CommittedV1", committed_ok, "A")
    v.bp.connect(digest, f"ScratchStorage{prefix}SnapshotHashV1", digest_ok, "A")
    return (exists_ok, schema_ok, generation_ok, committed_ok, digest_ok)


def build_validate_headers(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "ValidateStorageHeadersV1")
    a_combined = v.and_all(header_conditions(v, "A", 0, 256), 512, 256)
    a_set = v.b.setter("ScratchStorageAHeaderValidV1", "bool", 1536, 0)
    bp.connect(a_combined, "ReturnValue", a_set, "ScratchStorageAHeaderValidV1")

    b_combined = v.and_all(header_conditions(v, "B", 1792, 256), 2304, 256)
    b_set = v.b.setter("ScratchStorageBHeaderValidV1", "bool", 3328, 0)
    bp.connect(b_combined, "ReturnValue", b_set, "ScratchStorageBHeaderValidV1")

    bp.connect(v.entry, "then", a_set, "execute")
    bp.connect(a_set, "then", b_set, "execute")
    return v.nodes


def build_prepare(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "PreparePersistenceCandidateV1")
    b = v.b
    active_records = b.getter("ActiveRecordEnvelopesV1", "string", 0, 256, array=True)
    candidate_records = b.setter("CandidateRecordEnvelopesV1", "string", 256, 0, array=True)
    active_tombstones = b.getter("ActiveTombstoneFlypathIdsV1", "string", 256, 256, array=True)
    candidate_tombstones = b.setter("CandidateTombstoneFlypathIdsV1", "string", 512, 0, array=True)
    active_generation = b.getter("ActiveGenerationV1", "int", 512, 256)
    increment = v.int_math("Add_IntInt", 768, 256, b_default="1")
    candidate_generation = b.setter("CandidateGenerationV1", "int", 768, 0)
    candidate_hash = b.setter("CandidateSnapshotHashV1", "string", 1024, 0)
    enc.set_default(candidate_hash, "CandidateSnapshotHashV1", "")
    active_slot = b.getter("ActiveSlotV1", "string", 1024, 256)
    is_a = v.string_math("EqualEqual_StrStr", 1280, 256, b_default="EDD_Repository_A")
    branch = v.branch(1536, 0)
    target_b = b.setter("CandidateTargetSlotV1", "string", 1792, -128)
    target_a = b.setter("CandidateTargetSlotV1", "string", 1792, 128)
    enc.set_default(target_b, "CandidateTargetSlotV1", "EDD_Repository_B")
    enc.set_default(target_a, "CandidateTargetSlotV1", "EDD_Repository_A")

    bp.connect(active_records, "ActiveRecordEnvelopesV1", candidate_records, "CandidateRecordEnvelopesV1")
    bp.connect(active_tombstones, "ActiveTombstoneFlypathIdsV1", candidate_tombstones, "CandidateTombstoneFlypathIdsV1")
    bp.connect(active_generation, "ActiveGenerationV1", increment, "A")
    bp.connect(increment, "ReturnValue", candidate_generation, "CandidateGenerationV1")
    bp.connect(active_slot, "ActiveSlotV1", is_a, "A")
    bp.connect(is_a, "ReturnValue", branch, "Condition")
    bp.connect(v.entry, "then", candidate_records, "execute")
    bp.connect(candidate_records, "then", candidate_tombstones, "execute")
    bp.connect(candidate_tombstones, "then", candidate_generation, "execute")
    bp.connect(candidate_generation, "then", candidate_hash, "execute")
    bp.connect(candidate_hash, "then", branch, "execute")
    bp.connect(branch, "then", target_b, "execute")
    bp.connect(branch, "else", target_a, "execute")
    return v.nodes


def build_commit(bp, enc, templates):
    b = enc.Builder(bp, templates, "CommitPersistenceCandidateV1")
    candidate_records = b.getter("CandidateRecordEnvelopesV1", "string", 0, 256, array=True)
    active_records = b.setter("ActiveRecordEnvelopesV1", "string", 256, 0, array=True)
    candidate_tombstones = b.getter("CandidateTombstoneFlypathIdsV1", "string", 256, 256, array=True)
    active_tombstones = b.setter("ActiveTombstoneFlypathIdsV1", "string", 512, 0, array=True)
    candidate_generation = b.getter("CandidateGenerationV1", "int", 512, 256)
    active_generation = b.setter("ActiveGenerationV1", "int", 768, 0)
    candidate_slot = b.getter("CandidateTargetSlotV1", "string", 768, 256)
    active_slot = b.setter("ActiveSlotV1", "string", 1024, 0)
    loaded = b.setter("RepositoryLoadedV1", "bool", 1280, 0)
    enc.set_default(loaded, "RepositoryLoadedV1", "true")

    bp.connect(candidate_records, "CandidateRecordEnvelopesV1", active_records, "ActiveRecordEnvelopesV1")
    bp.connect(candidate_tombstones, "CandidateTombstoneFlypathIdsV1", active_tombstones, "ActiveTombstoneFlypathIdsV1")
    bp.connect(candidate_generation, "CandidateGenerationV1", active_generation, "ActiveGenerationV1")
    bp.connect(candidate_slot, "CandidateTargetSlotV1", active_slot, "ActiveSlotV1")
    bp.connect(b.entry, "then", active_records, "execute")
    bp.connect(active_records, "then", active_tombstones, "execute")
    bp.connect(active_tombstones, "then", active_generation, "execute")
    bp.connect(active_generation, "then", active_slot, "execute")
    bp.connect(active_slot, "then", loaded, "execute")
    return b.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_persistence_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_persistence_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    graphs = {
        "reset-repository-state-v1.eddgraph": build_reset(bp, enc, templates),
        "validate-storage-headers-v1.eddgraph": build_validate_headers(bp, enc, validation, templates),
        "prepare-persistence-candidate-v1.eddgraph": build_prepare(bp, enc, validation, templates),
        "commit-persistence-candidate-v1.eddgraph": build_commit(bp, enc, templates),
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
