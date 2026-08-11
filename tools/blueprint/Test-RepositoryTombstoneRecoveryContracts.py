"""Structural and semantic contracts for tombstone recovery graphs."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_tombstone_recovery_contract_base", path)
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


def has_default(c, node, pin_name: str, expected: str) -> bool:
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', c.pin(node, pin_name).body)
    return (match.group(1) if match else "") == expected


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
    assert_closed(c, nodes, 15 if paste else 16, "ResetRecoveryTombstonesV1", paste)
    scalars = (
        ("ScratchRecoveryChannelGenerationV1", "0"),
        ("ScratchRecoverySearchValueV1", ""),
        ("ScratchRecoverySearchIndexV1", "-1"),
        ("ScratchRecoveryCurrentTombstoneV1", ""),
        ("ScratchRecoveryTrimmedTombstoneV1", ""),
    )
    arrays = (
        "ScratchRecoveryTombstoneIdsV1",
        "ScratchRecoveryTombstoneGenerationsV1",
        "ScratchRecoveryChannelTombstonesV1",
        "ScratchRecoveryChannelSeenIdsV1",
        "ScratchRecoverySearchStringsV1",
    )
    execution = []
    for name, expected in scalars:
        setter = variable(c, nodes, name, "K2Node_VariableSet")
        default(c, setter, name, expected)
        execution.append(setter)
    clears = calls(nodes, "Array_Clear")
    c.require(len(clears) == len(arrays), "Tombstone reset array coverage changed")
    for name in arrays:
        getter = variable(c, nodes, name, "K2Node_VariableGet")
        matching = [clear for clear in clears if c.linked(getter, name, clear, "TargetArray")]
        c.require(len(matching) == 1, f"{name} must feed exactly one clear")
        execution.append(matching[0])
    c.require(not variables(nodes, "ScratchRecoveryFailedV1", "K2Node_VariableSet"), "Reset must preserve recovery failure")
    c.require(not variables(nodes, "ScratchRecoveryDetailV1", "K2Node_VariableSet"), "Reset must preserve recovery detail")
    if paste:
        c.require(not execution[0].pins["execute"].links, "Tombstone reset paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", execution[0], "execute", "Tombstone reset entry changed")
    for left, right in zip(execution, execution[1:]):
        c.require_link(left, "then", right, "execute", "Tombstone reset order changed")


def assert_find(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 7 if paste else 8, "FindRecoveryStringIndexV1", paste)
    setters = variables(nodes, "ScratchRecoverySearchIndexV1", "K2Node_VariableSet")
    reset_matches = [node for node in setters if has_default(c, node, "ScratchRecoverySearchIndexV1", "-1")]
    c.require(len(reset_matches) == 1, "String lookup reset write changed")
    reset = reset_matches[0]
    default(c, reset, "ScratchRecoverySearchIndexV1", "-1")
    strings = variable(c, nodes, "ScratchRecoverySearchStringsV1", "K2Node_VariableGet")
    search = variable(c, nodes, "ScratchRecoverySearchValueV1", "K2Node_VariableGet")
    loop = nodes_of(nodes, "K2Node_MacroInstance")
    c.require(len(loop) == 1 and "ForEachLoop" in loop[0].text, "String lookup loop changed")
    equal = calls(nodes, "EqualEqual_StrStr")
    c.require(len(equal) == 1, "String lookup equality changed")
    branch = nodes_of(nodes, "K2Node_IfThenElse")
    c.require(len(branch) == 1, "String lookup branch changed")
    found = [node for node in setters if node is not reset]
    c.require(len(found) == 1, "String lookup result write changed")
    c.require_link(strings, "ScratchRecoverySearchStringsV1", loop[0], "Array", "String lookup source changed")
    c.require_link(loop[0], "Array Element", equal[0], "A", "String lookup element changed")
    c.require_link(search, "ScratchRecoverySearchValueV1", equal[0], "B", "String lookup value changed")
    c.require_link(loop[0], "Array Index", found[0], "ScratchRecoverySearchIndexV1", "String lookup index changed")
    c.require_link(branch[0], "then", found[0], "execute", "String lookup true path changed")
    if paste:
        c.require(not reset.pins["execute"].links, "String lookup paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", reset, "execute", "String lookup entry changed")


def assert_validate(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 39 if paste else 40, "ValidateRecoveryTombstoneChannelV1", paste)
    c.require(len(calls(nodes, "Trim")) == 1, "Tombstone normalization must use native Trim once")
    c.require(len(calls(nodes, "FindRecoveryStringIndexV1")) == 2, "Tombstone lookup count changed")
    c.require(len(calls(nodes, "Array_Add")) == 3, "Tombstone append count changed")
    c.require(len(calls(nodes, "Array_Clear")) == 1, "Per-channel seen reset changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 4, "Tombstone branch coverage changed")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 1, "Empty-ID guard changed")
    c.require(len(calls(nodes, "EqualEqual_StrStr")) == 1, "Trim equality guard changed")
    c.require(len(calls(nodes, "BooleanAND")) == 1, "Tombstone format conjunction changed")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 2, "Tombstone absence guards changed")

    failed = variables(nodes, "ScratchRecoveryFailedV1", "K2Node_VariableSet")
    detail = variables(nodes, "ScratchRecoveryDetailV1", "K2Node_VariableSet")
    c.require(len(failed) == 2 and len(detail) == 2, "Tombstone failure writes changed")
    for setter in failed:
        default(c, setter, "ScratchRecoveryFailedV1", "true")
    details = {re.search(r'DefaultValue="([^"]+)"', c.pin(node, "ScratchRecoveryDetailV1").body).group(1) for node in detail}
    c.require(details == {"MalformedTombstone", "DuplicateTombstone"}, "Tombstone failure details changed")

    seen_getters = variables(nodes, "ScratchRecoveryChannelSeenIdsV1", "K2Node_VariableGet")
    seen_add = [
        node
        for node in calls(nodes, "Array_Add")
        if any(c.linked(getter, "ScratchRecoveryChannelSeenIdsV1", node, "TargetArray") for getter in seen_getters)
    ]
    c.require(len(seen_add) == 1, "Per-channel uniqueness append changed")
    merged_id_getters = variables(nodes, "ScratchRecoveryTombstoneIdsV1", "K2Node_VariableGet")
    id_add = [
        node
        for node in calls(nodes, "Array_Add")
        if any(c.linked(getter, "ScratchRecoveryTombstoneIdsV1", node, "TargetArray") for getter in merged_id_getters)
    ]
    c.require(len(id_add) == 1, "Merged tombstone ID append changed")
    generations = variable(c, nodes, "ScratchRecoveryTombstoneGenerationsV1", "K2Node_VariableGet")
    generation_add = [node for node in calls(nodes, "Array_Add") if c.linked(generations, "ScratchRecoveryTombstoneGenerationsV1", node, "TargetArray")]
    c.require(len(generation_add) == 1, "Merged tombstone generation append changed")
    channel_generation = variable(c, nodes, "ScratchRecoveryChannelGenerationV1", "K2Node_VariableGet")
    c.require_link(channel_generation, "ScratchRecoveryChannelGenerationV1", generation_add[0], "NewItem", "Tombstone generation provenance changed")
    if paste:
        clear = calls(nodes, "Array_Clear")[0]
        c.require(not clear.pins["execute"].links, "Tombstone validation paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        clear = calls(nodes, "Array_Clear")[0]
        c.require_link(entry, "then", clear, "execute", "Tombstone validation entry changed")


def assert_merge(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 21 if paste else 22, "MergeRecoveryTombstonesV1", paste)
    reset = calls(nodes, "ResetRecoveryTombstonesV1")
    validate = calls(nodes, "ValidateRecoveryTombstoneChannelV1")
    c.require(len(reset) == 1, "Tombstone merge reset changed")
    c.require(len(validate) == 2, "Tombstone channel validation count changed")
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 4, "Tombstone merge branch coverage changed")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 2, "Tombstone slot-presence guards changed")
    c.require(not variables(nodes, "ScratchRecoveryFailedV1", "K2Node_VariableSet"), "Merge must not erase selection failure")
    for source_name, target_name in (
        ("ScratchRecoveryNewestTombstoneFlypathIdsV1", "ScratchRecoveryChannelTombstonesV1"),
        ("ScratchRecoveryOlderTombstoneFlypathIdsV1", "ScratchRecoveryChannelTombstonesV1"),
        ("ScratchRecoveryNewestGenerationV1", "ScratchRecoveryChannelGenerationV1"),
        ("ScratchRecoveryOlderGenerationV1", "ScratchRecoveryChannelGenerationV1"),
    ):
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        targets = variables(nodes, target_name, "K2Node_VariableSet")
        c.require(sum(c.linked(source, source_name, target, target_name) for target in targets) == 1, f"{source_name} staging changed")
    if paste:
        c.require(not reset[0].pins["execute"].links, "Tombstone merge paste root changed")
    else:
        entry = nodes_of(nodes, "K2Node_FunctionEntry")[0]
        c.require_link(entry, "then", reset[0], "execute", "Tombstone merge entry changed")


def merge_model(
    *,
    pre_failed=False,
    pre_detail="",
    newest_slot="EDD_Repository_A",
    newest_generation=2,
    newest=(),
    older_slot="EDD_Repository_B",
    older_generation=1,
    older=(),
):
    ids = []
    generations = []
    if pre_failed:
        return True, pre_detail, ids, generations
    if not newest_slot:
        return False, "", ids, generations
    for slot, generation, channel in (
        (newest_slot, newest_generation, newest),
        (older_slot, older_generation, older),
    ):
        if not slot:
            continue
        seen = set()
        for tombstone in channel:
            if not tombstone or tombstone.strip() != tombstone:
                return True, "MalformedTombstone", ids, generations
            if tombstone in seen:
                return True, "DuplicateTombstone", ids, generations
            seen.add(tombstone)
            if tombstone not in ids:
                ids.append(tombstone)
                generations.append(generation)
    return False, "", ids, generations


def assert_semantics() -> None:
    cases = (
        ({"newest_slot": "", "older_slot": ""}, (False, "", [], [])),
        ({"newest": ("a", "b"), "older_slot": ""}, (False, "", ["a", "b"], [2, 2])),
        ({"newest": ("a",), "older": ("b",)}, (False, "", ["a", "b"], [2, 1])),
        ({"newest": ("a",), "older": ("a", "b")}, (False, "", ["a", "b"], [2, 1])),
        ({"newest": ("a", "a")}, (True, "DuplicateTombstone", ["a"], [2])),
        ({"newest": ("",)}, (True, "MalformedTombstone", [], [])),
        ({"newest": (" a",)}, (True, "MalformedTombstone", [], [])),
        ({"newest": ("a ",)}, (True, "MalformedTombstone", [], [])),
        ({"newest": ("a",), "older": ("b", "b")}, (True, "DuplicateTombstone", ["a", "b"], [2, 1])),
        (
            {"pre_failed": True, "pre_detail": "DivergentEqualGeneration", "newest": ("a",)},
            (True, "DivergentEqualGeneration", [], []),
        ),
    )
    for kwargs, expected in cases:
        actual = merge_model(**kwargs)
        if actual != expected:
            raise AssertionError(f"Tombstone semantic case failed: {kwargs}: {actual} != {expected}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument(
        "--only", choices=("all", "reset", "find", "validate", "merge"), default="all"
    )
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    specs = {
        "reset": ("reset-recovery-tombstones-v1", assert_reset),
        "find": ("find-recovery-string-index-v1", assert_find),
        "validate": ("validate-recovery-tombstone-channel-v1", assert_validate),
        "merge": ("merge-recovery-tombstones-v1", assert_merge),
    }
    selected = specs.items() if args.only == "all" else ((args.only, specs[args.only]),)
    for _, (filename, assertion) in selected:
        assertion(c, c.parse_graph(args.input_dir / f"{filename}{suffix}.eddgraph"), args.paste)
    assert_semantics()
    print("Repository tombstone recovery graph contracts passed")


if __name__ == "__main__":
    main()
