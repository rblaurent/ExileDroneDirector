"""Build the fail-closed airframe/gimbal desired-pose reset transaction."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetAirframeGimbalV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
RESULTS = (
    ("AirframeGimbalStageValidV1", "bool", "false"),
    ("AirframeGimbalResultBodyQuatV1", "quat", "0, 0, 0, 1"),
    ("AirframeGimbalResultGimbalQuatV1", "quat", "0, 0, 0, 1"),
    ("AirframeGimbalResultPathQuatV1", "quat", "0, 0, 0, 1"),
    ("AirframeGimbalResultSpeedCmPerSecondV1", "real", "0.0"),
    ("AirframeGimbalResultLateralAccelerationCmPerSecondSquaredV1", "real", "0.0"),
    ("AirframeGimbalResultTurnRadiusCmV1", "real", "0.0"),
    ("AirframeGimbalResultBankDegreesV1", "real", "0.0"),
    ("AirframeGimbalResultValidV1", "bool", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-CinematicPoseResetGraph.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_gimbal_reset_base", path)
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
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    quat_live = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-spherical-bezier-quaternion-v1.eddgraph")
    entry_form = bp.find_block(capture, r"K2Node_FunctionEntry")
    scalar_form = bp.find_block(playback, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    quat_form = bp.find_block(quat_live, r'K2Node_VariableSet.*MemberName="TrajectoryResultOrientationQuatV1"')

    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")',
        entry.text,
        1,
    )
    nodes = [entry]
    setters = []
    for index, (name, kind, value) in enumerate(RESULTS):
        form = quat_form if kind == "quat" else scalar_form
        old = "TrajectoryResultOrientationQuatV1" if kind == "quat" else "PlaybackActive"
        setter = bp.Node.clone(
            f"set_{index}", form, f"K2Node_VariableSet_{index}", 256 + index * 384, 0
        )
        reset.variable(setter, old, name, kind)
        reset.default(setter, name, value)
        nodes.append(setter)
        setters.append(setter)
    bp.connect(entry, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
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
