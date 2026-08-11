"""Build record-granular repository recovery and authoritative commit graphs."""

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


def chain(bp, entry, nodes) -> None:
    if not nodes:
        return
    bp.connect(entry, "then", nodes[0], "execute")
    for left, right in zip(nodes, nodes[1:]):
        bp.connect(left, "then", right, "execute")


def assign_array(bp, b, source_name: str, target_name: str, x: int, y: int):
    source = b.getter(source_name, "string", x, y + 224, array=True)
    target = b.setter(target_name, "string", x + 224, y, array=True)
    bp.connect(source, source_name, target, target_name)
    return source, target


def add_string(bp, b, array_name: str, value, value_pin: str, x: int, y: int):
    target = b.getter(array_name, "string", x, y + 224, array=True)
    add = b.array_add("string", x + 224, y)
    bp.connect(target, array_name, add, "TargetArray")
    bp.connect(value, value_pin, add, "NewItem")
    return add


def build_reset(bp, enc, templates):
    b = enc.Builder(bp, templates, "ResetRecoveryRecordsV1")
    generation = b.setter("ScratchRecoveryChannelRecordGenerationV1", "int", 256, 0)
    current = b.setter("ScratchRecoveryCurrentRecordEnvelopeV1", "string", 512, 0)
    enc.set_default(generation, "ScratchRecoveryChannelRecordGenerationV1", "0")
    enc.set_default(current, "ScratchRecoveryCurrentRecordEnvelopeV1", "")
    arrays = (
        "ScratchRecoveryRecordEnvelopesV1",
        "ScratchRecoveryRecordFlypathIdsV1",
        "ScratchRecoveryRecordOwnerAccountIdsV1",
        "ScratchRecoveryRecordVisibilitiesV1",
        "ScratchRecoveryRecordUpdatedUtcV1",
        "ScratchRecoveryChannelRecordEnvelopesV1",
        "ScratchRecoveryChannelSeenRecordIdsV1",
        "ScratchRecoveryChannelAmbiguousRecordIdsV1",
    )
    execution = [generation, current]
    for index, name in enumerate(arrays):
        getter = b.getter(name, "string", 768 + index * 384, 256, array=True)
        clear = b.array_clear("string", 768 + index * 384, 0)
        bp.connect(getter, name, clear, "TargetArray")
        execution.append(clear)
    chain(bp, b.entry, execution)
    return b.nodes


def build_decode_validate(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "DecodeValidateRecoveryEnvelopeV1")
    b = v.b
    current = b.getter("ScratchRecoveryCurrentRecordEnvelopeV1", "string", 0, 256)
    stage = b.setter("ScratchEncodedRecordV1", "string", 256, 0)
    decode = b.call("DecodeRecordV1", 512, 0)
    decoded_valid = b.getter("ScratchValidV1", "bool", 512, 256)
    branch = v.branch(768, 0)
    validate = b.call("ValidateRecordV1", 1024, 0)
    bp.connect(current, "ScratchRecoveryCurrentRecordEnvelopeV1", stage, "ScratchEncodedRecordV1")
    bp.connect(decoded_valid, "ScratchValidV1", branch, "Condition")
    bp.connect(v.entry, "then", stage, "execute")
    bp.connect(stage, "then", decode, "execute")
    bp.connect(decode, "then", branch, "execute")
    bp.connect(branch, "then", validate, "execute")
    return v.nodes


