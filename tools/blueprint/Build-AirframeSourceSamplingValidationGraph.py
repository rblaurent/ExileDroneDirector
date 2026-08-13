"""Build authored-shape validation for the airframe source-sampling bridge."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateAirframeSourceSamplingInputsV1"
ARRAYS = (
    ("PositionRouteInputWaypointPositionsV1", "vector"),
    ("PositionRouteInputDurationsV1", "real"),
    ("PositionRouteInputSpatialCurveTypesV1", "string"),
    ("PositionRouteInputTimeProfilesV1", "string"),
    ("AirframeSourceInputBodyWaypointQuatsV1", "quat"),
    ("AirframeSourceInputGimbalWaypointQuatsV1", "quat"),
    ("FlightProfileInputSegmentOverrideIdsV1", "string"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_validation_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
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
    b = scalar.Builder(bp, forms, FUNCTION)
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def retarget_call(node, member, pin_types):
        scalar.retarget_function(node, member)
        for pin, kind in pin_types.items():
            pin_kind(node, pin, kind)
        return node

    def array_get(name, kind, x, y):
        node = b.get(name, "real", x, y)
        scalar.retarget_variable(node, name, "real")
        pin_kind(node, name, kind, True)
        return node

    def array_length(source, source_pin, kind, x, y):
        node = add_form(f"length_{source_pin}", length_form, x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def compare(member, left, left_pin, x, y, kind="int", right=None, right_pin=None, default_b=None):
        node = b.add(f"compare_{len(b.nodes)}", "compare", x, y)
        retarget_call(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean_and(left, right, x, y):
        node = b.add(f"and_{len(b.nodes)}", "compare", x, y)
        retarget_call(node, "BooleanAND", {"A": "bool", "B": "bool", "ReturnValue": "bool"})
        bp.connect(left, "ReturnValue", node, "A")
        bp.connect(right, "ReturnValue", node, "B")
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = boolean_and(current, condition, x + index * 224, y)
        return current

    reset = b.set("AirframeSourceStageValidV1", "bool", 256, 2048, "false")
    bp.connect(b.entry, "then", reset, "execute")
    getters = [array_get(name, kind, 0, 128 + index * 224) for index, (name, kind) in enumerate(ARRAYS)]
    lengths = [
        array_length(source, name, kind, 320, 128 + index * 224)
        for index, (source, (name, kind)) in enumerate(zip(getters, ARRAYS))
    ]
    position_count = lengths[0]
    segment_count = lengths[1]
    subtract = b.math("Subtract_DoubleDouble", 640, 480)
    retarget_call(subtract, "Subtract_IntInt", {"A": "int", "B": "int", "ReturnValue": "int"})
    bp.connect(position_count, "ReturnValue", subtract, "A")
    scalar.set_default(subtract, "B", "1")
    conditions = [
        compare("GreaterEqual_IntInt", position_count, "ReturnValue", 640, 128, default_b="2"),
        compare("LessEqual_IntInt", position_count, "ReturnValue", 640, 256, default_b="512"),
        compare("EqualEqual_IntInt", segment_count, "ReturnValue", 896, 480, right=subtract, right_pin="ReturnValue"),
        compare("EqualEqual_IntInt", lengths[2], "ReturnValue", 896, 704, right=segment_count, right_pin="ReturnValue"),
        compare("EqualEqual_IntInt", lengths[3], "ReturnValue", 896, 928, right=segment_count, right_pin="ReturnValue"),
        compare("EqualEqual_IntInt", lengths[4], "ReturnValue", 896, 1152, right=position_count, right_pin="ReturnValue"),
        compare("EqualEqual_IntInt", lengths[5], "ReturnValue", 896, 1376, right=position_count, right_pin="ReturnValue"),
        compare("EqualEqual_IntInt", lengths[6], "ReturnValue", 896, 1600, right=segment_count, right_pin="ReturnValue"),
    ]
    step = b.get("AirframeSourceInputFixedStepSecondsV1", "real", 0, 1792)
    pin_kind(step, "AirframeSourceInputFixedStepSecondsV1", "real")
    conditions.extend((
        b.finite(step, "AirframeSourceInputFixedStepSecondsV1", 640, 1792),
        compare("GreaterEqual_DoubleDouble", step, "AirframeSourceInputFixedStepSecondsV1", 1088, 1792, "real", default_b="0.004166666666666667"),
        compare("LessEqual_DoubleDouble", step, "AirframeSourceInputFixedStepSecondsV1", 1312, 1792, "real", default_b="0.5"),
    ))
    valid = and_all(conditions, 1792, 1792)
    branch = b.add("shape_branch", "branch", 4480, 2048)
    bp.connect(reset, "then", branch, "execute")
    bp.connect(valid, "ReturnValue", branch, "Condition")
    accept = b.set("AirframeSourceStageValidV1", "bool", 4736, 2048, "true")
    bp.connect(branch, "then", accept, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in b.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
