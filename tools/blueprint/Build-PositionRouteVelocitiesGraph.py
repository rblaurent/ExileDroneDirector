"""Build deterministic, component-wise monotone waypoint velocities."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ComputePositionRouteVelocitiesV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_position_velocity_base", path)
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
    raw = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-position-route-candidate-v1.eddgraph")
    vector = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    forms.update({
        "foreach": bp.find_block(raw, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "array_item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "break_vector": bp.find_block(vector, r'MemberName="BreakVector"'),
        "make_vector": bp.find_block(marker, r'MemberName="MakeVector"'),
        "select_float": bp.find_block(speed, r'MemberName="SelectFloat"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get_array(name: str, kind: str, x: int, y: int):
        node = b.get(name, kind, x, y)
        variable(node, name, kind, True)
        return node

    def add_form(key: str, form: str, x: int, y: int):
        return b.add(key, form, x, y)

    def integer(member: str, x: int, y: int, b_default: str | None = None):
        node = b.math("Subtract_DoubleDouble", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, "int")
        if b_default is not None:
            scalar.set_default(node, "B", b_default)
        return node

    def compare(member: str, left, left_pin: str, right, right_pin: str | None, x: int, y: int, kind: str = "real", default_b: str | None = None):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default_b is not None:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(member: str, left, right, x: int, y: int):
        return compare(member, left, "ReturnValue", right, "ReturnValue", x, y, "bool")

    def array_item(source, source_pin: str, kind: str, index, index_pin: str, x: int, y: int, key: str):
        node = add_form(key, "array_item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def array_add(candidate, value, value_pin: str, exec_source, exec_pin: str, x: int, y: int, key: str):
        node = add_form(key, "array_add", x, y)
        pin_kind(node, "TargetArray", "vector", True)
        pin_kind(node, "NewItem", "vector")
        bp.connect(candidate, "PositionRouteCandidateWaypointVelocitiesV1", node, "TargetArray")
        if value is not None:
            bp.connect(value, value_pin, node, "NewItem")
        else:
            scalar.set_default(node, "NewItem", "0, 0, 0")
        bp.connect(exec_source, exec_pin, node, "execute")
        return node

    def math(member: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.math(member, x, y)
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def select(a_node, a_pin: str, b_node, b_pin: str | None, condition, x: int, y: int, key: str):
        node = add_form(key, "select_float", x, y)
        bp.connect(a_node, a_pin, node, "A")
        if b_node is not None:
            bp.connect(b_node, b_pin, node, "B")
        else:
            scalar.set_default(node, "B", "0.0")
        bp.connect(condition, "ReturnValue", node, "bPickA")
        return node

    positions = get_array("PositionRouteInputWaypointPositionsV1", "vector", 0, 128)
    durations = get_array("PositionRouteInputDurationsV1", "real", 0, 384)
    curves = get_array("PositionRouteInputSpatialCurveTypesV1", "string", 0, 640)
    candidate = get_array("PositionRouteCandidateWaypointVelocitiesV1", "vector", 0, 896)
    stage = b.get("PositionRouteStageValidV1", "bool", 256, 1152)

    clear = add_form("clear", "array_clear", 256, 1440)
    pin_kind(clear, "TargetArray", "vector", True)
    bp.connect(candidate, "PositionRouteCandidateWaypointVelocitiesV1", clear, "TargetArray")
    bp.connect(b.entry, "then", clear, "execute")
    outer = b.add("outer", "branch", 512, 1440)
    bp.connect(clear, "then", outer, "execute")
    bp.connect(stage, "PositionRouteStageValidV1", outer, "Condition")

    length = add_form("length", "array_length", 512, 128)
    pin_kind(length, "TargetArray", "vector", True)
    bp.connect(positions, "PositionRouteInputWaypointPositionsV1", length, "TargetArray")
    last = integer("Subtract_IntInt", 768, 128, "1")
    bp.connect(length, "ReturnValue", last, "A")
    loop = add_form("loop", "foreach", 768, 448)
    pin_kind(loop, "Array", "vector", True)
    pin_kind(loop, "Array Element", "vector")
    bp.connect(positions, "PositionRouteInputWaypointPositionsV1", loop, "Array")
    bp.connect(outer, "then", loop, "Exec")
    inner = b.add("inner", "branch", 1024, 1440)
    bp.connect(loop, "LoopBody", inner, "execute")
    bp.connect(stage, "PositionRouteStageValidV1", inner, "Condition")

    first = compare("EqualEqual_IntInt", loop, "Array Index", None, None, 1280, 448, "int", "0")
    is_last = compare("EqualEqual_IntInt", loop, "Array Index", last, "ReturnValue", 1280, 640, "int")
    endpoint = boolean("BooleanOR", first, is_last, 1536, 544)
    endpoint_branch = b.add("endpoint_branch", "branch", 1792, 1440)
    bp.connect(inner, "then", endpoint_branch, "execute")
    bp.connect(endpoint, "ReturnValue", endpoint_branch, "Condition")
    array_add(candidate, None, "", endpoint_branch, "then", 2048, 1280, "endpoint_zero")

    previous_index = integer("Subtract_IntInt", 1536, 128, "1")
    bp.connect(loop, "Array Index", previous_index, "A")
    next_index = integer("Add_IntInt", 1792, 128, "1")
    bp.connect(loop, "Array Index", next_index, "A")

    previous_position = array_item(positions, "PositionRouteInputWaypointPositionsV1", "vector", previous_index, "ReturnValue", 2048, 128, "previous_position")
    next_position = array_item(positions, "PositionRouteInputWaypointPositionsV1", "vector", next_index, "ReturnValue", 2048, 320, "next_position")
    previous_duration = array_item(durations, "PositionRouteInputDurationsV1", "real", previous_index, "ReturnValue", 2048, 512, "previous_duration")
    next_duration = array_item(durations, "PositionRouteInputDurationsV1", "real", loop, "Array Index", 2048, 704, "next_duration")
    previous_curve = array_item(curves, "PositionRouteInputSpatialCurveTypesV1", "string", previous_index, "ReturnValue", 2048, 896, "previous_curve")
    next_curve = array_item(curves, "PositionRouteInputSpatialCurveTypesV1", "string", loop, "Array Index", 2048, 1088, "next_curve")

    previous_auto = b.equal_string(2304, 896, "auto_cinematic")
    next_auto = b.equal_string(2304, 1088, "auto_cinematic")
    bp.connect(previous_curve, "Output", previous_auto, "A")
    bp.connect(next_curve, "Output", next_auto, "A")
    both_auto = boolean("BooleanAND", previous_auto, next_auto, 2560, 992)
    mode_branch = b.add("mode_branch", "branch", 2816, 1440)
    bp.connect(endpoint_branch, "else", mode_branch, "execute")
    bp.connect(both_auto, "ReturnValue", mode_branch, "Condition")
    array_add(candidate, None, "", mode_branch, "else", 3072, 1600, "mixed_zero")

    previous_break = add_form("previous_break", "break_vector", 2560, 128)
    current_break = add_form("current_break", "break_vector", 2560, 320)
    next_break = add_form("next_break", "break_vector", 2560, 512)
    bp.connect(previous_position, "Output", previous_break, "InVec")
    bp.connect(loop, "Array Element", current_break, "InVec")
    bp.connect(next_position, "Output", next_break, "InVec")
    result = add_form("result", "make_vector", 6144, 768)

    for axis_index, axis in enumerate("XYZ"):
        y = 128 + axis_index * 512
        incoming = math("Subtract_DoubleDouble", current_break, axis, previous_break, axis, 3072, y)
        outgoing = math("Subtract_DoubleDouble", next_break, axis, current_break, axis, 3072, y + 96)
        left_rate = math("Divide_DoubleDouble", incoming, "ReturnValue", previous_duration, "Output", 3328, y)
        right_rate = math("Divide_DoubleDouble", outgoing, "ReturnValue", next_duration, "Output", 3328, y + 96)
        left_positive = compare("Greater_DoubleDouble", left_rate, "ReturnValue", None, None, 3584, y, "real", "0.0")
        right_positive = compare("Greater_DoubleDouble", right_rate, "ReturnValue", None, None, 3584, y + 96, "real", "0.0")
        both_positive = boolean("BooleanAND", left_positive, right_positive, 3840, y)
        left_negative = compare("Less_DoubleDouble", left_rate, "ReturnValue", None, None, 3584, y + 192, "real", "0.0")
        right_negative = compare("Less_DoubleDouble", right_rate, "ReturnValue", None, None, 3584, y + 288, "real", "0.0")
        both_negative = boolean("BooleanAND", left_negative, right_negative, 3840, y + 240)
        left_is_min = compare("LessEqual_DoubleDouble", left_rate, "ReturnValue", right_rate, "ReturnValue", 4096, y, "real")
        positive_min = select(left_rate, "ReturnValue", right_rate, "ReturnValue", left_is_min, 4352, y, f"{axis}_positive_min")
        left_is_max = compare("GreaterEqual_DoubleDouble", left_rate, "ReturnValue", right_rate, "ReturnValue", 4096, y + 192, "real")
        negative_max = select(left_rate, "ReturnValue", right_rate, "ReturnValue", left_is_max, 4352, y + 192, f"{axis}_negative_max")
        negative_or_zero = select(negative_max, "ReturnValue", None, None, both_negative, 4608, y + 192, f"{axis}_negative_or_zero")
        final_axis = select(positive_min, "ReturnValue", negative_or_zero, "ReturnValue", both_positive, 4864, y + 96, f"{axis}_final")
        bp.connect(final_axis, "ReturnValue", result, axis)

    array_add(candidate, result, "ReturnValue", mode_branch, "then", 6400, 1440, "computed_add")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
