"""Build deterministic staged JSON encoders for Flypath documents.

The generated helpers deliberately use repository member variables as their
transaction boundary because Enhanced Python cannot author Blueprint function
parameters reliably.  `EncodeWaypointV1` and `EncodeSegmentV1` consume their
typed scratch values and publish one `ScratchNestedJsonV1`; `EncodeDocumentV1`
orchestrates the helpers and publishes `ScratchEncodedDocumentV1`.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository"
)
PLAYFAB_JSON = "/Script/CoreUObject.Class'/Script/PlayFab.PlayFabJsonObject'"
DOCUMENT_STRUCT = (
    "/Script/CoreUObject.UserDefinedStruct'"
    "/Game/Mods/ExileDroneDirector/Data/Structs/"
    "ST_EDD_FlypathDocument.ST_EDD_FlypathDocument'"
)
WAYPOINT_STRUCT = (
    "/Script/CoreUObject.UserDefinedStruct'"
    "/Game/Mods/ExileDroneDirector/Data/Structs/"
    "ST_EDD_Waypoint.ST_EDD_Waypoint'"
)
SEGMENT_STRUCT = (
    "/Script/CoreUObject.UserDefinedStruct'"
    "/Game/Mods/ExileDroneDirector/Data/Structs/"
    "ST_EDD_Segment.ST_EDD_Segment'"
)
REPOSITORY_GENERATED_CLASS = (
    "/Script/Engine.BlueprintGeneratedClass'"
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C'"
)

WP_ID = "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE"
WP_TRANSFORM = "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9"
WP_FOCAL = "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B"
WP_APERTURE = "Aperture_10_949C579344F8DFA750F1948051A417B2"
WP_FOCUS = "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F"
WP_HOLD = "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB"

SEGMENT_ID = "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0"
SEGMENT_FROM = "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91"
SEGMENT_TO = "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B"
SEGMENT_DURATION = "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A"
SEGMENT_CURVE = "SpatialCurveType_15_39D20A5A4CD2FB464BAA64839CE4012E"
SEGMENT_TIME = "TimeProfile_16_3195F0C3470E1AECB34316A7BFBD2FBA"

DOC_SCHEMA = "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"
DOC_ENGINE = "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D"
DOC_REVISION = "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"
DOC_REGION = "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"
DOC_DURATION = "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"
DOC_PROFILE = "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161"
DOC_WAYPOINTS = "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"
DOC_SEGMENTS = "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"
DOC_HASH = "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_repository_encoder_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def set_function_entry(node, name: str) -> None:
    node.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{name}")',
        node.text,
        count=1,
    )


def type_parts(kind: str) -> tuple[str, str, str]:
    if kind == "bool":
        return "bool", "", "None"
    if kind == "int":
        return "int", "", "None"
    if kind == "string":
        return "string", "", "None"
    if kind == "json":
        return "object", "", f'"{PLAYFAB_JSON}"'
    if kind == "document":
        return "struct", "", f'"{DOCUMENT_STRUCT}"'
    if kind == "waypoint":
        return "struct", "", f'"{WAYPOINT_STRUCT}"'
    if kind == "segment":
        return "struct", "", f'"{SEGMENT_STRUCT}"'
    raise RuntimeError(f"Unsupported pin kind: {kind}")


def set_pin_type(node, pin_name: str, kind: str, *, array: bool = False) -> None:
    category, subcategory, obj = type_parts(kind)

    def mutate(line: str) -> str:
        line = re.sub(r'PinType\.PinCategory="[^"]+"', f'PinType.PinCategory="{category}"', line, count=1)
        line = re.sub(r'PinType\.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, count=1)
        line = re.sub(
            r'PinType\.PinSubCategoryObject=(?:None|"[^"]+")',
            f"PinType.PinSubCategoryObject={obj}",
            line,
            count=1,
        )
        line = re.sub(
            r'PinType\.ContainerType=(?:None|Array)',
            f'PinType.ContainerType={"Array" if array else "None"}',
            line,
            count=1,
        )
        if category in {"object", "struct"}:
            line = re.sub(r',DefaultValue="[^"]*"', "", line)
            line = re.sub(r',AutogeneratedDefaultValue="[^"]*"', "", line)
        return line

    node.mutate_pin(pin_name, mutate)


def rename_pin(node, old_name: str, new_name: str) -> None:
    node.text = node.text.replace(f'PinName="{old_name}"', f'PinName="{new_name}"')
    node.pins[new_name] = node.pins.pop(old_name)


def retarget_variable(node, new_name: str, kind: str, *, array: bool = False) -> None:
    match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"{node.key} has no Blueprint member-variable reference")
    old_name = match.group(1)
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{re.escape(old_name)}"[^)]*\)',
        f'VariableReference=(MemberName="{new_name}",bSelfContext=True)',
        node.text,
        count=1,
    )
    rename_pin(node, old_name, new_name)
    set_pin_type(node, new_name, kind, array=array)
    if "Output_Get" in node.pins:
        set_pin_type(node, "Output_Get", kind, array=array)

    def retarget_self(line: str) -> str:
        return re.sub(
            r'PinType\.PinSubCategoryObject="/Script/Engine\.BlueprintGeneratedClass\'[^\']+\'"',
            f'PinType.PinSubCategoryObject="{REPOSITORY_GENERATED_CLASS}"',
            line,
            count=1,
        )

    node.mutate_pin("self", retarget_self)


def retarget_self_call(node, name: str) -> None:
    node.text = re.sub(
        r'FunctionReference=\([^)]*\)',
        f'FunctionReference=(MemberName="{name}",bSelfContext=True)',
        node.text,
        count=1,
    )


def set_default(node, pin_name: str, value: str) -> None:
    def mutate(line: str) -> str:
        if "DefaultValue=" in line:
            return re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, count=1)
        return line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1)

    node.mutate_pin(pin_name, mutate)


def make_array_template(native: str, count: int) -> str:
    """Resize an editor-authored float Make Array without inventing pin metadata."""
    if count not in (3, 4):
        raise ValueError(f"Only canonical vector/quaternion arrays are supported: {count}")
    result = re.sub(r"NumInputs=\d+", f"NumInputs={count}", native, count=1)
    if count == 3:
        result = "\n".join(
            line for line in result.splitlines() if 'PinName="[3]"' not in line
        )
    return result


class Builder:
    def __init__(self, bp, templates: dict[str, str], graph_name: str):
        self.bp = bp
        self.templates = templates
        self.nodes = []
        self.serial: dict[str, int] = {}
        bp.TARGET_ASSET = TARGET_ASSET
        bp.TARGET_GRAPH = graph_name
        self.entry = self.add("entry", "entry", 0, 0)
        set_function_entry(self.entry, graph_name)

    def next_name(self, class_name: str) -> str:
        index = self.serial.get(class_name, 0)
        self.serial[class_name] = index + 1
        return f"{class_name}_{index}"

    def add(self, key: str, template: str, x: int, y: int):
        block = self.templates[template]
        match = self.bp.BLOCK_RE.match(block)
        if match is None:
            raise RuntimeError(f"Invalid template {template}")
        class_name = match.group("class").rsplit(".", 1)[-1]
        name = "K2Node_FunctionEntry_0" if key == "entry" else self.next_name(class_name)
        node = self.bp.Node.clone(key, block, name, x, y)
        self.nodes.append(node)
        return node

    def getter(self, name: str, kind: str, x: int, y: int, *, array: bool = False):
        node = self.add(f"get_{name}_{len(self.nodes)}", "variable_get", x, y)
        retarget_variable(node, name, kind, array=array)
        return node

    def setter(self, name: str, kind: str, x: int, y: int, *, array: bool = False):
        node = self.add(f"set_{name}_{len(self.nodes)}", "variable_set", x, y)
        retarget_variable(node, name, kind, array=array)
        return node

    def json(self, member: str, x: int, y: int):
        return self.add(f"json_{member}_{len(self.nodes)}", f"json_{member}", x, y)

    def call(self, member: str, x: int, y: int):
        node = self.add(f"call_{member}_{len(self.nodes)}", "self_call", x, y)
        retarget_self_call(node, member)
        return node

    def array_clear(self, kind: str, x: int, y: int):
        node = self.add(f"clear_{len(self.nodes)}", "array_clear", x, y)
        set_pin_type(node, "TargetArray", kind, array=True)
        return node

    def array_add(self, kind: str, x: int, y: int):
        node = self.add(f"add_{len(self.nodes)}", "array_add", x, y)
        set_pin_type(node, "TargetArray", kind, array=True)
        set_pin_type(node, "NewItem", kind)
        return node

    def foreach(self, kind: str, x: int, y: int):
        node = self.add(f"foreach_{len(self.nodes)}", "foreach", x, y)
        set_pin_type(node, "Array", kind, array=True)
        set_pin_type(node, "Array Element", kind)
        return node

    def make_number_array(self, count: int, x: int, y: int):
        key = f"make_number_array_{count}_{len(self.nodes)}"
        block = make_array_template(self.templates["make_number_array"], count)
        name = self.next_name("K2Node_MakeArray")
        node = self.bp.Node.clone(key, block, name, x, y)
        self.nodes.append(node)
        return node


def load_templates(project_root: Path, bp) -> dict[str, str]:
    root = project_root / "tools" / "blueprint"
    json_forms = bp.read_blocks(root / "templates" / "repository-json-node-forms.eddgraph")
    transform_forms = bp.read_blocks(root / "templates" / "repository-codec-transform-node-forms.eddgraph")
    math_forms = bp.read_blocks(root / "templates" / "repository-codec-math-node-forms.eddgraph")
    vector_forms = bp.read_blocks(root / "templates" / "repository-codec-vector-node-forms.eddgraph")
    array_forms = bp.read_blocks(root / "templates" / "repository-codec-array-node-forms.eddgraph")
    marker_forms = bp.read_blocks(root / "templates" / "path-preview-marker-node-forms.eddgraph")
    document_forms = bp.read_blocks(root / "templates" / "document-sync-struct-node-forms.eddgraph")
    capture_forms = bp.read_blocks(root / "templates" / "waypoint-capture-node-forms.eddgraph")
    start = bp.read_blocks(root / "snippets" / "start-linear-playback.eddgraph")
    playback = bp.read_blocks(root / "snippets" / "update-linear-playback.eddgraph")
    sync = bp.read_blocks(root / "snippets" / "sync-draft-waypoints-v1.eddgraph")
    capture = bp.read_blocks(root / "snippets" / "capture-current-waypoint-preview.eddgraph")
    repository_live = bp.read_blocks(root / "live-snippets" / "reset-repository-result-v1.eddgraph")
    return {
        "entry": bp.find_block(capture_forms, r"K2Node_FunctionEntry"),
        "variable_get": bp.find_block(
            repository_live,
            r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_VariableGet ',
        ),
        "variable_set": bp.find_block(
            repository_live,
            r'^Begin Object Class=/Script/BlueprintGraph\.K2Node_VariableSet ',
        ),
        "array_clear": bp.find_block(sync, r'MemberName="Array_Clear"'),
        "array_add": bp.find_block(capture_forms, r'MemberName="Array_Add"'),
        "foreach": bp.find_block(marker_forms, r"K2Node_MacroInstance.*StandardMacros:ForEachLoop"),
        "self_call": bp.find_block(capture, r'MemberName="SyncDraftDocumentV1"'),
        "break_waypoint": bp.find_block(marker_forms, r'K2Node_BreakStruct.*StructType="[^"]*ST_EDD_Waypoint'),
        "break_segment": bp.find_block(document_forms, r'K2Node_BreakStruct.*StructType="[^"]*ST_EDD_Segment'),
        "break_document": bp.find_block(document_forms, r'K2Node_BreakStruct.*StructType="[^"]*ST_EDD_FlypathDocument'),
        "break_transform": bp.find_block(transform_forms, r'MemberName="BreakTransform"'),
        "break_vector": bp.find_block(vector_forms, r'MemberName="BreakVector"'),
        "make_number_array": bp.find_block(array_forms, r"K2Node_MakeArray"),
        "rotator_to_quat": bp.find_block(math_forms, r'MemberName="Conv_RotatorToQuaternion"'),
        **{
            f"json_{member}": bp.find_block(json_forms, rf'MemberName="{member}"')
            for member in (
                "ConstructJsonObject",
                "SetStringField",
                "SetNumberField",
                "SetNumberArrayField",
                "SetObjectField",
                "SetObjectArrayField",
                "EncodeJson",
            )
        },
    }


def field(node, name: str) -> None:
    set_default(node, "FieldName", name)


def build_waypoint(bp, templates: dict[str, str]):
    b = Builder(bp, templates, "EncodeWaypointV1")
    waypoint = b.getter("ScratchWaypointV1", "waypoint", 0, 400)
    split = b.add("break_waypoint", "break_waypoint", 256, 400)
    break_transform = b.add("break_transform", "break_transform", 512, 480)
    break_vector = b.add("break_vector", "break_vector", 768, 560)
    quat = b.add("body_quaternion", "rotator_to_quat", 768, 720)
    body_array = b.make_number_array(4, 1024, 720)
    gimbal_array = b.make_number_array(4, 1024, 920)
    position_array = b.make_number_array(3, 1024, 560)
    set_default(gimbal_array, "[3]", "1.0")

    root = b.json("ConstructJsonObject", 0, 160)
    store_root = b.setter("ScratchNestedJsonV1", "json", 256, 0)
    lens = b.json("ConstructJsonObject", 1792, 720)

    annotation = b.json("SetStringField", 512, 0)
    body = b.json("SetNumberArrayField", 768, 0)
    corner = b.json("SetStringField", 1024, 0)
    gimbal = b.json("SetNumberArrayField", 1280, 0)
    hold = b.json("SetNumberField", 1536, 0)
    lens_aperture = b.json("SetNumberField", 1792, 0)
    lens_focal = b.json("SetNumberField", 2048, 0)
    lens_focus = b.json("SetNumberField", 2304, 0)
    lens_object = b.json("SetObjectField", 2560, 0)
    position = b.json("SetNumberArrayField", 2816, 0)
    waypoint_id = b.json("SetNumberField", 3072, 0)

    for node, name in (
        (annotation, "annotation"),
        (body, "bodyRotation"),
        (corner, "cornerMode"),
        (gimbal, "gimbalRotation"),
        (hold, "holdSeconds"),
        (lens_aperture, "aperture"),
        (lens_focal, "focalLengthMm"),
        (lens_focus, "focusDistanceCm"),
        (lens_object, "lens"),
        (position, "position"),
        (waypoint_id, "waypointId"),
    ):
        field(node, name)
    set_default(annotation, "StringValue", "")
    set_default(corner, "StringValue", "glide")

    bp.connect(waypoint, "ScratchWaypointV1", split, "ST_EDD_Waypoint")
    bp.connect(split, WP_TRANSFORM, break_transform, "InTransform")
    bp.connect(break_transform, "Location", break_vector, "InVec")
    bp.connect(break_transform, "Rotation", quat, "InRot")
    for output, index in zip(("X", "Y", "Z"), range(3)):
        bp.connect(break_vector, output, position_array, f"[{index}]")
    for output, index in zip(
        ("ReturnValue_X", "ReturnValue_Y", "ReturnValue_Z", "ReturnValue_W"),
        range(4),
    ):
        bp.connect(quat, output, body_array, f"[{index}]")

    bp.connect(root, "ReturnValue", store_root, "ScratchNestedJsonV1")
    for node in (annotation, body, corner, gimbal, hold, lens_object, position, waypoint_id):
        bp.connect(store_root, "Output_Get", node, "self")
    for node in (lens_aperture, lens_focal, lens_focus):
        bp.connect(lens, "ReturnValue", node, "self")
    bp.connect(lens, "ReturnValue", lens_object, "JsonObject")

    bp.connect(body_array, "Array", body, "NumberArray")
    bp.connect(gimbal_array, "Array", gimbal, "NumberArray")
    bp.connect(position_array, "Array", position, "NumberArray")
    bp.connect(split, WP_HOLD, hold, "Number")
    bp.connect(split, WP_APERTURE, lens_aperture, "Number")
    bp.connect(split, WP_FOCAL, lens_focal, "Number")
    bp.connect(split, WP_FOCUS, lens_focus, "Number")
    bp.connect(split, WP_ID, waypoint_id, "Number")

    chain = [store_root, annotation, body, corner, gimbal, hold, lens_aperture, lens_focal, lens_focus, lens_object, position, waypoint_id]
    bp.connect(b.entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    return b.nodes


def build_segment(bp, templates: dict[str, str]):
    b = Builder(bp, templates, "EncodeSegmentV1")
    segment = b.getter("ScratchSegmentV1", "segment", 0, 400)
    split = b.add("break_segment", "break_segment", 256, 400)
    root = b.json("ConstructJsonObject", 0, 160)
    store_root = b.setter("ScratchNestedJsonV1", "json", 256, 0)
    duration = b.json("SetNumberField", 512, 0)
    from_id = b.json("SetNumberField", 768, 0)
    segment_id = b.json("SetNumberField", 1024, 0)
    curve = b.json("SetStringField", 1280, 0)
    time = b.json("SetStringField", 1536, 0)
    to_id = b.json("SetNumberField", 1792, 0)
    for node, name in (
        (duration, "durationSeconds"),
        (from_id, "fromWaypointId"),
        (segment_id, "segmentId"),
        (curve, "spatialCurveType"),
        (time, "timeProfile"),
        (to_id, "toWaypointId"),
    ):
        field(node, name)
        bp.connect(store_root, "Output_Get", node, "self")
    bp.connect(segment, "ScratchSegmentV1", split, "ST_EDD_Segment")
    for source_pin, node, target_pin in (
        (SEGMENT_DURATION, duration, "Number"),
        (SEGMENT_FROM, from_id, "Number"),
        (SEGMENT_ID, segment_id, "Number"),
        (SEGMENT_CURVE, curve, "StringValue"),
        (SEGMENT_TIME, time, "StringValue"),
        (SEGMENT_TO, to_id, "Number"),
    ):
        bp.connect(split, source_pin, node, target_pin)
    bp.connect(root, "ReturnValue", store_root, "ScratchNestedJsonV1")
    chain = [store_root, duration, from_id, segment_id, curve, time, to_id]
    bp.connect(b.entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    return b.nodes


def build_document(bp, templates: dict[str, str]):
    b = Builder(bp, templates, "EncodeDocumentV1")
    document = b.getter("ScratchDocumentV1", "document", 0, 560)
    split = b.add("break_document", "break_document", 256, 560)
    root = b.json("ConstructJsonObject", 0, 240)
    store_root = b.setter("ScratchRootJsonV1", "json", 256, 0)

    content_hash = b.json("SetStringField", 512, 0)
    profile = b.json("SetStringField", 768, 0)
    duration = b.json("SetNumberField", 1024, 0)
    region = b.json("SetStringField", 1280, 0)
    revision = b.json("SetNumberField", 1536, 0)
    schema = b.json("SetNumberField", 1792, 0)
    for node, name in (
        (content_hash, "contentHash"),
        (profile, "defaultFlightProfile"),
        (duration, "durationSeconds"),
        (region, "regionId"),
        (revision, "revisionNumber"),
        (schema, "schemaVersion"),
    ):
        field(node, name)
        bp.connect(store_root, "Output_Get", node, "self")

    objects_a = b.getter("ScratchJsonObjectsV1", "json", 1792, 360, array=True)
    clear_segments = b.array_clear("json", 2048, 0)
    segments = b.foreach("segment", 2304, 0)
    set_segment = b.setter("ScratchSegmentV1", "segment", 2560, 0)
    encode_segment = b.call("EncodeSegmentV1", 2816, 0)
    objects_b = b.getter("ScratchJsonObjectsV1", "json", 2816, 360, array=True)
    nested_a = b.getter("ScratchNestedJsonV1", "json", 3072, 360)
    add_segment = b.array_add("json", 3072, 0)
    objects_c = b.getter("ScratchJsonObjectsV1", "json", 3328, 360, array=True)
    set_segments = b.json("SetObjectArrayField", 3328, 0)
    field(set_segments, "segments")
    bp.connect(store_root, "Output_Get", set_segments, "self")

    engine = b.json("SetNumberField", 3584, 0)
    field(engine, "trajectoryEngineVersion")
    bp.connect(store_root, "Output_Get", engine, "self")
    objects_d = b.getter("ScratchJsonObjectsV1", "json", 3584, 360, array=True)
    clear_waypoints = b.array_clear("json", 3840, 0)
    waypoints = b.foreach("waypoint", 4096, 0)
    set_waypoint = b.setter("ScratchWaypointV1", "waypoint", 4352, 0)
    encode_waypoint = b.call("EncodeWaypointV1", 4608, 0)
    objects_e = b.getter("ScratchJsonObjectsV1", "json", 4608, 360, array=True)
    nested_b = b.getter("ScratchNestedJsonV1", "json", 4864, 360)
    add_waypoint = b.array_add("json", 4864, 0)
    objects_f = b.getter("ScratchJsonObjectsV1", "json", 5120, 360, array=True)
    set_waypoints = b.json("SetObjectArrayField", 5120, 0)
    field(set_waypoints, "waypoints")
    bp.connect(store_root, "Output_Get", set_waypoints, "self")
    encode_json = b.json("EncodeJson", 5376, 360)
    encoded = b.setter("ScratchEncodedDocumentV1", "string", 5632, 0)

    bp.connect(document, "ScratchDocumentV1", split, "ST_EDD_FlypathDocument")
    for source_pin, node, target_pin in (
        (DOC_HASH, content_hash, "StringValue"),
        (DOC_PROFILE, profile, "StringValue"),
        (DOC_DURATION, duration, "Number"),
        (DOC_REGION, region, "StringValue"),
        (DOC_REVISION, revision, "Number"),
        (DOC_SCHEMA, schema, "Number"),
        (DOC_ENGINE, engine, "Number"),
    ):
        bp.connect(split, source_pin, node, target_pin)
    bp.connect(root, "ReturnValue", store_root, "ScratchRootJsonV1")

    bp.connect(objects_a, "ScratchJsonObjectsV1", clear_segments, "TargetArray")
    bp.connect(split, DOC_SEGMENTS, segments, "Array")
    bp.connect(segments, "Array Element", set_segment, "ScratchSegmentV1")
    bp.connect(objects_b, "ScratchJsonObjectsV1", add_segment, "TargetArray")
    bp.connect(nested_a, "ScratchNestedJsonV1", add_segment, "NewItem")
    bp.connect(objects_c, "ScratchJsonObjectsV1", set_segments, "ObjectArray")

    bp.connect(objects_d, "ScratchJsonObjectsV1", clear_waypoints, "TargetArray")
    bp.connect(split, DOC_WAYPOINTS, waypoints, "Array")
    bp.connect(waypoints, "Array Element", set_waypoint, "ScratchWaypointV1")
    bp.connect(objects_e, "ScratchJsonObjectsV1", add_waypoint, "TargetArray")
    bp.connect(nested_b, "ScratchNestedJsonV1", add_waypoint, "NewItem")
    bp.connect(objects_f, "ScratchJsonObjectsV1", set_waypoints, "ObjectArray")
    bp.connect(store_root, "Output_Get", encode_json, "self")
    bp.connect(encode_json, "ReturnValue", encoded, "ScratchEncodedDocumentV1")

    scalar_chain = [store_root, content_hash, profile, duration, region, revision, schema, clear_segments]
    bp.connect(b.entry, "then", scalar_chain[0], "execute")
    for left, right in zip(scalar_chain, scalar_chain[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(clear_segments, "then", segments, "Exec")
    bp.connect(segments, "LoopBody", set_segment, "execute")
    bp.connect(set_segment, "then", encode_segment, "execute")
    bp.connect(encode_segment, "then", add_segment, "execute")
    bp.connect(segments, "Completed", set_segments, "execute")
    bp.connect(set_segments, "then", engine, "execute")
    bp.connect(engine, "then", clear_waypoints, "execute")
    bp.connect(clear_waypoints, "then", waypoints, "Exec")
    bp.connect(waypoints, "LoopBody", set_waypoint, "execute")
    bp.connect(set_waypoint, "then", encode_waypoint, "execute")
    bp.connect(encode_waypoint, "then", add_waypoint, "execute")
    bp.connect(waypoints, "Completed", set_waypoints, "execute")
    bp.connect(set_waypoints, "then", encoded, "execute")
    return b.nodes


def write(nodes, output: Path, *, paste: bool) -> None:
    entry = nodes[0]
    blocks = []
    for node in nodes:
        if paste and node is entry:
            continue
        # Enhanced 5.6.1 can reconstruct the split Quat node by itself, but
        # asserts in K2Node.cpp when that node is part of the large encoder
        # clipboard batch even with every Quat link removed. Install it as a
        # second isolated paste, then wire its five deferred pins in-editor.
        if paste and 'MemberName="Conv_RotatorToQuaternion"' in node.text:
            continue
        text = node.text
        if paste:
            text = re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", text)
            # Enhanced 5.6.1 crashes while reconstructing a pasted split Quat
            # output that is already linked to a Make Array. Both nodes and all
            # other bridges paste safely. Install these four links after paste.
            if node.name == "K2Node_MakeArray_0":
                text = re.sub(
                    r',LinkedTo=\(K2Node_CallFunction_2 [0-9A-F]{32},\)',
                    "",
                    text,
                )
            if 'MemberName="BreakTransform"' in text:
                text = re.sub(
                    r',LinkedTo=\(K2Node_CallFunction_2 [0-9A-F]{32},\)',
                    "",
                    text,
                )
        blocks.append(text)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(blocks) + "\n", encoding="utf-8")


def write_isolated_probe(nodes, output: Path, include) -> None:
    """Write unlinked body nodes for editor-paste reconstruction isolation."""
    blocks = []
    for node in nodes[1:]:
        if not include(node.text):
            continue
        blocks.append(re.sub(r",LinkedTo=\([^)]*\)", "", node.text))
    if not blocks:
        raise RuntimeError(f"Paste probe selected no nodes: {output.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(blocks) + "\n", encoding="utf-8")


def write_unsplit_quaternion_probe(nodes, output: Path) -> None:
    """Collapse the harvested split Quat return to its native unsplit form."""
    matches = [node for node in nodes if 'MemberName="Conv_RotatorToQuaternion"' in node.text]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Rotator-to-Quaternion node for {output.name}")
    lines = []
    for line in matches[0].text.splitlines():
        if 'PinName="ReturnValue_' in line:
            continue
        if 'PinName="ReturnValue",' in line:
            line = re.sub(r"SubPins=\([^)]*\),", "", line)
            line = line.replace("bHidden=True", "bHidden=False")
        line = re.sub(r",LinkedTo=\([^)]*\)", "", line)
        lines.append(line)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_linked_probe(nodes, output: Path, include) -> None:
    """Write a linked subset while pruning references to excluded nodes."""
    selected = [node for node in nodes[1:] if include(node.text)]
    selected_names = {node.name for node in selected}
    if not selected:
        raise RuntimeError(f"Linked paste probe selected no nodes: {output.name}")

    def prune(line: str) -> str:
        match = re.search(r",LinkedTo=\((?P<links>[^)]*)\)", line)
        if match is None:
            return line
        links = re.findall(r"([A-Za-z0-9_]+) ([0-9A-F]{32}),", match.group("links"))
        kept = [(name, pin) for name, pin in links if name in selected_names]
        replacement = "" if not kept else ",LinkedTo=(" + "".join(
            f"{name} {pin}," for name, pin in kept
        ) + ")"
        return line[: match.start()] + replacement + line[match.end() :]

    blocks = ["\n".join(prune(line) for line in node.text.splitlines()) for node in selected]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    parser.add_argument("--probe-dir", type=Path)
    args = parser.parse_args()
    bp = load_helpers(args.project_root)
    templates = load_templates(args.project_root, bp)
    graphs = {
        "encode-waypoint-v1.eddgraph": build_waypoint(bp, templates),
        "encode-segment-v1.eddgraph": build_segment(bp, templates),
        "encode-document-v1.eddgraph": build_document(bp, templates),
    }
    for filename, nodes in graphs.items():
        write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            write(nodes, args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"), paste=True)
    if args.probe_dir:
        waypoint = graphs["encode-waypoint-v1.eddgraph"]
        probes = {
            "waypoint-arrays.eddgraph": lambda text: text.startswith(
                "Begin Object Class=/Script/BlueprintGraph.K2Node_MakeArray "
            ),
            "waypoint-variables.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_VariableGet ")
                or text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_VariableSet ")
            ),
            "waypoint-structs.eddgraph": lambda text: text.startswith(
                "Begin Object Class=/Script/BlueprintGraph.K2Node_BreakStruct "
            ),
            "waypoint-math.eddgraph": lambda text: any(
                f'MemberName="{member}"' in text
                for member in ("BreakTransform", "BreakVector", "Conv_RotatorToQuaternion")
            ),
            "waypoint-break-transform.eddgraph": lambda text: (
                'MemberName="BreakTransform"' in text
            ),
            "waypoint-break-vector.eddgraph": lambda text: (
                'MemberName="BreakVector"' in text
            ),
            "waypoint-rotator-quaternion.eddgraph": lambda text: (
                'MemberName="Conv_RotatorToQuaternion"' in text
            ),
            "waypoint-json.eddgraph": lambda text: (
                "K2Node_CallFunction" in text
                and "/Script/PlayFab" in text
            ),
        }
        for filename, include in probes.items():
            write_isolated_probe(waypoint, args.probe_dir / filename, include)
        write_unsplit_quaternion_probe(
            waypoint,
            args.probe_dir / "waypoint-rotator-quaternion-unsplit.eddgraph",
        )
        linked_probes = {
            "waypoint-position-bridge.eddgraph": lambda text: (
                'MemberName="BreakVector"' in text
                or text.startswith(
                    'Begin Object Class=/Script/BlueprintGraph.K2Node_MakeArray Name="K2Node_MakeArray_2"'
                )
            ),
            "waypoint-body-bridge.eddgraph": lambda text: (
                'MemberName="Conv_RotatorToQuaternion"' in text
                or text.startswith(
                    'Begin Object Class=/Script/BlueprintGraph.K2Node_MakeArray Name="K2Node_MakeArray_0"'
                )
            ),
            "waypoint-data-chain.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_VariableGet ")
                or text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_BreakStruct ")
                or any(
                    f'MemberName="{member}"' in text
                    for member in ("BreakTransform", "BreakVector", "Conv_RotatorToQuaternion")
                )
                or text.startswith(
                    'Begin Object Class=/Script/BlueprintGraph.K2Node_MakeArray Name="K2Node_MakeArray_2"'
                )
            ),
            "waypoint-variable-struct-bridge.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_VariableGet ")
                or text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_BreakStruct ")
            ),
            "waypoint-struct-transform-bridge.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_BreakStruct ")
                or 'MemberName="BreakTransform"' in text
            ),
            "waypoint-transform-vector-bridge.eddgraph": lambda text: any(
                f'MemberName="{member}"' in text
                for member in ("BreakTransform", "BreakVector")
            ),
            "waypoint-transform-quat-bridge.eddgraph": lambda text: any(
                f'MemberName="{member}"' in text
                for member in ("BreakTransform", "Conv_RotatorToQuaternion")
            ),
            "waypoint-array-json-bridges.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_MakeArray ")
                or 'MemberName="SetNumberArrayField"' in text
            ),
            "waypoint-root-json.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_VariableSet ")
                or (
                    text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_CallFunction ")
                    and "/Script/PlayFab" in text
                )
            ),
            "waypoint-struct-json-bridges.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_BreakStruct ")
                or (
                    text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_CallFunction ")
                    and "/Script/PlayFab" in text
                )
            ),
            "waypoint-data-json-without-quat.eddgraph": lambda text: (
                text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_BreakStruct ")
                or any(
                    f'MemberName="{member}"' in text
                    for member in ("BreakTransform", "BreakVector")
                )
                or text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_MakeArray ")
                or (
                    text.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_CallFunction ")
                    and "/Script/PlayFab" in text
                )
            ),
        }
        for filename, include in linked_probes.items():
            write_linked_probe(waypoint, args.probe_dir / filename, include)


if __name__ == "__main__":
    main()
