"""Exact semantic contracts for adaptive arc transaction initialization."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path


ARRAYS = (
    ("TrajectoryArcBuildWorkU0V1", "0.0"),
    ("TrajectoryArcBuildWorkU1V1", "1.0"),
    ("TrajectoryArcBuildWorkP0V1", None),
    ("TrajectoryArcBuildWorkP1V1", None),
    ("TrajectoryArcBuildWorkDepthV1", "0"),
    ("TrajectoryArcBuildCandidateUsV1", "0.0"),
    ("TrajectoryArcBuildCandidatePositionsV1", None),
    ("TrajectoryArcBuildCandidateDistancesV1", "0.0"),
)


def load(root):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"; spec = importlib.util.spec_from_file_location("edd_adaptive_arc_initialize_contract_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root); nodes = c.parse_graph(args.graph); c.require(len(nodes) == (30 if args.paste else 31), f"initialization node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]; c.require(len(entries) == (0 if args.paste else 1), "entry count")
    def one(member): return next(node for node in nodes.values() if f'MemberName="{member}"' in node.text)
    clears = [node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text]; adds = [node for node in nodes.values() if 'MemberName="Array_Add"' in node.text]
    c.require(len(clears) == 8 and len(adds) == 8, "exact clear/append counts")
    getters = {name: one(name) for name, _ in ARRAYS}
    ordered_clears = []
    ordered_adds = []
    for name, default in ARRAYS:
        clear = next(node for node in clears if c.linked(getters[name], name, node, "TargetArray")); ordered_clears.append(clear)
        add = next(node for node in adds if c.linked(getters[name], name, node, "TargetArray")); ordered_adds.append(add)
        if default is not None:
            match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', add.pins["NewItem"].body)
            actual = match.group(1) if match else "0" if default == "0" else "0.0" if default == "0.0" else None
            c.require(actual == default, f"{name} initial value")
    operations = one("TrajectoryArcBuildOperationCountV1"); length = one("TrajectoryArcBuildCandidateLengthV1")
    c.require('DefaultValue="0"' in operations.pins["TrajectoryArcBuildOperationCountV1"].body, "operation reset")
    c.require('DefaultValue="0.0"' in length.pins["TrajectoryArcBuildCandidateLengthV1"].body, "length reset")
    start = one("TrajectoryArcBuildInputStartPositionV1"); end = one("TrajectoryArcBuildInputEndPositionV1")
    c.require_link(start, "TrajectoryArcBuildInputStartPositionV1", ordered_adds[2], "NewItem", "stack start position")
    c.require_link(end, "TrajectoryArcBuildInputEndPositionV1", ordered_adds[3], "NewItem", "stack end position")
    c.require_link(start, "TrajectoryArcBuildInputStartPositionV1", ordered_adds[6], "NewItem", "candidate initial position")
    stage = one("TrajectoryArcBuildStageValidV1"); guard = next(node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class)
    c.require_link(stage, "TrajectoryArcBuildStageValidV1", guard, "Condition", "prior-stage guard")
    chain = [*ordered_clears, operations, length, guard]
    if args.paste: c.require(not chain[0].pins["execute"].links, "paste root")
    else: c.require_link(entries[0], "then", chain[0], "execute", "entry seam")
    for left, right in zip(chain, chain[1:]): c.require_link(left, "then", right, "execute", "reset/guard order")
    c.require_link(guard, "then", ordered_adds[0], "execute", "valid initialization route")
    for left, right in zip(ordered_adds, ordered_adds[1:]): c.require_link(left, "then", right, "execute", "append order")
    known = set(nodes); external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}; c.require(not external, f"external links {external}")
    print(f"Adaptive arc initialization contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__": main()