def build_scan_identity(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "ScanRecoveryRecordIdentityV1")
    b = v.b
    record_id = b.getter("ScratchRecordFlypathIdV1", "string", 0, 256)
    _, stage_seen = assign_array(
        bp, b, "ScratchRecoveryChannelSeenRecordIdsV1", "ScratchRecoverySearchStringsV1", 0, 0
    )
    stage_value = b.setter("ScratchRecoverySearchValueV1", "string", 448, 0)
    find_seen = b.call("FindRecoveryStringIndexV1", 704, 0)
    seen_index = b.getter("ScratchRecoverySearchIndexV1", "int", 704, 256)
    unseen = v.int_math("EqualEqual_IntInt", 960, 256, b_default="-1")
    unseen_branch = v.branch(1216, 0)
    add_seen = add_string(
        bp, b, "ScratchRecoveryChannelSeenRecordIdsV1", record_id, "ScratchRecordFlypathIdV1", 1472, -96
    )
    _, stage_ambiguous = assign_array(
        bp,
        b,
        "ScratchRecoveryChannelAmbiguousRecordIdsV1",
        "ScratchRecoverySearchStringsV1",
        1472,
        160,
    )
    stage_ambiguous_value = b.setter("ScratchRecoverySearchValueV1", "string", 1920, 160)
    find_ambiguous = b.call("FindRecoveryStringIndexV1", 2176, 160)
    ambiguous_index = b.getter("ScratchRecoverySearchIndexV1", "int", 2176, 416)
    not_ambiguous = v.int_math("EqualEqual_IntInt", 2432, 416, b_default="-1")
    ambiguous_branch = v.branch(2688, 160)
    add_ambiguous = add_string(
        bp,
        b,
        "ScratchRecoveryChannelAmbiguousRecordIdsV1",
        record_id,
        "ScratchRecordFlypathIdV1",
        2944,
        160,
    )

    bp.connect(record_id, "ScratchRecordFlypathIdV1", stage_value, "ScratchRecoverySearchValueV1")
    bp.connect(seen_index, "ScratchRecoverySearchIndexV1", unseen, "A")
    bp.connect(unseen, "ReturnValue", unseen_branch, "Condition")
    bp.connect(record_id, "ScratchRecordFlypathIdV1", stage_ambiguous_value, "ScratchRecoverySearchValueV1")
    bp.connect(ambiguous_index, "ScratchRecoverySearchIndexV1", not_ambiguous, "A")
    bp.connect(not_ambiguous, "ReturnValue", ambiguous_branch, "Condition")
    bp.connect(v.entry, "then", stage_seen, "execute")
    bp.connect(stage_seen, "then", stage_value, "execute")
    bp.connect(stage_value, "then", find_seen, "execute")
    bp.connect(find_seen, "then", unseen_branch, "execute")
    bp.connect(unseen_branch, "then", add_seen, "execute")
    bp.connect(unseen_branch, "else", stage_ambiguous, "execute")
    bp.connect(stage_ambiguous, "then", stage_ambiguous_value, "execute")
    bp.connect(stage_ambiguous_value, "then", find_ambiguous, "execute")
    bp.connect(find_ambiguous, "then", ambiguous_branch, "execute")
    bp.connect(ambiguous_branch, "then", add_ambiguous, "execute")
    return v.nodes


