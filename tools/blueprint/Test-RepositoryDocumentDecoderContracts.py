"""Semantic contracts for strict staged Flypath document JSON decoders."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_repository_decoder_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin(c, node, name: str):
    return c.pin(node, name)


def one(c, nodes, marker: str):
    return c.one(nodes, marker)


def function_call(c, nodes, name: str):
    """Find a call by name even after the editor injects a MemberGuid."""
    marker = re.compile(rf'FunctionReference=\(MemberName="{re.escape(name)}"(?:,|\))')
    matches = [
        node for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class and marker.search(node.text)
    ]
    c.require(len(matches) == 1, f"Expected one call to {name}; found {len(matches)}")
    return matches[0]


def variable(c, nodes, name: str, node_class: str):
    matches = [
        node for node in nodes.values()
        if node_class in node.node_class and f'VariableReference=(MemberName="{name}"' in node.text
    ]
    c.require(len(matches) == 1, f"Expected one {node_class} for {name}; found {len(matches)}")
    return matches[0]


def field_node(c, nodes, function: str, field: str):
    matches = [
        node
        for node in nodes.values()
        if f'MemberName="{function}"' in node.text
        and any(
            'PinName="FieldName"' in line and f'DefaultValue="{field}"' in line
            for line in node.text.splitlines()
        )
    ]
    c.require(len(matches) == 1, f"Expected one {function}({field}); found {len(matches)}")
    return matches[0]


def assert_closed(c, nodes, expected: int, entry_name: str | None) -> None:
    c.require(len(nodes) == expected, f"Expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    external = sorted({
        target
        for node in nodes.values()
        for node_pin in node.pins.values()
        for target, _ in node_pin.links
        if target not in known
    })
    c.require(not external, f"External links are forbidden: {external}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (1 if entry_name else 0), "Function-entry inclusion changed")
    if entry_name:
        c.require(f'MemberName="{entry_name}"' in entries[0].text, "Wrong function entry")
    graph_text = "\n".join(node.text for node in nodes.values())
    c.require("bOrphanedPin=True" not in graph_text, "Decoder contains orphaned pins")
    c.require("/Core/Client/BPC_EDD_ClientDirector" not in graph_text, "Decoder leaked a client hidden self pin")


def require_exec_chain(c, nodes) -> None:
    for left, right in zip(nodes, nodes[1:]):
        right_pin = "Exec" if "K2Node_MacroInstance" in right.node_class else "execute"
        c.require_link(left, "then", right, right_pin, "Decoder execution order changed")


def require_split_quat(c, quat) -> None:
    parent = pin(c, quat, "Q").body
    parent_id = re.search(r"PinId=([0-9A-F]{32})", parent).group(1)
    subpins = re.search(r"SubPins=\(([^)]*)\)", parent)
    c.require(subpins is not None, "Quat input must remain split")
    actual = set(re.findall(rf"{re.escape(quat.name)} ([0-9A-F]{{32}})", subpins.group(1)))
    expected = set()
    for name in ("Q_X", "Q_Y", "Q_Z", "Q_W"):
        body = pin(c, quat, name).body
        pin_id = re.search(r"PinId=([0-9A-F]{32})", body).group(1)
        parent_ref = re.search(rf"ParentPin={re.escape(quat.name)} ([0-9A-F]{{32}})", body)
        c.require(parent_ref is not None and parent_ref.group(1) == parent_id, f"{name} parent GUID is stale")
        c.require('PinType.PinSubCategory="float"' in body, f"{name} precision changed")
        expected.add(pin_id)
    c.require(actual == expected, "Quat parent sub-pin GUIDs are stale")


def array_items_from(c, nodes, source):
    items = [node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]
    linked = []
    for item in items:
        if c.linked(source, "ReturnValue", item, "Array"):
            linked.append(item)
    return linked


def index_of(c, item) -> int:
    match = re.search(r'DefaultValue="(-?\d+)"', pin(c, item, "Dimension 1").body)
    c.require(match is not None, f"{item.name} has no literal index")
    return int(match.group(1))


def require_float_item(c, item) -> None:
    for name in ("Array", "Output"):
        body = pin(c, item, name).body
        c.require('PinType.PinCategory="real"' in body, f"{item.name}.{name} category changed")
        c.require('PinType.PinSubCategory="float"' in body, f"{item.name}.{name} precision changed")


def require_float_length(c, length) -> None:
    body = pin(c, length, "TargetArray").body
    c.require('PinType.PinCategory="real"' in body, f"{length.name} category changed")
    c.require('PinType.PinSubCategory="float"' in body, f"{length.name} precision changed")


def assert_waypoint(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 38 if not paste else 37, None if paste else "DecodeWaypointV1")
    source_store = variable(c, nodes, "ScratchSourceJsonV1", "K2Node_VariableSet")
    source_encode = [
        node for node in nodes.values()
        if 'MemberName="EncodeJson"' in node.text and c.linked(node, "ReturnValue", source_store, "ScratchSourceJsonV1")
    ]
    c.require(len(source_encode) == 1, "Waypoint source must be encoded exactly once before mutation")
    source_objects = [
        node for node in nodes.values()
        if "K2Node_VariableGet" in node.node_class
        and 'MemberName="ScratchNestedJsonV1"' in node.text
        and c.linked(node, "ScratchNestedJsonV1", source_encode[0], "self")
    ]
    c.require(len(source_objects) == 1, "Waypoint source encoding input changed")

    position = field_node(c, nodes, "GetNumberArrayField", "position")
    body = field_node(c, nodes, "GetNumberArrayField", "bodyRotation")
    lengths = [node for node in nodes.values() if 'MemberName="Array_Length"' in node.text]
    equal_ints = [node for node in nodes.values() if 'MemberName="EqualEqual_IntInt"' in node.text]
    guards = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(lengths) == 2 and len(equal_ints) == 2 and len(guards) == 2, "Waypoint arity guard topology changed")
    position_length = next(node for node in lengths if c.linked(position, "ReturnValue", node, "TargetArray"))
    body_length = next(node for node in lengths if c.linked(body, "ReturnValue", node, "TargetArray"))
    require_float_length(c, position_length)
    require_float_length(c, body_length)
    position_equal = next(node for node in equal_ints if c.linked(position_length, "ReturnValue", node, "A"))
    body_equal = next(node for node in equal_ints if c.linked(body_length, "ReturnValue", node, "A"))
    c.require('DefaultValue="3"' in pin(c, position_equal, "B").body, "Position arity must remain exactly three")
    c.require('DefaultValue="4"' in pin(c, body_equal, "B").body, "Body quaternion arity must remain exactly four")
    position_guard = next(node for node in guards if c.linked(position_equal, "ReturnValue", node, "Condition"))
    body_guard = next(node for node in guards if c.linked(body_equal, "ReturnValue", node, "Condition"))
    c.require(not pin(c, position_guard, "else").links, "Bad position arity must terminate without array reads")
    c.require(not pin(c, body_guard, "else").links, "Bad quaternion arity must terminate without array reads")
    position_items = sorted(array_items_from(c, nodes, position), key=lambda item: index_of(c, item))
    body_items = sorted(array_items_from(c, nodes, body), key=lambda item: index_of(c, item))
    c.require([index_of(c, item) for item in position_items] == [0, 1, 2], "Position array arity/order changed")
    c.require([index_of(c, item) for item in body_items] == [0, 1, 2, 3], "Body quaternion arity/order changed")
    for item in (*position_items, *body_items):
        require_float_item(c, item)

    vector = one(c, nodes, 'MemberName="MakeVector"')
    quat = one(c, nodes, 'MemberName="Quat_Rotator"')
    transform = one(c, nodes, 'MemberName="MakeTransform"')
    require_split_quat(c, quat)
    for item, component in zip(position_items, ("X", "Y", "Z")):
        c.require_link(item, "Output", vector, component, "Position component mapping changed")
    for item, component in zip(body_items, ("Q_X", "Q_Y", "Q_Z", "Q_W")):
        c.require_link(item, "Output", quat, component, "Body quaternion component mapping changed")
    c.require_link(vector, "ReturnValue", transform, "Location", "Decoded position no longer drives Transform")
    c.require_link(quat, "ReturnValue", transform, "Rotation", "Decoded quaternion no longer drives Transform")

    lens = field_node(c, nodes, "GetObjectField", "lens")
    aperture = field_node(c, nodes, "GetNumberField", "aperture")
    focal = field_node(c, nodes, "GetNumberField", "focalLengthMm")
    focus = field_node(c, nodes, "GetNumberField", "focusDistanceCm")
    for node in (aperture, focal, focus):
        c.require_link(lens, "ReturnValue", node, "self", "Lens scalar parent changed")
    hold = field_node(c, nodes, "GetNumberField", "holdSeconds")
    waypoint_id = field_node(c, nodes, "GetNumberField", "waypointId")
    trunc = one(c, nodes, 'MemberName="FTrunc"')
    c.require_link(waypoint_id, "ReturnValue", trunc, "A", "Waypoint ID conversion changed")

    make = next(node for node in nodes.values() if "K2Node_MakeStruct" in node.node_class)
    c.require_link(trunc, "ReturnValue", make, "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE", "Waypoint ID mapping changed")
    c.require_link(transform, "ReturnValue", make, "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9", "Waypoint Transform mapping changed")
    for source, target in (
        (focal, "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B"),
        (aperture, "Aperture_10_949C579344F8DFA750F1948051A417B2"),
        (focus, "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F"),
        (hold, "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB"),
    ):
        c.require_link(source, "ReturnValue", make, target, "Waypoint scalar mapping changed")

    store = variable(c, nodes, "ScratchWaypointV1", "K2Node_VariableSet")
    encode = function_call(c, nodes, "EncodeWaypointV1")
    equal = one(c, nodes, 'MemberName="EqualEqual_StrStr"')
    valid_setters = [
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class and 'MemberName="ScratchValidV1"' in node.text
    ]
    c.require(len(valid_setters) == 2, "Waypoint decoder must reset and terminally commit validity")
    valid = next(node for node in valid_setters if c.linked(equal, "ReturnValue", node, "ScratchValidV1"))
    valid_reset = next(node for node in valid_setters if node is not valid)
    c.require('DefaultValue="false"' in pin(c, valid_reset, "ScratchValidV1").body, "Waypoint validity reset changed")
    c.require_link(valid_reset, "then", source_store, "execute", "Waypoint source preservation must follow validity reset")
    c.require_link(source_store, "then", position, "execute", "Waypoint position decode order changed")
    c.require_link(position, "then", position_guard, "execute", "Position arity must be checked immediately")
    c.require_link(position_guard, "then", body, "execute", "Body decode must be gated by position arity")
    c.require_link(body, "then", body_guard, "execute", "Body arity must be checked immediately")
    c.require_link(body_guard, "then", store, "execute", "Waypoint construction must be gated by body arity")
    require_exec_chain(c, [store, encode, valid])
    if paste:
        c.require(not pin(c, valid_reset, "execute").links, "Paste body must expose validity reset")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="DecodeWaypointV1")')
        c.require_link(entry, "then", valid_reset, "execute", "Waypoint decoder entry changed")
    c.require_link(equal, "ReturnValue", valid, "ScratchValidV1", "Waypoint validity must be canonical equality")


def assert_segment(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 21 if not paste else 20, None if paste else "DecodeSegmentV1")
    source_store = variable(c, nodes, "ScratchSourceJsonV1", "K2Node_VariableSet")
    store = variable(c, nodes, "ScratchSegmentV1", "K2Node_VariableSet")
    encode = function_call(c, nodes, "EncodeSegmentV1")
    valid = variable(c, nodes, "ScratchValidV1", "K2Node_VariableSet")
    require_exec_chain(c, [source_store, store, encode, valid])
    if paste:
        c.require(not pin(c, source_store, "execute").links, "Paste body must expose source setter")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="DecodeSegmentV1")')
        c.require_link(entry, "then", source_store, "execute", "Segment decoder entry changed")

    make = next(node for node in nodes.values() if "K2Node_MakeStruct" in node.node_class)
    scalar_map = (
        ("durationSeconds", "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A", False),
        ("fromWaypointId", "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91", True),
        ("segmentId", "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0", True),
        ("spatialCurveType", "SpatialCurveType_15_39D20A5A4CD2FB464BAA64839CE4012E", False),
        ("timeProfile", "TimeProfile_16_3195F0C3470E1AECB34316A7BFBD2FBA", False),
        ("toWaypointId", "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B", True),
    )
    for field, target, integer in scalar_map:
        getter = field_node(c, nodes, "GetNumberField" if integer or field == "durationSeconds" else "GetStringField", field)
        if integer:
            linked_truncs = [node for node in nodes.values() if 'MemberName="FTrunc"' in node.text and c.linked(getter, "ReturnValue", node, "A")]
            c.require(len(linked_truncs) == 1, f"{field} must use one FTrunc")
            c.require_link(linked_truncs[0], "ReturnValue", make, target, f"{field} integer mapping changed")
        else:
            c.require_link(getter, "ReturnValue", make, target, f"{field} mapping changed")
    equal = one(c, nodes, 'MemberName="EqualEqual_StrStr"')
    c.require_link(equal, "ReturnValue", valid, "ScratchValidV1", "Segment validity must be canonical equality")


def assert_document(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 46 if not paste else 45, None if paste else "DecodeDocumentV1")
    source = variable(c, nodes, "ScratchSourceDocumentJsonV1", "K2Node_VariableSet")
    root = variable(c, nodes, "ScratchRootJsonV1", "K2Node_VariableSet")
    decode = one(c, nodes, 'MemberName="DecodeJson"')
    decode_guards = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    c.require(len(decode_guards) == 1, "Document decoder must gate all field reads on DecodeJson success")
    decode_guard = decode_guards[0]
    c.require_link(decode, "ReturnValue", decode_guard, "Condition", "DecodeJson result must drive the root guard")
    c.require_link(decode, "then", decode_guard, "execute", "Document root guard order changed")
    c.require(not pin(c, decode_guard, "else").links, "Invalid JSON must terminate before any root field read")
    c.require_link(source, "Output_Get", decode, "JsonString", "Document source preservation changed")
    c.require_link(root, "Output_Get", decode, "self", "Document DecodeJson target changed")

    clears = [node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text]
    c.require(len(clears) == 2, "Document decoder must clear both typed staging arrays")
    c.require(any(c.linked(decode_guard, "then", node, "execute") for node in clears), "Root reads must start only after DecodeJson succeeds")
    get_segments = field_node(c, nodes, "GetObjectArrayField", "segments")
    get_waypoints = field_node(c, nodes, "GetObjectArrayField", "waypoints")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    c.require(len(loops) == 2, "Document decoder must own two object loops")
    segment_loop = next(node for node in loops if c.linked(get_segments, "ReturnValue", node, "Array"))
    waypoint_loop = next(node for node in loops if c.linked(get_waypoints, "ReturnValue", node, "Array"))
    decode_segment = function_call(c, nodes, "DecodeSegmentV1")
    decode_waypoint = function_call(c, nodes, "DecodeWaypointV1")
    segment_nested = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and 'MemberName="ScratchNestedJsonV1"' in node.text and c.linked(segment_loop, "Array Element", node, "ScratchNestedJsonV1")]
    waypoint_nested = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and 'MemberName="ScratchNestedJsonV1"' in node.text and c.linked(waypoint_loop, "Array Element", node, "ScratchNestedJsonV1")]
    c.require(len(segment_nested) == 1 and len(waypoint_nested) == 1, "Nested object staging changed")
    c.require_link(segment_nested[0], "then", decode_segment, "execute", "Segment decode loop changed")
    c.require_link(waypoint_nested[0], "then", decode_waypoint, "execute", "Waypoint decode loop changed")

    make = next(node for node in nodes.values() if "K2Node_MakeStruct" in node.node_class)
    scalar_map = (
        ("schemaVersion", "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37", True),
        ("trajectoryEngineVersion", "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D", True),
        ("revisionNumber", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4", True),
        ("regionId", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4", False),
        ("durationSeconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9", False),
        ("defaultFlightProfile", "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161", False),
        ("contentHash", "ContentHash_28_C376573940EDD8D9F911D9800DB430BC", False),
    )
    for field, target, integer in scalar_map:
        numeric = integer or field == "durationSeconds"
        getter = field_node(c, nodes, "GetNumberField" if numeric else "GetStringField", field)
        if integer:
            truncs = [node for node in nodes.values() if 'MemberName="FTrunc"' in node.text and c.linked(getter, "ReturnValue", node, "A")]
            c.require(len(truncs) == 1, f"{field} must use one FTrunc")
            c.require_link(truncs[0], "ReturnValue", make, target, f"{field} integer mapping changed")
        else:
            c.require_link(getter, "ReturnValue", make, target, f"{field} mapping changed")
    # Three getters exist; choose the one attached to the final Make Struct.
    waypoint_getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and 'MemberName="ScratchWaypointsV1"' in node.text]
    segment_getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and 'MemberName="ScratchSegmentsV1"' in node.text]
    c.require(any(c.linked(node, "ScratchWaypointsV1", make, "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5") for node in waypoint_getters), "Final waypoint array mapping changed")
    c.require(any(c.linked(node, "ScratchSegmentsV1", make, "Segments_27_C44AF0F54C828C6532348D8A42A4A92B") for node in segment_getters), "Final segment array mapping changed")

    store = variable(c, nodes, "ScratchDocumentV1", "K2Node_VariableSet")
    encode = function_call(c, nodes, "EncodeDocumentV1")
    c.require_link(waypoint_loop, "Completed", store, "execute", "Document commit must follow waypoint loop")
    c.require_link(store, "then", encode, "execute", "Document re-encode order changed")
    equal = one(c, nodes, 'MemberName="EqualEqual_StrStr"')
    valid_setters = [
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class and 'MemberName="ScratchValidV1"' in node.text
    ]
    c.require(len(valid_setters) == 2, "Document decoder must reset and terminally commit validity")
    valid = next(node for node in valid_setters if c.linked(equal, "ReturnValue", node, "ScratchValidV1"))
    valid_reset = next(node for node in valid_setters if node is not valid)
    c.require('DefaultValue="false"' in pin(c, valid_reset, "ScratchValidV1").body, "Document validity reset changed")
    c.require_link(valid_reset, "then", source, "execute", "Document source preservation must follow validity reset")
    c.require_link(encode, "then", valid, "execute", "Document validity must commit terminally")
    c.require_link(equal, "ReturnValue", valid, "ScratchValidV1", "Document validity must be canonical equality")
    if paste:
        c.require(not pin(c, valid_reset, "execute").links, "Paste body must expose validity reset")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="DecodeDocumentV1")')
        c.require_link(entry, "then", valid_reset, "execute", "Document decoder entry changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument("--only", choices=("all", "waypoint", "segment", "document"), default="all")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    if args.only in ("all", "waypoint"):
        assert_waypoint(c, c.parse_graph(args.input_dir / f"decode-waypoint-v1{suffix}.eddgraph"), paste=args.paste)
    if args.only in ("all", "segment"):
        assert_segment(c, c.parse_graph(args.input_dir / f"decode-segment-v1{suffix}.eddgraph"), paste=args.paste)
    if args.only in ("all", "document"):
        assert_document(c, c.parse_graph(args.input_dir / f"decode-document-v1{suffix}.eddgraph"), paste=args.paste)
    print("Repository document decoder graph contracts passed")


if __name__ == "__main__":
    main()
