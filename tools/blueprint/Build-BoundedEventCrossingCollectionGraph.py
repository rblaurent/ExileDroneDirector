"""Build deterministic bounded Cue crossing collection for real playback."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CollectCrossedCuesV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_event_crossing_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""),
        "real": ("real", "double"), "string": ("string", ""),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

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
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    clear_source = bp.read_blocks(args.project_root / "tools/blueprint/snippets/build-airframe-source-gimbal-samples-v1.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(clear_source, r'MemberName="Array_Clear"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if value is not None:
            scalar.set_default(node, name, value)
        return node

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def array_get(name, kind, x, y):
        return get(name, kind, x, y, True)

    def length(source, source_pin, kind, x, y):
        node = add_form(f"length_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True); pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = add_form(f"item_{len(builder.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True); pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def retarget(node, member, kinds, parent=None):
        scalar.retarget_function(node, member)
        if parent is not None:
            node.text = re.sub(
                r'MemberParent="[^"]+"',
                f'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.{parent}\'"',
                node.text, 1,
            )
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member, left, left_pin, x, y, *, right=None, right_pin=None, default_b=None, kind="real", parent=None):
        node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"}, parent)
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(member, left, right, x, y):
        return compare(
            member, left, "ReturnValue", x, y,
            right=right, right_pin="ReturnValue", kind="bool",
        )

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = boolean("BooleanAND", current, condition, x + index * 224, y)
        return current

    def or_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = boolean("BooleanOR", current, condition, x + index * 224, y)
        return current

    def bool_value(source, pin, x, y):
        return compare("BooleanAND", source, pin, x, y, right=source, right_pin=pin, kind="bool")

    def string_equal(source, pin, value, x, y):
        return compare(
            "EqualEqual_StrStr", source, pin, x, y,
            default_b=value, kind="string", parent="KismetStringLibrary",
        )

    crossed = array_get("EventCrossedIndicesV1", "int", 0, 0)
    clear = add_form("clear_crossed", "array_clear", 256, 3200)
    pin_kind(clear, "TargetArray", "int", True)
    bp.connect(crossed, "EventCrossedIndicesV1", clear, "TargetArray")
    stage_false = set_("EventCrossingCollectionValidV1", "bool", 480, 3200, "false")
    failure = set_("EventDispatchCodeV1", "string", 704, 3200, "event_crossing_invalid")
    bp.connect(builder.entry, "then", clear, "execute")
    bp.connect(clear, "then", stage_false, "execute")
    bp.connect(stage_false, "then", failure, "execute")

    validation = get("EventPlanValidationValidV1", "bool", 0, 320)
    validation_guard = builder.add("validation_guard", "branch", 928, 3200)
    bp.connect(failure, "then", validation_guard, "execute")
    bp.connect(validation, "EventPlanValidationValidV1", validation_guard, "Condition")
    scrubbing = get("EventScrubbingV1", "bool", 0, 480)
    scrub_branch = builder.add("scrub_branch", "branch", 1152, 3200)
    bp.connect(validation_guard, "then", scrub_branch, "execute")
    bp.connect(scrubbing, "EventScrubbingV1", scrub_branch, "Condition")
    scrub_valid = set_("EventCrossingCollectionValidV1", "bool", 1376, 3040, "true")
    scrub_success = set_("EventDispatchCodeV1", "string", 1600, 3040, "")
    bp.connect(scrub_branch, "then", scrub_valid, "execute")
    bp.connect(scrub_valid, "then", scrub_success, "execute")

    playback_started = get("EventPlaybackStartedV1", "bool", 0, 640)
    direction = get("EventDirectionV1", "int", 0, 800)
    previous = get("EventPreviousTimeV1", "real", 0, 960)
    current = get("EventCurrentTimeV1", "real", 0, 1120)
    forward_direction = compare("EqualEqual_IntInt", direction, "EventDirectionV1", 256, 800, default_b="1", kind="int")
    reverse_direction = compare("EqualEqual_IntInt", direction, "EventDirectionV1", 480, 800, default_b="-1", kind="int")
    forward_order = compare("GreaterEqual_DoubleDouble", current, "EventCurrentTimeV1", 256, 1120, right=previous, right_pin="EventPreviousTimeV1")
    reverse_order = compare("GreaterEqual_DoubleDouble", previous, "EventPreviousTimeV1", 480, 1120, right=current, right_pin="EventCurrentTimeV1")
    forward_ready = boolean("BooleanAND", forward_direction, forward_order, 704, 960)
    reverse_ready = boolean("BooleanAND", reverse_direction, reverse_order, 704, 1120)
    direction_ready = boolean("BooleanOR", forward_ready, reverse_ready, 928, 1040)
    playback_ready = bool_value(playback_started, "EventPlaybackStartedV1", 928, 800)
    query_ready = boolean("BooleanAND", playback_ready, direction_ready, 1152, 960)
    query_guard = builder.add("query_guard", "branch", 1376, 3360)
    bp.connect(scrub_branch, "else", query_guard, "execute")
    bp.connect(query_ready, "ReturnValue", query_guard, "Condition")
    live_stage = set_("EventCrossingCollectionValidV1", "bool", 1600, 3360, "true")
    bp.connect(query_guard, "then", live_stage, "execute")

    times = array_get("EventCueTimesV1", "real", 0, 1440)
    policies = array_get("EventCueDirectionPoliciesV1", "string", 0, 1600)
    loop = add_form("cue_loop", "foreach", 1824, 3360)
    pin_kind(loop, "Array", "real", True); pin_kind(loop, "Array Element", "real"); pin_kind(loop, "Array Index", "int")
    bp.connect(times, "EventCueTimesV1", loop, "Array")
    bp.connect(live_stage, "then", loop, "Exec")

    time_finite = builder.finite(loop, "Array Element", 2048, 1440)
    finite_guard = builder.add("finite_guard", "branch", 2272, 3360)
    bp.connect(loop, "LoopBody", finite_guard, "execute")
    bp.connect(time_finite, "ReturnValue", finite_guard, "Condition")
    time_reject = set_("EventCrossingCollectionValidV1", "bool", 2496, 3680, "false")
    time_code = set_("EventDispatchCodeV1", "string", 2720, 3680, "event_cue_time_invalid")
    bp.connect(finite_guard, "else", time_reject, "execute")
    bp.connect(time_reject, "then", time_code, "execute")

    policy = item(policies, "EventCueDirectionPoliciesV1", "string", loop, "Array Index", 2048, 1760)
    policy_forward = string_equal(policy, "Output", "forward", 2272, 1760)
    policy_reverse = string_equal(policy, "Output", "reverse", 2272, 1920)
    policy_both = string_equal(policy, "Output", "both", 2272, 2080)
    policy_undo = string_equal(policy, "Output", "reverse_undo", 2272, 2240)
    forward_policy = boolean("BooleanOR", policy_forward, policy_both, 2496, 1840)
    reverse_policy_first = boolean("BooleanOR", policy_reverse, policy_undo, 2496, 2080)
    reverse_policy = boolean("BooleanOR", reverse_policy_first, policy_both, 2720, 2080)

    forward_low = compare("Greater_DoubleDouble", loop, "Array Element", 2272, 2400, right=previous, right_pin="EventPreviousTimeV1")
    forward_high = compare("LessEqual_DoubleDouble", loop, "Array Element", 2272, 2560, right=current, right_pin="EventCurrentTimeV1")
    reverse_low = compare("GreaterEqual_DoubleDouble", loop, "Array Element", 2272, 2720, right=current, right_pin="EventCurrentTimeV1")
    reverse_high = compare("Less_DoubleDouble", loop, "Array Element", 2272, 2880, right=previous, right_pin="EventPreviousTimeV1")
    forward_crossed = and_all((forward_direction, forward_low, forward_high, forward_policy), 2944, 2400)
    reverse_crossed = and_all((reverse_direction, reverse_low, reverse_high, reverse_policy), 2944, 2720)
    crossed_now = boolean("BooleanOR", forward_crossed, reverse_crossed, 3616, 2560)
    stage_current = get("EventCrossingCollectionValidV1", "bool", 3392, 2240)
    stage_ready = bool_value(stage_current, "EventCrossingCollectionValidV1", 3616, 2240)
    eligible = boolean("BooleanAND", crossed_now, stage_ready, 3840, 2400)
    eligible_guard = builder.add("eligible_guard", "branch", 4064, 3360)
    bp.connect(finite_guard, "then", eligible_guard, "execute")
    bp.connect(eligible, "ReturnValue", eligible_guard, "Condition")

    crossed_count = length(crossed, "EventCrossedIndicesV1", "int", 4064, 2880)
    capacity = compare("Less_IntInt", crossed_count, "ReturnValue", 4288, 2880, default_b="32", kind="int")
    capacity_guard = builder.add("capacity_guard", "branch", 4288, 3360)
    bp.connect(eligible_guard, "then", capacity_guard, "execute")
    bp.connect(capacity, "ReturnValue", capacity_guard, "Condition")
    add_index = add_form("add_index", "array_add", 4512, 3280)
    pin_kind(add_index, "TargetArray", "int", True); pin_kind(add_index, "NewItem", "int"); pin_kind(add_index, "ReturnValue", "int")
    bp.connect(crossed, "EventCrossedIndicesV1", add_index, "TargetArray")
    bp.connect(loop, "Array Index", add_index, "NewItem")
    bp.connect(capacity_guard, "then", add_index, "execute")
    limit_reject = set_("EventCrossingCollectionValidV1", "bool", 4512, 3680, "false")
    limit_code = set_("EventDispatchCodeV1", "string", 4736, 3680, "event_crossing_limit")
    bp.connect(capacity_guard, "else", limit_reject, "execute")
    bp.connect(limit_reject, "then", limit_code, "execute")

    final_stage = get("EventCrossingCollectionValidV1", "bool", 4736, 2880)
    final_guard = builder.add("final_guard", "branch", 4960, 3360)
    bp.connect(loop, "Completed", final_guard, "execute")
    bp.connect(final_stage, "EventCrossingCollectionValidV1", final_guard, "Condition")
    success = set_("EventDispatchCodeV1", "string", 5184, 3280, "")
    bp.connect(final_guard, "then", success, "execute")

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