def build_append_if_new(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "AppendRecoveryRecordIfNewV1")
    b = v.b
    record_id = b.getter("ScratchRecordFlypathIdV1", "string", 0, 256)
    _, stage_ids = assign_array(
        bp, b, "ScratchRecoveryRecordFlypathIdsV1", "ScratchRecoverySearchStringsV1", 0, 0
    )
    stage_value = b.setter("ScratchRecoverySearchValueV1", "string", 448, 0)
    find = b.call("FindRecoveryStringIndexV1", 704, 0)
    index = b.getter("ScratchRecoverySearchIndexV1", "int", 704, 256)
    missing = v.int_math("EqualEqual_IntInt", 960, 256, b_default="-1")
    branch = v.branch(1216, 0)
    current_envelope = b.getter("ScratchRecoveryCurrentRecordEnvelopeV1", "string", 1216, 384)
    owner = b.getter("ScratchRecordOwnerAccountIdV1", "string", 1216, 512)
    visibility = b.getter("ScratchRecordVisibilityV1", "string", 1216, 640)
    updated = b.getter("ScratchRecordUpdatedUtcV1", "string", 1216, 768)
    add_id = add_string(
        bp, b, "ScratchRecoveryRecordFlypathIdsV1", record_id, "ScratchRecordFlypathIdV1", 1472, 0
    )
    add_envelope = add_string(
        bp,
        b,
        "ScratchRecoveryRecordEnvelopesV1",
        current_envelope,
        "ScratchRecoveryCurrentRecordEnvelopeV1",
        1856,
        0,
    )
    add_owner = add_string(
        bp,
        b,
        "ScratchRecoveryRecordOwnerAccountIdsV1",
        owner,
        "ScratchRecordOwnerAccountIdV1",
        2240,
        0,
    )
    add_visibility = add_string(
        bp,
        b,
        "ScratchRecoveryRecordVisibilitiesV1",
        visibility,
        "ScratchRecordVisibilityV1",
        2624,
        0,
    )
    add_updated = add_string(
        bp,
        b,
        "ScratchRecoveryRecordUpdatedUtcV1",
        updated,
        "ScratchRecordUpdatedUtcV1",
        3008,
        0,
    )
    bp.connect(record_id, "ScratchRecordFlypathIdV1", stage_value, "ScratchRecoverySearchValueV1")
    bp.connect(index, "ScratchRecoverySearchIndexV1", missing, "A")
    bp.connect(missing, "ReturnValue", branch, "Condition")
    bp.connect(v.entry, "then", stage_ids, "execute")
    bp.connect(stage_ids, "then", stage_value, "execute")
    bp.connect(stage_value, "then", find, "execute")
    bp.connect(find, "then", branch, "execute")
    bp.connect(branch, "then", add_id, "execute")
    for left, right in zip(
        (add_id, add_envelope, add_owner, add_visibility),
        (add_envelope, add_owner, add_visibility, add_updated),
    ):
        bp.connect(left, "then", right, "execute")
    return v.nodes


def build_try_merge(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "TryMergeRecoveryRecordV1")
    b = v.b
    record_id = b.getter("ScratchRecordFlypathIdV1", "string", 0, 256)
    _, stage_ambiguous = assign_array(
        bp,
        b,
        "ScratchRecoveryChannelAmbiguousRecordIdsV1",
        "ScratchRecoverySearchStringsV1",
        0,
        0,
    )
    stage_ambiguous_value = b.setter("ScratchRecoverySearchValueV1", "string", 448, 0)
    find_ambiguous = b.call("FindRecoveryStringIndexV1", 704, 0)
    ambiguous_index = b.getter("ScratchRecoverySearchIndexV1", "int", 704, 256)
    unambiguous = v.int_math("EqualEqual_IntInt", 960, 256, b_default="-1")
    ambiguous_branch = v.branch(1216, 0)

    _, stage_tombstones = assign_array(
        bp, b, "ScratchRecoveryTombstoneIdsV1", "ScratchRecoverySearchStringsV1", 1472, 0
    )
    stage_tombstone_value = b.setter("ScratchRecoverySearchValueV1", "string", 1920, 0)
    find_tombstone = b.call("FindRecoveryStringIndexV1", 2176, 0)
    tombstone_index = b.getter("ScratchRecoverySearchIndexV1", "int", 2176, 256)
    no_tombstone = v.int_math("EqualEqual_IntInt", 2432, 256, b_default="-1")
    tombstone_branch = v.branch(2688, 0)
    append_no_tombstone = b.call("AppendRecoveryRecordIfNewV1", 2944, -128)

    tombstone_generations = b.getter(
        "ScratchRecoveryTombstoneGenerationsV1", "int", 2944, 256, array=True
    )
    generation_item = v.array_item(
        tombstone_generations,
        "ScratchRecoveryTombstoneGenerationsV1",
        tombstone_index,
        "ScratchRecoverySearchIndexV1",
        "int",
        3200,
        256,
    )
    record_generation = b.getter("ScratchRecoveryChannelRecordGenerationV1", "int", 3200, 448)
    masked = v.int_math("GreaterEqual_IntInt", 3456, 320)
    mask_branch = v.branch(3712, 0)
    append_unmasked = b.call("AppendRecoveryRecordIfNewV1", 3968, 128)

    bp.connect(record_id, "ScratchRecordFlypathIdV1", stage_ambiguous_value, "ScratchRecoverySearchValueV1")
    bp.connect(ambiguous_index, "ScratchRecoverySearchIndexV1", unambiguous, "A")
    bp.connect(unambiguous, "ReturnValue", ambiguous_branch, "Condition")
    bp.connect(record_id, "ScratchRecordFlypathIdV1", stage_tombstone_value, "ScratchRecoverySearchValueV1")
    bp.connect(tombstone_index, "ScratchRecoverySearchIndexV1", no_tombstone, "A")
    bp.connect(no_tombstone, "ReturnValue", tombstone_branch, "Condition")
    bp.connect(generation_item, "Output", masked, "A")
    bp.connect(record_generation, "ScratchRecoveryChannelRecordGenerationV1", masked, "B")
    bp.connect(masked, "ReturnValue", mask_branch, "Condition")

    bp.connect(v.entry, "then", stage_ambiguous, "execute")
    bp.connect(stage_ambiguous, "then", stage_ambiguous_value, "execute")
    bp.connect(stage_ambiguous_value, "then", find_ambiguous, "execute")
    bp.connect(find_ambiguous, "then", ambiguous_branch, "execute")
    bp.connect(ambiguous_branch, "then", stage_tombstones, "execute")
    bp.connect(stage_tombstones, "then", stage_tombstone_value, "execute")
    bp.connect(stage_tombstone_value, "then", find_tombstone, "execute")
    bp.connect(find_tombstone, "then", tombstone_branch, "execute")
    bp.connect(tombstone_branch, "then", append_no_tombstone, "execute")
    bp.connect(tombstone_branch, "else", mask_branch, "execute")
    bp.connect(mask_branch, "else", append_unmasked, "execute")
    return v.nodes


