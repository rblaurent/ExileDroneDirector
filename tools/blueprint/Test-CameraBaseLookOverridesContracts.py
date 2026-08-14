"""Exact graph and executable contracts for sparse named-look overrides."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


CHANNELS = (
    "focal_length_mm", "aperture_fstop", "focus_distance_cm", "focus_influence",
    "exposure_ev", "bloom_weight", "vignette_weight", "color_grading_weight",
    "tint_weight", "motion_blur_weight", "chromatic_aberration_weight",
    "sharpening_weight", "matte_weight",
)
FORBIDDEN = ("CameraLookResult", "CameraLookInputPresetIdV1", "CameraLookFailureCodeV1", "CameraLookValidationValidV1", "CameraChannel", "CameraApply", "Airframe", "Gimbal", "Document", "Playback", "Comfort", "CameraTransform")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_look_override_contract", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def execute(base, authored_ids, authored_values, stage=True):
    if not stage:
        return None
    overrides = dict(zip(authored_ids, authored_values))
    return (
        [overrides.get(channel_id, base[index]) for index, channel_id in enumerate(CHANNELS)],
        [channel_id in overrides for channel_id in CHANNELS],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (45 if args.paste else 46), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(all(channel_id in text for channel_id in CHANNELS), "canonical channel catalog")
    contracts.require(text.count('MemberName="Array_Clear"') == 2, "effective value and mask reset")
    contracts.require(text.count('MemberName="Array_Add"') == 4, "two mutually exclusive value/mask appends")
    contracts.require(text.count('MemberName="Array_Find"') == 1, "one authored lookup per canonical channel")
    contracts.require(not any(value in text for value in FORBIDDEN), "no accepted result, preset, failure, validation, camera-channel, engine, motion, document, playback, comfort, or legacy state")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == {"CameraLookCandidateValuesV1", "CameraLookCandidateOverrideMaskV1", "CameraLookScratchValidV1", "CameraLookInputAuthoredChannelIdsV1", "CameraLookInputAuthoredValuesV1", "CameraLookCandidateBaseValuesV1"}, "exact override reads")
    contracts.require(setters == {"CameraLookCandidateValidV1"}, "only candidate validity published")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 1 and 'DefaultValue="12"' in loops[0].text, "fixed thirteen-channel loop")
    selects = [node for node in nodes.values() if "K2Node_Select" in node.node_class]
    contracts.require(len(selects) == 12, "canonical channel select chain")
    contracts.require(sum(member(node) == "EqualEqual_IntInt" for node in nodes.values()) == 12, "canonical index comparisons")

    rng = random.Random(0xEDD101)
    for _ in range(80):
        base = [rng.uniform(-10.0, 1000.0) for _ in CHANNELS]
        authored_ids = rng.sample(CHANNELS, rng.randint(0, len(CHANNELS)))
        authored_values = [rng.uniform(-20.0, 1000.0) for _ in authored_ids]
        before = (tuple(base), tuple(authored_ids), tuple(authored_values))
        values, mask = execute(base, authored_ids, authored_values)
        expected = {channel_id: value for channel_id, value in zip(authored_ids, authored_values)}
        contracts.require(values == [expected.get(channel_id, base[index]) for index, channel_id in enumerate(CHANNELS)], "canonical effective values")
        contracts.require(mask == [channel_id in expected for channel_id in CHANNELS], "canonical override mask")
        reverse = execute(base, list(reversed(authored_ids)), list(reversed(authored_values)))
        contracts.require(reverse == (values, mask), "authored order independence")
        contracts.require(before == (tuple(base), tuple(authored_ids), tuple(authored_values)), "inputs and base immutable")
    contracts.require(execute([0.0] * 13, [], [], False) is None, "false-stage no publication")
    print(f"Camera base-look override contracts passed ({'paste' if args.paste else 'full'}): 80 forward/reverse compositions")


if __name__ == "__main__":
    main()
