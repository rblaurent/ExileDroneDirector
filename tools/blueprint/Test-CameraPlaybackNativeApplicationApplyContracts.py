"""Structural and executable contracts for transactional playback-native apply."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "DroneCameraRef", "DroneCamera",
    "CameraPlaybackNativePreflightValidV1", "CameraPlaybackNativeSessionActiveV1",
    "CameraApplyScratchStageValidV1", "CameraApplySessionActiveV1",
    "CameraPlaybackNativeInputPositionV1", "CameraPlaybackNativeInputBodyWorldQuatV1",
    "CameraPlaybackNativeInputGimbalRelativeQuatV1",
    "CameraPlaybackNativeBaselineActorTransformV1",
    "CameraPlaybackNativeBaselineComponentRelativeTransformV1",
    "CameraApplyResultValidV1", "CameraPlaybackNativeAppliedFrameCountV1",
}
WRITES = {
    "CameraPlaybackNativeResultValidV1",
    "CameraPlaybackNativeFailureCodeV1",
    "CameraPlaybackNativeAppliedFrameCountV1",
}
FORBIDDEN = (
    "CameraPlaybackNativeInputGimbalWorldQuatV1",
    "CameraPlaybackResult",
    "CameraApplyBaseline",
    "CameraApplyCurrent",
    "CameraApplyInputTargetValuesV1",
    "CameraChannel",
    "CinematicPose",
    "CarrierFrame",
    "CameraTransform",
    "Flypath",
    "Repository",
    "Server",
    "HUD",
    "UI",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_apply_contract_base", path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def one(nodes, *, cls=None, name=None):
    matches = [node for node in nodes.values() if (cls is None or cls in node.node_class) and (name is None or member(node) == name)]
    if len(matches) != 1: raise RuntimeError(f"expected one cls={cls} member={name}; found {len(matches)}")
    return matches[0]


def restore(session: dict) -> dict:
    result = dict(session)
    result.update(
        current_actor=session["baseline_actor"], current_component=session["baseline_component"],
        current_engine=session["baseline_engine"], active=False, result=False,
        failure="native_apply_failed",
    )
    return result


def simulate(session: dict, frame: dict, *, ready=True, actor_succeeded=True, component_verified=True, engine_succeeded=True) -> dict:
    staged = dict(session); staged.update(result=False, failure="native_apply_failed")
    if not ready:
        return staged
    if not actor_succeeded:
        return restore(staged)
    staged["current_actor"] = {
        "translation": frame["position"], "rotation": frame["body"],
        "scale": session["baseline_actor"]["scale"],
    }
    staged["current_component"] = {
        "translation": session["baseline_component"]["translation"],
        "rotation": frame["relative"],
        "scale": session["baseline_component"]["scale"],
    }
    if not component_verified:
        return restore(staged)
    if not engine_succeeded:
        return restore(staged)
    staged.update(current_engine=frame["engine"], count=session["count"] + 1, result=True, failure="")
    return staged


def axis_angle(axis, radians):
    half = radians * 0.5; sine = math.sin(half)
    return tuple(component * sine for component in axis) + (math.cos(half),)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (84 if args.paste else 85), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    if args.paste: contracts.require(not root.pins["execute"].links, "paste execution root")
    else: contracts.require_link(entries[0], "then", root, "execute", "entry invalidates native result")

    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in getters} == READS, f"exact apply reads: {{member(node) for node in getters}}")
    setter_names = [member(node) for node in setters]
    contracts.require(set(setter_names) == WRITES, f"exact apply writes: {setter_names}")
    contracts.require(setter_names.count("CameraPlaybackNativeResultValidV1") == 2, "result invalidates then publishes")
    contracts.require(setter_names.count("CameraPlaybackNativeFailureCodeV1") == 2, "diagnostic stages then clears")
    contracts.require(setter_names[-1] == "CameraPlaybackNativeResultValidV1", "native result publishes last")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "apply ownership is exact")
    for name, count in (
        ("K2_SetActorTransform", 1), ("K2_SetRelativeTransform", 1),
        ("ApplyCameraEngineFrameV1", 1), ("RestoreCameraPlaybackNativeStateV1", 1),
        ("GetRelativeTransform", 1), ("MakeTransform", 2), ("BreakTransform", 3),
        ("Quat_Rotator", 2), ("Conv_RotatorToQuaternion", 1),
    ):
        contracts.require(text.count(f'MemberName="{name}"') == count, f"exact {name} count")
    contracts.require(text.count('MemberName="IsValid"') == 2, "actor and component revalidated")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 4, "apply, actor, component-verification, engine guards")

    by_member = {}
    for node in getters: by_member.setdefault(member(node), []).append(node)
    actor_set = one(nodes, cls="K2Node_CallFunction", name="K2_SetActorTransform")
    component_set = one(nodes, cls="K2Node_CallFunction", name="K2_SetRelativeTransform")
    make_nodes = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "MakeTransform"]
    quat_rotators = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "Quat_Rotator"]
    contracts.require(len(make_nodes) == 2 and len(quat_rotators) == 2, "distinct actor/component construction")
    body_get = by_member["CameraPlaybackNativeInputBodyWorldQuatV1"][0]
    relative_get = by_member["CameraPlaybackNativeInputGimbalRelativeQuatV1"][0]
    body_rotator = next(node for node in quat_rotators if contracts.linked(body_get, "CameraPlaybackNativeInputBodyWorldQuatV1", node, "Q"))
    relative_rotator = next(node for node in quat_rotators if contracts.linked(relative_get, "CameraPlaybackNativeInputGimbalRelativeQuatV1", node, "Q"))
    actor_make = next(node for node in make_nodes if contracts.linked(body_rotator, "ReturnValue", node, "Rotation"))
    component_make = next(node for node in make_nodes if contracts.linked(relative_rotator, "ReturnValue", node, "Rotation"))
    contracts.require_link(actor_make, "ReturnValue", actor_set, "NewTransform", "body owns actor transform")
    contracts.require_link(component_make, "ReturnValue", component_set, "NewTransform", "relative gimbal owns component transform")
    contracts.require("ReturnValue" not in component_set.pins, "void component setter has no synthetic actor result")
    contracts.require('DefaultValue="true"' in actor_set.pins["bTeleport"].body and 'DefaultValue="true"' in component_set.pins["bTeleport"].body, "pose writes teleport without sweep")

    restore_call = one(nodes, cls="K2Node_CallFunction", name="RestoreCameraPlaybackNativeStateV1")
    branches = sorted((node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class), key=lambda node: node.name)
    contracts.require(sum(contracts.linked(branch, "else", restore_call, "execute") for branch in branches) == 3, "all three post-write failures converge on restore")
    engine_apply = one(nodes, cls="K2Node_CallFunction", name="ApplyCameraEngineFrameV1")
    engine_result_get = by_member["CameraApplyResultValidV1"][0]
    engine_guard = next(branch for branch in branches if contracts.linked(engine_result_get, "CameraApplyResultValidV1", branch, "Condition"))
    contracts.require_link(engine_apply, "then", engine_guard, "execute", "fresh engine result checked immediately")

    rng = random.Random(0xEDD824)
    for index in range(80):
        baseline_actor = {"translation": (9.0, 8.0, 7.0), "rotation": object(), "scale": tuple(rng.uniform(0.5, 2.0) for _ in range(3))}
        baseline_component = {"translation": tuple(rng.uniform(-5.0, 5.0) for _ in range(3)), "rotation": object(), "scale": tuple(rng.uniform(0.5, 2.0) for _ in range(3))}
        baseline_engine = {"opaque": ("baseline", index)}
        session = {
            "baseline_actor": baseline_actor, "baseline_component": baseline_component,
            "baseline_engine": baseline_engine, "current_actor": object(), "current_component": object(),
            "current_engine": object(), "active": True, "count": index, "result": False, "failure": "",
        }
        frame = {
            "position": tuple(rng.uniform(-10000.0, 10000.0) for _ in range(3)),
            "body": axis_angle((0.0, 0.0, 1.0), rng.uniform(-math.pi, math.pi)),
            "relative": axis_angle((0.0, 1.0, 0.0), rng.uniform(-1.0, 1.0)),
            "engine": {"opaque": ("frame", index)},
        }
        applied = simulate(session, frame)
        contracts.require(applied["result"] and applied["count"] == index + 1 and applied["active"], f"apply {index}")
        contracts.require(applied["current_actor"] == {"translation": frame["position"], "rotation": frame["body"], "scale": baseline_actor["scale"]}, "actor owns body and position only")
        contracts.require(applied["current_component"] == {"translation": baseline_component["translation"], "rotation": frame["relative"], "scale": baseline_component["scale"]}, "component owns relative gimbal only")
        for label, kwargs in (
            ("actor", {"actor_succeeded": False}),
            ("component", {"component_verified": False}),
            ("engine", {"engine_succeeded": False}),
        ):
            failed = simulate(session, frame, **kwargs)
            contracts.require(not failed["active"] and not failed["result"] and failed["failure"] == "native_apply_failed", f"{label} failure authority")
            contracts.require(failed["current_actor"] is baseline_actor and failed["current_component"] is baseline_component and failed["current_engine"] is baseline_engine, f"{label} exact rollback")
            contracts.require(failed["count"] == index, f"{label} count preserved")
    rejected = simulate(session, frame, ready=False)
    contracts.require(rejected["current_actor"] is session["current_actor"] and rejected["current_component"] is session["current_component"], "pre-write rejection performs no native mutation")
    print(f"Camera playback native apply contracts passed ({'paste' if args.paste else 'full'}): 80 frames, 240 exact rollbacks")


if __name__ == "__main__": main()
