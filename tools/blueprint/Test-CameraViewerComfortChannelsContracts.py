"""Structural and executable contracts for viewer-comfort channel staging."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


READS = {"CameraComfortInputChannelValuesV1", "CameraComfortCandidateEffectiveWeightsV1", "CameraComfortCandidateChannelValuesV1", "CameraComfortValidationValidV1"}
WRITES = {"CameraComfortCandidateValidV1"}
FORBIDDEN = (
    "CameraComfortCandidatePositionV1", "CameraComfortCandidateGimbalQuatV1", "CameraComfortCandidateAppliedV1",
    "CameraComfortResult", "CameraComfortFailureCodeV1", "CameraChannel", "CameraLook", "CameraApply",
    "Airframe", "BodyQuat", "Document", "Repository", "Playback", "Server", "CameraTransform",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def stage(values, weights, validation=True):
    candidate = []
    valid = False
    if not validation or len(values) != 13 or len(weights) != 5:
        return candidate, valid
    for index, value in enumerate(values):
        factor = weights[2] if index in (3, 9) else weights[3] if index == 4 else weights[4] if index == 10 else 1.0
        candidate.append(value * factor)
    return candidate, True


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_comfort_channels_contract_base")
    nodes = c.parse_graph(args.graph); c.require(len(nodes) == (28 if args.paste else 29), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]; c.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}; setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    c.require(getters == READS, "exact channel-stage reads"); c.require(setters == WRITES, "exact channel-stage writes")
    c.require(sum(member(node) == "Array_Clear" for node in nodes.values()) == 1, "one candidate rebuild clear")
    c.require(sum(member(node) == "Array_Add" for node in nodes.values()) == 1, "one loop-owned append")
    c.require(sum(member(node) == "Array_Length" for node in nodes.values()) == 2, "source/effective preflight lengths")
    c.require(sum("K2Node_MacroInstance" in node.node_class for node in nodes.values()) == 1, "one bounded channel loop")
    c.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 3, "three comfort-factor reads")
    c.require(sum("K2Node_Select" in node.node_class for node in nodes.values()) == 3, "three exact factor selectors")
    c.require(sum(member(node) == "Multiply_DoubleDouble" for node in nodes.values()) == 1, "one per-channel scale")
    text = args.graph.read_text(encoding="utf-8"); c.require(not any(value in text for value in FORBIDDEN), "no motion/result/external writes")
    c.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    invalidators = [node for node in nodes.values() if member(node) == "CameraComfortCandidateValidV1" and 'DefaultValue="true"' not in node.text]
    publishers = [node for node in nodes.values() if member(node) == "CameraComfortCandidateValidV1" and 'DefaultValue="true"' in node.text]
    c.require(len(invalidators) == len(publishers) == 1, "validity invalidated then published once")
    if args.paste: c.require(not next(node for node in nodes.values() if member(node) == "Array_Clear").pins["execute"].links, "paste root")
    else: c.require_link(entries[0], "then", next(node for node in nodes.values() if member(node) == "Array_Clear"), "execute", "native entry clear")

    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    comfort = load(args.project_root / "tools/trajectory/camera_viewer_comfort_reference.py", "edd_comfort_channels_reference")
    look = load(args.project_root / "tools/trajectory/camera_base_look_reference.py", "edd_comfort_channels_look")
    rng = random.Random(0xEDD10C3); cases = []
    for _ in range(80):
        source = list(look.compose_camera_base_look_v1(rng.choice(("raw", "high_speed_fpv", "vintage_lens")), (), ()).values)
        weights = tuple(rng.random() for _ in range(5)); cases.append((source, weights))
    forward = tuple(stage(values, weights) for values, weights in cases)
    reverse = tuple(reversed(tuple(stage(values, weights) for values, weights in reversed(cases))))
    c.require(forward == reverse, "80 forward/reverse channel candidates")
    for (source, weights), (candidate, valid) in zip(cases, forward):
        c.require(valid and len(candidate) == 13, "complete candidate")
        result = comfort.apply_camera_viewer_comfort_v1(True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0),
                                                        (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), source,
                                                        comfort.CameraViewerComfortSettingsV1(True, *weights))
        c.require(tuple(candidate) == result.camera_channel_values, "oracle channel composition")
        for index in set(range(13)) - {3, 4, 9, 10}: c.require(candidate[index] == source[index], f"channel {index} exact pass-through")
    source = list(look.compose_camera_base_look_v1("vintage_lens", (), ()).values)
    c.require(stage(source, (1.0,) * 5)[0] == source, "disabled/effective-one exact pass-through")
    c.require(stage(source[:-1], (1.0,) * 5) == ([], False), "source shape fails closed")
    c.require(stage(source, (1.0,) * 4) == ([], False), "weight shape fails closed")
    c.require(stage(source, (1.0,) * 5, False) == ([], False), "false validation fails closed")
    print(f"Camera viewer-comfort channel contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} oracle candidates")


if __name__ == "__main__": main()
