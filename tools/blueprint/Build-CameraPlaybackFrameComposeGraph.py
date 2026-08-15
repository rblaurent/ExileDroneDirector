"""Build the policy-free complete camera-playback coordinator."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ComposeCameraPlaybackFrameV1"
CALLS = (
    "ResetCameraPlaybackFrameV1",
    "StageCameraPlaybackEvaluationTimeV1",
    "EvaluateCameraPlaybackSourcesV1",
    "StageCameraOperatorFromPlaybackV1",
    "ApplyCameraOperatorOverrideV1",
    "StageCameraComfortFromPlaybackV1",
    "ApplyCameraViewerComfortV1",
    "CommitCameraPlaybackFrameV1",
)
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    path = args.project_root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_compose_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    scalar = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scalar
    spec.loader.exec_module(scalar)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    raw = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms["self_call"] = bp.find_block(raw, r'MemberName="SwitchToDroneView"')
    builder = scalar.Builder(bp, forms, FUNCTION)
    calls = []
    for index, name in enumerate(CALLS):
        node = builder.add(f"call_{name}", "self_call", 256 + index * 320, 0)
        node.text = re.sub(
            r"FunctionReference=\([^\n]*\)",
            f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1,
        )
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET}", line, 1,
            ),
        )
        calls.append(node)
    bp.connect(builder.entry, "then", calls[0], "execute")
    for left, right in zip(calls, calls[1:]):
        bp.connect(left, "then", right, "execute")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
