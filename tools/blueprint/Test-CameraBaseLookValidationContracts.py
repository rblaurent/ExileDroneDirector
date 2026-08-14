"""Structural and executable contracts for named camera-look input validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


PRESETS = (
    "raw", "clean_cinematic", "epic_landscape", "dreamy_shallow_focus",
    "dark_sorcery", "high_speed_fpv", "vintage_lens", "documentary",
)
BOUNDS = {
    "focal_length_mm": (1.0, 1000.0),
    "aperture_fstop": (0.1, 64.0),
    "focus_distance_cm": (1.0, 1_000_000_000.0),
    "focus_influence": (0.0, 1.0),
    "exposure_ev": (-20.0, 20.0),
    "bloom_weight": (0.0, 1.0),
    "vignette_weight": (0.0, 1.0),
    "color_grading_weight": (0.0, 1.0),
    "tint_weight": (0.0, 1.0),
    "motion_blur_weight": (0.0, 1.0),
    "chromatic_aberration_weight": (0.0, 1.0),
    "sharpening_weight": (0.0, 1.0),
    "matte_weight": (0.0, 1.0),
}
READS = {"CameraLookInputPresetIdV1", "CameraLookInputAuthoredChannelIdsV1", "CameraLookInputAuthoredValuesV1", "CameraLookScratchValidV1"}
WRITES = {"CameraLookValidationValidV1", "CameraLookScratchValidV1", "CameraLookScratchChannelIndexV1", "CameraLookFailureCodeV1"}
FORBIDDEN = ("CameraLookCandidate", "CameraLookResultPreset", "CameraLookResultChannel", "CameraLookResultBase", "CameraLookResultValues", "CameraLookResultOverride", "CameraChannel", "CameraApply", "Airframe", "Gimbal", "Document", "Playback", "Comfort", "CameraTransform")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_look_validation_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def validate(preset_id, channel_ids, values):
    if preset_id not in PRESETS or len(channel_ids) != len(values) or len(channel_ids) > len(BOUNDS):
        return False
    for index, (channel_id, value) in enumerate(zip(channel_ids, values)):
        if channel_id not in BOUNDS or channel_ids.index(channel_id) != index:
            return False
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False
        minimum, maximum = BOUNDS[channel_id]
        if not minimum <= float(value) <= maximum:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (90 if args.paste else 91), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    loops = [node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class]
    contracts.require(len(loops) == 1, "one bounded authored-channel loop")
    contracts.require(sum(member(node) == "Array_Find" for node in nodes.values()) == 1, "one deterministic uniqueness lookup")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact validation reads")
    contracts.require(setters == WRITES, "exact validation writes")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(all(preset in text for preset in PRESETS), "exact preset allowlist")
    contracts.require(all(channel_id in text for channel_id in BOUNDS), "exact channel allowlist")
    contracts.require(not any(value in text for value in FORBIDDEN), "no candidate, accepted result, camera-channel, engine, motion, document, playback, comfort, or legacy mutation")
    string_calls = [node for node in nodes.values() if member(node) in {"EqualEqual_StrStr", "NotEqual_StrStr"}]
    contracts.require(len(string_calls) == len(PRESETS) + len(BOUNDS), "exact string comparison count")
    contracts.require(all("KismetStringLibrary" in node.text and "KismetMathLibrary" not in node.text for node in string_calls), "reconstructable string comparisons")
    invalidators = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == "CameraLookValidationValidV1" and 'DefaultValue="true"' not in node.text]
    contracts.require(len(invalidators) == 1, "validation invalidated first")
    if not args.paste:
        contracts.require_link(entries[0], "then", invalidators[0], "execute", "native entry to validation root")

    rng = random.Random(0xEDD100)
    valid_cases = [(preset, [], []) for preset in PRESETS]
    channel_ids = tuple(BOUNDS)
    for _ in range(80):
        ids = rng.sample(channel_ids, rng.randint(0, len(channel_ids)))
        values = [rng.uniform(*BOUNDS[channel_id]) for channel_id in ids]
        valid_cases.append((rng.choice(PRESETS), ids, values))
    contracts.require(all(validate(*case) for case in valid_cases), "seeded valid requests")
    failures = (
        ("unknown", [], []),
        ("raw", ["focal_length_mm"], []),
        ("raw", list(channel_ids) + ["focal_length_mm"], [1.0] * 14),
        ("raw", ["unknown"], [0.5]),
        ("raw", ["bloom_weight", "bloom_weight"], [0.2, 0.3]),
        ("raw", ["focal_length_mm"], [math.nan]),
        ("raw", ["aperture_fstop"], [math.inf]),
        ("raw", ["focal_length_mm"], [0.99]),
        ("raw", ["aperture_fstop"], [64.01]),
        ("raw", ["focus_distance_cm"], [0.0]),
        ("raw", ["exposure_ev"], [20.01]),
        ("raw", ["matte_weight"], [-0.01]),
        ("raw", ["motion_blur_weight"], [1.01]),
    )
    contracts.require(all(not validate(*case) for case in failures), "failure families")
    before = tuple((preset, tuple(ids), tuple(values)) for preset, ids, values in valid_cases)
    [validate(*case) for case in valid_cases]
    contracts.require(before == tuple((preset, tuple(ids), tuple(values)) for preset, ids, values in valid_cases), "inputs immutable")
    print(f"Camera base-look validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid_cases)} valid, {len(failures)} failures")


if __name__ == "__main__":
    main()
