"""Build fail-closed validation for adaptive arc-table inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateAdaptiveArcBuildInputsV1"
VECTOR_INPUTS = (
    ("TrajectoryArcBuildInputStartPositionV1", "TrajectoryInputStartPositionVectorV1"),
    ("TrajectoryArcBuildInputEndPositionV1", "TrajectoryInputEndPositionVectorV1"),
    ("TrajectoryArcBuildInputStartVelocityUV1", "TrajectoryInputStartVelocityUVectorV1"),
    ("TrajectoryArcBuildInputEndVelocityUV1", "TrajectoryInputEndVelocityUVectorV1"),
    ("TrajectoryArcBuildInputStartAccelerationUV1", "TrajectoryInputStartAccelerationUVectorV1"),
    ("TrajectoryArcBuildInputEndAccelerationUV1", "TrajectoryInputEndAccelerationUVectorV1"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_adaptive_arc_validation_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        return re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
    node.mutate_pin(pin_name, mutate)


def retarget_call(scalar, node, member, pin_types):
    scalar.retarget_function(node, member)
    for pin, kind in pin_types.items(): pin_kind(node, pin, kind)
    return node


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path); args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp); b = scalar.Builder(bp, forms, FUNCTION)
    call_blocks = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    call_form = bp.find_block(call_blocks, r'MemberName="SwitchToDroneView"')

    def add_call(name, x, y):
        index = b.serial.get("K2Node_CallFunction", 0)
        b.serial["K2Node_CallFunction"] = index + 1
        node = bp.Node.clone("evaluate", call_form, f"K2Node_CallFunction_{index}", x, y)
        node.text = re.sub(r'FunctionReference=\([^)]*\)', f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        b.nodes.append(node); return node
    def compare(member, x, y, kind, default_b):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y)
        retarget_call(scalar, node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        scalar.set_default(node, "B", default_b); return node
    def bool_and(left, right, x, y):
        node = b.add(f"and_{len(b.nodes)}", "compare", x, y)
        retarget_call(scalar, node, "BooleanAND", {"A": "bool", "B": "bool", "ReturnValue": "bool"})
        bp.connect(left, "ReturnValue", node, "A"); bp.connect(right, "ReturnValue", node, "B"); return node

    reset = b.set("TrajectoryArcBuildStageValidV1", "bool", 256, 1344, "false")
    bp.connect(b.entry, "then", reset, "execute")
    chain = [reset]
    for index, (source_name, target_name) in enumerate(VECTOR_INPUTS):
        source = b.get(source_name, "vector", 256 + index * 416, 256)
        target = b.set(target_name, "vector", 512 + index * 416, 1344)
        bp.connect(source, source_name, target, target_name)
        bp.connect(chain[-1], "then", target, "execute"); chain.append(target)
    alpha = b.set("TrajectoryInputAlphaV1", "real", 512 + len(VECTOR_INPUTS) * 416, 1344, "0.5")
    bp.connect(chain[-1], "then", alpha, "execute"); chain.append(alpha)
    evaluate = add_call("EvaluateQuinticVectorV1", 768 + len(VECTOR_INPUTS) * 416, 1344)
    bp.connect(chain[-1], "then", evaluate, "execute")

    vector_valid = b.get("TrajectoryResultVectorValidV1", "bool", 3072, 256)
    tolerance = b.get("TrajectoryArcBuildInputToleranceV1", "real", 3072, 448)
    tolerance_finite = b.finite(tolerance, "TrajectoryArcBuildInputToleranceV1", 3328, 384)
    tolerance_positive = compare("Greater_DoubleDouble", 3328, 576, "real", "0.0"); bp.connect(tolerance, "TrajectoryArcBuildInputToleranceV1", tolerance_positive, "A")
    tolerance_valid = bool_and(tolerance_finite, tolerance_positive, 3792, 448)
    depth = b.get("TrajectoryArcBuildInputMaxDepthV1", "real", 3072, 768); pin_kind(depth, "TrajectoryArcBuildInputMaxDepthV1", "int")
    depth_min = compare("GreaterEqual_IntInt", 3328, 704, "int", "1"); bp.connect(depth, "TrajectoryArcBuildInputMaxDepthV1", depth_min, "A")
    depth_max = compare("LessEqual_IntInt", 3328, 832, "int", "12"); bp.connect(depth, "TrajectoryArcBuildInputMaxDepthV1", depth_max, "A")
    depth_valid = bool_and(depth_min, depth_max, 3792, 768)
    operations = b.get("TrajectoryArcBuildInputMaxOperationsV1", "real", 3072, 1088); pin_kind(operations, "TrajectoryArcBuildInputMaxOperationsV1", "int")
    operations_min = compare("GreaterEqual_IntInt", 3328, 1024, "int", "1"); bp.connect(operations, "TrajectoryArcBuildInputMaxOperationsV1", operations_min, "A")
    operations_max = compare("LessEqual_IntInt", 3328, 1152, "int", "8191"); bp.connect(operations, "TrajectoryArcBuildInputMaxOperationsV1", operations_max, "A")
    operations_valid = bool_and(operations_min, operations_max, 3792, 1088)
    first = b.add(f"and_{len(b.nodes)}", "compare", 4032, 384)
    retarget_call(scalar, first, "BooleanAND", {"A": "bool", "B": "bool", "ReturnValue": "bool"})
    bp.connect(vector_valid, "TrajectoryResultVectorValidV1", first, "A")
    bp.connect(tolerance_valid, "ReturnValue", first, "B")
    second = bool_and(first, depth_valid, 4272, 576)
    all_valid = bool_and(second, operations_valid, 4512, 768)
    branch = b.add("accept_branch", "branch", 4752, 1344); bp.connect(evaluate, "then", branch, "execute"); bp.connect(all_valid, "ReturnValue", branch, "Condition")
    accept = b.set("TrajectoryArcBuildStageValidV1", "bool", 4992, 1344, "true"); bp.connect(branch, "then", accept, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
