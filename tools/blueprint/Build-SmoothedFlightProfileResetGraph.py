"""Build the fail-closed smoothed flight-profile scratch/result reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetSmoothedFlightProfileV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
PARAMETERS = (
    "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
    "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
    "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
)
RESETS = (
    ("SmoothedFlightProfileStageValidV1", "bool", "false"),
    ("SmoothedFlightProfileCurrentIdV1", "string", ""),
    *((f"SmoothedFlightProfileCurrent{name}V1", "real", "0.0") for name in PARAMETERS),
    ("SmoothedFlightProfileNeighborIdV1", "string", ""),
    *((f"SmoothedFlightProfileNeighbor{name}V1", "real", "0.0") for name in PARAMETERS),
    ("SmoothedFlightProfileNeighborWeightV1", "real", "0.0"),
    ("SmoothedFlightProfileResultCurrentIdV1", "string", ""),
    ("SmoothedFlightProfileResultNeighborIdV1", "string", ""),
    ("SmoothedFlightProfileResultNeighborWeightV1", "real", "0.0"),
    *((f"SmoothedFlightProfileResult{name}V1", "real", "0.0") for name in PARAMETERS),
    ("SmoothedFlightProfileResultValidV1", "bool", "false"),
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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

    reset_base = load_module(
        args.project_root / "tools/blueprint/Build-FlightProfileResetGraph.py",
        "edd_smoothed_flight_profile_reset_base",
    )
    reset_graph_base = reset_base.load(args.project_root)
    bp = reset_graph_base.load(args.project_root)
    bp.TARGET_ASSET = TARGET
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-repository-result-v1.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    entry_form = bp.find_block(capture, r"K2Node_FunctionEntry")
    scalar_form = bp.find_block(playback, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    string_form = bp.find_block(repository, r'K2Node_VariableSet.*MemberName="ResultDetailV1"')

    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1,
    )
    nodes = [entry]
    setters = []
    for index, (name, kind, value) in enumerate(RESETS):
        form = string_form if kind == "string" else scalar_form
        old = "ResultDetailV1" if kind == "string" else "PlaybackActive"
        # Paste normalization centers the complete selection under the cursor.
        # Keep the execution root at that geometric center on a clear lane so
        # the native function entry never lands inside the long setter chain.
        x, y = ((7952, -192) if index == 0 else (256 + index * 416, 0))
        setter = bp.Node.clone(
            f"set_{index}", form, f"K2Node_VariableSet_{index}", x, y,
        )
        reset_base.variable(setter, old, name, kind)
        reset_base.default(setter, name, value)
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
