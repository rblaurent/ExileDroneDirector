"""Structural and executable contracts for playback-native input staging."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


POSE_MAPPING = {
    "CameraPlaybackResultPositionV1": "CameraPlaybackNativeInputPositionV1",
    "CameraPlaybackResultBodyWorldQuatV1": "CameraPlaybackNativeInputBodyWorldQuatV1",
    "CameraPlaybackResultGimbalWorldQuatV1": "CameraPlaybackNativeInputGimbalWorldQuatV1",
    "CameraPlaybackResultGimbalRelativeQuatV1": "CameraPlaybackNativeInputGimbalRelativeQuatV1",
}
READS = {
    "CameraApplyInputTargetValuesV1",
    "CameraPlaybackResultValidV1",
    "CameraPlaybackResultChannelValuesV1",
    "CameraPlaybackResultFilmbackPresetIdV1",
    "CameraPlaybackResultFilmbackSensorWidthMmV1",
    "CameraPlaybackResultFilmbackSensorHeightMmV1",
    *POSE_MAPPING,
}
WRITES = {
    "CameraApplyInputValidV1",
    "CameraApplyInputFilmbackPresetIdV1",
    "CameraPlaybackNativeInputValidV1",
    "CameraPlaybackNativeStageValidV1",
    *POSE_MAPPING.values(),
}
FORBIDDEN = (
    "CameraApplyCapability",
    "CameraApplyBaseline",
    "CameraApplyCurrent",
    "CameraApplySessionActiveV1",
    "CameraApplyAppliedFrameCountV1",
    "CameraChannelResult",
    "CameraChannelInput",
    "CameraChannelCandidate",
    "CameraChannelCompiled",
    "CinematicPoseResultQuatV1",
    "CarrierFrameResultQuatV1",
    "CameraTransform",
    "CameraPlaybackNativeBaseline",
    "CameraPlaybackNativeSessionActiveV1",
    "CameraPlaybackNativeAppliedFrameCountV1",
    "DroneCameraRef",
    "Flypath",
    "Repository",
    "Server",
    "HUD",
    "UI",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_stage_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def simulate(source: dict, prior: dict) -> dict:
    result = {
        "pose": prior["pose"],
        "id": "",
        "values": [],
        "apply_valid": False,
        "native_valid": False,
        "stage_valid": False,
    }
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
        result.update(
            pose=(source["position"], source["body"], source["gimbal"], source["relative"]),
            id=source["id"],
            values=[float(source["width"]), float(source["height"]), *values],
            apply_valid=True,
            native_valid=True,
            stage_valid=True,
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
    contracts.require(len(nodes) == (69 if args.paste else 70), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to staging root")
    getter_nodes = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setter_nodes = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    getters = {member(node) for node in getter_nodes}
    setters = [member(node) for node in setter_nodes]
    contracts.require(getters == READS, f"exact staging reads: {getters}")
    contracts.require(set(setters) == WRITES, f"exact staging writes: {setters}")
    contracts.require(setters.count("CameraApplyInputValidV1") == 2, "engine validity brackets staging")
    contracts.require(setters.count("CameraPlaybackNativeInputValidV1") == 2, "native validity brackets staging")
    contracts.require(setters.count("CameraPlaybackNativeStageValidV1") == 2, "stage validity brackets staging")
    contracts.require(setters[-1] == "CameraPlaybackNativeStageValidV1", "stage validity publishes last")
    by_getter = {member(node): node for node in getter_nodes}
    by_setter = {member(node): node for node in setter_nodes if member(node) in POSE_MAPPING.values()}
    for source, target in POSE_MAPPING.items():
        contracts.require_link(by_getter[source], source, by_setter[target], target, f"exact {source} to {target}")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "protected or legacy ownership forbidden")
    contracts.require(sum('MemberName="Array_Add"' in node.text for node in nodes.values()) == 15, "exact 15 target appends")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 13, "exact 13 channel reads")
    contracts.require("KismetStringLibrary" in text and 'MemberName="NotEqual_StrStr"' in text, "correct string library")

    rng = random.Random(0xEDD821)
    for index in range(80):
        source = {
            "valid": True,
            "id": f"filmback_{index}",
            "width": 24.0 + rng.random() * 20.0,
            "height": 12.0 + rng.random() * 20.0,
            "values": tuple(rng.uniform(-5.0, 5.0) for _ in range(13)),
            "position": tuple(rng.uniform(-1000.0, 1000.0) for _ in range(3)),
            "body": (0.0, 0.0, 0.3826834324, 0.9238795325),
            "gimbal": (0.0, 0.2588190451, 0.0, 0.9659258263),
            "relative": (-0.0990457605, 0.2391176184, -0.3696438106, 0.8923991008),
        }
        prior = {"pose": (object(), object(), object(), object())}
        before = dict(source)
        staged = simulate(source, prior)
        contracts.require(staged["stage_valid"] and staged["native_valid"] and staged["apply_valid"], f"frame {index}")
        contracts.require(staged["pose"] == (source["position"], source["body"], source["gimbal"], source["relative"]), "pose mapping")
        contracts.require(staged["values"] == [source["width"], source["height"], *source["values"]], "canonical lens mapping")
        contracts.require(source == before, "source snapshot immutable")

    base = {
        "valid": True, "id": "filmback", "width": 36.0, "height": 24.0,
        "values": tuple(range(13)), "position": (1.0, 2.0, 3.0),
        "body": (0.0, 0.0, 0.0, 1.0), "gimbal": (0.0, 0.0, 0.0, 1.0),
        "relative": (0.0, 0.0, 0.0, 1.0),
    }
    failures = (
        {**base, "valid": False}, {**base, "id": ""},
        {**base, "width": 0.0}, {**base, "width": math.nan},
        {**base, "height": 0.0}, {**base, "height": math.inf},
        {**base, "values": tuple(range(12))}, {**base, "values": tuple(range(14))},
    )
    prior_pose = (object(), object(), object(), object())
    for index, source in enumerate(failures):
        staged = simulate(source, {"pose": prior_pose})
        contracts.require(staged["pose"] is prior_pose, f"failure {index} pose preserved")
        contracts.require(staged["id"] == "" and staged["values"] == [], f"failure {index} lens cleared")
        contracts.require(not staged["stage_valid"] and not staged["native_valid"] and not staged["apply_valid"], f"failure {index} fail closed")
    print(
        f"Camera playback native staging contracts passed "
        f"({'paste' if args.paste else 'full'}): 80 snapshots, 8 failures"
    )


if __name__ == "__main__":
    main()
