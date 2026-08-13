"""Build fail-closed reset for the sampled airframe desired-stream transaction."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetAirframeDesiredStreamV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
ARRAYS = (
    ("AirframeDesiredStreamCandidateVelocitiesV1", "vector"),
    ("AirframeDesiredStreamCandidateAccelerationsV1", "vector"),
    ("AirframeDesiredStreamCandidateJerksV1", "vector"),
    ("AirframeDesiredStreamCandidateLookAheadVelocitiesV1", "vector"),
    ("AirframeDesiredStreamCandidateBodyQuatsV1", "quat"),
    ("AirframeDesiredStreamCandidateGimbalQuatsV1", "quat"),
    ("AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1", "real"),
    ("AirframePrebakeInputDesiredBodyQuatsV1", "quat"),
    ("AirframePrebakeInputDesiredGimbalQuatsV1", "quat"),
    ("AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1", "real"),
)
SCALARS = (
    ("AirframeDesiredStreamStageIndexV1", "int", "0"),
    ("AirframeDesiredStreamStageValidV1", "bool", "false"),
    ("AirframeDesiredStreamVelocitySampleInputSecondsV1", "real", "0.0"),
    ("AirframeDesiredStreamVelocitySampleResultV1", "vector", "0, 0, 0"),
    ("AirframeDesiredStreamVelocitySampleResultValidV1", "bool", "false"),
    ("AirframeDesiredStreamCompileValidV1", "bool", "false"),
    ("AirframePrebakeInputTotalSecondsV1", "real", "0.0"),
    ("AirframePrebakeInputFixedStepSecondsV1", "real", "0.0"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-OrientationTrackResetGraph.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_desired_reset_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    reset = load(args.project_root)
    bp = reset.load(args.project_root)
    bp.TARGET_ASSET = TARGET
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph")
    start = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    quat = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-spherical-bezier-quaternion-v1.eddgraph")
    call_blocks = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    entry_form = bp.find_block(capture, r"K2Node_FunctionEntry")
    array_form = bp.find_block(sync, r'MemberName="DraftWaypointIds"')
    clear_form = bp.find_block(sync, r'MemberName="Array_Clear"')
    setter_form = bp.find_block(start, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    quat_setter_form = bp.find_block(quat, r'K2Node_VariableSet.*MemberName="TrajectoryResultOrientationQuatV1"')
    call_form = bp.find_block(call_blocks, r'MemberName="SwitchToDroneView"')

    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1,
    )
    downstream = bp.Node.clone("downstream_reset", call_form, "K2Node_CallFunction_0", 256, 0)
    downstream.text = re.sub(
        r"FunctionReference=\([^)]*\)",
        'FunctionReference=(MemberName="ResetAirframePrebakeCandidateV1",bSelfContext=True)',
        downstream.text,
        count=1,
    )
    nodes = [entry, downstream]
    chain = [downstream]
    for index, (name, kind) in enumerate(ARRAYS):
        getter = bp.Node.clone(f"get_{index}", array_form, f"K2Node_VariableGet_{index}", 672 + index * 416, 256)
        reset.variable(getter, "DraftWaypointIds", name, kind, True)
        clear = bp.Node.clone(f"clear_{index}", clear_form, f"K2Node_CallArrayFunction_{index}", 672 + index * 416, 0)
        reset.pin_kind(clear, "TargetArray", kind, True)
        bp.connect(getter, name, clear, "TargetArray")
        nodes.extend((getter, clear))
        chain.append(clear)
    for index, (name, kind, value) in enumerate(SCALARS):
        form = quat_setter_form if kind == "quat" else setter_form
        old = "TrajectoryResultOrientationQuatV1" if kind == "quat" else "PlaybackActive"
        setter = bp.Node.clone(
            f"set_{index}", form, f"K2Node_VariableSet_{index}",
            672 + (len(ARRAYS) + index) * 416, 0,
        )
        reset.variable(setter, old, name, kind)
        reset.default(setter, name, value)
        nodes.append(setter)
        chain.append(setter)
    bp.connect(entry, "then", downstream, "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
