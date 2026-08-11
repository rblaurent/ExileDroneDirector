"""Structural and semantic contracts for record-granular repository recovery."""

from __future__ import annotations

import argparse
import importlib.util
from dataclasses import dataclass
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_record_recovery_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nodes_of(nodes, class_name: str):
    return [node for node in nodes.values() if class_name in node.node_class]


def calls(nodes, name: str):
    return [
        node
        for node in nodes.values()
        if "K2Node_Call" in node.node_class and f'MemberName="{name}"' in node.text
    ]


def variables(nodes, name: str, node_class: str):
    return [
        node
        for node in nodes.values()
        if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text
    ]


def variable(c, nodes, name: str, node_class: str):
    matches = variables(nodes, name, node_class)
    c.require(len(matches) == 1, f"Expected one {node_class} for {name}; found {len(matches)}")
    return matches[0]


def default(c, node, pin_name: str, expected: str) -> None:
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', c.pin(node, pin_name).body)
    actual = match.group(1) if match else ""
    c.require(actual == expected, f"{pin_name} default {actual!r} != {expected!r}")


def assert_closed(c, nodes, expected: int, function: str, paste: bool) -> None:
    c.require(len(nodes) == expected, f"{function}: expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"{function}: external links {sorted(external)}")
    entries = nodes_of(nodes, "K2Node_FunctionEntry")
    c.require(len(entries) == (0 if paste else 1), f"{function}: entry count changed")
    if not paste:
        c.require(f'MemberName="{function}"' in entries[0].text, f"{function}: wrong entry")
    c.require("bOrphanedPin=True" not in "\n".join(node.text for node in nodes.values()), f"{function}: orphaned pin")


def assert_entry(c, nodes, root, function: str, paste: bool) -> None:
    if paste:
        c.require(not root.pins["execute"].links, f"{function}: paste root changed")
    else:
        c.require_link(nodes_of(nodes, "K2Node_FunctionEntry")[0], "then", root, "execute", f"{function}: entry changed")


def assert_reset(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 18 if paste else 19, "ResetRecoveryRecordsV1", paste)
    generation = variable(c, nodes, "ScratchRecoveryChannelRecordGenerationV1", "K2Node_VariableSet")
    current = variable(c, nodes, "ScratchRecoveryCurrentRecordEnvelopeV1", "K2Node_VariableSet")
    default(c, generation, "ScratchRecoveryChannelRecordGenerationV1", "0")
    default(c, current, "ScratchRecoveryCurrentRecordEnvelopeV1", "")
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
    clears = calls(nodes, "Array_Clear")
    c.require(len(clears) == len(arrays), "Record recovery reset array coverage changed")
    for name in arrays:
        getters = variables(nodes, name, "K2Node_VariableGet")
        c.require(sum(c.linked(getter, name, clear, "TargetArray") for getter in getters for clear in clears) == 1, f"{name} reset changed")
    c.require(not variables(nodes, "ScratchRecoveryFailedV1", "K2Node_VariableSet"), "Record reset must preserve failure")
    c.require(not variables(nodes, "ScratchRecoveryTombstoneIdsV1", "K2Node_VariableSet"), "Record reset must preserve tombstones")
    assert_entry(c, nodes, generation, "ResetRecoveryRecordsV1", paste)


def assert_decode_validate(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 6 if paste else 7, "DecodeValidateRecoveryEnvelopeV1", paste)
    current = variable(c, nodes, "ScratchRecoveryCurrentRecordEnvelopeV1", "K2Node_VariableGet")
    stage = variable(c, nodes, "ScratchEncodedRecordV1", "K2Node_VariableSet")
    decode = calls(nodes, "DecodeRecordV1")
    validate = calls(nodes, "ValidateRecordV1")
    branch = nodes_of(nodes, "K2Node_IfThenElse")
    valid = variable(c, nodes, "ScratchValidV1", "K2Node_VariableGet")
    c.require(len(decode) == len(validate) == len(branch) == 1, "Decode/validate recovery seam changed")
    c.require_link(current, "ScratchRecoveryCurrentRecordEnvelopeV1", stage, "ScratchEncodedRecordV1", "Recovery decode source changed")
    c.require_link(valid, "ScratchValidV1", branch[0], "Condition", "Decode validity guard changed")
    c.require_link(branch[0], "then", validate[0], "execute", "Semantic validation guard changed")
    assert_entry(c, nodes, stage, "DecodeValidateRecoveryEnvelopeV1", paste)


def assert_scan(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 19 if paste else 20, "ScanRecoveryRecordIdentityV1", paste)
    c.require(len(calls(nodes, "FindRecoveryStringIndexV1")) == 2, "Identity lookup count changed")
    c.require(len(calls(nodes, "Array_Add")) == 2, "Identity seen/ambiguous append count changed")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 2, "Identity absence guards changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 2, "Identity branch count changed")
    record_id = variable(c, nodes, "ScratchRecordFlypathIdV1", "K2Node_VariableGet")
    for name in ("ScratchRecoveryChannelSeenRecordIdsV1", "ScratchRecoveryChannelAmbiguousRecordIdsV1"):
        getters = variables(nodes, name, "K2Node_VariableGet")
        adds = [add for add in calls(nodes, "Array_Add") if any(c.linked(getter, name, add, "TargetArray") for getter in getters)]
        c.require(len(adds) == 1, f"{name} append changed")
        c.require_link(record_id, "ScratchRecordFlypathIdV1", adds[0], "NewItem", f"{name} identity source changed")
    root = variables(nodes, "ScratchRecoverySearchStringsV1", "K2Node_VariableSet")[0]
    assert_entry(c, nodes, root, "ScanRecoveryRecordIdentityV1", paste)


def assert_append(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 22 if paste else 23, "AppendRecoveryRecordIfNewV1", paste)
    c.require(len(calls(nodes, "FindRecoveryStringIndexV1")) == 1, "Recovered-ID lookup changed")
    c.require(len(calls(nodes, "Array_Add")) == 5, "Recovered aligned append count changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 1, "Recovered append guard changed")
    mappings = (
        ("ScratchRecordFlypathIdV1", "ScratchRecoveryRecordFlypathIdsV1"),
        ("ScratchRecoveryCurrentRecordEnvelopeV1", "ScratchRecoveryRecordEnvelopesV1"),
        ("ScratchRecordOwnerAccountIdV1", "ScratchRecoveryRecordOwnerAccountIdsV1"),
        ("ScratchRecordVisibilityV1", "ScratchRecoveryRecordVisibilitiesV1"),
        ("ScratchRecordUpdatedUtcV1", "ScratchRecoveryRecordUpdatedUtcV1"),
    )
    for source_name, array_name in mappings:
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        targets = variables(nodes, array_name, "K2Node_VariableGet")
        adds = [add for add in calls(nodes, "Array_Add") if any(c.linked(target, array_name, add, "TargetArray") for target in targets)]
        c.require(len(adds) == 1, f"{array_name} append changed")
        c.require_link(source, source_name, adds[0], "NewItem", f"{array_name} value source changed")
    root = variable(c, nodes, "ScratchRecoverySearchStringsV1", "K2Node_VariableSet")
    assert_entry(c, nodes, root, "AppendRecoveryRecordIfNewV1", paste)


def assert_try_merge(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 22 if paste else 23, "TryMergeRecoveryRecordV1", paste)
    c.require(len(calls(nodes, "FindRecoveryStringIndexV1")) == 2, "Merge record lookup count changed")
    c.require(len(calls(nodes, "AppendRecoveryRecordIfNewV1")) == 2, "Unmasked convergence changed")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 2, "Ambiguous/tombstone absence guards changed")
    c.require(len(calls(nodes, "GreaterEqual_IntInt")) == 1, "Tombstone generation mask changed")
    c.require(len(nodes_of(nodes, "K2Node_GetArrayItem")) == 1, "Tombstone generation lookup changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 3, "Merge record branch count changed")
    tombstone_generations = variable(c, nodes, "ScratchRecoveryTombstoneGenerationsV1", "K2Node_VariableGet")
    item = nodes_of(nodes, "K2Node_GetArrayItem")[0]
    c.require_link(tombstone_generations, "ScratchRecoveryTombstoneGenerationsV1", item, "Array", "Tombstone generation array changed")
    record_generation = variable(c, nodes, "ScratchRecoveryChannelRecordGenerationV1", "K2Node_VariableGet")
    mask = calls(nodes, "GreaterEqual_IntInt")[0]
    c.require_link(record_generation, "ScratchRecoveryChannelRecordGenerationV1", mask, "B", "Record generation mask source changed")
    root = variables(nodes, "ScratchRecoverySearchStringsV1", "K2Node_VariableSet")[0]
    assert_entry(c, nodes, root, "TryMergeRecoveryRecordV1", paste)


def assert_channel(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 18 if paste else 19, "RecoverRecordChannelV1", paste)
    c.require(len(calls(nodes, "Array_Clear")) == 2, "Channel ambiguity reset changed")
    loops = nodes_of(nodes, "K2Node_MacroInstance")
    c.require(len(loops) == 2 and all("ForEachLoop" in loop.text for loop in loops), "Channel two-pass scan changed")
    c.require(len(calls(nodes, "DecodeValidateRecoveryEnvelopeV1")) == 2, "Channel decode pass count changed")
    c.require(len(calls(nodes, "ScanRecoveryRecordIdentityV1")) == 1, "Identity scan call changed")
    c.require(len(calls(nodes, "TryMergeRecoveryRecordV1")) == 1, "Merge pass call changed")
    c.require(len(variables(nodes, "ScratchRecoveryCurrentRecordEnvelopeV1", "K2Node_VariableSet")) == 2, "Channel envelope staging changed")
    root = calls(nodes, "Array_Clear")[0]
    assert_entry(c, nodes, root, "RecoverRecordChannelV1", paste)


def assert_recover(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 19 if paste else 20, "RecoverRepositoryRecordsV1", paste)
    reset = calls(nodes, "ResetRecoveryRecordsV1")
    c.require(len(reset) == 1, "Record recovery reset call changed")
    c.require(len(calls(nodes, "RecoverRecordChannelV1")) == 2, "Newest/older recovery call count changed")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 2, "Record slot presence guards changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 3, "Record repository branch count changed")
    c.require(not variables(nodes, "ScratchRecoveryFailedV1", "K2Node_VariableSet"), "Record recovery must preserve prior failure")
    for source_name, target_name in (
        ("ScratchRecoveryNewestRecordEnvelopesV1", "ScratchRecoveryChannelRecordEnvelopesV1"),
        ("ScratchRecoveryOlderRecordEnvelopesV1", "ScratchRecoveryChannelRecordEnvelopesV1"),
        ("ScratchRecoveryNewestGenerationV1", "ScratchRecoveryChannelRecordGenerationV1"),
        ("ScratchRecoveryOlderGenerationV1", "ScratchRecoveryChannelRecordGenerationV1"),
    ):
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        targets = variables(nodes, target_name, "K2Node_VariableSet")
        c.require(sum(c.linked(source, source_name, target, target_name) for target in targets) == 1, f"{source_name} staging changed")
    assert_entry(c, nodes, reset[0], "RecoverRepositoryRecordsV1", paste)


def assert_commit(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 19 if paste else 20, "CommitRecoveredRepositoryV1", paste)
    branch = nodes_of(nodes, "K2Node_IfThenElse")
    c.require(len(branch) == 1, "Recovered commit failure guard changed")
    failed = variable(c, nodes, "ScratchRecoveryFailedV1", "K2Node_VariableGet")
    c.require_link(failed, "ScratchRecoveryFailedV1", branch[0], "Condition", "Recovered commit failure source changed")
    mappings = (
        ("ScratchRecoveryRecordEnvelopesV1", "ActiveRecordEnvelopesV1"),
        ("ScratchRecoveryTombstoneIdsV1", "ActiveTombstoneFlypathIdsV1"),
        ("ScratchRecoveryRecordFlypathIdsV1", "ActiveFlypathIdsV1"),
        ("ScratchRecoveryRecordOwnerAccountIdsV1", "ActiveOwnerAccountIdsV1"),
        ("ScratchRecoveryRecordVisibilitiesV1", "ActiveVisibilitiesV1"),
        ("ScratchRecoveryRecordUpdatedUtcV1", "ActiveUpdatedUtcV1"),
        ("ScratchRecoveryNewestGenerationV1", "ActiveGenerationV1"),
        ("ScratchRecoveryNewestSlotV1", "ActiveSlotV1"),
    )
    for source_name, target_name in mappings:
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        target = variable(c, nodes, target_name, "K2Node_VariableSet")
        c.require_link(source, source_name, target, target_name, f"{target_name} commit source changed")
    loaded = variable(c, nodes, "RepositoryLoadedV1", "K2Node_VariableSet")
    default(c, loaded, "RepositoryLoadedV1", "true")
    assert_entry(c, nodes, branch[0], "CommitRecoveredRepositoryV1", paste)


def assert_load(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 5 if paste else 6, "LoadRepositoryV1", paste)
    names = (
        "ReadRepositoryStorageSlotsV1",
        "SelectRepositoryRecoveryOrderV1",
        "MergeRecoveryTombstonesV1",
        "RecoverRepositoryRecordsV1",
        "CommitRecoveredRepositoryV1",
    )
    sequence = []
    for name in names:
        found = calls(nodes, name)
        c.require(len(found) == 1, f"Load orchestration call {name} changed")
        sequence.append(found[0])
    for left, right in zip(sequence, sequence[1:]):
        c.require_link(left, "then", right, "execute", "Load orchestration order changed")
    assert_entry(c, nodes, sequence[0], "LoadRepositoryV1", paste)


@dataclass(frozen=True)
class Record:
    flypath_id: str
    envelope: str
    owner: str = "owner"
    visibility: str = "private"
    updated: str = "2026-08-11T00:00:00Z"
    valid: bool = True


def recover_model(newest, older=(), tombstones=None, newest_generation=2, older_generation=1):
    tombstones = tombstones or {}
    recovered = []
    recovered_ids = set()
    for generation, channel in ((newest_generation, newest), (older_generation, older)):
        valid = [record for record in channel if record.valid]
        counts = {}
        for record in valid:
            counts[record.flypath_id] = counts.get(record.flypath_id, 0) + 1
        for record in valid:
            if counts[record.flypath_id] != 1:
                continue
            if tombstones.get(record.flypath_id, 0) >= generation:
                continue
            if record.flypath_id in recovered_ids:
                continue
            recovered_ids.add(record.flypath_id)
            recovered.append(record)
    return recovered


def assert_semantics() -> None:
    n = Record("n", "new")
    o = Record("o", "old")
    fallback = Record("x", "older-x", owner="fallback-owner")
    corrupt = Record("x", "corrupt-x", valid=False)
    cases = (
        ((n,), (), {}, ["new"]),
        ((n,), (o,), {}, ["new", "old"]),
        ((Record("x", "new-x"),), (fallback,), {}, ["new-x"]),
        ((corrupt,), (fallback,), {}, ["older-x"]),
        ((Record("x", "a"), Record("x", "b")), (fallback,), {}, ["older-x"]),
        ((), (fallback,), {"x": 2}, []),
        ((Record("x", "new-x"),), (), {"x": 1}, ["new-x"]),
        ((Record("x", "new-x"),), (fallback,), {"x": 2}, []),
        ((Record("x", "a"), Record("x", "b")), (), {}, []),
    )
    for newest, older, tombstones, expected in cases:
        actual = [record.envelope for record in recover_model(newest, older, tombstones)]
        if actual != expected:
            raise AssertionError((newest, older, tombstones, actual, expected))
    metadata = recover_model((corrupt,), (fallback,))[0]
    if (metadata.flypath_id, metadata.owner, metadata.visibility, metadata.updated) != (
        "x",
        "fallback-owner",
        "private",
        "2026-08-11T00:00:00Z",
    ):
        raise AssertionError("Recovered metadata did not remain aligned with fallback envelope")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument(
        "--only",
        choices=("all", "reset", "decode", "scan", "append", "try_merge", "channel", "recover", "commit", "load"),
        default="all",
    )
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    specs = {
        "reset": ("reset-recovery-records-v1", assert_reset),
        "decode": ("decode-validate-recovery-envelope-v1", assert_decode_validate),
        "scan": ("scan-recovery-record-identity-v1", assert_scan),
        "append": ("append-recovery-record-if-new-v1", assert_append),
        "try_merge": ("try-merge-recovery-record-v1", assert_try_merge),
        "channel": ("recover-record-channel-v1", assert_channel),
        "recover": ("recover-repository-records-v1", assert_recover),
        "commit": ("commit-recovered-repository-v1", assert_commit),
        "load": ("load-repository-v1", assert_load),
    }
    selected = specs.items() if args.only == "all" else ((args.only, specs[args.only]),)
    for _, (filename, assertion) in selected:
        assertion(c, c.parse_graph(args.input_dir / f"{filename}{suffix}.eddgraph"), args.paste)
    assert_semantics()
    print("Repository record recovery graph contracts passed")


if __name__ == "__main__":
    main()
