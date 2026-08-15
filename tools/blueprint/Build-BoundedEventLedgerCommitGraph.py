"""Build atomic success-receipt-gated bounded Cue ledger publication."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCueExecutionLedgerV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_event_ledger_commit_base", path)
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
    forms.update({
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
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

    def array_add(target, target_pin, kind, value, value_pin, x, y):
        node = add_form(f"array_add_{len(builder.nodes)}", "array_add", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "NewItem", kind)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(target, target_pin, node, "TargetArray")
        bp.connect(value, value_pin, node, "NewItem")
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

    def compare(member, left, left_pin, x, y, *, right=None, right_pin=None,
                default_b=None, kind="int", parent=None):
        node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"}, parent)
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(member, left, left_pin, right, right_pin, x, y):
        return compare(
            member, left, left_pin, x, y, right=right, right_pin=right_pin, kind="bool"
        )

    def truth(source, pin, x, y):
        return boolean("BooleanAND", source, pin, source, pin, x, y)

    def string_compare(member, left, left_pin, value, x, y):
        return compare(
            member, left, left_pin, x, y, default_b=value,
            kind="string", parent="KismetStringLibrary",
        )

    def guard(previous, previous_pin, condition, condition_pin, code, x, y):
        branch = builder.add(f"guard_{code}", "branch", x, y)
        failure = set_("EventDispatchCodeV1", "string", x + 224, y + 224, code)
        bp.connect(previous, previous_pin, branch, "execute")
        bp.connect(condition, condition_pin, branch, "Condition")
        bp.connect(branch, "else", failure, "execute")
        return branch

    commit_false = set_("EventLedgerCommitValidV1", "bool", 256, 4480, "false")
    candidate_false = set_("EventCandidateAlreadyExecutedV1", "bool", 480, 4480, "false")
    unavailable = set_("EventDispatchCodeV1", "string", 704, 4480, "event_ledger_commit_unavailable")
    bp.connect(builder.entry, "then", commit_false, "execute")
    bp.connect(commit_false, "then", candidate_false, "execute")
    bp.connect(candidate_false, "then", unavailable, "execute")

    authorization_valid = get("EventDispatchResultValidV1", "bool", 0, 0)
    authorized = get("EventDispatchAuthorizedV1", "bool", 0, 160)
    selection_valid = get("EventSelectionValidV1", "bool", 0, 320)
    auth_a = boolean(
        "BooleanAND", authorization_valid, "EventDispatchResultValidV1",
        authorized, "EventDispatchAuthorizedV1", 256, 80,
    )
    auth_ready = boolean(
        "BooleanAND", auth_a, "ReturnValue", selection_valid,
        "EventSelectionValidV1", 480, 160,
    )
    auth_guard = guard(unavailable, "then", auth_ready, "ReturnValue", "event_authorization_invalid", 928, 4480)

    receipt_valid = get("EventAdapterExecutionResultValidV1", "bool", 0, 480)
    receipt_guard = guard(
        auth_guard, "then", receipt_valid, "EventAdapterExecutionResultValidV1",
        "event_execution_receipt_invalid", 1152, 4480,
    )
    execution_succeeded = get("EventAdapterExecutionSucceededV1", "bool", 0, 640)
    succeeded_guard = guard(
        receipt_guard, "then", execution_succeeded, "EventAdapterExecutionSucceededV1",
        "event_adapter_execution_failed", 1376, 4480,
    )
    execution_code = get("EventAdapterExecutionCodeV1", "string", 0, 800)
    executed = string_compare("EqualEqual_StrStr", execution_code, "EventAdapterExecutionCodeV1", "executed", 256, 800)
    satisfied = string_compare("EqualEqual_StrStr", execution_code, "EventAdapterExecutionCodeV1", "state_satisfied", 480, 800)
    success_code = boolean("BooleanOR", executed, "ReturnValue", satisfied, "ReturnValue", 704, 800)
    code_guard = guard(
        succeeded_guard, "then", success_code, "ReturnValue",
        "event_adapter_success_code_invalid", 1600, 4480,
    )

    dispatch_index = get("EventDispatchIndexV1", "int", 0, 960)
    cue_ids = get("EventCueIdsV1", "string", 0, 1120, True)
    cue_count = length(cue_ids, "EventCueIdsV1", "string", 256, 1120)
    index_nonnegative = compare("GreaterEqual_IntInt", dispatch_index, "EventDispatchIndexV1", 256, 960, default_b="0")
    index_bounded = compare(
        "Less_IntInt", dispatch_index, "EventDispatchIndexV1", 480, 960,
        right=cue_count, right_pin="ReturnValue",
    )
    index_ready = boolean("BooleanAND", index_nonnegative, "ReturnValue", index_bounded, "ReturnValue", 704, 960)
    index_guard = guard(
        code_guard, "then", index_ready, "ReturnValue",
        "event_selection_index_invalid", 1824, 4480,
    )
    cue_id = item(cue_ids, "EventCueIdsV1", "string", dispatch_index, "EventDispatchIndexV1", 928, 1120)
    identity_ready = string_compare("NotEqual_StrStr", cue_id, "Output", "", 1152, 1120)
    identity_guard = guard(
        index_guard, "then", identity_ready, "ReturnValue",
        "event_identity_invalid", 2048, 4480,
    )

    loop_iteration = get("EventLoopIterationV1", "int", 0, 1280)
    direction = get("EventDirectionV1", "int", 0, 1440)
    loop_ready = compare("GreaterEqual_IntInt", loop_iteration, "EventLoopIterationV1", 256, 1280, default_b="0")
    forward = compare("EqualEqual_IntInt", direction, "EventDirectionV1", 256, 1440, default_b="1")
    reverse = compare("EqualEqual_IntInt", direction, "EventDirectionV1", 480, 1440, default_b="-1")
    direction_ready = boolean("BooleanOR", forward, "ReturnValue", reverse, "ReturnValue", 704, 1440)
    context_ready = boolean("BooleanAND", loop_ready, "ReturnValue", direction_ready, "ReturnValue", 928, 1360)
    context_guard = guard(
        identity_guard, "then", context_ready, "ReturnValue",
        "event_playback_context_invalid", 2272, 4480,
    )

    ledger_ids = get("EventLedgerIdsV1", "string", 0, 1760, True)
    ledger_loops = get("EventLedgerLoopsV1", "int", 0, 1920, True)
    ledger_directions = get("EventLedgerDirectionsV1", "int", 0, 2080, True)
    ids_count = length(ledger_ids, "EventLedgerIdsV1", "string", 256, 1760)
    loops_count = length(ledger_loops, "EventLedgerLoopsV1", "int", 256, 1920)
    directions_count = length(ledger_directions, "EventLedgerDirectionsV1", "int", 256, 2080)
    shape_a = compare("EqualEqual_IntInt", ids_count, "ReturnValue", 480, 1760, right=loops_count, right_pin="ReturnValue")
    shape_b = compare("EqualEqual_IntInt", ids_count, "ReturnValue", 480, 1920, right=directions_count, right_pin="ReturnValue")
    shape_ready = boolean("BooleanAND", shape_a, "ReturnValue", shape_b, "ReturnValue", 704, 1840)
    shape_guard = guard(
        context_guard, "then", shape_ready, "ReturnValue",
        "event_ledger_invalid", 2496, 4480,
    )

    ledger_loop = foreach(ledger_ids, "EventLedgerIdsV1", "string", 2720, 4480)
    bp.connect(shape_guard, "then", ledger_loop, "Exec")
    prior_loop = item(ledger_loops, "EventLedgerLoopsV1", "int", ledger_loop, "Array Index", 2944, 1920)
    prior_direction = item(ledger_directions, "EventLedgerDirectionsV1", "int", ledger_loop, "Array Index", 2944, 2080)
    same_id = compare(
        "EqualEqual_StrStr", ledger_loop, "Array Element", 2944, 1760,
        right=cue_id, right_pin="Output", kind="string", parent="KismetStringLibrary",
    )
    same_loop = compare(
        "EqualEqual_IntInt", prior_loop, "Output", 3168, 1920,
        right=loop_iteration, right_pin="EventLoopIterationV1",
    )
    same_direction = compare(
        "EqualEqual_IntInt", prior_direction, "Output", 3168, 2080,
        right=direction, right_pin="EventDirectionV1",
    )
    same_context = boolean("BooleanAND", same_loop, "ReturnValue", same_direction, "ReturnValue", 3392, 2000)
    duplicate = boolean("BooleanAND", same_id, "ReturnValue", same_context, "ReturnValue", 3616, 1920)
    duplicate_guard = builder.add("duplicate_entry_guard", "branch", 2944, 4480)
    bp.connect(ledger_loop, "LoopBody", duplicate_guard, "execute")
    bp.connect(duplicate, "ReturnValue", duplicate_guard, "Condition")
    mark_duplicate = set_("EventCandidateAlreadyExecutedV1", "bool", 3168, 4640, "true")
    bp.connect(duplicate_guard, "then", mark_duplicate, "execute")

    duplicate_state = get("EventCandidateAlreadyExecutedV1", "bool", 3840, 2240)
    terminal_duplicate = builder.add("terminal_duplicate_guard", "branch", 3840, 4480)
    bp.connect(ledger_loop, "Completed", terminal_duplicate, "execute")
    bp.connect(duplicate_state, "EventCandidateAlreadyExecutedV1", terminal_duplicate, "Condition")
    duplicate_valid = set_("EventLedgerCommitValidV1", "bool", 4064, 4320, "true")
    duplicate_code = set_("EventDispatchCodeV1", "string", 4288, 4320, "event_ledger_already_committed")
    bp.connect(terminal_duplicate, "then", duplicate_valid, "execute")
    bp.connect(duplicate_valid, "then", duplicate_code, "execute")

    capacity_ready = compare("Less_IntInt", ids_count, "ReturnValue", 4064, 2400, default_b="1024")
    capacity_guard = guard(
        terminal_duplicate, "else", capacity_ready, "ReturnValue",
        "event_ledger_full", 4064, 4640,
    )

    candidate_ids_set = set_("EventLedgerCandidateIdsV1", "string", 4512, 4640, array=True)
    candidate_loops_set = set_("EventLedgerCandidateLoopsV1", "int", 4736, 4640, array=True)
    candidate_directions_set = set_("EventLedgerCandidateDirectionsV1", "int", 4960, 4640, array=True)
    bp.connect(ledger_ids, "EventLedgerIdsV1", candidate_ids_set, "EventLedgerCandidateIdsV1")
    bp.connect(ledger_loops, "EventLedgerLoopsV1", candidate_loops_set, "EventLedgerCandidateLoopsV1")
    bp.connect(ledger_directions, "EventLedgerDirectionsV1", candidate_directions_set, "EventLedgerCandidateDirectionsV1")
    bp.connect(capacity_guard, "then", candidate_ids_set, "execute")
    bp.connect(candidate_ids_set, "then", candidate_loops_set, "execute")
    bp.connect(candidate_loops_set, "then", candidate_directions_set, "execute")

    candidate_ids = get("EventLedgerCandidateIdsV1", "string", 4512, 2720, True)
    candidate_loops = get("EventLedgerCandidateLoopsV1", "int", 4512, 2880, True)
    candidate_directions = get("EventLedgerCandidateDirectionsV1", "int", 4512, 3040, True)
    add_id = array_add(candidate_ids, "EventLedgerCandidateIdsV1", "string", cue_id, "Output", 5184, 4640)
    add_loop = array_add(candidate_loops, "EventLedgerCandidateLoopsV1", "int", loop_iteration, "EventLoopIterationV1", 5408, 4640)
    add_direction = array_add(candidate_directions, "EventLedgerCandidateDirectionsV1", "int", direction, "EventDirectionV1", 5632, 4640)
    bp.connect(candidate_directions_set, "then", add_id, "execute")
    bp.connect(add_id, "then", add_loop, "execute")
    bp.connect(add_loop, "then", add_direction, "execute")

    id_index = compare("EqualEqual_IntInt", add_id, "ReturnValue", 5184, 3200, right=ids_count, right_pin="ReturnValue")
    loop_index = compare("EqualEqual_IntInt", add_loop, "ReturnValue", 5408, 3200, right=ids_count, right_pin="ReturnValue")
    direction_index = compare("EqualEqual_IntInt", add_direction, "ReturnValue", 5632, 3200, right=ids_count, right_pin="ReturnValue")
    index_pair = boolean("BooleanAND", id_index, "ReturnValue", loop_index, "ReturnValue", 5856, 3120)
    candidate_ready = boolean("BooleanAND", index_pair, "ReturnValue", direction_index, "ReturnValue", 6080, 3200)
    candidate_guard = guard(
        add_direction, "then", candidate_ready, "ReturnValue",
        "event_ledger_candidate_invalid", 5856, 4640,
    )

    publish_ids = set_("EventLedgerIdsV1", "string", 6304, 4640, array=True)
    publish_loops = set_("EventLedgerLoopsV1", "int", 6528, 4640, array=True)
    publish_directions = set_("EventLedgerDirectionsV1", "int", 6752, 4640, array=True)
    publish_valid = set_("EventLedgerCommitValidV1", "bool", 6976, 4640, "true")
    publish_code = set_("EventDispatchCodeV1", "string", 7200, 4640, "event_ledger_committed")
    bp.connect(candidate_ids, "EventLedgerCandidateIdsV1", publish_ids, "EventLedgerIdsV1")
    bp.connect(candidate_loops, "EventLedgerCandidateLoopsV1", publish_loops, "EventLedgerLoopsV1")
    bp.connect(candidate_directions, "EventLedgerCandidateDirectionsV1", publish_directions, "EventLedgerDirectionsV1")
    bp.connect(candidate_guard, "then", publish_ids, "execute")
    bp.connect(publish_ids, "then", publish_loops, "execute")
    bp.connect(publish_loops, "then", publish_directions, "execute")
    bp.connect(publish_directions, "then", publish_valid, "execute")
    bp.connect(publish_valid, "then", publish_code, "execute")

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
