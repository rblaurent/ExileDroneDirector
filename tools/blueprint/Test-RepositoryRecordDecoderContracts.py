"""Semantic contracts for strict staged repository record decoders."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_decoder_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-RepositoryDocumentDecoderContracts.py"
    spec = importlib.util.spec_from_file_location("edd_record_decoder_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load decoder contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def variable_nodes(nodes, name: str, node_class: str):
    return [
        node
        for node in nodes.values()
        if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text
    ]


def one_variable(c, nodes, name: str, node_class: str):
    matches = variable_nodes(nodes, name, node_class)
    c.require(len(matches) == 1, f"Expected one {node_class} for {name}; found {len(matches)}")
    return matches[0]


def branch_node(c, nodes):
    matches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(matches) == 1, f"Expected one branch; found {len(matches)}")
    return matches[0]


def call_node(c, nodes, name: str):
    matches = [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class
        and re.search(rf'MemberName="{re.escape(name)}"', node.text)
    ]
    c.require(len(matches) == 1, f"Expected one call to {name}; found {len(matches)}")
    return matches[0]


def default_is(node, pin_name: str, expected: str) -> bool:
    pin = node.pins[pin_name].body
    match = re.search(r'DefaultValue="([^"]*)"', pin)
    actual = match.group(1) if match else ""
    return actual.lower() == expected.lower()


def bool_stages(c, nodes, variable_name: str):
    setters = variable_nodes(nodes, variable_name, "K2Node_VariableSet")
    c.require(len(setters) == 2, f"Expected true/false setters for {variable_name}")
    false_setters = [node for node in setters if default_is(node, variable_name, "false")]
    true_setters = [node for node in setters if default_is(node, variable_name, "true")]
    c.require(len(false_setters) == 1, f"Missing false stage for {variable_name}")
    c.require(len(true_setters) == 1, f"Missing true stage for {variable_name}")
    return false_setters[0], true_setters[0]


def require_entry(c, d, nodes, name: str, first, *, paste: bool) -> None:
    if paste:
        c.require(not first.pins["execute"].links, f"Paste body must expose {name} entry seam")
    else:
        entry = d.one(c, nodes, f'FunctionReference=(MemberName="{name}")')
        c.require_link(entry, "then", first, "execute", f"{name} native entry changed")


def assert_null_probe(c, d, nodes, record, field_name: str, branch):
    get_field = d.field_node(c, nodes, "GetField", field_name)
    is_null = call_node(c, nodes, "IsNull")
    c.require_link(record, "ScratchRecordJsonV1", get_field, "self", f"{field_name} probe source changed")
    c.require_link(get_field, "ReturnValue", is_null, "self", f"{field_name} null probe changed")
    c.require_link(is_null, "ReturnValue", branch, "Condition", f"{field_name} branch condition changed")


def assert_published(c, d, nodes, *, paste: bool) -> None:
    d.assert_closed(c, nodes, 15 if paste else 16, None if paste else "DecodeRecordPublishedFieldsV1")
    record = one_variable(c, nodes, "ScratchRecordJsonV1", "K2Node_VariableGet")
    branch = branch_node(c, nodes)
    assert_null_probe(c, d, nodes, record, "published", branch)
    require_entry(c, d, nodes, "DecodeRecordPublishedFieldsV1", branch, paste=paste)

    absent, present = bool_stages(c, nodes, "ScratchRecordHasPublishedRevisionV1")
    c.require_link(branch, "then", absent, "execute", "Published null branch changed")
    c.require_link(branch, "else", present, "execute", "Published object branch changed")

    published = d.field_node(c, nodes, "GetObjectField", "published")
    encode_document = call_node(c, nodes, "EncodeJson")
    encoded_document = one_variable(c, nodes, "ScratchEncodedDocumentV1", "K2Node_VariableSet")
    decode_document = call_node(c, nodes, "DecodeDocumentV1")
    decoded_document = one_variable(c, nodes, "ScratchDocumentV1", "K2Node_VariableGet")
    store_document = one_variable(c, nodes, "ScratchRecordPublishedDocumentV1", "K2Node_VariableSet")
    revision = d.field_node(c, nodes, "GetNumberField", "publishedRevisionNumber")
    conversion = call_node(c, nodes, "FTrunc")
    store_revision = one_variable(
        c, nodes, "ScratchRecordPublishedRevisionNumberV1", "K2Node_VariableSet"
    )

    c.require_link(record, "ScratchRecordJsonV1", published, "self", "Published object source changed")
    c.require_link(published, "ReturnValue", encode_document, "self", "Published object encoding changed")
    c.require_link(
        encode_document,
        "ReturnValue",
        encoded_document,
        "ScratchEncodedDocumentV1",
        "Published document staging changed",
    )
    c.require_link(
        decoded_document,
        "ScratchDocumentV1",
        store_document,
        "ScratchRecordPublishedDocumentV1",
        "Published document result changed",
    )
    c.require_link(record, "ScratchRecordJsonV1", revision, "self", "Published revision source changed")
    c.require_link(revision, "ReturnValue", conversion, "A", "Published revision conversion changed")
    c.require_link(
        conversion,
        "ReturnValue",
        store_revision,
        "ScratchRecordPublishedRevisionNumberV1",
        "Published revision staging changed",
    )
    d.require_exec_chain(
        c,
        [present, encoded_document, decode_document, store_document, store_revision],
    )


def assert_source(c, d, nodes, *, paste: bool) -> None:
    d.assert_closed(c, nodes, 18 if paste else 19, None if paste else "DecodeRecordSourceAttributionV1")
    record = one_variable(c, nodes, "ScratchRecordJsonV1", "K2Node_VariableGet")
    branch = branch_node(c, nodes)
    assert_null_probe(c, d, nodes, record, "sourceAttribution", branch)
    require_entry(c, d, nodes, "DecodeRecordSourceAttributionV1", branch, paste=paste)

    absent, present = bool_stages(c, nodes, "ScratchRecordHasSourceAttributionV1")
    c.require_link(branch, "then", absent, "execute", "Attribution null branch changed")
    c.require_link(branch, "else", present, "execute", "Attribution object branch changed")

    source_object = d.field_node(c, nodes, "GetObjectField", "sourceAttribution")
    store_source = one_variable(c, nodes, "ScratchAttributionJsonV1", "K2Node_VariableSet")
    source = one_variable(c, nodes, "ScratchAttributionJsonV1", "K2Node_VariableGet")
    c.require_link(record, "ScratchRecordJsonV1", source_object, "self", "Attribution source changed")
    c.require_link(
        source_object,
        "ReturnValue",
        store_source,
        "ScratchAttributionJsonV1",
        "Attribution object staging changed",
    )

    stages = []
    for field_name, variable_name in (
        ("flypathId", "ScratchRecordSourceFlypathIdV1"),
        ("title", "ScratchRecordSourceTitleV1"),
        ("creatorDisplayName", "ScratchRecordSourceCreatorDisplayNameV1"),
    ):
        getter = d.field_node(c, nodes, "GetStringField", field_name)
        setter = one_variable(c, nodes, variable_name, "K2Node_VariableSet")
        c.require_link(source, "ScratchAttributionJsonV1", getter, "self", f"{field_name} source changed")
        c.require_link(getter, "ReturnValue", setter, variable_name, f"{field_name} staging changed")
        stages.append(setter)

    revision = d.field_node(c, nodes, "GetNumberField", "revisionNumber")
    conversion = call_node(c, nodes, "FTrunc")
    store_revision = one_variable(c, nodes, "ScratchRecordSourceRevisionNumberV1", "K2Node_VariableSet")
    c.require_link(source, "ScratchAttributionJsonV1", revision, "self", "Attribution revision source changed")
    c.require_link(revision, "ReturnValue", conversion, "A", "Attribution revision conversion changed")
    c.require_link(
        conversion,
        "ReturnValue",
        store_revision,
        "ScratchRecordSourceRevisionNumberV1",
        "Attribution revision staging changed",
    )
    d.require_exec_chain(c, [present, store_source, *stages, store_revision])


def assert_record(c, d, nodes, *, paste: bool) -> None:
    d.assert_closed(c, nodes, 49 if paste else 50, None if paste else "DecodeRecordV1")
    valid_setters = variable_nodes(nodes, "ScratchValidV1", "K2Node_VariableSet")
    c.require(len(valid_setters) == 2, "Record decoder must reset and commit validity exactly once")
    reset = [node for node in valid_setters if default_is(node, "ScratchValidV1", "false")]
    c.require(len(reset) == 1, "Record decoder validity reset changed")
    reset = reset[0]
    final_valid = [node for node in valid_setters if node is not reset][0]
    require_entry(c, d, nodes, "DecodeRecordV1", reset, paste=paste)

    source_store = one_variable(c, nodes, "ScratchSourceRecordJsonV1", "K2Node_VariableSet")
    encoded_getters = variable_nodes(nodes, "ScratchEncodedRecordV1", "K2Node_VariableGet")
    encoded_inputs = [
        node
        for node in encoded_getters
        if c.linked(node, "ScratchEncodedRecordV1", source_store, "ScratchSourceRecordJsonV1")
    ]
    c.require(len(encoded_inputs) == 1, "Record decoder input getter changed")
    encoded_input = encoded_inputs[0]
    c.require_link(
        encoded_input,
        "ScratchEncodedRecordV1",
        source_store,
        "ScratchSourceRecordJsonV1",
        "Record source preservation changed",
    )

    envelope_store = one_variable(c, nodes, "ScratchEnvelopeJsonV1", "K2Node_VariableSet")
    construct = call_node(c, nodes, "ConstructJsonObject")
    decode = call_node(c, nodes, "DecodeJson")
    guards = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(guards) == 2, "Record decoder must guard JSON decode and record object type")
    decode_guards = [node for node in guards if c.linked(decode, "ReturnValue", node, "Condition")]
    c.require(len(decode_guards) == 1, "Envelope decode guard changed")
    guard = decode_guards[0]
    c.require_link(construct, "ReturnValue", envelope_store, "ScratchEnvelopeJsonV1", "Envelope staging changed")
    c.require_link(envelope_store, "Output_Get", decode, "self", "Envelope decode target changed")
    c.require_link(source_store, "Output_Get", decode, "JsonString", "Envelope decode source changed")
    c.require_link(decode, "ReturnValue", guard, "Condition", "Envelope decode guard changed")
    c.require(not guard.pins["else"].links, "Malformed record input must terminate with validity false")
    d.require_exec_chain(c, [reset, source_store, envelope_store, decode])
    c.require_link(decode, "then", guard, "execute", "Decode guard execution changed")

    envelope = one_variable(c, nodes, "ScratchEnvelopeJsonV1", "K2Node_VariableGet")
    record_value = d.field_node(c, nodes, "GetField", "record")
    record_type = call_node(c, nodes, "GetTypeString")
    equal_nodes = [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class and 'MemberName="EqualEqual_StrStr"' in node.text
    ]
    c.require(len(equal_nodes) == 2, "Record decoder must own type and canonical string comparisons")
    type_equals = [node for node in equal_nodes if default_is(node, "B", "Object")]
    c.require(len(type_equals) == 1, "Record object type comparison changed")
    type_equal = type_equals[0]
    record_guards = [
        node for node in guards if node is not guard and c.linked(type_equal, "ReturnValue", node, "Condition")
    ]
    c.require(len(record_guards) == 1, "Record object guard changed")
    record_guard = record_guards[0]
    c.require_link(envelope, "ScratchEnvelopeJsonV1", record_value, "self", "Record value probe changed")
    c.require_link(record_value, "ReturnValue", record_type, "self", "Record type source changed")
    c.require_link(record_type, "ReturnValue", type_equal, "A", "Record type comparison changed")
    c.require(not record_guard.pins["else"].links, "Non-object record must terminate with validity false")
    c.require_link(guard, "then", record_guard, "execute", "Record type guard execution changed")
    record_object = d.field_node(c, nodes, "GetObjectField", "record")
    record_store = one_variable(c, nodes, "ScratchRecordJsonV1", "K2Node_VariableSet")
    record = one_variable(c, nodes, "ScratchRecordJsonV1", "K2Node_VariableGet")
    c.require_link(envelope, "ScratchEnvelopeJsonV1", record_object, "self", "Record object source changed")
    c.require_link(record_object, "ReturnValue", record_store, "ScratchRecordJsonV1", "Record staging changed")
    c.require_link(record_guard, "then", record_store, "execute", "Valid record-object path changed")

    execution = [record_store]
    for field_name, variable_name in (
        ("createdUtc", "ScratchRecordCreatedUtcV1"),
        ("description", "ScratchRecordDescriptionV1"),
    ):
        getter = d.field_node(c, nodes, "GetStringField", field_name)
        setter = one_variable(c, nodes, variable_name, "K2Node_VariableSet")
        c.require_link(record, "ScratchRecordJsonV1", getter, "self", f"{field_name} source changed")
        c.require_link(getter, "ReturnValue", setter, variable_name, f"{field_name} staging changed")
        execution.append(setter)

    draft = d.field_node(c, nodes, "GetObjectField", "draft")
    draft_encode = call_node(c, nodes, "EncodeJson")
    encoded_document = one_variable(c, nodes, "ScratchEncodedDocumentV1", "K2Node_VariableSet")
    decode_document = call_node(c, nodes, "DecodeDocumentV1")
    decoded_document = one_variable(c, nodes, "ScratchDocumentV1", "K2Node_VariableGet")
    store_document = one_variable(c, nodes, "ScratchRecordDraftDocumentV1", "K2Node_VariableSet")
    c.require_link(record, "ScratchRecordJsonV1", draft, "self", "Draft source changed")
    c.require_link(draft, "ReturnValue", draft_encode, "self", "Draft canonical staging changed")
    c.require_link(
        draft_encode,
        "ReturnValue",
        encoded_document,
        "ScratchEncodedDocumentV1",
        "Draft decoder input changed",
    )
    c.require_link(
        decoded_document,
        "ScratchDocumentV1",
        store_document,
        "ScratchRecordDraftDocumentV1",
        "Draft result staging changed",
    )
    execution.extend((encoded_document, decode_document, store_document))

    draft_revision = d.field_node(c, nodes, "GetNumberField", "draftRevisionNumber")
    conversions = [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class and 'MemberName="FTrunc"' in node.text
    ]
    c.require(len(conversions) == 1, "Draft revision must use one float-to-int bridge")
    store_revision = one_variable(c, nodes, "ScratchRecordDraftRevisionNumberV1", "K2Node_VariableSet")
    c.require_link(record, "ScratchRecordJsonV1", draft_revision, "self", "Draft revision source changed")
    c.require_link(draft_revision, "ReturnValue", conversions[0], "A", "Draft revision conversion changed")
    c.require_link(
        conversions[0],
        "ReturnValue",
        store_revision,
        "ScratchRecordDraftRevisionNumberV1",
        "Draft revision staging changed",
    )
    execution.append(store_revision)

    for field_name, variable_name in (
        ("flypathId", "ScratchRecordFlypathIdV1"),
        ("ownerAccountId", "ScratchRecordOwnerAccountIdV1"),
        ("ownerDisplayName", "ScratchRecordOwnerDisplayNameV1"),
    ):
        getter = d.field_node(c, nodes, "GetStringField", field_name)
        setter = one_variable(c, nodes, variable_name, "K2Node_VariableSet")
        c.require_link(record, "ScratchRecordJsonV1", getter, "self", f"{field_name} source changed")
        c.require_link(getter, "ReturnValue", setter, variable_name, f"{field_name} staging changed")
        execution.append(setter)

    published = call_node(c, nodes, "DecodeRecordPublishedFieldsV1")
    execution.append(published)
    region = d.field_node(c, nodes, "GetStringField", "regionId")
    store_region = one_variable(c, nodes, "ScratchRecordRegionIdV1", "K2Node_VariableSet")
    c.require_link(record, "ScratchRecordJsonV1", region, "self", "Region source changed")
    c.require_link(region, "ReturnValue", store_region, "ScratchRecordRegionIdV1", "Region staging changed")
    execution.append(store_region)
    source = call_node(c, nodes, "DecodeRecordSourceAttributionV1")
    execution.append(source)

    for field_name, variable_name in (
        ("title", "ScratchRecordTitleV1"),
        ("updatedUtc", "ScratchRecordUpdatedUtcV1"),
        ("visibility", "ScratchRecordVisibilityV1"),
    ):
        getter = d.field_node(c, nodes, "GetStringField", field_name)
        setter = one_variable(c, nodes, variable_name, "K2Node_VariableSet")
        c.require_link(record, "ScratchRecordJsonV1", getter, "self", f"{field_name} source changed")
        c.require_link(getter, "ReturnValue", setter, variable_name, f"{field_name} staging changed")
        execution.append(setter)

    encode_record = call_node(c, nodes, "EncodeRecordV1")
    execution.extend((encode_record, final_valid))
    d.require_exec_chain(c, execution)

    source_record = one_variable(c, nodes, "ScratchSourceRecordJsonV1", "K2Node_VariableGet")
    canonical_record = [node for node in encoded_getters if node is not encoded_input]
    c.require(len(canonical_record) == 1, "Canonical record output getter changed")
    canonical_equals = [node for node in equal_nodes if node is not type_equal]
    c.require(len(canonical_equals) == 1, "Canonical record comparison changed")
    equal = canonical_equals[0]
    c.require_link(source_record, "ScratchSourceRecordJsonV1", equal, "A", "Canonical source comparison changed")
    c.require_link(canonical_record[0], "ScratchEncodedRecordV1", equal, "B", "Canonical output comparison changed")
    c.require_link(equal, "ReturnValue", final_valid, "ScratchValidV1", "Final record validity changed")
    c.require("ScratchSourceDocumentJsonV1" not in "\n".join(n.text for n in nodes.values()), "Record source must not alias document source")


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

    d = load_decoder_contracts(args.project_root)
    c = d.load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    if args.only in ("all", "published"):
        assert_published(
            c,
            d,
            c.parse_graph(args.input_dir / f"decode-record-published-fields-v1{suffix}.eddgraph"),
            paste=args.paste,
        )
    if args.only in ("all", "source"):
        assert_source(
            c,
            d,
            c.parse_graph(args.input_dir / f"decode-record-source-attribution-v1{suffix}.eddgraph"),
            paste=args.paste,
        )
    if args.only in ("all", "record"):
        assert_record(
            c,
            d,
            c.parse_graph(args.input_dir / f"decode-record-v1{suffix}.eddgraph"),
            paste=args.paste,
        )
    print("Repository record decoder graph contracts passed")


if __name__ == "__main__":
    main()
