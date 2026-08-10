"""Semantic contracts for Ctrl+Z/Ctrl+Y history dispatch and diagnostics."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load_helpers():
    path = Path(__file__).with_name("Test-WaypointCaptureContracts.py")
    spec = importlib.util.spec_from_file_location("edd_history_dispatch_contract_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_dispatch(path: Path) -> None:
    h = load_helpers()
    nodes = h.parse_graph(path)
    h.require(len(nodes) == 86, f"History EventGraph expected 86 nodes; found {len(nodes)}")

    def calls(function: str):
        return [node for node in nodes.values() if f'MemberName="{function}"' in node.text]

    def one_call(function: str):
        matches = calls(function)
        h.require(len(matches) == 1, f"Expected one {function} call; found {len(matches)}")
        return matches[0]

    def poll(function: str, key: str):
        matches = [
            node for node in nodes.values()
            if f'MemberName="{function}"' in node.text and f'DefaultValue="{key}"' in h.pin(node, "Key").body
        ]
        h.require(len(matches) == 1, f"Expected one {function} poll for {key}; found {len(matches)}")
        return matches[0]

    def condition_branch(source, label: str):
        matches = [
            node for node in nodes.values()
            if node.node_class.endswith("K2Node_IfThenElse") and h.linked(source, "ReturnValue", node, "Condition")
        ]
        h.require(len(matches) == 1, f"{label} must drive exactly one branch; found {len(matches)}")
        return matches[0]

    left = poll("IsInputKeyDown", "LeftControl")
    right = poll("IsInputKeyDown", "RightControl")
    z_poll = poll("WasInputKeyJustPressed", "Z")
    y_poll = poll("WasInputKeyJustPressed", "Y")
    left_branch = condition_branch(left, "LeftControl")
    right_branch = condition_branch(right, "RightControl")
    z_branch = condition_branch(z_poll, "Z edge")
    y_branch = condition_branch(y_poll, "Y edge")

    controllers = [
        node for node in nodes.values()
        if 'MemberName="GetPlayerController"' in node.text
        and all(h.linked(node, "ReturnValue", target, "self") for target in (left, right, z_poll, y_poll))
    ]
    h.require(len(controllers) == 1, "History polls must reuse one local player-controller getter")
    h.require('DefaultValue="0"' in h.pin(controllers[0], "PlayerIndex").body, "History controller index must be zero")

    playback_active = h.one(nodes, 'VariableReference=(MemberName="PlaybackActive"')
    speed = one_call("UpdateSpeedControls")
    playback_update = one_call("UpdateLinearPlayback")
    manual_branch = [
        node for node in nodes.values()
        if node.node_class.endswith("K2Node_IfThenElse")
        and h.linked(playback_active, "PlaybackActive", node, "Condition")
        and h.linked(node, "then", playback_update, "execute")
    ]
    h.require(len(manual_branch) == 1, "Inactive playback must enter history arbitration before manual flight")
    h.require_link(manual_branch[0], "else", left_branch, "execute", "History arbitration must start with LeftControl")
    h.require_link(left_branch, "else", right_branch, "execute", "LeftControl false must test RightControl")
    h.require_link(left_branch, "then", z_branch, "execute", "LeftControl true must enter history keys")
    h.require_link(right_branch, "then", z_branch, "execute", "RightControl true must enter history keys")
    h.require_link(right_branch, "else", speed, "execute", "No Ctrl must preserve manual flight")
    h.require_link(z_branch, "else", y_branch, "execute", "Ctrl without Z must test Y")
    h.require_link(y_branch, "else", speed, "execute", "Ctrl without Z/Y must preserve precision flight")

    status_build = h.one(nodes, 'DefaultValue=" | selected: "')

    def assert_side(side: str, edge_branch, success_text: str, empty_text: str):
        title = side.title()
        documents = h.one(nodes, f'VariableReference=(MemberName="{title}DocumentsV1"')
        length = next(
            node for node in nodes.values()
            if 'MemberName="Array_Length"' in node.text and h.linked(documents, f"{title}DocumentsV1", node, "TargetArray")
        )
        available = next(
            node for node in nodes.values()
            if 'MemberName="Greater_IntInt"' in node.text and h.linked(length, "ReturnValue", node, "A")
        )
        availability_branch = condition_branch(available, f"{title} availability")
        h.require_link(edge_branch, "then", availability_branch, "execute", f"Ctrl+{side[-1].upper()} must test {side} availability")
        action = one_call(f"{title}DraftV1")
        h.require_link(availability_branch, "then", action, "execute", f"Available {side} must execute")
        success = h.one(nodes, f'DefaultValue="{success_text}"')
        empty = h.one(nodes, f'DefaultValue="{empty_text}"')
        h.require_link(availability_branch, "else", empty, "execute", f"Empty {side} must log rejection")
        h.require_link(action, "then", success, "execute", f"Applied {side} must log acceptance")
        status_prints = [
            node for node in nodes.values()
            if 'MemberName="PrintString"' in node.text
            and h.linked(success, "then", node, "execute")
            and h.linked(status_build, "ReturnValue", node, "InString")
        ]
        h.require(len(status_prints) == 1, f"Applied {side} must emit resulting count/selection")
        h.require(not h.pin(status_prints[0], "then").links, f"Applied {side} must terminate the tick")
        h.require(not h.pin(empty, "then").links, f"Rejected {side} must terminate the tick")

    assert_side("undo", z_branch, "[EDD] Undo applied", "[EDD] Undo ignored: history empty")
    assert_side("redo", y_branch, "[EDD] Redo applied", "[EDD] Redo ignored: history empty")
    h.require('ErrorType=' not in "".join(node.text for node in nodes.values()), "History graph retains compiler error metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    args = parser.parse_args()
    assert_dispatch(args.event)
    print("Draft history dispatch contracts valid: Ctrl+Z/Y arbitration and accepted/rejected diagnostics")


if __name__ == "__main__":
    main()
