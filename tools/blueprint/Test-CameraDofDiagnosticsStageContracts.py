"""Structural and executable contracts for DOF complete-frame staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraChannelResultValidV1",
    "CameraChannelResultValuesV1",
    "CameraChannelResultFilmbackSensorWidthMmV1",
    "CameraChannelResultFilmbackSensorHeightMmV1",
}
WRITES = {
    "CameraDofStageFilmbackWidthMmV1",
    "CameraDofStageFilmbackHeightMmV1",
    "CameraDofStageFocalLengthMmV1",
    "CameraDofStageApertureFstopV1",
    "CameraDofStageFocusDistanceCmV1",
    "CameraDofStageValidV1",
    "CameraDofFailureCodeV1",
}
FORBIDDEN = ("CameraChannelInput", "CameraChannelCandidate", "CameraChannelCompiled", "CameraApply", "CameraFocus", "Airframe", "Document")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_dof_stage_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def simulate(source: dict) -> dict:
    result = {"width": 0.0, "height": 0.0, "focal": 0.0, "aperture": 0.0, "focus": 0.0, "valid": False, "failure": ""}
    values = source.get("values")
    valid_number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    if (
        source.get("valid") is True
        and isinstance(values, tuple)
        and len(values) == 13
        and all(valid_number(value) for value in values)
        and valid_number(source.get("width"))
        and float(source["width"]) > 0.0
        and valid_number(source.get("height"))
        and float(source["height"]) > 0.0
    ):
        result.update(width=float(source["width"]), height=float(source["height"]), focal=float(values[0]), aperture=float(values[1]), focus=float(values[2]), valid=True)
    else:
        result["failure"] = "camera_dof_stage_failed"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (99 if args.paste else 100), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    contracts.require(getters == READS, f"exact reads:{getters}")
    contracts.require(set(member(node) for node in setters) == WRITES, "exact writes")
    contracts.require(sum(member(node) == "CameraDofStageValidV1" for node in setters) == 2, "stage validity invalidate/publish")
    contracts.require(member(setters[-2]) == "CameraDofStageValidV1", "success validity last")
    root = setters[0]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste root unlinked")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry to stage reset")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 13, "thirteen canonical reads")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "protected ownership")

    randomizer = random.Random(0xD0F571)
    for index in range(80):
        source = {"valid": True, "width": randomizer.uniform(10.0, 70.0), "height": randomizer.uniform(8.0, 50.0), "values": tuple(randomizer.uniform(-10.0, 1000.0) for _ in range(13))}
        before = source["values"]
        staged = simulate(source)
        contracts.require(staged["valid"], f"seed {index}")
        contracts.require((staged["focal"], staged["aperture"], staged["focus"]) == source["values"][:3], "canonical first three")
        contracts.require(source["values"] == before, "source immutable")
    base = {"valid": True, "width": 36.0, "height": 24.0, "values": tuple(float(index) for index in range(13))}
    failures = (
        {**base, "valid": False},
        {**base, "width": 0.0},
        {**base, "width": math.nan},
        {**base, "height": 0.0},
        {**base, "height": math.inf},
        {**base, "values": base["values"][:-1]},
        {**base, "values": base["values"] + (13.0,)},
        {**base, "values": (math.nan,) + base["values"][1:]},
        {**base, "values": base["values"][:-1] + (math.inf,)},
    )
    for index, source in enumerate(failures):
        contracts.require(simulate(source) == {"width": 0.0, "height": 0.0, "focal": 0.0, "aperture": 0.0, "focus": 0.0, "valid": False, "failure": "camera_dof_stage_failed"}, f"failure {index}")
    print(f"Camera DOF stage contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes, 80 frames, 9 failures")


if __name__ == "__main__":
    main()
