"""Build one finite absolute-time snapshot for all accepted playback evaluators."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageCameraPlaybackEvaluationTimeV1"
TARGETS = (
    "CinematicPoseInputElapsedSecondsV1",
    "AirframePrebakeInputElapsedSecondsV1",
    "CarrierFrameInputElapsedSecondsV1",
    "CameraChannelQueryTimeV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_time_stage_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
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
    builder = scalar.Builder(bp, forms, FUNCTION)

    elapsed = builder.get("CameraPlaybackInputElapsedSecondsV1", "real", 0, 0)
    finite = builder.finite(elapsed, "CameraPlaybackInputElapsedSecondsV1", 256, 0)
    invalidate = builder.set("CameraPlaybackStageValidV1", "bool", 896, 1024, "false")
    clear_failure = builder.set("CameraPlaybackFailureCodeV1", "string", 1152, 1024, "")
    guard = builder.add("finite_guard", "branch", 1408, 1024)
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", guard, "execute")
    bp.connect(finite, "ReturnValue", guard, "Condition")

    setters = []
    for index, name in enumerate(TARGETS):
        setter = builder.set(name, "real", 1664 + index * 256, 1024)
        bp.connect(elapsed, "CameraPlaybackInputElapsedSecondsV1", setter, name)
        setters.append(setter)
    publish = builder.set("CameraPlaybackStageValidV1", "bool", 2688, 1024, "true")
    bp.connect(guard, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(setters[-1], "then", publish, "execute")

    failure = builder.set("CameraPlaybackFailureCodeV1", "string", 1664, 1248, "query_invalid")
    bp.connect(guard, "else", failure, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text)
            for node in builder.nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
