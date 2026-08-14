"""Atomic publication contracts for the complete named camera look."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from copy import deepcopy
from pathlib import Path


CHANNELS = (
    "focal_length_mm", "aperture_fstop", "focus_distance_cm", "focus_influence",
    "exposure_ev", "bloom_weight", "vignette_weight", "color_grading_weight",
    "tint_weight", "motion_blur_weight", "chromatic_aberration_weight",
    "sharpening_weight", "matte_weight",
)
READS = {"CameraLookCandidateValidV1", "CameraLookCandidateBaseValuesV1", "CameraLookCandidateValuesV1", "CameraLookCandidateOverrideMaskV1", "CameraLookInputPresetIdV1", "CameraLookResultChannelIdsV1"}
WRITES = {"CameraLookResultValidV1", "CameraLookFailureCodeV1", "CameraLookResultPresetIdV1", "CameraLookResultBaseValuesV1", "CameraLookResultValuesV1", "CameraLookResultOverrideMaskV1"}
FORBIDDEN = ("CameraLookInputAuthored", "CameraLookValidationValidV1", "CameraLookScratch", "CameraChannel", "CameraApply", "Airframe", "Gimbal", "Document", "Playback", "Comfort", "CameraTransform")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_look_commit_contract", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def commit(candidate_valid, preset, base, values, mask, prior):
    result = deepcopy(prior)
    result["valid"] = False
    result["failure"] = "commit_failed"
    if candidate_valid and len(base) == len(values) == len(mask) == 13:
        result.update(
            preset=preset,
            channels=list(CHANNELS),
            base=list(base),
            values=list(values),
            mask=list(mask),
            failure="",
            valid=True,
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (38 if args.paste else 39), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, "exact commit reads")
    contracts.require({member(node) for node in setters} == WRITES, "exact commit writes")
    contracts.require(sum(member(node) == "CameraLookResultValidV1" for node in setters) == 2, "validity invalidated then published")
    contracts.require(sum(member(node) == "CameraLookFailureCodeV1" for node in setters) == 2, "failure staged then cleared")
    for name in ("CameraLookResultBaseValuesV1", "CameraLookResultValuesV1", "CameraLookResultOverrideMaskV1"):
        node = next(node for node in setters if member(node) == name)
        contracts.require("PinType.ContainerType=Array" in node.pins[name].body, f"{name} whole-array publication")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(value in text for value in FORBIDDEN), "commit boundary isolation")
    contracts.require(text.count('MemberName="Array_Length"') == 3, "three exact cardinalities")
    contracts.require(text.count('MemberName="Array_Clear"') == 1 and text.count('MemberName="Array_Add"') == 13, "canonical result identity rebuild")
    contracts.require(all(channel_id in text for channel_id in CHANNELS), "canonical result channel IDs explicit")
    invalidator = next(node for node in setters if member(node) == "CameraLookResultValidV1" and 'DefaultValue="true"' not in node.text)
    publisher = next(node for node in setters if member(node) == "CameraLookResultValidV1" and 'DefaultValue="true"' in node.text)
    contracts.require(not publisher.pins["then"].links, "validity published last")
    if args.paste:
        contracts.require(not invalidator.pins["execute"].links, "paste root unlinked")
    else:
        contracts.require_link(entries[0], "then", invalidator, "execute", "entry invalidates first")

    prior = {"preset": "old", "channels": ["old"], "base": [9.0], "values": [8.0], "mask": [True], "valid": True, "failure": "old"}
    rng = random.Random(0xEDD102)
    for _ in range(80):
        base = [rng.uniform(-20.0, 1000.0) for _ in CHANNELS]
        values = [rng.uniform(-20.0, 1000.0) for _ in CHANNELS]
        mask = [rng.choice((False, True)) for _ in CHANNELS]
        before = (deepcopy(base), deepcopy(values), deepcopy(mask))
        result = commit(True, "raw", base, values, mask, prior)
        contracts.require(result == {"preset": "raw", "channels": list(CHANNELS), "base": base, "values": values, "mask": mask, "valid": True, "failure": ""}, "exact atomic publication")
        contracts.require((base, values, mask) == before and result["base"] is not base and result["values"] is not values and result["mask"] is not mask, "value snapshot")
    failures = (
        (False, [0.0] * 13, [0.0] * 13, [False] * 13),
        (True, [0.0] * 12, [0.0] * 13, [False] * 13),
        (True, [0.0] * 13, [0.0] * 12, [False] * 13),
        (True, [0.0] * 13, [0.0] * 13, [False] * 12),
        (True, [0.0] * 14, [0.0] * 14, [False] * 14),
    )
    for candidate_valid, base, values, mask in failures:
        result = commit(candidate_valid, "raw", base, values, mask, prior)
        contracts.require(all(result[key] == prior[key] for key in ("preset", "channels", "base", "values", "mask")), "failure preserves accepted snapshot")
        contracts.require(not result["valid"] and result["failure"] == "commit_failed", "failure invalidates publication")
    print(f"Camera base-look commit contracts passed ({'paste' if args.paste else 'full'}): 80 snapshots, {len(failures)} failures")


if __name__ == "__main__":
    main()
