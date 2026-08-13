"""Build component compilation and exact source schedule staging."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CompileAirframeSourcePositionProfilesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_components_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin_name: str, value: str, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double"),
        "string": ("string", ""),
    }[value]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    linear = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    forms.update({
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "floor": bp.find_block(linear, r'MemberName="FFloor"'),
        "convert": bp.find_block(linear, r'MemberName="Conv_IntToDouble"'),
        "select": bp.find_block(public_list, r'^Begin Object Class=/Script/BlueprintGraph.K2Node_Select '),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, value, array=False):
        scalar.retarget_variable(node, name, "real" if value == "int" else value)
        kind(node, name, value, array)
        if "Output_Get" in node.pins:
            kind(node, "Output_Get", value)

    def get(name, value, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, value, array)
        return node

    def set_(name, value, x, y, default=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, value)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, value in kinds.items():
            kind(node, pin, value)
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, value="real"):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": value, "B": value, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default_b)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def math_node(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, value="real"):
        node = b.math("Add_DoubleDouble", x, y)
        retarget(node, member, {"A": value, "B": value, "ReturnValue": value})
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default_b)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = compare("BooleanAND", current, "ReturnValue", x + index * 224, y, condition, "ReturnValue", value="bool")
        return current

    def call(member, x, y):
        node = b.add(f"call_{member}_{len(b.nodes)}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1,
            ),
        )
        return node

    stage = get("AirframeSourceStageValidV1", "bool", 0, 0)
    guard = b.add("stage_guard", "branch", 256, 1600)
    bp.connect(b.entry, "then", guard, "execute")
    bp.connect(stage, "AirframeSourceStageValidV1", guard, "Condition")
    invalidate = set_("AirframeSourceStageValidV1", "bool", 512, 1600, "false")
    bp.connect(guard, "then", invalidate, "execute")

    durations = get("PositionRouteInputDurationsV1", "real", 0, 240, True)
    duration_count = b.add("duration_count", "length", 320, 240)
    kind(duration_count, "TargetArray", "real", True)
    bp.connect(durations, "PositionRouteInputDurationsV1", duration_count, "TargetArray")
    set_profile_count = set_("FlightProfileInputSegmentCountV1", "int", 768, 1600)
    bp.connect(duration_count, "ReturnValue", set_profile_count, "FlightProfileInputSegmentCountV1")
    bp.connect(invalidate, "then", set_profile_count, "execute")
    compile_position = call("CompilePositionRouteV1", 1024, 1600)
    bp.connect(set_profile_count, "then", compile_position, "execute")
    position_valid = get("PositionRouteCompileValidV1", "bool", 1024, 480)
    position_branch = b.add("position_branch", "branch", 1280, 1600)
    bp.connect(compile_position, "then", position_branch, "execute")
    bp.connect(position_valid, "PositionRouteCompileValidV1", position_branch, "Condition")
    compile_profiles = call("CompileFlightProfilesV1", 1536, 1600)
    bp.connect(position_branch, "then", compile_profiles, "execute")
    profile_valid = get("FlightProfileCompileValidV1", "bool", 1536, 480)
    profile_branch = b.add("profile_branch", "branch", 1792, 1600)
    bp.connect(compile_profiles, "then", profile_branch, "execute")
    bp.connect(profile_valid, "FlightProfileCompileValidV1", profile_branch, "Condition")

    total = get("PositionRouteCompiledTotalSecondsV1", "real", 0, 720)
    step = get("AirframeSourceInputFixedStepSecondsV1", "real", 0, 880)
    compiled_durations = get("PositionRouteCompiledDurationsV1", "real", 0, 1040, True)
    compiled_ids = get("FlightProfileCompiledIdsV1", "string", 0, 1200, True)
    duration_length = b.add("compiled_duration_count", "length", 320, 1040)
    kind(duration_length, "TargetArray", "real", True)
    bp.connect(compiled_durations, "PositionRouteCompiledDurationsV1", duration_length, "TargetArray")
    id_length = b.add("compiled_profile_count", "length", 320, 1200)
    kind(id_length, "TargetArray", "string", True)
    bp.connect(compiled_ids, "FlightProfileCompiledIdsV1", id_length, "TargetArray")

    quotient = math_node("Divide_DoubleDouble", total, "PositionRouteCompiledTotalSecondsV1", 640, 720, step, "AirframeSourceInputFixedStepSecondsV1")
    floor = b.add("sample_floor", "floor", 896, 720)
    bp.connect(quotient, "ReturnValue", floor, "A")
    floor_double = b.add("sample_floor_double", "convert", 1152, 720)
    bp.connect(floor, "ReturnValue", floor_double, "InInt")
    lower_time = math_node("Multiply_DoubleDouble", floor_double, "ReturnValue", 1408, 720, step, "AirframeSourceInputFixedStepSecondsV1")
    partial = compare("Less_DoubleDouble", lower_time, "ReturnValue", 1664, 720, total, "PositionRouteCompiledTotalSecondsV1")
    exact_count = math_node("Add_IntInt", floor, "ReturnValue", 1152, 560, default_b="1", value="int")
    partial_count = math_node("Add_IntInt", floor, "ReturnValue", 1152, 400, default_b="2", value="int")
    selected_count = b.add("expected_sample_count", "select", 1920, 560)
    for pin in ("Option 0", "Option 1", "ReturnValue"):
        kind(selected_count, pin, "int")
    kind(selected_count, "Index", "bool")
    bp.connect(partial, "ReturnValue", selected_count, "Index")
    bp.connect(exact_count, "ReturnValue", selected_count, "Option 0")
    bp.connect(partial_count, "ReturnValue", selected_count, "Option 1")

    conditions = (
        b.finite(total, "PositionRouteCompiledTotalSecondsV1", 640, 1360),
        compare("Greater_DoubleDouble", total, "PositionRouteCompiledTotalSecondsV1", 1088, 1360, default_b="0.0"),
        compare("LessEqual_DoubleDouble", total, "PositionRouteCompiledTotalSecondsV1", 1312, 1360, default_b="3600.0"),
        compare("EqualEqual_IntInt", duration_length, "ReturnValue", 640, 1520, id_length, "ReturnValue", value="int"),
        compare("GreaterEqual_IntInt", selected_count, "ReturnValue", 2176, 400, default_b="2", value="int"),
        compare("LessEqual_IntInt", selected_count, "ReturnValue", 2176, 560, default_b="65536", value="int"),
    )
    valid = and_all(conditions, 2464, 1360)
    output_branch = b.add("output_branch", "branch", 3808, 1600)
    bp.connect(profile_branch, "then", output_branch, "execute")
    bp.connect(valid, "ReturnValue", output_branch, "Condition")
    set_total = set_("AirframeSourceTotalSecondsV1", "real", 4064, 1600)
    bp.connect(total, "PositionRouteCompiledTotalSecondsV1", set_total, "AirframeSourceTotalSecondsV1")
    bp.connect(output_branch, "then", set_total, "execute")
    set_count = set_("AirframeSourceExpectedSampleCountV1", "int", 4320, 1600)
    bp.connect(selected_count, "ReturnValue", set_count, "AirframeSourceExpectedSampleCountV1")
    bp.connect(set_total, "then", set_count, "execute")
    accept = set_("AirframeSourceStageValidV1", "bool", 4576, 1600, "true")
    bp.connect(set_count, "then", accept, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
