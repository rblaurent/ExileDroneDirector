"""Build the owner-only optimistic SaveDraftV1 repository transaction."""

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


def specialize_array_set(enc, node, kind: str) -> None:
    enc.set_pin_type(node, "TargetArray", kind, array=True)
    enc.set_pin_type(node, "Item", kind)
    enc.set_default(node, "bSizeToFit", "false")


def build(bp, enc, validation, create, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "SaveDraftV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)
    find = b.call("FindRecordIndexV1", 512, 0)
    index = b.getter("ResultRecordIndexV1", "int", 512, 320)
    envelopes = b.getter("ActiveRecordEnvelopesV1", "string", 512, 480, array=True)
    index_valid = v.valid_index(
        envelopes, "ActiveRecordEnvelopesV1", index, "ResultRecordIndexV1", "string", 768, 320
    )
    found = v.branch(1024, 0)
    bp.connect(index_valid, "ReturnValue", found, "Condition")

    owners = b.getter("ActiveOwnerAccountIdsV1", "string", 1024, 480, array=True)
    indexed_owner = v.array_item(
        owners, "ActiveOwnerAccountIdsV1", index, "ResultRecordIndexV1", "string", 1280, 320
    )
    requester = b.getter("RequestRequesterAccountIdV1", "string", 1280, 480)
    derived_owner_equal = v.string_math("EqualEqual_StrStr", 1536, 320)
    derived_owner_branch = v.branch(1792, 0)
    bp.connect(indexed_owner, "Output", derived_owner_equal, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", derived_owner_equal, "B")
    bp.connect(derived_owner_equal, "ReturnValue", derived_owner_branch, "Condition")

    indexed_envelope = v.array_item(
        envelopes, "ActiveRecordEnvelopesV1", index, "ResultRecordIndexV1", "string", 1792, 480
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
    bp.connect(current_revision, "ScratchRecordDraftRevisionNumberV1", conflict_revision, "ResultCurrentRevisionV1")

    now, _trim_now, now_valid = create.trimmed_nonempty(
        v, templates, "RequestNowUtcV1", 4352, 400
    )
    request_valid_branch = v.branch(5120, 0)
    bp.connect(now_valid, "ReturnValue", request_valid_branch, "Condition")

    request_document = b.getter("RequestDraftDocumentV1", "document", 5120, 400)
    split_document = b.add("split_request_document", "break_document", 5376, 400)
    bp.connect(request_document, "RequestDraftDocumentV1", split_document, "ST_EDD_FlypathDocument")
    waypoint_count = v.length(split_document, enc.DOC_WAYPOINTS, "waypoint", 5632, 400)
    max_waypoints = b.getter("MaxWaypointsPerPathV1", "int", 5632, 544)
    waypoint_limit_ok = v.int_math("LessEqual_IntInt", 5888, 400)
    waypoint_limit_branch = v.branch(6144, 0)
    bp.connect(waypoint_count, "ReturnValue", waypoint_limit_ok, "A")
    bp.connect(max_waypoints, "MaxWaypointsPerPathV1", waypoint_limit_ok, "B")
    bp.connect(waypoint_limit_ok, "ReturnValue", waypoint_limit_branch, "Condition")

    record_region = b.getter("ScratchRecordRegionIdV1", "string", 6144, 400)
    region_equal = v.string_math("EqualEqual_StrStr", 6400, 400)
    region_branch = v.branch(6656, 0)
    bp.connect(record_region, "ScratchRecordRegionIdV1", region_equal, "A")
    bp.connect(split_document, enc.DOC_REGION, region_equal, "B")
    bp.connect(region_equal, "ReturnValue", region_branch, "Condition")

    next_revision = v.int_math("Add_IntInt", 6656, 400, b_default="1")
    bp.connect(current_revision, "ScratchRecordDraftRevisionNumberV1", next_revision, "A")
    make_document = b.add("make_saved_document", "make_document", 6912, 400)
    for pin in (
        enc.DOC_SCHEMA,
        enc.DOC_ENGINE,
        enc.DOC_REGION,
        enc.DOC_DURATION,
        enc.DOC_PROFILE,
        enc.DOC_WAYPOINTS,
        enc.DOC_SEGMENTS,
    ):
        bp.connect(split_document, pin, make_document, pin)
    bp.connect(next_revision, "ReturnValue", make_document, enc.DOC_REVISION)
    enc.set_default(make_document, enc.DOC_HASH, "")

    stage_document = b.setter("ScratchRecordDraftDocumentV1", "document", 7168, 0)
    stage_revision = b.setter("ScratchRecordDraftRevisionNumberV1", "int", 7424, 0)
    stage_updated = b.setter("ScratchRecordUpdatedUtcV1", "string", 7680, 0)
    bp.connect(make_document, "ST_EDD_FlypathDocument", stage_document, "ScratchRecordDraftDocumentV1")
    bp.connect(next_revision, "ReturnValue", stage_revision, "ScratchRecordDraftRevisionNumberV1")
    bp.connect(now, "RequestNowUtcV1", stage_updated, "ScratchRecordUpdatedUtcV1")

    validate_updated = b.call("ValidateRecordV1", 7936, 0)
    updated_valid = b.getter("ScratchValidV1", "bool", 7936, 320)
    updated_valid_branch = v.branch(8192, 0)
    bp.connect(updated_valid, "ScratchValidV1", updated_valid_branch, "Condition")
    encode = b.call("EncodeRecordV1", 8448, 0)
    encoded = b.getter("ScratchEncodedRecordV1", "string", 8448, 320)
    encoded_length = create.string_len(v, encoded, "ScratchEncodedRecordV1", 8704, 320)
    max_size = b.getter("MaxSerializedBytesV1", "int", 8704, 480)
    size_ok = v.int_math("LessEqual_IntInt", 8960, 320)
    size_branch = v.branch(9216, 0)
    bp.connect(encoded_length, "ReturnValue", size_ok, "A")
    bp.connect(max_size, "MaxSerializedBytesV1", size_ok, "B")
    bp.connect(size_ok, "ReturnValue", size_branch, "Condition")

    cache_index = b.setter("ScratchIndexV1", "int", 9472, 0)
    bp.connect(index, "ResultRecordIndexV1", cache_index, "ScratchIndexV1")
    prepare = b.call("PreparePersistenceCandidateV1", 9728, 0)
    candidate_records = b.getter("CandidateRecordEnvelopesV1", "string", 9728, 320, array=True)
    replace_candidate = b.add("replace_candidate_record", "array_set", 9984, 0)
    specialize_array_set(enc, replace_candidate, "string")
    bp.connect(candidate_records, "CandidateRecordEnvelopesV1", replace_candidate, "TargetArray")
    bp.connect(index, "ResultRecordIndexV1", replace_candidate, "Index")
    bp.connect(encoded, "ScratchEncodedRecordV1", replace_candidate, "Item")
    persist = b.call("PersistRepositoryV1", 10240, 0)
    committed = b.getter("ScratchPersistenceCommitSavedV1", "bool", 10240, 320)
    committed_branch = v.branch(10496, 0)
    bp.connect(committed, "ScratchPersistenceCommitSavedV1", committed_branch, "Condition")

    cached_index = b.getter("ScratchIndexV1", "int", 10496, 400)
    publish_index = b.setter("ResultRecordIndexV1", "int", 10752, 0)
    bp.connect(cached_index, "ScratchIndexV1", publish_index, "ResultRecordIndexV1")
    active_updated = b.getter("ActiveUpdatedUtcV1", "string", 10752, 400, array=True)
    replace_updated = b.add("replace_active_updated", "array_set", 11008, 0)
    specialize_array_set(enc, replace_updated, "string")
    bp.connect(active_updated, "ActiveUpdatedUtcV1", replace_updated, "TargetArray")
    bp.connect(cached_index, "ScratchIndexV1", replace_updated, "Index")
    bp.connect(now, "RequestNowUtcV1", replace_updated, "Item")

    result_envelope = b.setter("ResultRecordEnvelopeV1", "string", 11264, 0)
    result_revision = b.setter("ResultCurrentRevisionV1", "int", 11520, 0)
    result_has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", 11776, 0)
    enc.set_default(result_has_revision, "ResultHasCurrentRevisionV1", "true")
    saved_document = b.getter("ScratchRecordDraftDocumentV1", "document", 11776, 400)
    result_document = b.setter("ResultDraftDocumentV1", "document", 12032, 0)
    bp.connect(encoded, "ScratchEncodedRecordV1", result_envelope, "ResultRecordEnvelopeV1")
    # PersistRepositoryV1 resets repository result fields, and all pure nodes
    # are evaluated at their consumer.  Read the already-staged authoritative
    # record values here; recomputing current+1 after persistence would add 1
    # to the new revision a second time.
    bp.connect(current_revision, "ScratchRecordDraftRevisionNumberV1", result_revision, "ResultCurrentRevisionV1")
    bp.connect(saved_document, "ScratchRecordDraftDocumentV1", result_document, "ResultDraftDocumentV1")

    not_found = error(enc, b, "NotFound", "FlypathNotFound", 1280, -320)
    forbidden = error(enc, b, "Forbidden", "OwnerRequired", 2048, -320)
    decode_failed = error(enc, b, "ValidationFailed", "StoredRecordDecodeFailed", 2816, -320)
    stored_invalid = error(enc, b, "ValidationFailed", "StoredRecordInvalid", 3328, -320)
    identity_mismatch = error(enc, b, "ValidationFailed", "StoredRecordIndexMismatch", 4096, -320)
    revision_conflict = error(enc, b, "RevisionConflict", "ExpectedRevisionMismatch", 5120, -320)
    invalid_request = error(enc, b, "ValidationFailed", "InvalidSaveRequest", 5376, -320)
    waypoint_limit = error(enc, b, "LimitExceeded", "WaypointLimit", 6400, -320)
    region_mismatch = error(enc, b, "RegionForbidden", "DraftRegionMismatch", 6912, -320)
    draft_invalid = error(enc, b, "ValidationFailed", "DraftInvalid", 8448, -320)
    size_limit = error(enc, b, "LimitExceeded", "SerializedSize", 9472, -320)

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", find, "execute")
    bp.connect(find, "then", found, "execute")
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
    bp.connect(revision_branch, "then", request_valid_branch, "execute")
    bp.connect(request_valid_branch, "else", invalid_request[0], "execute")
    bp.connect(invalid_request[0], "then", invalid_request[1], "execute")
    bp.connect(request_valid_branch, "then", waypoint_limit_branch, "execute")
    bp.connect(waypoint_limit_branch, "else", waypoint_limit[0], "execute")
    bp.connect(waypoint_limit[0], "then", waypoint_limit[1], "execute")
    bp.connect(waypoint_limit_branch, "then", region_branch, "execute")
    bp.connect(region_branch, "else", region_mismatch[0], "execute")
    bp.connect(region_mismatch[0], "then", region_mismatch[1], "execute")
    bp.connect(region_branch, "then", stage_document, "execute")
    bp.connect(stage_document, "then", stage_revision, "execute")
    bp.connect(stage_revision, "then", stage_updated, "execute")
    bp.connect(stage_updated, "then", validate_updated, "execute")
    bp.connect(validate_updated, "then", updated_valid_branch, "execute")
    bp.connect(updated_valid_branch, "else", draft_invalid[0], "execute")
    bp.connect(draft_invalid[0], "then", draft_invalid[1], "execute")
    bp.connect(updated_valid_branch, "then", encode, "execute")
    bp.connect(encode, "then", size_branch, "execute")
    bp.connect(size_branch, "else", size_limit[0], "execute")
    bp.connect(size_limit[0], "then", size_limit[1], "execute")
    bp.connect(size_branch, "then", cache_index, "execute")
    bp.connect(cache_index, "then", prepare, "execute")
    bp.connect(prepare, "then", replace_candidate, "execute")
    bp.connect(replace_candidate, "then", persist, "execute")
    bp.connect(persist, "then", committed_branch, "execute")
    bp.connect(committed_branch, "then", publish_index, "execute")
    bp.connect(publish_index, "then", replace_updated, "execute")
    bp.connect(replace_updated, "then", result_envelope, "execute")
    bp.connect(result_envelope, "then", result_revision, "execute")
    bp.connect(result_revision, "then", result_has_revision, "execute")
    bp.connect(result_has_revision, "then", result_document, "execute")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_private_save_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_private_save_validation_base",
    )
    create = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryPrivateCreateGraph.py",
        "edd_private_save_create_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    document_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "document-sync-struct-node-forms.eddgraph"
    )
    edit_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "waypoint-edit-node-forms.eddgraph"
    )
    string_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-string-trim-node-form.eddgraph"
    )
    templates["make_document"] = bp.find_block(
        document_forms, r'K2Node_MakeStruct.*StructType="[^"]*ST_EDD_FlypathDocument'
    )
    templates["array_set"] = bp.find_block(edit_forms, r'MemberName="Array_Set"')
    templates["trim_string"] = bp.find_block(string_forms, r'MemberName="Trim"')
    nodes = build(bp, enc, validation, create, templates)
    enc.write(nodes, args.output_dir / "save-draft-v1.eddgraph", paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / "save-draft-v1-paste.eddgraph",
            paste=True,
        )


if __name__ == "__main__":
    main()
