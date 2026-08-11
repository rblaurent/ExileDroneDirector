"""Generate canonical Blueprint record-envelope encoder graphs.

The Enhanced DevKit cannot author reliable Blueprint function parameters from
Python, so these functions consume and publish the repository actor's explicit
``Scratch*V1`` staging members.  Optional publication and source-attribution
fields live in small helpers: each helper owns one branch and returns normally
to ``EncodeRecordV1`` without requiring an unsafe execution-flow merge.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


def load_encoder(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_record_encoder_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load document encoder helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_templates(project_root: Path, bp, enc) -> dict[str, str]:
    templates = enc.load_templates(project_root, bp)
    root = project_root / "tools" / "blueprint"
    json_forms = bp.read_blocks(root / "templates" / "repository-json-node-forms.eddgraph")
    waypoint_sync = bp.read_blocks(root / "snippets" / "sync-draft-waypoints-v1.eddgraph")
    templates.update(
        {
            "branch": bp.find_block(
                waypoint_sync,
                r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse ',
            ),
            "json_SetFieldNull": bp.find_block(json_forms, r'MemberName="SetFieldNull"'),
            "json_DecodeJson": bp.find_block(json_forms, r'MemberName="DecodeJson"'),
        }
    )
    return templates


def connect_exec_chain(bp, nodes) -> None:
    for left, right in zip(nodes, nodes[1:]):
        bp.connect(left, "then", right, "execute")


def build_published_fields(bp, templates: dict[str, str], enc):
    b = enc.Builder(bp, templates, "EncodeRecordPublishedFieldsV1")
    has_published = b.getter("ScratchRecordHasPublishedRevisionV1", "bool", 0, 360)
    branch = b.add("published_branch", "branch", 256, 0)
    bp.connect(has_published, "ScratchRecordHasPublishedRevisionV1", branch, "Condition")
    bp.connect(b.entry, "then", branch, "execute")

    record_json = b.getter("ScratchRecordJsonV1", "json", 1280, 640)

    published_document = b.getter(
        "ScratchRecordPublishedDocumentV1", "document", 512, 360
    )
    stage_document = b.setter("ScratchDocumentV1", "document", 512, 0)
    encode_document = b.call("EncodeDocumentV1", 768, 0)
    document_object = b.json("ConstructJsonObject", 768, 400)
    store_document_object = b.setter("ScratchDocumentJsonV1", "json", 1024, 0)
    encoded_document = b.getter("ScratchEncodedDocumentV1", "string", 1024, 400)
    decode_document = b.json("DecodeJson", 1280, 0)
    set_published = b.json("SetObjectField", 1536, 0)
    enc.field(set_published, "published")
    published_revision = b.getter(
        "ScratchRecordPublishedRevisionNumberV1", "int", 1536, 400
    )
    revision_number = b.add("published_revision_number", "int_to_double", 1792, 400)
    set_revision = b.json("SetNumberField", 1792, 0)
    enc.field(set_revision, "publishedRevisionNumber")

    bp.connect(published_document, "ScratchRecordPublishedDocumentV1", stage_document, "ScratchDocumentV1")
    bp.connect(document_object, "ReturnValue", store_document_object, "ScratchDocumentJsonV1")
    bp.connect(store_document_object, "Output_Get", decode_document, "self")
    bp.connect(encoded_document, "ScratchEncodedDocumentV1", decode_document, "JsonString")
    bp.connect(record_json, "ScratchRecordJsonV1", set_published, "self")
    bp.connect(store_document_object, "Output_Get", set_published, "JsonObject")
    bp.connect(record_json, "ScratchRecordJsonV1", set_revision, "self")
    bp.connect(published_revision, "ScratchRecordPublishedRevisionNumberV1", revision_number, "InInt")
    bp.connect(revision_number, "ReturnValue", set_revision, "Number")
    bp.connect(branch, "then", stage_document, "execute")
    connect_exec_chain(
        bp,
        [stage_document, encode_document, store_document_object, decode_document, set_published, set_revision],
    )

    null_published = b.json("SetFieldNull", 512, 800)
    null_revision = b.json("SetFieldNull", 768, 800)
    enc.field(null_published, "published")
    enc.field(null_revision, "publishedRevisionNumber")
    bp.connect(record_json, "ScratchRecordJsonV1", null_published, "self")
    bp.connect(record_json, "ScratchRecordJsonV1", null_revision, "self")
    bp.connect(branch, "else", null_published, "execute")
    bp.connect(null_published, "then", null_revision, "execute")
    return b.nodes


def build_source_attribution(bp, templates: dict[str, str], enc):
    b = enc.Builder(bp, templates, "EncodeRecordSourceAttributionV1")
    has_source = b.getter("ScratchRecordHasSourceAttributionV1", "bool", 0, 360)
    branch = b.add("source_branch", "branch", 256, 0)
    bp.connect(has_source, "ScratchRecordHasSourceAttributionV1", branch, "Condition")
    bp.connect(b.entry, "then", branch, "execute")

    record_json = b.getter("ScratchRecordJsonV1", "json", 1536, 640)
    attribution_object = b.json("ConstructJsonObject", 512, 400)
    store_attribution = b.setter("ScratchAttributionJsonV1", "json", 512, 0)
    creator = b.json("SetStringField", 768, 0)
    flypath = b.json("SetStringField", 1024, 0)
    revision = b.json("SetNumberField", 1280, 0)
    title = b.json("SetStringField", 1536, 0)
    set_source = b.json("SetObjectField", 1792, 0)
    for node, field_name in (
        (creator, "creatorDisplayName"),
        (flypath, "flypathId"),
        (revision, "revisionNumber"),
        (title, "title"),
        (set_source, "sourceAttribution"),
    ):
        enc.field(node, field_name)

    source_creator = b.getter(
        "ScratchRecordSourceCreatorDisplayNameV1", "string", 768, 400
    )
    source_flypath = b.getter("ScratchRecordSourceFlypathIdV1", "string", 1024, 400)
    source_revision = b.getter("ScratchRecordSourceRevisionNumberV1", "int", 1280, 400)
    revision_number = b.add("source_revision_number", "int_to_double", 1280, 560)
    source_title = b.getter("ScratchRecordSourceTitleV1", "string", 1536, 400)

    bp.connect(attribution_object, "ReturnValue", store_attribution, "ScratchAttributionJsonV1")
    for node in (creator, flypath, revision, title):
        bp.connect(store_attribution, "Output_Get", node, "self")
    bp.connect(source_creator, "ScratchRecordSourceCreatorDisplayNameV1", creator, "StringValue")
    bp.connect(source_flypath, "ScratchRecordSourceFlypathIdV1", flypath, "StringValue")
    bp.connect(source_revision, "ScratchRecordSourceRevisionNumberV1", revision_number, "InInt")
    bp.connect(revision_number, "ReturnValue", revision, "Number")
    bp.connect(source_title, "ScratchRecordSourceTitleV1", title, "StringValue")
    bp.connect(record_json, "ScratchRecordJsonV1", set_source, "self")
    bp.connect(store_attribution, "Output_Get", set_source, "JsonObject")
    bp.connect(branch, "then", store_attribution, "execute")
    connect_exec_chain(bp, [store_attribution, creator, flypath, revision, title, set_source])

    null_source = b.json("SetFieldNull", 512, 800)
    enc.field(null_source, "sourceAttribution")
    bp.connect(record_json, "ScratchRecordJsonV1", null_source, "self")
    bp.connect(branch, "else", null_source, "execute")
    return b.nodes


def build_record(bp, templates: dict[str, str], enc):
    b = enc.Builder(bp, templates, "EncodeRecordV1")
    record_object = b.json("ConstructJsonObject", 0, 400)
    store_record = b.setter("ScratchRecordJsonV1", "json", 0, 0)
    envelope_object = b.json("ConstructJsonObject", 256, 400)
    store_envelope = b.setter("ScratchEnvelopeJsonV1", "json", 256, 0)
    bp.connect(record_object, "ReturnValue", store_record, "ScratchRecordJsonV1")
    bp.connect(envelope_object, "ReturnValue", store_envelope, "ScratchEnvelopeJsonV1")

    record_json = b.getter("ScratchRecordJsonV1", "json", 2048, 720)
    scalar_specs = (
        ("createdUtc", "ScratchRecordCreatedUtcV1"),
        ("description", "ScratchRecordDescriptionV1"),
    )
    fields = []
    x = 512
    for field_name, variable_name in scalar_specs:
        node = b.json("SetStringField", x, 0)
        enc.field(node, field_name)
        value = b.getter(variable_name, "string", x, 400)
        bp.connect(record_json, "ScratchRecordJsonV1", node, "self")
        bp.connect(value, variable_name, node, "StringValue")
        fields.append(node)
        x += 256

    draft_document = b.getter("ScratchRecordDraftDocumentV1", "document", x, 400)
    stage_document = b.setter("ScratchDocumentV1", "document", x, 0)
    bp.connect(draft_document, "ScratchRecordDraftDocumentV1", stage_document, "ScratchDocumentV1")
    x += 256
    encode_document = b.call("EncodeDocumentV1", x, 0)
    x += 256
    document_object = b.json("ConstructJsonObject", x, 400)
    store_document = b.setter("ScratchDocumentJsonV1", "json", x, 0)
    bp.connect(document_object, "ReturnValue", store_document, "ScratchDocumentJsonV1")
    x += 256
    encoded_document = b.getter("ScratchEncodedDocumentV1", "string", x, 400)
    decode_document = b.json("DecodeJson", x, 0)
    bp.connect(store_document, "Output_Get", decode_document, "self")
    bp.connect(encoded_document, "ScratchEncodedDocumentV1", decode_document, "JsonString")
    x += 256
    set_draft = b.json("SetObjectField", x, 0)
    enc.field(set_draft, "draft")
    bp.connect(record_json, "ScratchRecordJsonV1", set_draft, "self")
    bp.connect(store_document, "Output_Get", set_draft, "JsonObject")
    x += 256

    draft_revision = b.json("SetNumberField", x, 0)
    enc.field(draft_revision, "draftRevisionNumber")
    draft_revision_value = b.getter("ScratchRecordDraftRevisionNumberV1", "int", x, 400)
    draft_revision_number = b.add("draft_revision_number", "int_to_double", x, 560)
    bp.connect(record_json, "ScratchRecordJsonV1", draft_revision, "self")
    bp.connect(draft_revision_value, "ScratchRecordDraftRevisionNumberV1", draft_revision_number, "InInt")
    bp.connect(draft_revision_number, "ReturnValue", draft_revision, "Number")
    x += 256

    for field_name, variable_name in (
        ("flypathId", "ScratchRecordFlypathIdV1"),
        ("ownerAccountId", "ScratchRecordOwnerAccountIdV1"),
        ("ownerDisplayName", "ScratchRecordOwnerDisplayNameV1"),
    ):
        node = b.json("SetStringField", x, 0)
        enc.field(node, field_name)
        value = b.getter(variable_name, "string", x, 400)
        bp.connect(record_json, "ScratchRecordJsonV1", node, "self")
        bp.connect(value, variable_name, node, "StringValue")
        fields.append(node)
        x += 256

    published = b.call("EncodeRecordPublishedFieldsV1", x, 0)
    x += 256
    region = b.json("SetStringField", x, 0)
    enc.field(region, "regionId")
    region_value = b.getter("ScratchRecordRegionIdV1", "string", x, 400)
    bp.connect(record_json, "ScratchRecordJsonV1", region, "self")
    bp.connect(region_value, "ScratchRecordRegionIdV1", region, "StringValue")
    x += 256
    source = b.call("EncodeRecordSourceAttributionV1", x, 0)
    x += 256

    tail_fields = []
    for field_name, variable_name in (
        ("title", "ScratchRecordTitleV1"),
        ("updatedUtc", "ScratchRecordUpdatedUtcV1"),
        ("visibility", "ScratchRecordVisibilityV1"),
    ):
        node = b.json("SetStringField", x, 0)
        enc.field(node, field_name)
        value = b.getter(variable_name, "string", x, 400)
        bp.connect(record_json, "ScratchRecordJsonV1", node, "self")
        bp.connect(value, variable_name, node, "StringValue")
        tail_fields.append(node)
        x += 256

    envelope_json = b.getter("ScratchEnvelopeJsonV1", "json", x, 720)
    integrity = b.json("SetStringField", x, 0)
    enc.field(integrity, "integrityMode")
    enc.set_default(integrity, "StringValue", "structural-v1")
    bp.connect(envelope_json, "ScratchEnvelopeJsonV1", integrity, "self")
    x += 256
    set_record = b.json("SetObjectField", x, 0)
    enc.field(set_record, "record")
    bp.connect(envelope_json, "ScratchEnvelopeJsonV1", set_record, "self")
    bp.connect(record_json, "ScratchRecordJsonV1", set_record, "JsonObject")
    x += 256
    content_hash = b.json("SetStringField", x, 0)
    enc.field(content_hash, "recordContentHash")
    enc.set_default(content_hash, "StringValue", "")
    bp.connect(envelope_json, "ScratchEnvelopeJsonV1", content_hash, "self")
    x += 256
    repository_version = b.json("SetNumberField", x, 0)
    enc.field(repository_version, "repositorySchemaVersion")
    enc.set_default(repository_version, "Number", "1.0")
    bp.connect(envelope_json, "ScratchEnvelopeJsonV1", repository_version, "self")
    x += 256
    encode_envelope = b.json("EncodeJson", x, 400)
    store_encoded = b.setter("ScratchEncodedRecordV1", "string", x + 256, 0)
    bp.connect(envelope_json, "ScratchEnvelopeJsonV1", encode_envelope, "self")
    bp.connect(encode_envelope, "ReturnValue", store_encoded, "ScratchEncodedRecordV1")

    chain = [
        store_record,
        store_envelope,
        *fields[:2],
        stage_document,
        encode_document,
        store_document,
        decode_document,
        set_draft,
        draft_revision,
        *fields[2:],
        published,
        region,
        source,
        *tail_fields,
        integrity,
        set_record,
        content_hash,
        repository_version,
        store_encoded,
    ]
    bp.connect(b.entry, "then", chain[0], "execute")
    connect_exec_chain(bp, chain)
    return b.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()

    enc = load_encoder(args.project_root)
    bp = enc.load_helpers(args.project_root)
    templates = load_templates(args.project_root, bp, enc)
    graphs = {
        "encode-record-published-fields-v1.eddgraph": build_published_fields(bp, templates, enc),
        "encode-record-source-attribution-v1.eddgraph": build_source_attribution(bp, templates, enc),
        "encode-record-v1.eddgraph": build_record(bp, templates, enc),
    }
    for filename, nodes in graphs.items():
        enc.write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            enc.write(nodes, args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"), paste=True)


if __name__ == "__main__":
    main()
