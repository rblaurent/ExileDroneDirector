"""Build the exact spherical-cubic quaternion segment evaluator.

The four control quaternions are compiler outputs.  This evaluator validates
that they remain finite and normalized, rejects non-finite alpha, clamps finite
alpha to [0,1], evaluates spherical cubic Bezier by six native Quat_Slerp
calls, and publishes result/validity atomically.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "EvaluateSphericalBezierQuaternionV1"
INPUTS = (
    "TrajectoryInputOrientationStartQuatV1",
    "TrajectoryInputOrientationStartControlQuatV1",
    "TrajectoryInputOrientationEndControlQuatV1",
    "TrajectoryInputOrientationEndQuatV1",
)
OUTPUT = "TrajectoryResultOrientationQuatV1"
VALID = "TrajectoryResultOrientationValidV1"
ALPHA = "TrajectoryInputAlphaV1"


def load_scalar(root: Path):
    path = root / "tools" / "blueprint" / "Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_quat_scalar_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def retarget_quat_variable(scalar, node, name: str) -> None:
    scalar.retarget_variable(node, name, "vector")
    for pin in (name, "Output_Get"):
        if pin not in node.pins:
            continue
        def mutate(line: str) -> str:
            return line.replace("/Script/CoreUObject.Vector'", "/Script/CoreUObject.Quat'")
        node.mutate_pin(pin, mutate)


def exact_form(root: Path, bp, member: str) -> str:
    blocks = bp.read_blocks(
        root / "tools" / "blueprint" / "templates" /
        "trajectory-quaternion-native-node-forms.eddgraph"
    )
    return bp.find_block(blocks, rf'MemberName="{member}"')


def build(root: Path):
    scalar = load_scalar(root)
    bp = scalar.load_helpers(root)
    forms = scalar.load_templates(root, bp)
    forms.update({
        "quat_finite": exact_form(root, bp, "Quat_IsFinite"),
        "quat_normalized": exact_form(root, bp, "Quat_IsNormalized"),
        "quat_slerp": exact_form(root, bp, "Quat_Slerp"),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def quat_get(name: str, x: int, y: int):
        node = b.get(name, "vector", x, y)
        retarget_quat_variable(scalar, node, name)
        return node

    def quat_set(name: str, x: int, y: int, default: str | None = None):
        node = b.set(name, "vector", x, y)
        retarget_quat_variable(scalar, node, name)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    reset_result = quat_set(OUTPUT, 256, 1792, "0, 0, 0, 1")
    reset_valid = b.set(VALID, "bool", 512, 1792, "false")
    bp.connect(b.entry, "then", reset_result, "execute")
    bp.connect(reset_result, "then", reset_valid, "execute")

    alpha = b.get(ALPHA, "real", 0, 128)
    finite_alpha = b.finite(alpha, ALPHA, 224, 128)
    clamped = b.clamp(alpha, ALPHA, 448, 288)
    guards = [finite_alpha]
    sources = []
    for index, name in enumerate(INPUTS):
        source = quat_get(name, 0, 480 + index * 256)
        finite = b.add(f"finite_quat_{index}", "quat_finite", 256, 480 + index * 256)
        normalized = b.add(f"normalized_quat_{index}", "quat_normalized", 512, 480 + index * 256)
        bp.connect(source, name, finite, "Q")
        bp.connect(source, name, normalized, "Q")
        both = b.add(f"guard_and_{index}", "compare", 768, 480 + index * 256)
        scalar.retarget_function(both, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"):
            scalar.set_pin_type(both, pin, "bool")
        bp.connect(finite, "ReturnValue", both, "A")
        bp.connect(normalized, "ReturnValue", both, "B")
        guards.append(both)
        sources.append(source)

    combined = guards[0]
    for index, guard in enumerate(guards[1:]):
        node = b.add(f"all_guard_{index}", "compare", 1024 + index * 208, 192)
        scalar.retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"):
            scalar.set_pin_type(node, pin, "bool")
        bp.connect(combined, "ReturnValue", node, "A")
        bp.connect(guard, "ReturnValue", node, "B")
        combined = node
    branch = b.add("valid_branch", "branch", 1936, 1792)
    bp.connect(reset_valid, "then", branch, "execute")
    bp.connect(combined, "ReturnValue", branch, "Condition")

    def slerp(name: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.add(name, "quat_slerp", x, y)
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        bp.connect(clamped, "ReturnValue", node, "Alpha")
        return node

    first = slerp("slerp_first", sources[0], INPUTS[0], sources[1], INPUTS[1], 2176, 320)
    second = slerp("slerp_second", sources[1], INPUTS[1], sources[2], INPUTS[2], 2176, 640)
    third = slerp("slerp_third", sources[2], INPUTS[2], sources[3], INPUTS[3], 2176, 960)
    fourth = slerp("slerp_fourth", first, "ReturnValue", second, "ReturnValue", 2496, 448)
    fifth = slerp("slerp_fifth", second, "ReturnValue", third, "ReturnValue", 2496, 832)
    result = slerp("slerp_result", fourth, "ReturnValue", fifth, "ReturnValue", 2816, 640)
    output = quat_set(OUTPUT, 3136, 1792)
    valid = b.set(VALID, "bool", 3392, 1792, "true")
    bp.connect(branch, "then", output, "execute")
    bp.connect(output, "then", valid, "execute")
    bp.connect(result, "ReturnValue", output, OUTPUT)
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
        body = [
            re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text)
            for node in nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
