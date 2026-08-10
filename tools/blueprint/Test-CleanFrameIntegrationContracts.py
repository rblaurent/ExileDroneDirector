"""Semantic contracts for Clean Frame exit restoration and F7 dispatch."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_helpers(root: Path):
    path = root / "tools" / "blueprint" / "Test-PathPreviewContracts.py"
    spec = importlib.util.spec_from_file_location("edd_clean_frame_integration_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def one(c, nodes, pattern: str, label: str):
    matches = [node for node in nodes.values() if re.search(pattern, node.text)]
    c.require(len(matches) == 1, f"Expected one {label}; found {len(matches)}")
    return matches[0]


def assert_closed(c, nodes) -> None:
    known = set(nodes)
    external = sorted(
        {
            target
            for node in nodes.values()
            for pin in node.pins.values()
            for target, _ in pin.links
            if target not in known
        }
    )
    c.require(not external, f"Graph contains external links: {external}")


def assert_exit(c, nodes, paste: bool) -> None:
    assert_closed(c, nodes)
    restore = one(c, nodes, r'MemberName="ExitCleanFrameV1"', "Clean Frame restore")
    destroy = one(c, nodes, r'MemberName="DestroyPathPreviewV1"', "preview destroy")
    c.require_link(restore, "then", destroy, "execute", "Clean Frame must restore before preview teardown")
    if paste:
        c.require(not restore.pins["execute"].links, "Paste body must expose Clean Frame restore")
    else:
        entry = one(c, nodes, r'FunctionReference=\(MemberName="ExitDroneMode"\)', "ExitDroneMode entry")
        c.require_link(entry, "then", restore, "execute", "Normal exit must always restore Clean Frame")


def assert_dispatch(c, nodes) -> None:
    assert_closed(c, nodes)
    poll = one(c, nodes, r'DefaultValue="F7"', "F7 poll")
    toggle = one(c, nodes, r'MemberName="ToggleCleanFrameV1"', "Clean Frame toggle")
    camera_guard = nodes["K2Node_IfThenElse_4"]
    playback_dispatch = nodes["K2Node_IfThenElse_9"]
    branch = c.linked_target(nodes, poll, "ReturnValue", "Condition", "K2Node_IfThenElse")
    c.require_link(camera_guard, "then", branch, "execute", "F7 must follow camera validity")
    c.require_link(branch, "then", toggle, "execute", "F7 must toggle Clean Frame")
    c.require_link(branch, "else", playback_dispatch, "execute", "Non-F7 ticks must retain playback dispatch")
    c.require(not toggle.pins["then"].links, "F7 toggle must terminate the tick")
    controller = nodes["K2Node_CallFunction_15"]
    c.require_link(controller, "ReturnValue", poll, "self", "F7 must poll the owning local controller")
    playback = one(c, nodes, r'VariableReference=\(MemberName="PlaybackActive"', "playback state")
    c.require(
        all(target != branch.name for target, _ in playback.pins["PlaybackActive"].links),
        "Clean Frame dispatch must not be gated by playback state",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--exit", type=Path, required=True)
    parser.add_argument("--dispatch", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_helpers(args.project_root)
    assert_exit(c, c.parse(args.exit), args.paste)
    if not args.paste:
        assert_dispatch(c, c.parse(args.dispatch))
    print("Clean Frame integration contracts passed")


if __name__ == "__main__":
    main()
