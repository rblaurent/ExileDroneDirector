"""Build atomic publication of a fully assembled position-route candidate."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCompiledPositionRouteV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_position_commit_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, value: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[value]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


def variable(scalar, node, name: str, value: str, array: bool = False) -> None:
    scalar.retarget_variable(node, name, "real" if value == "int" else value)
    pin_kind(node, name, value, array)
    if "Output_Get" in node.pins:
        pin_kind(node, "Output_Get", value)


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
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-position-route-candidate-v1.eddgraph")
    foreach_form = bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')
    item_form = bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")
    clear_form = bp.find_block(reset, r'MemberName="Array_Clear"')
    b = scalar.Builder(bp, forms, FUNCTION)

    def add(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(form)
        node_class = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(node_class, 0)
        b.serial[node_class] = index + 1
        node = bp.Node.clone(key, form, f"{node_class}_{index}", x, y)
        b.nodes.append(node)
        return node

    def base_kind(value: str) -> str:
        return "real" if value == "int" else value

    def get(name: str, value: str, x: int, y: int, array: bool = False):
        node = b.get(name, base_kind(value), x, y)
        variable(scalar, node, name, value, array)
        return node

    def set_value(name: str, value: str, x: int, y: int, default: str | None = None, array: bool = False):
        node = b.set(name, base_kind(value), x, y, default)
        variable(scalar, node, name, value, array)
        return node

    def length(source, source_pin: str, value: str, x: int, y: int, key: str):
        node = add(key, length_form, x, y)
        pin_kind(node, "TargetArray", value, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin: str, value: str, index, index_pin: str, x: int, y: int, key: str):
        node = add(key, item_form, x, y)
        pin_kind(node, "Array", value, True)
        pin_kind(node, "Output", value)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def compare(member: str, left, left_pin: str, right, right_pin: str, x: int, y: int, value: str):
        node = b.add(f"cmp_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, value)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def math(member: str, left, left_pin: str, right, right_pin: str, x: int, y: int, value: str):
        node = b.math(member, x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, value)
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def and_all(values, x: int, y: int):
        current = values[0]
        for index, value in enumerate(values[1:]):
            current = compare("BooleanAND", current, "ReturnValue", value, "ReturnValue", x + index * 192, y, "bool")
        return current

    mappings = (
        ("PositionRouteInputWaypointPositionsV1", "PositionRouteCompiledWaypointPositionsV1", "vector"),
        ("PositionRouteInputDurationsV1", "PositionRouteCompiledDurationsV1", "real"),
        ("PositionRouteInputSpatialCurveTypesV1", "PositionRouteCompiledSpatialCurveTypesV1", "string"),
        ("PositionRouteInputTimeProfilesV1", "PositionRouteCompiledTimeProfilesV1", "string"),
        ("PositionRouteCandidateWaypointVelocitiesV1", "PositionRouteCompiledWaypointVelocitiesV1", "vector"),
        ("PositionRouteCandidateSegmentStartsV1", "PositionRouteCompiledSegmentStartsV1", "real"),
        ("PositionRouteCandidateArcSampleStartsV1", "PositionRouteCompiledArcSampleStartsV1", "int"),
        ("PositionRouteCandidateArcSampleCountsV1", "PositionRouteCompiledArcSampleCountsV1", "int"),
        ("PositionRouteCandidateArcUsV1", "PositionRouteCompiledArcUsV1", "real"),
        ("PositionRouteCandidateArcDistancesV1", "PositionRouteCompiledArcDistancesV1", "real"),
        ("PositionRouteCandidateSegmentLengthsV1", "PositionRouteCompiledSegmentLengthsV1", "real"),
    )

    reset_chain = []
    compiled_getters = {}
    for index, (_source_name, target_name, value) in enumerate(mappings):
        source = get(target_name, value, 0, index * 144, True)
        compiled_getters[target_name] = source
        clear = add(f"clear_{target_name}", clear_form, 256 + index * 224, 1856)
        pin_kind(clear, "TargetArray", value, True)
        bp.connect(source, target_name, clear, "TargetArray")
        reset_chain.append(clear)
    reset_specs = (
        ("PositionRouteCompiledTotalSecondsV1", "real", "0.0"),
        ("PositionRouteCompiledTotalDistanceV1", "real", "0.0"),
        ("PositionRouteCompileValidV1", "bool", "false"),
        ("PositionRouteResultSegmentIndexV1", "int", "-1"),
        ("PositionRouteResultLocalTimeAlphaV1", "real", "0.0"),
        ("PositionRouteResultDistanceAlphaV1", "real", "0.0"),
        ("PositionRouteResultCurveUV1", "real", "0.0"),
        ("PositionRouteResultPositionV1", "vector", "0, 0, 0"),
        ("PositionRouteResultCompleteV1", "bool", "false"),
        ("PositionRouteResultValidV1", "bool", "false"),
    )
    for name, value, default in reset_specs:
        reset_chain.append(set_value(name, value, 256 + len(reset_chain) * 224, 1856, default))
    bp.connect(b.entry, "then", reset_chain[0], "execute")
    for left, right in zip(reset_chain, reset_chain[1:]):
        bp.connect(left, "then", right, "execute")

    sources = {
        source_name: get(source_name, value, 0, 2400 + index * 144, True)
        for index, (source_name, _target_name, value) in enumerate(mappings)
    }
    lengths = {
        source_name: length(sources[source_name], source_name, value, 512 + index * 208, 2400, f"length_{index}")
        for index, (source_name, _target_name, value) in enumerate(mappings)
    }
    point_count = lengths["PositionRouteInputWaypointPositionsV1"]
    duration_count = lengths["PositionRouteInputDurationsV1"]
    flat_u_count = lengths["PositionRouteCandidateArcUsV1"]
    flat_distance_count = lengths["PositionRouteCandidateArcDistancesV1"]
    segment_count = math("Subtract_IntInt", point_count, "ReturnValue", None, "1", 512, 3200, "int")
    outer_conditions = [
        compare("GreaterEqual_IntInt", point_count, "ReturnValue", None, "2", 736, 3040, "int"),
        compare("LessEqual_IntInt", point_count, "ReturnValue", None, "512", 736, 3200, "int"),
        compare("EqualEqual_IntInt", duration_count, "ReturnValue", segment_count, "ReturnValue", 960, 3040, "int"),
    ]
    for index, name in enumerate((
        "PositionRouteInputSpatialCurveTypesV1",
        "PositionRouteInputTimeProfilesV1",
        "PositionRouteCandidateSegmentStartsV1",
        "PositionRouteCandidateArcSampleStartsV1",
        "PositionRouteCandidateArcSampleCountsV1",
        "PositionRouteCandidateSegmentLengthsV1",
    )):
        outer_conditions.append(compare("EqualEqual_IntInt", lengths[name], "ReturnValue", segment_count, "ReturnValue", 1184 + index * 224, 3040, "int"))
    outer_conditions.extend((
        compare("EqualEqual_IntInt", lengths["PositionRouteCandidateWaypointVelocitiesV1"], "ReturnValue", point_count, "ReturnValue", 1184, 3200, "int"),
        compare("EqualEqual_IntInt", flat_u_count, "ReturnValue", flat_distance_count, "ReturnValue", 1408, 3200, "int"),
    ))
    candidate_seconds = get("PositionRouteCandidateTotalSecondsV1", "real", 2752, 2400)
    candidate_distance = get("PositionRouteCandidateTotalDistanceV1", "real", 2752, 2544)
    candidate_operations = get("PositionRouteCandidateOperationCountV1", "int", 2752, 2688)
    max_operations = get("PositionRouteInputMaxArcOperationsV1", "int", 2752, 2832)
    stage = get("PositionRouteStageValidV1", "bool", 2752, 2976)
    outer_conditions.extend((
        b.finite(candidate_seconds, "PositionRouteCandidateTotalSecondsV1", 2976, 2400),
        compare("Greater_DoubleDouble", candidate_seconds, "PositionRouteCandidateTotalSecondsV1", None, "0.0", 2976, 2544, "real"),
        b.finite(candidate_distance, "PositionRouteCandidateTotalDistanceV1", 2976, 2688),
        compare("GreaterEqual_DoubleDouble", candidate_distance, "PositionRouteCandidateTotalDistanceV1", None, "0.0", 2976, 2832, "real"),
        compare("GreaterEqual_IntInt", candidate_operations, "PositionRouteCandidateOperationCountV1", segment_count, "ReturnValue", 3200, 2400, "int"),
    ))
    maximum_total_operations = math("Multiply_IntInt", segment_count, "ReturnValue", max_operations, "PositionRouteInputMaxArcOperationsV1", 3200, 2544, "int")
    outer_conditions.append(compare("LessEqual_IntInt", candidate_operations, "PositionRouteCandidateOperationCountV1", maximum_total_operations, "ReturnValue", 3424, 2544, "int"))
    stage_wrap = compare("BooleanAND", stage, "PositionRouteStageValidV1", None, "true", 3200, 2976, "bool")
    outer_conditions.append(stage_wrap)
    outer_valid = and_all(outer_conditions, 3648, 3200)
    sample_accumulator_init = set_value("PositionRouteResultSegmentIndexV1", "int", 3648, 1856, "0")
    bp.connect(reset_chain[-1], "then", sample_accumulator_init, "execute")
    outer = b.add("outer", "branch", 7040, 1856)
    bp.connect(sample_accumulator_init, "then", outer, "execute")
    bp.connect(outer_valid, "ReturnValue", outer, "Condition")
    outer_result_reset = set_value("PositionRouteResultSegmentIndexV1", "int", 7264, 1984, "-1")
    outer_reject = set_value("PositionRouteStageValidV1", "bool", 7488, 2112, "false")
    bp.connect(outer, "else", outer_result_reset, "execute")
    bp.connect(outer_result_reset, "then", outer_reject, "execute")

    loop = add("segment_loop", foreach_form, 7264, 2560)
    pin_kind(loop, "Array", "real", True)
    pin_kind(loop, "Array Element", "real")
    bp.connect(sources["PositionRouteInputDurationsV1"], "PositionRouteInputDurationsV1", loop, "Array")
    bp.connect(outer, "then", loop, "Exec")
    starts = sources["PositionRouteCandidateSegmentStartsV1"]
    arc_starts = sources["PositionRouteCandidateArcSampleStartsV1"]
    arc_counts = sources["PositionRouteCandidateArcSampleCountsV1"]
    lengths_source = sources["PositionRouteCandidateSegmentLengthsV1"]
    start_item = item(starts, "PositionRouteCandidateSegmentStartsV1", "real", loop, "Array Index", 7520, 2240, "segment_start")
    arc_start_item = item(arc_starts, "PositionRouteCandidateArcSampleStartsV1", "int", loop, "Array Index", 7520, 2400, "arc_start")
    arc_count_item = item(arc_counts, "PositionRouteCandidateArcSampleCountsV1", "int", loop, "Array Index", 7520, 2560, "arc_count")
    segment_length_item = item(lengths_source, "PositionRouteCandidateSegmentLengthsV1", "real", loop, "Array Index", 7520, 2720, "segment_length")
    accumulated_seconds = get("PositionRouteCompiledTotalSecondsV1", "real", 7776, 2080)
    accumulated_distance = get("PositionRouteCompiledTotalDistanceV1", "real", 7776, 2240)
    accumulated_samples = get("PositionRouteResultSegmentIndexV1", "int", 7776, 2400)
    end_index_sum = math("Add_IntInt", arc_start_item, "Output", arc_count_item, "Output", 7776, 2720, "int")
    end_index = math("Subtract_IntInt", end_index_sum, "ReturnValue", None, "1", 8000, 2720, "int")
    bounds_conditions = (
        compare("BooleanAND", stage, "PositionRouteStageValidV1", None, "true", 8000, 2080, "bool"),
        compare("EqualEqual_DoubleDouble", start_item, "Output", accumulated_seconds, "PositionRouteCompiledTotalSecondsV1", 8000, 2240, "real"),
        b.finite(loop, "Array Element", 8000, 2400),
        compare("Greater_DoubleDouble", loop, "Array Element", None, "0.0", 8000, 2560, "real"),
        compare("EqualEqual_IntInt", arc_start_item, "Output", accumulated_samples, "PositionRouteResultSegmentIndexV1", 8224, 2080, "int"),
        compare("GreaterEqual_IntInt", arc_count_item, "Output", None, "2", 8224, 2240, "int"),
        b.finite(segment_length_item, "Output", 8224, 2400),
        compare("GreaterEqual_DoubleDouble", segment_length_item, "Output", None, "0.0", 8224, 2560, "real"),
        compare("Less_IntInt", end_index, "ReturnValue", flat_u_count, "ReturnValue", 8224, 2720, "int"),
    )
    bounds_valid = and_all(list(bounds_conditions), 8448, 2880)
    bounds_guard = b.add("bounds_guard", "branch", 10112, 2560)
    bp.connect(loop, "LoopBody", bounds_guard, "execute")
    bp.connect(bounds_valid, "ReturnValue", bounds_guard, "Condition")
    bounds_reject = set_value("PositionRouteStageValidV1", "bool", 10336, 3040, "false")
    bp.connect(bounds_guard, "else", bounds_reject, "execute")

    arc_us = sources["PositionRouteCandidateArcUsV1"]
    arc_distances = sources["PositionRouteCandidateArcDistancesV1"]
    u0 = item(arc_us, "PositionRouteCandidateArcUsV1", "real", arc_start_item, "Output", 10336, 2080, "u0")
    u1 = item(arc_us, "PositionRouteCandidateArcUsV1", "real", end_index, "ReturnValue", 10336, 2240, "u1")
    d0 = item(arc_distances, "PositionRouteCandidateArcDistancesV1", "real", arc_start_item, "Output", 10336, 2400, "d0")
    d1 = item(arc_distances, "PositionRouteCandidateArcDistancesV1", "real", end_index, "ReturnValue", 10336, 2560, "d1")
    endpoint_valid = and_all([
        compare("EqualEqual_DoubleDouble", u0, "Output", None, "0.0", 10560, 2080, "real"),
        compare("EqualEqual_DoubleDouble", u1, "Output", None, "1.0", 10560, 2240, "real"),
        compare("EqualEqual_DoubleDouble", d0, "Output", None, "0.0", 10560, 2400, "real"),
        compare("EqualEqual_DoubleDouble", d1, "Output", segment_length_item, "Output", 10560, 2560, "real"),
    ], 10784, 2720)
    endpoint_guard = b.add("endpoint_guard", "branch", 11360, 2560)
    bp.connect(bounds_guard, "then", endpoint_guard, "execute")
    bp.connect(endpoint_valid, "ReturnValue", endpoint_guard, "Condition")
    endpoint_reject = set_value("PositionRouteStageValidV1", "bool", 11584, 3040, "false")
    bp.connect(endpoint_guard, "else", endpoint_reject, "execute")

    seconds_sum = math("Add_DoubleDouble", accumulated_seconds, "PositionRouteCompiledTotalSecondsV1", loop, "Array Element", 11584, 2080, "real")
    distance_sum = math("Add_DoubleDouble", accumulated_distance, "PositionRouteCompiledTotalDistanceV1", segment_length_item, "Output", 11584, 2240, "real")
    sample_sum = math("Add_IntInt", accumulated_samples, "PositionRouteResultSegmentIndexV1", arc_count_item, "Output", 11584, 2400, "int")
    advance_seconds = set_value("PositionRouteCompiledTotalSecondsV1", "real", 11808, 2560)
    advance_distance = set_value("PositionRouteCompiledTotalDistanceV1", "real", 12032, 2560)
    advance_samples = set_value("PositionRouteResultSegmentIndexV1", "int", 12256, 2560)
    bp.connect(seconds_sum, "ReturnValue", advance_seconds, "PositionRouteCompiledTotalSecondsV1")
    bp.connect(distance_sum, "ReturnValue", advance_distance, "PositionRouteCompiledTotalDistanceV1")
    bp.connect(sample_sum, "ReturnValue", advance_samples, "PositionRouteResultSegmentIndexV1")
    bp.connect(endpoint_guard, "then", advance_seconds, "execute")
    bp.connect(advance_seconds, "then", advance_distance, "execute")
    bp.connect(advance_distance, "then", advance_samples, "execute")

    final_conditions = [
        compare("BooleanAND", stage, "PositionRouteStageValidV1", None, "true", 12480, 2080, "bool"),
        compare("EqualEqual_DoubleDouble", accumulated_seconds, "PositionRouteCompiledTotalSecondsV1", candidate_seconds, "PositionRouteCandidateTotalSecondsV1", 12480, 2240, "real"),
        compare("EqualEqual_DoubleDouble", accumulated_distance, "PositionRouteCompiledTotalDistanceV1", candidate_distance, "PositionRouteCandidateTotalDistanceV1", 12480, 2400, "real"),
        compare("EqualEqual_IntInt", accumulated_samples, "PositionRouteResultSegmentIndexV1", flat_u_count, "ReturnValue", 12480, 2560, "int"),
    ]
    final_valid = and_all(final_conditions, 12704, 2720)
    final_guard = b.add("final_guard", "branch", 13280, 2560)
    bp.connect(loop, "Completed", final_guard, "execute")
    bp.connect(final_valid, "ReturnValue", final_guard, "Condition")

    reset_sample_result = set_value("PositionRouteResultSegmentIndexV1", "int", 13504, 2240, "-1")
    bp.connect(final_guard, "then", reset_sample_result, "execute")
    publish = []
    for index, (source_name, target_name, value) in enumerate(mappings):
        node = set_value(target_name, value, 13728 + index * 224, 2240, array=True)
        bp.connect(sources[source_name], source_name, node, target_name)
        publish.append(node)
    bp.connect(reset_sample_result, "then", publish[0], "execute")
    for left, right in zip(publish, publish[1:]):
        bp.connect(left, "then", right, "execute")
    accept = set_value("PositionRouteCompileValidV1", "bool", 13728 + len(publish) * 224, 2240, "true")
    bp.connect(publish[-1], "then", accept, "execute")

    fail_seconds = set_value("PositionRouteCompiledTotalSecondsV1", "real", 13504, 2880, "0.0")
    fail_distance = set_value("PositionRouteCompiledTotalDistanceV1", "real", 13728, 2880, "0.0")
    fail_sample = set_value("PositionRouteResultSegmentIndexV1", "int", 13952, 2880, "-1")
    fail_stage = set_value("PositionRouteStageValidV1", "bool", 14176, 2880, "false")
    bp.connect(final_guard, "else", fail_seconds, "execute")
    bp.connect(fail_seconds, "then", fail_distance, "execute")
    bp.connect(fail_distance, "then", fail_sample, "execute")
    bp.connect(fail_sample, "then", fail_stage, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
