"""Build strict staged JSON decoders for Flypath documents.

Each decoder preserves its source, projects JSON into the typed repository
scratch struct, calls the corresponding accepted encoder, and commits validity
only from exact canonical string equality.  This turns PlayFab's permissive
getter defaults into deterministic rejection of missing, extra, mistyped,
misordered, or otherwise noncanonical payloads.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_encoder(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_repository_decoder_encoder_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load encoder graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def float_array_item(node) -> None:
    def mutate(line: str) -> str:
        line = line.replace('PinType.PinCategory="wildcard"', 'PinType.PinCategory="real"')
        line = re.sub(
            r'PinType\.PinSubCategory="(?:double|float)?"',
            'PinType.PinSubCategory="float"',
            line,
            count=1,
        )
        return line

    node.mutate_pin("Array", mutate)
    node.mutate_pin("Output", mutate)


def float_array_length(node) -> None:
    def mutate(line: str) -> str:
        line = line.replace('PinType.PinCategory="wildcard"', 'PinType.PinCategory="real"')
        line = re.sub(
            r'PinType\.PinSubCategory="(?:double|float)?"',
            'PinType.PinSubCategory="float"',
            line,
            count=1,
        )
        return line

    node.mutate_pin("TargetArray", mutate)


def load_templates(project_root: Path, bp, enc) -> dict[str, str]:
    root = project_root / "tools" / "blueprint"
    templates = enc.load_templates(project_root, bp)
    json_forms = bp.read_blocks(root / "templates" / "repository-json-node-forms.eddgraph")
    decoder_forms = bp.read_blocks(root / "templates" / "repository-decoder-native-node-forms.eddgraph")
    transform_forms = bp.read_blocks(root / "templates" / "repository-codec-transform-node-forms.eddgraph")
    marker_forms = bp.read_blocks(root / "templates" / "path-preview-marker-node-forms.eddgraph")
    linear_forms = bp.read_blocks(root / "templates" / "linear-playback-node-forms.eddgraph")
    waypoint_forms = bp.read_blocks(root / "templates" / "waypoint-struct-sync-node-forms.eddgraph")
    document_forms = bp.read_blocks(root / "templates" / "document-sync-struct-node-forms.eddgraph")
    waypoint_edit_forms = bp.read_blocks(root / "templates" / "waypoint-edit-node-forms.eddgraph")
    waypoint_sync_graph = bp.read_blocks(root / "snippets" / "sync-draft-waypoints-v1.eddgraph")
    templates.update(
        {
            "float_array_item": bp.find_block(
                decoder_forms,
                r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_GetArrayItem ',
            ),
            "float_array_length": bp.find_block(waypoint_edit_forms, r'MemberName="Array_Length"'),
            "equal_int": bp.find_block(waypoint_sync_graph, r'MemberName="EqualEqual_IntInt"'),
            "branch": bp.find_block(
                waypoint_sync_graph,
                r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse ',
            ),
            "equal_string": bp.find_block(decoder_forms, r'MemberName="EqualEqual_StrStr"'),
            "quat_rotator": bp.find_block(decoder_forms, r'MemberName="Quat_Rotator"'),
            "make_vector": bp.find_block(marker_forms, r'MemberName="MakeVector"'),
            "make_transform": bp.find_block(transform_forms, r'MemberName="MakeTransform"'),
            "float_to_int": bp.find_block(linear_forms, r'MemberName="FTrunc"'),
            "make_waypoint": bp.find_block(
                waypoint_forms,
                r'K2Node_MakeStruct.*StructType="[^"]*ST_EDD_Waypoint',
            ),
            "make_segment": bp.find_block(
                document_forms,
                r'K2Node_MakeStruct.*StructType="[^"]*ST_EDD_Segment',
            ),
            "make_document": bp.find_block(
                document_forms,
                r'K2Node_MakeStruct.*StructType="[^"]*ST_EDD_FlypathDocument',
            ),
            **{
                f"json_{member}": bp.find_block(json_forms, rf'MemberName="{member}"')
                for member in (
                    "GetStringField",
                    "GetNumberField",
                    "GetNumberArrayField",
                    "GetObjectField",
                    "GetObjectArrayField",
                    "DecodeJson",
                )
            },
        }
    )
    return templates


def add_float_item(b, index: int, x: int, y: int):
    node = b.add(f"float_item_{index}_{len(b.nodes)}", "float_array_item", x, y)
    float_array_item(node)
    b.bp.set_pin_default(node, "Dimension 1", str(index))
    return node


def json_field(enc, node, name: str) -> None:
    enc.field(node, name)


def build_waypoint(bp, templates: dict[str, str], enc):
    b = enc.Builder(bp, templates, "DecodeWaypointV1")
    valid_reset = b.setter("ScratchValidV1", "bool", 0, 0)
    enc.set_default(valid_reset, "ScratchValidV1", "false")
    source_object = b.getter("ScratchNestedJsonV1", "json", 0, 520)
    source_encode = b.json("EncodeJson", 256, 520)
    source_store = b.setter("ScratchSourceJsonV1", "string", 256, 0)

    position = b.json("GetNumberArrayField", 512, 0)
    body = b.json("GetNumberArrayField", 768, 0)
    json_field(enc, position, "position")
    json_field(enc, body, "bodyRotation")
    for node in (position, body):
        bp.connect(source_object, "ScratchNestedJsonV1", node, "self")

    position_length = b.add("position_length", "float_array_length", 768, 256)
    float_array_length(position_length)
    position_arity = b.add("position_arity", "equal_int", 1024, 256)
    enc.set_default(position_arity, "B", "3")
    position_guard = b.add("position_guard", "branch", 1280, 0)
    bp.connect(position, "ReturnValue", position_length, "TargetArray")
    bp.connect(position_length, "ReturnValue", position_arity, "A")
    bp.connect(position_arity, "ReturnValue", position_guard, "Condition")

    body_length = b.add("body_length", "float_array_length", 1536, 256)
    float_array_length(body_length)
    body_arity = b.add("body_arity", "equal_int", 1792, 256)
    enc.set_default(body_arity, "B", "4")
    body_guard = b.add("body_guard", "branch", 2048, 0)
    bp.connect(body, "ReturnValue", body_length, "TargetArray")
    bp.connect(body_length, "ReturnValue", body_arity, "A")
    bp.connect(body_arity, "ReturnValue", body_guard, "Condition")

    position_items = [add_float_item(b, i, 768 + i * 192, 560) for i in range(3)]
    body_items = [add_float_item(b, i, 1344 + i * 192, 720) for i in range(4)]
    for item in position_items:
        bp.connect(position, "ReturnValue", item, "Array")
    for item in body_items:
        bp.connect(body, "ReturnValue", item, "Array")

    make_position = b.add("make_position", "make_vector", 1344, 480)
    quat_rotator = b.add("body_quat_rotator", "quat_rotator", 2112, 720)
    make_transform = b.add("make_camera_transform", "make_transform", 2368, 480)
    for item, pin in zip(position_items, ("X", "Y", "Z")):
        bp.connect(item, "Output", make_position, pin)
    for item, pin in zip(body_items, ("Q_X", "Q_Y", "Q_Z", "Q_W")):
        bp.connect(item, "Output", quat_rotator, pin)
    bp.connect(make_position, "ReturnValue", make_transform, "Location")
    bp.connect(quat_rotator, "ReturnValue", make_transform, "Rotation")

    lens = b.json("GetObjectField", 512, 960)
    json_field(enc, lens, "lens")
    bp.connect(source_object, "ScratchNestedJsonV1", lens, "self")
    lens_aperture = b.json("GetNumberField", 768, 960)
    lens_focal = b.json("GetNumberField", 1024, 960)
    lens_focus = b.json("GetNumberField", 1280, 960)
    for node, name in (
        (lens_aperture, "aperture"),
        (lens_focal, "focalLengthMm"),
        (lens_focus, "focusDistanceCm"),
    ):
        json_field(enc, node, name)
        bp.connect(lens, "ReturnValue", node, "self")

    hold = b.json("GetNumberField", 1536, 960)
    waypoint_id = b.json("GetNumberField", 1792, 960)
    json_field(enc, hold, "holdSeconds")
    json_field(enc, waypoint_id, "waypointId")
    bp.connect(source_object, "ScratchNestedJsonV1", hold, "self")
    bp.connect(source_object, "ScratchNestedJsonV1", waypoint_id, "self")
    waypoint_id_int = b.add("waypoint_id_int", "float_to_int", 2048, 960)
    bp.connect(waypoint_id, "ReturnValue", waypoint_id_int, "A")

    make_waypoint = b.add("make_waypoint", "make_waypoint", 2624, 480)
    bp.connect(waypoint_id_int, "ReturnValue", make_waypoint, enc.WP_ID)
    bp.connect(make_transform, "ReturnValue", make_waypoint, enc.WP_TRANSFORM)
    bp.connect(lens_focal, "ReturnValue", make_waypoint, enc.WP_FOCAL)
    bp.connect(lens_aperture, "ReturnValue", make_waypoint, enc.WP_APERTURE)
    bp.connect(lens_focus, "ReturnValue", make_waypoint, enc.WP_FOCUS)
    bp.connect(hold, "ReturnValue", make_waypoint, enc.WP_HOLD)
    waypoint_store = b.setter("ScratchWaypointV1", "waypoint", 2880, 0)
    bp.connect(make_waypoint, "ST_EDD_Waypoint", waypoint_store, "ScratchWaypointV1")

    encode_waypoint = b.call("EncodeWaypointV1", 3136, 0)
    canonical_source = b.getter("ScratchSourceJsonV1", "string", 3136, 400)
    encoded_object = b.getter("ScratchNestedJsonV1", "json", 3392, 560)
    canonical_encode = b.json("EncodeJson", 3648, 560)
    equal = b.add("canonical_equal", "equal_string", 3904, 480)
    valid = b.setter("ScratchValidV1", "bool", 4160, 0)
    bp.connect(source_object, "ScratchNestedJsonV1", source_encode, "self")
    bp.connect(source_encode, "ReturnValue", source_store, "ScratchSourceJsonV1")
    bp.connect(canonical_source, "ScratchSourceJsonV1", equal, "A")
    bp.connect(encoded_object, "ScratchNestedJsonV1", canonical_encode, "self")
    bp.connect(canonical_encode, "ReturnValue", equal, "B")
    bp.connect(equal, "ReturnValue", valid, "ScratchValidV1")

    bp.connect(b.entry, "then", valid_reset, "execute")
    bp.connect(valid_reset, "then", source_store, "execute")
    bp.connect(source_store, "then", position, "execute")
    bp.connect(position, "then", position_guard, "execute")
    bp.connect(position_guard, "then", body, "execute")
    bp.connect(body, "then", body_guard, "execute")
    bp.connect(body_guard, "then", waypoint_store, "execute")
    bp.connect(waypoint_store, "then", encode_waypoint, "execute")
    bp.connect(encode_waypoint, "then", valid, "execute")
    return b.nodes


def build_segment(bp, templates: dict[str, str], enc):
    b = enc.Builder(bp, templates, "DecodeSegmentV1")
    source_object = b.getter("ScratchNestedJsonV1", "json", 0, 480)
    source_encode = b.json("EncodeJson", 256, 480)
    source_store = b.setter("ScratchSourceJsonV1", "string", 256, 0)

    fields = {}
    for index, (member, name, kind) in enumerate(
        (
            (enc.SEGMENT_DURATION, "durationSeconds", "number"),
            (enc.SEGMENT_FROM, "fromWaypointId", "number"),
            (enc.SEGMENT_ID, "segmentId", "number"),
            (enc.SEGMENT_CURVE, "spatialCurveType", "string"),
            (enc.SEGMENT_TIME, "timeProfile", "string"),
            (enc.SEGMENT_TO, "toWaypointId", "number"),
        )
    ):
        node = b.json("GetNumberField" if kind == "number" else "GetStringField", 512 + index * 224, 480)
        json_field(enc, node, name)
        bp.connect(source_object, "ScratchNestedJsonV1", node, "self")
        fields[member] = node

    conversions = {}
    for index, member in enumerate((enc.SEGMENT_FROM, enc.SEGMENT_ID, enc.SEGMENT_TO)):
        conversion = b.add(f"int_{index}", "float_to_int", 736 + index * 448, 720)
        bp.connect(fields[member], "ReturnValue", conversion, "A")
        conversions[member] = conversion

    make_segment = b.add("make_segment", "make_segment", 2016, 480)
    for member in (enc.SEGMENT_DURATION, enc.SEGMENT_CURVE, enc.SEGMENT_TIME):
        bp.connect(fields[member], "ReturnValue", make_segment, member)
    for member, conversion in conversions.items():
        bp.connect(conversion, "ReturnValue", make_segment, member)
    segment_store = b.setter("ScratchSegmentV1", "segment", 2272, 0)
    bp.connect(make_segment, "ST_EDD_Segment", segment_store, "ScratchSegmentV1")

    encode_segment = b.call("EncodeSegmentV1", 2528, 0)
    canonical_source = b.getter("ScratchSourceJsonV1", "string", 2528, 400)
    encoded_object = b.getter("ScratchNestedJsonV1", "json", 2784, 560)
    canonical_encode = b.json("EncodeJson", 3040, 560)
    equal = b.add("canonical_equal", "equal_string", 3296, 480)
    valid = b.setter("ScratchValidV1", "bool", 3552, 0)
    bp.connect(source_object, "ScratchNestedJsonV1", source_encode, "self")
    bp.connect(source_encode, "ReturnValue", source_store, "ScratchSourceJsonV1")
    bp.connect(canonical_source, "ScratchSourceJsonV1", equal, "A")
    bp.connect(encoded_object, "ScratchNestedJsonV1", canonical_encode, "self")
    bp.connect(canonical_encode, "ReturnValue", equal, "B")
    bp.connect(equal, "ReturnValue", valid, "ScratchValidV1")

    chain = [source_store, segment_store, encode_segment, valid]
    bp.connect(b.entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    return b.nodes


def build_document(bp, templates: dict[str, str], enc):
    b = enc.Builder(bp, templates, "DecodeDocumentV1")
    valid_reset = b.setter("ScratchValidV1", "bool", 0, 0)
    enc.set_default(valid_reset, "ScratchValidV1", "false")
    encoded_input = b.getter("ScratchEncodedDocumentV1", "string", 0, 480)
    source_store = b.setter("ScratchSourceDocumentJsonV1", "string", 256, 0)
    bp.connect(encoded_input, "ScratchEncodedDocumentV1", source_store, "ScratchSourceDocumentJsonV1")

    root = b.json("ConstructJsonObject", 256, 480)
    root_store = b.setter("ScratchRootJsonV1", "json", 512, 0)
    decode = b.json("DecodeJson", 768, 0)
    decode_guard = b.add("decode_guard", "branch", 1024, 0)
    bp.connect(root, "ReturnValue", root_store, "ScratchRootJsonV1")
    bp.connect(root_store, "Output_Get", decode, "self")
    bp.connect(source_store, "Output_Get", decode, "JsonString")
    bp.connect(decode, "ReturnValue", decode_guard, "Condition")

    root_object = b.getter("ScratchRootJsonV1", "json", 768, 480)
    segments_array = b.getter("ScratchSegmentsV1", "segment", 1024, 480, array=True)
    clear_segments = b.array_clear("segment", 1024, 0)
    get_segments = b.json("GetObjectArrayField", 1280, 0)
    json_field(enc, get_segments, "segments")
    segments_loop = b.foreach("json", 1536, 0)
    nested_segment = b.setter("ScratchNestedJsonV1", "json", 1792, 0)
    decode_segment = b.call("DecodeSegmentV1", 2048, 0)
    segments_array_add = b.getter("ScratchSegmentsV1", "segment", 2048, 480, array=True)
    decoded_segment = b.getter("ScratchSegmentV1", "segment", 2304, 480)
    add_segment = b.array_add("segment", 2304, 0)
    bp.connect(segments_array, "ScratchSegmentsV1", clear_segments, "TargetArray")
    bp.connect(root_object, "ScratchRootJsonV1", get_segments, "self")
    bp.connect(get_segments, "ReturnValue", segments_loop, "Array")
    bp.connect(segments_loop, "Array Element", nested_segment, "ScratchNestedJsonV1")
    bp.connect(segments_array_add, "ScratchSegmentsV1", add_segment, "TargetArray")
    bp.connect(decoded_segment, "ScratchSegmentV1", add_segment, "NewItem")

    waypoints_array = b.getter("ScratchWaypointsV1", "waypoint", 2560, 480, array=True)
    clear_waypoints = b.array_clear("waypoint", 2560, 0)
    get_waypoints = b.json("GetObjectArrayField", 2816, 0)
    json_field(enc, get_waypoints, "waypoints")
    waypoints_loop = b.foreach("json", 3072, 0)
    nested_waypoint = b.setter("ScratchNestedJsonV1", "json", 3328, 0)
    decode_waypoint = b.call("DecodeWaypointV1", 3584, 0)
    waypoints_array_add = b.getter("ScratchWaypointsV1", "waypoint", 3584, 480, array=True)
    decoded_waypoint = b.getter("ScratchWaypointV1", "waypoint", 3840, 480)
    add_waypoint = b.array_add("waypoint", 3840, 0)
    bp.connect(waypoints_array, "ScratchWaypointsV1", clear_waypoints, "TargetArray")
    bp.connect(root_object, "ScratchRootJsonV1", get_waypoints, "self")
    bp.connect(get_waypoints, "ReturnValue", waypoints_loop, "Array")
    bp.connect(waypoints_loop, "Array Element", nested_waypoint, "ScratchNestedJsonV1")
    bp.connect(waypoints_array_add, "ScratchWaypointsV1", add_waypoint, "TargetArray")
    bp.connect(decoded_waypoint, "ScratchWaypointV1", add_waypoint, "NewItem")

    scalar_specs = (
        (enc.DOC_SCHEMA, "schemaVersion", "number"),
        (enc.DOC_ENGINE, "trajectoryEngineVersion", "number"),
        (enc.DOC_REVISION, "revisionNumber", "number"),
        (enc.DOC_REGION, "regionId", "string"),
        (enc.DOC_DURATION, "durationSeconds", "number"),
        (enc.DOC_PROFILE, "defaultFlightProfile", "string"),
        (enc.DOC_HASH, "contentHash", "string"),
    )
    scalar_nodes = {}
    for index, (member, name, kind) in enumerate(scalar_specs):
        node = b.json("GetNumberField" if kind == "number" else "GetStringField", 4096 + index * 224, 640)
        json_field(enc, node, name)
        bp.connect(root_object, "ScratchRootJsonV1", node, "self")
        scalar_nodes[member] = node
    integer_nodes = {}
    for index, member in enumerate((enc.DOC_SCHEMA, enc.DOC_ENGINE, enc.DOC_REVISION)):
        conversion = b.add(f"doc_int_{index}", "float_to_int", 4096 + index * 448, 880)
        bp.connect(scalar_nodes[member], "ReturnValue", conversion, "A")
        integer_nodes[member] = conversion

    make_document = b.add("make_document", "make_document", 5664, 480)
    for member in (enc.DOC_REGION, enc.DOC_DURATION, enc.DOC_PROFILE, enc.DOC_HASH):
        bp.connect(scalar_nodes[member], "ReturnValue", make_document, member)
    for member, conversion in integer_nodes.items():
        bp.connect(conversion, "ReturnValue", make_document, member)
    final_waypoints = b.getter("ScratchWaypointsV1", "waypoint", 5408, 800, array=True)
    final_segments = b.getter("ScratchSegmentsV1", "segment", 5408, 960, array=True)
    bp.connect(final_waypoints, "ScratchWaypointsV1", make_document, enc.DOC_WAYPOINTS)
    bp.connect(final_segments, "ScratchSegmentsV1", make_document, enc.DOC_SEGMENTS)
    document_store = b.setter("ScratchDocumentV1", "document", 5920, 0)
    bp.connect(make_document, "ST_EDD_FlypathDocument", document_store, "ScratchDocumentV1")

    encode_document = b.call("EncodeDocumentV1", 6176, 0)
    source_document = b.getter("ScratchSourceDocumentJsonV1", "string", 6176, 480)
    canonical_document = b.getter("ScratchEncodedDocumentV1", "string", 6432, 640)
    equal = b.add("canonical_document_equal", "equal_string", 6688, 480)
    valid = b.setter("ScratchValidV1", "bool", 6944, 0)
    bp.connect(source_document, "ScratchSourceDocumentJsonV1", equal, "A")
    bp.connect(canonical_document, "ScratchEncodedDocumentV1", equal, "B")
    bp.connect(equal, "ReturnValue", valid, "ScratchValidV1")

    bp.connect(b.entry, "then", valid_reset, "execute")
    bp.connect(valid_reset, "then", source_store, "execute")
    chain = [source_store, root_store, decode]
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute" if right is not segments_loop else "Exec")
    bp.connect(decode, "then", decode_guard, "execute")
    bp.connect(decode_guard, "then", clear_segments, "execute")
    bp.connect(clear_segments, "then", get_segments, "execute")
    bp.connect(get_segments, "then", segments_loop, "Exec")
    bp.connect(segments_loop, "LoopBody", nested_segment, "execute")
    bp.connect(nested_segment, "then", decode_segment, "execute")
    bp.connect(decode_segment, "then", add_segment, "execute")
    bp.connect(segments_loop, "Completed", clear_waypoints, "execute")
    bp.connect(clear_waypoints, "then", get_waypoints, "execute")
    bp.connect(get_waypoints, "then", waypoints_loop, "Exec")
    bp.connect(waypoints_loop, "LoopBody", nested_waypoint, "execute")
    bp.connect(nested_waypoint, "then", decode_waypoint, "execute")
    bp.connect(decode_waypoint, "then", add_waypoint, "execute")
    bp.connect(waypoints_loop, "Completed", document_store, "execute")
    bp.connect(document_store, "then", encode_document, "execute")
    bp.connect(encode_document, "then", valid, "execute")
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
        "decode-waypoint-v1.eddgraph": build_waypoint(bp, templates, enc),
        "decode-segment-v1.eddgraph": build_segment(bp, templates, enc),
        "decode-document-v1.eddgraph": build_document(bp, templates, enc),
    }
    for name, nodes in graphs.items():
        enc.write(nodes, args.output_dir / name, paste=False)
        if args.paste_dir:
            enc.write(nodes, args.paste_dir / name.replace(".eddgraph", "-paste.eddgraph"), paste=True)


if __name__ == "__main__":
    main()
