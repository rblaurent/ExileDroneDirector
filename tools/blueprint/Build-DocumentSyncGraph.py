"""Build the transactional SyncDraftDocumentV1 Blueprint graph.

The graph mirrors ``tools/document/document_bridge.py`` using only node forms
round-tripped from the Conan Exiles Enhanced UE 5.6 DevKit. It rebuilds the
typed waypoint snapshot first, scans reusable prior segments, reconciles exact
adjacencies into scratch storage, validates document metadata and calculated
duration, then replaces both public draft values in one final commit chain.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_GRAPH = "SyncDraftDocumentV1"
TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
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
DOCUMENT_STRUCT = (
    "/Script/CoreUObject.UserDefinedStruct'"
    "/Game/Mods/ExileDroneDirector/Data/Structs/"
    "ST_EDD_FlypathDocument.ST_EDD_FlypathDocument'"
)
MAX_INT = 2_147_483_647

WP_ID = "WaypointId_2_0654FE3F4542AC31B6E13BBB55C34DAE"
WP_HOLD = "HoldSeconds_14_09EDC66D4C9D2D3AF6C4D2A7871843EB"
SEG_ID = "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0"
SEG_FROM = "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91"
SEG_TO = "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B"
SEG_DURATION = "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A"
SEG_CURVE = "SpatialCurveType_15_39D20A5A4CD2FB464BAA64839CE4012E"
SEG_PROFILE = "TimeProfile_16_3195F0C3470E1AECB34316A7BFBD2FBA"
DOC_SCHEMA = "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"
DOC_ENGINE = "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D"
DOC_REVISION = "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"
DOC_REGION = "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"
DOC_DURATION = "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"
DOC_PROFILE = "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161"
DOC_WAYPOINTS = "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"
DOC_SEGMENTS = "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"
DOC_HASH = "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"


def load_primitives(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_document_graph_primitives", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph primitives from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.TARGET_ASSET = TARGET_ASSET
    module.TARGET_GRAPH = TARGET_GRAPH
    module._id_counter = 0
    return module


def replace_pin_type(
    node,
    pin_name: str,
    category: str,
    subcategory: str = "",
    obj: str = "None",
    container: str = "None",
) -> None:
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, count=1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, count=1)
        line = re.sub(
            r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',
            f"PinType.PinSubCategoryObject={obj}",
            line,
            count=1,
        )
        return re.sub(r"PinType.ContainerType=\w+", f"PinType.ContainerType={container}", line, count=1)

    node.mutate_pin(pin_name, mutate)


def kind_parts(kind: str) -> tuple[str, str, str]:
    if kind == "bool":
        return "bool", "", "None"
    if kind == "int":
        return "int", "", "None"
    if kind == "real":
        return "real", "double", "None"
    if kind == "string":
        return "string", "", "None"
    if kind == "waypoint":
        return "struct", "", f'"{WAYPOINT_STRUCT}"'
    if kind == "segment":
        return "struct", "", f'"{SEGMENT_STRUCT}"'
    if kind == "document":
        return "struct", "", f'"{DOCUMENT_STRUCT}"'
    raise RuntimeError(f"Unsupported Blueprint kind: {kind}")


def set_kind(node, pin_name: str, kind: str, *, array: bool = False) -> None:
    category, subcategory, obj = kind_parts(kind)
    replace_pin_type(node, pin_name, category, subcategory, obj, "Array" if array else "None")


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name)
    node.text = "\n".join(line for line in node.text.splitlines() if f"PinId={pin_id}" not in line)


def rename_pin(node, old_name: str, new_name: str) -> None:
    node.text = node.text.replace(f'PinName="{old_name}"', f'PinName="{new_name}"')
    node.pins[new_name] = node.pins.pop(old_name)


def retarget_variable(node, old_name: str, new_name: str, kind: str, *, array: bool = False) -> None:
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{re.escape(old_name)}"[^)]*\)',
        f'VariableReference=(MemberName="{new_name}",bSelfContext=True)',
        node.text,
        count=1,
    )
    rename_pin(node, old_name, new_name)
    set_kind(node, new_name, kind, array=array)
    if "Output_Get" in node.pins:
        set_kind(node, "Output_Get", kind, array=array)


def retarget_math(node, member_name: str, result_kind: str = "bool") -> None:
    node.text = re.sub(r'MemberName="[^"]+"', f'MemberName="{member_name}"', node.text, count=1)
    if "ReturnValue" in node.pins:
        set_kind(node, "ReturnValue", result_kind)


def retarget_string_equal(node) -> None:
    retarget_math(node, "EqualEqual_StrStr")
    node.text = re.sub(
        r'MemberParent="[^"]+"',
        'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetStringLibrary\'"',
        node.text,
        count=1,
    )
    for pin in ("A", "B"):
        set_kind(node, pin, "string")
    if "self" in node.pins:
        def mutate(line: str) -> str:
            line = re.sub(
                r'PinType.PinSubCategoryObject="[^"]+"',
                'PinType.PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.KismetStringLibrary\'"',
                line,
                count=1,
            )
            return re.sub(
                r'DefaultObject="[^"]+"',
                'DefaultObject="/Script/Engine.Default__KismetStringLibrary"',
                line,
                count=1,
            )
        node.mutate_pin("self", mutate)


def make_clear(node) -> None:
    node.text = node.text.replace('MemberName="Array_Add"', 'MemberName="Array_Clear"', 1)
    remove_pin(node, "NewItem")
    remove_pin(node, "ReturnValue")


def make_array_find(node) -> None:
    node.text = node.text.replace('MemberName="Array_IsValidIndex"', 'MemberName="Array_Find"', 1)
    rename_pin(node, "IndexToTest", "ItemToFind")
    set_kind(node, "TargetArray", "int", array=True)
    set_kind(node, "ItemToFind", "int")
    set_kind(node, "ReturnValue", "int")


def make_break_waypoint(node) -> None:
    node.text = node.text.replace("/Script/BlueprintGraph.K2Node_MakeStruct", "/Script/BlueprintGraph.K2Node_BreakStruct")
    header, rest = node.text.split("\n", 1)
    node.text = header + "\n   bMadeAfterOverridePinRemoval=True\n" + rest

    def make_input(line: str) -> str:
        return line.replace(',Direction="EGPD_Output"', "", 1)

    def make_output(line: str) -> str:
        if 'Direction="EGPD_Output"' not in line:
            line = line.replace(",PinType.PinCategory=", ',Direction="EGPD_Output",PinType.PinCategory=', 1)
        line = re.sub(r',DefaultValue="[^"]*"', "", line)
        return re.sub(r',AutogeneratedDefaultValue="[^"]*"', "", line)

    node.mutate_pin("ST_EDD_Waypoint", make_input)
    for pin in (WP_ID, "CameraTransform_5_6A923AA84DB46D9EE28DF38943321FC9", "FocalLength_8_C703B5A74B2AD4D6061535A85504FB8B", "Aperture_10_949C579344F8DFA750F1948051A417B2", "ManualFocusDistance_12_FDAA24BB4FD409CE159361B97904885F", WP_HOLD):
        node.mutate_pin(pin, make_output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    bp = load_primitives(args.project_root)
    Node = bp.Node
    connect = bp.connect
    set_default = bp.set_pin_default
    read_blocks = bp.read_blocks
    find = bp.find_block

    root = args.project_root / "tools" / "blueprint"
    waypoint_forms = read_blocks(root / "templates" / "waypoint-struct-sync-node-forms.eddgraph")
    document_forms = read_blocks(root / "templates" / "document-sync-struct-node-forms.eddgraph")
    capture_forms = read_blocks(root / "templates" / "waypoint-capture-node-forms.eddgraph")
    edit_forms = read_blocks(root / "templates" / "waypoint-edit-node-forms.eddgraph")
    start = read_blocks(root / "snippets" / "start-linear-playback.eddgraph")
    playback = read_blocks(root / "snippets" / "update-linear-playback.eddgraph")
    enter = read_blocks(root / "snippets" / "enter-drone-mode.eddgraph")
    event = read_blocks(root / "snippets" / "client-director-event-graph.eddgraph")

    templates = {
        "entry": find(waypoint_forms, r"K2Node_FunctionEntry"),
        "foreach": find(waypoint_forms, r"K2Node_MacroInstance"),
        "make_waypoint": find(waypoint_forms, r"K2Node_MakeStruct"),
        "waypoints": find(waypoint_forms, r'MemberName="DraftWaypointsV1"'),
        "make_segment": find(document_forms, r"K2Node_MakeStruct.*?StructType=.*?ST_EDD_Segment"),
        "break_segment": find(document_forms, r"K2Node_BreakStruct.*?StructType=.*?ST_EDD_Segment"),
        "make_document": find(document_forms, r"K2Node_MakeStruct.*?StructType=.*?ST_EDD_FlypathDocument"),
        "break_document": find(document_forms, r"K2Node_BreakStruct.*?StructType=.*?ST_EDD_FlypathDocument"),
        "array_add": find(capture_forms, r'MemberName="Array_Add"'),
        "int_add": find(capture_forms, r'MemberName="Add_IntInt"'),
        "array_find": find(edit_forms, r'MemberName="Array_IsValidIndex"'),
        "get_item": find(
            playback,
            r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_GetArrayItem\b",
        ),
        "length": find(playback, r'MemberName="Array_Length"'),
        "int_math": find(playback, r'MemberName="Subtract_IntInt"'),
        "int_compare": find(start, r'MemberName="GreaterEqual_IntInt"'),
        "double_math": find(start, r'MemberName="GreaterEqual_DoubleDouble"'),
        "bool_get": find(playback, r'K2Node_VariableGet.*?MemberName="PlaybackActive"'),
        "bool_set": find(start, r'K2Node_VariableSet.*?MemberName="PlaybackActive"'),
        "branch": find(enter, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse\b"),
        "print": find(enter, r'MemberName="PrintString"'),
        "self_call": find(event, r'MemberName="EnterDroneMode"'),
    }

    nodes = {}
    serial: dict[str, int] = {}

    def add(key: str, template: str, prefix: str, x: int, y: int):
        class_name = {
            "get": "K2Node_VariableGet",
            "set": "K2Node_VariableSet",
            "call": "K2Node_CallFunction",
            "branch": "K2Node_IfThenElse",
            "array": "K2Node_CallArrayFunction",
            "macro": "K2Node_MacroInstance",
            "struct": "K2Node_StructOperation",
            "print": "K2Node_CallFunction",
        }[prefix]
        index = serial.get(class_name, 0)
        serial[class_name] = index + 1
        node = Node.clone(key, templates[template], f"{class_name}_{index}", x, y)
        nodes[key] = node
        return node

    def var_get(key: str, name: str, kind: str, x: int, y: int, *, array: bool = False):
        node = add(key, "bool_get", "get", x, y)
        retarget_variable(node, "PlaybackActive", name, kind, array=array)
        return node

    def var_set(key: str, name: str, kind: str, x: int, y: int, *, array: bool = False, default: str | None = None):
        node = add(key, "bool_set", "set", x, y)
        retarget_variable(node, "PlaybackActive", name, kind, array=array)
        if default is not None:
            set_default(node, name, default)
        return node

    def array_getter(key: str, name: str, kind: str, x: int, y: int):
        node = add(key, "waypoints", "get", x, y)
        retarget_variable(node, "DraftWaypointsV1", name, kind, array=True)
        return node

    def array_add(key: str, kind: str, x: int, y: int):
        node = add(key, "array_add", "array", x, y)
        set_kind(node, "TargetArray", kind, array=True)
        set_kind(node, "NewItem", kind)
        return node

    def array_clear(key: str, kind: str, x: int, y: int):
        node = add(key, "array_add", "array", x, y)
        make_clear(node)
        set_kind(node, "TargetArray", kind, array=True)
        return node

    def foreach(key: str, kind: str, x: int, y: int):
        node = add(key, "foreach", "macro", x, y)
        set_kind(node, "Array", kind, array=True)
        set_kind(node, "Array Element", kind)
        return node

    def get_item(key: str, kind: str, x: int, y: int):
        node = add(key, "get_item", "call", x, y)
        set_kind(node, "Array", kind, array=True)
        set_kind(node, "Output", kind)
        return node

    def math(key: str, function: str, kind: str, result: str, x: int, y: int):
        template = "double_math" if kind == "real" else "int_math"
        node = add(key, template, "call", x, y)
        retarget_math(node, function, result)
        for pin in ("A", "B"):
            set_kind(node, pin, kind)
        return node

    def branch(key: str, x: int, y: int):
        return add(key, "branch", "branch", x, y)

    def failure(key: str, message: str, x: int, y: int):
        node = add(key, "print", "print", x, y)
        set_default(node, "InString", message)
        return node

    # Entry and typed-waypoint preflight.
    entry = Node.clone("entry", templates["entry"], "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(r'MemberName="SyncDraftWaypointsV1"', 'MemberName="SyncDraftDocumentV1"', entry.text, count=1)
    nodes["entry"] = entry
    sync_waypoints = add("sync_waypoints", "self_call", "call", 256, 0)
    sync_waypoints.text = re.sub(
        r'FunctionReference=\([^)]*\)',
        'FunctionReference=(MemberName="SyncDraftWaypointsV1",bSelfContext=True)',
        sync_waypoints.text,
        count=1,
    )
    preflight = branch("waypoint_preflight", 512, 0)
    preflight_get = var_get("waypoint_preflight_get", "WaypointPreflightValid", "bool", 512, 208)
    preflight_fail = failure("waypoint_preflight_fail", "[EDD] Document sync rejected: waypoint preflight failed", 736, -208)
    connect(entry, "then", sync_waypoints, "execute")
    connect(sync_waypoints, "then", preflight, "execute")
    connect(preflight_get, "WaypointPreflightValid", preflight, "Condition")
    connect(preflight, "else", preflight_fail, "execute")

    # Transaction scratch initialization.
    valid_true = var_set("valid_true", "DocumentSyncValidV1", "bool", 768, 0, default="true")
    total_zero = var_set("total_zero", "DocumentTotalDurationV1", "real", 1024, 0, default="0.0")
    next_zero = var_set("next_zero", "DocumentNextSegmentIdV1", "int", 1280, 0, default="0")
    used_get_clear = array_getter("used_get_clear", "DocumentUsedSegmentIdsV1", "int", 1536, 208)
    used_clear = array_clear("used_clear", "int", 1760, 0)
    scratch_get_clear = array_getter("scratch_get_clear", "DocumentSegmentsScratchV1", "segment", 2016, 208)
    scratch_clear = array_clear("scratch_clear", "segment", 2240, 0)
    connect(preflight, "then", valid_true, "execute")
    connect(valid_true, "then", total_zero, "execute")
    connect(total_zero, "then", next_zero, "execute")
    connect(next_zero, "then", used_clear, "execute")
    connect(used_get_clear, "DocumentUsedSegmentIdsV1", used_clear, "TargetArray")
    connect(used_clear, "then", scratch_clear, "execute")
    connect(scratch_get_clear, "DocumentSegmentsScratchV1", scratch_clear, "TargetArray")

    # Reusable prior-segment scan establishes the monotonic ID floor.
    prior_get_scan = array_getter("prior_get_scan", "DraftSegmentsV1", "segment", 2496, 240)
    prior_scan = foreach("prior_scan", "segment", 2496, 0)
    prior_break_scan = add("prior_break_scan", "break_segment", "struct", 2784, 256)
    connect(scratch_clear, "then", prior_scan, "Exec")
    connect(prior_get_scan, "DraftSegmentsV1", prior_scan, "Array")
    connect(prior_scan, "Array Element", prior_break_scan, "ST_EDD_Segment")

    scan_conditions = []
    id_positive = math("scan_id_positive", "Greater_IntInt", "int", "bool", 3072, 224)
    set_default(id_positive, "B", "0")
    connect(prior_break_scan, SEG_ID, id_positive, "A")
    scan_conditions.append((id_positive, "ReturnValue", "then"))
    duration_delta = math("scan_duration_delta", "Subtract_DoubleDouble", "real", "real", 3072, 384)
    connect(prior_break_scan, SEG_DURATION, duration_delta, "A")
    connect(prior_break_scan, SEG_DURATION, duration_delta, "B")
    duration_finite = math("scan_duration_finite", "EqualEqual_DoubleDouble", "real", "bool", 3296, 384)
    set_default(duration_finite, "B", "0.0")
    connect(duration_delta, "ReturnValue", duration_finite, "A")
    scan_conditions.append((duration_finite, "ReturnValue", "then"))
    duration_positive = math("scan_duration_positive", "Greater_DoubleDouble", "real", "bool", 3072, 544)
    set_default(duration_positive, "B", "0.0")
    connect(prior_break_scan, SEG_DURATION, duration_positive, "A")
    scan_conditions.append((duration_positive, "ReturnValue", "then"))
    curve_empty = math("scan_curve_empty", "EqualEqual_IntInt", "int", "bool", 3072, 704)
    retarget_string_equal(curve_empty)
    set_default(curve_empty, "B", "")
    connect(prior_break_scan, SEG_CURVE, curve_empty, "A")
    scan_conditions.append((curve_empty, "ReturnValue", "else"))
    profile_empty = math("scan_profile_empty", "EqualEqual_IntInt", "int", "bool", 3072, 864)
    retarget_string_equal(profile_empty)
    set_default(profile_empty, "B", "")
    connect(prior_break_scan, SEG_PROFILE, profile_empty, "A")
    scan_conditions.append((profile_empty, "ReturnValue", "else"))
    scan_branches = []
    for index, (condition, pin, success_pin) in enumerate(scan_conditions):
        check = branch(f"scan_check_{index}", 3552 + index * 256, 0)
        connect(condition, pin, check, "Condition")
        scan_branches.append((check, success_pin))
    connect(prior_scan, "LoopBody", scan_branches[0][0], "execute")
    for (before, success_pin), (after, _) in zip(scan_branches, scan_branches[1:]):
        connect(before, success_pin, after, "execute")
    next_get_scan = var_get("next_get_scan", "DocumentNextSegmentIdV1", "int", 4896, 320)
    max_id = math("scan_max_id", "Max_IntInt", "int", "int", 5120, 256)
    connect(next_get_scan, "DocumentNextSegmentIdV1", max_id, "A")
    connect(prior_break_scan, SEG_ID, max_id, "B")
    next_set_scan = var_set("next_set_scan", "DocumentNextSegmentIdV1", "int", 5344, 0)
    connect(scan_branches[-1][0], scan_branches[-1][1], next_set_scan, "execute")
    connect(max_id, "ReturnValue", next_set_scan, "DocumentNextSegmentIdV1")

    # Outer waypoint loop accumulates holds and reconciles each adjacency.
    waypoints_get_outer = array_getter("waypoints_get_outer", "DraftWaypointsV1", "waypoint", 5600, 256)
    waypoint_loop = foreach("waypoint_loop", "waypoint", 5600, 0)
    current_break = add("current_break", "make_waypoint", "struct", 5888, 384)
    make_break_waypoint(current_break)
    connect(prior_scan, "Completed", waypoint_loop, "Exec")
    connect(waypoints_get_outer, "DraftWaypointsV1", waypoint_loop, "Array")
    connect(waypoint_loop, "Array Element", current_break, "ST_EDD_Waypoint")
    total_get_hold = var_get("total_get_hold", "DocumentTotalDurationV1", "real", 5888, 128)
    add_hold = math("add_hold", "Add_DoubleDouble", "real", "real", 6112, 128)
    connect(total_get_hold, "DocumentTotalDurationV1", add_hold, "A")
    connect(current_break, WP_HOLD, add_hold, "B")
    total_set_hold = var_set("total_set_hold", "DocumentTotalDurationV1", "real", 6336, 0)
    connect(waypoint_loop, "LoopBody", total_set_hold, "execute")
    connect(add_hold, "ReturnValue", total_set_hold, "DocumentTotalDurationV1")

    waypoint_length = add("waypoint_length", "length", "array", 5888, 720)
    set_kind(waypoint_length, "TargetArray", "waypoint", array=True)
    connect(waypoints_get_outer, "DraftWaypointsV1", waypoint_length, "TargetArray")
    segment_count = math("segment_count", "Subtract_IntInt", "int", "int", 6112, 720)
    set_default(segment_count, "B", "1")
    connect(waypoint_length, "ReturnValue", segment_count, "A")
    has_adjacency = math("has_adjacency", "Less_IntInt", "int", "bool", 6336, 720)
    connect(waypoint_loop, "Array Index", has_adjacency, "A")
    connect(segment_count, "ReturnValue", has_adjacency, "B")
    adjacency_branch = branch("adjacency_branch", 6592, 0)
    connect(total_set_hold, "then", adjacency_branch, "execute")
    connect(has_adjacency, "ReturnValue", adjacency_branch, "Condition")

    next_index = math("next_index", "Add_IntInt", "int", "int", 6592, 720)
    set_default(next_index, "B", "1")
    connect(waypoint_loop, "Array Index", next_index, "A")
    next_waypoint = get_item("next_waypoint", "waypoint", 6816, 608)
    connect(waypoints_get_outer, "DraftWaypointsV1", next_waypoint, "Array")
    connect(next_index, "ReturnValue", next_waypoint, "Dimension 1")
    next_break = add("next_break", "make_waypoint", "struct", 7040, 608)
    make_break_waypoint(next_break)
    connect(next_waypoint, "Output", next_break, "ST_EDD_Waypoint")

    match_false = var_set("match_false", "DocumentMatchFoundV1", "bool", 6816, 0, default="false")
    connect(adjacency_branch, "then", match_false, "execute")
    prior_get_match = array_getter("prior_get_match", "DraftSegmentsV1", "segment", 7072, 288)
    match_loop = foreach("match_loop", "segment", 7072, 0)
    connect(match_false, "then", match_loop, "Exec")
    connect(prior_get_match, "DraftSegmentsV1", match_loop, "Array")
    match_break = add("match_break", "break_segment", "struct", 7360, 288)
    connect(match_loop, "Array Element", match_break, "ST_EDD_Segment")

    match_get = var_get("match_get", "DocumentMatchFoundV1", "bool", 7360, 64)
    match_not_yet = branch("match_not_yet", 7584, 0)
    connect(match_loop, "LoopBody", match_not_yet, "execute")
    connect(match_get, "DocumentMatchFoundV1", match_not_yet, "Condition")
    match_conditions = []
    from_equal = math("match_from", "EqualEqual_IntInt", "int", "bool", 7584, 480)
    connect(match_break, SEG_FROM, from_equal, "A")
    connect(current_break, WP_ID, from_equal, "B")
    match_conditions.append((from_equal, "ReturnValue", "then"))
    to_equal = math("match_to", "EqualEqual_IntInt", "int", "bool", 7584, 608)
    connect(match_break, SEG_TO, to_equal, "A")
    connect(next_break, WP_ID, to_equal, "B")
    match_conditions.append((to_equal, "ReturnValue", "then"))
    match_id_positive = math("match_id_positive", "Greater_IntInt", "int", "bool", 7584, 736)
    set_default(match_id_positive, "B", "0")
    connect(match_break, SEG_ID, match_id_positive, "A")
    match_conditions.append((match_id_positive, "ReturnValue", "then"))
    match_duration_delta = math("match_duration_delta", "Subtract_DoubleDouble", "real", "real", 7584, 864)
    connect(match_break, SEG_DURATION, match_duration_delta, "A")
    connect(match_break, SEG_DURATION, match_duration_delta, "B")
    match_duration_finite = math("match_duration_finite", "EqualEqual_DoubleDouble", "real", "bool", 7808, 864)
    set_default(match_duration_finite, "B", "0.0")
    connect(match_duration_delta, "ReturnValue", match_duration_finite, "A")
    match_conditions.append((match_duration_finite, "ReturnValue", "then"))
    match_duration_positive = math("match_duration_positive", "Greater_DoubleDouble", "real", "bool", 7584, 992)
    set_default(match_duration_positive, "B", "0.0")
    connect(match_break, SEG_DURATION, match_duration_positive, "A")
    match_conditions.append((match_duration_positive, "ReturnValue", "then"))
    match_curve_empty = math("match_curve_empty", "EqualEqual_IntInt", "int", "bool", 7584, 1120)
    retarget_string_equal(match_curve_empty)
    set_default(match_curve_empty, "B", "")
    connect(match_break, SEG_CURVE, match_curve_empty, "A")
    match_conditions.append((match_curve_empty, "ReturnValue", "else"))
    match_profile_empty = math("match_profile_empty", "EqualEqual_IntInt", "int", "bool", 7584, 1248)
    retarget_string_equal(match_profile_empty)
    set_default(match_profile_empty, "B", "")
    connect(match_break, SEG_PROFILE, match_profile_empty, "A")
    match_conditions.append((match_profile_empty, "ReturnValue", "else"))
    used_get_find = array_getter("used_get_find", "DocumentUsedSegmentIdsV1", "int", 7584, 1376)
    used_find = add("used_find", "array_find", "array", 7808, 1376)
    make_array_find(used_find)
    connect(used_get_find, "DocumentUsedSegmentIdsV1", used_find, "TargetArray")
    connect(match_break, SEG_ID, used_find, "ItemToFind")
    unused = math("unused", "EqualEqual_IntInt", "int", "bool", 8032, 1376)
    set_default(unused, "B", "-1")
    connect(used_find, "ReturnValue", unused, "A")
    match_conditions.append((unused, "ReturnValue", "then"))

    match_branches = []
    for index, (condition, pin, success_pin) in enumerate(match_conditions):
        check = branch(f"match_check_{index}", 8096 + index * 240, 0)
        connect(condition, pin, check, "Condition")
        match_branches.append((check, success_pin))
    connect(match_not_yet, "else", match_branches[0][0], "execute")
    for (before, success_pin), (after, _) in zip(match_branches, match_branches[1:]):
        connect(before, success_pin, after, "execute")
    candidate_set = var_set("candidate_set", "DocumentCandidateSegmentV1", "segment", 10032, 0)
    connect(match_branches[-1][0], match_branches[-1][1], candidate_set, "execute")
    connect(match_loop, "Array Element", candidate_set, "DocumentCandidateSegmentV1")
    match_true = var_set("match_true", "DocumentMatchFoundV1", "bool", 10288, 0, default="true")
    connect(candidate_set, "then", match_true, "execute")

    # Completed nested scan chooses preserved or new segment append path.
    match_result_get = var_get("match_result_get", "DocumentMatchFoundV1", "bool", 10544, 240)
    match_result = branch("match_result", 10768, 0)
    connect(match_loop, "Completed", match_result, "execute")
    connect(match_result_get, "DocumentMatchFoundV1", match_result, "Condition")

    def append_segment(prefix: str, exec_node, exec_pin: str, value_node, value_pin: str, duration_node, duration_pin: str, id_node, id_pin: str, x: int):
        scratch_get = array_getter(f"{prefix}_scratch_get", "DocumentSegmentsScratchV1", "segment", x, 320)
        add_segment = array_add(f"{prefix}_add_segment", "segment", x + 224, 0)
        connect(exec_node, exec_pin, add_segment, "execute")
        connect(scratch_get, "DocumentSegmentsScratchV1", add_segment, "TargetArray")
        connect(value_node, value_pin, add_segment, "NewItem")
        used_get = array_getter(f"{prefix}_used_get", "DocumentUsedSegmentIdsV1", "int", x + 448, 320)
        add_used = array_add(f"{prefix}_add_used", "int", x + 672, 0)
        connect(add_segment, "then", add_used, "execute")
        connect(used_get, "DocumentUsedSegmentIdsV1", add_used, "TargetArray")
        connect(id_node, id_pin, add_used, "NewItem")
        total_get = var_get(f"{prefix}_total_get", "DocumentTotalDurationV1", "real", x + 896, 320)
        total_add = math(f"{prefix}_total_add", "Add_DoubleDouble", "real", "real", x + 1120, 256)
        connect(total_get, "DocumentTotalDurationV1", total_add, "A")
        connect(duration_node, duration_pin, total_add, "B")
        total_set = var_set(f"{prefix}_total_set", "DocumentTotalDurationV1", "real", x + 1344, 0)
        connect(add_used, "then", total_set, "execute")
        connect(total_add, "ReturnValue", total_set, "DocumentTotalDurationV1")
        return total_set

    candidate_get = var_get("preserved_candidate_get", "DocumentCandidateSegmentV1", "segment", 10768, 368)
    candidate_break = add("preserved_candidate_break", "break_segment", "struct", 10992, 368)
    connect(candidate_get, "DocumentCandidateSegmentV1", candidate_break, "ST_EDD_Segment")
    append_segment("preserved", match_result, "then", candidate_get, "DocumentCandidateSegmentV1", candidate_break, SEG_DURATION, candidate_break, SEG_ID, 11248)

    next_get_exhaust = var_get("next_get_exhaust", "DocumentNextSegmentIdV1", "int", 10768, 608)
    exhausted = math("exhausted", "GreaterEqual_IntInt", "int", "bool", 10992, 608)
    set_default(exhausted, "B", str(MAX_INT))
    connect(next_get_exhaust, "DocumentNextSegmentIdV1", exhausted, "A")
    exhausted_branch = branch("exhausted_branch", 11248, 0)
    connect(match_result, "else", exhausted_branch, "execute")
    connect(exhausted, "ReturnValue", exhausted_branch, "Condition")
    invalid_exhausted = var_set("invalid_exhausted", "DocumentSyncValidV1", "bool", 11504, -192, default="false")
    exhausted_message = failure("exhausted_message", "[EDD] Document sync rejected: segment ID space exhausted", 11760, -192)
    connect(exhausted_branch, "then", invalid_exhausted, "execute")
    connect(invalid_exhausted, "then", exhausted_message, "execute")
    increment_id = math("increment_id", "Add_IntInt", "int", "int", 11504, 544)
    set_default(increment_id, "B", "1")
    connect(next_get_exhaust, "DocumentNextSegmentIdV1", increment_id, "A")
    next_set_new = var_set("next_set_new", "DocumentNextSegmentIdV1", "int", 11728, 0)
    connect(exhausted_branch, "else", next_set_new, "execute")
    connect(increment_id, "ReturnValue", next_set_new, "DocumentNextSegmentIdV1")
    make_new = add("make_new", "make_segment", "struct", 11984, 416)
    connect(increment_id, "ReturnValue", make_new, SEG_ID)
    connect(current_break, WP_ID, make_new, SEG_FROM)
    connect(next_break, WP_ID, make_new, SEG_TO)
    append_segment("new", next_set_new, "then", make_new, "ST_EDD_Segment", make_new, SEG_DURATION, make_new, SEG_ID, 12240)

    # Final validation and atomic publication.
    valid_final_get = var_get("valid_final_get", "DocumentSyncValidV1", "bool", 13760, 240)
    valid_final = branch("valid_final", 13984, 0)
    final_invalid = failure("final_invalid", "[EDD] Document sync rejected: transaction invalid", 14240, -192)
    connect(waypoint_loop, "Completed", valid_final, "execute")
    connect(valid_final_get, "DocumentSyncValidV1", valid_final, "Condition")
    connect(valid_final, "else", final_invalid, "execute")

    document_get = var_get("document_get", "DraftDocumentV1", "document", 13984, 384)
    document_break = add("document_break", "break_document", "struct", 14240, 384)
    connect(document_get, "DraftDocumentV1", document_break, "ST_EDD_FlypathDocument")
    metadata_conditions = []
    schema_ok = math("schema_ok", "EqualEqual_IntInt", "int", "bool", 14496, 416)
    set_default(schema_ok, "B", "1")
    connect(document_break, DOC_SCHEMA, schema_ok, "A")
    metadata_conditions.append((schema_ok, "ReturnValue", "then"))
    engine_ok = math("engine_ok", "EqualEqual_IntInt", "int", "bool", 14496, 544)
    set_default(engine_ok, "B", "1")
    connect(document_break, DOC_ENGINE, engine_ok, "A")
    metadata_conditions.append((engine_ok, "ReturnValue", "then"))
    revision_ok = math("revision_ok", "GreaterEqual_IntInt", "int", "bool", 14496, 672)
    set_default(revision_ok, "B", "0")
    connect(document_break, DOC_REVISION, revision_ok, "A")
    metadata_conditions.append((revision_ok, "ReturnValue", "then"))
    profile_is_empty = math("profile_is_empty", "EqualEqual_IntInt", "int", "bool", 14496, 800)
    retarget_string_equal(profile_is_empty)
    set_default(profile_is_empty, "B", "")
    connect(document_break, DOC_PROFILE, profile_is_empty, "A")
    metadata_conditions.append((profile_is_empty, "ReturnValue", "else"))
    total_get_finite = var_get("total_get_finite", "DocumentTotalDurationV1", "real", 14496, 960)
    total_delta = math("total_delta", "Subtract_DoubleDouble", "real", "real", 14720, 960)
    connect(total_get_finite, "DocumentTotalDurationV1", total_delta, "A")
    connect(total_get_finite, "DocumentTotalDurationV1", total_delta, "B")
    total_finite = math("total_finite", "EqualEqual_DoubleDouble", "real", "bool", 14944, 960)
    set_default(total_finite, "B", "0.0")
    connect(total_delta, "ReturnValue", total_finite, "A")
    metadata_conditions.append((total_finite, "ReturnValue", "then"))
    metadata_branches = []
    for index, (condition, pin, success_pin) in enumerate(metadata_conditions):
        check = branch(f"metadata_check_{index}", 15200 + index * 256, 0)
        connect(condition, pin, check, "Condition")
        reject = failure(f"metadata_reject_{index}", f"[EDD] Document sync rejected: metadata guard {index + 1}", 15200 + index * 256, -192)
        connect(check, "else" if success_pin == "then" else "then", reject, "execute")
        metadata_branches.append((check, success_pin))
    connect(valid_final, "then", metadata_branches[0][0], "execute")
    for (before, success_pin), (after, _) in zip(metadata_branches, metadata_branches[1:]):
        connect(before, success_pin, after, "execute")

    make_document = add("make_document", "make_document", "struct", 16544, 384)
    connect(document_break, DOC_REVISION, make_document, DOC_REVISION)
    connect(document_break, DOC_REGION, make_document, DOC_REGION)
    connect(document_break, DOC_PROFILE, make_document, DOC_PROFILE)
    total_get_commit = var_get("total_get_commit", "DocumentTotalDurationV1", "real", 16288, 672)
    connect(total_get_commit, "DocumentTotalDurationV1", make_document, DOC_DURATION)
    waypoints_get_commit = array_getter("waypoints_get_commit", "DraftWaypointsV1", "waypoint", 16288, 800)
    connect(waypoints_get_commit, "DraftWaypointsV1", make_document, DOC_WAYPOINTS)
    scratch_get_commit = array_getter("scratch_get_commit", "DocumentSegmentsScratchV1", "segment", 16288, 928)
    connect(scratch_get_commit, "DocumentSegmentsScratchV1", make_document, DOC_SEGMENTS)
    set_default(make_document, DOC_HASH, "")

    segments_set = var_set("segments_set", "DraftSegmentsV1", "segment", 16832, 0, array=True)
    connect(metadata_branches[-1][0], metadata_branches[-1][1], segments_set, "execute")
    connect(scratch_get_commit, "DocumentSegmentsScratchV1", segments_set, "DraftSegmentsV1")
    document_set = var_set("document_set", "DraftDocumentV1", "document", 17088, 0)
    connect(segments_set, "then", document_set, "execute")
    connect(make_document, "ST_EDD_FlypathDocument", document_set, "DraftDocumentV1")
    success = failure("success", "[EDD] Document sync complete", 17344, 0)
    connect(document_set, "then", success, "execute")

    ordered = list(nodes.values())
    full = "\n".join(node.text for node in ordered) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        pasted = []
        entry_pin_id = entry.pins["then"]
        for node in ordered:
            if node.key == "entry":
                continue
            text = re.sub(
                rf",LinkedTo=\(K2Node_FunctionEntry_0 {entry_pin_id},\)",
                "",
                node.text,
            )
            pasted.append(text)
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(pasted) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
