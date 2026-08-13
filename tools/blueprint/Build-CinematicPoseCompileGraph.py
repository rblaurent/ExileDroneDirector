"""Build ordered position/orientation compilation and combined publication."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CompileCinematicPoseV1"
STAGES = (
    "ResetCinematicPoseV1",
    "ValidateCinematicPoseInputsV1",
    "CompilePositionRouteV1",
    "CompileOrientationTrackV1",
    "CommitCompiledCinematicPoseV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_compile_base", path)
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
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    builder = scalar.Builder(bp, forms, FUNCTION)
    blocks = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    template = bp.find_block(blocks, r'MemberName="SwitchToDroneView"')
    calls = []
    for index, name in enumerate(STAGES):
        node = bp.Node.clone(f"stage_{index}", template, f"K2Node_CallFunction_{index}", 256 + index * 320, 0)
        node.text = re.sub(
            r"FunctionReference=\([^)]*\)",
            f'FunctionReference=(MemberName="{name}",bSelfContext=True)',
            node.text,
            count=1,
        )
        builder.nodes.append(node)
        calls.append(node)
    bp.connect(builder.entry, "then", calls[0], "execute")
    for left, right in zip(calls, calls[1:]):
        bp.connect(left, "then", right, "execute")
    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