def build_recover_channel(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "RecoverRecordChannelV1")
    b = v.b
    seen = b.getter("ScratchRecoveryChannelSeenRecordIdsV1", "string", 0, 256, array=True)
    clear_seen = b.array_clear("string", 256, 0)
    ambiguous = b.getter(
        "ScratchRecoveryChannelAmbiguousRecordIdsV1", "string", 256, 256, array=True
    )
    clear_ambiguous = b.array_clear("string", 512, 0)
    scan_source = b.getter(
        "ScratchRecoveryChannelRecordEnvelopesV1", "string", 512, 256, array=True
    )
    scan = b.foreach("string", 768, 0)
    scan_current = b.setter("ScratchRecoveryCurrentRecordEnvelopeV1", "string", 1024, 0)
    scan_decode = b.call("DecodeValidateRecoveryEnvelopeV1", 1280, 0)
    scan_valid = b.getter("ScratchValidV1", "bool", 1280, 256)
    scan_branch = v.branch(1536, 0)
    scan_identity = b.call("ScanRecoveryRecordIdentityV1", 1792, 0)

    merge_source = b.getter(
        "ScratchRecoveryChannelRecordEnvelopesV1", "string", 1792, 384, array=True
    )
    merge = b.foreach("string", 2048, 128)
    merge_current = b.setter("ScratchRecoveryCurrentRecordEnvelopeV1", "string", 2304, 128)
    merge_decode = b.call("DecodeValidateRecoveryEnvelopeV1", 2560, 128)
    merge_valid = b.getter("ScratchValidV1", "bool", 2560, 384)
    merge_branch = v.branch(2816, 128)
    try_merge = b.call("TryMergeRecoveryRecordV1", 3072, 128)

    bp.connect(seen, "ScratchRecoveryChannelSeenRecordIdsV1", clear_seen, "TargetArray")
    bp.connect(ambiguous, "ScratchRecoveryChannelAmbiguousRecordIdsV1", clear_ambiguous, "TargetArray")
    bp.connect(scan_source, "ScratchRecoveryChannelRecordEnvelopesV1", scan, "Array")
    bp.connect(scan, "Array Element", scan_current, "ScratchRecoveryCurrentRecordEnvelopeV1")
    bp.connect(scan_valid, "ScratchValidV1", scan_branch, "Condition")
    bp.connect(merge_source, "ScratchRecoveryChannelRecordEnvelopesV1", merge, "Array")
    bp.connect(merge, "Array Element", merge_current, "ScratchRecoveryCurrentRecordEnvelopeV1")
    bp.connect(merge_valid, "ScratchValidV1", merge_branch, "Condition")
    bp.connect(v.entry, "then", clear_seen, "execute")
    bp.connect(clear_seen, "then", clear_ambiguous, "execute")
    bp.connect(clear_ambiguous, "then", scan, "Exec")
    bp.connect(scan, "LoopBody", scan_current, "execute")
    bp.connect(scan_current, "then", scan_decode, "execute")
    bp.connect(scan_decode, "then", scan_branch, "execute")
    bp.connect(scan_branch, "then", scan_identity, "execute")
    bp.connect(scan, "Completed", merge, "Exec")
    bp.connect(merge, "LoopBody", merge_current, "execute")
    bp.connect(merge_current, "then", merge_decode, "execute")
    bp.connect(merge_decode, "then", merge_branch, "execute")
    bp.connect(merge_branch, "then", try_merge, "execute")
    return v.nodes


