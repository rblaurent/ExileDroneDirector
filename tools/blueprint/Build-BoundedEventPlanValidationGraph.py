"""Build fail-closed structural validation for the bounded Cue execution plan."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateBoundedEventPlanV1"
CUE_ARRAYS = (
    ("EventCueIdsV1", "string"),
    ("EventCueTimesV1", "real"),
    ("EventCueAdapterIdsV1", "string"),
    ("EventCueAdapterVersionsV1", "int"),
    ("EventCueOperationIdsV1", "string"),
    ("EventCueScopesV1", "string"),
    ("EventCuePayloadsV1", "string"),
    ("EventCueDirectionPoliciesV1", "string"),
    ("EventCueRepeatPoliciesV1", "string"),
    ("EventCueFailurePoliciesV1", "string"),
    ("EventCueBindingIdsV1", "string"),
    ("EventCueBindingRegionsV1", "string"),
    ("EventCueBindingAdapterIdsV1", "string"),
    ("EventCueBindingAdapterVersionsV1", "int"),
    ("EventCueBindingEnabledV1", "bool"),
    ("EventCueBindingReauthorizedV1", "bool"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_event_validation_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory = {
        "bool": ("bool", ""),
        "int": ("int", ""),
        "real": ("real", "double"),
        "string": ("string", ""),
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
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    forms["length"] = bp.find_block(edit, r'MemberName="Array_Length"')
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

    def length(source, source_pin, kind, x, y):
        node = add_form(f"length_{source_pin}_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member, left, left_pin, x, y, *, right=None, right_pin=None, default_b=None, kind="int"):
        node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def and_all(conditions, x, y):
        current = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            current = compare(
                "BooleanAND", current, "ReturnValue", x + index * 224, y,
                right=condition, right_pin="ReturnValue", kind="bool",
            )
        return current

    stage_false = set_("EventPlanValidationValidV1", "bool", 256, 3520, "false")
    failure = set_("EventDispatchCodeV1", "string", 480, 3520, "event_plan_invalid")
    bp.connect(builder.entry, "then", stage_false, "execute")
    bp.connect(stage_false, "then", failure, "execute")

    arrays = {
        name: get(name, kind, 0, index * 160, True)
        for index, (name, kind) in enumerate(CUE_ARRAYS)
    }
    lengths = {
        name: length(arrays[name], name, kind, 256, index * 160)
        for index, (name, kind) in enumerate(CUE_ARRAYS)
    }
    cue_count = lengths[CUE_ARRAYS[0][0]]
    plan_authority = get("EventCuePlanValidV1", "bool", 0, 2720)
    immutable = get("EventImmutableRevisionV1", "int", 0, 2880)
    requested = get("EventRequestedRevisionV1", "int", 0, 3040)
    playback = get("EventPlaybackStartedV1", "bool", 0, 3200)
    scrubbing = get("EventScrubbingV1", "bool", 0, 3360)
    previous = get("EventPreviousTimeV1", "real", 0, 3520)
    current = get("EventCurrentTimeV1", "real", 0, 3680)
    loop = get("EventLoopIterationV1", "int", 0, 3840)
    direction = get("EventDirectionV1", "int", 0, 4000)
    resolved_ids = get("EventResolvedBindingIdsV1", "string", 0, 4160, True)
    resolved_distances = get("EventResolvedBindingDistancesV1", "real", 0, 4320, True)
    permissions = get("EventGrantedPermissionsV1", "string", 0, 4480, True)
    rate = get("EventRemainingRateBudgetV1", "int", 0, 4640)
    resolved_id_count = length(resolved_ids, "EventResolvedBindingIdsV1", "string", 256, 4160)
    resolved_distance_count = length(resolved_distances, "EventResolvedBindingDistancesV1", "real", 256, 4320)
    permission_count = length(permissions, "EventGrantedPermissionsV1", "string", 256, 4480)

    plan_ready = compare(
        "BooleanAND", plan_authority, "EventCuePlanValidV1", 704, 2720,
        right=plan_authority, right_pin="EventCuePlanValidV1", kind="bool",
    )
    conditions = [
        plan_ready,
        compare("GreaterEqual_IntInt", cue_count, "ReturnValue", 704, 0, default_b="1"),
        compare("LessEqual_IntInt", cue_count, "ReturnValue", 704, 160, default_b="256"),
    ]
    for index, (name, _kind) in enumerate(CUE_ARRAYS[1:]):
        conditions.append(compare(
            "EqualEqual_IntInt", lengths[name], "ReturnValue", 704,
            320 + index * 160, right=cue_count, right_pin="ReturnValue",
        ))
    conditions.extend((
        compare("Greater_IntInt", immutable, "EventImmutableRevisionV1", 704, 2880, default_b="0"),
        compare("EqualEqual_IntInt", requested, "EventRequestedRevisionV1", 704, 3040, right=immutable, right_pin="EventImmutableRevisionV1"),
        compare("BooleanOR", playback, "EventPlaybackStartedV1", 704, 3280, right=scrubbing, right_pin="EventScrubbingV1", kind="bool"),
        builder.finite(previous, "EventPreviousTimeV1", 704, 3520),
        builder.finite(current, "EventCurrentTimeV1", 704, 3680),
        compare("GreaterEqual_IntInt", loop, "EventLoopIterationV1", 704, 3840, default_b="0"),
    ))
    direction_forward = compare("EqualEqual_IntInt", direction, "EventDirectionV1", 704, 4000, default_b="1")
    direction_reverse = compare("EqualEqual_IntInt", direction, "EventDirectionV1", 928, 4000, default_b="-1")
    conditions.append(compare(
        "BooleanOR", direction_forward, "ReturnValue", 1152, 4000,
        right=direction_reverse, right_pin="ReturnValue", kind="bool",
    ))
    conditions.extend((
        compare("EqualEqual_IntInt", resolved_id_count, "ReturnValue", 704, 4160, right=resolved_distance_count, right_pin="ReturnValue"),
        compare("LessEqual_IntInt", resolved_id_count, "ReturnValue", 704, 4320, default_b="256"),
        compare("LessEqual_IntInt", permission_count, "ReturnValue", 704, 4480, default_b="64"),
        compare("GreaterEqual_IntInt", rate, "EventRemainingRateBudgetV1", 704, 4640, default_b="0"),
    ))
    ready = and_all(conditions, 1408, 2400)
    branch = builder.add("validation_branch", "branch", 7488, 3520)
    bp.connect(failure, "then", branch, "execute")
    bp.connect(ready, "ReturnValue", branch, "Condition")
    stage_true = set_("EventPlanValidationValidV1", "bool", 7712, 3440, "true")
    success = set_("EventDispatchCodeV1", "string", 7936, 3440, "")
    bp.connect(branch, "then", stage_true, "execute")
    bp.connect(stage_true, "then", success, "execute")

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
