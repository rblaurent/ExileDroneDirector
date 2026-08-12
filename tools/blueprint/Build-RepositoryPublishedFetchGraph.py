"""Build the immutable public playback fetch boundary.

Revision zero means "latest published"; a positive revision requests that
exact immutable snapshot.  The query never returns the stored record envelope
or draft and performs no persistence mutation.
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


def build(bp, enc, validation, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "FetchPublishedRevisionV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)
    find = b.call("FindRecordIndexV1", 512, 0)
    found_index = b.getter("ResultRecordIndexV1", "int", 512, 320)
    cache_index = b.setter("ScratchIndexV1", "int", 768, 0)
    clear_index = b.setter("ResultRecordIndexV1", "int", 1024, 0)
    enc.set_default(clear_index, "ResultRecordIndexV1", "-1")
    bp.connect(found_index, "ResultRecordIndexV1", cache_index, "ScratchIndexV1")

    cached_index = b.getter("ScratchIndexV1", "int", 1024, 320)
    envelopes = b.getter("ActiveRecordEnvelopesV1", "string", 1024, 480, array=True)
    visibilities = b.getter("ActiveVisibilitiesV1", "string", 1024, 640, array=True)
    envelope_index_valid = v.valid_index(
        envelopes, "ActiveRecordEnvelopesV1", cached_index, "ScratchIndexV1", "string", 1280, 320
    )
    visibility_index_valid = v.valid_index(
        visibilities, "ActiveVisibilitiesV1", cached_index, "ScratchIndexV1", "string", 1280, 480
    )
    index_aligned = v.bool_math("BooleanAND", 1536, 400)
    found = v.int_math("GreaterEqual_IntInt", 1536, 640, b_default="0")
    found_and_aligned = v.bool_math("BooleanAND", 1792, 480)
    aligned_branch = v.branch(2048, 0)
    bp.connect(envelope_index_valid, "ReturnValue", index_aligned, "A")
    bp.connect(visibility_index_valid, "ReturnValue", index_aligned, "B")
    bp.connect(cached_index, "ScratchIndexV1", found, "A")
    bp.connect(found, "ReturnValue", found_and_aligned, "A")
    bp.connect(index_aligned, "ReturnValue", found_and_aligned, "B")
    bp.connect(found_and_aligned, "ReturnValue", aligned_branch, "Condition")

    # Distinguish an ordinary miss from a corrupt derived index without exposing
    # private existence.  A negative index is always NotFound.
    found_branch = v.branch(2304, -160)
    bp.connect(found, "ReturnValue", found_branch, "Condition")

    derived_visibility = v.array_item(
        visibilities, "ActiveVisibilitiesV1", cached_index, "ScratchIndexV1", "string", 2304, 320
    )
    derived_public = v.string_math("EqualEqual_StrStr", 2560, 320, b_default="public")
    public_branch = v.branch(2816, 0)
    bp.connect(derived_visibility, "Output", derived_public, "A")
    bp.connect(derived_public, "ReturnValue", public_branch, "Condition")

    envelope = v.array_item(
        envelopes, "ActiveRecordEnvelopesV1", cached_index, "ScratchIndexV1", "string", 2816, 480
    )
    stage = b.setter("ScratchEncodedRecordV1", "string", 3072, 0)
    decode = b.call("DecodeRecordV1", 3328, 0)
    decoded = b.getter("ScratchValidV1", "bool", 3328, 320)
    decoded_branch = v.branch(3584, 0)
    validate = b.call("ValidateRecordV1", 3840, 0)
    valid = b.getter("ScratchValidV1", "bool", 3840, 320)
    valid_branch = v.branch(4096, 0)
    bp.connect(envelope, "Output", stage, "ScratchEncodedRecordV1")
    bp.connect(decoded, "ScratchValidV1", decoded_branch, "Condition")
    bp.connect(valid, "ScratchValidV1", valid_branch, "Condition")

    record_id = b.getter("ScratchRecordFlypathIdV1", "string", 4096, 320)
    request_id = b.getter("RequestFlypathIdV1", "string", 4096, 464)
    id_equal = v.string_math("EqualEqual_StrStr", 4352, 320)
    record_visibility = b.getter("ScratchRecordVisibilityV1", "string", 4096, 608)
    decoded_public = v.string_math("EqualEqual_StrStr", 4352, 608, b_default="public")
    has_published = b.getter("ScratchRecordHasPublishedRevisionV1", "bool", 4096, 752)
    id_and_public = v.bool_math("BooleanAND", 4608, 400)
    identity_valid = v.bool_math("BooleanAND", 4864, 480)
    identity_branch = v.branch(5120, 0)
    bp.connect(record_id, "ScratchRecordFlypathIdV1", id_equal, "A")
    bp.connect(request_id, "RequestFlypathIdV1", id_equal, "B")
    bp.connect(record_visibility, "ScratchRecordVisibilityV1", decoded_public, "A")
    bp.connect(id_equal, "ReturnValue", id_and_public, "A")
    bp.connect(decoded_public, "ReturnValue", id_and_public, "B")
    bp.connect(id_and_public, "ReturnValue", identity_valid, "A")
    bp.connect(has_published, "ScratchRecordHasPublishedRevisionV1", identity_valid, "B")
    bp.connect(identity_valid, "ReturnValue", identity_branch, "Condition")

    expected = b.getter("RequestExpectedRevisionV1", "int", 5120, 320)
    nonnegative = v.int_math("GreaterEqual_IntInt", 5376, 320, b_default="0")
    request_branch = v.branch(5632, 0)
    bp.connect(expected, "RequestExpectedRevisionV1", nonnegative, "A")
    bp.connect(nonnegative, "ReturnValue", request_branch, "Condition")

    published_revision = b.getter("ScratchRecordPublishedRevisionNumberV1", "int", 5632, 320)
    latest = v.int_math("EqualEqual_IntInt", 5888, 320, b_default="0")
    exact = v.int_math("EqualEqual_IntInt", 5888, 480)
    revision_match = v.bool_math("BooleanOR", 6144, 400)
    revision_branch = v.branch(6400, 0)
    bp.connect(expected, "RequestExpectedRevisionV1", latest, "A")
    bp.connect(expected, "RequestExpectedRevisionV1", exact, "A")
    bp.connect(published_revision, "ScratchRecordPublishedRevisionNumberV1", exact, "B")
    bp.connect(latest, "ReturnValue", revision_match, "A")
    bp.connect(exact, "ReturnValue", revision_match, "B")
    bp.connect(revision_match, "ReturnValue", revision_branch, "Condition")

    result_revision = b.setter("ResultCurrentRevisionV1", "int", 6656, 0)
    result_has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", 6912, 0)
    enc.set_default(result_has_revision, "ResultHasCurrentRevisionV1", "true")
    published_document = b.getter("ScratchRecordPublishedDocumentV1", "document", 6656, 320)
    result_document = b.setter("ResultPublishedDocumentV1", "document", 7168, 0)
    bp.connect(published_revision, "ScratchRecordPublishedRevisionNumberV1", result_revision, "ResultCurrentRevisionV1")
    bp.connect(published_document, "ScratchRecordPublishedDocumentV1", result_document, "ResultPublishedDocumentV1")

    not_found = error(enc, b, "NotFound", "FlypathNotFound", 2560, -480)
    misaligned = error(enc, b, "ValidationFailed", "MetadataIndexMisaligned", 2560, -320)
    decode_failed = error(enc, b, "ValidationFailed", "StoredRecordDecodeFailed", 3840, -320)
    stored_invalid = error(enc, b, "ValidationFailed", "StoredRecordInvalid", 4352, -320)
    identity_mismatch = error(enc, b, "ValidationFailed", "StoredRecordIndexMismatch", 5376, -320)
    invalid_request = error(enc, b, "ValidationFailed", "InvalidPublishedRevisionRequest", 5888, -320)
    revision_missing = error(enc, b, "NotFound", "PublishedRevisionNotFound", 6656, -320)

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", find, "execute")
    bp.connect(find, "then", cache_index, "execute")
    bp.connect(cache_index, "then", clear_index, "execute")
    bp.connect(clear_index, "then", aligned_branch, "execute")
    bp.connect(aligned_branch, "else", found_branch, "execute")
    bp.connect(found_branch, "else", not_found[0], "execute")
    bp.connect(not_found[0], "then", not_found[1], "execute")
    bp.connect(found_branch, "then", misaligned[0], "execute")
    bp.connect(misaligned[0], "then", misaligned[1], "execute")
    bp.connect(aligned_branch, "then", public_branch, "execute")
    bp.connect(public_branch, "else", not_found[0], "execute")
    bp.connect(public_branch, "then", stage, "execute")
    bp.connect(stage, "then", decode, "execute")
    bp.connect(decode, "then", decoded_branch, "execute")
    bp.connect(decoded_branch, "else", decode_failed[0], "execute")
    bp.connect(decode_failed[0], "then", decode_failed[1], "execute")
    bp.connect(decoded_branch, "then", validate, "execute")
    bp.connect(validate, "then", valid_branch, "execute")
    bp.connect(valid_branch, "else", stored_invalid[0], "execute")
    bp.connect(stored_invalid[0], "then", stored_invalid[1], "execute")
    bp.connect(valid_branch, "then", identity_branch, "execute")
    bp.connect(identity_branch, "else", identity_mismatch[0], "execute")
    bp.connect(identity_mismatch[0], "then", identity_mismatch[1], "execute")
    bp.connect(identity_branch, "then", request_branch, "execute")
    bp.connect(request_branch, "else", invalid_request[0], "execute")
    bp.connect(invalid_request[0], "then", invalid_request[1], "execute")
    bp.connect(request_branch, "then", revision_branch, "execute")
    bp.connect(revision_branch, "else", revision_missing[0], "execute")
    bp.connect(revision_missing[0], "then", revision_missing[1], "execute")
    bp.connect(revision_branch, "then", result_revision, "execute")
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
        "edd_published_fetch_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_published_fetch_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    nodes = build(bp, enc, validation, templates)
    enc.write(nodes, args.output_dir / "fetch-published-revision-v1.eddgraph", paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / "fetch-published-revision-v1-paste.eddgraph",
            paste=True,
        )


if __name__ == "__main__":
    main()
