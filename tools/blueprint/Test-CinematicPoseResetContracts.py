"""Exact semantic contracts for the combined cinematic-pose reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


SCALARS = (
    ("CinematicPoseStageValidV1", "false"),
    ("CinematicPoseCompiledTotalSecondsV1", "0.0"),
    ("CinematicPoseCompileValidV1", "false"),
    ("CinematicPoseResultSegmentIndexV1", "-1"),
    ("CinematicPoseResultLocalTimeAlphaV1", "0.0"),
    ("CinematicPoseResultDistanceAlphaV1", "0.0"),
    ("CinematicPoseResultCurveUV1", "0.0"),
    ("CinematicPoseResultPositionV1", None),
    ("CinematicPoseResultQuatV1", None),
    ("CinematicPoseResultCompleteV1", "false"),
    ("CinematicPoseResultValidV1", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def explicit_default(body):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', body)
    return None if match is None else match.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root)
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (11 if args.paste else 12), f"reset node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = []
    for name, value in SCALARS:
        setter = contracts.one(nodes, f'MemberName="{name}"')
        actual = explicit_default(setter.pins[name].body)
        if name == "CinematicPoseResultPositionV1":
            contracts.require(actual in ("0, 0, 0", "(X=0.000000,Y=0.000000,Z=0.000000)"), "position reset changed")
        elif name == "CinematicPoseResultQuatV1":
            contracts.require(actual in ("0, 0, 0, 1", "(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000)"), "quat reset changed")
        else:
            contracts.require(actual == value, f"{name} reset changed: {actual!r}")
        setters.append(setter)
    if args.paste:
        contracts.require(not setters[0].pins["execute"].links, "paste root must be exposed")
    else:
        contracts.require_link(entries[0], "then", setters[0], "execute", "entry reset seam")
    for left, right in zip(setters, setters[1:]):
        contracts.require_link(left, "then", right, "execute", "reset order changed")
    known = set(nodes)
    external = {
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _pin in pin.links
        if target not in known
    }
    contracts.require(not external, f"external links {external}")
    print(f"Cinematic pose reset contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes")


if __name__ == "__main__":
    main()
