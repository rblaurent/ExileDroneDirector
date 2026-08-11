"""Semantic graph contracts for repository document and record validation."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_validation_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nodes_with(nodes, marker: str):
    return [node for node in nodes.values() if marker in node.text]


def nodes_of(nodes, class_name: str):
    return [node for node in nodes.values() if class_name in node.node_class]


def one(c, nodes, marker: str):
    matches = nodes_with(nodes, marker)
    c.require(len(matches) == 1, f"Expected one {marker}; found {len(matches)}")
    return matches[0]


def call(c, nodes, name: str):
    matches = [
        node for node in nodes.values()
        if ("K2Node_CallFunction" in node.node_class or "K2Node_CallArrayFunction" in node.node_class)
        and re.search(rf'MemberName="{re.escape(name)}"', node.text)
    ]
    c.require(len(matches) == 1, f"Expected one call to {name}; found {len(matches)}")
    return matches[0]


def calls(nodes, name: str):
    return [
        node for node in nodes.values()
        if ("K2Node_CallFunction" in node.node_class or "K2Node_CallArrayFunction" in node.node_class)
        and f'MemberName="{name}"' in node.text
    ]


def variables(nodes, name: str, node_class: str | None = None):
    return [
        node for node in nodes.values()
        if (node_class is None or node_class in node.node_class)
        and f'VariableReference=(MemberName="{name}"' in node.text
    ]


def default(c, node, pin_name: str, expected: str) -> None:
    body = c.pin(node, pin_name).body
    c.require(
        re.search(rf'(?:^|,)DefaultValue="{re.escape(expected)}"(?:,|$)', body) is not None,
        f"{node.name}.{pin_name} default changed",
    )


def assert_closed(c, nodes, expected: int, function: str, paste: bool) -> None:
    c.require(len(nodes) == expected, f"{function}: expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _ in pin.links
        if target not in known
    }
    c.require(not external, f"{function}: external links {sorted(external)}")
    entries = nodes_of(nodes, "K2Node_FunctionEntry")
    c.require(len(entries) == (0 if paste else 1), f"{function}: entry count changed")
    if paste:
        executable = [node for node in nodes.values() if "execute" in node.pins]
        roots = [node for node in executable if not node.pins["execute"].links]
        c.require(roots, f"{function}: paste body exposes no execution seam")
    else:
        c.require(f'MemberName="{function}"' in entries[0].text, f"{function}: wrong entry")
    text = "\n".join(node.text for node in nodes.values())
    c.require("bOrphanedPin=True" not in text, f"{function}: orphaned pin")
    c.require("/Core/Client/BPC_EDD_ClientDirector" not in text, f"{function}: client self leak")


def assert_waypoint(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 65 if paste else 66, "ValidateWaypointV1", paste)
    branches = nodes_of(nodes, "K2Node_IfThenElse")
    c.require(len(branches) == 1, "Waypoint validator branch count changed")
    branch = branches[0]
    invalid = variables(nodes, "ScratchValidV1", "K2Node_VariableSet")
    c.require(len(invalid) == 1, "Waypoint validator must only invalidate")
    default(c, invalid[0], "ScratchValidV1", "false")
    c.require_link(branch, "else", invalid[0], "execute", "Invalid waypoint path changed")
    c.require(len(calls(nodes, "Subtract_DoubleDouble")) == 11, "Waypoint finite coverage changed")
    c.require(len(calls(nodes, "BooleanAND")) == 19, "Waypoint conjunction coverage changed")
    c.require(len(calls(nodes, "Greater_DoubleDouble")) == 2, "Positive lens checks changed")
    c.require(len(calls(nodes, "GreaterEqual_DoubleDouble")) == 2, "Non-negative camera checks changed")
    c.require(len(calls(nodes, "EqualEqual_DoubleDouble")) == 14, "Finite/unit-scale checks changed")
    find_id = call(c, nodes, "Array_Find")
    add_id = call(c, nodes, "Array_Add")
    id_array = variables(nodes, "ScratchIntegerArrayV1", "K2Node_VariableGet")
    c.require(len(id_array) == 1, "Waypoint seen-ID array changed")
    c.require_link(id_array[0], "ScratchIntegerArrayV1", find_id, "TargetArray", "Waypoint duplicate lookup changed")
    c.require_link(id_array[0], "ScratchIntegerArrayV1", add_id, "TargetArray", "Waypoint ID commit changed")
    duration_set = variables(nodes, "ScratchCalculatedDurationV1", "K2Node_VariableSet")
    c.require(len(duration_set) == 1, "Waypoint hold accumulator changed")
    c.require_link(branch, "then", add_id, "execute", "Valid waypoint must commit its ID")
    c.require_link(add_id, "then", duration_set[0], "execute", "Waypoint duration order changed")


def assert_segment(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 39 if paste else 40, "ValidateSegmentV1", paste)
    branches = nodes_of(nodes, "K2Node_IfThenElse")
    c.require(len(branches) == 2, "Segment validator must guard indices and values")
    c.require(len(calls(nodes, "Array_IsValidIndex")) == 2, "Segment adjacency index guards changed")
    c.require(len(nodes_of(nodes, "K2Node_GetArrayItem")) == 2, "Segment adjacency reads changed")
    invalid = variables(nodes, "ScratchValidV1", "K2Node_VariableSet")
    c.require(len(invalid) == 2, "Segment invalid exits changed")
    for node in invalid:
        default(c, node, "ScratchValidV1", "false")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 3, "Segment ID/topology checks changed")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 2, "Segment curve/time text checks changed")
    c.require(len(calls(nodes, "Subtract_DoubleDouble")) == 1, "Segment finite duration check changed")
    find_id = call(c, nodes, "Array_Find")
    add_id = call(c, nodes, "Array_Add")
    ids = variables(nodes, "ScratchIntegerArrayV1", "K2Node_VariableGet")
    c.require(len(ids) == 1, "Segment seen-ID array changed")
    c.require_link(ids[0], "ScratchIntegerArrayV1", find_id, "TargetArray", "Segment duplicate lookup changed")
    c.require_link(ids[0], "ScratchIntegerArrayV1", add_id, "TargetArray", "Segment ID commit changed")
    duration_set = variables(nodes, "ScratchCalculatedDurationV1", "K2Node_VariableSet")
    c.require(len(duration_set) == 1, "Segment duration accumulator changed")
    c.require_link(add_id, "then", duration_set[0], "execute", "Segment duration order changed")


def assert_document(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 46 if paste else 47, "ValidateDocumentV1", paste)
    loops = nodes_of(nodes, "K2Node_MacroInstance")
    c.require(len(loops) == 2, "Document validator must scan waypoint and segment arrays")
    call(c, nodes, "ValidateWaypointV1")
    call(c, nodes, "ValidateSegmentV1")
    c.require(len(calls(nodes, "Array_Clear")) == 2, "Document seen-ID resets changed")
    c.require(len(calls(nodes, "Array_Length")) == 2, "Document topology lengths changed")
    c.require(not calls(nodes, "Max_IntInt"), "Document topology must not use the DevKit-fragile Max_IntInt node")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 5, "Document version/topology checks changed")
    c.require(len(calls(nodes, "Greater_IntInt")) == 2, "Document revision/topology positivity checks changed")
    topology_or = calls(nodes, "BooleanOR")
    c.require(len(topology_or) == 1, "Document empty/nonempty topology alternatives changed")
    topology_ands = [
        node for node in calls(nodes, "BooleanAND")
        if c.linked(node, "ReturnValue", topology_or[0], "A")
        or c.linked(node, "ReturnValue", topology_or[0], "B")
    ]
    c.require(len(topology_ands) == 2, "Document topology alternatives must both feed the topology OR")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 2, "Document required text checks changed")
    call(c, nodes, "Subtract_DoubleDouble")
    valid_setters = variables(nodes, "ScratchValidV1", "K2Node_VariableSet")
    c.require(len(valid_setters) == 2, "Document root/final validity commits changed")
    duration_reset = variables(nodes, "ScratchCalculatedDurationV1", "K2Node_VariableSet")
    c.require(len(duration_reset) == 1, "Document duration reset changed")
    default(c, duration_reset[0], "ScratchCalculatedDurationV1", "0.0")
    prior_valid = variables(nodes, "ScratchValidV1", "K2Node_VariableGet")
    c.require(len(prior_valid) == 1, "Document final validity read changed")
    final_ands = [
        node for node in calls(nodes, "BooleanAND")
        if c.linked(prior_valid[0], "ScratchValidV1", node, "A")
    ]
    c.require(len(final_ands) == 1, "Document final validity conjunction changed")
    final_equal = [
        node for node in calls(nodes, "EqualEqual_DoubleDouble")
        if c.linked(node, "ReturnValue", final_ands[0], "B")
    ]
    c.require(len(final_equal) == 1, "Cached duration must gate final validity")
    final_set = [
        node for node in valid_setters
        if c.linked(final_ands[0], "ReturnValue", node, "ScratchValidV1")
    ]
    c.require(len(final_set) == 1, "Document validity must preserve prior failures and duration equality")


def assert_record_published(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 17 if paste else 18, "ValidateRecordPublishedV1", paste)
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 2, "Published validator branch count changed")
    call(c, nodes, "ValidateDocumentV1")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 1, "Published revision equality changed")
    call(c, nodes, "LessEqual_IntInt")
    call(c, nodes, "EqualEqual_StrStr")
    store = variables(nodes, "ScratchValidV1", "K2Node_VariableSet")
    c.require(len(store) == 1, "Published validator must commit one semantic result")


def assert_record_source(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 11 if paste else 12, "ValidateRecordSourceAttributionV1", paste)
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 1, "Source optional branch changed")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 2, "Source required text checks changed")
    call(c, nodes, "Greater_IntInt")
    store = variables(nodes, "ScratchValidV1", "K2Node_VariableSet")
    c.require(len(store) == 1, "Source validator must commit one semantic result")


def assert_record(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes, 46 if paste else 47, "ValidateRecordV1", paste)
    c.require(len(nodes_of(nodes, "K2Node_IfThenElse")) == 4, "Record guard topology changed")
    c.require(len(calls(nodes, "NotEqual_StrStr")) == 6, "Record required field checks changed")
    c.require(len(calls(nodes, "EqualEqual_StrStr")) == 3, "Record visibility/region checks changed")
    c.require(len(calls(nodes, "EqualEqual_IntInt")) == 1, "Record draft revision check changed")
    call(c, nodes, "ValidateDocumentV1")
    call(c, nodes, "ValidateRecordPublishedV1")
    call(c, nodes, "ValidateRecordSourceAttributionV1")
    c.require(len(calls(nodes, "BooleanOR")) == 2, "Visibility/publication policy changed")
    invalid = [
        node for node in variables(nodes, "ScratchValidV1", "K2Node_VariableSet")
        if re.search(
            r'(?:^|,)DefaultValue="false"(?:,|$)',
            c.pin(node, "ScratchValidV1").body,
        )
    ]
    c.require(len(invalid) == 1, "Public-without-snapshot rejection changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    specs = (
        ("validate-waypoint-v1", assert_waypoint),
        ("validate-segment-v1", assert_segment),
        ("validate-document-v1", assert_document),
        ("validate-record-published-v1", assert_record_published),
        ("validate-record-source-attribution-v1", assert_record_source),
        ("validate-record-v1", assert_record),
    )
    for filename, assertion in specs:
        assertion(c, c.parse_graph(args.input_dir / f"{filename}{suffix}.eddgraph"), args.paste)
    print("Repository validation graph contracts passed")


if __name__ == "__main__":
    main()
