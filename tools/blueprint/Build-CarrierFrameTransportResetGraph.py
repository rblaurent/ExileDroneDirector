"""Build the fail-closed, state-preserving carrier-frame transport reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetCarrierFrameTransportV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
ARRAYS = (
    ("CarrierFrameCandidateTangentsV1", "vector"),
    ("CarrierFrameCandidateQuatsV1", "quat"),
    ("CarrierFrameCompiledTangentsV1", "vector"),
    ("CarrierFrameCompiledQuatsV1", "quat"),
)
SCALARS = (
    ("CarrierFrameCompileValidV1", "bool", "false"),
    ("CarrierFrameResultValidV1", "bool", "false"),
    ("CarrierFrameStageValidV1", "bool", "false"),
    ("CarrierFrameCompiledTotalSecondsV1", "real", "0.0"),
    ("CarrierFrameCompiledFixedStepSecondsV1", "real", "0.0"),
    ("CarrierFrameResultSegmentIndexV1", "int", "-1"),
    ("CarrierFrameResultAlphaV1", "real", "0.0"),
    ("CarrierFrameResultQuatV1", "quat", "0, 0, 0, 1"),
    ("CarrierFrameResultCompleteV1", "bool", "false"),
    ("CarrierFrameFailureCodeV1", "string", ""),
    ("CarrierFrameScratchIndexV1", "int", "0"),
    ("CarrierFrameScratchForwardV1", "vector", "1, 0, 0"),
    ("CarrierFrameScratchRightV1", "vector", "0, 1, 0"),
    ("CarrierFrameScratchUpV1", "vector", "0, 0, 1"),
    ("CarrierFrameScratchQuatV1", "quat", "0, 0, 0, 1"),
    ("CarrierFrameScratchValidV1", "bool", "false"),
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
        "edd_carrier_reset_camera",
    )
    reset = camera.load(args.project_root)
    bp = reset.load(args.project_root)
    bp.TARGET_ASSET = TARGET
    bp.TARGET_GRAPH = FUNCTION

    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph")
    start = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    vector_live = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-quintic-vector-v1.eddgraph")
    quat_live = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-spherical-bezier-quaternion-v1.eddgraph")

    entry = bp.Node.clone("entry", bp.find_block(capture, r"K2Node_FunctionEntry"), "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")',
        entry.text,
        1,
    )
    array_form = bp.find_block(sync, r'MemberName="DraftWaypointIds"')
    clear_form = bp.find_block(sync, r'MemberName="Array_Clear"')
    scalar_form = bp.find_block(start, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    vector_form = bp.find_block(vector_live, r'K2Node_VariableSet.*MemberName="TrajectoryResultPositionVectorV1"')
    quat_form = bp.find_block(quat_live, r'K2Node_VariableSet.*MemberName="TrajectoryResultOrientationQuatV1"')

    nodes = [entry]
    chain = []
    for index, (name, kind, value) in enumerate(SCALARS[:3]):
        setter = bp.Node.clone(f"set_{index}", scalar_form, f"K2Node_VariableSet_{index}", 256 + index * 416, 0)
        reset.variable(setter, "PlaybackActive", name, kind)
        reset.default(setter, name, value)
        nodes.append(setter)
        chain.append(setter)

    for index, (name, kind) in enumerate(ARRAYS):
        x = 256 + (3 + index) * 416
        getter = bp.Node.clone(f"get_{index}", array_form, f"K2Node_VariableGet_{index}", x, 256)
        reset.variable(getter, "DraftWaypointIds", name, kind, True)
        clear = bp.Node.clone(f"clear_{index}", clear_form, f"K2Node_CallArrayFunction_{index}", x, 0)
        reset.pin_kind(clear, "TargetArray", kind, True)
        bp.connect(getter, name, clear, "TargetArray")
        nodes.extend((getter, clear))
        chain.append(clear)

    for scalar_index, (name, kind, value) in enumerate(SCALARS[3:], start=3):
        if kind == "vector":
            form, old = vector_form, "TrajectoryResultPositionVectorV1"
        elif kind == "quat":
            form, old = quat_form, "TrajectoryResultOrientationQuatV1"
        else:
            form, old = scalar_form, "PlaybackActive"
        action_index = len(chain)
        setter = bp.Node.clone(
            f"set_{scalar_index}", form, f"K2Node_VariableSet_{scalar_index}",
            256 + action_index * 416, 0,
        )
        camera.string_variable(setter, old, name) if kind == "string" else reset.variable(setter, old, name, kind)
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
        paste = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(paste) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
