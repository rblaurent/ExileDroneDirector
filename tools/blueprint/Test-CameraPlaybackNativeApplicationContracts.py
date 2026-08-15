"""Exact orchestration contracts for playback-native application."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ORDER = (
    "ResetCameraPlaybackNativeApplicationResultV1",
    "ResetCameraEngineApplicationResultV1",
    "StageCameraPlaybackNativeApplicationInputsV1",
    "ValidateCameraPlaybackNativeApplicationInputsV1",
    "CaptureCameraPlaybackNativeStateV1",
    "ApplyCameraPlaybackNativeFrameV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_orchestrator_contract_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (10 if args.paste else 11), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    reset = nodes["K2Node_CallFunction_0"]
    if args.paste: contracts.require(not reset.pins["execute"].links, "paste root")
    else: contracts.require_link(entries[0], "then", reset, "execute", "entry reaches native reset")
    text = args.graph.read_text(encoding="utf-8")
    positions = [text.index(f'MemberName="{name}"') for name in ORDER]
    contracts.require(positions == sorted(positions), "exact native reset/engine reset/stage/validate/capture/apply order")
    for name in ORDER: contracts.require(text.count(f'MemberName="{name}"') == 1, f"one {name}")
    contracts.require(text.index('MemberName="ResetCameraEngineApplicationResultV1"') < text.index('MemberName="StageCameraPlaybackNativeApplicationInputsV1"'), "engine result reset before fresh staging")
    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    contracts.require({next(name for name in ("CameraPlaybackNativePreflightValidV1", "CameraPlaybackNativeSessionActiveV1") if name in node.text) for node in getters} == {"CameraPlaybackNativePreflightValidV1", "CameraPlaybackNativeSessionActiveV1"}, "sole orchestration authority reads")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 2, "preflight and capture guards")
    forbidden = (
        "CameraPlaybackNativeInputPositionV1", "CameraPlaybackNativeInputBodyWorldQuatV1",
        "CameraPlaybackNativeInputGimbal", "CameraPlaybackNativeBaseline",
        "CameraApplyInput", "CameraApplyBaseline", "CameraApplyCurrent",
        "DroneCameraRef", "CameraTransform", "CinematicPose", "CarrierFrame",
        "Flypath", "Repository", "Server", "HUD", "UI",
    )
    contracts.require(not any(name in text for name in forbidden), "coordinator owns no policy, pose, target, or storage")
    calls = [nodes[f"K2Node_CallFunction_{index}"] for index in range(6)]
    guards = [nodes[f"K2Node_IfThenElse_{index}"] for index in range(2)]
    contracts.require_link(calls[0], "then", calls[1], "execute", "native reset before engine reset")
    contracts.require_link(calls[1], "then", calls[2], "execute", "engine reset before stage")
    contracts.require_link(calls[2], "then", calls[3], "execute", "stage before validate")
    contracts.require_link(calls[3], "then", guards[0], "execute", "validate before preflight guard")
    contracts.require_link(guards[0], "then", calls[4], "execute", "preflight gates capture")
    contracts.require_link(calls[4], "then", guards[1], "execute", "capture before session guard")
    contracts.require_link(guards[1], "then", calls[5], "execute", "session authority gates apply")
    success = list(ORDER)
    validation_failure = list(ORDER[:4])
    capture_failure = list(ORDER[:5])
    contracts.require(success[-1] == "ApplyCameraPlaybackNativeFrameV1", "success applies")
    contracts.require("CaptureCameraPlaybackNativeStateV1" not in validation_failure and "ApplyCameraPlaybackNativeFrameV1" not in validation_failure, "validation failure short-circuits")
    contracts.require("ApplyCameraPlaybackNativeFrameV1" not in capture_failure, "capture failure short-circuits")
    print(f"Camera playback native orchestrator contracts passed ({'paste' if args.paste else 'full'}): exact fresh-reset guarded order")


if __name__ == "__main__": main()
