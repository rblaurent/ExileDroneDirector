"""Build metadata-only owner-filtered ListMineV1 repository graphs.

The query is read-only.  It validates the aligned derived index, filters by the
requesting owner, selection-sorts matching source indexes by
``(updatedUtc, flypathId)`` descending, clamps paging to 1..100, decodes and
validates only the selected records, and publishes minimal metadata JSON.
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


def connect_exec(bp, nodes) -> None:
    for left, right in zip(nodes, nodes[1:]):
        bp.connect(left, "then", right, "execute")


def error(enc, b, code: str, detail: str, x: int, y: int):
    code_node = b.setter("ResultCodeV1", "string", x, y)
    detail_node = b.setter("ResultDetailV1", "string", x + 256, y)
    enc.set_default(code_node, "ResultCodeV1", code)
    enc.set_default(detail_node, "ResultDetailV1", detail)
    return code_node, detail_node


def int_select(enc, b, key: str, x: int, y: int):
    node = b.add(key, "select", x, y)
    for pin in ("Option 0", "Option 1", "ReturnValue"):
        enc.set_pin_type(node, pin, "int")
    return node


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name)
    node.text = "\n".join(
        line for line in node.text.splitlines() if f"PinId={pin_id}" not in line
    )


def character_array(v, source, source_pin: str, x: int, y: int):
    node = v.b.add(f"character_array_{len(v.nodes)}", "string_math", x, y)
    node.text = node.text.replace(
        'MemberName="EqualEqual_StrStr"',
        'MemberName="GetCharacterArrayFromString"',
        1,
    )
    v.enc.rename_pin(node, "A", "SourceString")
    remove_pin(node, "B")
    v.enc.set_pin_type(node, "ReturnValue", "string", array=True)
    v.bp.connect(source, source_pin, node, "SourceString")
    return node


def character_number(v, source, source_pin: str, index, index_pin: str, x: int, y: int):
    node = v.b.add(f"character_number_{len(v.nodes)}", "string_math", x, y)
    node.text = node.text.replace(
        'MemberName="EqualEqual_StrStr"',
        'MemberName="GetCharacterAsNumber"',
        1,
    )
    v.enc.rename_pin(node, "A", "SourceString")
    v.enc.rename_pin(node, "B", "Index")
    v.enc.set_pin_type(node, "Index", "int")
    v.enc.set_pin_type(node, "ReturnValue", "int")
    v.bp.connect(source, source_pin, node, "SourceString")
    v.bp.connect(index, index_pin, node, "Index")
    return node


def build_ordinal_compare(bp, enc, validation, create, templates):
    """Build an ASCII/UTF-16 ordinal greater-than helper from shipped nodes."""
    v = validation.ValidationBuilder(bp, enc, templates, "CompareStringsOrdinalV1")
    b = v.b
    reset_resolved = b.setter("ScratchCompareResolvedV1", "bool", 256, 0)
    reset_greater = b.setter("ScratchStringGreaterV1", "bool", 512, 0)
    enc.set_default(reset_resolved, "ScratchCompareResolvedV1", "false")
    enc.set_default(reset_greater, "ScratchStringGreaterV1", "false")
    left = b.getter("ScratchCompareLeftV1", "string", 512, 384)
    right = b.getter("ScratchCompareRightV1", "string", 512, 544)
    characters = character_array(v, left, "ScratchCompareLeftV1", 768, 384)
    loop = b.foreach("string", 1024, 0)
    bp.connect(characters, "ReturnValue", loop, "Array")

    resolved = b.getter("ScratchCompareResolvedV1", "bool", 1280, 384)
    unresolved = v.bool_math("EqualEqual_BoolBool", 1504, 384)
    enc.set_default(unresolved, "B", "false")
    unresolved_branch = v.branch(1728, 160)
    bp.connect(resolved, "ScratchCompareResolvedV1", unresolved, "A")
    bp.connect(unresolved, "ReturnValue", unresolved_branch, "Condition")
    bp.connect(loop, "LoopBody", unresolved_branch, "execute")

    left_character = character_number(
        v, left, "ScratchCompareLeftV1", loop, "Array Index", 1984, 384
    )
    right_character = character_number(
        v, right, "ScratchCompareRightV1", loop, "Array Index", 1984, 544
    )
    different = v.int_math("NotEqual_IntInt", 2208, 464)
    different_branch = v.branch(2432, 160)
    bp.connect(left_character, "ReturnValue", different, "A")
    bp.connect(right_character, "ReturnValue", different, "B")
    bp.connect(different, "ReturnValue", different_branch, "Condition")
    bp.connect(unresolved_branch, "then", different_branch, "execute")
    character_greater = v.int_math("Greater_IntInt", 2688, 384)
    set_greater = b.setter("ScratchStringGreaterV1", "bool", 2912, 160)
    set_resolved = b.setter("ScratchCompareResolvedV1", "bool", 3168, 160)
    enc.set_default(set_resolved, "ScratchCompareResolvedV1", "true")
    bp.connect(left_character, "ReturnValue", character_greater, "A")
    bp.connect(right_character, "ReturnValue", character_greater, "B")
    bp.connect(character_greater, "ReturnValue", set_greater, "ScratchStringGreaterV1")
    bp.connect(different_branch, "then", set_greater, "execute")
    connect_exec(bp, [set_greater, set_resolved])

    resolved_final = b.getter("ScratchCompareResolvedV1", "bool", 1280, 704)
    unresolved_final = v.bool_math("EqualEqual_BoolBool", 1504, 704)
    enc.set_default(unresolved_final, "B", "false")
    prefix_branch = v.branch(1728, 704)
    left_length = create.string_len(v, left, "ScratchCompareLeftV1", 1984, 704)
    right_length = create.string_len(v, right, "ScratchCompareRightV1", 1984, 864)
    left_longer = v.int_math("Greater_IntInt", 2208, 784)
    set_prefix_result = b.setter("ScratchStringGreaterV1", "bool", 2432, 704)
    bp.connect(resolved_final, "ScratchCompareResolvedV1", unresolved_final, "A")
    bp.connect(unresolved_final, "ReturnValue", prefix_branch, "Condition")
    bp.connect(left_length, "ReturnValue", left_longer, "A")
    bp.connect(right_length, "ReturnValue", left_longer, "B")
    bp.connect(left_longer, "ReturnValue", set_prefix_result, "ScratchStringGreaterV1")
    bp.connect(loop, "Completed", prefix_branch, "execute")
    bp.connect(prefix_branch, "then", set_prefix_result, "execute")

    bp.connect(v.entry, "then", reset_resolved, "execute")
    connect_exec(bp, [reset_resolved, reset_greater])
    bp.connect(reset_greater, "then", loop, "Exec")
    return v.nodes


def build_metadata(bp, enc, templates):
    b = enc.Builder(bp, templates, "EncodeMetadataV1")
    root = b.json("ConstructJsonObject", 256, 384)
    store = b.setter("ScratchRootJsonV1", "json", 256, 0)
    bp.connect(root, "ReturnValue", store, "ScratchRootJsonV1")
    root_value = b.getter("ScratchRootJsonV1", "json", 512, 640)

    nodes = []
    x = 512
    for field_name, variable_name in (
        ("flypathId", "ScratchRecordFlypathIdV1"),
        ("ownerDisplayName", "ScratchRecordOwnerDisplayNameV1"),
        ("title", "ScratchRecordTitleV1"),
        ("visibility", "ScratchRecordVisibilityV1"),
        ("regionId", "ScratchRecordRegionIdV1"),
        ("updatedUtc", "ScratchRecordUpdatedUtcV1"),
    ):
        node = b.json("SetStringField", x, 0)
        enc.field(node, field_name)
        value = b.getter(variable_name, "string", x, 384)
        bp.connect(root_value, "ScratchRootJsonV1", node, "self")
        bp.connect(value, variable_name, node, "StringValue")
        nodes.append(node)
        x += 256

    draft = b.json("SetNumberField", x, 0)
    enc.field(draft, "draftRevisionNumber")
    draft_value = b.getter("ScratchRecordDraftRevisionNumberV1", "int", x, 384)
    draft_number = b.add("draft_revision_number", "int_to_double", x, 544)
    bp.connect(root_value, "ScratchRootJsonV1", draft, "self")
    bp.connect(draft_value, "ScratchRecordDraftRevisionNumberV1", draft_number, "InInt")
    bp.connect(draft_number, "ReturnValue", draft, "Number")
    nodes.append(draft)
    x += 256

    has_published = b.json("SetBoolField", x, 0)
    enc.field(has_published, "hasPublishedRevision")
    has_value = b.getter("ScratchRecordHasPublishedRevisionV1", "bool", x, 384)
    bp.connect(root_value, "ScratchRootJsonV1", has_published, "self")
    bp.connect(has_value, "ScratchRecordHasPublishedRevisionV1", has_published, "InValue")
    nodes.append(has_published)
    x += 256

    published = b.json("SetNumberField", x, 0)
    enc.field(published, "publishedRevisionNumber")
    published_value = b.getter("ScratchRecordPublishedRevisionNumberV1", "int", x, 384)
    published_number = b.add("published_revision_number", "int_to_double", x, 544)
    bp.connect(root_value, "ScratchRootJsonV1", published, "self")
    bp.connect(published_value, "ScratchRecordPublishedRevisionNumberV1", published_number, "InInt")
    bp.connect(published_number, "ReturnValue", published, "Number")
    nodes.append(published)
    x += 256

    encode = b.json("EncodeJson", x, 384)
    result = b.setter("ScratchEncodedMetadataV1", "string", x + 256, 0)
    bp.connect(root_value, "ScratchRootJsonV1", encode, "self")
    bp.connect(encode, "ReturnValue", result, "ScratchEncodedMetadataV1")
    bp.connect(b.entry, "then", store, "execute")
    connect_exec(bp, [store, *nodes, result])
    return b.nodes


def build_list(bp, enc, validation, create, templates):
    v = validation.ValidationBuilder(bp, enc, templates, "ListMineV1")
    b = v.b

    reset = b.call("ResetRepositoryResultV1", 256, 0)
    _request, _trimmed, request_ok = create.trimmed_nonempty(
        v, templates, "RequestRequesterAccountIdV1", 512, 384
    )
    request_branch = v.branch(1024, 0)
    bp.connect(request_ok, "ReturnValue", request_branch, "Condition")

    ids = b.getter("ActiveFlypathIdsV1", "string", 1024, 400, array=True)
    owners = b.getter("ActiveOwnerAccountIdsV1", "string", 1024, 544, array=True)
    visibilities = b.getter("ActiveVisibilitiesV1", "string", 1024, 688, array=True)
    updated = b.getter("ActiveUpdatedUtcV1", "string", 1024, 832, array=True)
    envelopes = b.getter("ActiveRecordEnvelopesV1", "string", 1024, 976, array=True)
    lengths = [
        v.length(source, pin, "string", 1280 + index * 224, 400 + index * 144)
        for index, (source, pin) in enumerate(
            (
                (ids, "ActiveFlypathIdsV1"),
                (owners, "ActiveOwnerAccountIdsV1"),
                (visibilities, "ActiveVisibilitiesV1"),
                (updated, "ActiveUpdatedUtcV1"),
                (envelopes, "ActiveRecordEnvelopesV1"),
            )
        )
    ]
    equal_lengths = []
    for index, other in enumerate(lengths[1:]):
        equal = v.int_math("EqualEqual_IntInt", 2496 + index * 224, 400 + index * 144)
        bp.connect(lengths[0], "ReturnValue", equal, "A")
        bp.connect(other, "ReturnValue", equal, "B")
        equal_lengths.append(equal)
    aligned = v.and_all(equal_lengths, 3392, 480)
    aligned_branch = v.branch(4288, 0)
    bp.connect(aligned, "ReturnValue", aligned_branch, "Condition")

    owner_indexes = b.getter("ScratchListOwnerIndexesV1", "int", 4544, 384, array=True)
    clear_owner_indexes = b.array_clear("int", 4544, 0)
    sorted_indexes = b.getter("ScratchListSortedIndexesV1", "int", 4800, 384, array=True)
    clear_sorted_indexes = b.array_clear("int", 4800, 0)
    clear_failed = b.setter("ScratchListFailedV1", "bool", 5056, 0)
    enc.set_default(clear_failed, "ScratchListFailedV1", "false")

    filter_loop = b.foreach("string", 5312, 0)
    requester = b.getter("RequestRequesterAccountIdV1", "string", 5312, 384)
    owner_equal = v.string_math("EqualEqual_StrStr", 5568, 384)
    owner_branch = v.branch(5824, 160)
    owner_indexes_for_add = b.getter("ScratchListOwnerIndexesV1", "int", 6080, 384, array=True)
    add_owner_index = b.array_add("int", 6080, 160)
    bp.connect(owners, "ActiveOwnerAccountIdsV1", filter_loop, "Array")
    bp.connect(filter_loop, "Array Element", owner_equal, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", owner_equal, "B")
    bp.connect(owner_equal, "ReturnValue", owner_branch, "Condition")
    bp.connect(owner_indexes_for_add, "ScratchListOwnerIndexesV1", add_owner_index, "TargetArray")
    bp.connect(filter_loop, "Array Index", add_owner_index, "NewItem")
    bp.connect(filter_loop, "LoopBody", owner_branch, "execute")
    bp.connect(owner_branch, "then", add_owner_index, "execute")

    # Deterministic selection sort.  Each outer iteration selects the greatest
    # remaining (updatedUtc, flypathId) tuple and appends its source index.
    owner_indexes_for_outer = b.getter("ScratchListOwnerIndexesV1", "int", 6336, 384, array=True)
    sort_outer = b.foreach("int", 6336, 0)
    reset_best_index = b.setter("ScratchListBestIndexV1", "int", 6592, 0)
    enc.set_default(reset_best_index, "ScratchListBestIndexV1", "-1")
    reset_best_updated = b.setter("ScratchListBestUpdatedUtcV1", "string", 6848, 0)
    enc.set_default(reset_best_updated, "ScratchListBestUpdatedUtcV1", "")
    reset_best_id = b.setter("ScratchListBestFlypathIdV1", "string", 7104, 0)
    enc.set_default(reset_best_id, "ScratchListBestFlypathIdV1", "")
    owner_indexes_for_inner = b.getter("ScratchListOwnerIndexesV1", "int", 7360, 384, array=True)
    sort_inner = b.foreach("int", 7360, 0)

    sorted_for_find = b.getter("ScratchListSortedIndexesV1", "int", 7616, 384, array=True)
    already_find = b.add("already_sorted_find", "array_find", 7872, 384)
    validation.array_find_form(already_find, enc, "int")
    not_sorted = v.int_math("EqualEqual_IntInt", 8096, 384, b_default="-1")
    bp.connect(sorted_for_find, "ScratchListSortedIndexesV1", already_find, "TargetArray")
    bp.connect(sort_inner, "Array Element", already_find, "ItemToFind")
    bp.connect(already_find, "ReturnValue", not_sorted, "A")

    candidate_updated = v.array_item(
        updated, "ActiveUpdatedUtcV1", sort_inner, "Array Element", "string", 8320, 384
    )
    candidate_id = v.array_item(
        ids, "ActiveFlypathIdsV1", sort_inner, "Array Element", "string", 8320, 544
    )
    best_index = b.getter("ScratchListBestIndexV1", "int", 8320, 704)
    best_missing = v.int_math("EqualEqual_IntInt", 8544, 704, b_default="-1")
    bp.connect(best_index, "ScratchListBestIndexV1", best_missing, "A")
    best_updated = b.getter("ScratchListBestUpdatedUtcV1", "string", 8544, 384)
    best_id = b.getter("ScratchListBestFlypathIdV1", "string", 8544, 864)
    updated_equal = v.string_math("EqualEqual_StrStr", 8768, 384)
    bp.connect(candidate_updated, "Output", updated_equal, "A")
    bp.connect(best_updated, "ScratchListBestUpdatedUtcV1", updated_equal, "B")

    candidate_available = v.branch(8992, 160)
    best_missing_branch = v.branch(9248, 160)
    bp.connect(not_sorted, "ReturnValue", candidate_available, "Condition")
    bp.connect(best_missing, "ReturnValue", best_missing_branch, "Condition")
    bp.connect(sort_inner, "LoopBody", candidate_available, "execute")
    bp.connect(candidate_available, "then", best_missing_branch, "execute")

    compare_updated_left = b.setter("ScratchCompareLeftV1", "string", 9504, 320)
    compare_updated_right = b.setter("ScratchCompareRightV1", "string", 9760, 320)
    compare_updated = b.call("CompareStringsOrdinalV1", 10016, 320)
    updated_is_greater = b.getter("ScratchStringGreaterV1", "bool", 10016, 640)
    updated_greater_branch = v.branch(10272, 320)
    updated_equal_branch = v.branch(10528, 480)
    bp.connect(candidate_updated, "Output", compare_updated_left, "ScratchCompareLeftV1")
    bp.connect(best_updated, "ScratchListBestUpdatedUtcV1", compare_updated_right, "ScratchCompareRightV1")
    bp.connect(updated_is_greater, "ScratchStringGreaterV1", updated_greater_branch, "Condition")
    bp.connect(updated_equal, "ReturnValue", updated_equal_branch, "Condition")
    bp.connect(best_missing_branch, "else", compare_updated_left, "execute")
    connect_exec(bp, [compare_updated_left, compare_updated_right, compare_updated])
    bp.connect(compare_updated, "then", updated_greater_branch, "execute")
    bp.connect(updated_greater_branch, "else", updated_equal_branch, "execute")

    compare_id_left = b.setter("ScratchCompareLeftV1", "string", 10784, 480)
    compare_id_right = b.setter("ScratchCompareRightV1", "string", 11040, 480)
    compare_id = b.call("CompareStringsOrdinalV1", 11296, 480)
    id_is_greater = b.getter("ScratchStringGreaterV1", "bool", 11296, 800)
    id_greater_branch = v.branch(11552, 480)
    bp.connect(candidate_id, "Output", compare_id_left, "ScratchCompareLeftV1")
    bp.connect(best_id, "ScratchListBestFlypathIdV1", compare_id_right, "ScratchCompareRightV1")
    bp.connect(id_is_greater, "ScratchStringGreaterV1", id_greater_branch, "Condition")
    bp.connect(updated_equal_branch, "then", compare_id_left, "execute")
    connect_exec(bp, [compare_id_left, compare_id_right, compare_id])
    bp.connect(compare_id, "then", id_greater_branch, "execute")

    set_best_index = b.setter("ScratchListBestIndexV1", "int", 11808, 160)
    set_best_updated = b.setter("ScratchListBestUpdatedUtcV1", "string", 12064, 160)
    set_best_id = b.setter("ScratchListBestFlypathIdV1", "string", 12320, 160)
    bp.connect(sort_inner, "Array Element", set_best_index, "ScratchListBestIndexV1")
    bp.connect(candidate_updated, "Output", set_best_updated, "ScratchListBestUpdatedUtcV1")
    bp.connect(candidate_id, "Output", set_best_id, "ScratchListBestFlypathIdV1")
    bp.connect(best_missing_branch, "then", set_best_index, "execute")
    bp.connect(updated_greater_branch, "then", set_best_index, "execute")
    bp.connect(id_greater_branch, "then", set_best_index, "execute")
    connect_exec(bp, [set_best_index, set_best_updated, set_best_id])

    sorted_for_add = b.getter("ScratchListSortedIndexesV1", "int", 10912, 384, array=True)
    final_best_index = b.getter("ScratchListBestIndexV1", "int", 10912, 544)
    add_sorted_index = b.array_add("int", 11168, 160)
    bp.connect(sorted_for_add, "ScratchListSortedIndexesV1", add_sorted_index, "TargetArray")
    bp.connect(final_best_index, "ScratchListBestIndexV1", add_sorted_index, "NewItem")
    bp.connect(sort_inner, "Completed", add_sorted_index, "execute")

    bp.connect(owner_indexes_for_outer, "ScratchListOwnerIndexesV1", sort_outer, "Array")
    bp.connect(sort_outer, "LoopBody", reset_best_index, "execute")
    connect_exec(bp, [reset_best_index, reset_best_updated, reset_best_id])
    bp.connect(reset_best_id, "then", sort_inner, "Exec")
    bp.connect(owner_indexes_for_inner, "ScratchListOwnerIndexesV1", sort_inner, "Array")

    total = v.length(owner_indexes_for_outer, "ScratchListOwnerIndexesV1", "int", 11424, 384)
    result_total = b.setter("ResultTotalCountV1", "int", 11424, 0)
    bp.connect(total, "ReturnValue", result_total, "ResultTotalCountV1")
    request_offset = b.getter("RequestOffsetV1", "int", 11680, 384)
    offset_nonnegative = v.int_math("GreaterEqual_IntInt", 11904, 384, b_default="0")
    safe_offset_value = int_select(enc, b, "select_safe_offset", 12128, 384)
    safe_offset = b.setter("ScratchListSafeOffsetV1", "int", 12128, 0)
    result_offset = b.setter("ResultPageOffsetV1", "int", 12384, 0)
    bp.connect(request_offset, "RequestOffsetV1", offset_nonnegative, "A")
    bp.connect(offset_nonnegative, "ReturnValue", safe_offset_value, "Index")
    enc.set_default(safe_offset_value, "Option 0", "0")
    bp.connect(request_offset, "RequestOffsetV1", safe_offset_value, "Option 1")
    bp.connect(safe_offset_value, "ReturnValue", safe_offset, "ScratchListSafeOffsetV1")
    bp.connect(safe_offset_value, "ReturnValue", result_offset, "ResultPageOffsetV1")
    request_limit = b.getter("RequestLimitV1", "int", 12128, 544)
    limit_at_least_one = v.int_math("GreaterEqual_IntInt", 12352, 544, b_default="1")
    min_limit = int_select(enc, b, "select_min_limit", 12576, 544)
    enc.set_default(min_limit, "Option 0", "1")
    bp.connect(request_limit, "RequestLimitV1", limit_at_least_one, "A")
    bp.connect(limit_at_least_one, "ReturnValue", min_limit, "Index")
    bp.connect(request_limit, "RequestLimitV1", min_limit, "Option 1")
    limit_at_most_hundred = v.int_math("LessEqual_IntInt", 12800, 544, b_default="100")
    max_limit = int_select(enc, b, "select_max_limit", 13024, 544)
    enc.set_default(max_limit, "Option 0", "100")
    bp.connect(min_limit, "ReturnValue", limit_at_most_hundred, "A")
    bp.connect(limit_at_most_hundred, "ReturnValue", max_limit, "Index")
    bp.connect(min_limit, "ReturnValue", max_limit, "Option 1")
    safe_limit = b.setter("ScratchListSafeLimitV1", "int", 12800, 0)
    bp.connect(max_limit, "ReturnValue", safe_limit, "ScratchListSafeLimitV1")
    offset_plus_limit = v.int_math("Add_IntInt", 13056, 384)
    sum_within_total = v.int_math("LessEqual_IntInt", 13280, 384)
    end_value = int_select(enc, b, "select_end", 13504, 384)
    end_exclusive = b.setter("ScratchListEndExclusiveV1", "int", 13504, 0)
    bp.connect(safe_offset_value, "ReturnValue", offset_plus_limit, "A")
    bp.connect(max_limit, "ReturnValue", offset_plus_limit, "B")
    bp.connect(offset_plus_limit, "ReturnValue", sum_within_total, "A")
    bp.connect(total, "ReturnValue", sum_within_total, "B")
    bp.connect(sum_within_total, "ReturnValue", end_value, "Index")
    bp.connect(total, "ReturnValue", end_value, "Option 0")
    bp.connect(offset_plus_limit, "ReturnValue", end_value, "Option 1")
    bp.connect(end_value, "ReturnValue", end_exclusive, "ScratchListEndExclusiveV1")

    sorted_for_output = b.getter("ScratchListSortedIndexesV1", "int", 13760, 384, array=True)
    output_loop = b.foreach("int", 13760, 0)
    safe_offset_read = b.getter("ScratchListSafeOffsetV1", "int", 14016, 384)
    end_read = b.getter("ScratchListEndExclusiveV1", "int", 14016, 544)
    after_offset = v.int_math("GreaterEqual_IntInt", 14240, 384)
    before_end = v.int_math("Less_IntInt", 14240, 544)
    in_page = v.bool_math("BooleanAND", 14464, 448)
    failed_read = b.getter("ScratchListFailedV1", "bool", 14016, 704)
    not_failed = v.bool_math("EqualEqual_BoolBool", 14240, 704)
    enc.set_default(not_failed, "B", "false")
    process_item = v.bool_math("BooleanAND", 14688, 512)
    page_branch = v.branch(14912, 160)
    bp.connect(output_loop, "Array Index", after_offset, "A")
    bp.connect(safe_offset_read, "ScratchListSafeOffsetV1", after_offset, "B")
    bp.connect(output_loop, "Array Index", before_end, "A")
    bp.connect(end_read, "ScratchListEndExclusiveV1", before_end, "B")
    bp.connect(after_offset, "ReturnValue", in_page, "A")
    bp.connect(before_end, "ReturnValue", in_page, "B")
    bp.connect(failed_read, "ScratchListFailedV1", not_failed, "A")
    bp.connect(in_page, "ReturnValue", process_item, "A")
    bp.connect(not_failed, "ReturnValue", process_item, "B")
    bp.connect(process_item, "ReturnValue", page_branch, "Condition")
    bp.connect(output_loop, "LoopBody", page_branch, "execute")

    selected_envelope = v.array_item(
        envelopes, "ActiveRecordEnvelopesV1", output_loop, "Array Element", "string", 15168, 384
    )
    stage_envelope = b.setter("ScratchEncodedRecordV1", "string", 15168, 160)
    decode = b.call("DecodeRecordV1", 15424, 160)
    decoded = b.getter("ScratchValidV1", "bool", 15424, 480)
    decoded_branch = v.branch(15680, 160)
    bp.connect(selected_envelope, "Output", stage_envelope, "ScratchEncodedRecordV1")
    bp.connect(decoded, "ScratchValidV1", decoded_branch, "Condition")
    bp.connect(page_branch, "then", stage_envelope, "execute")
    bp.connect(stage_envelope, "then", decode, "execute")
    bp.connect(decode, "then", decoded_branch, "execute")
    validate_record = b.call("ValidateRecordV1", 15936, 160)
    record_valid = b.getter("ScratchValidV1", "bool", 15936, 480)
    valid_branch = v.branch(16192, 160)
    bp.connect(record_valid, "ScratchValidV1", valid_branch, "Condition")
    bp.connect(decoded_branch, "then", validate_record, "execute")
    bp.connect(validate_record, "then", valid_branch, "execute")

    derived_id = v.array_item(ids, "ActiveFlypathIdsV1", output_loop, "Array Element", "string", 16448, 384)
    derived_owner = v.array_item(owners, "ActiveOwnerAccountIdsV1", output_loop, "Array Element", "string", 16448, 528)
    derived_visibility = v.array_item(visibilities, "ActiveVisibilitiesV1", output_loop, "Array Element", "string", 16448, 672)
    derived_updated = v.array_item(updated, "ActiveUpdatedUtcV1", output_loop, "Array Element", "string", 16448, 816)
    identity_conditions = []
    for row, (record_name, derived, derived_pin) in enumerate(
        (
            ("ScratchRecordFlypathIdV1", derived_id, "Output"),
            ("ScratchRecordOwnerAccountIdV1", derived_owner, "Output"),
            ("ScratchRecordVisibilityV1", derived_visibility, "Output"),
            ("ScratchRecordUpdatedUtcV1", derived_updated, "Output"),
        )
    ):
        record_value = b.getter(record_name, "string", 16704, 384 + row * 144)
        equal = v.string_math("EqualEqual_StrStr", 16928, 384 + row * 144)
        bp.connect(record_value, record_name, equal, "A")
        bp.connect(derived, derived_pin, equal, "B")
        identity_conditions.append(equal)
    owner_request_equal = v.string_math("EqualEqual_StrStr", 16928, 960)
    record_owner = b.getter("ScratchRecordOwnerAccountIdV1", "string", 16704, 960)
    bp.connect(record_owner, "ScratchRecordOwnerAccountIdV1", owner_request_equal, "A")
    bp.connect(requester, "RequestRequesterAccountIdV1", owner_request_equal, "B")
    identity_conditions.append(owner_request_equal)
    identity_ok = v.and_all(identity_conditions, 17152, 544)
    identity_branch = v.branch(18272, 160)
    bp.connect(identity_ok, "ReturnValue", identity_branch, "Condition")
    bp.connect(valid_branch, "then", identity_branch, "execute")

    encode_metadata = b.call("EncodeMetadataV1", 18528, 160)
    metadata_results = b.getter("ResultMetadataEnvelopesV1", "string", 18528, 480, array=True)
    encoded_metadata = b.getter("ScratchEncodedMetadataV1", "string", 18528, 624)
    append_metadata = b.array_add("string", 18784, 160)
    bp.connect(metadata_results, "ResultMetadataEnvelopesV1", append_metadata, "TargetArray")
    bp.connect(encoded_metadata, "ScratchEncodedMetadataV1", append_metadata, "NewItem")
    bp.connect(identity_branch, "then", encode_metadata, "execute")
    bp.connect(encode_metadata, "then", append_metadata, "execute")

    # Any selected-record failure atomically clears all partial page output.
    def failure_chain(branch, pin: str, detail: str, x: int, y: int):
        reset_failure = b.call("ResetRepositoryResultV1", x, y)
        failed = b.setter("ScratchListFailedV1", "bool", x + 256, y)
        enc.set_default(failed, "ScratchListFailedV1", "true")
        failure = error(enc, b, "ValidationFailed", detail, x + 512, y)
        bp.connect(branch, pin, reset_failure, "execute")
        connect_exec(bp, [reset_failure, failed, failure[0], failure[1]])

    failure_chain(decoded_branch, "else", "StoredRecordDecodeFailed", 15936, -320)
    failure_chain(valid_branch, "else", "StoredRecordInvalid", 16448, -320)
    failure_chain(identity_branch, "else", "StoredRecordIndexMismatch", 18528, -320)

    end_read_final = b.getter("ScratchListEndExclusiveV1", "int", 19040, 384)
    has_more_value = v.int_math("Less_IntInt", 19264, 384)
    final_failed = b.getter("ScratchListFailedV1", "bool", 19040, 544)
    final_ok = v.bool_math("EqualEqual_BoolBool", 19264, 544)
    enc.set_default(final_ok, "B", "false")
    final_branch = v.branch(19488, 160)
    result_has_more = b.setter("ResultHasMoreV1", "bool", 19744, 160)
    bp.connect(end_read_final, "ScratchListEndExclusiveV1", has_more_value, "A")
    bp.connect(total, "ReturnValue", has_more_value, "B")
    bp.connect(final_failed, "ScratchListFailedV1", final_ok, "A")
    bp.connect(final_ok, "ReturnValue", final_branch, "Condition")
    bp.connect(has_more_value, "ReturnValue", result_has_more, "ResultHasMoreV1")
    bp.connect(output_loop, "Completed", final_branch, "execute")
    bp.connect(final_branch, "then", result_has_more, "execute")

    invalid_request = error(enc, b, "ValidationFailed", "InvalidListRequest", 1280, -320)
    misaligned = error(enc, b, "ValidationFailed", "MetadataIndexMisaligned", 4544, -320)
    bp.connect(v.entry, "then", reset, "execute")
    bp.connect(reset, "then", request_branch, "execute")
    bp.connect(request_branch, "else", invalid_request[0], "execute")
    bp.connect(invalid_request[0], "then", invalid_request[1], "execute")
    bp.connect(request_branch, "then", aligned_branch, "execute")
    bp.connect(aligned_branch, "else", misaligned[0], "execute")
    bp.connect(misaligned[0], "then", misaligned[1], "execute")
    bp.connect(aligned_branch, "then", clear_owner_indexes, "execute")
    connect_exec(bp, [clear_owner_indexes, clear_sorted_indexes, clear_failed])
    bp.connect(clear_failed, "then", filter_loop, "Exec")
    bp.connect(owner_indexes, "ScratchListOwnerIndexesV1", clear_owner_indexes, "TargetArray")
    bp.connect(sorted_indexes, "ScratchListSortedIndexesV1", clear_sorted_indexes, "TargetArray")
    bp.connect(filter_loop, "Completed", sort_outer, "Exec")
    bp.connect(sort_outer, "Completed", result_total, "execute")
    connect_exec(bp, [result_total, safe_offset, result_offset, safe_limit, end_exclusive])
    bp.connect(end_exclusive, "then", output_loop, "Exec")
    bp.connect(sorted_for_output, "ScratchListSortedIndexesV1", output_loop, "Array")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_private_list_encoder_base",
    )
    record_encoder = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryRecordEncoderGraphs.py",
        "edd_private_list_record_encoder_base",
    )
    validation = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_private_list_validation_base",
    )
    create = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryPrivateCreateGraph.py",
        "edd_private_list_create_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    templates.update(record_encoder.load_templates(args.project_root, bp, enc))
    json_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-json-node-forms.eddgraph"
    )
    string_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-string-trim-node-form.eddgraph"
    )
    templates["json_SetBoolField"] = bp.find_block(json_forms, r'MemberName="SetBoolField"')
    templates["trim_string"] = bp.find_block(string_forms, r'MemberName="Trim"')
    clean_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "conan-clean-frame-node-forms.eddgraph"
    )
    templates["select"] = bp.find_block(clean_forms, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_Select ")
    graphs = {
        "compare-strings-ordinal-v1.eddgraph": build_ordinal_compare(
            bp, enc, validation, create, templates
        ),
        "encode-metadata-v1.eddgraph": build_metadata(bp, enc, templates),
        "list-mine-v1.eddgraph": build_list(bp, enc, validation, create, templates),
    }
    for filename, nodes in graphs.items():
        enc.write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            enc.write(
                validation.fold_paste_layout(nodes),
                args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"),
                paste=True,
            )


if __name__ == "__main__":
    main()
