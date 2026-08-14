"""Structural and executable contracts for evaluated-frame staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraApplyInputTargetValuesV1",
    "CameraChannelResultValidV1",
    "CameraChannelResultValuesV1",
    "CameraChannelResultFilmbackPresetIdV1",
    "CameraChannelResultFilmbackSensorWidthMmV1",
    "CameraChannelResultFilmbackSensorHeightMmV1",
}
WRITES = {"CameraApplyInputValidV1", "CameraApplyInputFilmbackPresetIdV1"}
FORBIDDEN = (
    "CameraApplyCapability",
    "CameraApplyBaseline",
    "CameraApplyCurrent",
    "CameraApplySessionActiveV1",
    "CameraApplyAppliedFrameCountV1",
    "CameraChannelInput",
    "CameraChannelCandidate",
    "CameraChannelCompiled",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_apply_stage_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def simulate(source: dict, prior: dict) -> dict:
    result = {"id": "", "values": [], "valid": False}
    values = source.get("values")
    if (
        source.get("valid") is True
        and isinstance(values, tuple)
        and len(values) == 13
        and isinstance(source.get("id"), str)
        and bool(source["id"])
        and isinstance(source.get("width"), (int, float))
        and not isinstance(source.get("width"), bool)
        and math.isfinite(float(source["width"]))
        and float(source["width"]) > 0.0
        and isinstance(source.get("height"), (int, float))
        and not isinstance(source.get("height"), bool)
        and math.isfinite(float(source["height"]))
        and float(source["height"]) > 0.0
    ):
        result["id"] = source["id"]
        result["values"] = [float(source["width"]), float(source["height"]), *values]
        result["valid"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (57 if args.paste else 58), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to staging root")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, f"exact staging reads: {getters}")
    contracts.require(set(setters) == WRITES, f"exact staging writes: {setters}")
    contracts.require(setters.count("CameraApplyInputValidV1") == 2, "validity invalidates then publishes")
    contracts.require(setters[-1] == "CameraApplyInputValidV1", "input validity publishes last")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "staging cannot touch protected storage")
    contracts.require(
        sum('MemberName="Array_Add"' in node.text for node in nodes.values()) == 15,
        "exact width/height/thirteen-channel appends",
    )
    contracts.require(
        sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 13,
        "exact thirteen channel reads",
    )
    contracts.require("KismetStringLibrary" in text and 'MemberName="NotEqual_StrStr"' in text, "correct string comparison library")

    rng = random.Random(0xEDD711)
    for index in range(80):
        source = {
            "valid": True,
            "id": f"filmback_{index}",
            "width": 24.0 + rng.random() * 20.0,
            "height": 12.0 + rng.random() * 20.0,
            "values": tuple(rng.uniform(-5.0, 5.0) for _ in range(13)),
        }
        prior = {"id": "poison", "values": [99.0], "valid": True}
        staged = simulate(source, prior)
        contracts.require(staged["valid"], f"seeded frame {index}")
        contracts.require(staged["values"] == [source["width"], source["height"], *source["values"]], "canonical mapping")
        contracts.require(source["values"] == tuple(source["values"]), "source immutability")

    base = {"valid": True, "id": "filmback", "width": 36.0, "height": 24.0, "values": tuple(range(13))}
    failures = (
        {**base, "valid": False},
        {**base, "id": ""},
        {**base, "width": 0.0},
        {**base, "width": math.nan},
        {**base, "height": 0.0},
        {**base, "height": math.inf},
        {**base, "values": tuple(range(12))},
        {**base, "values": tuple(range(14))},
    )
    for index, source in enumerate(failures):
        staged = simulate(source, {"id": "poison", "values": [99.0], "valid": True})
        contracts.require(staged == {"id": "", "values": [], "valid": False}, f"failure {index} fail closed")
    print(
        f"Camera engine application staging contracts passed "
        f"({'paste' if args.paste else 'full'}): 80 frames, 8 failures"
    )


if __name__ == "__main__":
    main()
