"""Structural and executable semantic contracts for the two-phase writer."""

from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_writer_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def marked(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def one(c, nodes, marker: str):
    matches = marked(nodes, marker)
    c.require(len(matches) == 1, f"Expected one {marker}; found {len(matches)}")
    return matches[0]


def calls(nodes, name: str):
    return [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and f'MemberName="{name}"' in node.text]


def variable(c, nodes, name: str, node_class: str):
    matches = [node for node in nodes.values() if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text]
    c.require(len(matches) == 1, f"Expected one {node_class} for {name}; found {len(matches)}")
    return matches[0]


def storage_property(c, nodes, name: str):
    matches = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and "SG_EDD_RepositoryStorage" in node.text and f'MemberName="{name}"' in node.text]
    c.require(len(matches) == 1, f"Expected one storage setter for {name}; found {len(matches)}")
    return matches[0]


def default(c, node, pin_name: str, expected: str) -> None:
    body = c.pin(node, pin_name).body
    c.require(re.search(rf'(?:^|,)DefaultValue="{re.escape(expected)}"(?:,|$)', body) is not None, f"{pin_name} default changed")


def assert_closed(c, nodes, expected: int, function: str, paste: bool):
    c.require(len(nodes) == expected, f"{function}: expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"{function}: external links {sorted(external)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if paste else 1), f"{function}: entry count changed")
    if not paste:
        c.require(f'MemberName="{function}"' in entries[0].text, f"{function}: wrong entry")
    c.require("bOrphanedPin=True" not in "\n".join(node.text for node in nodes.values()), f"{function}: orphaned pin")
    return entries[0] if entries else None


def assert_failure(c, nodes, branch, detail: str):
    code = variable(c, nodes, "ResultCodeV1", "K2Node_VariableSet")
    message = variable(c, nodes, "ResultDetailV1", "K2Node_VariableSet")
    default(c, code, "ResultCodeV1", "PersistenceUnavailable")
    default(c, message, "ResultDetailV1", detail)
    c.require_link(branch, "else", code, "execute", f"{detail}: false branch changed")
    c.require_link(code, "then", message, "execute", f"{detail}: result order changed")


def assert_reset(c, nodes, paste):
    entry = assert_closed(c, nodes, 4 if paste else 5, "ResetPersistenceWriteV1", paste)
    reset = one(c, nodes, 'MemberName="ResetRepositoryResultV1"')
    chain = [reset]
    for name in ("ScratchPersistenceStorageCreatedV1", "ScratchPersistenceStageSavedV1", "ScratchPersistenceCommitSavedV1"):
        setter = variable(c, nodes, name, "K2Node_VariableSet")
        default(c, setter, name, "false")
        chain.append(setter)
    if paste:
        c.require(not reset.pins["execute"].links, "Reset paste root changed")
    else:
        c.require_link(entry, "then", reset, "execute", "Reset entry changed")
    for left, right in zip(chain, chain[1:]):
        c.require_link(left, "then", right, "execute", "Reset writer order changed")


def assert_build(c, nodes, paste):
    entry = assert_closed(c, nodes, 18 if paste else 19, "BuildPersistenceWriteStorageV1", paste)
    create = one(c, nodes, 'MemberName="CreateSaveGameObject"')
    c.require("SG_EDD_RepositoryStorage_C" in c.pin(create, "SaveGameClass").body, "Create class changed")
    storage = variable(c, nodes, "ScratchWriteStorageV1", "K2Node_VariableSet")
    valid = one(c, nodes, 'MemberName="IsValid"')
    created = variable(c, nodes, "ScratchPersistenceStorageCreatedV1", "K2Node_VariableSet")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 1, "Build validity branch count changed")
    branch = branches[0]
    c.require_link(create, "ReturnValue", storage, "ScratchWriteStorageV1", "Created storage must be retained")
    c.require_link(create, "ReturnValue", valid, "Object", "Created storage must be validated")
    c.require_link(valid, "ReturnValue", created, "ScratchPersistenceStorageCreatedV1", "Validity result staging changed")
    c.require_link(created, "Output_Get", branch, "Condition", "Storage creation guard changed")
    if paste:
        c.require(not create.pins["execute"].links, "Build paste root changed")
    else:
        c.require_link(entry, "then", create, "execute", "Build entry changed")
    c.require_link(create, "then", storage, "execute", "Create/store order changed")
    c.require_link(storage, "then", created, "execute", "Store/validity order changed")
    c.require_link(created, "then", branch, "execute", "Validity branch order changed")

    storage_get = variable(c, nodes, "ScratchWriteStorageV1", "K2Node_VariableGet")
    fields = ["RepositorySchemaVersion", "Generation", "Committed", "SnapshotHash", "RecordEnvelopes", "TombstoneFlypathIds"]
    setters = [storage_property(c, nodes, name) for name in fields]
    for setter, name in zip(setters, fields):
        c.require_link(storage_get, "ScratchWriteStorageV1", setter, "self", f"{name}: storage target changed")
    default(c, setters[0], "RepositorySchemaVersion", "1")
    default(c, setters[2], "Committed", "false")
    sources = (
        ("CandidateGenerationV1", setters[1], "Generation"),
        ("CandidateSnapshotHashV1", setters[3], "SnapshotHash"),
        ("CandidateRecordEnvelopesV1", setters[4], "RecordEnvelopes"),
        ("CandidateTombstoneFlypathIdsV1", setters[5], "TombstoneFlypathIds"),
    )
    for source_name, setter, pin in sources:
        source = variable(c, nodes, source_name, "K2Node_VariableGet")
        c.require_link(source, source_name, setter, pin, f"{pin}: candidate source changed")
    c.require_link(branch, "then", setters[0], "execute", "Canonical storage population root changed")
    for left, right in zip(setters, setters[1:]):
        c.require_link(left, "then", right, "execute", "Canonical storage field order changed")
    assert_failure(c, nodes, branch, "CreateStorageFailed")


