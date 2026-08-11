"""Build the private-by-default repository create transaction.

The graph consumes the explicit Request*V1 staging fields, builds and validates
one complete record, appends it to a copy-on-write persistence candidate, and
only exposes it through the derived indexes after the accepted two-phase writer
has committed successfully.
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


def string_len(v, source, source_pin: str, x: int, y: int):
    """Derive KismetStringLibrary.Len from the reviewed string call form."""
    node = v.b.add(f"string_len_{len(v.nodes)}", "string_math", x, y)
    # retarget_function belongs to the validation module, not the encoder.
    node.text = node.text.replace('MemberName="EqualEqual_StrStr"', 'MemberName="Len"', 1)
    v.enc.rename_pin(node, "A", "S")
    validation_remove_pin = node.pins.pop("B")
    node.text = "\n".join(
        line for line in node.text.splitlines() if f"PinId={validation_remove_pin}" not in line
    )
    v.enc.set_pin_type(node, "ReturnValue", "int")
    v.bp.connect(source, source_pin, node, "S")
    return node


def trimmed_nonempty(v, templates, variable: str, x: int, y: int):
    b = v.b
    value = b.getter(variable, "string", x, y)
    trim = b.add(f"trim_{variable}", "trim_string", x + 224, y)
    not_empty = v.string_math("NotEqual_StrStr", x + 448, y, b_default="")
    v.bp.connect(value, variable, trim, "SourceString")
    v.bp.connect(trim, "ReturnValue", not_empty, "A")
    return value, trim, not_empty


def build(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "CreatePrivateFlypathV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)
    find = b.call("FindRecordIndexV1", 512, 0)
    index = b.getter("ResultRecordIndexV1", "int", 512, 320)
    absent = v.int_math("EqualEqual_IntInt", 768, 320, b_default="-1")
    collision_branch = v.branch(1024, 0)
    bp.connect(index, "ResultRecordIndexV1", absent, "A")
    bp.connect(absent, "ReturnValue", collision_branch, "Condition")

    required = []
    request_nodes = {}
    for offset, variable in enumerate(
        (
            "RequestRequesterAccountIdV1",
            "RequestFlypathIdV1",
            "RequestTitleV1",
            "RequestRegionIdV1",
            "RequestNowUtcV1",
        )
    ):
        value, _trim, condition = trimmed_nonempty(v, templates, variable, 1280, 320 + offset * 144)
        request_nodes[variable] = value
        required.append(condition)
    required_ok = v.and_all(required, 1952, 320)
    required_branch = v.branch(3072, 0)
    bp.connect(required_ok, "ReturnValue", required_branch, "Condition")

    title_length = string_len(v, request_nodes["RequestTitleV1"], "RequestTitleV1", 3072, 480)
    max_title = b.getter("MaxTitleCharsV1", "int", 3296, 624)
    title_ok = v.int_math("LessEqual_IntInt", 3520, 480)
    title_branch = v.branch(3744, 0)
    bp.connect(title_length, "ReturnValue", title_ok, "A")
    bp.connect(max_title, "MaxTitleCharsV1", title_ok, "B")
    bp.connect(title_ok, "ReturnValue", title_branch, "Condition")

    allowed_regions = b.getter("AllowedRegionsV1", "string", 3744, 480, array=True)
    region_find = b.add("find_region", "array_find", 3968, 480)
    validation.array_find_form(region_find, enc, "string")
    region_allowed = v.int_math("NotEqual_IntInt", 4192, 480, b_default="-1")
    region_branch = v.branch(4416, 0)
    bp.connect(allowed_regions, "AllowedRegionsV1", region_find, "TargetArray")
    bp.connect(request_nodes["RequestRegionIdV1"], "RequestRegionIdV1", region_find, "ItemToFind")
    bp.connect(region_find, "ReturnValue", region_allowed, "A")
    bp.connect(region_allowed, "ReturnValue", region_branch, "Condition")

    reset_owned = b.setter("ScratchIndexV1", "int", 4672, 0)
    enc.set_default(reset_owned, "ScratchIndexV1", "0")
    owners = b.getter("ActiveOwnerAccountIdsV1", "string", 4672, 320, array=True)
    each_owner = b.foreach("string", 4928, 0)
    owner_equal = v.string_math("EqualEqual_StrStr", 5184, 320)
    owner_branch = v.branch(5408, 192)
    owned_count = b.getter("ScratchIndexV1", "int", 5664, 320)
    increment = v.int_math("Add_IntInt", 5888, 320, b_default="1")
    store_count = b.setter("ScratchIndexV1", "int", 6112, 192)
    bp.connect(owners, "ActiveOwnerAccountIdsV1", each_owner, "Array")
    bp.connect(each_owner, "Array Element", owner_equal, "A")
    bp.connect(request_nodes["RequestRequesterAccountIdV1"], "RequestRequesterAccountIdV1", owner_equal, "B")
    bp.connect(owner_equal, "ReturnValue", owner_branch, "Condition")
    bp.connect(owned_count, "ScratchIndexV1", increment, "A")
    bp.connect(increment, "ReturnValue", store_count, "ScratchIndexV1")
    bp.connect(each_owner, "LoopBody", owner_branch, "execute")
    bp.connect(owner_branch, "then", store_count, "execute")

    final_owned_count = b.getter("ScratchIndexV1", "int", 5408, 640)
    max_owned = b.getter("MaxPathsPerOwnerV1", "int", 5632, 640)
    owner_under_limit = v.int_math("Less_IntInt", 5856, 640)
    owner_limit_branch = v.branch(6080, 0)
    bp.connect(final_owned_count, "ScratchIndexV1", owner_under_limit, "A")
    bp.connect(max_owned, "MaxPathsPerOwnerV1", owner_under_limit, "B")
    bp.connect(owner_under_limit, "ReturnValue", owner_limit_branch, "Condition")

    # Stage the complete private record. RequestFlypathIdV1 is a deterministic,
    # server-staged identity; revision one is fixed by the creation contract.
    stage_specs = (
        ("ScratchRecordFlypathIdV1", "string", "RequestFlypathIdV1", None),
        ("ScratchRecordOwnerAccountIdV1", "string", "RequestRequesterAccountIdV1", None),
        ("ScratchRecordOwnerDisplayNameV1", "string", "RequestRequesterDisplayNameV1", None),
        ("ScratchRecordTitleV1", "string", "RequestTitleV1", None),
        ("ScratchRecordDescriptionV1", "string", "RequestDescriptionV1", None),
        ("ScratchRecordVisibilityV1", "string", None, "private"),
        ("ScratchRecordRegionIdV1", "string", "RequestRegionIdV1", None),
        ("ScratchRecordCreatedUtcV1", "string", "RequestNowUtcV1", None),
        ("ScratchRecordUpdatedUtcV1", "string", "RequestNowUtcV1", None),
        ("ScratchRecordDraftRevisionNumberV1", "int", None, "1"),
        ("ScratchRecordDraftDocumentV1", "document", "RequestDraftDocumentV1", None),
        ("ScratchRecordHasPublishedRevisionV1", "bool", None, "false"),
        ("ScratchRecordPublishedRevisionNumberV1", "int", None, "0"),
        ("ScratchRecordHasSourceAttributionV1", "bool", None, "false"),
        ("ScratchRecordSourceRevisionNumberV1", "int", None, "0"),
    )
    staged = []
    x = 6336
    for target, kind, source_name, default in stage_specs:
        setter = b.setter(target, kind, x, 0)
        if source_name is not None:
            source = b.getter(source_name, kind, x, 384)
            bp.connect(source, source_name, setter, target)
        else:
            enc.set_default(setter, target, default or "")
        staged.append(setter)
        x += 256

    validate = b.call("ValidateRecordV1", x, 0)
    valid = b.getter("ScratchValidV1", "bool", x, 320)
    valid_branch = v.branch(x + 256, 0)
    encode = b.call("EncodeRecordV1", x + 512, 0)
    encoded = b.getter("ScratchEncodedRecordV1", "string", x + 512, 320)
    encoded_length = string_len(v, encoded, "ScratchEncodedRecordV1", x + 736, 320)
    max_bytes = b.getter("MaxSerializedBytesV1", "int", x + 736, 480)
    size_ok = v.int_math("LessEqual_IntInt", x + 960, 320)
    size_branch = v.branch(x + 1184, 0)
    bp.connect(valid, "ScratchValidV1", valid_branch, "Condition")
    bp.connect(encoded_length, "ReturnValue", size_ok, "A")
    bp.connect(max_bytes, "MaxSerializedBytesV1", size_ok, "B")
    bp.connect(size_ok, "ReturnValue", size_branch, "Condition")

    prepare = b.call("PreparePersistenceCandidateV1", x + 1440, 0)
    candidate_records = b.getter("CandidateRecordEnvelopesV1", "string", x + 1440, 320, array=True)
    append_candidate = b.array_add("string", x + 1696, 0)
    persist = b.call("PersistRepositoryV1", x + 1952, 0)
    committed = b.getter("ScratchPersistenceCommitSavedV1", "bool", x + 1952, 320)
    committed_branch = v.branch(x + 2208, 0)
    bp.connect(candidate_records, "CandidateRecordEnvelopesV1", append_candidate, "TargetArray")
    bp.connect(encoded, "ScratchEncodedRecordV1", append_candidate, "NewItem")
    bp.connect(committed, "ScratchPersistenceCommitSavedV1", committed_branch, "Condition")

    # Promote derived indexes only after the physical writer committed.
    active_ids = b.getter("ActiveFlypathIdsV1", "string", x + 2464, 320, array=True)
    add_id = b.array_add("string", x + 2464, 0)
    active_owners = b.getter("ActiveOwnerAccountIdsV1", "string", x + 2720, 320, array=True)
    add_owner = b.array_add("string", x + 2720, 0)
    active_visibility = b.getter("ActiveVisibilitiesV1", "string", x + 2976, 320, array=True)
    add_visibility = b.array_add("string", x + 2976, 0)
    active_updated = b.getter("ActiveUpdatedUtcV1", "string", x + 3232, 320, array=True)
    add_updated = b.array_add("string", x + 3232, 0)
    result_index = b.setter("ResultRecordIndexV1", "int", x + 3488, 0)
    result_envelope = b.setter("ResultRecordEnvelopeV1", "string", x + 3744, 0)
    result_revision = b.setter("ResultCurrentRevisionV1", "int", x + 4000, 0)
    enc.set_default(result_revision, "ResultCurrentRevisionV1", "1")
    result_has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", x + 4256, 0)
    enc.set_default(result_has_revision, "ResultHasCurrentRevisionV1", "true")
    request_document = b.getter("RequestDraftDocumentV1", "document", x + 4256, 320)
    result_document = b.setter("ResultDraftDocumentV1", "document", x + 4512, 0)

    bp.connect(active_ids, "ActiveFlypathIdsV1", add_id, "TargetArray")
    bp.connect(request_nodes["RequestFlypathIdV1"], "RequestFlypathIdV1", add_id, "NewItem")
    bp.connect(active_owners, "ActiveOwnerAccountIdsV1", add_owner, "TargetArray")
    bp.connect(request_nodes["RequestRequesterAccountIdV1"], "RequestRequesterAccountIdV1", add_owner, "NewItem")
    bp.connect(active_visibility, "ActiveVisibilitiesV1", add_visibility, "TargetArray")
    enc.set_default(add_visibility, "NewItem", "private")
    bp.connect(active_updated, "ActiveUpdatedUtcV1", add_updated, "TargetArray")
    bp.connect(request_nodes["RequestNowUtcV1"], "RequestNowUtcV1", add_updated, "NewItem")
    bp.connect(add_id, "ReturnValue", result_index, "ResultRecordIndexV1")
    bp.connect(encoded, "ScratchEncodedRecordV1", result_envelope, "ResultRecordEnvelopeV1")
    bp.connect(request_document, "RequestDraftDocumentV1", result_document, "ResultDraftDocumentV1")

    collision = error(enc, b, "AlreadyExists", "FlypathIdCollision", 1280, -320)
    invalid_request = error(enc, b, "ValidationFailed", "InvalidCreateRequest", 3072, -320)
    title_limit = error(enc, b, "LimitExceeded", "TitleLength", 4000, -320)
    region_denied = error(enc, b, "RegionForbidden", "RegionNotAllowed", 4672, -320)
    owner_limit = error(enc, b, "LimitExceeded", "OwnerPathLimit", 6336, -320)
    invalid_record = error(enc, b, "ValidationFailed", "InitialRecordInvalid", x + 512, -320)
    size_limit = error(enc, b, "LimitExceeded", "SerializedSize", x + 1440, -320)

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", find, "execute")
    bp.connect(find, "then", collision_branch, "execute")
    bp.connect(collision_branch, "else", collision[0], "execute")
    bp.connect(collision[0], "then", collision[1], "execute")
    bp.connect(collision_branch, "then", required_branch, "execute")
    bp.connect(required_branch, "else", invalid_request[0], "execute")
    bp.connect(invalid_request[0], "then", invalid_request[1], "execute")
    bp.connect(required_branch, "then", title_branch, "execute")
    bp.connect(title_branch, "else", title_limit[0], "execute")
    bp.connect(title_limit[0], "then", title_limit[1], "execute")
    bp.connect(title_branch, "then", region_branch, "execute")
    bp.connect(region_branch, "else", region_denied[0], "execute")
    bp.connect(region_denied[0], "then", region_denied[1], "execute")
    bp.connect(region_branch, "then", reset_owned, "execute")
    bp.connect(reset_owned, "then", each_owner, "Exec")
    bp.connect(each_owner, "Completed", owner_limit_branch, "execute")
    bp.connect(owner_limit_branch, "else", owner_limit[0], "execute")
    bp.connect(owner_limit[0], "then", owner_limit[1], "execute")
    bp.connect(owner_limit_branch, "then", staged[0], "execute")
    for left, right in zip(staged, staged[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(staged[-1], "then", validate, "execute")
    bp.connect(validate, "then", valid_branch, "execute")
    bp.connect(valid_branch, "else", invalid_record[0], "execute")
    bp.connect(invalid_record[0], "then", invalid_record[1], "execute")
    bp.connect(valid_branch, "then", encode, "execute")
    bp.connect(encode, "then", size_branch, "execute")
    bp.connect(size_branch, "else", size_limit[0], "execute")
    bp.connect(size_limit[0], "then", size_limit[1], "execute")
    bp.connect(size_branch, "then", prepare, "execute")
    bp.connect(prepare, "then", append_candidate, "execute")
    bp.connect(append_candidate, "then", persist, "execute")
    bp.connect(persist, "then", committed_branch, "execute")
    bp.connect(committed_branch, "then", add_id, "execute")
    for left, right in zip(
        (add_id, add_owner, add_visibility, add_updated, result_index, result_envelope, result_revision, result_has_revision),
        (add_owner, add_visibility, add_updated, result_index, result_envelope, result_revision, result_has_revision, result_document),
    ):
        bp.connect(left, "then", right, "execute")
    # committed=false terminates with the precise PersistenceUnavailable detail
    # authored by the accepted writer; it must never reach derived-index mutation.
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_private_create_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_private_create_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    string_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-string-trim-node-form.eddgraph"
    )
    templates["trim_string"] = bp.find_block(string_forms, r'MemberName="Trim"')
    nodes = build(bp, enc, validation, templates)
    enc.write(nodes, args.output_dir / "create-private-flypath-v1.eddgraph", paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / "create-private-flypath-v1-paste.eddgraph",
            paste=True,
        )


if __name__ == "__main__":
    main()
