"""Semantic contracts for EventGraph linear-playback arbitration."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_helpers():
    path = Path(__file__).with_name("Test-WaypointCaptureContracts.py")
    spec = importlib.util.spec_from_file_location("edd_playback_dispatch_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_dispatch(path: Path) -> None:
    h = load_helpers()
    nodes = h.parse_graph(path)
    h.require(len(nodes) == 62, f"Playback EventGraph expected 62 nodes; found {len(nodes)}")

    def calls(function: str):
        return [node for node in nodes.values() if f'MemberName="{function}"' in node.text]

    def one_call(function: str):
        matches = calls(function)
        h.require(len(matches) == 1, f"Expected one {function} call; found {len(matches)}")
        return matches[0]

    def key_poll(key: str):
        matches = [
            node
            for node in nodes.values()
            if 'MemberName="WasInputKeyJustPressed"' in node.text
            and f'DefaultValue="{key}"' in h.pin(node, "Key").body
        ]
        h.require(len(matches) == 1, f"Expected one {key} edge poll; found {len(matches)}")
        return matches[0]

    def driven_branch(source, source_pin: str, label: str):
        matches = [
            node
            for node in nodes.values()
            if node.node_class.endswith("K2Node_IfThenElse")
            and h.linked(source, source_pin, node, "Condition")
        ]
        h.require(len(matches) == 1, f"{label} must drive exactly one branch; found {len(matches)}")
        return matches[0]

    p_poll = key_poll("P")
    p_branch = driven_branch(p_poll, "ReturnValue", "P edge")
    active = h.one(nodes, 'VariableReference=(MemberName="PlaybackActive"')
    active_branches = [
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_IfThenElse")
        and h.linked(active, "PlaybackActive", node, "Condition")
    ]
    h.require(len(active_branches) == 2, "PlaybackActive must drive the toggle and tick arbitration branches")

    start = one_call("StartLinearPlayback")
    update = one_call("UpdateLinearPlayback")
    speed = one_call("UpdateSpeedControls")
    stop_calls = calls("StopLinearPlayback")
    h.require(len(stop_calls) == 4, f"Expected four StopLinearPlayback calls; found {len(stop_calls)}")

    toggle_candidates = [
        branch
        for branch in active_branches
        if h.linked(branch, "else", start, "execute")
        and any(h.linked(branch, "then", stop, "execute") for stop in stop_calls)
    ]
    h.require(len(toggle_candidates) == 1, "P true must choose Start when inactive and Stop when active")
    toggle_branch = toggle_candidates[0]
    toggle_stop = next(stop for stop in stop_calls if h.linked(toggle_branch, "then", stop, "execute"))
    h.require_link(p_branch, "then", toggle_branch, "execute", "P true must enter only the toggle chooser")
    h.require(not h.pin(start, "then").links, "Start toggle must terminate the current tick")
    h.require(not h.pin(toggle_stop, "then").links, "Stop toggle must terminate the current tick")

    update_candidates = [
        branch
        for branch in active_branches
        if h.linked(branch, "then", update, "execute")
        and h.linked(branch, "else", speed, "execute")
    ]
    h.require(len(update_candidates) == 1, "Tick arbitration must update playback when active and manual flight when inactive")
    update_branch = update_candidates[0]
    h.require_link(p_branch, "else", update_branch, "execute", "Only a tick without a P edge may update movement")
    h.require(not h.pin(update, "then").links, "Playback update must suppress all manual/edit controls for the tick")

    valid_camera_branch = next(
        node
        for node in nodes.values()
        if node.node_class.endswith("K2Node_IfThenElse")
        and any('MemberName="IsValid"' in other.text and h.linked(other, "ReturnValue", node, "Condition") for other in nodes.values())
    )
    h.require_link(valid_camera_branch, "then", p_branch, "execute", "P arbitration must be the first valid-camera action")
    h.require(not h.linked(valid_camera_branch, "then", speed, "execute"), "Valid-camera ticks must not bypass playback arbitration")

    controllers = [
        node
        for node in nodes.values()
        if 'MemberName="GetPlayerController"' in node.text
        and h.linked(node, "ReturnValue", p_poll, "self")
    ]
    h.require(len(controllers) == 1, "P must reuse one local player-controller getter")
    h.require('DefaultValue="0"' in h.pin(controllers[0], "PlayerIndex").body, "P controller index must remain zero")

    exits = calls("ExitDroneMode") + calls("EmergencyExitDroneMode")
    h.require(len(exits) == 3, f"Expected three drone exit calls; found {len(exits)}")
    cleanup_stops = []
    for exit_call in exits:
        predecessors = [stop for stop in stop_calls if h.linked(stop, "then", exit_call, "execute")]
        h.require(len(predecessors) == 1, f"{exit_call.name} must have exactly one playback cleanup predecessor")
        cleanup_stops.extend(predecessors)
    h.require(len({node.name for node in cleanup_stops}) == 3, "Each exit path needs a distinct playback cleanup call")
    h.require(toggle_stop.name not in {node.name for node in cleanup_stops}, "Toggle stop cannot double as exit cleanup")

    capture = one_call("CaptureCurrentWaypoint")
    replace = one_call("ReplaceSelectedWaypoint")
    delete = one_call("DeleteSelectedWaypoint")
    for mutation in (capture, replace, delete):
        feedback = [
            node
            for node in nodes.values()
            if 'MemberName="PrintString"' in node.text and h.linked(mutation, "then", node, "execute")
        ]
        h.require(len(feedback) == 1, f"{mutation.name} feedback path must survive playback dispatch")

    h.require('ErrorType=' not in "".join(node.text for node in nodes.values()), "Playback graph retains compiler error metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    args = parser.parse_args()
    assert_dispatch(args.event)
    print("Linear playback dispatch contracts valid: P arbitration, manual suppression, and exit cleanup")


if __name__ == "__main__":
    main()
