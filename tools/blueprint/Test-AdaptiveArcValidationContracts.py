"""Exact executable contracts for adaptive arc input validation."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path


VECTOR_INPUTS = (
    ("TrajectoryArcBuildInputStartPositionV1", "TrajectoryInputStartPositionVectorV1"),
    ("TrajectoryArcBuildInputEndPositionV1", "TrajectoryInputEndPositionVectorV1"),
    ("TrajectoryArcBuildInputStartVelocityUV1", "TrajectoryInputStartVelocityUVectorV1"),
    ("TrajectoryArcBuildInputEndVelocityUV1", "TrajectoryInputEndVelocityUVectorV1"),
    ("TrajectoryArcBuildInputStartAccelerationUV1", "TrajectoryInputStartAccelerationUVectorV1"),
    ("TrajectoryArcBuildInputEndAccelerationUV1", "TrajectoryInputEndAccelerationUVectorV1"),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_adaptive_arc_validation_contract_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def one_member(c, nodes, member):
    return c.one(nodes, f'MemberName="{member}"')


def default(node, pin, expected):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body)
    return match is not None and match.group(1) == expected


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root); nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (35 if args.paste else 36), f"validation node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "validation entry count")
    stage_sets = [node for node in nodes.values() if 'MemberName="TrajectoryArcBuildStageValidV1"' in node.text]
    c.require(len(stage_sets) == 2, "stage must have one reset and one accept")
    reset = next(node for node in stage_sets if default(node, "TrajectoryArcBuildStageValidV1", "false"))
    accept = next(node for node in stage_sets if default(node, "TrajectoryArcBuildStageValidV1", "true"))
    chain = [reset]
    for source_name, target_name in VECTOR_INPUTS:
        source = one_member(c, nodes, source_name); target = one_member(c, nodes, target_name)
        c.require_link(source, source_name, target, target_name, f"{source_name} staging changed")
        c.require_link(chain[-1], "then", target, "execute", f"{target_name} exec order changed")
        chain.append(target)
    alpha = one_member(c, nodes, "TrajectoryInputAlphaV1")
    c.require(default(alpha, "TrajectoryInputAlphaV1", "0.5"), "validation alpha changed")
    c.require_link(chain[-1], "then", alpha, "execute", "alpha staging order changed")
    evaluate = one_member(c, nodes, "EvaluateQuinticVectorV1")
    c.require_link(alpha, "then", evaluate, "execute", "vector evaluator call disconnected")
    vector_valid = one_member(c, nodes, "TrajectoryResultVectorValidV1")
    tolerance = one_member(c, nodes, "TrajectoryArcBuildInputToleranceV1")
    finite = [node for node in nodes.values() if 'MemberName="GreaterEqual_DoubleDouble"' in node.text or 'MemberName="LessEqual_DoubleDouble"' in node.text]
    c.require(len(finite) == 2 and all(c.linked(tolerance, "TrajectoryArcBuildInputToleranceV1", node, "A") for node in finite), "tolerance finite bounds disconnected")
    positive = one_member(c, nodes, "Greater_DoubleDouble")
    c.require(default(positive, "B", "0.0") and c.linked(tolerance, "TrajectoryArcBuildInputToleranceV1", positive, "A"), "tolerance positivity changed")
    depth = one_member(c, nodes, "TrajectoryArcBuildInputMaxDepthV1")
    operations = one_member(c, nodes, "TrajectoryArcBuildInputMaxOperationsV1")
    integer_min = [node for node in nodes.values() if 'MemberName="GreaterEqual_IntInt"' in node.text]
    integer_max = [node for node in nodes.values() if 'MemberName="LessEqual_IntInt"' in node.text]
    c.require(len(integer_min) == 2 and len(integer_max) == 2, "integer bounds changed")
    dmin = next(node for node in integer_min if default(node, "B", "1") and c.linked(depth, "TrajectoryArcBuildInputMaxDepthV1", node, "A"))
    dmax = next(node for node in integer_max if default(node, "B", "12") and c.linked(depth, "TrajectoryArcBuildInputMaxDepthV1", node, "A"))
    omin = next(node for node in integer_min if default(node, "B", "1") and c.linked(operations, "TrajectoryArcBuildInputMaxOperationsV1", node, "A"))
    omax = next(node for node in integer_max if default(node, "B", "8191") and c.linked(operations, "TrajectoryArcBuildInputMaxOperationsV1", node, "A"))
    c.require(all((dmin, dmax, omin, omax)), "bounded validation missing")
    branch = next(node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class)
    c.require_link(evaluate, "then", branch, "execute", "accept branch must run after evaluator")
    c.require_link(branch, "then", accept, "execute", "accept write disconnected")
    boolean_ands = [node for node in nodes.values() if 'MemberName="BooleanAND"' in node.text]
    c.require(len(boolean_ands) == 7, "boolean conjunction count changed")
    c.require(any(c.linked(vector_valid, "TrajectoryResultVectorValidV1", node, "A") for node in boolean_ands), "vector validity omitted")
    if args.paste:
        c.require(not reset.pins["execute"].links, "paste root must be exposed")
    else:
        c.require_link(entries[0], "then", reset, "execute", "entry reset missing")
    known = set(nodes); external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Adaptive arc validation contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__": main()
