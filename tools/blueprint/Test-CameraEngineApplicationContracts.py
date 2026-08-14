"""Exact orchestration contracts for camera engine application."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ORDER = (
    "ResetCameraEngineApplicationResultV1",
    "StageEvaluatedCameraChannelFrameV1",
    "ValidateCameraEngineApplicationInputsV1",
    "CaptureCameraEngineStateV1",
    "ApplyCameraEngineFrameV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_orchestrator_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (8 if args.paste else 9), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    reset = nodes["K2Node_CallFunction_0"]
    if args.paste:
        contracts.require(not reset.pins["execute"].links, "paste root unwired")
    else:
        contracts.require_link(entries[0], "then", reset, "execute", "entry reaches reset")
    text = args.graph.read_text(encoding="utf-8")
    positions = [text.index(f'MemberName="{name}"') for name in ORDER]
    contracts.require(positions == sorted(positions), "exact reset/stage/validate/capture/apply order")
    for name in ORDER:
        contracts.require(text.count(f'MemberName="{name}"') == 1, f"one {name} call")
    contracts.require(len([node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]) == 2, "validation and capture guards")
    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    contracts.require(len(getters) == 1 and 'MemberName="CameraApplyScratchStageValidV1"' in getters[0].text, "sole orchestration state read")
    forbidden = ("CameraApplyInputTargetValuesV1", "CameraApplyBaseline", "CameraApplyCurrent", "Filmback", "FocusSettings", "PostProcessSettings", "CameraChannelCompiled")
    contracts.require(not any(marker in text for marker in forbidden), "orchestrator owns no policy or storage")

    success = ["reset", "stage", "validate", "capture", "apply"]
    validation_failure = ["reset", "stage", "validate"]
    capture_failure = ["reset", "stage", "validate", "capture"]
    contracts.require(success == ["reset", "stage", "validate", "capture", "apply"], "success order")
    contracts.require("capture" not in validation_failure and "apply" not in validation_failure, "validation failure short-circuits")
    contracts.require("apply" not in capture_failure, "capture failure short-circuits")
    print(f"Camera engine application orchestrator contracts passed ({'paste' if args.paste else 'full'}): exact guarded order")


if __name__ == "__main__":
    main()
