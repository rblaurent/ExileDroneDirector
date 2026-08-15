"""Build the thin fresh-reset/stage/validate/capture/apply native coordinator."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ApplyComposedCameraPlaybackFrameV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
ORDER = (
    "ResetCameraPlaybackNativeApplicationResultV1",
    "ResetCameraEngineApplicationResultV1",
    "StageCameraPlaybackNativeApplicationInputsV1",
    "ValidateCameraPlaybackNativeApplicationInputsV1",
    "CaptureCameraPlaybackNativeStateV1",
    "ApplyCameraPlaybackNativeFrameV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_native_orchestrator_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path); args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms["self_call"] = bp.find_block(calls, r'MemberName="SwitchToDroneView"')
    builder = scalar.Builder(bp, forms, FUNCTION)
    call_nodes = []
    for index, name in enumerate(ORDER):
        node = builder.add(f"call_{name}", "self_call", 256 + index * 320, 1024)
        node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET}", line, 1))
        call_nodes.append(node)
    preflight = builder.get("CameraPlaybackNativePreflightValidV1", "bool", 1280, 768)
    session = builder.get("CameraPlaybackNativeSessionActiveV1", "bool", 1920, 768)
    validation_guard = builder.add("validation_guard", "branch", 1536, 1024)
    capture_guard = builder.add("capture_guard", "branch", 2176, 1024)
    bp.connect(builder.entry, "then", call_nodes[0], "execute")
    for left, right in zip(call_nodes[:3], call_nodes[1:4]): bp.connect(left, "then", right, "execute")
    bp.connect(call_nodes[3], "then", validation_guard, "execute"); bp.connect(preflight, "CameraPlaybackNativePreflightValidV1", validation_guard, "Condition")
    bp.connect(validation_guard, "then", call_nodes[4], "execute")
    bp.connect(call_nodes[4], "then", capture_guard, "execute"); bp.connect(session, "CameraPlaybackNativeSessionActiveV1", capture_guard, "Condition")
    bp.connect(capture_guard, "then", call_nodes[5], "execute")
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
