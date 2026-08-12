"""Build candidate position segments and flattened adaptive arc tables."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildPositionRouteSegmentsV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_position_segments_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-position-route-candidate-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    translation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-translation-input.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "array_item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
        "make_vector": bp.find_block(marker, r'MemberName="MakeVector"'),
        "multiply_vector": bp.find_block(translation, r'MemberName="Multiply_VectorVector"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get_array(name: str, kind: str, x: int, y: int):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, True)
        return node

    def get_value(name: str, kind: str, x: int, y: int):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind)
        return node

    def set_value(name: str, kind: str, x: int, y: int, default: str | None = None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def add_node(key: str, form: str, x: int, y: int):
        return b.add(key, form, x, y)

    def array_item(source, source_pin: str, kind: str, index, index_pin: str, x: int, y: int, key: str):
        node = add_node(key, "array_item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def array_add(target, target_pin: str, kind: str, value, value_pin: str, x: int, y: int, key: str):
        node = add_node(key, "array_add", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "NewItem", kind)
        bp.connect(target, target_pin, node, "TargetArray")
        bp.connect(value, value_pin, node, "NewItem")
        return node

    def array_clear(target, target_pin: str, kind: str, x: int, y: int, key: str):
        node = add_node(key, "array_clear", x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(target, target_pin, node, "TargetArray")
        return node

    def array_length(source, source_pin: str, kind: str, x: int, y: int, key: str):
        node = add_node(key, "array_length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def math(member: str, kind: str, left, left_pin: str, right, right_pin: str, x: int, y: int, key: str):
        node = b.math(member, x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, kind)
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def call(member: str, x: int, y: int):
        node = add_node(f"call_{member}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1))
        return node

    positions = get_array("PositionRouteInputWaypointPositionsV1", "vector", 0, 0)
    durations = get_array("PositionRouteInputDurationsV1", "real", 0, 192)
    curves = get_array("PositionRouteInputSpatialCurveTypesV1", "string", 0, 384)
    velocities = get_array("PositionRouteCandidateWaypointVelocitiesV1", "vector", 0, 576)
    segment_starts = get_array("PositionRouteCandidateSegmentStartsV1", "real", 0, 768)
    arc_starts = get_array("PositionRouteCandidateArcSampleStartsV1", "int", 0, 960)
    arc_counts = get_array("PositionRouteCandidateArcSampleCountsV1", "int", 0, 1152)
    arc_us = get_array("PositionRouteCandidateArcUsV1", "real", 0, 1344)
    arc_distances = get_array("PositionRouteCandidateArcDistancesV1", "real", 0, 1536)
    segment_lengths = get_array("PositionRouteCandidateSegmentLengthsV1", "real", 0, 1728)

    clears = [
        array_clear(segment_starts, "PositionRouteCandidateSegmentStartsV1", "real", 256, 2112, "clear_segment_starts"),
        array_clear(arc_starts, "PositionRouteCandidateArcSampleStartsV1", "int", 512, 2112, "clear_arc_starts"),
        array_clear(arc_counts, "PositionRouteCandidateArcSampleCountsV1", "int", 768, 2112, "clear_arc_counts"),
        array_clear(arc_us, "PositionRouteCandidateArcUsV1", "real", 1024, 2112, "clear_arc_us"),
        array_clear(arc_distances, "PositionRouteCandidateArcDistancesV1", "real", 1280, 2112, "clear_arc_distances"),
        array_clear(segment_lengths, "PositionRouteCandidateSegmentLengthsV1", "real", 1536, 2112, "clear_segment_lengths"),
    ]
    bp.connect(b.entry, "then", clears[0], "execute")
    for left, right in zip(clears, clears[1:]):
        bp.connect(left, "then", right, "execute")
    reset_seconds = set_value("PositionRouteCandidateTotalSecondsV1", "real", 1792, 2112, "0.0")
    reset_distance = set_value("PositionRouteCandidateTotalDistanceV1", "real", 2048, 2112, "0.0")
    reset_operations = set_value("PositionRouteCandidateOperationCountV1", "int", 2304, 2112, "0")
    bp.connect(clears[-1], "then", reset_seconds, "execute")
    bp.connect(reset_seconds, "then", reset_distance, "execute")
    bp.connect(reset_distance, "then", reset_operations, "execute")

    stage = get_value("PositionRouteStageValidV1", "bool", 2304, 1824)
    position_count = array_length(positions, "PositionRouteInputWaypointPositionsV1", "vector", 2304, 1440, "position_count")
    velocity_count = array_length(velocities, "PositionRouteCandidateWaypointVelocitiesV1", "vector", 2304, 1600, "velocity_count")
    counts_match = b.add("counts_match", "compare", 2560, 1440)
    scalar.retarget_function(counts_match, "EqualEqual_IntInt")
    for pin in ("A", "B"):
        pin_kind(counts_match, pin, "int")
    pin_kind(counts_match, "ReturnValue", "bool")
    bp.connect(position_count, "ReturnValue", counts_match, "A")
    bp.connect(velocity_count, "ReturnValue", counts_match, "B")
    ready = b.add("ready", "compare", 2560, 1600)
    scalar.retarget_function(ready, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(ready, pin, "bool")
    bp.connect(stage, "PositionRouteStageValidV1", ready, "A")
    bp.connect(counts_match, "ReturnValue", ready, "B")
    outer = b.add("outer", "branch", 2560, 2112)
    bp.connect(reset_operations, "then", outer, "execute")
    bp.connect(ready, "ReturnValue", outer, "Condition")
    loop = add_node("segment_loop", "foreach", 2816, 1824)
    pin_kind(loop, "Array", "real", True)
    pin_kind(loop, "Array Element", "real")
    bp.connect(durations, "PositionRouteInputDurationsV1", loop, "Array")
    bp.connect(outer, "then", loop, "Exec")
    inner = b.add("inner", "branch", 3072, 2112)
    bp.connect(loop, "LoopBody", inner, "execute")
    bp.connect(stage, "PositionRouteStageValidV1", inner, "Condition")

    plus_one = b.math("Add_IntInt", 3072, 0)
    scalar.retarget_function(plus_one, "Add_IntInt")
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(plus_one, pin, "int")
    scalar.set_default(plus_one, "B", "1")
    bp.connect(loop, "Array Index", plus_one, "A")
    p0 = array_item(positions, "PositionRouteInputWaypointPositionsV1", "vector", loop, "Array Index", 3328, 0, "p0")
    p1 = array_item(positions, "PositionRouteInputWaypointPositionsV1", "vector", plus_one, "ReturnValue", 3328, 160, "p1")
    v0 = array_item(velocities, "PositionRouteCandidateWaypointVelocitiesV1", "vector", loop, "Array Index", 3328, 320, "v0")
    v1 = array_item(velocities, "PositionRouteCandidateWaypointVelocitiesV1", "vector", plus_one, "ReturnValue", 3328, 480, "v1")
    curve = array_item(curves, "PositionRouteInputSpatialCurveTypesV1", "string", loop, "Array Index", 3328, 640, "curve")
    linear = b.equal_string(3584, 640, "linear")
    bp.connect(curve, "Output", linear, "A")

    duration_vector = add_node("duration_vector", "make_vector", 3584, 320)
    for axis in "XYZ":
        bp.connect(loop, "Array Element", duration_vector, axis)
    scaled_v0 = add_node("scaled_v0", "multiply_vector", 3840, 320)
    scaled_v1 = add_node("scaled_v1", "multiply_vector", 3840, 480)
    bp.connect(v0, "Output", scaled_v0, "A")
    bp.connect(v1, "Output", scaled_v1, "A")
    bp.connect(duration_vector, "ReturnValue", scaled_v0, "B")
    bp.connect(duration_vector, "ReturnValue", scaled_v1, "B")

    tolerance = get_value("PositionRouteInputArcToleranceV1", "real", 3584, 800)
    max_depth = get_value("PositionRouteInputMaxArcDepthV1", "int", 3584, 960)
    max_operations = get_value("PositionRouteInputMaxArcOperationsV1", "int", 3584, 1120)
    staged = []
    for name, kind, source, source_pin, default in (
        ("TrajectoryArcBuildInputStartPositionV1", "vector", p0, "Output", None),
        ("TrajectoryArcBuildInputEndPositionV1", "vector", p1, "Output", None),
        ("TrajectoryArcBuildInputStartVelocityUV1", "vector", scaled_v0, "ReturnValue", None),
        ("TrajectoryArcBuildInputEndVelocityUV1", "vector", scaled_v1, "ReturnValue", None),
        ("TrajectoryArcBuildInputStartAccelerationUV1", "vector", None, "", "0, 0, 0"),
        ("TrajectoryArcBuildInputEndAccelerationUV1", "vector", None, "", "0, 0, 0"),
        ("TrajectoryArcBuildInputLinearV1", "bool", linear, "ReturnValue", None),
        ("TrajectoryArcBuildInputToleranceV1", "real", tolerance, "PositionRouteInputArcToleranceV1", None),
        ("TrajectoryArcBuildInputMaxDepthV1", "int", max_depth, "PositionRouteInputMaxArcDepthV1", None),
        ("TrajectoryArcBuildInputMaxOperationsV1", "int", max_operations, "PositionRouteInputMaxArcOperationsV1", None),
    ):
        node = set_value(name, kind, 4096, 1280 + len(staged) * 128, default)
        if source is not None:
            bp.connect(source, source_pin, node, name)
        staged.append(node)
    bp.connect(inner, "then", staged[0], "execute")
    for left, right in zip(staged, staged[1:]):
        bp.connect(left, "then", right, "execute")
    primitive = call("BuildAdaptiveArcTableV1", 4352, 2560)
    bp.connect(staged[-1], "then", primitive, "execute")
    arc_valid = get_value("TrajectoryArcBuildValidV1", "bool", 4608, 2304)
    result_guard = b.add("result_guard", "branch", 4864, 2560)
    bp.connect(primitive, "then", result_guard, "execute")
    bp.connect(arc_valid, "TrajectoryArcBuildValidV1", result_guard, "Condition")
    reject = set_value("PositionRouteStageValidV1", "bool", 5120, 2912, "false")
    bp.connect(outer, "else", reject, "execute")
    bp.connect(result_guard, "else", reject, "execute")

    total_seconds = get_value("PositionRouteCandidateTotalSecondsV1", "real", 4864, 1600)
    total_distance = get_value("PositionRouteCandidateTotalDistanceV1", "real", 4864, 1760)
    total_operations = get_value("PositionRouteCandidateOperationCountV1", "int", 4864, 1920)
    built_us = get_array("TrajectoryArcBuiltUsV1", "real", 4864, 0)
    built_distances = get_array("TrajectoryArcBuiltDistancesV1", "real", 4864, 192)
    built_length = get_value("TrajectoryArcBuiltLengthV1", "real", 4864, 384)
    built_operations = get_value("TrajectoryArcBuildOperationCountV1", "int", 4864, 576)
    flat_start = array_length(arc_us, "PositionRouteCandidateArcUsV1", "real", 5120, 0, "flat_start")
    sample_count = array_length(built_us, "TrajectoryArcBuiltUsV1", "real", 5120, 192, "sample_count")
    add_start = array_add(segment_starts, "PositionRouteCandidateSegmentStartsV1", "real", total_seconds, "PositionRouteCandidateTotalSecondsV1", 5376, 2176, "add_segment_start")
    add_arc_start = array_add(arc_starts, "PositionRouteCandidateArcSampleStartsV1", "int", flat_start, "ReturnValue", 5632, 2176, "add_arc_start")
    add_arc_count = array_add(arc_counts, "PositionRouteCandidateArcSampleCountsV1", "int", sample_count, "ReturnValue", 5888, 2176, "add_arc_count")
    bp.connect(result_guard, "then", add_start, "execute")
    bp.connect(add_start, "then", add_arc_start, "execute")
    bp.connect(add_arc_start, "then", add_arc_count, "execute")

    us_loop = add_node("us_loop", "foreach", 6144, 1920)
    pin_kind(us_loop, "Array", "real", True)
    pin_kind(us_loop, "Array Element", "real")
    bp.connect(built_us, "TrajectoryArcBuiltUsV1", us_loop, "Array")
    bp.connect(add_arc_count, "then", us_loop, "Exec")
    add_u = array_add(arc_us, "PositionRouteCandidateArcUsV1", "real", us_loop, "Array Element", 6400, 2176, "add_u")
    bp.connect(us_loop, "LoopBody", add_u, "execute")

    distance_loop = add_node("distance_loop", "foreach", 6656, 1920)
    pin_kind(distance_loop, "Array", "real", True)
    pin_kind(distance_loop, "Array Element", "real")
    bp.connect(built_distances, "TrajectoryArcBuiltDistancesV1", distance_loop, "Array")
    bp.connect(us_loop, "Completed", distance_loop, "Exec")
    add_distance = array_add(arc_distances, "PositionRouteCandidateArcDistancesV1", "real", distance_loop, "Array Element", 6912, 2176, "add_distance")
    bp.connect(distance_loop, "LoopBody", add_distance, "execute")

    add_length = array_add(segment_lengths, "PositionRouteCandidateSegmentLengthsV1", "real", built_length, "TrajectoryArcBuiltLengthV1", 7168, 2176, "add_length")
    bp.connect(distance_loop, "Completed", add_length, "execute")
    seconds_sum = math("Add_DoubleDouble", "real", total_seconds, "PositionRouteCandidateTotalSecondsV1", loop, "Array Element", 7168, 1440, "seconds_sum")
    distance_sum = math("Add_DoubleDouble", "real", total_distance, "PositionRouteCandidateTotalDistanceV1", built_length, "TrajectoryArcBuiltLengthV1", 7168, 1600, "distance_sum")
    operation_sum = math("Add_IntInt", "int", total_operations, "PositionRouteCandidateOperationCountV1", built_operations, "TrajectoryArcBuildOperationCountV1", 7168, 1760, "operation_sum")
    commit_seconds = set_value("PositionRouteCandidateTotalSecondsV1", "real", 7424, 2176)
    commit_distance = set_value("PositionRouteCandidateTotalDistanceV1", "real", 7680, 2176)
    commit_operations = set_value("PositionRouteCandidateOperationCountV1", "int", 7936, 2176)
    bp.connect(seconds_sum, "ReturnValue", commit_seconds, "PositionRouteCandidateTotalSecondsV1")
    bp.connect(distance_sum, "ReturnValue", commit_distance, "PositionRouteCandidateTotalDistanceV1")
    bp.connect(operation_sum, "ReturnValue", commit_operations, "PositionRouteCandidateOperationCountV1")
    bp.connect(add_length, "then", commit_seconds, "execute")
    bp.connect(commit_seconds, "then", commit_distance, "execute")
    bp.connect(commit_distance, "then", commit_operations, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
