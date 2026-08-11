"""Semantic contracts for staged Flypath document JSON encoders."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_repository_encoder_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def one(c, nodes, marker: str):
    return c.one(nodes, marker)


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


def pin_line(node, name: str) -> str:
    return next(line for line in node.text.splitlines() if f'PinName="{name}"' in line)


def assert_closed(c, nodes, expected: int, entry_name: str | None) -> None:
    c.require(len(nodes) == expected, f"Expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    unknown = sorted(
        {
            target
            for node in nodes.values()
            for pin in node.pins.values()
            for target, _ in pin.links
            if target not in known
        }
    )
    c.require(not unknown, f"External links are forbidden: {unknown}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (1 if entry_name else 0), "Function entry inclusion changed")
    if entry_name:
        c.require(f'MemberName="{entry_name}"' in entries[0].text, "Wrong function entry")
    graph_text = "\n".join(node.text for node in nodes.values())
    c.require(
        "/Core/Client/BPC_EDD_ClientDirector" not in graph_text,
        "Repository graph leaked a client-director hidden self pin",
    )
    repository_class = (
        "/Game/Mods/ExileDroneDirector/Server/Repository/"
        "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
    )
    for node in nodes.values():
        if not (
            "K2Node_VariableGet" in node.node_class
            or "K2Node_VariableSet" in node.node_class
        ):
            continue
        c.require(
            repository_class in pin_line(node, "self"),
            f"{node.name} hidden self pin does not target the repository class",
        )


def require_exec_chain(c, nodes) -> None:
    for left, right in zip(nodes, nodes[1:]):
        c.require_link(left, "then", right, "execute", "Canonical field execution order changed")


def require_int_number_bridge(c, nodes, split, source_pin: str, target) -> None:
    conversion_names = {
        node.name
        for node in nodes.values()
        if 'MemberName="Conv_IntToDouble"' in node.text
    }
    linked_names = {name for name, _ in split.pins[source_pin].links}
    matches = conversion_names & linked_names
    c.require(len(matches) == 1, f"{source_pin} must use one explicit integer conversion")
    conversion = nodes[next(iter(matches))]
    c.require_link(split, source_pin, conversion, "InInt", "Integer conversion input changed")
    c.require_link(conversion, "ReturnValue", target, "Number", "Integer conversion output changed")


def assert_waypoint(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 25 if not paste else 24, None if paste else "EncodeWaypointV1")
    store = one(c, nodes, 'MemberName="ScratchNestedJsonV1"')
    fields = [
        field_node(c, nodes, "SetStringField", "annotation"),
        field_node(c, nodes, "SetNumberArrayField", "bodyRotation"),
        field_node(c, nodes, "SetStringField", "cornerMode"),
        field_node(c, nodes, "SetNumberArrayField", "gimbalRotation"),
        field_node(c, nodes, "SetNumberField", "holdSeconds"),
        field_node(c, nodes, "SetNumberField", "aperture"),
        field_node(c, nodes, "SetNumberField", "focalLengthMm"),
        field_node(c, nodes, "SetNumberField", "focusDistanceCm"),
        field_node(c, nodes, "SetObjectField", "lens"),
        field_node(c, nodes, "SetNumberArrayField", "position"),
        field_node(c, nodes, "SetNumberField", "waypointId"),
    ]
    require_exec_chain(c, [store, *fields])
    if paste:
        c.require(not store.pins["execute"].links, "Paste body must expose the root setter")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="EncodeWaypointV1")')
        c.require_link(entry, "then", store, "execute", "Waypoint encoder entry changed")

    split = next(node for node in nodes.values() if "K2Node_BreakStruct" in node.node_class)
    transform = one(c, nodes, 'MemberName="BreakTransform"')
    vector = one(c, nodes, 'MemberName="BreakVector"')
    quat = one(c, nodes, 'MemberName="Conv_RotatorToQuaternion"')
    break_quat = one(c, nodes, 'MemberName="BreakQuat"')
    c.require_link(split, "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9", transform, "InTransform", "Waypoint Transform bridge changed")
    c.require_link(transform, "Location", vector, "InVec", "Position extraction changed")
    c.require_link(transform, "Rotation", quat, "InRot", "Body quaternion conversion changed")
    c.require_link(quat, "ReturnValue", break_quat, "InQuat", "Body quaternion extraction changed")
    c.require("ReturnValue_X" not in quat.pins, "Quaternion conversion return must remain unsplit")

    arrays = [node for node in nodes.values() if "K2Node_MakeArray" in node.node_class]
    c.require(len(arrays) == 3, "Waypoint encoder must own body/gimbal/position arrays")
    by_count = {}
    for node in arrays:
        count = len([name for name in node.pins if re.fullmatch(r"\[\d+\]", name)])
        by_count.setdefault(count, []).append(node)
        c.require('PinType.PinSubCategory="float"' in pin_line(node, "Array"), "JSON number arrays must be float")
    c.require(len(by_count.get(4, [])) == 2 and len(by_count.get(3, [])) == 1, "Quaternion/vector array arities changed")
    position_array = by_count[3][0]
    for source, index in zip(("X", "Y", "Z"), range(3)):
        c.require_link(vector, source, position_array, f"[{index}]", "Position component order changed")
        c.require('PinType.PinSubCategory="double"' in pin_line(vector, source), "Transform coordinates must remain double")
        c.require('PinType.PinSubCategory="float"' in pin_line(position_array, f"[{index}]"), "JSON coordinates must narrow through compiler coercion")

    annotation = fields[0]
    corner = fields[2]
    annotation_value = pin_line(annotation, "StringValue")
    explicit_annotation = re.search(r'DefaultValue="([^"]*)"', annotation_value)
    c.require(
        explicit_annotation is None or explicit_annotation.group(1) == "",
        "Annotation default changed",
    )
    c.require("LinkedTo=" not in annotation_value, "Annotation must remain an unlinked empty string")
    c.require('DefaultValue="glide"' in pin_line(corner, "StringValue"), "Corner mode bridge changed")
    gimbal_array = next(
        node
        for node in by_count[4]
        if 'DefaultValue="1.0"' in pin_line(node, "[3]")
    )
    body_array = next(node for node in by_count[4] if node is not gimbal_array)
    for source, index in zip(
        ("X", "Y", "Z", "W"),
        range(4),
    ):
        c.require_link(
            break_quat,
            source,
            body_array,
            f"[{index}]",
            "Body quaternion component order changed",
        )
    require_int_number_bridge(
        c,
        nodes,
        split,
        "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE",
        fields[-1],
    )
    c.require_link(gimbal_array, "Array", fields[3], "NumberArray", "Identity gimbal bridge changed")
    c.require("bOrphanedPin=True" not in "\n".join(node.text for node in nodes.values()), "Encoder contains orphaned pins")


def assert_segment(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 14 if not paste else 13, None if paste else "EncodeSegmentV1")
    store = one(c, nodes, 'MemberName="ScratchNestedJsonV1"')
    fields = [
        field_node(c, nodes, "SetNumberField", "durationSeconds"),
        field_node(c, nodes, "SetNumberField", "fromWaypointId"),
        field_node(c, nodes, "SetNumberField", "segmentId"),
        field_node(c, nodes, "SetStringField", "spatialCurveType"),
        field_node(c, nodes, "SetStringField", "timeProfile"),
        field_node(c, nodes, "SetNumberField", "toWaypointId"),
    ]
    require_exec_chain(c, [store, *fields])
    if paste:
        c.require(not store.pins["execute"].links, "Paste body must expose the root setter")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="EncodeSegmentV1")')
        c.require_link(entry, "then", store, "execute", "Segment encoder entry changed")
    split = next(node for node in nodes.values() if "K2Node_BreakStruct" in node.node_class)
    expected_sources = (
        "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A",
        "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91",
        "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0",
        "SpatialCurveType_15_39D20A5A4CD2FB464BAA64839CE4012E",
        "TimeProfile_16_3195F0C3470E1AECB34316A7BFBD2FBA",
        "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B",
    )
    integer_sources = {
        "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91",
        "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0",
        "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B",
    }
    for source, target in zip(expected_sources, fields):
        target_pin = "StringValue" if 'SetStringField' in target.text else "Number"
        if source in integer_sources:
            require_int_number_bridge(c, nodes, split, source, target)
        else:
            c.require_link(split, source, target, target_pin, "Segment field mapping changed")


def assert_document(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 37 if not paste else 36, None if paste else "EncodeDocumentV1")
    store = one(c, nodes, 'MemberName="ScratchRootJsonV1"')
    scalar_fields = [
        field_node(c, nodes, "SetStringField", "contentHash"),
        field_node(c, nodes, "SetStringField", "defaultFlightProfile"),
        field_node(c, nodes, "SetNumberField", "durationSeconds"),
        field_node(c, nodes, "SetStringField", "regionId"),
        field_node(c, nodes, "SetNumberField", "revisionNumber"),
        field_node(c, nodes, "SetNumberField", "schemaVersion"),
    ]
    clears = [node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text]
    c.require(len(clears) == 2, "Document encoder must clear object staging before both arrays")
    require_exec_chain(c, [store, *scalar_fields, clears[0]])
    if paste:
        c.require(not store.pins["execute"].links, "Paste body must expose the root setter")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="EncodeDocumentV1")')
        c.require_link(entry, "then", store, "execute", "Document encoder entry changed")

    split = next(node for node in nodes.values() if "K2Node_BreakStruct" in node.node_class)
    segment_loop = next(node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class and "ST_EDD_Segment" in pin_line(node, "Array"))
    waypoint_loop = next(node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class and "ST_EDD_Waypoint" in pin_line(node, "Array"))
    c.require_link(split, "Segments_27_C44AF0F54C828C6532348D8A42A4A92B", segment_loop, "Array", "Segment loop mapping changed")
    c.require_link(split, "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5", waypoint_loop, "Array", "Waypoint loop mapping changed")
    encode_segment = one(c, nodes, 'MemberName="EncodeSegmentV1"')
    encode_waypoint = one(c, nodes, 'MemberName="EncodeWaypointV1"')
    c.require_link(segment_loop, "LoopBody", one(c, nodes, 'MemberName="ScratchSegmentV1"'), "execute", "Segment staging loop changed")
    c.require_link(waypoint_loop, "LoopBody", one(c, nodes, 'MemberName="ScratchWaypointV1"'), "execute", "Waypoint staging loop changed")
    c.require(encode_segment.pins["execute"].links and encode_waypoint.pins["execute"].links, "Nested codec calls must be executable")

    segments = field_node(c, nodes, "SetObjectArrayField", "segments")
    engine = field_node(c, nodes, "SetNumberField", "trajectoryEngineVersion")
    waypoints = field_node(c, nodes, "SetObjectArrayField", "waypoints")
    c.require_link(segment_loop, "Completed", segments, "execute", "Segments must commit after loop completion")
    c.require_link(segments, "then", engine, "execute", "trajectoryEngineVersion canonical position changed")
    c.require_link(engine, "then", clears[1], "execute", "Waypoint staging clear changed")
    require_int_number_bridge(c, nodes, split, "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4", scalar_fields[4])
    require_int_number_bridge(c, nodes, split, "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37", scalar_fields[5])
    require_int_number_bridge(c, nodes, split, "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D", engine)
    c.require_link(waypoint_loop, "Completed", waypoints, "execute", "Waypoints must commit after loop completion")
    encoded = one(c, nodes, 'MemberName="ScratchEncodedDocumentV1"')
    c.require_link(waypoints, "then", encoded, "execute", "Canonical document encode must commit terminally")
    encode_json = one(c, nodes, 'MemberName="EncodeJson"')
    c.require_link(encode_json, "ReturnValue", encoded, "ScratchEncodedDocumentV1", "Encoded text output changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    parser.add_argument(
        "--only",
        choices=("all", "waypoint", "segment", "document"),
        default="all",
        help="Validate one live-exported graph or the complete generated encoder set.",
    )
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    if args.only in ("all", "waypoint"):
        assert_waypoint(c, c.parse_graph(args.input_dir / f"encode-waypoint-v1{suffix}.eddgraph"), paste=args.paste)
    if args.only in ("all", "segment"):
        assert_segment(c, c.parse_graph(args.input_dir / f"encode-segment-v1{suffix}.eddgraph"), paste=args.paste)
    if args.only in ("all", "document"):
        assert_document(c, c.parse_graph(args.input_dir / f"encode-document-v1{suffix}.eddgraph"), paste=args.paste)
    print("Repository document encoder graph contracts passed")


if __name__ == "__main__":
    main()
