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


def simulate(session: dict, frame: dict, *, ready=True, actor_verified=True, component_verified=True, engine_succeeded=True) -> dict:
    staged = dict(session); staged.update(result=False, failure="native_apply_failed")
    if not ready:
        return staged
    staged["current_actor"] = {
        "translation": frame["position"], "rotation": frame["body"],
        "scale": session["baseline_actor"]["scale"],
    }
    staged["current_component"] = {
        "translation": session["baseline_component"]["translation"],
        "rotation": frame["relative"],
        "scale": session["baseline_component"]["scale"],
    }
    if not actor_verified:
        return restore(staged)
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
    contracts.require(len(nodes) == (50 if args.paste else 51), f"node count {len(nodes)}")
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
        ("K2_SetActorTransform", 1), ("K2_SetRelativeRotation", 1),
        ("ApplyCameraEngineFrameV1", 1), ("RestoreCameraPlaybackNativeStateV1", 1),
        ("GetTransform", 1), ("GetRelativeTransform", 1), ("MakeTransform", 1), ("BreakTransform", 3),
        ("Vector_Distance", 1), ("Quat_Rotator", 2), ("Conv_RotatorToQuaternion", 0),
        ("EqualEqual_RotatorRotator", 2), ("EqualEqual_QuatQuat", 0), ("LessEqual_DoubleDouble", 1),
        ("PrintString", 4),
    ):
        contracts.require(text.count(f'MemberName="{name}"') == count, f"exact {name} count")
    contracts.require(text.count('MemberName="IsValid"') == 2, "actor and component revalidated")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 5, "apply, three authored pose-readback, and engine guards")

    by_member = {}
    for node in getters: by_member.setdefault(member(node), []).append(node)
    actor_set = one(nodes, cls="K2Node_CallFunction", name="K2_SetActorTransform")
    component_set = one(nodes, cls="K2Node_CallFunction", name="K2_SetRelativeRotation")
    actor_get = one(nodes, cls="K2Node_CallFunction", name="GetTransform")
    component_get = one(nodes, cls="K2Node_CallFunction", name="GetRelativeTransform")
    contracts.require(
        "bIsReference=False" in component_get.pins["ReturnValue"].body
        and "bIsConst=False" in component_get.pins["ReturnValue"].body,
        "component relative Transform uses Unreal's canonical by-value return",
    )
    make_nodes = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "MakeTransform"]
    quat_rotators = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "Quat_Rotator"]
    contracts.require(len(make_nodes) == 1 and len(quat_rotators) == 2, "distinct actor transform and component rotation construction")
    body_get = by_member["CameraPlaybackNativeInputBodyWorldQuatV1"][0]
    relative_get = by_member["CameraPlaybackNativeInputGimbalRelativeQuatV1"][0]
    body_rotator = next(node for node in quat_rotators if contracts.linked(body_get, "CameraPlaybackNativeInputBodyWorldQuatV1", node, "Q"))
    relative_rotator = next(node for node in quat_rotators if contracts.linked(relative_get, "CameraPlaybackNativeInputGimbalRelativeQuatV1", node, "Q"))
    for rotator in (body_rotator, relative_rotator):
        contracts.require("SubPins=" not in rotator.pins["Q"].body, "Quat-to-Rotator input is collapsed before parent-pin linking")
        contracts.require(not any(name.startswith("Q_") for name in rotator.pins), "no hidden split quaternion inputs can override authored rotation")
    actor_make = next(node for node in make_nodes if contracts.linked(body_rotator, "ReturnValue", node, "Rotation"))
    contracts.require_link(actor_make, "ReturnValue", actor_set, "NewTransform", "body owns actor transform")
    contracts.require_link(relative_rotator, "ReturnValue", component_set, "NewRotation", "relative gimbal exclusively owns component rotation")
    contracts.require(not actor_set.pins["ReturnValue"].links, "setter metadata cannot overrule authoritative actor readback")
    contracts.require_link(actor_set, "then", component_set, "execute", "body and gimbal writes form one verified transaction")
    contracts.require("ReturnValue" not in component_set.pins, "void component setter has no synthetic actor result")
    contracts.require('DefaultValue="true"' in actor_set.pins["bTeleport"].body and 'DefaultValue="true"' in component_set.pins["bTeleport"].body, "pose writes teleport without sweep")

    break_nodes = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "BreakTransform"]
    actor_break = next(node for node in break_nodes if contracts.linked(actor_get, "ReturnValue", node, "InTransform"))
    component_break = next(node for node in break_nodes if contracts.linked(component_get, "ReturnValue", node, "InTransform"))
    rotator_equal = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "EqualEqual_RotatorRotator"]
    body_equal = next(node for node in rotator_equal if contracts.linked(actor_break, "Rotation", node, "A"))
    contracts.require_link(actor_break, "Rotation", body_equal, "A", "observed actor Rotator owns body readback comparison")
    contracts.require_link(body_rotator, "ReturnValue", body_equal, "B", "authored body Rotator owns actor readback comparison")
    contracts.require('DefaultValue="0.000100"' in body_equal.pins["ErrorTolerance"].body, "canonical actor-body Rotator equality tolerance")
    relative_equal = next(node for node in rotator_equal if contracts.linked(component_break, "Rotation", node, "A"))
    contracts.require_link(relative_rotator, "ReturnValue", relative_equal, "B", "authored relative-gimbal Rotator owns component readback comparison")
    contracts.require('DefaultValue="0.000001"' in relative_equal.pins["ErrorTolerance"].body, "tight relative-gimbal Rotator equality tolerance")
    position_distance = one(nodes, cls="K2Node_CallFunction", name="Vector_Distance")
    contracts.require_link(actor_break, "Location", position_distance, "V1", "observed actor position owns distance left input")
    contracts.require_link(by_member["CameraPlaybackNativeInputPositionV1"][0], "CameraPlaybackNativeInputPositionV1", position_distance, "V2", "authored position owns distance right input")
    position_limit = one(nodes, cls="K2Node_CallFunction", name="LessEqual_DoubleDouble")
    contracts.require_link(position_distance, "ReturnValue", position_limit, "A", "native position distance is bounded")
    contracts.require('DefaultValue="0.001000"' in position_limit.pins["B"].body, "one-thousandth-centimeter position verification tolerance")
    contracts.require(not any(member(node) in {"BreakQuat", "Subtract_DoubleDouble", "Add_DoubleDouble"} for node in nodes.values()), "no componentwise float-to-double quaternion comparison")

    restore_call = one(nodes, cls="K2Node_CallFunction", name="RestoreCameraPlaybackNativeStateV1")
    branches = sorted((node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class), key=lambda node: node.name)
    diagnostics = [node for node in nodes.values() if "K2Node_CallFunction" in node.node_class and member(node) == "PrintString"]
    diagnostic_markers = {
        "EDD_CAMERA_PLAYBACK_NATIVE_APPLY|POSE_POSITION_READBACK_FAILED",
        "EDD_CAMERA_PLAYBACK_NATIVE_APPLY|POSE_BODY_READBACK_FAILED",
        "EDD_CAMERA_PLAYBACK_NATIVE_APPLY|POSE_GIMBAL_READBACK_FAILED",
        "EDD_CAMERA_PLAYBACK_NATIVE_APPLY|ENGINE_READBACK_FAILED",
    }
    contracts.require({re.search(r'DefaultValue="([^"]+)"', node.pins["InString"].body).group(1) for node in diagnostics} == diagnostic_markers, "exact live failure diagnostics")
    contracts.require(all('DefaultValue="false"' in node.pins["bPrintToScreen"].body and 'DefaultValue="true"' in node.pins["bPrintToLog"].body for node in diagnostics), "diagnostics are log-only")
    contracts.require(sum(contracts.linked(node, "then", restore_call, "execute") for node in diagnostics) == 4, "all post-write diagnostics converge on exact restore")
    engine_apply = one(nodes, cls="K2Node_CallFunction", name="ApplyCameraEngineFrameV1")
    engine_result_get = by_member["CameraApplyResultValidV1"][0]
    engine_guard = next(branch for branch in branches if contracts.linked(engine_result_get, "CameraApplyResultValidV1", branch, "Condition"))
    position_guard = next(branch for branch in branches if contracts.linked(position_limit, "ReturnValue", branch, "Condition"))
    body_guard = next(branch for branch in branches if contracts.linked(body_equal, "ReturnValue", branch, "Condition"))
    relative_guard = next(branch for branch in branches if contracts.linked(relative_equal, "ReturnValue", branch, "Condition"))
    contracts.require_link(component_set, "then", position_guard, "execute", "position readback is checked immediately after both pose writes")
    contracts.require_link(position_guard, "then", body_guard, "execute", "body readback follows position")
    contracts.require_link(body_guard, "then", relative_guard, "execute", "gimbal readback follows body")
    contracts.require_link(relative_guard, "then", engine_apply, "execute", "engine apply begins only after all three pose tracks pass")
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
            ("actor", {"actor_verified": False}),
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
