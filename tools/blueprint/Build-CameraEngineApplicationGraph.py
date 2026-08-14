"""Build the thin reset/stage/validate/capture/apply coordinator."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ApplyEvaluatedCameraChannelFrameV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
ORDER = (
    "ResetCameraEngineApplicationResultV1",
    "StageEvaluatedCameraChannelFrameV1",
    "ValidateCameraEngineApplicationInputsV1",
    "CaptureCameraEngineStateV1",
    "ApplyCameraEngineFrameV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_engine_orchestrator_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms["self_call"] = bp.find_block(calls, r'MemberName="SwitchToDroneView"')
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        raw = forms[form]
        match = bp.BLOCK_RE.match(raw)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, raw, f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def call(name: str, x: int, y: int):
        node = add_form(f"call_{name}", "self_call", x, y)
        node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET}", line, 1))
        return node

    reset, stage, validate, capture, apply = [call(name, 256 + index * 256, 1024) for index, name in enumerate(ORDER)]
    stage_valid = builder.get("CameraApplyScratchStageValidV1", "bool", 768, 768)
    validation_guard = builder.add("validation_guard", "branch", 1024, 1024)
    capture_guard = builder.add("capture_guard", "branch", 1536, 1024)
    bp.connect(builder.entry, "then", reset, "execute")
    bp.connect(reset, "then", stage, "execute")
    bp.connect(stage, "then", validate, "execute")
    bp.connect(validate, "then", validation_guard, "execute")
    bp.connect(stage_valid, "CameraApplyScratchStageValidV1", validation_guard, "Condition")
    bp.connect(validation_guard, "then", capture, "execute")
    bp.connect(capture, "then", capture_guard, "execute")
    bp.connect(stage_valid, "CameraApplyScratchStageValidV1", capture_guard, "Condition")
    bp.connect(capture_guard, "then", apply, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text) for node in builder.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
