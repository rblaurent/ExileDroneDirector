"""Build the fail-closed bounded event-dispatch result reset graph."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetBoundedEventDispatchResultV1"
SCALARS = (
    ("EventPlanValidationValidV1", "bool", "false"),
    ("EventCrossingCollectionValidV1", "bool", "false"),
    ("EventSelectionValidV1", "bool", "false"),
    ("EventCandidateAlreadyExecutedV1", "bool", "false"),
    ("EventDispatchResultValidV1", "bool", "false"),
    ("EventDispatchAuthorizedV1", "bool", "false"),
    ("EventDispatchIndexV1", "int", "-1"),
    ("EventDispatchCodeV1", "string", "event_dispatch_unavailable"),
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()

    camera = load(
        args.project_root / "tools/blueprint/Build-CameraChannelCompileResetGraph.py",
        "edd_event_reset_camera",
    )
    reset = camera.load(args.project_root)
    bp = reset.load(args.project_root)
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(
        args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph"
    )
    start = bp.read_blocks(
        args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph"
    )
    entry = bp.Node.clone(
        "entry", bp.find_block(capture, r"K2Node_FunctionEntry"),
        "K2Node_FunctionEntry_0", 0, 0,
    )
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1,
    )
    scalar_form = bp.find_block(
        start, r'K2Node_VariableSet.*MemberName="PlaybackActive"'
    )
    nodes = [entry]
    setters = []
    for index, (name, kind, value) in enumerate(SCALARS):
        node = bp.Node.clone(
            f"set_{index}", scalar_form, f"K2Node_VariableSet_{index}",
            256 + index * 416, 0,
        )
        if kind == "string":
            camera.string_variable(node, "PlaybackActive", name)
        else:
            reset.variable(node, "PlaybackActive", name, kind)
        reset.default(node, name, value)
        nodes.append(node)
        setters.append(node)
    bp.connect(entry, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
        bp.connect(left, "then", right, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
