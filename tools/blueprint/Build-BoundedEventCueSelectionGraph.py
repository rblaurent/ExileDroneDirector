"""Build direction-correct Cue selection with repeat-ledger filtering."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "SelectEligibleCrossedCueV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_event_selection_base", path)
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
    forms.update({
        "foreach": bp.find_block(sync, r"K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
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

    def foreach(source, source_pin, kind, x, y):
        node = add_form(f"foreach_{len(builder.nodes)}", "foreach", x, y)
        pin_kind(node, "Array", kind, True); pin_kind(node, "Array Element", kind); pin_kind(node, "Array Index", "int")
        bp.connect(source, source_pin, node, "Array")
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

    def compare(member, left, left_pin, x, y, *, right=None, right_pin=None, default_b=None, kind="int", parent=None):
        node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"}, parent)
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(member, left, right, x, y):
        return compare(member, left, "ReturnValue", x, y, right=right, right_pin="ReturnValue", kind="bool")

    def string_equal(left, left_pin, right=None, right_pin=None, default_b=None, x=0, y=0):
        return compare(
            "EqualEqual_StrStr", left, left_pin, x, y,
            right=right, right_pin=right_pin, default_b=default_b,
            kind="string", parent="KismetStringLibrary",
        )

    stage_false = set_("EventSelectionValidV1", "bool", 256, 3840, "false")
    candidate_false = set_("EventCandidateAlreadyExecutedV1", "bool", 480, 3840, "false")
    result_false = set_("EventDispatchResultValidV1", "bool", 704, 3840, "false")
    authorized_false = set_("EventDispatchAuthorizedV1", "bool", 928, 3840, "false")
    index_reset = set_("EventDispatchIndexV1", "int", 1152, 3840, "-1")
    failure = set_("EventDispatchCodeV1", "string", 1376, 3840, "event_selection_invalid")
    bp.connect(builder.entry, "then", stage_false, "execute")
    for left, right in zip(
        (stage_false, candidate_false, result_false, authorized_false, index_reset),
        (candidate_false, result_false, authorized_false, index_reset, failure),
    ):
        bp.connect(left, "then", right, "execute")

    crossing_valid = get("EventCrossingCollectionValidV1", "bool", 0, 0)
    crossed = array_get("EventCrossedIndicesV1", "int", 0, 160)
    crossed_count = length(crossed, "EventCrossedIndicesV1", "int", 256, 160)
    ledger_ids = array_get("EventLedgerIdsV1", "string", 0, 320)
    ledger_loops = array_get("EventLedgerLoopsV1", "int", 0, 480)
    ledger_directions = array_get("EventLedgerDirectionsV1", "int", 0, 640)
    ledger_id_count = length(ledger_ids, "EventLedgerIdsV1", "string", 256, 320)
    ledger_loop_count = length(ledger_loops, "EventLedgerLoopsV1", "int", 256, 480)
    ledger_direction_count = length(ledger_directions, "EventLedgerDirectionsV1", "int", 256, 640)
    ledger_shape_a = compare("EqualEqual_IntInt", ledger_id_count, "ReturnValue", 480, 320, right=ledger_loop_count, right_pin="ReturnValue")
    ledger_shape_b = compare("EqualEqual_IntInt", ledger_id_count, "ReturnValue", 480, 480, right=ledger_direction_count, right_pin="ReturnValue")
    ledger_limit = compare("LessEqual_IntInt", ledger_id_count, "ReturnValue", 480, 640, default_b="1024")
    ledger_shape = boolean("BooleanAND", ledger_shape_a, ledger_shape_b, 704, 400)
    ledger_ready = boolean("BooleanAND", ledger_shape, ledger_limit, 928, 480)
    crossing_ready = compare(
        "BooleanAND", crossing_valid, "EventCrossingCollectionValidV1", 928, 160,
        right=crossing_valid, right_pin="EventCrossingCollectionValidV1", kind="bool",
    )
    preflight_ready = boolean("BooleanAND", crossing_ready, ledger_ready, 1152, 320)
    preflight_guard = builder.add("preflight_guard", "branch", 1600, 3840)
    bp.connect(failure, "then", preflight_guard, "execute")
    bp.connect(preflight_ready, "ReturnValue", preflight_guard, "Condition")
    has_crossing = compare("Greater_IntInt", crossed_count, "ReturnValue", 1376, 160, default_b="0")
    crossing_guard = builder.add("crossing_guard", "branch", 1824, 3840)
    bp.connect(preflight_guard, "then", crossing_guard, "execute")
    bp.connect(has_crossing, "ReturnValue", crossing_guard, "Condition")
    empty_valid = set_("EventSelectionValidV1", "bool", 2048, 4160, "true")
    empty_code = set_("EventDispatchCodeV1", "string", 2272, 4160, "no_event_crossing")
    bp.connect(crossing_guard, "else", empty_valid, "execute")
    bp.connect(empty_valid, "then", empty_code, "execute")

    outer = foreach(crossed, "EventCrossedIndicesV1", "int", 2048, 3840)
    bp.connect(crossing_guard, "then", outer, "Exec")
    reset_candidate = set_("EventCandidateAlreadyExecutedV1", "bool", 2272, 3840, "false")
    bp.connect(outer, "LoopBody", reset_candidate, "execute")
    cue_ids = array_get("EventCueIdsV1", "string", 0, 960)
    repeat_policies = array_get("EventCueRepeatPoliciesV1", "string", 0, 1120)
    cue_id = item(cue_ids, "EventCueIdsV1", "string", outer, "Array Element", 2272, 960)
    repeat_policy = item(repeat_policies, "EventCueRepeatPoliciesV1", "string", outer, "Array Element", 2272, 1120)
    every_loop = string_equal(repeat_policy, "Output", default_b="every_loop", x=2496, y=1120)

    inner = foreach(ledger_ids, "EventLedgerIdsV1", "string", 2496, 3840)
    bp.connect(reset_candidate, "then", inner, "Exec")
    same_id = string_equal(cue_id, "Output", right=inner, right_pin="Array Element", x=2720, y=960)
    ledger_loop = item(ledger_loops, "EventLedgerLoopsV1", "int", inner, "Array Index", 2720, 1280)
    ledger_direction = item(ledger_directions, "EventLedgerDirectionsV1", "int", inner, "Array Index", 2720, 1440)
    current_loop = get("EventLoopIterationV1", "int", 2496, 1280)
    current_direction = get("EventDirectionV1", "int", 2496, 1440)
    same_loop = compare("EqualEqual_IntInt", ledger_loop, "Output", 2944, 1280, right=current_loop, right_pin="EventLoopIterationV1")
    same_direction = compare("EqualEqual_IntInt", ledger_direction, "Output", 2944, 1440, right=current_direction, right_pin="EventDirectionV1")
    same_iteration = boolean("BooleanAND", same_loop, same_direction, 3168, 1360)
    not_every_loop = compare("EqualEqual_BoolBool", every_loop, "ReturnValue", 2944, 1120, default_b="false", kind="bool")
    repeated_loop = boolean("BooleanAND", every_loop, same_iteration, 3392, 1280)
    repeated_policy = boolean("BooleanOR", not_every_loop, repeated_loop, 3616, 1200)
    already_executed = boolean("BooleanAND", same_id, repeated_policy, 3840, 1120)
    already_guard = builder.add("already_guard", "branch", 2944, 3840)
    bp.connect(inner, "LoopBody", already_guard, "execute")
    bp.connect(already_executed, "ReturnValue", already_guard, "Condition")
    mark_executed = set_("EventCandidateAlreadyExecutedV1", "bool", 3168, 4000, "true")
    bp.connect(already_guard, "then", mark_executed, "execute")

    candidate_state = get("EventCandidateAlreadyExecutedV1", "bool", 4064, 1600)
    candidate_available = compare(
        "EqualEqual_BoolBool", candidate_state, "EventCandidateAlreadyExecutedV1",
        4288, 1600, default_b="false", kind="bool",
    )
    is_reverse = compare("EqualEqual_IntInt", current_direction, "EventDirectionV1", 4064, 1760, default_b="-1")
    selected_index = get("EventDispatchIndexV1", "int", 4064, 1920)
    no_selection = compare("Less_IntInt", selected_index, "EventDispatchIndexV1", 4288, 1920, default_b="0")
    selection_open = boolean("BooleanOR", is_reverse, no_selection, 4512, 1840)
    should_select = boolean("BooleanAND", candidate_available, selection_open, 4736, 1760)
    select_guard = builder.add("select_guard", "branch", 4064, 3840)
    bp.connect(inner, "Completed", select_guard, "execute")
    bp.connect(should_select, "ReturnValue", select_guard, "Condition")
    select_index = set_("EventDispatchIndexV1", "int", 4288, 3840)
    bp.connect(outer, "Array Element", select_index, "EventDispatchIndexV1")
    bp.connect(select_guard, "then", select_index, "execute")

    final_index = get("EventDispatchIndexV1", "int", 4960, 2080)
    selected = compare("GreaterEqual_IntInt", final_index, "EventDispatchIndexV1", 5184, 2080, default_b="0")
    final_guard = builder.add("final_guard", "branch", 4960, 3840)
    bp.connect(outer, "Completed", final_guard, "execute")
    bp.connect(selected, "ReturnValue", final_guard, "Condition")
    selected_valid = set_("EventSelectionValidV1", "bool", 5184, 3760, "true")
    selected_code = set_("EventDispatchCodeV1", "string", 5408, 3760, "event_authorization_pending")
    exhausted_valid = set_("EventSelectionValidV1", "bool", 5184, 4080, "true")
    exhausted_code = set_("EventDispatchCodeV1", "string", 5408, 4080, "event_already_executed")
    bp.connect(final_guard, "then", selected_valid, "execute")
    bp.connect(selected_valid, "then", selected_code, "execute")
    bp.connect(final_guard, "else", exhausted_valid, "execute")
    bp.connect(exhausted_valid, "then", exhausted_code, "execute")

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
