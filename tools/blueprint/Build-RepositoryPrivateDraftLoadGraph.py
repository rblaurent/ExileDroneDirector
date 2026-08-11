"""Build the owner-only private draft read boundary for the repository actor."""

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
    v = validation.ValidationBuilder(bp, enc, templates, "LoadDraftV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)
    find = b.call("FindRecordIndexV1", 512, 0)
    index = b.getter("ResultRecordIndexV1", "int", 512, 320)
    envelopes = b.getter("ActiveRecordEnvelopesV1", "string", 512, 480, array=True)
    index_valid = v.valid_index(
        envelopes,
        "ActiveRecordEnvelopesV1",
        index,
        "ResultRecordIndexV1",
        "string",
        768,
        320,
    )
    found = v.branch(1024, 0)

    owners = b.getter("ActiveOwnerAccountIdsV1", "string", 1024, 480, array=True)
    owner = v.array_item(
        owners,
        "ActiveOwnerAccountIdsV1",
        index,
        "ResultRecordIndexV1",
        "string",
        1280,
        320,
    )
    requester = b.getter("RequestRequesterAccountIdV1", "string", 1280, 480)
    owns = v.string_math("EqualEqual_StrStr", 1536, 320)
    owner_branch = v.branch(1792, 0)

    envelope = v.array_item(
        envelopes,
        "ActiveRecordEnvelopesV1",
        index,
        "ResultRecordIndexV1",
        "string",
        1792,
        480,
    )
    stage = b.setter("ScratchEncodedRecordV1", "string", 2048, 0)
    decode = b.call("DecodeRecordV1", 2304, 0)
    decoded = b.getter("ScratchValidV1", "bool", 2304, 320)
    decoded_branch = v.branch(2560, 0)
    validate = b.call("ValidateRecordV1", 2816, 0)
    validated = b.getter("ScratchValidV1", "bool", 2816, 320)
    validated_branch = v.branch(3072, 0)

    result_envelope = b.setter("ResultRecordEnvelopeV1", "string", 3328, 0)
    revision = b.getter("ScratchRecordDraftRevisionNumberV1", "int", 3328, 320)
    result_revision = b.setter("ResultCurrentRevisionV1", "int", 3584, 0)
    has_revision = b.setter("ResultHasCurrentRevisionV1", "bool", 3840, 0)
    enc.set_default(has_revision, "ResultHasCurrentRevisionV1", "true")
    document = b.getter("ScratchRecordDraftDocumentV1", "document", 3840, 320)
    result_document = b.setter("ResultDraftDocumentV1", "document", 4096, 0)

    not_found = error(enc, b, "NotFound", "FlypathNotFound", 1280, -320)
    forbidden = error(enc, b, "Forbidden", "OwnerRequired", 2048, -320)
    decode_failed = error(enc, b, "ValidationFailed", "StoredRecordDecodeFailed", 2816, -320)
    validation_failed = error(enc, b, "ValidationFailed", "StoredRecordInvalid", 3328, -320)

    bp.connect(index_valid, "ReturnValue", found, "Condition")
    bp.connect(owner, "Output", owns, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", owns, "B")
    bp.connect(owns, "ReturnValue", owner_branch, "Condition")
    bp.connect(envelope, "Output", stage, "ScratchEncodedRecordV1")
    bp.connect(decoded, "ScratchValidV1", decoded_branch, "Condition")
    bp.connect(validated, "ScratchValidV1", validated_branch, "Condition")
    bp.connect(envelope, "Output", result_envelope, "ResultRecordEnvelopeV1")
    bp.connect(revision, "ScratchRecordDraftRevisionNumberV1", result_revision, "ResultCurrentRevisionV1")
    bp.connect(document, "ScratchRecordDraftDocumentV1", result_document, "ResultDraftDocumentV1")

    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", find, "execute")
    bp.connect(find, "then", found, "execute")
    bp.connect(found, "else", not_found[0], "execute")
    bp.connect(not_found[0], "then", not_found[1], "execute")
    bp.connect(found, "then", owner_branch, "execute")
    bp.connect(owner_branch, "else", forbidden[0], "execute")
    bp.connect(forbidden[0], "then", forbidden[1], "execute")
    bp.connect(owner_branch, "then", stage, "execute")
    bp.connect(stage, "then", decode, "execute")
    bp.connect(decode, "then", decoded_branch, "execute")
    bp.connect(decoded_branch, "else", decode_failed[0], "execute")
    bp.connect(decode_failed[0], "then", decode_failed[1], "execute")
    bp.connect(decoded_branch, "then", validate, "execute")
    bp.connect(validate, "then", validated_branch, "execute")
    bp.connect(validated_branch, "else", validation_failed[0], "execute")
    bp.connect(validation_failed[0], "then", validation_failed[1], "execute")
    bp.connect(validated_branch, "then", result_envelope, "execute")
    bp.connect(result_envelope, "then", result_revision, "execute")
    bp.connect(result_revision, "then", has_revision, "execute")
    bp.connect(has_revision, "then", result_document, "execute")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_private_load_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_private_load_validation_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    nodes = build(bp, enc, validation, templates)
    enc.write(nodes, args.output_dir / "load-draft-v1.eddgraph", paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / "load-draft-v1-paste.eddgraph",
            paste=True,
        )


if __name__ == "__main__":
    main()
