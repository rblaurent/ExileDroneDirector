"""Build fail-closed atomic publication for compiled airframe/gimbal samples."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCompiledAirframePrebakeV1"
CHANNELS = (
    ("BodyQuats", "quat"),
    ("GimbalQuats", "quat"),
    ("BodyAngularRatesDegreesPerSecond", "real"),
    ("GimbalAngularRatesDegreesPerSecond", "real"),
    ("BodyRateLimited", "bool"),
    ("GimbalRateLimited", "bool"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_prebake_commit_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[value]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


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
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-prebake-candidate-v1.eddgraph")
    forms["array_length"] = bp.find_block(edit, r'MemberName="Array_Length"')
    forms["array_clear"] = bp.find_block(reset, r'MemberName="Array_Clear"')
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, value, array=False):
        template = "real" if value == "int" else ("vector" if value == "quat" else value)
        scalar.retarget_variable(node, name, template)
        pin_kind(node, name, value, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", value)

    def get(name, value, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, value, array)
        return node

    def set_(name, value, x, y, default=None, array=False):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, value, array)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def length(source, source_pin, value, x, y):
        node = builder.add(f"length_{len(builder.nodes)}", "array_length", x, y)
        pin_kind(node, "TargetArray", value, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def compare(member, left, left_pin, right, right_pin, value, x, y):
        node = builder.add(f"compare_{len(builder.nodes)}", "compare", x, y)
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

    def and_(left, left_pin, right, right_pin, x, y):
        return compare("BooleanAND", left, left_pin, right, right_pin, "bool", x, y)

    candidate_getters = []
    candidate_lengths = []
    compiled_getters = []
    clears = []
    for index, (suffix, value) in enumerate(CHANNELS):
        candidate_name = f"AirframePrebakeCandidate{suffix}V1"
        compiled_name = f"AirframePrebakeCompiled{suffix}V1"
        candidate = get(candidate_name, value, 0, index * 192, True)
        candidate_getters.append(candidate)
        candidate_lengths.append(length(candidate, candidate_name, value, 320, index * 192))
        compiled = get(compiled_name, value, 0, 1536 + index * 192, True)
        compiled_getters.append(compiled)
        clear = builder.add(f"clear_{compiled_name}", "array_clear", 320 + index * 320, 2688)
        pin_kind(clear, "TargetArray", value, True)
        bp.connect(compiled, compiled_name, clear, "TargetArray")
        clears.append(clear)

    reset_step = set_("AirframePrebakeCompiledFixedStepSecondsV1", "real", 2240, 2688, "0.0")
    reset_total = set_("AirframePrebakeCompiledTotalSecondsV1", "real", 2496, 2688, "0.0")
    reset_valid = set_("AirframePrebakeCompileValidV1", "bool", 2752, 2688, "false")
    chain = [*clears, reset_step, reset_total, reset_valid]
    bp.connect(builder.entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")

    stage_valid = get("AirframePrebakeStageValidV1", "bool", 0, 1280)
    stage_index = get("AirframePrebakeStageIndexV1", "int", 0, 1408)
    input_step = get("AirframePrebakeInputFixedStepSecondsV1", "real", 0, 2816)
    input_total = get("AirframePrebakeInputTotalSecondsV1", "real", 0, 2944)
    count = candidate_lengths[0]
    minimum = compare("GreaterEqual_IntInt", count, "ReturnValue", None, "2", "int", 640, 0)
    maximum = compare("LessEqual_IntInt", count, "ReturnValue", None, "65536", "int", 640, 128)
    minus_one = builder.math("Subtract_DoubleDouble", 640, 1408)
    scalar.retarget_function(minus_one, "Subtract_IntInt")
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(minus_one, pin, "int")
    bp.connect(count, "ReturnValue", minus_one, "A")
    scalar.set_default(minus_one, "B", "1")
    terminal = compare("EqualEqual_IntInt", stage_index, "AirframePrebakeStageIndexV1", minus_one, "ReturnValue", "int", 896, 1408)
    guards = [(stage_valid, "AirframePrebakeStageValidV1"), (minimum, "ReturnValue"), (maximum, "ReturnValue"), (terminal, "ReturnValue")]
    for index, other_length in enumerate(candidate_lengths[1:]):
        equal = compare("EqualEqual_IntInt", other_length, "ReturnValue", count, "ReturnValue", "int", 640, 320 + index * 192)
        guards.append((equal, "ReturnValue"))
    combined, combined_pin = guards[0]
    for index, (guard, guard_pin) in enumerate(guards[1:]):
        combined = and_(combined, combined_pin, guard, guard_pin, 1216 + index * 224, 1408)
        combined_pin = "ReturnValue"
    preflight = builder.add("preflight", "branch", 3072, 2688)
    bp.connect(reset_valid, "then", preflight, "execute")
    bp.connect(combined, combined_pin, preflight, "Condition")

    publications = []
    for index, ((suffix, value), candidate) in enumerate(zip(CHANNELS, candidate_getters)):
        candidate_name = f"AirframePrebakeCandidate{suffix}V1"
        compiled_name = f"AirframePrebakeCompiled{suffix}V1"
        setter = set_(compiled_name, value, 3328 + index * 320, 2688, array=True)
        bp.connect(candidate, candidate_name, setter, compiled_name)
        publications.append(setter)
    publish_step = set_("AirframePrebakeCompiledFixedStepSecondsV1", "real", 5248, 2688)
    publish_total = set_("AirframePrebakeCompiledTotalSecondsV1", "real", 5504, 2688)
    publish_valid = set_("AirframePrebakeCompileValidV1", "bool", 5760, 2688, "true")
    bp.connect(input_step, "AirframePrebakeInputFixedStepSecondsV1", publish_step, "AirframePrebakeCompiledFixedStepSecondsV1")
    bp.connect(input_total, "AirframePrebakeInputTotalSecondsV1", publish_total, "AirframePrebakeCompiledTotalSecondsV1")
    publish_chain = [*publications, publish_step, publish_total, publish_valid]
    bp.connect(preflight, "then", publish_chain[0], "execute")
    for left, right in zip(publish_chain, publish_chain[1:]):
        bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
