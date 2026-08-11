"""Build deterministic tombstone-validation and recovery-merge graphs.

Recovery selection stages a newest and optional older A/B snapshot.  These
helpers validate every selected tombstone channel before merging it, reject
malformed or duplicate identifiers fail-closed, and retain the generation of
the newest snapshot that deleted each flypath.
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


def build_reset(bp, enc, templates):
    b = enc.Builder(bp, templates, "ResetRecoveryTombstonesV1")
    scalars = (
        ("ScratchRecoveryChannelGenerationV1", "int", "0"),
        ("ScratchRecoverySearchValueV1", "string", ""),
        ("ScratchRecoverySearchIndexV1", "int", "-1"),
        ("ScratchRecoveryCurrentTombstoneV1", "string", ""),
        ("ScratchRecoveryTrimmedTombstoneV1", "string", ""),
    )
    arrays = (
        "ScratchRecoveryTombstoneIdsV1",
        "ScratchRecoveryTombstoneGenerationsV1",
        "ScratchRecoveryChannelTombstonesV1",
        "ScratchRecoveryChannelSeenIdsV1",
        "ScratchRecoverySearchStringsV1",
    )
    execution = []
    for index, (name, kind, value) in enumerate(scalars):
        setter = b.setter(name, kind, 256 * (index + 1), 0)
        enc.set_default(setter, name, value)
        execution.append(setter)
    base_x = 256 * (len(scalars) + 1)
    for index, name in enumerate(arrays):
        kind = "int" if name == "ScratchRecoveryTombstoneGenerationsV1" else "string"
        getter = b.getter(name, kind, base_x + index * 384, 256, array=True)
        clear = b.array_clear(kind, base_x + index * 384, 0)
        bp.connect(getter, name, clear, "TargetArray")
        execution.append(clear)
    chain(bp, b.entry, execution)
    return b.nodes


def build_find_string(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "FindRecoveryStringIndexV1")
    b = v.b
    reset = b.setter("ScratchRecoverySearchIndexV1", "int", 256, 0)
    enc.set_default(reset, "ScratchRecoverySearchIndexV1", "-1")
    strings = b.getter("ScratchRecoverySearchStringsV1", "string", 256, 256, array=True)
    loop = b.foreach("string", 512, 0)
    search = b.getter("ScratchRecoverySearchValueV1", "string", 768, 256)
    equal = v.string_math("EqualEqual_StrStr", 1024, 256)
    branch = v.branch(1280, 0)
    found = b.setter("ScratchRecoverySearchIndexV1", "int", 1536, 0)

    bp.connect(strings, "ScratchRecoverySearchStringsV1", loop, "Array")
    bp.connect(loop, "Array Element", equal, "A")
    bp.connect(search, "ScratchRecoverySearchValueV1", equal, "B")
    bp.connect(equal, "ReturnValue", branch, "Condition")
    bp.connect(loop, "Array Index", found, "ScratchRecoverySearchIndexV1")
    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", loop, "Exec")
    bp.connect(loop, "LoopBody", branch, "execute")
    bp.connect(branch, "then", found, "execute")
    return v.nodes


def build_validate_channel(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "ValidateRecoveryTombstoneChannelV1")
    b = v.b

    seen_clear_source = b.getter("ScratchRecoveryChannelSeenIdsV1", "string", 0, 256, array=True)
    clear_seen = b.array_clear("string", 256, 0)
    channel = b.getter("ScratchRecoveryChannelTombstonesV1", "string", 256, 256, array=True)
    loop = b.foreach("string", 512, 0)
    failed = b.getter("ScratchRecoveryFailedV1", "bool", 768, 256)
    failed_guard = v.branch(1024, 0)
    current = b.setter("ScratchRecoveryCurrentTombstoneV1", "string", 1280, 0)
    current_value = b.getter("ScratchRecoveryCurrentTombstoneV1", "string", 1280, 256)
    trim = b.add("trim_tombstone", "string_trim", 1536, 256)
    trimmed = b.setter("ScratchRecoveryTrimmedTombstoneV1", "string", 1792, 0)
    not_empty = v.string_math("NotEqual_StrStr", 1792, 256, b_default="")
    unchanged = v.string_math("EqualEqual_StrStr", 1792, 448)
    well_formed = v.and_all((not_empty, unchanged), 2048, 352)
    format_branch = v.branch(2304, 0)
    malformed = b.setter("ScratchRecoveryFailedV1", "bool", 2560, -192)
    malformed_detail = b.setter("ScratchRecoveryDetailV1", "string", 2816, -192)

    seen_source, stage_seen = assign_array(
        bp, b, "ScratchRecoveryChannelSeenIdsV1", "ScratchRecoverySearchStringsV1", 2560, 160
    )
    stage_seen_value = b.setter("ScratchRecoverySearchValueV1", "string", 3008, 160)
    find_seen = b.call("FindRecoveryStringIndexV1", 3264, 160)
    seen_index = b.getter("ScratchRecoverySearchIndexV1", "int", 3264, 416)
    unseen = v.int_math("EqualEqual_IntInt", 3520, 416, b_default="-1")
    unseen_branch = v.branch(3776, 160)
    duplicate = b.setter("ScratchRecoveryFailedV1", "bool", 4032, -32)
    duplicate_detail = b.setter("ScratchRecoveryDetailV1", "string", 4288, -32)

    seen_target = b.getter("ScratchRecoveryChannelSeenIdsV1", "string", 4032, 416, array=True)
    add_seen = b.array_add("string", 4288, 160)
    merged_source, stage_merged = assign_array(
        bp, b, "ScratchRecoveryTombstoneIdsV1", "ScratchRecoverySearchStringsV1", 4544, 160
    )
    stage_merged_value = b.setter("ScratchRecoverySearchValueV1", "string", 4992, 160)
    find_merged = b.call("FindRecoveryStringIndexV1", 5248, 160)
    merged_index = b.getter("ScratchRecoverySearchIndexV1", "int", 5248, 416)
    missing = v.int_math("EqualEqual_IntInt", 5504, 416, b_default="-1")
    missing_branch = v.branch(5760, 160)
    merged_ids = b.getter("ScratchRecoveryTombstoneIdsV1", "string", 6016, 416, array=True)
    add_id = b.array_add("string", 6272, 160)
    merged_generations = b.getter(
        "ScratchRecoveryTombstoneGenerationsV1", "int", 6528, 416, array=True
    )
    channel_generation = b.getter("ScratchRecoveryChannelGenerationV1", "int", 6528, 608)
    add_generation = b.array_add("int", 6784, 160)

    enc.set_default(malformed, "ScratchRecoveryFailedV1", "true")
    enc.set_default(malformed_detail, "ScratchRecoveryDetailV1", "MalformedTombstone")
    enc.set_default(duplicate, "ScratchRecoveryFailedV1", "true")
    enc.set_default(duplicate_detail, "ScratchRecoveryDetailV1", "DuplicateTombstone")

    bp.connect(seen_clear_source, "ScratchRecoveryChannelSeenIdsV1", clear_seen, "TargetArray")
    bp.connect(channel, "ScratchRecoveryChannelTombstonesV1", loop, "Array")
    bp.connect(failed, "ScratchRecoveryFailedV1", failed_guard, "Condition")
    bp.connect(loop, "Array Element", current, "ScratchRecoveryCurrentTombstoneV1")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", trim, "SourceString")
    bp.connect(trim, "ReturnValue", trimmed, "ScratchRecoveryTrimmedTombstoneV1")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", not_empty, "A")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", unchanged, "A")
    bp.connect(trim, "ReturnValue", unchanged, "B")
    bp.connect(well_formed, "ReturnValue", format_branch, "Condition")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", stage_seen_value, "ScratchRecoverySearchValueV1")
    bp.connect(seen_index, "ScratchRecoverySearchIndexV1", unseen, "A")
    bp.connect(unseen, "ReturnValue", unseen_branch, "Condition")
    bp.connect(seen_target, "ScratchRecoveryChannelSeenIdsV1", add_seen, "TargetArray")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", add_seen, "NewItem")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", stage_merged_value, "ScratchRecoverySearchValueV1")
    bp.connect(merged_index, "ScratchRecoverySearchIndexV1", missing, "A")
    bp.connect(missing, "ReturnValue", missing_branch, "Condition")
    bp.connect(merged_ids, "ScratchRecoveryTombstoneIdsV1", add_id, "TargetArray")
    bp.connect(current_value, "ScratchRecoveryCurrentTombstoneV1", add_id, "NewItem")
    bp.connect(
        merged_generations,
        "ScratchRecoveryTombstoneGenerationsV1",
        add_generation,
        "TargetArray",
    )
    bp.connect(channel_generation, "ScratchRecoveryChannelGenerationV1", add_generation, "NewItem")

    bp.connect(v.entry, "then", clear_seen, "execute")
    bp.connect(clear_seen, "then", loop, "Exec")
    bp.connect(loop, "LoopBody", failed_guard, "execute")
    bp.connect(failed_guard, "else", current, "execute")
    bp.connect(current, "then", trimmed, "execute")
    bp.connect(trimmed, "then", format_branch, "execute")
    bp.connect(format_branch, "else", malformed, "execute")
    bp.connect(malformed, "then", malformed_detail, "execute")
    bp.connect(format_branch, "then", stage_seen, "execute")
    bp.connect(stage_seen, "then", stage_seen_value, "execute")
    bp.connect(stage_seen_value, "then", find_seen, "execute")
    bp.connect(find_seen, "then", unseen_branch, "execute")
    bp.connect(unseen_branch, "else", duplicate, "execute")
    bp.connect(duplicate, "then", duplicate_detail, "execute")
    bp.connect(unseen_branch, "then", add_seen, "execute")
    bp.connect(add_seen, "then", stage_merged, "execute")
    bp.connect(stage_merged, "then", stage_merged_value, "execute")
    bp.connect(stage_merged_value, "then", find_merged, "execute")
    bp.connect(find_merged, "then", missing_branch, "execute")
    bp.connect(missing_branch, "then", add_id, "execute")
    bp.connect(add_id, "then", add_generation, "execute")
    return v.nodes


def build_merge(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "MergeRecoveryTombstonesV1")
    b = v.b
    reset = b.call("ResetRecoveryTombstonesV1", 256, 0)
    pre_failed = b.getter("ScratchRecoveryFailedV1", "bool", 256, 256)
    pre_guard = v.branch(512, 0)
    newest_slot = b.getter("ScratchRecoveryNewestSlotV1", "string", 512, 256)
    newest_present = v.string_math("NotEqual_StrStr", 768, 256, b_default="")
    newest_branch = v.branch(1024, 0)
    _, newest_tombstones = assign_array(
        bp,
        b,
        "ScratchRecoveryNewestTombstoneFlypathIdsV1",
        "ScratchRecoveryChannelTombstonesV1",
        1280,
        0,
    )
    newest_generation_source = b.getter("ScratchRecoveryNewestGenerationV1", "int", 1728, 256)
    newest_generation = b.setter("ScratchRecoveryChannelGenerationV1", "int", 1984, 0)
    validate_newest = b.call("ValidateRecoveryTombstoneChannelV1", 2240, 0)
    newest_failed = b.getter("ScratchRecoveryFailedV1", "bool", 2240, 256)
    newest_guard = v.branch(2496, 0)
    older_slot = b.getter("ScratchRecoveryOlderSlotV1", "string", 2496, 256)
    older_present = v.string_math("NotEqual_StrStr", 2752, 256, b_default="")
    older_branch = v.branch(3008, 0)
    _, older_tombstones = assign_array(
        bp,
        b,
        "ScratchRecoveryOlderTombstoneFlypathIdsV1",
        "ScratchRecoveryChannelTombstonesV1",
        3264,
        0,
    )
    older_generation_source = b.getter("ScratchRecoveryOlderGenerationV1", "int", 3712, 256)
    older_generation = b.setter("ScratchRecoveryChannelGenerationV1", "int", 3968, 0)
    validate_older = b.call("ValidateRecoveryTombstoneChannelV1", 4224, 0)

    bp.connect(pre_failed, "ScratchRecoveryFailedV1", pre_guard, "Condition")
    bp.connect(newest_slot, "ScratchRecoveryNewestSlotV1", newest_present, "A")
    bp.connect(newest_present, "ReturnValue", newest_branch, "Condition")
    bp.connect(
        newest_generation_source,
        "ScratchRecoveryNewestGenerationV1",
        newest_generation,
        "ScratchRecoveryChannelGenerationV1",
    )
    bp.connect(newest_failed, "ScratchRecoveryFailedV1", newest_guard, "Condition")
    bp.connect(older_slot, "ScratchRecoveryOlderSlotV1", older_present, "A")
    bp.connect(older_present, "ReturnValue", older_branch, "Condition")
    bp.connect(
        older_generation_source,
        "ScratchRecoveryOlderGenerationV1",
        older_generation,
        "ScratchRecoveryChannelGenerationV1",
    )

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", pre_guard, "execute")
    bp.connect(pre_guard, "else", newest_branch, "execute")
    bp.connect(newest_branch, "then", newest_tombstones, "execute")
    bp.connect(newest_tombstones, "then", newest_generation, "execute")
    bp.connect(newest_generation, "then", validate_newest, "execute")
    bp.connect(validate_newest, "then", newest_guard, "execute")
    bp.connect(newest_guard, "else", older_branch, "execute")
    bp.connect(older_branch, "then", older_tombstones, "execute")
    bp.connect(older_tombstones, "then", older_generation, "execute")
    bp.connect(older_generation, "then", validate_older, "execute")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_tombstone_recovery_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_tombstone_recovery_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    trim_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-string-trim-node-form.eddgraph"
    )
    templates["string_trim"] = bp.find_block(trim_forms, r'MemberName="Trim"')
    graphs = {
        "reset-recovery-tombstones-v1.eddgraph": build_reset(bp, enc, templates),
        "find-recovery-string-index-v1.eddgraph": build_find_string(
            bp, enc, validation, templates
        ),
        "validate-recovery-tombstone-channel-v1.eddgraph": build_validate_channel(
            bp, enc, validation, templates
        ),
        "merge-recovery-tombstones-v1.eddgraph": build_merge(
            bp, enc, validation, templates
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