def build_recover_repository(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "RecoverRepositoryRecordsV1")
    b = v.b
    reset = b.call("ResetRecoveryRecordsV1", 256, 0)
    failed = b.getter("ScratchRecoveryFailedV1", "bool", 256, 256)
    failed_branch = v.branch(512, 0)
    newest_slot = b.getter("ScratchRecoveryNewestSlotV1", "string", 512, 256)
    newest_present = v.string_math("NotEqual_StrStr", 768, 256, b_default="")
    newest_branch = v.branch(1024, 0)
    _, newest_records = assign_array(
        bp,
        b,
        "ScratchRecoveryNewestRecordEnvelopesV1",
        "ScratchRecoveryChannelRecordEnvelopesV1",
        1280,
        0,
    )
    newest_generation_source = b.getter("ScratchRecoveryNewestGenerationV1", "int", 1728, 256)
    newest_generation = b.setter("ScratchRecoveryChannelRecordGenerationV1", "int", 1984, 0)
    recover_newest = b.call("RecoverRecordChannelV1", 2240, 0)
    older_slot = b.getter("ScratchRecoveryOlderSlotV1", "string", 2240, 256)
    older_present = v.string_math("NotEqual_StrStr", 2496, 256, b_default="")
    older_branch = v.branch(2752, 0)
    _, older_records = assign_array(
        bp,
        b,
        "ScratchRecoveryOlderRecordEnvelopesV1",
        "ScratchRecoveryChannelRecordEnvelopesV1",
        3008,
        0,
    )
    older_generation_source = b.getter("ScratchRecoveryOlderGenerationV1", "int", 3456, 256)
    older_generation = b.setter("ScratchRecoveryChannelRecordGenerationV1", "int", 3712, 0)
    recover_older = b.call("RecoverRecordChannelV1", 3968, 0)
    bp.connect(failed, "ScratchRecoveryFailedV1", failed_branch, "Condition")
    bp.connect(newest_slot, "ScratchRecoveryNewestSlotV1", newest_present, "A")
    bp.connect(newest_present, "ReturnValue", newest_branch, "Condition")
    bp.connect(
        newest_generation_source,
        "ScratchRecoveryNewestGenerationV1",
        newest_generation,
        "ScratchRecoveryChannelRecordGenerationV1",
    )
    bp.connect(older_slot, "ScratchRecoveryOlderSlotV1", older_present, "A")
    bp.connect(older_present, "ReturnValue", older_branch, "Condition")
    bp.connect(
        older_generation_source,
        "ScratchRecoveryOlderGenerationV1",
        older_generation,
        "ScratchRecoveryChannelRecordGenerationV1",
    )
    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", failed_branch, "execute")
    bp.connect(failed_branch, "else", newest_branch, "execute")
    bp.connect(newest_branch, "then", newest_records, "execute")
    bp.connect(newest_records, "then", newest_generation, "execute")
    bp.connect(newest_generation, "then", recover_newest, "execute")
    bp.connect(recover_newest, "then", older_branch, "execute")
    bp.connect(older_branch, "then", older_records, "execute")
    bp.connect(older_records, "then", older_generation, "execute")
    bp.connect(older_generation, "then", recover_older, "execute")
    return v.nodes


