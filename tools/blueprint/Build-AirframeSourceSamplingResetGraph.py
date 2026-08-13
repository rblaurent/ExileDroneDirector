"""Build fail-closed reset for the airframe source-sampling bridge."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetAirframeSourceSamplingV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
ARRAYS = (
    ("AirframeSourceCandidatePositionsV1", "vector"),
    ("AirframeSourceCandidateBodyQuatsV1", "quat"),
    ("AirframeSourceCandidateGimbalQuatsV1", "quat"),
    ("AirframeSourceCandidatePathFollowWeightsV1", "real"),
    ("AirframeSourceCandidateHorizonStabilizationWeightsV1", "real"),
    ("AirframeSourceCandidateLookAheadSecondsV1", "real"),
    ("AirframeSourceCandidateBankGainsV1", "real"),
    ("AirframeSourceCandidateMaxBankDegreesV1", "real"),
    ("AirframeSourceCandidateCameraUptiltDegreesV1", "real"),
    ("AirframeSourceCandidateMaxAngularRatesDegreesPerSecondV1", "real"),
    ("AirframeSourceCandidateMaxAccelerationsCmPerSecondSquaredV1", "real"),
    ("AirframeSourceCandidateMaxJerksCmPerSecondCubedV1", "real"),
    ("AirframeSourceCandidateMinimumTurnRadiiCmV1", "real"),
)
SCALARS = (
    ("AirframeSourceExpectedSampleCountV1", "int", "0"),
    ("AirframeSourceSampleIndexV1", "int", "0"),
    ("AirframeSourceSampleElapsedSecondsV1", "real", "0.0"),
    ("AirframeSourceTotalSecondsV1", "real", "0.0"),
    ("AirframeSourceStageValidV1", "bool", "false"),
    ("AirframeSourceCompileValidV1", "bool", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-OrientationTrackResetGraph.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_reset_base", path)
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
    call_blocks = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    entry_form = bp.find_block(capture, r"K2Node_FunctionEntry")
    array_form = bp.find_block(sync, r'MemberName="DraftWaypointIds"')
    clear_form = bp.find_block(sync, r'MemberName="Array_Clear"')
    setter_form = bp.find_block(start, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    call_form = bp.find_block(call_blocks, r'MemberName="SwitchToDroneView"')

    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1,
    )
    downstream = bp.Node.clone("downstream_reset", call_form, "K2Node_CallFunction_0", 256, 0)
    downstream.text = re.sub(
        r"FunctionReference=\([^)]*\)",
        'FunctionReference=(MemberName="ResetAirframeDesiredStreamV1",bSelfContext=True)',
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
        setter = bp.Node.clone(
            f"set_{index}", setter_form, f"K2Node_VariableSet_{index}",
            672 + (len(ARRAYS) + index) * 416, 0,
        )
        reset.variable(setter, "PlaybackActive", name, kind)
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