def assert_stage(c, nodes, paste):
    entry = assert_closed(c, nodes, 7 if paste else 8, "StagePersistenceWriteV1", paste)
    storage = variable(c, nodes, "ScratchWriteStorageV1", "K2Node_VariableGet")
    slot = variable(c, nodes, "CandidateTargetSlotV1", "K2Node_VariableGet")
    save = one(c, nodes, 'MemberName="SaveGameToSlot"')
    saved = variable(c, nodes, "ScratchPersistenceStageSavedV1", "K2Node_VariableSet")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 1, "Stage branch count changed")
    branch = branches[0]
    c.require_link(storage, "ScratchWriteStorageV1", save, "SaveGameObject", "Stage object changed")
    c.require_link(slot, "CandidateTargetSlotV1", save, "SlotName", "Stage slot changed")
    c.require_link(save, "ReturnValue", saved, "ScratchPersistenceStageSavedV1", "Stage result changed")
    c.require_link(saved, "Output_Get", branch, "Condition", "Stage guard changed")
    if paste:
        c.require(not save.pins["execute"].links, "Stage paste root changed")
    else:
        c.require_link(entry, "then", save, "execute", "Stage entry changed")
    c.require_link(save, "then", saved, "execute", "Stage result order changed")
    c.require_link(saved, "then", branch, "execute", "Stage branch order changed")
    assert_failure(c, nodes, branch, "StageWriteFailed")


def assert_commit(c, nodes, paste):
    entry = assert_closed(c, nodes, 9 if paste else 10, "CommitPersistenceWriteV1", paste)
    storage = variable(c, nodes, "ScratchWriteStorageV1", "K2Node_VariableGet")
    mark = storage_property(c, nodes, "Committed")
    default(c, mark, "Committed", "true")
    slot = variable(c, nodes, "CandidateTargetSlotV1", "K2Node_VariableGet")
    save = one(c, nodes, 'MemberName="SaveGameToSlot"')
    saved = variable(c, nodes, "ScratchPersistenceCommitSavedV1", "K2Node_VariableSet")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 1, "Commit branch count changed")
    branch = branches[0]
    promote = one(c, nodes, 'MemberName="CommitPersistenceCandidateV1"')
    c.require_link(storage, "ScratchWriteStorageV1", mark, "self", "Commit marker target changed")
    c.require_link(storage, "ScratchWriteStorageV1", save, "SaveGameObject", "Commit object changed")
    c.require_link(slot, "CandidateTargetSlotV1", save, "SlotName", "Commit slot changed")
    c.require_link(save, "ReturnValue", saved, "ScratchPersistenceCommitSavedV1", "Commit result changed")
    c.require_link(saved, "Output_Get", branch, "Condition", "Commit guard changed")
    c.require_link(branch, "then", promote, "execute", "Authority promotion must require committed save")
    if paste:
        c.require(not mark.pins["execute"].links, "Commit paste root changed")
    else:
        c.require_link(entry, "then", mark, "execute", "Commit entry changed")
    c.require_link(mark, "then", save, "execute", "Committed marker must precede rewrite")
    c.require_link(save, "then", saved, "execute", "Commit result order changed")
    c.require_link(saved, "then", branch, "execute", "Commit branch order changed")
    assert_failure(c, nodes, branch, "CommitWriteFailed")


