"""Structural and executable contracts for one-shot playback-native capture."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraPlaybackNativePreflightValidV1",
    "CameraPlaybackNativeSessionActiveV1",
    "CameraApplyScratchStageValidV1",
    "CameraApplySessionActiveV1",
    "DroneCameraRef",
    "DroneCamera",
}
WRITES = {
    "CameraPlaybackNativeBaselineActorTransformV1",
    "CameraPlaybackNativeBaselineComponentRelativeTransformV1",
    "CameraPlaybackNativeAppliedFrameCountV1",
    "CameraPlaybackNativeFailureCodeV1",
    "CameraPlaybackNativeSessionActiveV1",
}
FORBIDDEN = (
    "CameraPlaybackNativeInput",
    "CameraPlaybackNativeStageValidV1",
    "CameraPlaybackNativeResultValidV1",
    "CameraPlaybackResult",
    "CameraApplyBaseline",
    "CameraApplyCurrent",
    "CameraApplyInput",
    "CameraApplyAppliedFrameCountV1",
    "CameraChannel",
    "CinematicPose",
    "CarrierFrame",
    "CameraTransform",
    "K2_SetActor",
    "SetRelative",
    "SetWorld",
    "Flypath",
    "Repository",
    "Server",
    "HUD",
    "UI",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_playback_native_capture_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def one(nodes, *, cls=None, name=None):
    matches = [
        node for node in nodes.values()
        if (cls is None or cls in node.node_class) and (name is None or member(node) == name)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one cls={cls} member={name}; found {len(matches)}")
    return matches[0]


def simulate(prior: dict, *, preflight: bool, engine_capture_succeeded: bool, actor_transform, component_transform) -> dict:
    if not preflight or prior["active"]:
        return dict(prior)
    result = dict(prior)
    result["failure"] = "native_capture_failed"
    if not engine_capture_succeeded:
        return result
    result.update(
        baseline_actor=actor_transform,
        baseline_component=component_transform,
        count=0,
        failure="",
        active=True,
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
    contracts.require(len(nodes) == (19 if args.paste else 20), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    preflight_guard = nodes["K2Node_IfThenElse_0"]
    if args.paste:
        contracts.require(not preflight_guard.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", preflight_guard, "execute", "entry reaches preflight guard")

    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]
    setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({member(node) for node in getters} == READS, "exact capture reads")
    setter_names = [member(node) for node in setters]
    contracts.require(set(setter_names) == WRITES, "exact capture writes")
    contracts.require(setter_names.count("CameraPlaybackNativeFailureCodeV1") == 2, "capture diagnostic stages then clears")
    contracts.require(setter_names[-1] == "CameraPlaybackNativeSessionActiveV1", "session authority publishes last")

    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "capture cannot mutate pose, engine, or protected ownership")
    contracts.require(text.count('MemberName="CaptureCameraEngineStateV1"') == 1, "exact accepted engine capture call")
    contracts.require(text.count('MemberName="GetTransform"') == 1, "one verbatim actor transform getter")
    contracts.require(text.count('MemberName="GetRelativeTransform"') == 1, "one verbatim component-relative transform getter")
    contracts.require("MakeTransform" not in text and "BreakTransform" not in text, "capture never reconstructs transforms")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 3, "preflight, active, and engine guards")
    for name in ("CameraPlaybackNativeBaselineActorTransformV1", "CameraPlaybackNativeBaselineComponentRelativeTransformV1"):
        setter = one(nodes, cls="K2Node_VariableSet", name=name)
        contracts.require("/Script/CoreUObject.Transform" in setter.pins[name].body, f"{name} exact native Transform")
    actor_get = one(nodes, cls="K2Node_CallFunction", name="GetTransform")
    component_get = one(nodes, cls="K2Node_CallFunction", name="GetRelativeTransform")
    contracts.require("bIsReference=True" in actor_get.pins["ReturnValue"].body and "bIsConst=True" in actor_get.pins["ReturnValue"].body, "actor Transform returned verbatim const reference")
    contracts.require("bIsReference=False" in component_get.pins["ReturnValue"].body and "bIsConst=False" in component_get.pins["ReturnValue"].body, "component relative Transform uses Unreal's canonical by-value return")
    contracts.require("/Script/Engine.SceneComponent" in component_get.text, "relative getter owned by SceneComponent")

    by_member = {member(node): node for node in getters}
    engine_call = one(nodes, cls="K2Node_CallFunction", name="CaptureCameraEngineStateV1")
    branches = sorted((node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class), key=lambda node: node.name)
    contracts.require_link(by_member["DroneCameraRef"], "DroneCameraRef", actor_get, "self", "actor owns actor transform")
    contracts.require_link(by_member["DroneCameraRef"], "DroneCameraRef", by_member["DroneCamera"], "self", "actor owns component")
    contracts.require_link(by_member["DroneCamera"], "DroneCamera", component_get, "self", "component owns relative transform")
    contracts.require_link(branches[0], "then", branches[1], "execute", "preflight gates active check")
    contracts.require_link(branches[1], "else", setters[0], "execute", "inactive session stages capture")
    contracts.require_link(setters[0], "then", engine_call, "execute", "capture diagnostic precedes engine capture")
    contracts.require_link(engine_call, "then", branches[2], "execute", "engine capture precedes native baselines")
    contracts.require_link(branches[2], "then", setters[1], "execute", "engine success gates actor baseline")
    for left, right in zip(setters[1:], setters[2:]):
        contracts.require_link(left, "then", right, "execute", "ordered atomic native capture")

    rng = random.Random(0xEDD823)
    for index in range(80):
        actor_transform = {
            "translation": tuple(rng.uniform(-10000.0, 10000.0) for _ in range(3)),
            "rotation": tuple(rng.uniform(-1.0, 1.0) for _ in range(4)),
            "scale": tuple(rng.uniform(0.1, 5.0) for _ in range(3)),
            "opaque": ("actor", index),
        }
        component_transform = {
            "translation": tuple(rng.uniform(-100.0, 100.0) for _ in range(3)),
            "rotation": tuple(rng.uniform(-1.0, 1.0) for _ in range(4)),
            "scale": tuple(rng.uniform(0.1, 5.0) for _ in range(3)),
            "opaque": ("component", index),
        }
        prior = {
            "baseline_actor": object(), "baseline_component": object(),
            "count": 91, "failure": "old", "active": False, "sentinel": object(),
        }
        result = simulate(
            prior, preflight=True, engine_capture_succeeded=True,
            actor_transform=actor_transform, component_transform=component_transform,
        )
        contracts.require(result["active"] and result["count"] == 0 and result["failure"] == "", f"capture {index}")
        contracts.require(result["baseline_actor"] is actor_transform, "actor Transform captured verbatim")
        contracts.require(result["baseline_component"] is component_transform, "component Transform captured verbatim")
        contracts.require(result["sentinel"] is prior["sentinel"], "unowned state identity")
        repeated = simulate(
            result, preflight=True, engine_capture_succeeded=True,
            actor_transform=object(), component_transform=object(),
        )
        contracts.require(repeated == result, "active session baseline cannot be replaced")

    prior_actor, prior_component = object(), object()
    prior = {"baseline_actor": prior_actor, "baseline_component": prior_component, "count": 7, "failure": "prior", "active": False}
    rejected = simulate(prior, preflight=False, engine_capture_succeeded=True, actor_transform=object(), component_transform=object())
    contracts.require(rejected == prior, "preflight failure is a complete no-op")
    failed = simulate(prior, preflight=True, engine_capture_succeeded=False, actor_transform=object(), component_transform=object())
    contracts.require(failed["baseline_actor"] is prior_actor and failed["baseline_component"] is prior_component, "engine failure preserves native baselines")
    contracts.require(not failed["active"] and failed["count"] == 7 and failed["failure"] == "native_capture_failed", "engine failure remains nonauthoritative")
    print(
        f"Camera playback native capture contracts passed "
        f"({'paste' if args.paste else 'full'}): 80 verbatim snapshots, repeat/failure preservation"
    )


if __name__ == "__main__":
    main()
