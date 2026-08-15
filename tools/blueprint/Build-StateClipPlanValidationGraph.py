"""Build fail-closed structural validation for an accepted State Clip plan."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateStateClipPlanV1"
ARRAYS = (
    ("StateClipIdsV1", "string"),
    ("StateClipStartTimesV1", "real"),
    ("StateClipEndTimesV1", "real"),
    ("StateClipDesiredStatesV1", "string"),
    ("StateClipEnterLeadSecondsV1", "real"),
    ("StateClipExitLeadSecondsV1", "real"),
    ("StateClipScopesV1", "string"),
    ("StateClipRestorePoliciesV1", "string"),
    ("StateClipConflictPoliciesV1", "string"),
    ("StateClipFailurePoliciesV1", "string"),
    ("StateClipTimeoutSecondsV1", "real"),
    ("StateClipPreviewPoliciesV1", "string"),
    ("StateClipBindingIdsV1", "string"),
    ("StateClipBindingTypesV1", "string"),
    ("StateClipBindingRegionsV1", "string"),
    ("StateClipBindingAdapterIdsV1", "string"),
    ("StateClipBindingAdapterVersionsV1", "int"),
    ("StateClipBindingEnabledV1", "bool"),
    ("StateClipBindingReauthorizedV1", "bool"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_state_clip_validation_base", path)
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

    def set_(name, x, y, value):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, "bool")
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
        current = conditions[0][0]
        current_pin = conditions[0][1]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            current = compare(
                "BooleanAND", current, current_pin, x + index * 224, y,
                right=condition, right_pin=condition_pin, kind="bool",
            )
            current_pin = "ReturnValue"
        return current

    stage_false = set_("StateClipValidationValidV1", 256, 3360, "false")
    bp.connect(builder.entry, "then", stage_false, "execute")
    arrays = {name: get(name, kind, 0, index * 160, True) for index, (name, kind) in enumerate(ARRAYS)}
    lengths = {name: length(arrays[name], name, kind, 256, index * 160) for index, (name, kind) in enumerate(ARRAYS)}
    count = lengths[ARRAYS[0][0]]
    authority = get("StateClipPlanValidV1", "bool", 0, 3120)
    duration = get("StateClipPlanDurationV1", "real", 0, 3280)
    conditions = [(authority, "StateClipPlanValidV1")]
    conditions.append((compare("LessEqual_IntInt", count, "ReturnValue", 704, 0, default_b="128"), "ReturnValue"))
    for index, (name, _kind) in enumerate(ARRAYS[1:]):
        conditions.append((compare(
            "EqualEqual_IntInt", lengths[name], "ReturnValue", 704, 160 + index * 160,
            right=count, right_pin="ReturnValue",
        ), "ReturnValue"))
    conditions.append((builder.finite(duration, "StateClipPlanDurationV1", 704, 3120), "ReturnValue"))
    conditions.append((compare(
        "GreaterEqual_DoubleDouble", duration, "StateClipPlanDurationV1", 704, 3280,
        default_b="0.0", kind="real",
    ), "ReturnValue"))
    ready = and_all(conditions, 1408, 2400)
    branch = builder.add("validation_branch", "branch", 6336, 3360)
    bp.connect(stage_false, "then", branch, "execute")
    bp.connect(ready, "ReturnValue", branch, "Condition")
    stage_true = set_("StateClipValidationValidV1", 6560, 3280, "true")
    bp.connect(branch, "then", stage_true, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
