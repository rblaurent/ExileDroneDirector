"""Semantic contracts for the canonical repository record encoder graphs."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_document_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-RepositoryDocumentEncoderContracts.py"
    spec = importlib.util.spec_from_file_location("edd_record_encoder_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load document encoder contracts: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def variable_node(c, nodes, name: str, *, setter: bool):
    class_marker = "K2Node_VariableSet" if setter else "K2Node_VariableGet"
    matches = [
        node
        for node in nodes.values()
        if class_marker in node.node_class and f'MemberName="{name}"' in node.text
    ]
    c.require(
        len(matches) == 1,
        f"Expected one {'setter' if setter else 'getter'} for {name}; found {len(matches)}",
    )
    return matches[0]


def function_call(c, nodes, name: str):
    matches = [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class
        and re.search(rf'MemberName="{re.escape(name)}"', node.text)
    ]
    c.require(len(matches) == 1, f"Expected one call to {name}; found {len(matches)}")
    return matches[0]


def branch_node(c, nodes):
    matches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(matches) == 1, f"Expected one branch; found {len(matches)}")
    return matches[0]


def assert_no_orphans(c, nodes) -> None:
    c.require(
        "bOrphanedPin=True" not in "\n".join(node.text for node in nodes.values()),
        "Record encoder contains orphaned pins",
    )


def assert_published(c, e, nodes, *, paste: bool) -> None:
    e.assert_closed(
        c,
        nodes,
        16 if paste else 17,
        None if paste else "EncodeRecordPublishedFieldsV1",
    )
    branch = branch_node(c, nodes)
    has_value = variable_node(c, nodes, "ScratchRecordHasPublishedRevisionV1", setter=False)
    c.require_link(
        has_value,
        "ScratchRecordHasPublishedRevisionV1",
        branch,
        "Condition",
        "Published-presence branch changed",
    )
    if paste:
        c.require(not branch.pins["execute"].links, "Paste body must expose the published branch")
    else:
        entry = e.one(c, nodes, 'FunctionReference=(MemberName="EncodeRecordPublishedFieldsV1")')
        c.require_link(entry, "then", branch, "execute", "Published helper entry changed")

    stage_document = variable_node(c, nodes, "ScratchDocumentV1", setter=True)
    encode_document = function_call(c, nodes, "EncodeDocumentV1")
    store_document = variable_node(c, nodes, "ScratchDocumentJsonV1", setter=True)
    decode_document = function_call(c, nodes, "DecodeJson")
    set_published = e.field_node(c, nodes, "SetObjectField", "published")
    set_revision = e.field_node(c, nodes, "SetNumberField", "publishedRevisionNumber")
    true_chain = [stage_document, encode_document, store_document, decode_document, set_published, set_revision]
    c.require_link(branch, "then", true_chain[0], "execute", "Published true branch changed")
    e.require_exec_chain(c, true_chain)

    source_document = variable_node(c, nodes, "ScratchRecordPublishedDocumentV1", setter=False)
    c.require_link(
        source_document,
        "ScratchRecordPublishedDocumentV1",
        stage_document,
        "ScratchDocumentV1",
        "Published document staging changed",
    )
    encoded_document = variable_node(c, nodes, "ScratchEncodedDocumentV1", setter=False)
    c.require_link(
        encoded_document,
        "ScratchEncodedDocumentV1",
        decode_document,
        "JsonString",
        "Published nested-document decode changed",
    )
    revision_source = variable_node(
        c, nodes, "ScratchRecordPublishedRevisionNumberV1", setter=False
    )
    conversion = function_call(c, nodes, "Conv_IntToDouble")
    c.require_link(
        revision_source,
        "ScratchRecordPublishedRevisionNumberV1",
        conversion,
        "InInt",
        "Published revision conversion input changed",
    )
    c.require_link(
        conversion,
        "ReturnValue",
        set_revision,
        "Number",
        "Published revision conversion output changed",
    )

    null_published = e.field_node(c, nodes, "SetFieldNull", "published")
    null_revision = e.field_node(c, nodes, "SetFieldNull", "publishedRevisionNumber")
    c.require_link(branch, "else", null_published, "execute", "Published null branch changed")
    c.require_link(
        null_published,
        "then",
        null_revision,
        "execute",
        "Published optional pair must be null together",
    )
    assert_no_orphans(c, nodes)


def assert_source(c, e, nodes, *, paste: bool) -> None:
    e.assert_closed(
        c,
        nodes,
        16 if paste else 17,
        None if paste else "EncodeRecordSourceAttributionV1",
    )
    branch = branch_node(c, nodes)
    has_value = variable_node(c, nodes, "ScratchRecordHasSourceAttributionV1", setter=False)
    c.require_link(
        has_value,
        "ScratchRecordHasSourceAttributionV1",
        branch,
        "Condition",
        "Attribution-presence branch changed",
    )
    if paste:
        c.require(not branch.pins["execute"].links, "Paste body must expose the source branch")
    else:
        entry = e.one(c, nodes, 'FunctionReference=(MemberName="EncodeRecordSourceAttributionV1")')
        c.require_link(entry, "then", branch, "execute", "Attribution helper entry changed")

    store = variable_node(c, nodes, "ScratchAttributionJsonV1", setter=True)
    fields = [
        e.field_node(c, nodes, "SetStringField", "creatorDisplayName"),
        e.field_node(c, nodes, "SetStringField", "flypathId"),
        e.field_node(c, nodes, "SetNumberField", "revisionNumber"),
        e.field_node(c, nodes, "SetStringField", "title"),
        e.field_node(c, nodes, "SetObjectField", "sourceAttribution"),
    ]
    c.require_link(branch, "then", store, "execute", "Attribution true branch changed")
    e.require_exec_chain(c, [store, *fields])
    revision_source = variable_node(c, nodes, "ScratchRecordSourceRevisionNumberV1", setter=False)
    conversion = function_call(c, nodes, "Conv_IntToDouble")
    c.require_link(
        revision_source,
        "ScratchRecordSourceRevisionNumberV1",
        conversion,
        "InInt",
        "Source revision conversion input changed",
    )
    c.require_link(
        conversion,
        "ReturnValue",
        fields[2],
        "Number",
        "Source revision conversion output changed",
    )
    null_source = e.field_node(c, nodes, "SetFieldNull", "sourceAttribution")
    c.require_link(branch, "else", null_source, "execute", "Attribution null branch changed")
    assert_no_orphans(c, nodes)


def assert_record(c, e, nodes, *, paste: bool) -> None:
    e.assert_closed(c, nodes, 43 if paste else 44, None if paste else "EncodeRecordV1")
    record_store = variable_node(c, nodes, "ScratchRecordJsonV1", setter=True)
    envelope_store = variable_node(c, nodes, "ScratchEnvelopeJsonV1", setter=True)
    created = e.field_node(c, nodes, "SetStringField", "createdUtc")
    description = e.field_node(c, nodes, "SetStringField", "description")
    stage_document = variable_node(c, nodes, "ScratchDocumentV1", setter=True)
    encode_document = function_call(c, nodes, "EncodeDocumentV1")
    document_store = variable_node(c, nodes, "ScratchDocumentJsonV1", setter=True)
    decode_document = function_call(c, nodes, "DecodeJson")
    draft = e.field_node(c, nodes, "SetObjectField", "draft")
    draft_revision = e.field_node(c, nodes, "SetNumberField", "draftRevisionNumber")
    flypath = e.field_node(c, nodes, "SetStringField", "flypathId")
    owner_account = e.field_node(c, nodes, "SetStringField", "ownerAccountId")
    owner_display = e.field_node(c, nodes, "SetStringField", "ownerDisplayName")
    published = function_call(c, nodes, "EncodeRecordPublishedFieldsV1")
    region = e.field_node(c, nodes, "SetStringField", "regionId")
    source = function_call(c, nodes, "EncodeRecordSourceAttributionV1")
    title = e.field_node(c, nodes, "SetStringField", "title")
    updated = e.field_node(c, nodes, "SetStringField", "updatedUtc")
    visibility = e.field_node(c, nodes, "SetStringField", "visibility")
    integrity = e.field_node(c, nodes, "SetStringField", "integrityMode")
    record = e.field_node(c, nodes, "SetObjectField", "record")
    content_hash = e.field_node(c, nodes, "SetStringField", "recordContentHash")
    repository_version = e.field_node(c, nodes, "SetNumberField", "repositorySchemaVersion")
    encoded = variable_node(c, nodes, "ScratchEncodedRecordV1", setter=True)

    canonical_chain = [
        record_store,
        envelope_store,
        created,
        description,
        stage_document,
        encode_document,
        document_store,
        decode_document,
        draft,
        draft_revision,
        flypath,
        owner_account,
        owner_display,
        published,
        region,
        source,
        title,
        updated,
        visibility,
        integrity,
        record,
        content_hash,
        repository_version,
        encoded,
    ]
    e.require_exec_chain(c, canonical_chain)
    if paste:
        c.require(not record_store.pins["execute"].links, "Paste body must expose record root setter")
    else:
        entry = e.one(c, nodes, 'FunctionReference=(MemberName="EncodeRecordV1")')
        c.require_link(entry, "then", record_store, "execute", "Record encoder entry changed")

    draft_source = variable_node(c, nodes, "ScratchRecordDraftDocumentV1", setter=False)
    c.require_link(
        draft_source,
        "ScratchRecordDraftDocumentV1",
        stage_document,
        "ScratchDocumentV1",
        "Draft document staging changed",
    )
    encoded_document = variable_node(c, nodes, "ScratchEncodedDocumentV1", setter=False)
    c.require_link(
        encoded_document,
        "ScratchEncodedDocumentV1",
        decode_document,
        "JsonString",
        "Draft nested-document decode changed",
    )
    draft_revision_source = variable_node(
        c, nodes, "ScratchRecordDraftRevisionNumberV1", setter=False
    )
    conversion = function_call(c, nodes, "Conv_IntToDouble")
    c.require_link(
        draft_revision_source,
        "ScratchRecordDraftRevisionNumberV1",
        conversion,
        "InInt",
        "Draft revision conversion input changed",
    )
    c.require_link(
        conversion,
        "ReturnValue",
        draft_revision,
        "Number",
        "Draft revision conversion output changed",
    )
    c.require('DefaultValue="structural-v1"' in e.pin_line(integrity, "StringValue"), "Integrity mode changed")
    c.require('DefaultValue="1.0"' in e.pin_line(repository_version, "Number"), "Repository schema version changed")
    c.require("LinkedTo=" not in e.pin_line(content_hash, "StringValue"), "Reserved record hash must remain empty")
    encode_json = function_call(c, nodes, "EncodeJson")
    c.require_link(
        encode_json,
        "ReturnValue",
        encoded,
        "ScratchEncodedRecordV1",
        "Terminal record text commit changed",
    )
    assert_no_orphans(c, nodes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument(
        "--only",
        choices=("all", "published", "source", "record"),
        default="all",
    )
    args = parser.parse_args()
    e = load_document_contracts(args.project_root)
    c = e.load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    if args.only in ("all", "published"):
        assert_published(
            c,
            e,
            c.parse_graph(args.input_dir / f"encode-record-published-fields-v1{suffix}.eddgraph"),
            paste=args.paste,
        )
    if args.only in ("all", "source"):
        assert_source(
            c,
            e,
            c.parse_graph(args.input_dir / f"encode-record-source-attribution-v1{suffix}.eddgraph"),
            paste=args.paste,
        )
    if args.only in ("all", "record"):
        assert_record(
            c,
            e,
            c.parse_graph(args.input_dir / f"encode-record-v1{suffix}.eddgraph"),
            paste=args.paste,
        )
    print("Repository record encoder graph contracts passed")


if __name__ == "__main__":
    main()
