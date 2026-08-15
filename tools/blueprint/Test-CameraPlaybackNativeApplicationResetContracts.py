"""Exact execution and ownership contracts for playback-native reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


DEFAULTS = {
    "CameraPlaybackNativeInputValidV1": "false",
    "CameraPlaybackNativeStageValidV1": "false",
    "CameraPlaybackNativePreflightValidV1": "false",
    "CameraPlaybackNativeResultValidV1": "false",
    "CameraPlaybackNativeFailureCodeV1": "",
}
PRESERVED = (
    "CameraPlaybackNativeInputPositionV1",
    "CameraPlaybackNativeInputBodyWorldQuatV1",
    "CameraPlaybackNativeInputGimbalWorldQuatV1",
    "CameraPlaybackNativeInputGimbalRelativeQuatV1",
    "CameraPlaybackNativeBaselineActorTransformV1",
    "CameraPlaybackNativeBaselineComponentRelativeTransformV1",
    "CameraPlaybackNativeSessionActiveV1",
    "CameraPlaybackNativeAppliedFrameCountV1",
)
FORBIDDEN = (
    "CameraPlaybackResult", "CameraApply", "CinematicPose", "Airframe",
    "CarrierFrame", "CameraTransform", "DroneCameraRef", "Flypath",
    "Repository", "Event", "Cue", "StateClip", "Server", "HUD", "UI",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_reset_base", path)
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
    contracts.require(len(nodes) == (5 if args.paste else 6), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = sorted(
        (node for node in nodes.values() if "K2Node_VariableSet" in node.node_class),
        key=lambda node: int(node.name.rsplit("_", 1)[1]),
    )
    contracts.require(len(setters) == 5, "exact setter count")
    contracts.require({member(node) for node in setters} == set(DEFAULTS), "exact reset ownership")
    if args.paste:
        contracts.require(not setters[0].pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", setters[0], "execute", "native entry seam")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", "exact reset chain")
    for node in setters:
        name = member(node)
        contracts.require(default(node, name) == DEFAULTS[name], f"{name} default")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED), "data/baseline/session preserved")
    contracts.require(not any(name in text for name in FORBIDDEN), "external ownership forbidden")

    preserved = {name: object() for name in PRESERVED}
    state = dict(preserved)
    state.update(DEFAULTS)
    contracts.require(all(state[name] is preserved[name] for name in PRESERVED), "preserved identity")
    contracts.require(
        all(state[name] == "false" for name in DEFAULTS if name.endswith("ValidV1")),
        "all per-call authority fail closed",
    )
    contracts.require(state["CameraPlaybackNativeFailureCodeV1"] == "", "diagnostic clear")
    print(
        f"Camera playback native-application reset contracts passed "
        f"({'paste' if args.paste else 'full'}): baselines and sessions preserved"
    )


if __name__ == "__main__":
    main()
