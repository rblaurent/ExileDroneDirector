"""Semantic contracts for pure repository persistence-state Blueprint graphs."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_persistence_state_contract_base", path)
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


def one(c, nodes, marker: str):
    matches = nodes_with(nodes, marker)
    c.require(len(matches) == 1, f"Expected one {marker}; found {len(matches)}")
    return matches[0]


def calls(nodes, name: str):
    return [
        node
        for node in nodes.values()
        if (
            "K2Node_CallFunction" in node.node_class
            or "K2Node_CallArrayFunction" in node.node_class
        )
        and f'MemberName="{name}"' in node.text
    ]


def variable(nodes, name: str, node_class: str):
    matches = [
        node
        for node in nodes.values()
        if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {node_class} for {name}; found {len(matches)}")
    return matches[0]


def default(c, node, pin_name: str, expected: str) -> None:
    body = c.pin(node, pin_name).body
    if expected == "":
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', body)
        c.require(match is None or match.group(1) == "", f"{pin_name} must default empty")
    else:
        c.require(
            re.search(rf'(?:^|,)DefaultValue="{re.escape(expected)}"(?:,|$)', body) is not None,
            f"{pin_name} default changed",
        )


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
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), f"{function}: entry count changed")
    if not paste:
        c.require(f'MemberName="{function}"' in entries[0].text, f"{function}: wrong entry")
    text = "\n".join(node.text for node in nodes.values())
    c.require("bOrphanedPin=True" not in text, f"{function}: orphaned pin")


def assert_reset(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 24 if paste else 25, "ResetRepositoryStateV1", paste)
    scalar_defaults = (
        ("RepositoryLoadedV1", "false"),
        ("ActiveGenerationV1", "0"),
        ("ActiveSlotV1", ""),
        ("CandidateGenerationV1", "0"),
        ("CandidateTargetSlotV1", ""),
        ("CandidateSnapshotHashV1", ""),
        ("ScratchStorageAHeaderValidV1", "false"),
        ("ScratchStorageBHeaderValidV1", "false"),
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
    for name, expected in scalar_defaults:
        setter = variable(nodes, name, "K2Node_VariableSet")
        default(c, setter, name, expected)
        chain.append(setter)
    clears = calls(nodes, "Array_Clear")
    c.require(len(clears) == len(arrays), "Reset must clear every active/candidate array")
    for name in arrays:
        getter = variable(nodes, name, "K2Node_VariableGet")
        matching = [node for node in clears if c.linked(getter, name, node, "TargetArray")]
        c.require(len(matching) == 1, f"{name} must feed exactly one clear")
        chain.append(matching[0])
    if paste:
        c.require(not chain[0].pins["execute"].links, "Reset paste root changed")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="ResetRepositoryStateV1")')
        c.require_link(entry, "then", chain[0], "execute", "Reset entry changed")
    for left, right in zip(chain, chain[1:]):
        c.require_link(left, "then", right, "execute", "Reset order changed")


def assert_headers(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 30 if paste else 31, "ValidateStorageHeadersV1", paste)
    c.require(len(calls(nodes, "EqualEqual_BoolBool")) == 4, "Exists/committed guards changed")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 2, "Schema guards changed")
    c.require(len(calls(nodes, "Greater_IntInt")) == 2, "Generation guards changed")
    c.require(len(calls(nodes, "EqualEqual_StrStr")) == 2, "Reserved hash guards changed")
    c.require(len(calls(nodes, "BooleanAND")) == 8, "Header conjunction coverage changed")
    a_set = variable(nodes, "ScratchStorageAHeaderValidV1", "K2Node_VariableSet")
    b_set = variable(nodes, "ScratchStorageBHeaderValidV1", "K2Node_VariableSet")
    for prefix, setter in (("A", a_set), ("B", b_set)):
        for field in ("Exists", "SchemaVersion", "Generation", "Committed", "SnapshotHash"):
            variable(nodes, f"ScratchStorage{prefix}{field}V1", "K2Node_VariableGet")
        producers = [
            node for node in calls(nodes, "BooleanAND")
            if c.linked(node, "ReturnValue", setter, f"ScratchStorage{prefix}HeaderValidV1")
        ]
        c.require(len(producers) == 1, f"Storage {prefix} final header conjunction changed")
    if paste:
        c.require(not a_set.pins["execute"].links, "Header paste root changed")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="ValidateStorageHeadersV1")')
        c.require_link(entry, "then", a_set, "execute", "Header entry changed")
    c.require_link(a_set, "then", b_set, "execute", "Header commit order changed")


def assert_prepare(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 13 if paste else 14, "PreparePersistenceCandidateV1", paste)
    active_records = variable(nodes, "ActiveRecordEnvelopesV1", "K2Node_VariableGet")
    candidate_records = variable(nodes, "CandidateRecordEnvelopesV1", "K2Node_VariableSet")
    active_tombstones = variable(nodes, "ActiveTombstoneFlypathIdsV1", "K2Node_VariableGet")
    candidate_tombstones = variable(nodes, "CandidateTombstoneFlypathIdsV1", "K2Node_VariableSet")
    c.require_link(active_records, "ActiveRecordEnvelopesV1", candidate_records, "CandidateRecordEnvelopesV1", "Candidate records must snapshot authority")
    c.require_link(active_tombstones, "ActiveTombstoneFlypathIdsV1", candidate_tombstones, "CandidateTombstoneFlypathIdsV1", "Candidate tombstones must snapshot authority")
    active_generation = variable(nodes, "ActiveGenerationV1", "K2Node_VariableGet")
    increment = one(c, nodes, 'MemberName="Add_IntInt"')
    default(c, increment, "B", "1")
    generation = variable(nodes, "CandidateGenerationV1", "K2Node_VariableSet")
    c.require_link(active_generation, "ActiveGenerationV1", increment, "A", "Candidate generation source changed")
    c.require_link(increment, "ReturnValue", generation, "CandidateGenerationV1", "Candidate generation increment changed")
    digest = variable(nodes, "CandidateSnapshotHashV1", "K2Node_VariableSet")
    default(c, digest, "CandidateSnapshotHashV1", "")
    slot = variable(nodes, "ActiveSlotV1", "K2Node_VariableGet")
    is_a = one(c, nodes, 'MemberName="EqualEqual_StrStr"')
    default(c, is_a, "B", "EDD_Repository_A")
    branches = nodes_of(nodes, "K2Node_IfThenElse")
    c.require(len(branches) == 1, "Candidate inactive-slot branch count changed")
    branch = branches[0]
    c.require_link(slot, "ActiveSlotV1", is_a, "A", "Inactive slot comparison changed")
    c.require_link(is_a, "ReturnValue", branch, "Condition", "Inactive slot branch changed")
    targets = nodes_with(nodes, 'VariableReference=(MemberName="CandidateTargetSlotV1"')
    c.require(len(targets) == 2, "Candidate must own one setter per inactive-slot branch")
    by_default = {}
    for target in targets:
        body = c.pin(target, "CandidateTargetSlotV1").body
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"(?:,|$)', body)
        c.require(match is not None, "Candidate target slot default missing")
        by_default[match.group(1)] = target
    c.require(set(by_default) == {"EDD_Repository_A", "EDD_Repository_B"}, "Candidate target defaults changed")
    c.require_link(branch, "then", by_default["EDD_Repository_B"], "execute", "Active A must target B")
    c.require_link(branch, "else", by_default["EDD_Repository_A"], "execute", "Empty/B authority must target A")
    chain = (candidate_records, candidate_tombstones, generation, digest, branch)
    if paste:
        c.require(not chain[0].pins["execute"].links, "Prepare paste root changed")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="PreparePersistenceCandidateV1")')
        c.require_link(entry, "then", chain[0], "execute", "Prepare entry changed")
    for left, right in zip(chain, chain[1:]):
        c.require_link(left, "then", right, "execute", "Prepare transaction order changed")


def assert_commit(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 9 if paste else 10, "CommitPersistenceCandidateV1", paste)
    pairs = (
        ("CandidateRecordEnvelopesV1", "ActiveRecordEnvelopesV1"),
        ("CandidateTombstoneFlypathIdsV1", "ActiveTombstoneFlypathIdsV1"),
        ("CandidateGenerationV1", "ActiveGenerationV1"),
        ("CandidateTargetSlotV1", "ActiveSlotV1"),
    )
    chain = []
    for source_name, target_name in pairs:
        source = variable(nodes, source_name, "K2Node_VariableGet")
        target = variable(nodes, target_name, "K2Node_VariableSet")
        c.require_link(source, source_name, target, target_name, f"{target_name} commit source changed")
        chain.append(target)
    loaded = variable(nodes, "RepositoryLoadedV1", "K2Node_VariableSet")
    default(c, loaded, "RepositoryLoadedV1", "true")
    chain.append(loaded)
    if paste:
        c.require(not chain[0].pins["execute"].links, "Commit paste root changed")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="CommitPersistenceCandidateV1")')
        c.require_link(entry, "then", chain[0], "execute", "Commit entry changed")
    for left, right in zip(chain, chain[1:]):
        c.require_link(left, "then", right, "execute", "Authoritative commit order changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    specs = (
        ("reset-repository-state-v1", assert_reset),
        ("validate-storage-headers-v1", assert_headers),
        ("prepare-persistence-candidate-v1", assert_prepare),
        ("commit-persistence-candidate-v1", assert_commit),
    )
    for filename, assertion in specs:
        assertion(c, c.parse_graph(args.input_dir / f"{filename}{suffix}.eddgraph"), args.paste)
    print("Repository persistence state graph contracts passed")


if __name__ == "__main__":
    main()
