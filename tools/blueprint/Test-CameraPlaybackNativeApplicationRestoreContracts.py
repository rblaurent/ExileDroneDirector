"""Structural and executable contracts for exact playback-native restoration."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraPlaybackNativeSessionActiveV1", "DroneCameraRef", "DroneCamera",
    "CameraPlaybackNativeBaselineActorTransformV1",
    "CameraPlaybackNativeBaselineComponentRelativeTransformV1",
    "CameraApplyResultValidV1", "CameraApplySessionActiveV1",
}
WRITES = {"CameraPlaybackNativeResultValidV1", "CameraPlaybackNativeSessionActiveV1"}
FORBIDDEN = (
    "CameraPlaybackNativeInput", "CameraPlaybackNativePreflightValidV1",
    "CameraPlaybackNativeAppliedFrameCountV1", "CameraPlaybackNativeFailureCodeV1",
    "CameraPlaybackResult", "CameraApplyBaseline", "CameraApplyCurrent",
    "CameraChannel", "CinematicPose", "CarrierFrame", "CameraTransform",
    "Flypath", "Repository", "Server", "HUD", "UI",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_restore_contract_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def one(nodes, *, cls=None, name=None):
    matches = [node for node in nodes.values() if (cls is None or cls in node.node_class) and (name is None or member(node) == name)]
    if len(matches) != 1: raise RuntimeError(f"expected one cls={cls} member={name}; found {len(matches)}")
    return matches[0]


def simulate(session: dict, *, refs_valid=True, actor_succeeded=True, engine_restored=True) -> dict:
    if not session["active"]: return dict(session)
    result = dict(session); result["result"] = False
    if not refs_valid or not actor_succeeded: return result
    result.update(current_actor=session["baseline_actor"], current_component=session["baseline_component"])
    if not engine_restored: return result
    result.update(current_engine=session["baseline_engine"], active=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (22 if args.paste else 23), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    active_guard = nodes["K2Node_IfThenElse_0"]
    if args.paste: contracts.require(not active_guard.pins["execute"].links, "paste root")
    else: contracts.require_link(entries[0], "then", active_guard, "execute", "entry reaches active guard")
    contracts.require(not active_guard.pins["else"].links, "inactive restore is exact no-op")
    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in getters} == READS, "exact restore reads")
    contracts.require({member(node) for node in setters} == WRITES, "exact restore writes")
    contracts.require([member(node) for node in setters] == ["CameraPlaybackNativeResultValidV1", "CameraPlaybackNativeSessionActiveV1"], "result invalidates; session deactivates only after success")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "restore preserves all unrelated/native diagnostic state")
    for name, count in (
        ("K2_SetActorTransform", 1), ("K2_SetRelativeTransform", 1),
        ("ResetCameraEngineApplicationResultV1", 1), ("RestoreCameraEngineStateV1", 1),
        ("IsValid", 2),
    ):
        contracts.require(text.count(f'MemberName="{name}"') == count, f"exact {name}")
    contracts.require(text.index('MemberName="ResetCameraEngineApplicationResultV1"') < text.index('MemberName="RestoreCameraEngineStateV1"'), "fresh engine restore authority")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 4, "active, reference, actor, engine guards")
    actor_set = one(nodes, cls="K2Node_CallFunction", name="K2_SetActorTransform")
    component_set = one(nodes, cls="K2Node_CallFunction", name="K2_SetRelativeTransform")
    by_member = {member(node): node for node in getters}
    valid_nodes = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "IsValid"]
    contracts.require(len(valid_nodes) == 2 and all("object" in node.pins and "Object" not in node.pins for node in valid_nodes), "restore freezes Unreal's lowercase IsValid object pin")
    contracts.require_link(by_member["CameraPlaybackNativeBaselineActorTransformV1"], "CameraPlaybackNativeBaselineActorTransformV1", actor_set, "NewTransform", "verbatim actor baseline")
    contracts.require_link(by_member["CameraPlaybackNativeBaselineComponentRelativeTransformV1"], "CameraPlaybackNativeBaselineComponentRelativeTransformV1", component_set, "NewTransform", "verbatim component baseline")
    contracts.require("ReturnValue" not in component_set.pins, "void component setter exact shape")
    contracts.require('DefaultValue="true"' in actor_set.pins["bTeleport"].body and 'DefaultValue="true"' in component_set.pins["bTeleport"].body, "exact teleport restore")
    engine_reset = one(nodes, cls="K2Node_CallFunction", name="ResetCameraEngineApplicationResultV1")
    engine_restore = one(nodes, cls="K2Node_CallFunction", name="RestoreCameraEngineStateV1")
    contracts.require_link(component_set, "then", engine_reset, "execute", "pose restored before engine reset")
    contracts.require_link(engine_reset, "then", engine_restore, "execute", "fresh reset before engine restore")
    engine_active = by_member["CameraApplySessionActiveV1"]
    false_compare = one(nodes, cls="K2Node_CallFunction", name="EqualEqual_BoolBool")
    contracts.require_link(engine_active, "CameraApplySessionActiveV1", false_compare, "A", "engine must be inactive after restore")

    rng = random.Random(0xEDD825)
    for index in range(80):
        baseline_actor = {"opaque": ("actor", index), "bits": tuple(rng.getrandbits(53) for _ in range(10))}
        baseline_component = {"opaque": ("component", index), "bits": tuple(rng.getrandbits(53) for _ in range(10))}
        baseline_engine = {"opaque": ("engine", index)}
        session = {
            "baseline_actor": baseline_actor, "baseline_component": baseline_component,
            "baseline_engine": baseline_engine, "current_actor": object(), "current_component": object(),
            "current_engine": object(), "active": True, "count": index,
            "result": True, "failure": "native_apply_failed", "sentinel": object(),
        }
        restored = simulate(session)
        contracts.require(restored["current_actor"] is baseline_actor and restored["current_component"] is baseline_component and restored["current_engine"] is baseline_engine, f"verbatim restore {index}")
        contracts.require(not restored["active"] and not restored["result"], "restored session inactive")
        contracts.require(restored["count"] == index and restored["failure"] == "native_apply_failed" and restored["sentinel"] is session["sentinel"], "diagnostic/count/unowned preservation")
        contracts.require(simulate(restored) == restored, "idempotent repeated restore")
        for label, kwargs in (
            ("refs", {"refs_valid": False}),
            ("actor", {"actor_succeeded": False}),
            ("engine", {"engine_restored": False}),
        ):
            failed = simulate(session, **kwargs)
            contracts.require(failed["active"] and not failed["result"] and failed["count"] == index and failed["failure"] == "native_apply_failed", f"{label} retryable authority")
            if label in ("refs", "actor"):
                contracts.require(failed["current_actor"] is session["current_actor"] and failed["current_component"] is session["current_component"], f"{label} pre-write preservation")
            else:
                contracts.require(failed["current_actor"] is baseline_actor and failed["current_component"] is baseline_component and failed["current_engine"] is session["current_engine"], "engine failure leaves pose restored and session retryable")
    print(f"Camera playback native restore contracts passed ({'paste' if args.paste else 'full'}): 80 exact restores, 240 retryable failures")


if __name__ == "__main__": main()
