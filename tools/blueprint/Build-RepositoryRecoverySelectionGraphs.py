"""Build deterministic A/B recovery-order selection graphs.

This slice stops before tombstone merging and record recovery.  It converts the
validated raw slot channels into newest/older staging, accepts identical
equal-generation peers with the deterministic B tie-break, and fails closed on
divergent equal-generation snapshots.
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


def build_reset(bp, enc, templates):
    b = enc.Builder(bp, templates, "ResetRecoverySelectionV1")
    scalars = (
        ("ScratchRecoveryFailedV1", "bool", "false"),
        ("ScratchRecoveryDetailV1", "string", ""),
        ("ScratchRecoveryEquivalentV1", "bool", "false"),
        ("ScratchRecoveryRecordArraysEqualV1", "bool", "false"),
        ("ScratchRecoveryNewestSlotV1", "string", ""),
        ("ScratchRecoveryNewestGenerationV1", "int", "0"),
        ("ScratchRecoveryOlderSlotV1", "string", ""),
        ("ScratchRecoveryOlderGenerationV1", "int", "0"),
        ("ScratchCompareStringsEqualV1", "bool", "false"),
    )
    arrays = (
        "ScratchRecoveryNewestRecordEnvelopesV1",
        "ScratchRecoveryNewestTombstoneFlypathIdsV1",
        "ScratchRecoveryOlderRecordEnvelopesV1",
        "ScratchRecoveryOlderTombstoneFlypathIdsV1",
        "ScratchCompareLeftStringsV1",
        "ScratchCompareRightStringsV1",
    )
    execution = []
    for index, (name, kind, default) in enumerate(scalars):
        setter = b.setter(name, kind, 256 * (index + 1), 0)
        enc.set_default(setter, name, default)
        execution.append(setter)
    base_x = 256 * (len(scalars) + 1)
    for index, name in enumerate(arrays):
        getter = b.getter(name, "string", base_x + index * 384, 256, array=True)
        clear = b.array_clear("string", base_x + index * 384, 0)
        bp.connect(getter, name, clear, "TargetArray")
        execution.append(clear)
    chain(bp, b.entry, execution)
    return b.nodes


def build_compare_strings(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "CompareRecoveryStringArraysV1")
    b = v.b
    result_true = b.setter("ScratchCompareStringsEqualV1", "bool", 256, 0)
    enc.set_default(result_true, "ScratchCompareStringsEqualV1", "true")
    left = b.getter("ScratchCompareLeftStringsV1", "string", 256, 256, array=True)
    right = b.getter("ScratchCompareRightStringsV1", "string", 256, 512, array=True)
    left_length = v.length(left, "ScratchCompareLeftStringsV1", "string", 512, 256)
    right_length = v.length(right, "ScratchCompareRightStringsV1", "string", 512, 512)
    lengths_equal = v.int_math("EqualEqual_IntInt", 768, 384)
    length_branch = v.branch(1024, 0)
    length_failed = b.setter("ScratchCompareStringsEqualV1", "bool", 1280, -192)
    enc.set_default(length_failed, "ScratchCompareStringsEqualV1", "false")
    loop = b.foreach("string", 1280, 128)
    right_item = v.array_item(
        right,
        "ScratchCompareRightStringsV1",
        loop,
        "Array Index",
        "string",
        1536,
        384,
    )
    item_equal = v.string_math("EqualEqual_StrStr", 1792, 384)
    item_branch = v.branch(2048, 128)
    item_failed = b.setter("ScratchCompareStringsEqualV1", "bool", 2304, 128)
    enc.set_default(item_failed, "ScratchCompareStringsEqualV1", "false")

    bp.connect(left_length, "ReturnValue", lengths_equal, "A")
    bp.connect(right_length, "ReturnValue", lengths_equal, "B")
    bp.connect(lengths_equal, "ReturnValue", length_branch, "Condition")
    bp.connect(left, "ScratchCompareLeftStringsV1", loop, "Array")
    bp.connect(loop, "Array Element", item_equal, "A")
    bp.connect(right_item, "Output", item_equal, "B")
    bp.connect(item_equal, "ReturnValue", item_branch, "Condition")

    bp.connect(v.entry, "then", result_true, "execute")
    bp.connect(result_true, "then", length_branch, "execute")
    bp.connect(length_branch, "else", length_failed, "execute")
    bp.connect(length_branch, "then", loop, "Exec")
    bp.connect(loop, "LoopBody", item_branch, "execute")
    bp.connect(item_branch, "else", item_failed, "execute")
    return v.nodes


def assign_array(bp, b, source_name: str, target_name: str, x: int, y: int):
    getter = b.getter(source_name, "string", x, y + 224, array=True)
    setter = b.setter(target_name, "string", x + 224, y, array=True)
    bp.connect(getter, source_name, setter, target_name)
    return getter, setter


def build_compare_equal_storage(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "CompareEqualGenerationStorageV1")
    b = v.b
    execution = []
    _, left_records = assign_array(
        bp, b, "ScratchStorageARecordEnvelopesV1", "ScratchCompareLeftStringsV1", 0, 0
    )
    _, right_records = assign_array(
        bp, b, "ScratchStorageBRecordEnvelopesV1", "ScratchCompareRightStringsV1", 448, 0
    )
    compare_records = b.call("CompareRecoveryStringArraysV1", 896, 0)
    record_result = b.getter("ScratchCompareStringsEqualV1", "bool", 896, 256)
    store_record_result = b.setter("ScratchRecoveryRecordArraysEqualV1", "bool", 1152, 0)
    bp.connect(
        record_result,
        "ScratchCompareStringsEqualV1",
        store_record_result,
        "ScratchRecoveryRecordArraysEqualV1",
    )
    _, left_tombstones = assign_array(
        bp, b, "ScratchStorageATombstoneFlypathIdsV1", "ScratchCompareLeftStringsV1", 1408, 0
    )
    _, right_tombstones = assign_array(
        bp, b, "ScratchStorageBTombstoneFlypathIdsV1", "ScratchCompareRightStringsV1", 1856, 0
    )
    compare_tombstones = b.call("CompareRecoveryStringArraysV1", 2304, 0)
    record_equal = b.getter("ScratchRecoveryRecordArraysEqualV1", "bool", 2304, 256)
    tombstone_equal = b.getter("ScratchCompareStringsEqualV1", "bool", 2304, 400)
    both_equal = v.bool_math("BooleanAND", 2560, 320)
    equivalent = b.setter("ScratchRecoveryEquivalentV1", "bool", 2816, 0)
    bp.connect(record_equal, "ScratchRecoveryRecordArraysEqualV1", both_equal, "A")
    bp.connect(tombstone_equal, "ScratchCompareStringsEqualV1", both_equal, "B")
    bp.connect(both_equal, "ReturnValue", equivalent, "ScratchRecoveryEquivalentV1")
    execution.extend(
        (
            left_records,
            right_records,
            compare_records,
            store_record_result,
            left_tombstones,
            right_tombstones,
            compare_tombstones,
            equivalent,
        )
    )
    chain(bp, v.entry, execution)
    return v.nodes


def stage_scalar(bp, b, source_name: str, target_name: str, kind: str, x: int, y: int):
    getter = b.getter(source_name, kind, x, y + 224)
    setter = b.setter(target_name, kind, x + 224, y)
    bp.connect(getter, source_name, setter, target_name)
    return setter


def stage_slot(bp, enc, templates, function: str, newest: str, older: str | None):
    b = enc.Builder(bp, templates, function)
    execution = []
    newest_slot = b.setter("ScratchRecoveryNewestSlotV1", "string", 256, 0)
    enc.set_default(newest_slot, "ScratchRecoveryNewestSlotV1", f"EDD_Repository_{newest}")
    execution.append(newest_slot)
    execution.append(
        stage_scalar(
            bp,
            b,
            f"ScratchStorage{newest}GenerationV1",
            "ScratchRecoveryNewestGenerationV1",
            "int",
            512,
            0,
        )
    )
    _, newest_records = assign_array(
        bp,
        b,
        f"ScratchStorage{newest}RecordEnvelopesV1",
        "ScratchRecoveryNewestRecordEnvelopesV1",
        960,
        0,
    )
    _, newest_tombstones = assign_array(
        bp,
        b,
        f"ScratchStorage{newest}TombstoneFlypathIdsV1",
        "ScratchRecoveryNewestTombstoneFlypathIdsV1",
        1408,
        0,
    )
    execution.extend((newest_records, newest_tombstones))

    older_slot = b.setter("ScratchRecoveryOlderSlotV1", "string", 1856, 0)
    older_generation = b.setter("ScratchRecoveryOlderGenerationV1", "int", 2112, 0)
    execution.extend((older_slot, older_generation))
    if older is None:
        enc.set_default(older_slot, "ScratchRecoveryOlderSlotV1", "")
        enc.set_default(older_generation, "ScratchRecoveryOlderGenerationV1", "0")
        for index, name in enumerate(
            (
                "ScratchRecoveryOlderRecordEnvelopesV1",
                "ScratchRecoveryOlderTombstoneFlypathIdsV1",
            )
        ):
            getter = b.getter(name, "string", 2368 + index * 384, 224, array=True)
            clear = b.array_clear("string", 2368 + index * 384, 0)
            bp.connect(getter, name, clear, "TargetArray")
            execution.append(clear)
    else:
        enc.set_default(older_slot, "ScratchRecoveryOlderSlotV1", f"EDD_Repository_{older}")
        older_generation_source = b.getter(
            f"ScratchStorage{older}GenerationV1", "int", 2112, 224
        )
        bp.connect(
            older_generation_source,
            f"ScratchStorage{older}GenerationV1",
            older_generation,
            "ScratchRecoveryOlderGenerationV1",
        )
        _, older_records = assign_array(
            bp,
            b,
            f"ScratchStorage{older}RecordEnvelopesV1",
            "ScratchRecoveryOlderRecordEnvelopesV1",
            2368,
            0,
        )
        _, older_tombstones = assign_array(
            bp,
            b,
            f"ScratchStorage{older}TombstoneFlypathIdsV1",
            "ScratchRecoveryOlderTombstoneFlypathIdsV1",
            2816,
            0,
        )
        execution.extend((older_records, older_tombstones))
    chain(bp, b.entry, execution)
    return b.nodes


def build_select(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "SelectRepositoryRecoveryOrderV1")
    b = v.b
    reset = b.call("ResetRecoverySelectionV1", 256, 0)
    a_valid = b.getter("ScratchStorageAHeaderValidV1", "bool", 256, 256)
    b_valid = b.getter("ScratchStorageBHeaderValidV1", "bool", 256, 400)
    a_branch = v.branch(512, 0)
    b_only_branch = v.branch(768, -192)
    both_branch = v.branch(768, 192)
    a_only = b.call("StageRecoveryAOnlyV1", 1024, 384)
    b_only = b.call("StageRecoveryBOnlyV1", 1024, -384)
    b_tie = b.call("StageRecoveryBOnlyV1", 2560, 448)

    a_generation = b.getter("ScratchStorageAGenerationV1", "int", 1024, 128)
    b_generation = b.getter("ScratchStorageBGenerationV1", "int", 1024, 272)
    a_greater = v.int_math("Greater_IntInt", 1280, 128)
    a_greater_branch = v.branch(1536, 128)
    a_newer = b.call("StageRecoveryANewerV1", 1792, -64)
    b_greater = v.int_math("Greater_IntInt", 1792, 272)
    b_greater_branch = v.branch(2048, 272)
    b_newer = b.call("StageRecoveryBNewerV1", 2304, 80)
    compare_equal = b.call("CompareEqualGenerationStorageV1", 2304, 272)
    equivalent = b.getter("ScratchRecoveryEquivalentV1", "bool", 2304, 544)
    equivalent_branch = v.branch(2560, 272)
    failed = b.setter("ScratchRecoveryFailedV1", "bool", 2816, 208)
    detail = b.setter("ScratchRecoveryDetailV1", "string", 3072, 208)
    enc.set_default(failed, "ScratchRecoveryFailedV1", "true")
    enc.set_default(detail, "ScratchRecoveryDetailV1", "DivergentEqualGeneration")

    bp.connect(a_valid, "ScratchStorageAHeaderValidV1", a_branch, "Condition")
    bp.connect(b_valid, "ScratchStorageBHeaderValidV1", b_only_branch, "Condition")
    bp.connect(b_valid, "ScratchStorageBHeaderValidV1", both_branch, "Condition")
    bp.connect(a_generation, "ScratchStorageAGenerationV1", a_greater, "A")
    bp.connect(b_generation, "ScratchStorageBGenerationV1", a_greater, "B")
    bp.connect(b_generation, "ScratchStorageBGenerationV1", b_greater, "A")
    bp.connect(a_generation, "ScratchStorageAGenerationV1", b_greater, "B")
    bp.connect(a_greater, "ReturnValue", a_greater_branch, "Condition")
    bp.connect(b_greater, "ReturnValue", b_greater_branch, "Condition")
    bp.connect(equivalent, "ScratchRecoveryEquivalentV1", equivalent_branch, "Condition")

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", a_branch, "execute")
    bp.connect(a_branch, "else", b_only_branch, "execute")
    bp.connect(b_only_branch, "then", b_only, "execute")
    bp.connect(a_branch, "then", both_branch, "execute")
    bp.connect(both_branch, "else", a_only, "execute")
    bp.connect(both_branch, "then", a_greater_branch, "execute")
    bp.connect(a_greater_branch, "then", a_newer, "execute")
    bp.connect(a_greater_branch, "else", b_greater_branch, "execute")
    bp.connect(b_greater_branch, "then", b_newer, "execute")
    bp.connect(b_greater_branch, "else", compare_equal, "execute")
    bp.connect(compare_equal, "then", equivalent_branch, "execute")
    bp.connect(equivalent_branch, "then", b_tie, "execute")
    bp.connect(equivalent_branch, "else", failed, "execute")
    bp.connect(failed, "then", detail, "execute")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_recovery_selection_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_recovery_selection_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    graphs = {
        "reset-recovery-selection-v1.eddgraph": build_reset(bp, enc, templates),
        "compare-recovery-string-arrays-v1.eddgraph": build_compare_strings(
            bp, enc, validation, templates
        ),
        "compare-equal-generation-storage-v1.eddgraph": build_compare_equal_storage(
            bp, enc, validation, templates
        ),
        "stage-recovery-a-only-v1.eddgraph": stage_slot(
            bp, enc, templates, "StageRecoveryAOnlyV1", "A", None
        ),
        "stage-recovery-b-only-v1.eddgraph": stage_slot(
            bp, enc, templates, "StageRecoveryBOnlyV1", "B", None
        ),
        "stage-recovery-a-newer-v1.eddgraph": stage_slot(
            bp, enc, templates, "StageRecoveryANewerV1", "A", "B"
        ),
        "stage-recovery-b-newer-v1.eddgraph": stage_slot(
            bp, enc, templates, "StageRecoveryBNewerV1", "B", "A"
        ),
        "select-repository-recovery-order-v1.eddgraph": build_select(
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
