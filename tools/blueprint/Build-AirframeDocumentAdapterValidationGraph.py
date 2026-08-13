"""Build fail-closed structural validation for the normalized v2 document ABI."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateAirframeDocumentSourceAdapterV2"
WAYPOINT_ARRAYS = (
    ("AirframeDocumentInputWaypointIdsV2", "int"),
    ("AirframeDocumentInputWaypointPositionsV2", "vector"),
    ("AirframeDocumentInputWaypointBodyQuatsV2", "quat"),
    ("AirframeDocumentInputWaypointGimbalQuatsV2", "quat"),
)
SEGMENT_ARRAYS = (
    ("AirframeDocumentInputSegmentIdsV2", "int"),
    ("AirframeDocumentInputSegmentFromWaypointIdsV2", "int"),
    ("AirframeDocumentInputSegmentToWaypointIdsV2", "int"),
    ("AirframeDocumentInputSegmentDurationsV2", "real"),
    ("AirframeDocumentInputSegmentSpatialCurveTypesV2", "string"),
    ("AirframeDocumentInputSegmentTimeProfilesV2", "string"),
    ("AirframeDocumentInputSegmentFlightProfileOverridesV2", "string"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_document_adapter_validation_base", path)
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
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
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
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    find = bp.read_blocks(args.project_root / "tools/blueprint/snippets/find-record-index-v1.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "find": bp.find_block(find, r'MemberName="Array_Find"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        if value is not None:
            scalar.set_default(node, name, value)
        return node

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def length(source, source_pin, kind, x, y):
        node = add_form(f"length_{source_pin}_{len(b.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def foreach(source, source_pin, kind, x, y):
        node = add_form(f"foreach_{source_pin}_{len(b.nodes)}", "foreach", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Array Element", kind)
        pin_kind(node, "Array Index", "int")
        bp.connect(source, source_pin, node, "Array")
        return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = add_form(f"item_{source_pin}_{len(b.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def find_first(source, source_pin, value, value_pin, x, y):
        node = add_form(f"find_{source_pin}_{len(b.nodes)}", "find", x, y)
        pin_kind(node, "TargetArray", "int", True)
        pin_kind(node, "ItemToFind", "int")
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        bp.connect(value, value_pin, node, "ItemToFind")
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="int"):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def math(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.math("Add_DoubleDouble", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": kind})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            node = compare("BooleanAND", current, "ReturnValue", x + index * 224, y, condition, "ReturnValue", kind="bool")
            current = node
        return current

    stage_false = set_("AirframeDocumentAdapterStageValidV2", "bool", 256, 2880, "false")
    duration_zero = set_("AirframeDocumentAdapterDurationAccumulatorV2", "real", 480, 2880, "0.0")
    failure = set_("AirframeDocumentAdapterFailureCodeV2", "string", 704, 2880, "validation_failed")
    bp.connect(b.entry, "then", stage_false, "execute")
    bp.connect(stage_false, "then", duration_zero, "execute")
    bp.connect(duration_zero, "then", failure, "execute")

    arrays = {name: get(name, kind, 0, index * 160, True) for index, (name, kind) in enumerate((*WAYPOINT_ARRAYS, *SEGMENT_ARRAYS))}
    lengths = {name: length(arrays[name], name, kind, 256, index * 160) for index, (name, kind) in enumerate((*WAYPOINT_ARRAYS, *SEGMENT_ARRAYS))}
    waypoint_count = lengths[WAYPOINT_ARRAYS[0][0]]
    segment_count = math("Subtract_IntInt", waypoint_count, "ReturnValue", 480, 0, default_b="1", kind="int")
    schema = get("AirframeDocumentInputSchemaVersionV2", "int", 0, 1920)
    engine = get("AirframeDocumentInputTrajectoryEngineVersionV2", "int", 0, 2080)
    total = get("AirframeDocumentInputDurationSecondsV2", "real", 0, 2240)
    fixed = get("AirframeDocumentInputFixedStepSecondsV2", "real", 0, 2400)
    shape = [
        compare("EqualEqual_IntInt", schema, "AirframeDocumentInputSchemaVersionV2", 256, 1920, default_b="2"),
        compare("EqualEqual_IntInt", engine, "AirframeDocumentInputTrajectoryEngineVersionV2", 256, 2080, default_b="1"),
        compare("GreaterEqual_IntInt", waypoint_count, "ReturnValue", 704, 0, default_b="2"),
        compare("LessEqual_IntInt", waypoint_count, "ReturnValue", 704, 160, default_b="512"),
    ]
    for index, (name, _kind) in enumerate(WAYPOINT_ARRAYS[1:]):
        shape.append(compare("EqualEqual_IntInt", lengths[name], "ReturnValue", 704, 320 + index * 160, waypoint_count, "ReturnValue"))
    for index, (name, _kind) in enumerate(SEGMENT_ARRAYS):
        shape.append(compare("EqualEqual_IntInt", lengths[name], "ReturnValue", 928, index * 160, segment_count, "ReturnValue"))
    total_finite = b.finite(total, "AirframeDocumentInputDurationSecondsV2", 256, 2240)
    fixed_finite = b.finite(fixed, "AirframeDocumentInputFixedStepSecondsV2", 256, 2400)
    shape.extend([
        total_finite,
        compare("Greater_DoubleDouble", total, "AirframeDocumentInputDurationSecondsV2", 480, 2240, default_b="0.0", kind="real"),
        fixed_finite,
        compare("GreaterEqual_DoubleDouble", fixed, "AirframeDocumentInputFixedStepSecondsV2", 480, 2400, default_b="0.004166666666666667", kind="real"),
        compare("LessEqual_DoubleDouble", fixed, "AirframeDocumentInputFixedStepSecondsV2", 704, 2400, default_b="0.5", kind="real"),
    ])
    shape_valid = and_all(shape, 1408, 1280)
    shape_branch = b.add("shape_branch", "branch", 5568, 2880)
    bp.connect(failure, "then", shape_branch, "execute")
    bp.connect(shape_valid, "ReturnValue", shape_branch, "Condition")
    stage_true = set_("AirframeDocumentAdapterStageValidV2", "bool", 5792, 2880, "true")
    bp.connect(shape_branch, "then", stage_true, "execute")

    waypoint_loop = foreach(arrays[WAYPOINT_ARRAYS[0][0]], WAYPOINT_ARRAYS[0][0], "int", 6016, 2880)
    bp.connect(stage_true, "then", waypoint_loop, "Exec")
    waypoint_positive = compare("Greater_IntInt", waypoint_loop, "Array Element", 6272, 2400, default_b="0")
    waypoint_first = find_first(arrays[WAYPOINT_ARRAYS[0][0]], WAYPOINT_ARRAYS[0][0], waypoint_loop, "Array Element", 6272, 2560)
    waypoint_unique = compare("EqualEqual_IntInt", waypoint_first, "ReturnValue", 6496, 2560, waypoint_loop, "Array Index")
    waypoint_valid = and_all([waypoint_positive, waypoint_unique], 6720, 2480)
    waypoint_branch = b.add("waypoint_branch", "branch", 6944, 2880)
    bp.connect(waypoint_loop, "LoopBody", waypoint_branch, "execute")
    bp.connect(waypoint_valid, "ReturnValue", waypoint_branch, "Condition")
    waypoint_reject = set_("AirframeDocumentAdapterStageValidV2", "bool", 7168, 3040, "false")
    bp.connect(waypoint_branch, "else", waypoint_reject, "execute")

    durations = arrays["AirframeDocumentInputSegmentDurationsV2"]
    segment_loop = foreach(durations, "AirframeDocumentInputSegmentDurationsV2", "real", 7424, 2880)
    bp.connect(waypoint_loop, "Completed", segment_loop, "Exec")
    seg_id = item(arrays["AirframeDocumentInputSegmentIdsV2"], "AirframeDocumentInputSegmentIdsV2", "int", segment_loop, "Array Index", 7680, 1600)
    from_id = item(arrays["AirframeDocumentInputSegmentFromWaypointIdsV2"], "AirframeDocumentInputSegmentFromWaypointIdsV2", "int", segment_loop, "Array Index", 7680, 1760)
    to_id = item(arrays["AirframeDocumentInputSegmentToWaypointIdsV2"], "AirframeDocumentInputSegmentToWaypointIdsV2", "int", segment_loop, "Array Index", 7680, 1920)
    next_index = math("Add_IntInt", segment_loop, "Array Index", 7680, 2080, default_b="1", kind="int")
    expected_from = item(arrays[WAYPOINT_ARRAYS[0][0]], WAYPOINT_ARRAYS[0][0], "int", segment_loop, "Array Index", 7936, 1760)
    expected_to = item(arrays[WAYPOINT_ARRAYS[0][0]], WAYPOINT_ARRAYS[0][0], "int", next_index, "ReturnValue", 7936, 1920)
    first_seg = find_first(arrays["AirframeDocumentInputSegmentIdsV2"], "AirframeDocumentInputSegmentIdsV2", seg_id, "Output", 7936, 1600)
    conditions = [
        compare("Greater_IntInt", seg_id, "Output", 8192, 1440, default_b="0"),
        compare("EqualEqual_IntInt", first_seg, "ReturnValue", 8192, 1600, segment_loop, "Array Index"),
        compare("EqualEqual_IntInt", from_id, "Output", 8192, 1760, expected_from, "Output"),
        compare("EqualEqual_IntInt", to_id, "Output", 8192, 1920, expected_to, "Output"),
        b.finite(segment_loop, "Array Element", 8192, 2080),
        compare("Greater_DoubleDouble", segment_loop, "Array Element", 8192, 2240, default_b="0.0", kind="real"),
    ]
    segment_valid = and_all(conditions, 8640, 1760)
    segment_branch = b.add("segment_branch", "branch", 9760, 2880)
    bp.connect(segment_loop, "LoopBody", segment_branch, "execute")
    bp.connect(segment_valid, "ReturnValue", segment_branch, "Condition")
    segment_reject = set_("AirframeDocumentAdapterStageValidV2", "bool", 9984, 3040, "false")
    bp.connect(segment_branch, "else", segment_reject, "execute")
    accumulator = get("AirframeDocumentAdapterDurationAccumulatorV2", "real", 9760, 2400)
    summed = math("Add_DoubleDouble", accumulator, "AirframeDocumentAdapterDurationAccumulatorV2", 9984, 2400, segment_loop, "Array Element")
    store_sum = set_("AirframeDocumentAdapterDurationAccumulatorV2", "real", 10208, 2880)
    bp.connect(summed, "ReturnValue", store_sum, "AirframeDocumentAdapterDurationAccumulatorV2")
    bp.connect(segment_branch, "then", store_sum, "execute")

    prior_stage = get("AirframeDocumentAdapterStageValidV2", "bool", 10432, 2400)
    final_sum = get("AirframeDocumentAdapterDurationAccumulatorV2", "real", 10432, 2560)
    exact = compare("EqualEqual_DoubleDouble", final_sum, "AirframeDocumentAdapterDurationAccumulatorV2", 10656, 2560, total, "AirframeDocumentInputDurationSecondsV2", kind="real")
    final_valid = compare("BooleanAND", prior_stage, "AirframeDocumentAdapterStageValidV2", 10880, 2480, exact, "ReturnValue", kind="bool")
    final_branch = b.add("final_branch", "branch", 11104, 2880)
    bp.connect(segment_loop, "Completed", final_branch, "execute")
    bp.connect(final_valid, "ReturnValue", final_branch, "Condition")
    final_reject = set_("AirframeDocumentAdapterStageValidV2", "bool", 11328, 3040, "false")
    final_success = set_("AirframeDocumentAdapterFailureCodeV2", "string", 11328, 2880, "")
    bp.connect(final_branch, "else", final_reject, "execute")
    bp.connect(final_branch, "then", final_success, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
