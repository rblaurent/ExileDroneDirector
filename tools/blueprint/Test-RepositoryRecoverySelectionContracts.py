"""Semantic contracts for repository recovery-order selection graphs."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_recovery_selection_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nodes_with(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def nodes_of(nodes, class_name: str):
    return [node for node in nodes.values() if class_name in node.node_class]


def calls(nodes, name: str):
    return [
        node
        for node in nodes.values()
        if "K2Node_Call" in node.node_class and f'MemberName="{name}"' in node.text
    ]


def one(c, nodes, marker: str):
    matches = nodes_with(nodes, marker)
    c.require(len(matches) == 1, f"Expected one node containing {marker!r}; found {len(matches)}")
    return matches[0]


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
    body = c.pin(node, pin_name).body
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', body)
    if expected == "":
        c.require(match is None or match.group(1) == "", f"{pin_name} must default empty")
    else:
        c.require(match is not None and match.group(1) == expected, f"{pin_name} default changed")


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
    c.require(
        "bOrphanedPin=True" not in "\n".join(node.text for node in nodes.values()),
        f"{function}: orphaned pin",
    )


def assert_reset(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 21 if paste else 22, "ResetRecoverySelectionV1", paste)
    scalars = (
        ("ScratchRecoveryFailedV1", "false"),
        ("ScratchRecoveryDetailV1", ""),
        ("ScratchRecoveryEquivalentV1", "false"),
        ("ScratchRecoveryRecordArraysEqualV1", "false"),
        ("ScratchRecoveryNewestSlotV1", ""),
        ("ScratchRecoveryNewestGenerationV1", "0"),
        ("ScratchRecoveryOlderSlotV1", ""),
        ("ScratchRecoveryOlderGenerationV1", "0"),
        ("ScratchCompareStringsEqualV1", "false"),
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
    for name, expected in scalars:
        setter = variable(c, nodes, name, "K2Node_VariableSet")
        default(c, setter, name, expected)
        execution.append(setter)
    clears = calls(nodes, "Array_Clear")
    c.require(len(clears) == len(arrays), "Recovery reset array coverage changed")
    for name in arrays:
        getter = variable(c, nodes, name, "K2Node_VariableGet")
        matching = [node for node in clears if c.linked(getter, name, node, "TargetArray")]
        c.require(len(matching) == 1, f"{name} must feed exactly one clear")
        execution.append(matching[0])
    if paste:
        c.require(not execution[0].pins["execute"].links, "Recovery reset paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", execution[0], "execute", "Recovery reset entry changed")
    for left, right in zip(execution, execution[1:]):
        c.require_link(left, "then", right, "execute", "Recovery reset order changed")


def assert_compare_strings(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 13 if paste else 14, "CompareRecoveryStringArraysV1", paste)
    c.require(len(calls(nodes, "Array_Length")) == 2, "Array comparison length guards changed")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 1, "Array comparison length equality changed")
    c.require(len(calls(nodes, "EqualEqual_StrStr")) == 1, "Array item equality changed")
    loops = nodes_of(nodes, "K2Node_MacroInstance")
    c.require(len(loops) == 1 and "ForEachLoop" in loops[0].text, "Array comparison loop changed")
    c.require(len(nodes_of(nodes, "K2Node_GetArrayItem")) == 1, "Indexed right-array read changed")
    branches = nodes_of(nodes, "K2Node_IfThenElse")
    c.require(len(branches) == 2, "Array comparison branch coverage changed")
    setters = variables(nodes, "ScratchCompareStringsEqualV1", "K2Node_VariableSet")
    c.require(len(setters) == 3, "Array comparison must own true and two monotonic false writes")
    by_default = {value: [] for value in ("true", "false")}
    for setter in setters:
        body = c.pin(setter, "ScratchCompareStringsEqualV1").body
        match = re.search(r'(?:^|,)DefaultValue="(true|false)"(?:,|$)', body)
        c.require(match is not None, "Comparison setter default missing")
        by_default[match.group(1)].append(setter)
    c.require(len(by_default["true"]) == 1 and len(by_default["false"]) == 2, "Comparison defaults changed")
    if paste:
        c.require(not by_default["true"][0].pins["execute"].links, "Comparison paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", by_default["true"][0], "execute", "Comparison entry changed")


def assert_compare_equal_storage(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 16 if paste else 17, "CompareEqualGenerationStorageV1", paste)
    c.require(len(calls(nodes, "CompareRecoveryStringArraysV1")) == 2, "Equal peer comparison count changed")
    pairs = (
        ("ScratchStorageARecordEnvelopesV1", "ScratchCompareLeftStringsV1"),
        ("ScratchStorageBRecordEnvelopesV1", "ScratchCompareRightStringsV1"),
        ("ScratchStorageATombstoneFlypathIdsV1", "ScratchCompareLeftStringsV1"),
        ("ScratchStorageBTombstoneFlypathIdsV1", "ScratchCompareRightStringsV1"),
    )
    for source_name, target_name in pairs:
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        targets = variables(nodes, target_name, "K2Node_VariableSet")
        matching = [target for target in targets if c.linked(source, source_name, target, target_name)]
        c.require(len(matching) == 1, f"{source_name} comparison staging changed")
    record_store = variable(c, nodes, "ScratchRecoveryRecordArraysEqualV1", "K2Node_VariableSet")
    equivalent = variable(c, nodes, "ScratchRecoveryEquivalentV1", "K2Node_VariableSet")
    conjunction = one(c, nodes, 'MemberName="BooleanAND"')
    c.require_link(conjunction, "ReturnValue", equivalent, "ScratchRecoveryEquivalentV1", "Peer equality conjunction changed")
    if not paste:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        first_left = variables(nodes, "ScratchCompareLeftStringsV1", "K2Node_VariableSet")[0]
        c.require_link(entry, "then", first_left, "execute", "Equal-peer comparison entry changed")
    else:
        c.require(not variables(nodes, "ScratchCompareLeftStringsV1", "K2Node_VariableSet")[0].pins["execute"].links, "Equal-peer paste root changed")
    c.require(record_store is not equivalent, "Peer equality result channels aliased")


def assert_stage(c, nodes, paste: bool, newest: str, older: str | None) -> None:
    function = f"StageRecovery{newest}{'Newer' if older else 'Only'}V1"
    assert_closed(c, nodes, (14 if older else 13) if paste else (15 if older else 14), function, paste)
    newest_slot = variable(c, nodes, "ScratchRecoveryNewestSlotV1", "K2Node_VariableSet")
    default(c, newest_slot, "ScratchRecoveryNewestSlotV1", f"EDD_Repository_{newest}")
    for source_suffix, target_name in (
        ("GenerationV1", "ScratchRecoveryNewestGenerationV1"),
        ("RecordEnvelopesV1", "ScratchRecoveryNewestRecordEnvelopesV1"),
        ("TombstoneFlypathIdsV1", "ScratchRecoveryNewestTombstoneFlypathIdsV1"),
    ):
        source_name = f"ScratchStorage{newest}{source_suffix}"
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        target = variable(c, nodes, target_name, "K2Node_VariableSet")
        c.require_link(source, source_name, target, target_name, f"{function} newest staging changed")
    older_slot = variable(c, nodes, "ScratchRecoveryOlderSlotV1", "K2Node_VariableSet")
    older_generation = variable(c, nodes, "ScratchRecoveryOlderGenerationV1", "K2Node_VariableSet")
    if older:
        default(c, older_slot, "ScratchRecoveryOlderSlotV1", f"EDD_Repository_{older}")
        for source_suffix, target_name in (
            ("GenerationV1", "ScratchRecoveryOlderGenerationV1"),
            ("RecordEnvelopesV1", "ScratchRecoveryOlderRecordEnvelopesV1"),
            ("TombstoneFlypathIdsV1", "ScratchRecoveryOlderTombstoneFlypathIdsV1"),
        ):
            source_name = f"ScratchStorage{older}{source_suffix}"
            source = variable(c, nodes, source_name, "K2Node_VariableGet")
            target = variable(c, nodes, target_name, "K2Node_VariableSet")
            c.require_link(source, source_name, target, target_name, f"{function} older staging changed")
    else:
        default(c, older_slot, "ScratchRecoveryOlderSlotV1", "")
        default(c, older_generation, "ScratchRecoveryOlderGenerationV1", "0")
        clears = calls(nodes, "Array_Clear")
        c.require(len(clears) == 2, f"{function} must clear both older arrays")
        for name in (
            "ScratchRecoveryOlderRecordEnvelopesV1",
            "ScratchRecoveryOlderTombstoneFlypathIdsV1",
        ):
            getter = variable(c, nodes, name, "K2Node_VariableGet")
            c.require(any(c.linked(getter, name, clear, "TargetArray") for clear in clears), f"{function} stale {name}")
    if paste:
        c.require(not newest_slot.pins["execute"].links, f"{function} paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", newest_slot, "execute", f"{function} entry changed")


def assert_select(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 22 if paste else 23, "SelectRepositoryRecoveryOrderV1", paste)
    expected_calls = {
        "ResetRecoverySelectionV1": 1,
        "StageRecoveryAOnlyV1": 1,
        "StageRecoveryBOnlyV1": 2,
        "StageRecoveryANewerV1": 1,
        "StageRecoveryBNewerV1": 1,
        "CompareEqualGenerationStorageV1": 1,
    }
    for name, count in expected_calls.items():
        c.require(len(calls(nodes, name)) == count, f"{name} call count changed")
    c.require(len(calls(nodes, "Greater_IntInt")) == 2, "Generation ordering comparisons changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 6, "Recovery selection branch coverage changed")
    failed = variable(c, nodes, "ScratchRecoveryFailedV1", "K2Node_VariableSet")
    detail = variable(c, nodes, "ScratchRecoveryDetailV1", "K2Node_VariableSet")
    default(c, failed, "ScratchRecoveryFailedV1", "true")
    default(c, detail, "ScratchRecoveryDetailV1", "DivergentEqualGeneration")
    c.require_link(failed, "then", detail, "execute", "Split-brain failure detail changed")
    reset = calls(nodes, "ResetRecoverySelectionV1")[0]
    a_valid = variable(c, nodes, "ScratchStorageAHeaderValidV1", "K2Node_VariableGet")
    a_branches = [branch for branch in nodes_of(nodes, "K2Node_IfThenElse") if c.linked(a_valid, "ScratchStorageAHeaderValidV1", branch, "Condition")]
    c.require(len(a_branches) == 1, "A validity root branch changed")
    if paste:
        c.require(not reset.pins["execute"].links, "Selection paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", reset, "execute", "Selection entry changed")
    c.require_link(reset, "then", a_branches[0], "execute", "Selection reset-before-branch changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument(
        "--only",
        choices=(
            "all",
            "reset",
            "compare_strings",
            "compare_equal",
            "a_only",
            "b_only",
            "a_newer",
            "b_newer",
            "select",
        ),
        default="all",
    )
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    specs = {
        "reset": ("reset-recovery-selection-v1", assert_reset),
        "compare_strings": ("compare-recovery-string-arrays-v1", assert_compare_strings),
        "compare_equal": ("compare-equal-generation-storage-v1", assert_compare_equal_storage),
        "a_only": ("stage-recovery-a-only-v1", lambda c, n, p: assert_stage(c, n, p, "A", None)),
        "b_only": ("stage-recovery-b-only-v1", lambda c, n, p: assert_stage(c, n, p, "B", None)),
        "a_newer": ("stage-recovery-a-newer-v1", lambda c, n, p: assert_stage(c, n, p, "A", "B")),
        "b_newer": ("stage-recovery-b-newer-v1", lambda c, n, p: assert_stage(c, n, p, "B", "A")),
        "select": ("select-repository-recovery-order-v1", assert_select),
    }
    selected = specs.items() if args.only == "all" else ((args.only, specs[args.only]),)
    for _, (filename, assertion) in selected:
        assertion(c, c.parse_graph(args.input_dir / f"{filename}{suffix}.eddgraph"), args.paste)
    print("Repository recovery selection graph contracts passed")


if __name__ == "__main__":
    main()