def assert_coordinator(c, nodes, paste):
    entry = assert_closed(c, nodes, 8 if paste else 9, "PersistRepositoryV1", paste)
    reset = one(c, nodes, 'MemberName="ResetPersistenceWriteV1"')
    build = one(c, nodes, 'MemberName="BuildPersistenceWriteStorageV1"')
    stage = one(c, nodes, 'MemberName="StagePersistenceWriteV1"')
    commit = one(c, nodes, 'MemberName="CommitPersistenceWriteV1"')
    c.require(not calls(nodes, "PreparePersistenceCandidateV1"), "Persist must not overwrite caller-mutated candidate state")
    created = variable(c, nodes, "ScratchPersistenceStorageCreatedV1", "K2Node_VariableGet")
    staged = variable(c, nodes, "ScratchPersistenceStageSavedV1", "K2Node_VariableGet")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(branches) == 2, "Coordinator guard count changed")
    created_branch = [node for node in branches if c.linked(created, "ScratchPersistenceStorageCreatedV1", node, "Condition")]
    staged_branch = [node for node in branches if c.linked(staged, "ScratchPersistenceStageSavedV1", node, "Condition")]
    c.require(len(created_branch) == 1 and len(staged_branch) == 1, "Coordinator guards changed")
    if paste:
        c.require(not reset.pins["execute"].links, "Coordinator paste root changed")
    else:
        c.require_link(entry, "then", reset, "execute", "Coordinator entry changed")
    c.require_link(reset, "then", build, "execute", "Reset/build order changed")
    c.require_link(build, "then", created_branch[0], "execute", "Build guard order changed")
    c.require_link(created_branch[0], "then", stage, "execute", "Stage must require valid storage")
    c.require_link(stage, "then", staged_branch[0], "execute", "Stage guard order changed")
    c.require_link(staged_branch[0], "then", commit, "execute", "Commit must require stage success")


def simulate(active, candidate, *, create=True, stage=True, commit=True):
    state = {"active": copy.deepcopy(active), "flags": [False, False, False], "writes": [], "code": "Success", "detail": ""}
    state["flags"][0] = create
    if not create:
        state.update(code="PersistenceUnavailable", detail="CreateStorageFailed")
        return state
    storage = copy.deepcopy(candidate)
    storage["committed"] = False
    state["flags"][1] = stage
    if not stage:
        state.update(code="PersistenceUnavailable", detail="StageWriteFailed")
        return state
    state["writes"].append(copy.deepcopy(storage))
    storage["committed"] = True
    state["flags"][2] = commit
    if not commit:
        state.update(code="PersistenceUnavailable", detail="CommitWriteFailed")
        return state
    state["writes"].append(copy.deepcopy(storage))
    state["active"] = copy.deepcopy(candidate)
    state["active"]["loaded"] = True
    return state


def assert_semantics():
    active = {"generation": 4, "slot": "EDD_Repository_A", "records": ["old"], "tombstones": []}
    candidate = {"generation": 5, "slot": "EDD_Repository_B", "records": ["new"], "tombstones": ["gone"], "hash": ""}
    for kwargs, detail in (({"create": False}, "CreateStorageFailed"), ({"stage": False}, "StageWriteFailed"), ({"commit": False}, "CommitWriteFailed")):
        result = simulate(active, candidate, **kwargs)
        assert result["active"] == active, f"{detail} changed authority"
        assert result["detail"] == detail and result["code"] == "PersistenceUnavailable"
    stage_failure = simulate(active, candidate, stage=False)
    assert stage_failure["writes"] == [], "Failed stage must publish no accepted write"
    commit_failure = simulate(active, candidate, commit=False)
    assert len(commit_failure["writes"]) == 1 and commit_failure["writes"][0]["committed"] is False
    success = simulate(active, candidate)
    assert [write["committed"] for write in success["writes"]] == [False, True]
    assert success["writes"][0]["slot"] == success["writes"][1]["slot"] == "EDD_Repository_B"
    assert success["active"]["records"] == ["new"] and success["active"]["loaded"] is True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    specs = (
        ("reset-persistence-write-v1", assert_reset),
        ("build-persistence-write-storage-v1", assert_build),
        ("stage-persistence-write-v1", assert_stage),
        ("commit-persistence-write-v1", assert_commit),
        ("persist-repository-v1", assert_coordinator),
    )
    for filename, assertion in specs:
        assertion(c, c.parse_graph(args.input_dir / f"{filename}{suffix}.eddgraph"), args.paste)
    assert_semantics()
    print("Repository persistence writer graph contracts passed")


if __name__ == "__main__":
    main()
