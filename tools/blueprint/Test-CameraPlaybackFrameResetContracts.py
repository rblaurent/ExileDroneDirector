"""Exact ownership and execution contracts for playback-frame reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


DEFAULTS = {
    "CameraPlaybackStageValidV1": "false",
    "CameraPlaybackSourcesValidV1": "false",
    "CameraPlaybackOperatorStageValidV1": "false",
    "CameraPlaybackComfortStageValidV1": "false",
    "CameraPlaybackResultValidV1": "false",
    "CameraPlaybackFailureCodeV1": "",
}
PRESERVED = (
    "CameraPlaybackInputElapsedSecondsV1",
    "CameraPlaybackInputDeltaSecondsV1",
    "CameraPlaybackInputRequestedModeV1",
    "CameraPlaybackInputTranslationV1",
    "CameraPlaybackInputLookV1",
    "CameraPlaybackInputRecenterRequestedV1",
    "CameraPlaybackInputReturnToDirectedRequestedV1",
    "CameraPlaybackInputProceduralTranslationOffsetV1",
    "CameraPlaybackInputProceduralRotationOffsetV1",
    "CameraPlaybackResultPositionV1",
    "CameraPlaybackResultBodyWorldQuatV1",
    "CameraPlaybackResultGimbalWorldQuatV1",
    "CameraPlaybackResultGimbalRelativeQuatV1",
    "CameraPlaybackResultFilmbackPresetIdV1",
    "CameraPlaybackResultFilmbackSensorWidthMmV1",
    "CameraPlaybackResultFilmbackSensorHeightMmV1",
    "CameraPlaybackResultChannelValuesV1",
    "CameraPlaybackResultCompleteV1",
    "CameraPlaybackResultModeV1",
    "CameraPlaybackResultOverrideActiveV1",
    "CameraPlaybackResultTransitionActiveV1",
    "CameraPlaybackResultTetherAppliedV1",
    "CameraPlaybackResultComfortEffectiveWeightsV1",
    "CameraPlaybackResultComfortAppliedV1",
)
FORBIDDEN = (
    "CinematicPose", "AirframePrebake", "CarrierFrame", "CameraChannel",
    "CameraOperator", "CameraComfort", "CameraApply", "CameraTransform",
    "DroneCameraRef", "Flypath", "Repository", "Event", "Cue", "StateClip", "Server",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_reset_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, name):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[name].body)
    return "" if match is None else match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (6 if args.paste else 7), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = sorted(
        (node for node in nodes.values() if "K2Node_VariableSet" in node.node_class),
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    contracts.require(len(setters) == 6, "exact setter count")
    contracts.require({member(node) for node in setters} == set(DEFAULTS), "exact reset ownership")
    if args.paste:
        contracts.require(not setters[0].pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", setters[0], "execute", "native entry seam")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", f"reset seam {left.name} to {right.name}")
    for node in setters:
        name = member(node)
        contracts.require(default(node, name) == DEFAULTS[name], f"{name} default")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "inputs and prior result preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "external ownership forbidden")

    state = {name: object() for name in PRESERVED}
    before = dict(state)
    state.update(DEFAULTS)
    contracts.require(all(state[name] is before[name] for name in PRESERVED), "preserved object identity")
    contracts.require(all(state[name] == "false" for name in DEFAULTS if name.endswith("ValidV1")), "fail closed")
    contracts.require(state["CameraPlaybackFailureCodeV1"] == "", "failure cleared")
    print(f"Camera playback-frame reset contracts passed ({'paste' if args.paste else 'full'}): prior complete snapshot preserved")


if __name__ == "__main__":
    main()
