"""Build the fail-closed State Clip evaluation reset graph."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetStateClipEvaluationV1"
ARRAYS = (
    ("StateClipCandidateIdsV1", "string"),
    ("StateClipCandidateBindingIdsV1", "string"),
    ("StateClipCandidateAdapterIdsV1", "string"),
    ("StateClipCandidateAdapterVersionsV1", "int"),
    ("StateClipCandidateDesiredStatesV1", "string"),
    ("StateClipCandidateScopesV1", "string"),
    ("StateClipCandidateRestorePoliciesV1", "string"),
    ("StateClipCandidatePreviewAllowedV1", "bool"),
    ("StateClipCandidateCodesV1", "string"),
)
SCALARS = (
    ("StateClipValidationValidV1", "bool", "false"),
    ("StateClipCollectionValidV1", "bool", "false"),
    ("StateClipCommitValidV1", "bool", "false"),
    ("StateClipCandidateValidV1", "bool", "false"),
    ("StateClipCurrentActiveV1", "bool", "false"),
    ("StateClipResultValidV1", "bool", "false"),
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
        "edd_state_clip_reset_camera",
    )
    reset = camera.load(args.project_root)
    bp = reset.load(args.project_root)
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(
        args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph"
    )
    sync = bp.read_blocks(
        args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph"
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
        f'FunctionReference=(MemberName="{FUNCTION}")',
        entry.text,
        1,
    )
    array_form = bp.find_block(sync, r'MemberName="DraftWaypointIds"')
    clear_form = bp.find_block(sync, r'MemberName="Array_Clear"')
    setter_form = bp.find_block(start, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    nodes = [entry]
    chain = []
    for index, (name, kind) in enumerate(ARRAYS):
        getter = bp.Node.clone(
            f"get_{index}", array_form, f"K2Node_VariableGet_{index}",
            256 + index * 416, 256,
        )
        if kind == "string":
            camera.string_variable(getter, "DraftWaypointIds", name, True)
        else:
            reset.variable(getter, "DraftWaypointIds", name, kind, True)
        clear = bp.Node.clone(
            f"clear_{index}", clear_form, f"K2Node_CallArrayFunction_{index}",
            256 + index * 416, 0,
        )
        if kind == "string":
            camera.string_pin(clear, "TargetArray", True)
        else:
            reset.pin_kind(clear, "TargetArray", kind, True)
        bp.connect(getter, name, clear, "TargetArray")
        nodes.extend((getter, clear))
        chain.append(clear)
    for index, (name, kind, value) in enumerate(SCALARS):
        setter = bp.Node.clone(
            f"set_{index}", setter_form, f"K2Node_VariableSet_{index}",
            256 + (len(ARRAYS) + index) * 416, 0,
        )
        reset.variable(setter, "PlaybackActive", name, kind)
        reset.default(setter, name, value)
        nodes.append(setter)
        chain.append(setter)
    bp.connect(entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
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
