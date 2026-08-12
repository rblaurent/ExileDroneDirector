"""Build the private deep-clone transaction for one published revision.

The source is authorized solely through public visibility, decoded and
validated before use, and pinned to an exact immutable revision.  The target is
always a new private revision-one record owned by the requester.  Source
attribution is captured before any decoded scratch fields are overwritten and
the accepted copy-on-write A/B writer remains the only mutation boundary.
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


def error(enc, b, code: str, detail: str, x: int, y: int):
    code_node = b.setter("ResultCodeV1", "string", x, y)
    detail_node = b.setter("ResultDetailV1", "string", x + 256, y)
    enc.set_default(code_node, "ResultCodeV1", code)
    enc.set_default(detail_node, "ResultDetailV1", detail)
    return code_node, detail_node


def build(bp, enc, validation, create, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "ClonePublishedV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)

    # Validate caller-controlled scalar inputs before touching repository state.
    required = []
    request_nodes = {}
    for offset, variable in enumerate((
        "RequestRequesterAccountIdV1",
        "RequestSourceFlypathIdV1",
        "RequestFlypathIdV1",
        "RequestTitleV1",
        "RequestNowUtcV1",
    )):
        value, _trim, condition = create.trimmed_nonempty(
            v, templates, variable, 512, 320 + offset * 144
        )
        request_nodes[variable] = value
        required.append(condition)
    required_ok = v.and_all(required, 1184, 320)
    required_branch = v.branch(2080, 0)
    bp.connect(required_ok, "ReturnValue", required_branch, "Condition")

    expected = b.getter("RequestExpectedRevisionV1", "int", 2080, 320)
    positive_revision = v.int_math("Greater_IntInt", 2336, 320, b_default="0")
    revision_request_branch = v.branch(2592, 0)
    bp.connect(expected, "RequestExpectedRevisionV1", positive_revision, "A")
    bp.connect(positive_revision, "ReturnValue", revision_request_branch, "Condition")

    title_length = create.string_len(
        v, request_nodes["RequestTitleV1"], "RequestTitleV1", 2592, 320
    )
    max_title = b.getter("MaxTitleCharsV1", "int", 2816, 464)
    title_ok = v.int_math("LessEqual_IntInt", 3040, 320)
    title_branch = v.branch(3296, 0)
    bp.connect(title_length, "ReturnValue", title_ok, "A")
    bp.connect(max_title, "MaxTitleCharsV1", title_ok, "B")
    bp.connect(title_ok, "ReturnValue", title_branch, "Condition")

    # Resolve the source directly so the target ID remains untouched.
    active_ids = b.getter("ActiveFlypathIdsV1", "string", 3296, 320, array=True)
    source_find = b.add("find_source", "array_find", 3552, 320)
    validation.array_find_form(source_find, enc, "string")
    bp.connect(active_ids, "ActiveFlypathIdsV1", source_find, "TargetArray")
    bp.connect(
        request_nodes["RequestSourceFlypathIdV1"],
        "RequestSourceFlypathIdV1",
        source_find,
        "ItemToFind",
    )
    cache_index = b.setter("ScratchIndexV1", "int", 3808, 0)
    bp.connect(source_find, "ReturnValue", cache_index, "ScratchIndexV1")
    source_index = b.getter("ScratchIndexV1", "int", 3808, 320)
    envelopes = b.getter("ActiveRecordEnvelopesV1", "string", 3808, 480, array=True)
    visibilities = b.getter("ActiveVisibilitiesV1", "string", 3808, 640, array=True)
    envelope_aligned = v.valid_index(
        envelopes, "ActiveRecordEnvelopesV1", source_index, "ScratchIndexV1", "string", 4064, 320
    )
    visibility_aligned = v.valid_index(
        visibilities, "ActiveVisibilitiesV1", source_index, "ScratchIndexV1", "string", 4064, 480
    )
    aligned = v.bool_math("BooleanAND", 4320, 400)
    source_found = v.int_math("GreaterEqual_IntInt", 4320, 640, b_default="0")
    found_and_aligned = v.bool_math("BooleanAND", 4576, 480)
    alignment_branch = v.branch(4832, 0)
    found_branch = v.branch(5088, -160)
    bp.connect(envelope_aligned, "ReturnValue", aligned, "A")
    bp.connect(visibility_aligned, "ReturnValue", aligned, "B")
    bp.connect(source_index, "ScratchIndexV1", source_found, "A")
    bp.connect(source_found, "ReturnValue", found_and_aligned, "A")
    bp.connect(aligned, "ReturnValue", found_and_aligned, "B")
    bp.connect(found_and_aligned, "ReturnValue", alignment_branch, "Condition")
    bp.connect(source_found, "ReturnValue", found_branch, "Condition")

    derived_visibility = v.array_item(
        visibilities, "ActiveVisibilitiesV1", source_index, "ScratchIndexV1", "string", 5088, 320
    )
    derived_public = v.string_math("EqualEqual_StrStr", 5344, 320, b_default="public")
    public_branch = v.branch(5600, 0)
    bp.connect(derived_visibility, "Output", derived_public, "A")
    bp.connect(derived_public, "ReturnValue", public_branch, "Condition")

    envelope = v.array_item(
        envelopes, "ActiveRecordEnvelopesV1", source_index, "ScratchIndexV1", "string", 5600, 480
    )
    stage_envelope = b.setter("ScratchEncodedRecordV1", "string", 5856, 0)
    decode = b.call("DecodeRecordV1", 6112, 0)
    decoded = b.getter("ScratchValidV1", "bool", 6112, 320)
    decoded_branch = v.branch(6368, 0)
    validate_source = b.call("ValidateRecordV1", 6624, 0)
    source_valid = b.getter("ScratchValidV1", "bool", 6624, 320)
    source_valid_branch = v.branch(6880, 0)
    bp.connect(envelope, "Output", stage_envelope, "ScratchEncodedRecordV1")
    bp.connect(decoded, "ScratchValidV1", decoded_branch, "Condition")
    bp.connect(source_valid, "ScratchValidV1", source_valid_branch, "Condition")

    source_id = b.getter("ScratchRecordFlypathIdV1", "string", 6880, 320)
    id_equal = v.string_math("EqualEqual_StrStr", 7136, 320)
    decoded_visibility = b.getter("ScratchRecordVisibilityV1", "string", 6880, 464)
    decoded_public = v.string_math("EqualEqual_StrStr", 7136, 464, b_default="public")
    has_published = b.getter("ScratchRecordHasPublishedRevisionV1", "bool", 6880, 608)
    id_and_public = v.bool_math("BooleanAND", 7392, 384)
    source_identity = v.bool_math("BooleanAND", 7648, 464)
    source_identity_branch = v.branch(7904, 0)
    bp.connect(source_id, "ScratchRecordFlypathIdV1", id_equal, "A")
    bp.connect(
        request_nodes["RequestSourceFlypathIdV1"],
        "RequestSourceFlypathIdV1",
        id_equal,
        "B",
    )
    bp.connect(decoded_visibility, "ScratchRecordVisibilityV1", decoded_public, "A")
    bp.connect(id_equal, "ReturnValue", id_and_public, "A")
    bp.connect(decoded_public, "ReturnValue", id_and_public, "B")
    bp.connect(id_and_public, "ReturnValue", source_identity, "A")
    bp.connect(has_published, "ScratchRecordHasPublishedRevisionV1", source_identity, "B")
    bp.connect(source_identity, "ReturnValue", source_identity_branch, "Condition")

    published_revision = b.getter("ScratchRecordPublishedRevisionNumberV1", "int", 7904, 320)
    exact_revision = v.int_math("EqualEqual_IntInt", 8160, 320)
    revision_branch = v.branch(8416, 0)
    bp.connect(published_revision, "ScratchRecordPublishedRevisionNumberV1", exact_revision, "A")
    bp.connect(expected, "RequestExpectedRevisionV1", exact_revision, "B")
    bp.connect(exact_revision, "ReturnValue", revision_branch, "Condition")

    conflict_revision = b.setter("ResultCurrentRevisionV1", "int", 8672, -320)
    conflict_has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", 8928, -320)
    enc.set_default(conflict_has_revision, "ResultHasCurrentRevisionV1", "true")
    bp.connect(
        published_revision,
        "ScratchRecordPublishedRevisionNumberV1",
        conflict_revision,
        "ResultCurrentRevisionV1",
    )

    source_region = b.getter("ScratchRecordRegionIdV1", "string", 8416, 400)
    allowed_regions = b.getter("AllowedRegionsV1", "string", 8416, 544, array=True)
    region_find = b.add("find_source_region", "array_find", 8672, 400)
    validation.array_find_form(region_find, enc, "string")
    region_allowed = v.int_math("NotEqual_IntInt", 8928, 400, b_default="-1")
    region_branch = v.branch(9184, 0)
    bp.connect(allowed_regions, "AllowedRegionsV1", region_find, "TargetArray")
    bp.connect(source_region, "ScratchRecordRegionIdV1", region_find, "ItemToFind")
    bp.connect(region_find, "ReturnValue", region_allowed, "A")
    bp.connect(region_allowed, "ReturnValue", region_branch, "Condition")

    published_document = b.getter("ScratchRecordPublishedDocumentV1", "document", 9184, 400)
    break_published = b.add("break_published_clone", "break_document", 9440, 400)
    bp.connect(
        published_document,
        "ScratchRecordPublishedDocumentV1",
        break_published,
        "ST_EDD_FlypathDocument",
    )
    waypoint_count = v.length(break_published, enc.DOC_WAYPOINTS, "waypoint", 9696, 400)
    max_waypoints = b.getter("MaxWaypointsPerPathV1", "int", 9696, 544)
    waypoints_allowed = v.int_math("LessEqual_IntInt", 9952, 400)
    waypoint_branch = v.branch(10208, 0)
    bp.connect(waypoint_count, "ReturnValue", waypoints_allowed, "A")
    bp.connect(max_waypoints, "MaxWaypointsPerPathV1", waypoints_allowed, "B")
    bp.connect(waypoints_allowed, "ReturnValue", waypoint_branch, "Condition")

    target_find = b.add("find_target", "array_find", 10208, 400)
    validation.array_find_form(target_find, enc, "string")
    target_absent = v.int_math("EqualEqual_IntInt", 10464, 400, b_default="-1")
    collision_branch = v.branch(10720, 0)
    bp.connect(active_ids, "ActiveFlypathIdsV1", target_find, "TargetArray")
    bp.connect(request_nodes["RequestFlypathIdV1"], "RequestFlypathIdV1", target_find, "ItemToFind")
    bp.connect(target_find, "ReturnValue", target_absent, "A")
    bp.connect(target_absent, "ReturnValue", collision_branch, "Condition")

    reset_owned = b.setter("ScratchListSafeOffsetV1", "int", 10976, 0)
    enc.set_default(reset_owned, "ScratchListSafeOffsetV1", "0")
    owners = b.getter("ActiveOwnerAccountIdsV1", "string", 10976, 400, array=True)
    each_owner = b.foreach("string", 11232, 0)
    requester = b.getter("RequestRequesterAccountIdV1", "string", 11232, 400)
    owner_equal = v.string_math("EqualEqual_StrStr", 11488, 400)
    owner_branch = v.branch(11744, 192)
    owned_count = b.getter("ScratchListSafeOffsetV1", "int", 12000, 400)
    increment = v.int_math("Add_IntInt", 12256, 400, b_default="1")
    store_count = b.setter("ScratchListSafeOffsetV1", "int", 12512, 192)
    bp.connect(owners, "ActiveOwnerAccountIdsV1", each_owner, "Array")
    bp.connect(each_owner, "Array Element", owner_equal, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", owner_equal, "B")
    bp.connect(owner_equal, "ReturnValue", owner_branch, "Condition")
    bp.connect(owned_count, "ScratchListSafeOffsetV1", increment, "A")
    bp.connect(increment, "ReturnValue", store_count, "ScratchListSafeOffsetV1")
    bp.connect(each_owner, "LoopBody", owner_branch, "execute")
    bp.connect(owner_branch, "then", store_count, "execute")
    final_owned = b.getter("ScratchListSafeOffsetV1", "int", 11744, 640)
    max_owned = b.getter("MaxPathsPerOwnerV1", "int", 12000, 640)
    under_limit = v.int_math("Less_IntInt", 12256, 640)
    owner_limit_branch = v.branch(12512, 0)
    bp.connect(final_owned, "ScratchListSafeOffsetV1", under_limit, "A")
    bp.connect(max_owned, "MaxPathsPerOwnerV1", under_limit, "B")
    bp.connect(under_limit, "ReturnValue", owner_limit_branch, "Condition")

    # Build the revision-one clone document as a deep value snapshot.
    make_clone_document = b.add("make_clone_document", "make_document", 12768, 400)
    for pin in (
        enc.DOC_SCHEMA,
        enc.DOC_ENGINE,
        enc.DOC_REGION,
        enc.DOC_DURATION,
        enc.DOC_PROFILE,
        enc.DOC_WAYPOINTS,
        enc.DOC_SEGMENTS,
    ):
        bp.connect(break_published, pin, make_clone_document, pin)
    enc.set_default(make_clone_document, enc.DOC_REVISION, "1")
    enc.set_default(make_clone_document, enc.DOC_HASH, "")

    # Capture immutable source attribution before overwriting decoded source
    # scratch fields with the new target record.
    source_title = b.getter("ScratchRecordTitleV1", "string", 12768, 640)
    source_creator = b.getter("ScratchRecordOwnerDisplayNameV1", "string", 12768, 784)
    stage_specs = (
        ("ScratchRecordHasSourceAttributionV1", "bool", None, "true"),
        ("ScratchRecordSourceFlypathIdV1", "string", source_id, "ScratchRecordFlypathIdV1"),
        ("ScratchRecordSourceRevisionNumberV1", "int", published_revision, "ScratchRecordPublishedRevisionNumberV1"),
        ("ScratchRecordSourceTitleV1", "string", source_title, "ScratchRecordTitleV1"),
        ("ScratchRecordSourceCreatorDisplayNameV1", "string", source_creator, "ScratchRecordOwnerDisplayNameV1"),
        ("ScratchRecordDraftDocumentV1", "document", make_clone_document, "ST_EDD_FlypathDocument"),
        ("ScratchRecordFlypathIdV1", "string", request_nodes["RequestFlypathIdV1"], "RequestFlypathIdV1"),
        ("ScratchRecordOwnerAccountIdV1", "string", requester, "RequestRequesterAccountIdV1"),
        ("ScratchRecordOwnerDisplayNameV1", "string", None, None),
        ("ScratchRecordTitleV1", "string", request_nodes["RequestTitleV1"], "RequestTitleV1"),
        ("ScratchRecordDescriptionV1", "string", None, None),
        ("ScratchRecordRegionIdV1", "string", source_region, "ScratchRecordRegionIdV1"),
        ("ScratchRecordVisibilityV1", "string", None, "private"),
        ("ScratchRecordCreatedUtcV1", "string", request_nodes["RequestNowUtcV1"], "RequestNowUtcV1"),
        ("ScratchRecordUpdatedUtcV1", "string", request_nodes["RequestNowUtcV1"], "RequestNowUtcV1"),
        ("ScratchRecordDraftRevisionNumberV1", "int", None, "1"),
        ("ScratchRecordHasPublishedRevisionV1", "bool", None, "false"),
        ("ScratchRecordPublishedRevisionNumberV1", "int", None, "0"),
        ("ScratchRecordPublishedDocumentV1", "document", None, None),
    )
    # Explicit request getters for optional display/description ensure the clone
    # cannot inherit these mutable fields from the source by accident.
    requester_display = b.getter("RequestRequesterDisplayNameV1", "string", 12768, 928)
    request_description = b.getter("RequestDescriptionV1", "string", 12768, 1072)
    staged = []
    x = 13024
    for target, kind, source, source_pin_or_default in stage_specs:
        setter = b.setter(target, kind, x, 0)
        if target == "ScratchRecordOwnerDisplayNameV1":
            bp.connect(requester_display, "RequestRequesterDisplayNameV1", setter, target)
        elif target == "ScratchRecordDescriptionV1":
            bp.connect(request_description, "RequestDescriptionV1", setter, target)
        elif source is not None:
            bp.connect(source, source_pin_or_default, setter, target)
        elif source_pin_or_default is not None:
            enc.set_default(setter, target, source_pin_or_default)
        staged.append(setter)
        x += 256

    validate_clone = b.call("ValidateRecordV1", x, 0)
    clone_valid = b.getter("ScratchValidV1", "bool", x, 320)
    clone_valid_branch = v.branch(x + 256, 0)
    encode = b.call("EncodeRecordV1", x + 512, 0)
    encoded = b.getter("ScratchEncodedRecordV1", "string", x + 512, 320)
    encoded_length = create.string_len(v, encoded, "ScratchEncodedRecordV1", x + 768, 320)
    max_size = b.getter("MaxSerializedBytesV1", "int", x + 768, 464)
    size_ok = v.int_math("LessEqual_IntInt", x + 1024, 320)
    size_branch = v.branch(x + 1280, 0)
    bp.connect(clone_valid, "ScratchValidV1", clone_valid_branch, "Condition")
    bp.connect(encoded_length, "ReturnValue", size_ok, "A")
    bp.connect(max_size, "MaxSerializedBytesV1", size_ok, "B")
    bp.connect(size_ok, "ReturnValue", size_branch, "Condition")

    prepare = b.call("PreparePersistenceCandidateV1", x + 1536, 0)
    candidate_records = b.getter("CandidateRecordEnvelopesV1", "string", x + 1536, 320, array=True)
    append_candidate = b.array_add("string", x + 1792, 0)
    persist = b.call("PersistRepositoryV1", x + 2048, 0)
    committed = b.getter("ScratchPersistenceCommitSavedV1", "bool", x + 2048, 320)
    committed_branch = v.branch(x + 2304, 0)
    bp.connect(candidate_records, "CandidateRecordEnvelopesV1", append_candidate, "TargetArray")
    bp.connect(encoded, "ScratchEncodedRecordV1", append_candidate, "NewItem")
    bp.connect(committed, "ScratchPersistenceCommitSavedV1", committed_branch, "Condition")

    # Promote derived state and result payload only after durable commit.
    derived_ids = b.getter("ActiveFlypathIdsV1", "string", x + 2560, 320, array=True)
    add_id = b.array_add("string", x + 2560, 0)
    derived_owners = b.getter("ActiveOwnerAccountIdsV1", "string", x + 2816, 320, array=True)
    add_owner = b.array_add("string", x + 2816, 0)
    derived_visibility = b.getter("ActiveVisibilitiesV1", "string", x + 3072, 320, array=True)
    add_visibility = b.array_add("string", x + 3072, 0)
    derived_updated = b.getter("ActiveUpdatedUtcV1", "string", x + 3328, 320, array=True)
    add_updated = b.array_add("string", x + 3328, 0)
    result_index = b.setter("ResultRecordIndexV1", "int", x + 3584, 0)
    result_envelope = b.setter("ResultRecordEnvelopeV1", "string", x + 3840, 0)
    result_revision = b.setter("ResultCurrentRevisionV1", "int", x + 4096, 0)
    enc.set_default(result_revision, "ResultCurrentRevisionV1", "1")
    result_has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", x + 4352, 0)
    enc.set_default(result_has_revision, "ResultHasCurrentRevisionV1", "true")
    clone_document = b.getter("ScratchRecordDraftDocumentV1", "document", x + 4352, 320)
    result_document = b.setter("ResultDraftDocumentV1", "document", x + 4608, 0)
    bp.connect(derived_ids, "ActiveFlypathIdsV1", add_id, "TargetArray")
    bp.connect(request_nodes["RequestFlypathIdV1"], "RequestFlypathIdV1", add_id, "NewItem")
    bp.connect(derived_owners, "ActiveOwnerAccountIdsV1", add_owner, "TargetArray")
    bp.connect(requester, "RequestRequesterAccountIdV1", add_owner, "NewItem")
    bp.connect(derived_visibility, "ActiveVisibilitiesV1", add_visibility, "TargetArray")
    enc.set_default(add_visibility, "NewItem", "private")
    bp.connect(derived_updated, "ActiveUpdatedUtcV1", add_updated, "TargetArray")
    bp.connect(request_nodes["RequestNowUtcV1"], "RequestNowUtcV1", add_updated, "NewItem")
    bp.connect(add_id, "ReturnValue", result_index, "ResultRecordIndexV1")
    bp.connect(encoded, "ScratchEncodedRecordV1", result_envelope, "ResultRecordEnvelopeV1")
    bp.connect(clone_document, "ScratchRecordDraftDocumentV1", result_document, "ResultDraftDocumentV1")

    invalid_request = error(enc, b, "ValidationFailed", "InvalidCloneRequest", 2336, -480)
    invalid_revision = error(enc, b, "ValidationFailed", "InvalidPublishedRevisionRequest", 2816, -480)
    title_limit = error(enc, b, "LimitExceeded", "TitleLength", 3552, -480)
    not_found = error(enc, b, "NotFound", "FlypathNotFound", 5344, -480)
    misaligned = error(enc, b, "ValidationFailed", "MetadataIndexMisaligned", 5344, -320)
    decode_failed = error(enc, b, "ValidationFailed", "StoredRecordDecodeFailed", 6624, -320)
    stored_invalid = error(enc, b, "ValidationFailed", "StoredRecordInvalid", 7136, -320)
    identity_mismatch = error(enc, b, "ValidationFailed", "StoredRecordIndexMismatch", 8160, -320)
    revision_conflict = error(enc, b, "RevisionConflict", "PublishedRevisionMismatch", 9184, -320)
    region_denied = error(enc, b, "RegionForbidden", "RegionNotAllowed", 9440, -320)
    waypoint_limit = error(enc, b, "LimitExceeded", "WaypointCount", 10464, -320)
    collision = error(enc, b, "AlreadyExists", "FlypathIdCollision", 10976, -320)
    owner_limit = error(enc, b, "LimitExceeded", "OwnerPathLimit", 12768, -320)
    clone_invalid = error(enc, b, "ValidationFailed", "CloneRecordInvalid", x + 512, -320)
    size_limit = error(enc, b, "LimitExceeded", "SerializedSize", x + 1536, -320)

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", required_branch, "execute")
    bp.connect(required_branch, "else", invalid_request[0], "execute")
    bp.connect(invalid_request[0], "then", invalid_request[1], "execute")
    bp.connect(required_branch, "then", revision_request_branch, "execute")
    bp.connect(revision_request_branch, "else", invalid_revision[0], "execute")
    bp.connect(invalid_revision[0], "then", invalid_revision[1], "execute")
    bp.connect(revision_request_branch, "then", title_branch, "execute")
    bp.connect(title_branch, "else", title_limit[0], "execute")
    bp.connect(title_limit[0], "then", title_limit[1], "execute")
    bp.connect(title_branch, "then", cache_index, "execute")
    bp.connect(cache_index, "then", alignment_branch, "execute")
    bp.connect(alignment_branch, "else", found_branch, "execute")
    bp.connect(found_branch, "else", not_found[0], "execute")
    bp.connect(not_found[0], "then", not_found[1], "execute")
    bp.connect(found_branch, "then", misaligned[0], "execute")
    bp.connect(misaligned[0], "then", misaligned[1], "execute")
    bp.connect(alignment_branch, "then", public_branch, "execute")
    bp.connect(public_branch, "else", not_found[0], "execute")
    bp.connect(public_branch, "then", stage_envelope, "execute")
    bp.connect(stage_envelope, "then", decode, "execute")
    bp.connect(decode, "then", decoded_branch, "execute")
    bp.connect(decoded_branch, "else", decode_failed[0], "execute")
    bp.connect(decode_failed[0], "then", decode_failed[1], "execute")
    bp.connect(decoded_branch, "then", validate_source, "execute")
    bp.connect(validate_source, "then", source_valid_branch, "execute")
    bp.connect(source_valid_branch, "else", stored_invalid[0], "execute")
    bp.connect(stored_invalid[0], "then", stored_invalid[1], "execute")
    bp.connect(source_valid_branch, "then", source_identity_branch, "execute")
    bp.connect(source_identity_branch, "else", identity_mismatch[0], "execute")
    bp.connect(identity_mismatch[0], "then", identity_mismatch[1], "execute")
    bp.connect(source_identity_branch, "then", revision_branch, "execute")
    bp.connect(revision_branch, "else", revision_conflict[0], "execute")
    bp.connect(revision_conflict[0], "then", revision_conflict[1], "execute")
    bp.connect(revision_conflict[1], "then", conflict_revision, "execute")
    bp.connect(conflict_revision, "then", conflict_has_revision, "execute")
    bp.connect(revision_branch, "then", region_branch, "execute")
    bp.connect(region_branch, "else", region_denied[0], "execute")
    bp.connect(region_denied[0], "then", region_denied[1], "execute")
    bp.connect(region_branch, "then", waypoint_branch, "execute")
    bp.connect(waypoint_branch, "else", waypoint_limit[0], "execute")
    bp.connect(waypoint_limit[0], "then", waypoint_limit[1], "execute")
    bp.connect(waypoint_branch, "then", collision_branch, "execute")
    bp.connect(collision_branch, "else", collision[0], "execute")
    bp.connect(collision[0], "then", collision[1], "execute")
    bp.connect(collision_branch, "then", reset_owned, "execute")
    bp.connect(reset_owned, "then", each_owner, "Exec")
    bp.connect(each_owner, "Completed", owner_limit_branch, "execute")
    bp.connect(owner_limit_branch, "else", owner_limit[0], "execute")
    bp.connect(owner_limit[0], "then", owner_limit[1], "execute")
    bp.connect(owner_limit_branch, "then", staged[0], "execute")
    for left, right in zip(staged, staged[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(staged[-1], "then", validate_clone, "execute")
    bp.connect(validate_clone, "then", clone_valid_branch, "execute")
    bp.connect(clone_valid_branch, "else", clone_invalid[0], "execute")
    bp.connect(clone_invalid[0], "then", clone_invalid[1], "execute")
    bp.connect(clone_valid_branch, "then", encode, "execute")
    bp.connect(encode, "then", size_branch, "execute")
    bp.connect(size_branch, "else", size_limit[0], "execute")
    bp.connect(size_limit[0], "then", size_limit[1], "execute")
    bp.connect(size_branch, "then", prepare, "execute")
    bp.connect(prepare, "then", append_candidate, "execute")
    bp.connect(append_candidate, "then", persist, "execute")
    bp.connect(persist, "then", committed_branch, "execute")
    bp.connect(committed_branch, "then", add_id, "execute")
    for left, right in zip(
        (add_id, add_owner, add_visibility, add_updated, result_index, result_envelope,
         result_revision, result_has_revision),
        (add_owner, add_visibility, add_updated, result_index, result_envelope,
         result_revision, result_has_revision, result_document),
    ):
        bp.connect(left, "then", right, "execute")
    # committed=false terminates with the writer's precise persistence result.
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_clone_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_clone_validation_base",
    )
    create = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryPrivateCreateGraph.py",
        "edd_clone_create_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    document_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "document-sync-struct-node-forms.eddgraph"
    )
    string_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-string-trim-node-form.eddgraph"
    )
    templates["trim_string"] = bp.find_block(string_forms, r'MemberName="Trim"')
    templates["make_document"] = bp.find_block(
        document_forms, r'K2Node_MakeStruct.*StructType="[^"]*ST_EDD_FlypathDocument'
    )
    nodes = build(bp, enc, validation, create, templates)
    enc.write(nodes, args.output_dir / "clone-published-v1.eddgraph", paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / "clone-published-v1-paste.eddgraph",
            paste=True,
        )


if __name__ == "__main__":
    main()
