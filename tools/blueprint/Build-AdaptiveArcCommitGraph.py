"""Build atomic publication of a completed adaptive arc-table candidate."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitAdaptiveArcBuildV1"
WORK = (
    ("TrajectoryArcBuildWorkU0V1", "real"),
    ("TrajectoryArcBuildWorkU1V1", "real"),
    ("TrajectoryArcBuildWorkP0V1", "vector"),
    ("TrajectoryArcBuildWorkP1V1", "vector"),
    ("TrajectoryArcBuildWorkDepthV1", "int"),
)
CANDIDATE = (
    ("TrajectoryArcBuildCandidateUsV1", "real"),
    ("TrajectoryArcBuildCandidatePositionsV1", "vector"),
    ("TrajectoryArcBuildCandidateDistancesV1", "real"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_arc_commit_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin: str, value: str, array: bool = False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[value]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


def variable(scalar, node, name: str, value: str, array: bool = False):
    scalar.retarget_variable(node, name, "vector" if value == "vector" else ("real" if value == "int" else value))
    kind(node, name, value, array)
    if "Output_Get" in node.pins:
        kind(node, "Output_Get", value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    builder = scalar.Builder(bp, forms, FUNCTION)

    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    foreach_form = bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')
    item_form = bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem")
    clear_form = bp.find_block(reset, r'MemberName="Array_Clear"')

    def add(key, form, x, y):
        match = bp.BLOCK_RE.match(form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def base_kind(value):
        return "vector" if value == "vector" else ("real" if value == "int" else value)

    def get(name, value, x, y, array=False):
        node = builder.get(name, base_kind(value), x, y)
        variable(scalar, node, name, value, array)
        return node

    def setv(name, value, x, y, default=None, array=False):
        node = builder.set(name, base_kind(value), x, y, default)
        variable(scalar, node, name, value, array)
        return node

    def length(source, source_pin, value, x, y, key):
        node = add(key, length_form, x, y)
        kind(node, "TargetArray", value, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin, index, index_pin, value, x, y, key):
        node = add(key, item_form, x, y)
        kind(node, "Array", value, True)
        kind(node, "Output", value)
        bp.connect(source, source_pin, node, "Array")
        if index is None:
            scalar.set_default(node, "Dimension 1", index_pin)
        else:
            bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def compare(member, left, left_pin, right, right_pin, x, y, value):
        node = builder.add(f"compare_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        kind(node, "A", value)
        kind(node, "B", value)
        kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def and_(left, right, x, y):
        return compare("BooleanAND", left, "ReturnValue", right, "ReturnValue", x, y, "bool")

    def math(member, left, left_pin, right, right_pin, x, y, value):
        node = builder.math(member, x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            kind(node, pin, value)
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def combine(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = and_(current, condition, x + index * 208, y)
        return current

    built_us = get("TrajectoryArcBuiltUsV1", "real", 0, 0, True)
    built_distances = get("TrajectoryArcBuiltDistancesV1", "real", 0, 160, True)
    clear_us = add("clear_built_us", clear_form, 256, 1760)
    clear_distances = add("clear_built_distances", clear_form, 512, 1760)
    kind(clear_us, "TargetArray", "real", True)
    kind(clear_distances, "TargetArray", "real", True)
    bp.connect(built_us, "TrajectoryArcBuiltUsV1", clear_us, "TargetArray")
    bp.connect(built_distances, "TrajectoryArcBuiltDistancesV1", clear_distances, "TargetArray")
    reset_length = setv("TrajectoryArcBuiltLengthV1", "real", 768, 1760, "0.0")
    reset_valid = setv("TrajectoryArcBuildValidV1", "bool", 1024, 1760, "false")
    bp.connect(builder.entry, "then", clear_us, "execute")
    bp.connect(clear_us, "then", clear_distances, "execute")
    bp.connect(clear_distances, "then", reset_length, "execute")
    bp.connect(reset_length, "then", reset_valid, "execute")

    work = {name: get(name, value, 0, 480 + index * 144, True) for index, (name, value) in enumerate(WORK)}
    candidates = {name: get(name, value, 0, 1280 + index * 144, True) for index, (name, value) in enumerate(CANDIDATE)}
    work_lengths = [length(work[name], name, value, 256 + index * 208, 480, f"work_length_{index}") for index, (name, value) in enumerate(WORK)]
    candidate_lengths = [length(candidates[name], name, value, 256 + (index + 5) * 208, 480, f"candidate_length_{index}") for index, (name, value) in enumerate(CANDIDATE)]
    u_length, position_length, distance_length = candidate_lengths
    stage = get("TrajectoryArcBuildStageValidV1", "bool", 256, 960)
    stage_wrap = builder.add("stage_wrap", "compare", 464, 960)
    scalar.retarget_function(stage_wrap, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"):
        kind(stage_wrap, pin, "bool")
    bp.connect(stage, "TrajectoryArcBuildStageValidV1", stage_wrap, "A")
    scalar.set_default(stage_wrap, "B", "true")
    candidate_length = get("TrajectoryArcBuildCandidateLengthV1", "real", 256, 1120)

    conditions = [stage_wrap]
    conditions.extend(compare("EqualEqual_IntInt", node, "ReturnValue", None, "0", 464 + index * 208, 1120, "int") for index, node in enumerate(work_lengths))
    conditions.extend((
        compare("GreaterEqual_IntInt", u_length, "ReturnValue", None, "2", 1504, 1120, "int"),
        compare("EqualEqual_IntInt", position_length, "ReturnValue", u_length, "ReturnValue", 1712, 1120, "int"),
        compare("EqualEqual_IntInt", distance_length, "ReturnValue", u_length, "ReturnValue", 1920, 1120, "int"),
        builder.finite(candidate_length, "TrajectoryArcBuildCandidateLengthV1", 2128, 1120),
        compare("GreaterEqual_DoubleDouble", candidate_length, "TrajectoryArcBuildCandidateLengthV1", None, "0.0", 2336, 1120, "real"),
    ))
    shape = combine(conditions, 2560, 1120)
    shape_branch = builder.add("shape_branch", "branch", 4640, 1760)
    bp.connect(reset_valid, "then", shape_branch, "execute")
    bp.connect(shape, "ReturnValue", shape_branch, "Condition")
    shape_fail = setv("TrajectoryArcBuildStageValidV1", "bool", 4864, 2000, "false")
    bp.connect(shape_branch, "else", shape_fail, "execute")

    last_index = math("Subtract_IntInt", u_length, "ReturnValue", None, "1", 4640, 720, "int")
    candidate_us = candidates["TrajectoryArcBuildCandidateUsV1"]
    candidate_distances = candidates["TrajectoryArcBuildCandidateDistancesV1"]
    first_u = item(candidate_us, "TrajectoryArcBuildCandidateUsV1", None, "0", "real", 4864, 560, "first_u")
    first_distance = item(candidate_distances, "TrajectoryArcBuildCandidateDistancesV1", None, "0", "real", 4864, 720, "first_distance")
    last_u = item(candidate_us, "TrajectoryArcBuildCandidateUsV1", last_index, "ReturnValue", "real", 4864, 880, "last_u")
    last_distance = item(candidate_distances, "TrajectoryArcBuildCandidateDistancesV1", last_index, "ReturnValue", "real", 4864, 1040, "last_distance")
    endpoints = combine((
        compare("EqualEqual_DoubleDouble", first_u, "Output", None, "0.0", 5120, 560, "real"),
        compare("EqualEqual_DoubleDouble", first_distance, "Output", None, "0.0", 5120, 720, "real"),
        compare("EqualEqual_DoubleDouble", last_u, "Output", None, "1.0", 5120, 880, "real"),
        compare("EqualEqual_DoubleDouble", last_distance, "Output", candidate_length, "TrajectoryArcBuildCandidateLengthV1", 5120, 1040, "real"),
    ), 5344, 800)
    endpoint_branch = builder.add("endpoint_branch", "branch", 6016, 1760)
    bp.connect(shape_branch, "then", endpoint_branch, "execute")
    bp.connect(endpoints, "ReturnValue", endpoint_branch, "Condition")
    endpoint_fail = setv("TrajectoryArcBuildStageValidV1", "bool", 6240, 2000, "false")
    bp.connect(endpoint_branch, "else", endpoint_fail, "execute")

    loop = add("candidate_loop", foreach_form, 6240, 2400)
    kind(loop, "Array", "real", True)
    kind(loop, "Array Element", "real")
    bp.connect(candidate_us, "TrajectoryArcBuildCandidateUsV1", loop, "Array")
    bp.connect(endpoint_branch, "then", loop, "Exec")
    not_first = compare("Greater_IntInt", loop, "Array Index", None, "0", 6496, 2240, "int")
    item_branch = builder.add("item_branch", "branch", 6752, 2400)
    bp.connect(loop, "LoopBody", item_branch, "execute")
    bp.connect(not_first, "ReturnValue", item_branch, "Condition")
    previous_index = math("Subtract_IntInt", loop, "Array Index", None, "1", 6496, 2640, "int")
    current_distance = item(candidate_distances, "TrajectoryArcBuildCandidateDistancesV1", loop, "Array Index", "real", 6752, 2800, "current_distance")
    previous_u = item(candidate_us, "TrajectoryArcBuildCandidateUsV1", previous_index, "ReturnValue", "real", 6752, 2960, "previous_u")
    previous_distance = item(candidate_distances, "TrajectoryArcBuildCandidateDistancesV1", previous_index, "ReturnValue", "real", 6752, 3120, "previous_distance")
    loop_stage = get("TrajectoryArcBuildStageValidV1", "bool", 6752, 3280)
    loop_stage_wrap = builder.add("loop_stage_wrap", "compare", 7008, 3280)
    scalar.retarget_function(loop_stage_wrap, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"):
        kind(loop_stage_wrap, pin, "bool")
    bp.connect(loop_stage, "TrajectoryArcBuildStageValidV1", loop_stage_wrap, "A")
    scalar.set_default(loop_stage_wrap, "B", "true")
    item_valid = combine((
        loop_stage_wrap,
        builder.finite(loop, "Array Element", 7008, 2800),
        builder.finite(current_distance, "Output", 7008, 3040),
        compare("Less_DoubleDouble", previous_u, "Output", loop, "Array Element", 7232, 3360, "real"),
        compare("LessEqual_DoubleDouble", previous_distance, "Output", current_distance, "Output", 7456, 3360, "real"),
    ), 7680, 3200)
    item_guard = builder.add("item_guard", "branch", 8608, 2400)
    bp.connect(item_branch, "then", item_guard, "execute")
    bp.connect(item_valid, "ReturnValue", item_guard, "Condition")
    item_fail = setv("TrajectoryArcBuildStageValidV1", "bool", 8832, 2640, "false")
    bp.connect(item_guard, "else", item_fail, "execute")

    final_stage = get("TrajectoryArcBuildStageValidV1", "bool", 8832, 3200)
    final_stage_wrap = builder.add("final_stage_wrap", "compare", 9088, 3200)
    scalar.retarget_function(final_stage_wrap, "BooleanAND")
    for pin in ("A", "B", "ReturnValue"):
        kind(final_stage_wrap, pin, "bool")
    bp.connect(final_stage, "TrajectoryArcBuildStageValidV1", final_stage_wrap, "A")
    scalar.set_default(final_stage_wrap, "B", "true")
    final_branch = builder.add("final_branch", "branch", 9344, 2400)
    bp.connect(loop, "Completed", final_branch, "execute")
    bp.connect(final_stage_wrap, "ReturnValue", final_branch, "Condition")
    final_fail = setv("TrajectoryArcBuildStageValidV1", "bool", 9568, 2800, "false")
    bp.connect(final_branch, "else", final_fail, "execute")

    publish_us = setv("TrajectoryArcBuiltUsV1", "real", 9568, 2240, array=True)
    publish_distances = setv("TrajectoryArcBuiltDistancesV1", "real", 9824, 2240, array=True)
    publish_length = setv("TrajectoryArcBuiltLengthV1", "real", 10080, 2240)
    publish_valid = setv("TrajectoryArcBuildValidV1", "bool", 10336, 2240, "true")
    bp.connect(final_branch, "then", publish_us, "execute")
    bp.connect(candidate_us, "TrajectoryArcBuildCandidateUsV1", publish_us, "TrajectoryArcBuiltUsV1")
    bp.connect(publish_us, "then", publish_distances, "execute")
    bp.connect(candidate_distances, "TrajectoryArcBuildCandidateDistancesV1", publish_distances, "TrajectoryArcBuiltDistancesV1")
    bp.connect(publish_distances, "then", publish_length, "execute")
    bp.connect(candidate_length, "TrajectoryArcBuildCandidateLengthV1", publish_length, "TrajectoryArcBuiltLengthV1")
    bp.connect(publish_length, "then", publish_valid, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