def build_commit_recovered(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "CommitRecoveredRepositoryV1")
    b = v.b
    failed = b.getter("ScratchRecoveryFailedV1", "bool", 0, 256)
    branch = v.branch(256, 0)
    mappings = (
        ("ScratchRecoveryRecordEnvelopesV1", "ActiveRecordEnvelopesV1"),
        ("ScratchRecoveryTombstoneIdsV1", "ActiveTombstoneFlypathIdsV1"),
        ("ScratchRecoveryRecordFlypathIdsV1", "ActiveFlypathIdsV1"),
        ("ScratchRecoveryRecordOwnerAccountIdsV1", "ActiveOwnerAccountIdsV1"),
        ("ScratchRecoveryRecordVisibilitiesV1", "ActiveVisibilitiesV1"),
        ("ScratchRecoveryRecordUpdatedUtcV1", "ActiveUpdatedUtcV1"),
    )
    execution = []
    x = 512
    for source_name, target_name in mappings:
        _, setter = assign_array(bp, b, source_name, target_name, x, 0)
        execution.append(setter)
        x += 448
    newest_generation = b.getter("ScratchRecoveryNewestGenerationV1", "int", x, 256)
    active_generation = b.setter("ActiveGenerationV1", "int", x + 256, 0)
    newest_slot = b.getter("ScratchRecoveryNewestSlotV1", "string", x + 256, 256)
    active_slot = b.setter("ActiveSlotV1", "string", x + 512, 0)
    loaded = b.setter("RepositoryLoadedV1", "bool", x + 768, 0)
    enc.set_default(loaded, "RepositoryLoadedV1", "true")
    bp.connect(newest_generation, "ScratchRecoveryNewestGenerationV1", active_generation, "ActiveGenerationV1")
    bp.connect(newest_slot, "ScratchRecoveryNewestSlotV1", active_slot, "ActiveSlotV1")
    bp.connect(failed, "ScratchRecoveryFailedV1", branch, "Condition")
    bp.connect(v.entry, "then", branch, "execute")
    bp.connect(branch, "else", execution[0], "execute")
    for left, right in zip(execution, execution[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(execution[-1], "then", active_generation, "execute")
    bp.connect(active_generation, "then", active_slot, "execute")
    bp.connect(active_slot, "then", loaded, "execute")
    return v.nodes


def build_load_repository(bp, enc, templates):
    b = enc.Builder(bp, templates, "LoadRepositoryV1")
    calls = [
        b.call("ReadRepositoryStorageSlotsV1", 256, 0),
        b.call("SelectRepositoryRecoveryOrderV1", 512, 0),
        b.call("MergeRecoveryTombstonesV1", 768, 0),
        b.call("RecoverRepositoryRecordsV1", 1024, 0),
        b.call("CommitRecoveredRepositoryV1", 1280, 0),
    ]
    chain(bp, b.entry, calls)
    return b.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_record_recovery_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_record_recovery_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    graphs = {
        "reset-recovery-records-v1.eddgraph": build_reset(bp, enc, templates),
        "decode-validate-recovery-envelope-v1.eddgraph": build_decode_validate(
            bp, enc, validation, templates
        ),
        "scan-recovery-record-identity-v1.eddgraph": build_scan_identity(
            bp, enc, validation, templates
        ),
        "append-recovery-record-if-new-v1.eddgraph": build_append_if_new(
            bp, enc, validation, templates
        ),
        "try-merge-recovery-record-v1.eddgraph": build_try_merge(
            bp, enc, validation, templates
        ),
        "recover-record-channel-v1.eddgraph": build_recover_channel(
            bp, enc, validation, templates
        ),
        "recover-repository-records-v1.eddgraph": build_recover_repository(
            bp, enc, validation, templates
        ),
        "commit-recovered-repository-v1.eddgraph": build_commit_recovered(
            bp, enc, validation, templates
        ),
        "load-repository-v1.eddgraph": build_load_repository(bp, enc, templates),
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
