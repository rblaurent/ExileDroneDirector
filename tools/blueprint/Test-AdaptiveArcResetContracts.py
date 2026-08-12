"""Exact semantic contracts for the adaptive arc reset transaction."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path


ARRAYS = (
    "TrajectoryArcBuildWorkU0V1", "TrajectoryArcBuildWorkU1V1",
    "TrajectoryArcBuildWorkP0V1", "TrajectoryArcBuildWorkP1V1",
    "TrajectoryArcBuildWorkDepthV1", "TrajectoryArcBuildCandidateUsV1",
    "TrajectoryArcBuildCandidatePositionsV1", "TrajectoryArcBuildCandidateDistancesV1",
    "TrajectoryArcBuiltUsV1", "TrajectoryArcBuiltDistancesV1",
)
SCALARS = (
    ("TrajectoryArcBuildCurrentU0V1", "0.0"),
    ("TrajectoryArcBuildCurrentU1V1", "0.0"),
    ("TrajectoryArcBuildCurrentP0V1", None),
    ("TrajectoryArcBuildCurrentP1V1", None),
    ("TrajectoryArcBuildCurrentDepthV1", "0"),
    ("TrajectoryArcBuildMidpointUV1", "0.0"),
    ("TrajectoryArcBuildMidpointPositionV1", None),
    ("TrajectoryArcBuildOperationCountV1", "0"),
    ("TrajectoryArcBuildCandidateLengthV1", "0.0"),
    ("TrajectoryArcBuildStageValidV1", "false"),
    ("TrajectoryArcBuiltLengthV1", "0.0"),
    ("TrajectoryArcBuildValidV1", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_adaptive_arc_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root); nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (32 if args.paste else 33), f"reset node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (0 if args.paste else 1), "reset entry count")
    clears = []
    for name in ARRAYS:
        getter = c.one(nodes, f'MemberName="{name}"')
        clear = next((node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text and c.linked(getter, name, node, "TargetArray")), None)
        c.require(clear is not None, f"{name} clear missing"); clears.append(clear)
    setters = []
    for name, value in SCALARS:
        setter = c.one(nodes, f'MemberName="{name}"')
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', setter.pins[name].body)
        c.require(match is not None, f"{name} has no explicit reset")
        if value is None:
            c.require(match.group(1) in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"), f"{name} vector reset changed")
        else:
            c.require(match.group(1) == value, f"{name} reset changed")
        setters.append(setter)
    chain = [*clears, *setters]
    if args.paste:
        c.require(not chain[0].pins["execute"].links, "paste root must be exposed")
    else:
        c.require_link(entries[0], "then", chain[0], "execute", "entry must reach first clear")
    for left, right in zip(chain, chain[1:]):
        c.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes); external = {target for node in nodes.values() for pin in node.pins.values() for target, _ in pin.links if target not in known}
    c.require(not external, f"external links {external}")
    print(f"Adaptive arc reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__": main()
