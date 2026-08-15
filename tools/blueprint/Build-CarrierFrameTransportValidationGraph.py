"""Build fail-closed carrier-frame staged-input validation."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateCarrierFrameTransportInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_validation_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
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
        return re.sub(r"PinType.ContainerType=(?:None|Array)", f"PinType.ContainerType={'Array' if array else 'None'}", line, 1)

    node.mutate_pin(pin_name, mutate)


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
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    vector_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    runtime = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    forms.update(
        foreach=bp.find_block(raw, r"K2Node_MacroInstance"),
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        break_vector=bp.find_block(vector_forms, r'MemberName="BreakVector"'),
        int_to_double=bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        item=bp.find_block(runtime, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        block = forms[form]
        match = bp.BLOCK_RE.match(block)
        if match is None:
            raise RuntimeError(form)
        node_class = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(node_class, 0)
        builder.serial[node_class] = index + 1
        node = bp.Node.clone(key, block, f"{node_class}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def variable(node, name: str, kind: str, array: bool = False):
        scalar.retarget_variable(node, name, "real" if kind in ("int", "vector") else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_value(name: str, kind: str, x: int, y: int, default=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def compare(member: str, left, left_pin: str, x: int, y: int, *, kind="real", right=None, right_pin=None, default=None):
        node = builder.add(f"compare_{member}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def and_all(conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (other, other_pin) in enumerate(conditions[1:]):
            node = builder.add(f"and_{index}_{len(builder.nodes)}", "compare", x + index * 224, y)
            scalar.retarget_function(node, "BooleanAND")
            for pin in ("A", "B", "ReturnValue"):
                pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A")
            bp.connect(other, other_pin, node, "B")
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    def int_math(member: str, source, source_pin: str, amount: str, x: int, y: int):
        node = builder.add(f"{member}_{len(builder.nodes)}", "math", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, "int")
        bp.connect(source, source_pin, node, "A")
        scalar.set_default(node, "B", amount)
        return node

    def convert_int(source, source_pin: str, x: int, y: int):
        node = add_form(f"convert_{len(builder.nodes)}", "int_to_double", x, y)
        pin_kind(node, "InInt", "int")
        pin_kind(node, "ReturnValue", "real")
        bp.connect(source, source_pin, node, "InInt")
        return node

    def multiply(left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = builder.math("Multiply_DoubleDouble", x, y)
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def foreach(source, source_pin: str, x: int, y: int):
        node = add_form(f"foreach_{len(builder.nodes)}", "foreach", x, y)
        pin_kind(node, "Array", "vector", True)
        pin_kind(node, "Array Element", "vector")
        pin_kind(node, "Array Index", "int")
        bp.connect(source, source_pin, node, "Array")
        return node

    positions = get("CarrierFrameInputPositionsV1", "vector", 0, 0, True)
    total = get("CarrierFrameInputTotalSecondsV1", "real", 0, 224)
    step = get("CarrierFrameInputFixedStepSecondsV1", "real", 0, 448)
    staged = get("CarrierFrameStageValidV1", "bool", 0, 672)
    length = add_form("position_count", "length", 320, 0)
    pin_kind(length, "TargetArray", "vector", True)
    pin_kind(length, "ReturnValue", "int")
    bp.connect(positions, "CarrierFrameInputPositionsV1", length, "TargetArray")

    conditions = [
        (staged, "CarrierFrameStageValidV1"),
        (compare("GreaterEqual_IntInt", length, "ReturnValue", 640, 0, kind="int", default="2"), "ReturnValue"),
        (compare("LessEqual_IntInt", length, "ReturnValue", 640, 128, kind="int", default="65536"), "ReturnValue"),
        (scalar.Builder.finite(builder, total, "CarrierFrameInputTotalSecondsV1", 640, 256), "ReturnValue"),
        (compare("Greater_DoubleDouble", total, "CarrierFrameInputTotalSecondsV1", 1088, 256, default="0.0"), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", total, "CarrierFrameInputTotalSecondsV1", 1312, 256, default="3600.0"), "ReturnValue"),
        (scalar.Builder.finite(builder, step, "CarrierFrameInputFixedStepSecondsV1", 640, 512), "ReturnValue"),
        (compare("GreaterEqual_DoubleDouble", step, "CarrierFrameInputFixedStepSecondsV1", 1088, 512, default="0.004166666666666667"), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", step, "CarrierFrameInputFixedStepSecondsV1", 1312, 512, default="0.5"), "ReturnValue"),
    ]
    minus_two = int_math("Subtract_IntInt", length, "ReturnValue", "2", 640, 768)
    minus_one = int_math("Subtract_IntInt", length, "ReturnValue", "1", 640, 896)
    lower_index = convert_int(minus_two, "ReturnValue", 896, 768)
    upper_index = convert_int(minus_one, "ReturnValue", 896, 896)
    lower_time = multiply(lower_index, "ReturnValue", step, "CarrierFrameInputFixedStepSecondsV1", 1152, 768)
    upper_time = multiply(upper_index, "ReturnValue", step, "CarrierFrameInputFixedStepSecondsV1", 1152, 896)
    conditions.extend((
        (compare("Less_DoubleDouble", lower_time, "ReturnValue", 1408, 768, right=total, right_pin="CarrierFrameInputTotalSecondsV1"), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", total, "CarrierFrameInputTotalSecondsV1", 1408, 896, right=upper_time, right_pin="ReturnValue"), "ReturnValue"),
    ))
    shape_valid, shape_valid_pin = and_all(conditions, 1792, 1152)

    invalidate = set_value("CarrierFrameScratchValidV1", "bool", 256, 1536, "false")
    clear_failure = set_value("CarrierFrameFailureCodeV1", "string", 576, 1536, "")
    shape_guard = builder.add("shape_guard", "branch", 3200, 1536)
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", shape_guard, "execute")
    bp.connect(shape_valid, shape_valid_pin, shape_guard, "Condition")
    shape_failure = set_value("CarrierFrameFailureCodeV1", "string", 3456, 1792, "input_invalid")
    bp.connect(shape_guard, "else", shape_failure, "execute")

    assume_finite = set_value("CarrierFrameScratchValidV1", "bool", 3456, 1536, "true")
    finite_loop = foreach(positions, "CarrierFrameInputPositionsV1", 3776, 1536)
    bp.connect(shape_guard, "then", assume_finite, "execute")
    bp.connect(assume_finite, "then", finite_loop, "Exec")
    split = add_form("break_position", "break_vector", 4064, 1216)
    pin_kind(split, "InVec", "vector")
    for pin in ("X", "Y", "Z"):
        pin_kind(split, pin, "real")
    bp.connect(finite_loop, "Array Element", split, "InVec")
    finite_conditions = [
        (scalar.Builder.finite(builder, split, pin, 4352, 1120 + index * 160), "ReturnValue")
        for index, pin in enumerate(("X", "Y", "Z"))
    ]
    finite_valid, finite_valid_pin = and_all(finite_conditions, 5024, 1280)
    finite_guard = builder.add("finite_guard", "branch", 5472, 1536)
    bp.connect(finite_loop, "LoopBody", finite_guard, "execute")
    bp.connect(finite_valid, finite_valid_pin, finite_guard, "Condition")
    finite_reject = set_value("CarrierFrameScratchValidV1", "bool", 5728, 1760, "false")
    finite_failure = set_value("CarrierFrameFailureCodeV1", "string", 6048, 1760, "position_not_finite")
    bp.connect(finite_guard, "else", finite_reject, "execute")
    bp.connect(finite_reject, "then", finite_failure, "execute")

    finite_result = get("CarrierFrameScratchValidV1", "bool", 5728, 1216)
    finite_done = builder.add("finite_done", "branch", 6368, 1536)
    bp.connect(finite_loop, "Completed", finite_done, "execute")
    bp.connect(finite_result, "CarrierFrameScratchValidV1", finite_done, "Condition")

    first = add_form("first_position", "item", 6368, 1024)
    pin_kind(first, "Array", "vector", True)
    pin_kind(first, "Output", "vector")
    scalar.set_default(first, "Dimension 1", "0")
    bp.connect(positions, "CarrierFrameInputPositionsV1", first, "Array")
    store_first = set_value("CarrierFrameScratchForwardV1", "vector", 6624, 1536)
    bp.connect(first, "Output", store_first, "CarrierFrameScratchForwardV1")
    reset_direction = set_value("CarrierFrameScratchValidV1", "bool", 7008, 1536, "false")
    direction_loop = foreach(positions, "CarrierFrameInputPositionsV1", 7328, 1536)
    bp.connect(finite_done, "then", store_first, "execute")
    bp.connect(store_first, "then", reset_direction, "execute")
    bp.connect(reset_direction, "then", direction_loop, "Exec")

    first_value = get("CarrierFrameScratchForwardV1", "vector", 7328, 1120)
    delta = builder.add("direction_delta", "compare", 7616, 1184)
    scalar.retarget_function(delta, "Subtract_VectorVector")
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(delta, pin, "vector")
    bp.connect(direction_loop, "Array Element", delta, "A")
    bp.connect(first_value, "CarrierFrameScratchForwardV1", delta, "B")
    squared = builder.add("direction_squared", "compare", 7904, 1184)
    scalar.retarget_function(squared, "Dot_VectorVector")
    pin_kind(squared, "A", "vector")
    pin_kind(squared, "B", "vector")
    pin_kind(squared, "ReturnValue", "real")
    bp.connect(delta, "ReturnValue", squared, "A")
    bp.connect(delta, "ReturnValue", squared, "B")
    nonzero = compare("Greater_DoubleDouble", squared, "ReturnValue", 8192, 1184, default="1e-18")
    direction_guard = builder.add("direction_guard", "branch", 8448, 1536)
    bp.connect(direction_loop, "LoopBody", direction_guard, "execute")
    bp.connect(nonzero, "ReturnValue", direction_guard, "Condition")
    found = set_value("CarrierFrameScratchValidV1", "bool", 8704, 1536, "true")
    bp.connect(direction_guard, "then", found, "execute")

    direction_result = get("CarrierFrameScratchValidV1", "bool", 8704, 1184)
    direction_done = builder.add("direction_done", "branch", 9024, 1536)
    bp.connect(direction_loop, "Completed", direction_done, "execute")
    bp.connect(direction_result, "CarrierFrameScratchValidV1", direction_done, "Condition")
    success_clear = set_value("CarrierFrameFailureCodeV1", "string", 9280, 1536, "")
    publish = set_value("CarrierFrameScratchValidV1", "bool", 9600, 1536, "true")
    bp.connect(direction_done, "then", success_clear, "execute")
    bp.connect(success_clear, "then", publish, "execute")
    direction_failure = set_value("CarrierFrameFailureCodeV1", "string", 9280, 1792, "path_has_no_direction")
    bp.connect(direction_done, "else", direction_failure, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text)
            for node in builder.nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
