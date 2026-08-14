"""Build the result-only reset for camera engine application."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetCameraEngineApplicationResultV1"
ARRAYS = (("CameraApplyUnavailableTargetIdsV1", "string"),)
SCALARS = (
    ("CameraApplyFailureCodeV1", "string", ""),
    ("CameraApplyResultValidV1", "bool", "false"),
    ("CameraApplyScratchTargetIndexV1", "int", "0"),
    ("CameraApplyScratchStageValidV1", "bool", "false"),
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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

    camera_reset = load_module(
        args.project_root / "tools/blueprint/Build-CameraChannelCompileResetGraph.py",
        "edd_camera_engine_application_reset_forms",
    )
    reset = camera_reset.load(args.project_root)
    bp = reset.load(args.project_root)
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(
        args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph"
    )
    sync = bp.read_blocks(
        args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph"
    )
    playback = bp.read_blocks(
        args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph"
    )
    entry = bp.Node.clone(
        "entry",
        bp.find_block(capture, r"K2Node_FunctionEntry"),
        "K2Node_FunctionEntry_0",
        0,
        0,
    )
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")',
        entry.text,
        1,
    )
    array_form = bp.find_block(sync, r'MemberName="DraftWaypointIds"')
    clear_form = bp.find_block(sync, r'MemberName="Array_Clear"')
    setter_form = bp.find_block(playback, r'K2Node_VariableSet.*MemberName="PlaybackActive"')

    nodes = [entry]
    chain = []
    for index, (name, kind) in enumerate(ARRAYS):
        getter = bp.Node.clone(
            f"get_{index}", array_form, f"K2Node_VariableGet_{index}", 256, 256
        )
        camera_reset.string_variable(getter, "DraftWaypointIds", name, True)
        clear = bp.Node.clone(
            f"clear_{index}", clear_form, f"K2Node_CallArrayFunction_{index}", 256, 0
        )
        camera_reset.string_pin(clear, "TargetArray", True)
        bp.connect(getter, name, clear, "TargetArray")
        nodes.extend((getter, clear))
        chain.append(clear)
    for index, (name, kind, value) in enumerate(SCALARS):
        setter = bp.Node.clone(
            f"set_{index}",
            setter_form,
            f"K2Node_VariableSet_{index}",
            672 + index * 416,
            0,
        )
        if kind == "string":
            camera_reset.string_variable(setter, "PlaybackActive", name)
        else:
            reset.variable(setter, "PlaybackActive", name, kind)
        reset.default(setter, name, value)
        nodes.append(setter)
        chain.append(setter)

    bp.connect(entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    full = "\n".join(node.text for node in nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(
                r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)",
                "",
                node.text,
            )
            for node in nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
