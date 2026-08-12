"""Build the atomic vector wrapper around the accepted scalar quintic kernel."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "EvaluateQuinticVectorV1"
INPUTS = (
    "TrajectoryInputStartPositionVectorV1",
    "TrajectoryInputStartVelocityUVectorV1",
    "TrajectoryInputStartAccelerationUVectorV1",
    "TrajectoryInputEndPositionVectorV1",
    "TrajectoryInputEndVelocityUVectorV1",
    "TrajectoryInputEndAccelerationUVectorV1",
)
SCALAR_INPUTS = (
    "TrajectoryInputStartValueV1",
    "TrajectoryInputStartVelocityUV1",
    "TrajectoryInputStartAccelerationUV1",
    "TrajectoryInputEndValueV1",
    "TrajectoryInputEndVelocityUV1",
    "TrajectoryInputEndAccelerationUV1",
)
OUTPUTS = (
    "TrajectoryResultPositionVectorV1",
    "TrajectoryResultDerivativeUVectorV1",
    "TrajectoryResultSecondDerivativeUVectorV1",
)
SCRATCH = tuple(
    f"TrajectoryVectorScratch{channel}{axis}V1"
    for axis in "XYZ"
    for channel in ("Value", "Derivative", "SecondDerivative")
)


def load_scalar(root: Path):
    path = root / "tools" / "blueprint" / "Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_vector_scalar_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def retarget_call(node) -> None:
    node.text = re.sub(
        r'FunctionReference=\([^\n]+\)',
        'FunctionReference=(MemberName="EvaluateQuinticScalarV1",bSelfContext=True)',
        node.text,
        count=1,
    )


def load_forms(root: Path, scalar, bp):
    forms = scalar.load_templates(root, bp)
    blueprint = root / "tools" / "blueprint"
    capture = bp.read_blocks(blueprint / "snippets" / "capture-current-waypoint.eddgraph")
    vector = bp.read_blocks(blueprint / "templates" / "repository-codec-vector-node-forms.eddgraph")
    marker = bp.read_blocks(blueprint / "templates" / "path-preview-marker-node-forms.eddgraph")
    forms.update({
        "self_call": bp.find_block(capture, r'MemberName="SyncDraftWaypointsV1"'),
        "break_vector": bp.find_block(vector, r'MemberName="BreakVector"'),
        "make_vector": bp.find_block(marker, r'MemberName="MakeVector"'),
    })
    return forms


def build(root: Path):
    scalar = load_scalar(root)
    bp = scalar.load_helpers(root)
    forms = load_forms(root, scalar, bp)
    b = scalar.Builder(bp, forms, FUNCTION)
    exec_y = 2200
    reset_nodes = [b.set(name, "vector", 256 + index * 240, exec_y, "0, 0, 0") for index, name in enumerate(OUTPUTS)]
    reset_valid = b.set("TrajectoryResultVectorValidV1", "bool", 976, exec_y, "false")
    chain = [b.entry, *reset_nodes, reset_valid]
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")

    input_gets = [b.get(name, "vector", 0, 320 + index * 240) for index, name in enumerate(INPUTS)]
    breaks = []
    for index, source in enumerate(input_gets):
        node = b.add(f"break_{index}", "break_vector", 256, 320 + index * 240)
        bp.connect(source, INPUTS[index], node, "InVec")
        breaks.append(node)

    previous = reset_valid
    for axis_index, axis in enumerate("XYZ"):
        axis_y = 320 + axis_index * 640
        setters = []
        for input_index, scalar_name in enumerate(SCALAR_INPUTS):
            setter = b.set(scalar_name, "real", 640 + input_index * 224, axis_y)
            bp.connect(breaks[input_index], axis, setter, scalar_name)
            setters.append(setter)
        call = b.add(f"call_scalar_{axis}", "self_call", 2016, axis_y)
        retarget_call(call)
        valid = b.get("TrajectoryResultValidV1", "bool", 2240, axis_y + 160)
        branch = b.add(f"branch_{axis}", "branch", 2464, axis_y)
        bp.connect(valid, "TrajectoryResultValidV1", branch, "Condition")
        axis_chain = [previous, *setters, call, branch]
        for left, right in zip(axis_chain, axis_chain[1:]):
            bp.connect(left, "then", right, "execute")

        result_names = (
            "TrajectoryResultValueV1",
            "TrajectoryResultDerivativeUV1",
            "TrajectoryResultSecondDerivativeUV1",
        )
        scratch_names = (
            f"TrajectoryVectorScratchValue{axis}V1",
            f"TrajectoryVectorScratchDerivative{axis}V1",
            f"TrajectoryVectorScratchSecondDerivative{axis}V1",
        )
        scratch_setters = []
        for result_index, (result_name, scratch_name) in enumerate(zip(result_names, scratch_names)):
            getter = b.get(result_name, "real", 2688, axis_y + result_index * 144)
            setter = b.set(scratch_name, "real", 2912 + result_index * 224, axis_y)
            bp.connect(getter, result_name, setter, scratch_name)
            scratch_setters.append(setter)
        bp.connect(branch, "then", scratch_setters[0], "execute")
        for left, right in zip(scratch_setters, scratch_setters[1:]):
            bp.connect(left, "then", right, "execute")
        previous = scratch_setters[-1]

    make_nodes = []
    channel_names = ("Value", "Derivative", "SecondDerivative")
    for channel_index, channel in enumerate(channel_names):
        make = b.add(f"make_{channel}", "make_vector", 3904, 800 + channel_index * 320)
        for axis_index, axis in enumerate("XYZ"):
            scratch_name = f"TrajectoryVectorScratch{channel}{axis}V1"
            getter = b.get(scratch_name, "real", 3648, 720 + channel_index * 320 + axis_index * 80)
            bp.connect(getter, scratch_name, make, axis)
        make_nodes.append(make)

    output_setters = [b.set(name, "vector", 4304 + index * 240, exec_y) for index, name in enumerate(OUTPUTS)]
    commit_valid = b.set("TrajectoryResultVectorValidV1", "bool", 5024, exec_y, "true")
    bp.connect(previous, "then", output_setters[0], "execute")
    for left, right in zip(output_setters, output_setters[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(output_setters[-1], "then", commit_valid, "execute")
    for make, setter, name in zip(make_nodes, output_setters, OUTPUTS):
        bp.connect(make, "ReturnValue", setter, name)
    return bp, b.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    _bp, nodes = build(args.project_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in nodes[1:]
        ]
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
