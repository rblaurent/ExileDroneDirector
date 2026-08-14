"""Structural and executable contracts for thin-lens DOF computation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from copy import deepcopy
from pathlib import Path


READS = {
    "CameraDofStageFilmbackWidthMmV1",
    "CameraDofStageFilmbackHeightMmV1",
    "CameraDofStageFocalLengthMmV1",
    "CameraDofStageApertureFstopV1",
    "CameraDofStageFocusDistanceCmV1",
    "CameraDofStageValidV1",
}
WRITES = {
    "CameraDofCircleOfConfusionMmV1",
    "CameraDofHyperfocalDistanceCmV1",
    "CameraDofFocalPlaneDistanceCmV1",
    "CameraDofNearLimitCmV1",
    "CameraDofFarLimitCmV1",
    "CameraDofFarUnboundedV1",
    "CameraDofFrontDepthCmV1",
    "CameraDofRearDepthCmV1",
    "CameraDofFocalPlaneWidthCmV1",
    "CameraDofFocalPlaneHeightCmV1",
    "CameraDofFailureCodeV1",
    "CameraDofResultValidV1",
}
FORBIDDEN = (
    "CameraChannelInput",
    "CameraChannelCandidate",
    "CameraChannelCompiled",
    "CameraApply",
    "CameraFocus",
    "Airframe",
    "Document",
    "Transform",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def interpret(stage: dict, prior: dict | None = None) -> dict:
    """Execute the exported graph's guarded publication algorithm."""

    result = deepcopy(prior or {})
    result.update(valid=False, failure="")
    numeric = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    width = stage.get("width")
    height = stage.get("height")
    focal = stage.get("focal")
    aperture = stage.get("aperture")
    focus = stage.get("focus")
    if not (
        stage.get("valid") is True
        and all(numeric(value) for value in (width, height, focal, aperture, focus))
        and width > 0.0
        and height > 0.0
        and 1.0 <= focal <= 1000.0
        and 0.1 <= aperture <= 64.0
        and 1.0 <= focus <= 1.0e9
        and focus * 10.0 > focal
    ):
        result["failure"] = "camera_dof_compute_failed"
        return result

    coc = math.hypot(width, height) / 1500.0
    focus_mm = focus * 10.0
    hyperfocal_mm = focal * focal / (aperture * coc) + focal
    numerator = hyperfocal_mm * focus_mm
    near_cm = numerator / (hyperfocal_mm + (focus_mm - focal)) * 0.1
    unbounded = focus_mm >= hyperfocal_mm + focal
    if unbounded:
        far_cm = rear_cm = 0.0
    else:
        far_cm = numerator / (hyperfocal_mm - (focus_mm - focal)) * 0.1
        rear_cm = far_cm - focus
    result.update(
        coc=coc,
        hyperfocal=hyperfocal_mm * 0.1,
        plane=focus,
        near=near_cm,
        far=far_cm,
        unbounded=unbounded,
        front=focus - near_cm,
        rear=rear_cm,
        width=focus * width / focal,
        height=focus * height / focal,
        failure="",
        valid=True,
    )
    return result


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=2.0e-12, abs_tol=2.0e-12)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_camera_dof_compute_graph_contracts")
    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    reference = load(args.project_root / "tools/trajectory/camera_dof_diagnostics_reference.py", "edd_camera_dof_compute_reference")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (89 if args.paste else 90), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, f"exact reads:{getters}")
    contracts.require({member(node) for node in setters} == WRITES, "exact writes")
    contracts.require(sum(member(node) == "CameraDofResultValidV1" for node in setters) == 3, "one invalidation and two terminal publications")
    contracts.require(sum(member(node) == "CameraDofFarLimitCmV1" for node in setters) == 2, "bounded/unbounded far publication")
    contracts.require(sum(member(node) == "CameraDofRearDepthCmV1" for node in setters) == 2, "bounded/unbounded rear publication")
    contracts.require(sum(member(node) == "CameraDofFarUnboundedV1" for node in setters) == 2, "explicit bounded/unbounded flag")
    root = setters[0]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste root unlinked")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry invalidates result first")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(value in text for value in FORBIDDEN), "protected authorship boundary")
    for function, count in {
        "MakeVector": 1,
        "VSize": 1,
        "Multiply_DoubleDouble": 9,
        "Divide_DoubleDouble": 6,
        "Add_DoubleDouble": 3,
        "Subtract_DoubleDouble": 4,
        "BooleanAND": 19,
    }.items():
        contracts.require(sum(member(node) == function for node in nodes.values()) == count, f"{count} {function} nodes")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 2, "physical guard plus far-bound branch")
    contracts.require(text.count('DefaultValue="camera_dof_compute_failed"') == 1, "stable compute failure code")
    contracts.require(text.count('DefaultValue="true"') >= 3, "stage and terminal true defaults")
    contracts.require(text.count('DefaultValue="1500.0"') == 1, "frozen circle-of-confusion divisor")

    rng = random.Random(0xD0FC01)
    valid_cases = []
    for _ in range(80):
        valid_cases.append(
            {
                "valid": True,
                "width": rng.uniform(12.0, 70.0),
                "height": rng.uniform(8.0, 50.0),
                "focal": rng.uniform(8.0, 600.0),
                "aperture": rng.uniform(0.7, 32.0),
                "focus": rng.uniform(100.0, 250000.0),
            }
        )
    bounded = unbounded = 0
    for index, case in enumerate(valid_cases):
        before = deepcopy(case)
        actual = interpret(case, {"sentinel": 991.0, "valid": True, "failure": "old"})
        values = [case["focal"], case["aperture"], case["focus"], *([0.0] * 10)]
        expected = reference.evaluate_camera_dof_diagnostics_v1(True, case["width"], case["height"], values)
        contracts.require(actual["valid"] and actual["failure"] == "", f"valid case {index}")
        pairs = (
            (actual["coc"], expected.circle_of_confusion_mm),
            (actual["hyperfocal"], expected.hyperfocal_distance_cm),
            (actual["plane"], expected.focal_plane_distance_cm),
            (actual["near"], expected.near_limit_cm),
            (actual["far"], expected.far_limit_cm),
            (actual["front"], expected.front_depth_cm),
            (actual["rear"], expected.rear_depth_cm),
            (actual["width"], expected.focal_plane_width_cm),
            (actual["height"], expected.focal_plane_height_cm),
        )
        contracts.require(all(close(left, right) for left, right in pairs), f"reference equivalence {index}")
        contracts.require(actual["unbounded"] == expected.far_unbounded, f"far flag {index}")
        contracts.require(case == before, "stage immutable")
        unbounded += int(actual["unbounded"])
        bounded += int(not actual["unbounded"])
    contracts.require(bounded > 0 and unbounded > 0, "seed corpus covers both far domains")

    base = {"valid": True, "width": 36.0, "height": 24.0, "focal": 50.0, "aperture": 2.8, "focus": 1000.0}
    failures = (
        {**base, "valid": False},
        {**base, "width": 0.0},
        {**base, "height": math.nan},
        {**base, "focal": 0.99},
        {**base, "focal": 1000.01},
        {**base, "aperture": 0.09},
        {**base, "aperture": 64.01},
        {**base, "focus": 0.99},
        {**base, "focus": math.inf},
        {**base, "focal": 1000.0, "focus": 100.0},
    )
    prior = {"coc": 17.0, "far": 19.0, "unbounded": True, "valid": True, "failure": "old"}
    for index, case in enumerate(failures):
        actual = interpret(case, prior)
        contracts.require(not actual["valid"] and actual["failure"] == "camera_dof_compute_failed", f"failure {index}")
        contracts.require(actual["coc"] == 17.0 and actual["far"] == 19.0 and actual["unbounded"] is True, "invalid compute preserves unpublished diagnostics")
    print(f"Camera DOF compute contracts passed ({'paste' if args.paste else 'full'}): {len(nodes)} nodes, 80 reference cases ({bounded} bounded/{unbounded} unbounded), {len(failures)} failures")


if __name__ == "__main__":
    main()
