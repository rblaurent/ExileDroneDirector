"""Build policy-checked atomic manual Cue ledger re-arming."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetManualCueLedgerEntryV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_event_manual_reset_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""), "string": ("string", ""),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(
            r'PinType.ContainerType=(?:None|Array)',
            f'PinType.ContainerType={"Array" if array else "None"}', line, 1,
        )

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
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    clear_source = bp.read_blocks(args.project_root / "tools/blueprint/snippets/build-airframe-source-gimbal-samples-v1.eddgraph")
    forms.update({
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(clear_source, r'MemberName="Array_Clear"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name, kind, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None, array=False):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind, array)
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

    def length(source, source_pin, kind, x, y):
        node = add_form(f"length_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def foreach(source, source_pin, kind, x, y):
        node = add_form(f"foreach_{len(builder.nodes)}", "foreach", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Array Element", kind)
        pin_kind(node, "Array Index", "int")
        bp.connect(source, source_pin, node, "Array")
        return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = add_form(f"item_{len(builder.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def array_op(form, target, target_pin, kind, x, y, value=None, value_pin=None):
        node = add_form(f"{form}_{len(builder.nodes)}", form, x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(target, target_pin, node, "TargetArray")
        if form == "array_add":
            pin_kind(node, "NewItem", kind)
            pin_kind(node, "ReturnValue", "int")
            bp.connect(value, value_pin, node, "NewItem")
        return node

    def retarget(node, function, kinds, parent=None):
        scalar.retarget_function(node, function)
        if parent is not None:
            node.text = re.sub(
                r'MemberParent="[^"]+"',
                f'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.{parent}\'"',
                node.text, 1,
            )
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(function, left, left_pin, x, y, *, right=None, right_pin=None,
                default_b=None, kind="int", parent=None):
        node = builder.add(f"{function}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, function, {"A": kind, "B": kind, "ReturnValue": "bool"}, parent)
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(function, left, left_pin, right, right_pin, x, y):
        return compare(
            function, left, left_pin, x, y, right=right, right_pin=right_pin,
            kind="bool",
        )

    def string_compare(function, left, left_pin, value, x, y):
        return compare(
            function, left, left_pin, x, y, default_b=value,
            kind="string", parent="KismetStringLibrary",
        )

    def guard(previous, previous_pin, condition, condition_pin, code, x, y):
        branch = builder.add(f"guard_{code}", "branch", x, y)
        failure = set_("EventDispatchCodeV1", "string", x + 224, y + 224, code)
        bp.connect(previous, previous_pin, branch, "execute")
        bp.connect(condition, condition_pin, branch, "Condition")
        bp.connect(branch, "else", failure, "execute")
        return branch

    result_false = set_("EventManualResetResultValidV1", "bool", 256, 4000, "false")
    commit_false = set_("EventLedgerCommitValidV1", "bool", 480, 4000, "false")
    found_false = set_("EventManualResetCueFoundV1", "bool", 704, 4000, "false")
    removed_false = set_("EventManualResetRemovedAnyV1", "bool", 928, 4000, "false")
    candidate_true = set_("EventManualResetCandidateValidV1", "bool", 1152, 4000, "true")
    unavailable = set_("EventDispatchCodeV1", "string", 1376, 4000, "event_manual_reset_unavailable")
    bp.connect(builder.entry, "then", result_false, "execute")
    for left, right in zip(
        (result_false, commit_false, found_false, removed_false, candidate_true),
        (commit_false, found_false, removed_false, candidate_true, unavailable),
    ):
        bp.connect(left, "then", right, "execute")

    request = get("EventManualResetCueIdV1", "string", 0, 0)
    request_ready = string_compare("NotEqual_StrStr", request, "EventManualResetCueIdV1", "", 256, 0)
    request_guard = guard(
        unavailable, "then", request_ready, "ReturnValue",
        "event_manual_reset_request_invalid", 1600, 4000,
    )
    plan_valid = get("EventCuePlanValidV1", "bool", 0, 160)
    plan_guard = guard(
        request_guard, "then", plan_valid, "EventCuePlanValidV1",
        "event_manual_reset_plan_invalid", 1824, 4000,
    )

    cue_ids = get("EventCueIdsV1", "string", 0, 320, True)
    repeat_policies = get("EventCueRepeatPoliciesV1", "string", 0, 480, True)
    cue_count = length(cue_ids, "EventCueIdsV1", "string", 256, 320)
    repeat_count = length(repeat_policies, "EventCueRepeatPoliciesV1", "string", 256, 480)
    cue_nonempty = compare("GreaterEqual_IntInt", cue_count, "ReturnValue", 480, 320, default_b="1")
    cue_bounded = compare("LessEqual_IntInt", cue_count, "ReturnValue", 480, 480, default_b="256")
    cue_aligned = compare("EqualEqual_IntInt", cue_count, "ReturnValue", 480, 640, right=repeat_count, right_pin="ReturnValue")
    cue_shape_a = boolean("BooleanAND", cue_nonempty, "ReturnValue", cue_bounded, "ReturnValue", 704, 400)
    cue_shape = boolean("BooleanAND", cue_shape_a, "ReturnValue", cue_aligned, "ReturnValue", 928, 480)
    shape_guard = guard(
        plan_guard, "then", cue_shape, "ReturnValue",
        "event_manual_reset_plan_invalid", 2048, 4000,
    )

    cue_loop = foreach(cue_ids, "EventCueIdsV1", "string", 2272, 4000)
    bp.connect(shape_guard, "then", cue_loop, "Exec")
    policy = item(repeat_policies, "EventCueRepeatPoliciesV1", "string", cue_loop, "Array Index", 2496, 480)
    same_id = compare(
        "EqualEqual_StrStr", cue_loop, "Array Element", 2496, 320,
        right=request, right_pin="EventManualResetCueIdV1", kind="string",
        parent="KismetStringLibrary",
    )
    manual = string_compare("EqualEqual_StrStr", policy, "Output", "manual_reset", 2720, 480)
    eligible = boolean("BooleanAND", same_id, "ReturnValue", manual, "ReturnValue", 2944, 400)
    eligible_branch = builder.add("eligible_cue_branch", "branch", 2496, 4000)
    bp.connect(cue_loop, "LoopBody", eligible_branch, "execute")
    bp.connect(eligible, "ReturnValue", eligible_branch, "Condition")
    mark_found = set_("EventManualResetCueFoundV1", "bool", 2720, 4160, "true")
    bp.connect(eligible_branch, "then", mark_found, "execute")
    found = get("EventManualResetCueFoundV1", "bool", 3168, 640)
    policy_guard = guard(
        cue_loop, "Completed", found, "EventManualResetCueFoundV1",
        "event_manual_reset_policy_invalid", 3168, 4000,
    )

    ledger_ids = get("EventLedgerIdsV1", "string", 0, 800, True)
    ledger_loops = get("EventLedgerLoopsV1", "int", 0, 960, True)
    ledger_directions = get("EventLedgerDirectionsV1", "int", 0, 1120, True)
    ids_count = length(ledger_ids, "EventLedgerIdsV1", "string", 256, 800)
    loops_count = length(ledger_loops, "EventLedgerLoopsV1", "int", 256, 960)
    directions_count = length(ledger_directions, "EventLedgerDirectionsV1", "int", 256, 1120)
    ledger_shape_a = compare("EqualEqual_IntInt", ids_count, "ReturnValue", 480, 800, right=loops_count, right_pin="ReturnValue")
    ledger_shape_b = compare("EqualEqual_IntInt", ids_count, "ReturnValue", 480, 960, right=directions_count, right_pin="ReturnValue")
    ledger_limit = compare("LessEqual_IntInt", ids_count, "ReturnValue", 480, 1120, default_b="1024")
    ledger_shape_pair = boolean("BooleanAND", ledger_shape_a, "ReturnValue", ledger_shape_b, "ReturnValue", 704, 880)
    ledger_shape = boolean("BooleanAND", ledger_shape_pair, "ReturnValue", ledger_limit, "ReturnValue", 928, 960)
    ledger_guard = guard(
        policy_guard, "then", ledger_shape, "ReturnValue",
        "event_manual_reset_ledger_invalid", 3392, 4000,
    )

    candidate_ids = get("EventLedgerCandidateIdsV1", "string", 0, 1440, True)
    candidate_loops = get("EventLedgerCandidateLoopsV1", "int", 0, 1600, True)
    candidate_directions = get("EventLedgerCandidateDirectionsV1", "int", 0, 1760, True)
    clear_ids = array_op("array_clear", candidate_ids, "EventLedgerCandidateIdsV1", "string", 3616, 4000)
    clear_loops = array_op("array_clear", candidate_loops, "EventLedgerCandidateLoopsV1", "int", 3840, 4000)
    clear_directions = array_op("array_clear", candidate_directions, "EventLedgerCandidateDirectionsV1", "int", 4064, 4000)
    bp.connect(ledger_guard, "then", clear_ids, "execute")
    bp.connect(clear_ids, "then", clear_loops, "execute")
    bp.connect(clear_loops, "then", clear_directions, "execute")

    ledger_loop = foreach(ledger_ids, "EventLedgerIdsV1", "string", 4288, 4000)
    bp.connect(clear_directions, "then", ledger_loop, "Exec")
    ledger_loop_value = item(ledger_loops, "EventLedgerLoopsV1", "int", ledger_loop, "Array Index", 4512, 960)
    ledger_direction_value = item(ledger_directions, "EventLedgerDirectionsV1", "int", ledger_loop, "Array Index", 4512, 1120)
    should_remove = compare(
        "EqualEqual_StrStr", ledger_loop, "Array Element", 4512, 800,
        right=request, right_pin="EventManualResetCueIdV1", kind="string",
        parent="KismetStringLibrary",
    )
    remove_branch = builder.add("remove_matching_entry_branch", "branch", 4512, 4000)
    bp.connect(ledger_loop, "LoopBody", remove_branch, "execute")
    bp.connect(should_remove, "ReturnValue", remove_branch, "Condition")
    mark_removed = set_("EventManualResetRemovedAnyV1", "bool", 4736, 3840, "true")
    bp.connect(remove_branch, "then", mark_removed, "execute")

    add_id = array_op(
        "array_add", candidate_ids, "EventLedgerCandidateIdsV1", "string", 4736, 4160,
        ledger_loop, "Array Element",
    )
    add_loop = array_op(
        "array_add", candidate_loops, "EventLedgerCandidateLoopsV1", "int", 4960, 4160,
        ledger_loop_value, "Output",
    )
    add_direction = array_op(
        "array_add", candidate_directions, "EventLedgerCandidateDirectionsV1", "int", 5184, 4160,
        ledger_direction_value, "Output",
    )
    bp.connect(remove_branch, "else", add_id, "execute")
    bp.connect(add_id, "then", add_loop, "execute")
    bp.connect(add_loop, "then", add_direction, "execute")
    append_loop_aligned = compare("EqualEqual_IntInt", add_id, "ReturnValue", 5408, 1440, right=add_loop, right_pin="ReturnValue")
    append_direction_aligned = compare("EqualEqual_IntInt", add_id, "ReturnValue", 5408, 1600, right=add_direction, right_pin="ReturnValue")
    append_aligned = boolean(
        "BooleanAND", append_loop_aligned, "ReturnValue",
        append_direction_aligned, "ReturnValue", 5632, 1520,
    )
    append_guard = builder.add("candidate_append_guard", "branch", 5408, 4160)
    bp.connect(add_direction, "then", append_guard, "execute")
    bp.connect(append_aligned, "ReturnValue", append_guard, "Condition")
    candidate_false = set_("EventManualResetCandidateValidV1", "bool", 5632, 4320, "false")
    bp.connect(append_guard, "else", candidate_false, "execute")

    candidate_id_count = length(candidate_ids, "EventLedgerCandidateIdsV1", "string", 5856, 1440)
    candidate_loop_count = length(candidate_loops, "EventLedgerCandidateLoopsV1", "int", 5856, 1600)
    candidate_direction_count = length(candidate_directions, "EventLedgerCandidateDirectionsV1", "int", 5856, 1760)
    candidate_shape_a = compare("EqualEqual_IntInt", candidate_id_count, "ReturnValue", 6080, 1440, right=candidate_loop_count, right_pin="ReturnValue")
    candidate_shape_b = compare("EqualEqual_IntInt", candidate_id_count, "ReturnValue", 6080, 1600, right=candidate_direction_count, right_pin="ReturnValue")
    candidate_bounded = compare("LessEqual_IntInt", candidate_id_count, "ReturnValue", 6080, 1760, right=ids_count, right_pin="ReturnValue")
    candidate_shape_pair = boolean("BooleanAND", candidate_shape_a, "ReturnValue", candidate_shape_b, "ReturnValue", 6304, 1520)
    candidate_shape = boolean("BooleanAND", candidate_shape_pair, "ReturnValue", candidate_bounded, "ReturnValue", 6528, 1600)
    candidate_state = get("EventManualResetCandidateValidV1", "bool", 6304, 1920)
    candidate_ready = boolean(
        "BooleanAND", candidate_shape, "ReturnValue",
        candidate_state, "EventManualResetCandidateValidV1", 6752, 1760,
    )
    candidate_guard = guard(
        ledger_loop, "Completed", candidate_ready, "ReturnValue",
        "event_manual_reset_candidate_invalid", 5856, 4000,
    )

    publish_ids = set_("EventLedgerIdsV1", "string", 6080, 4000, array=True)
    publish_loops = set_("EventLedgerLoopsV1", "int", 6304, 4000, array=True)
    publish_directions = set_("EventLedgerDirectionsV1", "int", 6528, 4000, array=True)
    publish_valid = set_("EventManualResetResultValidV1", "bool", 6752, 4000, "true")
    bp.connect(candidate_ids, "EventLedgerCandidateIdsV1", publish_ids, "EventLedgerIdsV1")
    bp.connect(candidate_loops, "EventLedgerCandidateLoopsV1", publish_loops, "EventLedgerLoopsV1")
    bp.connect(candidate_directions, "EventLedgerCandidateDirectionsV1", publish_directions, "EventLedgerDirectionsV1")
    bp.connect(candidate_guard, "then", publish_ids, "execute")
    bp.connect(publish_ids, "then", publish_loops, "execute")
    bp.connect(publish_loops, "then", publish_directions, "execute")
    bp.connect(publish_directions, "then", publish_valid, "execute")

    removed = get("EventManualResetRemovedAnyV1", "bool", 6976, 2080)
    removed_branch = builder.add("removed_result_branch", "branch", 6976, 4000)
    completed_code = set_("EventDispatchCodeV1", "string", 7200, 3840, "event_manual_reset_completed")
    armed_code = set_("EventDispatchCodeV1", "string", 7200, 4160, "event_manual_reset_already_armed")
    bp.connect(publish_valid, "then", removed_branch, "execute")
    bp.connect(removed, "EventManualResetRemovedAnyV1", removed_branch, "Condition")
    bp.connect(removed_branch, "then", completed_code, "execute")
    bp.connect(removed_branch, "else", armed_code, "execute")

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
