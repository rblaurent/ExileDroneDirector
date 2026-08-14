"""Structural and executable contracts for viewer-comfort input validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraComfortInputFrameValidV1", "CameraComfortInputPositionV1",
    "CameraComfortInputGimbalQuatV1", "CameraComfortInputProceduralTranslationOffsetV1",
    "CameraComfortInputProceduralRotationOffsetV1", "CameraComfortInputChannelValuesV1",
    "CameraComfortRollWeightV1", "CameraComfortShakeWeightV1", "CameraComfortBlurWeightV1",
    "CameraComfortExposureChangeWeightV1", "CameraComfortChromaticAberrationWeightV1",
    "CameraComfortScratchValidV1",
}
WRITES = {"CameraComfortValidationValidV1", "CameraComfortScratchValidV1", "CameraComfortScratchChannelIndexV1", "CameraComfortFailureCodeV1"}
FORBIDDEN = (
    "CameraComfortCandidate", "CameraComfortResultPosition", "CameraComfortResultGimbal",
    "CameraComfortResultChannel", "CameraComfortResultEffective", "CameraComfortResultApplied",
    "CameraChannel", "CameraLook", "CameraApply", "Airframe", "BodyQuat", "Document",
    "Repository", "Playback", "Server", "CameraTransform",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_comfort_validation_contract_base")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (145 if args.paste else 146), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact validation reads")
    contracts.require(setters == WRITES, "exact validation writes")
    contracts.require(sum(member(node) == "BreakVector" for node in nodes.values()) == 2, "two finite vector decompositions")
    contracts.require(sum(member(node) == "Quat_IsFinite" for node in nodes.values()) == 2, "two quaternion finite guards")
    contracts.require(sum(member(node) == "Quat_Size" for node in nodes.values()) == 2, "two quaternion unit guards")
    contracts.require(sum("K2Node_MacroInstance" in node.node_class for node in nodes.values()) == 1, "one bounded thirteen-channel loop")
    contracts.require(sum(member(node) == "Array_Length" for node in nodes.values()) == 1, "one exact channel cardinality")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()), "no reroute knots")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(value in text for value in FORBIDDEN), "no candidate/result/external authorship mutation")
    for literal in ("13", "0.999999", "1.000001", "1000.0", "64.0", "1000000000.0", "-20.0", "20.0"):
        contracts.require(literal in text, f"required validation literal {literal}")
    invalidators = [node for node in nodes.values() if member(node) == "CameraComfortValidationValidV1" and 'DefaultValue="true"' not in node.text]
    contracts.require(len(invalidators) == 1, "validation invalidated first")
    if args.paste:
        contracts.require(not invalidators[0].pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", invalidators[0], "execute", "native entry to validation root")

    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    comfort = load(args.project_root / "tools/trajectory/camera_viewer_comfort_reference.py", "edd_comfort_validation_reference")
    look = load(args.project_root / "tools/trajectory/camera_base_look_reference.py", "edd_comfort_validation_look")
    base_values = look.compose_camera_base_look_v1("raw", (), ()).values
    rng = random.Random(0xEDD10C1)
    valid_cases = []
    for _ in range(80):
        half = math.radians(rng.uniform(-170.0, 170.0)) * 0.5
        quat = (math.sin(half), 0.0, 0.0, math.cos(half))
        settings = comfort.CameraViewerComfortSettingsV1(rng.choice((True, False)), *(rng.random() for _ in range(5)))
        valid_cases.append((True, tuple(rng.uniform(-1e6, 1e6) for _ in range(3)), quat,
                            tuple(rng.uniform(-100.0, 100.0) for _ in range(3)), (0.0, 0.0, 0.0, 1.0), base_values, settings))
    for case in valid_cases:
        comfort.apply_camera_viewer_comfort_v1(*case)
    failures = (
        (False, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), base_values, comfort.CameraViewerComfortSettingsV1()),
        (True, (math.nan, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), base_values, comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 2.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), base_values, comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, math.inf, 0.0), (0.0, 0.0, 0.0, 1.0), base_values, comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0), base_values, comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), base_values[:-1], comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), tuple(math.inf if i == 0 else v for i, v in enumerate(base_values)), comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0,) + base_values[1:], comfort.CameraViewerComfortSettingsV1()),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), base_values, comfort.CameraViewerComfortSettingsV1(True, -0.01, 1.0, 1.0, 1.0, 1.0)),
        (True, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), base_values, comfort.CameraViewerComfortSettingsV1(True, 1.0, 1.0, 1.0, 1.0, 1.01)),
    )
    rejected = 0
    for case in failures:
        try:
            comfort.apply_camera_viewer_comfort_v1(*case)
        except comfort.CameraViewerComfortError:
            rejected += 1
    contracts.require(rejected == len(failures), "all failure families rejected")
    before = tuple(valid_cases)
    [comfort.apply_camera_viewer_comfort_v1(*case) for case in reversed(valid_cases)]
    contracts.require(tuple(valid_cases) == before, "inputs and preferences immutable")
    print(f"Camera viewer-comfort validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid_cases)} valid, {len(failures)} failures")


if __name__ == "__main__":
    main()
