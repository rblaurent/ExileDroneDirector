"""Semantic contracts for the generated SyncDraftDocumentV1 Blueprint graph."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


MAX_INT = "2147483647"
SEGMENT_MARKER = "ST_EDD_Segment.ST_EDD_Segment'"
DOCUMENT_MARKER = "ST_EDD_FlypathDocument.ST_EDD_FlypathDocument'"
WAYPOINT_MARKER = "ST_EDD_Waypoint.ST_EDD_Waypoint'"

WP_ID = "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE"
WP_HOLD = "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB"
SEG_ID = "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0"
SEG_FROM = "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91"
SEG_TO = "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B"
SEG_DURATION = "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A"
DOC_SCHEMA = "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"
DOC_ENGINE = "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D"
DOC_REVISION = "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"
DOC_REGION = "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"
DOC_DURATION = "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"
DOC_PROFILE = "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161"
DOC_WAYPOINTS = "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"
DOC_SEGMENTS = "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"
DOC_HASH = "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"


def load_contract_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointStructSyncContracts.py"
    spec = importlib.util.spec_from_file_location("edd_document_contract_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph contract helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_contract(graph: Path, project_root: Path, has_entry: bool) -> None:
    c = load_contract_helpers(project_root)
    nodes = c.parse(graph)
    c.require(len(nodes) == (124 if has_entry else 123), f"Unexpected node count: {len(nodes)}")

    pins_by_id = {
        (node.name, pin.pin_id): (node, pin_name, pin)
        for node in nodes.values()
        for pin_name, pin in node.pins.items()
    }
    checked_edges = set()
    for node in nodes.values():
        for pin_name, pin in node.pins.items():
            is_output = 'Direction="EGPD_Output"' in pin.body
            if not is_output:
                c.require(
                    len(pin.links) <= 1,
                    f"Input pin has multiple links: {node.name}.{pin_name}",
                )
            for target_name, target_pin_id in pin.links:
                edge = tuple(sorted(((node.name, pin.pin_id), (target_name, target_pin_id))))
                if edge in checked_edges or (target_name, target_pin_id) not in pins_by_id:
                    continue
                checked_edges.add(edge)
                target_node, target_pin_name, target_pin = pins_by_id[(target_name, target_pin_id)]
                target_is_output = 'Direction="EGPD_Output"' in target_pin.body
                c.require(
                    is_output != target_is_output,
                    "Pin direction mismatch: "
                    f"{node.name}.{pin_name} -> {target_node.name}.{target_pin_name}",
                )

    entries = [node for node in nodes.values() if 'MemberName="SyncDraftDocumentV1"' in node.text]
    c.require(len(entries) == (1 if has_entry else 0), "Function entry inclusion changed")
    if not has_entry:
        unknown = sorted(
            {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links}
            - set(nodes)
        )
        c.require(not unknown, f"Paste graph contains external links: {unknown}")

    sync_calls = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_CallFunction")
        and re.search(
            r'FunctionReference=\([^)]*MemberName="SyncDraftWaypointsV1"[^)]*bSelfContext=True[^)]*\)',
            node.text,
        )
    ]
    c.require(len(sync_calls) == 1, "Document sync must invoke typed waypoint preflight once")
    sync = sync_calls[0]
    preflight_get = c.one(nodes, 'VariableReference=(MemberName="WaypointPreflightValid"')
    preflight_fail = c.one(nodes, "waypoint preflight failed")
    preflight_branch = next(
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_IfThenElse")
        and (node.name, node.pins["Condition"].pin_id) in preflight_get.pins["WaypointPreflightValid"].links
    )
    if has_entry:
        c.require_link(entries[0], "then", sync, "execute", "Entry must rebuild typed waypoints first")
    else:
        c.require(not sync.pins["execute"].links, "Paste body must expose one intentional entry pin")
    c.require_link(sync, "then", preflight_branch, "execute", "Typed rebuild must gate document work")
    c.require_link(preflight_branch, "else", preflight_fail, "execute", "Invalid waypoints must reject")

    loops = [node for node in nodes.values() if "StandardMacros:ForEachLoop" in node.text]
    c.require(len(loops) == 3, "Prior scan, waypoint scan, and nested match scan are required")
    clears = [node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text]
    adds = [node for node in nodes.values() if 'MemberName="Array_Add"' in node.text]
    c.require(len(clears) == 2, "Used-ID and segment scratch arrays must be cleared")
    c.require(len(adds) == 4, "Preserved/new paths must each append segment and used ID")
    c.require(len([n for n in nodes.values() if 'MemberName="Array_Find"' in n.text]) == 1, "Used-ID lookup changed")

    struct_nodes = [node for node in nodes.values() if "K2Node_MakeStruct" in node.node_class or "K2Node_BreakStruct" in node.node_class]
    def owns_struct(node, marker: str) -> bool:
        return re.search(rf'^\s*StructType="[^"]*{re.escape(marker)}"$', node.text, re.MULTILINE) is not None

    make_segments = [n for n in struct_nodes if n.node_class.endswith("K2Node_MakeStruct") and owns_struct(n, SEGMENT_MARKER)]
    make_documents = [n for n in struct_nodes if n.node_class.endswith("K2Node_MakeStruct") and owns_struct(n, DOCUMENT_MARKER)]
    break_segments = [n for n in struct_nodes if n.node_class.endswith("K2Node_BreakStruct") and owns_struct(n, SEGMENT_MARKER)]
    break_waypoints = [n for n in struct_nodes if n.node_class.endswith("K2Node_BreakStruct") and owns_struct(n, WAYPOINT_MARKER)]
    break_documents = [n for n in struct_nodes if n.node_class.endswith("K2Node_BreakStruct") and owns_struct(n, DOCUMENT_MARKER)]
    c.require(len(make_segments) == 1, "Exactly one default segment constructor is required")
    c.require(len(make_documents) == 1, "Exactly one final document constructor is required")
    c.require(len(break_segments) == 3, "Prior scan, match scan, and preserved append need segment breaks")
    c.require(len(break_waypoints) == 2, "Current and next waypoint breaks are required")
    c.require(len(break_documents) == 1, "Prior document metadata must be read once")
    document_break = break_documents[0]

    def metadata_guard(field_pin: str, member_name: str, expected_default: str):
        matches = [
            node
            for node in nodes.values()
            if f'MemberName="{member_name}"' in node.text
            and (node.name, node.pins["A"].pin_id) in document_break.pins[field_pin].links
        ]
        c.require(len(matches) == 1, f"Metadata guard changed for {field_pin}")
        guard = matches[0]
        default_match = re.search(r'DefaultValue="([^"]*)"', guard.pins["B"].body)
        c.require(
            default_match is not None and default_match.group(1) == expected_default,
            f"Metadata guard constant changed for {field_pin}",
        )
        c.require(not guard.pins["B"].links, f"Metadata guard B must stay unlinked for {field_pin}")
        return guard

    metadata_guard(DOC_SCHEMA, "EqualEqual_IntInt", "1")
    metadata_guard(DOC_ENGINE, "EqualEqual_IntInt", "1")
    metadata_guard(DOC_REVISION, "GreaterEqual_IntInt", "0")

    next_id_initializers = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet")
        and 'MemberName="DocumentNextSegmentIdV1"' in node.text
        and not node.pins["DocumentNextSegmentIdV1"].links
    ]
    c.require(len(next_id_initializers) == 1, "Next-segment ID needs one unlinked transaction initializer")
    next_id_default = re.search(
        r'DefaultValue="([^"]*)"',
        next_id_initializers[0].pins["DocumentNextSegmentIdV1"].body,
    )
    c.require(
        next_id_default is not None and next_id_default.group(1) == "0",
        "Next-segment ID transaction must start from zero",
    )

    max_nodes = [
        node
        for node in nodes.values()
        if (
            node.node_class.endswith("K2Node_CallFunction")
            and 'MemberName="Max_IntInt"' in node.text
        )
        or (
            node.node_class.endswith("K2Node_CommutativeAssociativeBinaryOperator")
            and 'MemberName="Max"' in node.text
        )
    ]
    c.require(len(max_nodes) == 1, f"Integer Max representation changed: {len(max_nodes)}")
    max_id = max_nodes[0]
    c.require(
        all(pin in max_id.pins for pin in ("A", "B", "ReturnValue")),
        "Integer Max pins changed",
    )
    c.require(
        all('PinType.PinCategory="int"' in max_id.pins[pin].body for pin in ("A", "B", "ReturnValue")),
        "Monotonic ID Max must remain integer-typed",
    )

    for marker, count in (
        ('MemberName="Less_IntInt"', 1),
        ('MemberName="Array_Find"', 1),
        ('MemberName="EqualEqual_StrStr"', 5),
        ('MemberName="Add_DoubleDouble"', 3),
        ('MemberName="Subtract_DoubleDouble"', 3),
    ):
        found = [node for node in nodes.values() if marker in node.text]
        c.require(len(found) == count, f"{marker} count changed: {len(found)}")

    exhausted = next(
        node
        for node in nodes.values()
        if 'MemberName="GreaterEqual_IntInt"' in node.text and f'DefaultValue="{MAX_INT}"' in node.pins["B"].body
    )
    c.require(f'DefaultValue="{MAX_INT}"' in exhausted.pins["B"].body, "ID ceiling guard changed")
    exhausted_message = c.one(nodes, "segment ID space exhausted")
    invalid_setters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet")
        and 'MemberName="DocumentSyncValidV1"' in node.text
        and re.search(r'(?:^|,)DefaultValue="false"', node.pins["DocumentSyncValidV1"].body)
    ]
    c.require(len(invalid_setters) == 1, "Exhaustion must own the only runtime invalidation setter")
    c.require_link(invalid_setters[0], "then", exhausted_message, "execute", "ID exhaustion needs an explicit diagnostic")

    next_id_getters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableGet")
        and 'MemberName="DocumentNextSegmentIdV1"' in node.text
        and (max_id.name, max_id.pins["A"].pin_id) in node.pins["DocumentNextSegmentIdV1"].links
    ]
    c.require(len(next_id_getters) == 1, "Monotonic ID Max must read the current next ID")
    prior_id_breaks = [
        node
        for node in break_segments
        if (max_id.name, max_id.pins["B"].pin_id) in node.pins[SEG_ID].links
    ]
    c.require(len(prior_id_breaks) == 1, "Monotonic ID Max must read each prior segment ID")
    next_id_setters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet")
        and 'MemberName="DocumentNextSegmentIdV1"' in node.text
        and (max_id.name, max_id.pins["ReturnValue"].pin_id)
        in node.pins["DocumentNextSegmentIdV1"].links
    ]
    c.require(len(next_id_setters) == 1, "Monotonic ID Max must update the next-ID floor")

    make_segment = make_segments[0]
    increment = next(
        node
        for node in nodes.values()
        if 'MemberName="Add_IntInt"' in node.text
        and 'DefaultValue="1"' in node.pins["B"].body
        and any(
            target.node_class.endswith("K2Node_VariableSet")
            and 'MemberName="DocumentNextSegmentIdV1"' in target.text
            and (target.name, target.pins["DocumentNextSegmentIdV1"].pin_id) in node.pins["ReturnValue"].links
            for target in nodes.values()
        )
    )
    committed_id_setters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet")
        and 'MemberName="DocumentNextSegmentIdV1"' in node.text
        and (node.name, node.pins["DocumentNextSegmentIdV1"].pin_id) in increment.pins["ReturnValue"].links
    ]
    c.require(len(committed_id_setters) == 1, "Increment must write one committed next-ID setter")
    committed_id = committed_id_setters[0]
    c.require_link(committed_id, "Output_Get", make_segment, SEG_ID, "New segment must use the committed next ID")
    new_id_adds = [
        node
        for node in nodes.values()
        if 'MemberName="Array_Add"' in node.text
        and 'PinType.PinCategory="int"' in node.pins["NewItem"].body
        and (node.name, node.pins["NewItem"].pin_id) in committed_id.pins["Output_Get"].links
    ]
    c.require(len(new_id_adds) == 1, "New segment ID must append from the committed setter output")
    default_duration_adds = [
        node
        for node in nodes.values()
        if 'MemberName="Add_DoubleDouble"' in node.text
        and (
            (match := re.search(r'DefaultValue="([+-]?(?:\d+(?:\.\d*)?|\.\d+))"', node.pins["B"].body))
            is not None
            and abs(float(match.group(1)) - 3.0) < 1e-9
        )
        and not node.pins["B"].links
    ]
    c.require(len(default_duration_adds) == 1, "New segment duration total must use the 3-second default")
    current_break, next_break = break_waypoints
    c.require(
        any((make_segment.name, make_segment.pins[SEG_FROM].pin_id) in node.pins[WP_ID].links for node in break_waypoints),
        "New segment FromWaypointId must come from a waypoint break",
    )
    c.require(
        any((make_segment.name, make_segment.pins[SEG_TO].pin_id) in node.pins[WP_ID].links for node in break_waypoints),
        "New segment ToWaypointId must come from a waypoint break",
    )
    c.require('DefaultValue="3.000000"' in make_segment.pins[SEG_DURATION].body, "New segment duration default changed")
    c.require('DefaultValue="linear"' in make_segment.text, "New segment curve/profile defaults changed")

    public_segment_setters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet") and 'MemberName="DraftSegmentsV1"' in node.text
    ]
    public_document_setters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableSet") and 'MemberName="DraftDocumentV1"' in node.text
    ]
    c.require(len(public_segment_setters) == 1, "DraftSegmentsV1 must have one final commit setter")
    c.require(len(public_document_setters) == 1, "DraftDocumentV1 must have one final commit setter")
    segment_set = public_segment_setters[0]
    document_set = public_document_setters[0]
    c.require_link(segment_set, "then", document_set, "execute", "Public values must commit in one final chain")

    make_document = make_documents[0]
    for pin in (DOC_REVISION, DOC_REGION, DOC_PROFILE):
        c.require_link(document_break, pin, make_document, pin, f"Prior metadata {pin} must be preserved")
    c.require('DefaultValue="1"' in make_document.pins[DOC_SCHEMA].body, "Schema version default changed")
    c.require('DefaultValue="1"' in make_document.pins[DOC_ENGINE].body, "Trajectory engine default changed")
    hash_default = re.search(r'(?:^|,)DefaultValue="([^"]*)"', make_document.pins[DOC_HASH].body)
    c.require(hash_default is None or hash_default.group(1) == "", "Content hash must remain empty")
    c.require_link(make_document, "ST_EDD_FlypathDocument", document_set, "DraftDocumentV1", "Final document value must be published")
    c.require(WAYPOINT_MARKER in make_document.pins[DOC_WAYPOINTS].body, "Document lost typed waypoint array")
    c.require(SEGMENT_MARKER in make_document.pins[DOC_SEGMENTS].body, "Document lost typed segment array")

    scratch_commit_getters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableGet")
        and 'MemberName="DocumentSegmentsScratchV1"' in node.text
        and (segment_set.name, segment_set.pins["DraftSegmentsV1"].pin_id) in node.pins["DocumentSegmentsScratchV1"].links
    ]
    c.require(len(scratch_commit_getters) == 1, "Final segment commit must copy validated scratch storage")
    scratch_commit = scratch_commit_getters[0]
    c.require_link(scratch_commit, "DocumentSegmentsScratchV1", segment_set, "DraftSegmentsV1", "Scratch segments must publish")
    c.require_link(scratch_commit, "DocumentSegmentsScratchV1", make_document, DOC_SEGMENTS, "Document and public segments must share snapshot")

    typed_commit_getters = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_VariableGet")
        and 'MemberName="DraftWaypointsV1"' in node.text
        and (make_document.name, make_document.pins[DOC_WAYPOINTS].pin_id) in node.pins["DraftWaypointsV1"].links
    ]
    c.require(len(typed_commit_getters) == 1, "Final document must copy validated typed waypoints")
    success = c.one(nodes, "[EDD] Document sync complete")
    c.require_link(document_set, "then", success, "execute", "Successful atomic commit needs diagnostic")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste-graph", type=Path)
    args = parser.parse_args()
    assert_contract(args.graph, args.project_root, has_entry=True)
    if args.paste_graph:
        assert_contract(args.paste_graph, args.project_root, has_entry=False)
    print("Document sync graph contracts passed.")


if __name__ == "__main__":
    main()
