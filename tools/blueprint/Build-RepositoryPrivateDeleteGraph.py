"""Build the owner-only optimistic DeleteFlypathV1 repository transaction."""

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


def error(enc, b, code: str, detail: str, x: int, y: int):
    code_node = b.setter("ResultCodeV1", "string", x, y)
    detail_node = b.setter("ResultDetailV1", "string", x + 256, y)
    enc.set_default(code_node, "ResultCodeV1", code)
    enc.set_default(detail_node, "ResultDetailV1", detail)
    return code_node, detail_node


def specialize_array_remove(node, enc, kind: str) -> None:
    enc.set_pin_type(node, "TargetArray", kind, array=True)


def specialize_array_add(node, enc, kind: str) -> None:
    enc.set_pin_type(node, "TargetArray", kind, array=True)
    enc.set_pin_type(node, "NewItem", kind)


def build(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "DeleteFlypathV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)
    find = b.call("FindRecordIndexV1", 512, 0)
    index = b.getter("ResultRecordIndexV1", "int", 512, 320)
    cache_index = b.setter("ScratchIndexV1", "int", 512, -320)
    clear_result_index = b.setter("ResultRecordIndexV1", "int", 768, -320)
    enc.set_default(clear_result_index, "ResultRecordIndexV1", "-1")
    bp.connect(index, "ResultRecordIndexV1", cache_index, "ScratchIndexV1")
    cached_index = b.getter("ScratchIndexV1", "int", 5888, 400)
    envelopes = b.getter("ActiveRecordEnvelopesV1", "string", 512, 480, array=True)
    index_valid = v.valid_index(
        envelopes,
        "ActiveRecordEnvelopesV1",
        cached_index,
        "ScratchIndexV1",
        "string",
        768,
        320,
    )
    found = v.branch(1024, 0)
    bp.connect(index_valid, "ReturnValue", found, "Condition")

    owners = b.getter("ActiveOwnerAccountIdsV1", "string", 1024, 480, array=True)
    indexed_owner = v.array_item(
        owners,
        "ActiveOwnerAccountIdsV1",
        cached_index,
        "ScratchIndexV1",
        "string",
        1280,
        320,
    )
    requester = b.getter("RequestRequesterAccountIdV1", "string", 1280, 480)
    derived_owner_equal = v.string_math("EqualEqual_StrStr", 1536, 320)
    derived_owner_branch = v.branch(1792, 0)
    bp.connect(indexed_owner, "Output", derived_owner_equal, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", derived_owner_equal, "B")
    bp.connect(derived_owner_equal, "ReturnValue", derived_owner_branch, "Condition")

    indexed_envelope = v.array_item(
        envelopes,
        "ActiveRecordEnvelopesV1",
        cached_index,
        "ScratchIndexV1",
        "string",
        1792,
        480,
    )
    stage_envelope = b.setter("ScratchEncodedRecordV1", "string", 2048, 0)
    decode = b.call("DecodeRecordV1", 2304, 0)
    decoded = b.getter("ScratchValidV1", "bool", 2304, 320)
    decoded_branch = v.branch(2560, 0)
    validate_current = b.call("ValidateRecordV1", 2816, 0)
    current_valid = b.getter("ScratchValidV1", "bool", 2816, 320)
    current_valid_branch = v.branch(3072, 0)
    bp.connect(indexed_envelope, "Output", stage_envelope, "ScratchEncodedRecordV1")
    bp.connect(decoded, "ScratchValidV1", decoded_branch, "Condition")
    bp.connect(current_valid, "ScratchValidV1", current_valid_branch, "Condition")

    record_id = b.getter("ScratchRecordFlypathIdV1", "string", 3072, 400)
    request_id = b.getter("RequestFlypathIdV1", "string", 3072, 544)
    actual_id_equal = v.string_math("EqualEqual_StrStr", 3328, 400)
    record_owner = b.getter("ScratchRecordOwnerAccountIdV1", "string", 3072, 688)
    actual_owner_equal = v.string_math("EqualEqual_StrStr", 3328, 688)
    identity_valid = v.bool_math("BooleanAND", 3584, 480)
    identity_branch = v.branch(3840, 0)
    bp.connect(record_id, "ScratchRecordFlypathIdV1", actual_id_equal, "A")
    bp.connect(request_id, "RequestFlypathIdV1", actual_id_equal, "B")
    bp.connect(record_owner, "ScratchRecordOwnerAccountIdV1", actual_owner_equal, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", actual_owner_equal, "B")
    bp.connect(actual_id_equal, "ReturnValue", identity_valid, "A")
    bp.connect(actual_owner_equal, "ReturnValue", identity_valid, "B")
    bp.connect(identity_valid, "ReturnValue", identity_branch, "Condition")

    current_revision = b.getter("ScratchRecordDraftRevisionNumberV1", "int", 3840, 400)
    expected_revision = b.getter("RequestExpectedRevisionV1", "int", 3840, 544)
    revision_equal = v.int_math("EqualEqual_IntInt", 4096, 400)
    revision_branch = v.branch(4352, 0)
    bp.connect(current_revision, "ScratchRecordDraftRevisionNumberV1", revision_equal, "A")
    bp.connect(expected_revision, "RequestExpectedRevisionV1", revision_equal, "B")
    bp.connect(revision_equal, "ReturnValue", revision_branch, "Condition")

    conflict_revision = b.setter("ResultCurrentRevisionV1", "int", 4608, -320)
    conflict_has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", 4864, -320)
    enc.set_default(conflict_has_revision, "ResultHasCurrentRevisionV1", "true")
    bp.connect(
        current_revision,
        "ScratchRecordDraftRevisionNumberV1",
        conflict_revision,
        "ResultCurrentRevisionV1",
    )

    prepare = b.call("PreparePersistenceCandidateV1", 4864, 0)

    candidate_records = b.getter(
        "CandidateRecordEnvelopesV1", "string", 4864, 400, array=True
    )
    remove_candidate_record = b.add("remove_candidate_record", "array_remove", 5120, 0)
    specialize_array_remove(remove_candidate_record, enc, "string")
    bp.connect(
        candidate_records,
        "CandidateRecordEnvelopesV1",
        remove_candidate_record,
        "TargetArray",
    )
    bp.connect(cached_index, "ScratchIndexV1", remove_candidate_record, "IndexToRemove")

    candidate_tombstones = b.getter(
        "CandidateTombstoneFlypathIdsV1", "string", 5120, 400, array=True
    )
    add_tombstone = b.add("add_candidate_tombstone", "array_add", 5376, 0)
    specialize_array_add(add_tombstone, enc, "string")
    bp.connect(
        candidate_tombstones,
        "CandidateTombstoneFlypathIdsV1",
        add_tombstone,
        "TargetArray",
    )
    bp.connect(request_id, "RequestFlypathIdV1", add_tombstone, "NewItem")

    persist = b.call("PersistRepositoryV1", 5632, 0)
    committed = b.getter("ScratchPersistenceCommitSavedV1", "bool", 5632, 320)
    committed_branch = v.branch(5888, 0)
    bp.connect(committed, "ScratchPersistenceCommitSavedV1", committed_branch, "Condition")

    active_specs = (
        ("ActiveFlypathIdsV1", "string"),
        ("ActiveOwnerAccountIdsV1", "string"),
        ("ActiveVisibilitiesV1", "string"),
        ("ActiveUpdatedUtcV1", "string"),
    )
    active_removes = []
    for offset, (name, kind) in enumerate(active_specs):
        x = 6144 + offset * 512
        getter = b.getter(name, kind, x, 400, array=True)
        remove = b.add(f"remove_{name}", "array_remove", x + 256, 0)
        specialize_array_remove(remove, enc, kind)
        bp.connect(getter, name, remove, "TargetArray")
        bp.connect(cached_index, "ScratchIndexV1", remove, "IndexToRemove")
        active_removes.append(remove)

    not_found = error(enc, b, "NotFound", "FlypathNotFound", 1280, -320)
    forbidden = error(enc, b, "Forbidden", "OwnerRequired", 2048, -320)
    decode_failed = error(enc, b, "ValidationFailed", "StoredRecordDecodeFailed", 2816, -320)
    stored_invalid = error(enc, b, "ValidationFailed", "StoredRecordInvalid", 3328, -320)
    identity_mismatch = error(enc, b, "ValidationFailed", "StoredRecordIndexMismatch", 4096, -320)
    revision_conflict = error(
        enc, b, "RevisionConflict", "ExpectedRevisionMismatch", 5120, -320
    )

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", find, "execute")
    bp.connect(find, "then", cache_index, "execute")
    bp.connect(cache_index, "then", clear_result_index, "execute")
    bp.connect(clear_result_index, "then", found, "execute")
    bp.connect(found, "else", not_found[0], "execute")
    bp.connect(not_found[0], "then", not_found[1], "execute")
    bp.connect(found, "then", derived_owner_branch, "execute")
    bp.connect(derived_owner_branch, "else", forbidden[0], "execute")
    bp.connect(forbidden[0], "then", forbidden[1], "execute")
    bp.connect(derived_owner_branch, "then", stage_envelope, "execute")
    bp.connect(stage_envelope, "then", decode, "execute")
    bp.connect(decode, "then", decoded_branch, "execute")
    bp.connect(decoded_branch, "else", decode_failed[0], "execute")
    bp.connect(decode_failed[0], "then", decode_failed[1], "execute")
    bp.connect(decoded_branch, "then", validate_current, "execute")
    bp.connect(validate_current, "then", current_valid_branch, "execute")
    bp.connect(current_valid_branch, "else", stored_invalid[0], "execute")
    bp.connect(stored_invalid[0], "then", stored_invalid[1], "execute")
    bp.connect(current_valid_branch, "then", identity_branch, "execute")
    bp.connect(identity_branch, "else", identity_mismatch[0], "execute")
    bp.connect(identity_mismatch[0], "then", identity_mismatch[1], "execute")
    bp.connect(identity_branch, "then", revision_branch, "execute")
    bp.connect(revision_branch, "else", conflict_revision, "execute")
    bp.connect(conflict_revision, "then", conflict_has_revision, "execute")
    bp.connect(conflict_has_revision, "then", revision_conflict[0], "execute")
    bp.connect(revision_conflict[0], "then", revision_conflict[1], "execute")
    bp.connect(revision_branch, "then", prepare, "execute")
    bp.connect(prepare, "then", remove_candidate_record, "execute")
    bp.connect(remove_candidate_record, "then", add_tombstone, "execute")
    bp.connect(add_tombstone, "then", persist, "execute")
    bp.connect(persist, "then", committed_branch, "execute")
    bp.connect(committed_branch, "then", active_removes[0], "execute")
    for before, after in zip(active_removes, active_removes[1:]):
        bp.connect(before, "then", after, "execute")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()

    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_private_delete_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_private_delete_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    edit_forms = bp.read_blocks(
        args.project_root
        / "tools"
        / "blueprint"
        / "templates"
        / "waypoint-edit-node-forms.eddgraph"
    )
    capture_forms = bp.read_blocks(
        args.project_root
        / "tools"
        / "blueprint"
        / "templates"
        / "waypoint-capture-node-forms.eddgraph"
    )
    templates["array_remove"] = bp.find_block(edit_forms, r'MemberName="Array_Remove"')
    templates["array_add"] = bp.find_block(capture_forms, r'MemberName="Array_Add"')

    nodes = build(bp, enc, validation, templates)
    enc.write(nodes, args.output_dir / "delete-flypath-v1.eddgraph", paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / "delete-flypath-v1-paste.eddgraph",
            paste=True,
        )


if __name__ == "__main__":
    main()
