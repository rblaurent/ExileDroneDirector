"""Semantic contracts for shared waypoint count/selection feedback."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_contract_helpers():
    helper_path = Path(__file__).with_name("Test-WaypointCaptureContracts.py")
    spec = importlib.util.spec_from_file_location("edd_waypoint_contract_helpers", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_feedback(path: Path) -> None:
    helpers = load_contract_helpers()
    nodes = helpers.parse_graph(path)
    helpers.require(len(nodes) == 51, f"Feedback EventGraph expected 51 nodes; found {len(nodes)}")

    builders = [node for node in nodes.values() if 'MemberName="BuildString_Int"' in node.text]
    helpers.require(len(builders) == 2, f"Feedback needs exactly two BuildString_Int nodes; found {len(builders)}")
    count_builders = [
        node for node in builders
        if 'DefaultValue="[EDD] Draft waypoints: "' in helpers.pin(node, "Prefix").body
    ]
    helpers.require(len(count_builders) == 1, "Feedback needs one count-message builder")
    count_builder = count_builders[0]
    selected_builder = next(node for node in builders if node.name != count_builder.name)
    helpers.require(
        'DefaultValue=" | selected: "' in helpers.pin(count_builder, "Suffix").body,
        "Count builder separator changed",
    )
    def string_default(node, pin_name: str) -> str:
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', helpers.pin(node, pin_name).body)
        return match.group(1) if match else ""

    helpers.require(
        string_default(selected_builder, "Prefix") == ""
        and string_default(selected_builder, "Suffix") == "",
        "Selected-index builder must append only its integer",
    )

    ids = helpers.one(nodes, 'VariableReference=(MemberName="DraftWaypointIds"')
    selected = helpers.one(nodes, 'VariableReference=(MemberName="SelectedWaypointIndex"')
    length = helpers.one(nodes, 'MemberName="Array_Length"')
    helpers.require_link(ids, "DraftWaypointIds", length, "TargetArray", "Draft IDs must drive the count")
    helpers.require_link(length, "ReturnValue", count_builder, "InInt", "Array length must format as the count")
    helpers.require_link(
        count_builder,
        "ReturnValue",
        selected_builder,
        "AppendTo",
        "Selected index must append to the complete count message",
    )
    helpers.require_link(
        selected,
        "SelectedWaypointIndex",
        selected_builder,
        "InInt",
        "Current selection must format as the selected index",
    )

    mutations = [
        helpers.one(nodes, 'MemberName="CaptureCurrentWaypoint"'),
        helpers.one(nodes, 'MemberName="ReplaceSelectedWaypoint"'),
        helpers.one(nodes, 'MemberName="DeleteSelectedWaypoint"'),
    ]
    feedback_prints = []
    for mutation in mutations:
        matches = [
            node
            for node in nodes.values()
            if 'MemberName="PrintString"' in node.text
            and helpers.linked(mutation, "then", node, "execute")
        ]
        helpers.require(len(matches) == 1, f"{mutation.name} must continue to exactly one feedback print")
        feedback = matches[0]
        helpers.require_link(
            mutation,
            "then",
            feedback,
            "execute",
            f"{mutation.name} must execute its feedback print",
        )
        helpers.require_link(
            selected_builder,
            "ReturnValue",
            feedback,
            "InString",
            f"{mutation.name} feedback must display the shared dynamic message",
        )
        helpers.require(not helpers.pin(feedback, "then").links, f"{feedback.name} must terminate its execution path")
        feedback_prints.append(feedback.name)

    helpers.require(len(set(feedback_prints)) == 3, "Each mutation needs a distinct feedback PrintString node")
    helpers.require('ErrorType=' not in "".join(node.text for node in nodes.values()), "Feedback graph retains compiler error metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    args = parser.parse_args()
    assert_feedback(args.event)
    print("Waypoint feedback contracts valid: shared dynamic count/selection after capture, replace, and delete")


if __name__ == "__main__":
    main()
