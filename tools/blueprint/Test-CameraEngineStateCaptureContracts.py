"""Structural and executable contracts for one-shot native camera capture."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_capture_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return match.group(1) if match else None


def one(nodes, *, cls: str | None = None, name: str | None = None):
    matches = [node for node in nodes.values() if (cls is None or cls in node.node_class) and (name is None or member(node) == name)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one cls={cls} member={name}; found {len(matches)}")
    return matches[0]


def simulate(prior: dict, camera: dict | None) -> dict:
    if camera is None:
        result = dict(prior)
        result["stage_valid"] = False
        result["failure"] = "camera_invalid"
        return result
    if prior["active"]:
        return dict(prior)
    values = (
        camera["filmback"]["SensorWidth"], camera["filmback"]["SensorHeight"],
        camera["focal"], camera["aperture"], camera["focus"]["ManualFocusDistance"],
        1.0, camera["post"]["AutoExposureBias"], camera["post"]["BloomIntensity"],
        camera["post"]["VignetteIntensity"], 0.0, 0.0,
        camera["post"]["MotionBlurAmount"], camera["post"]["SceneFringeIntensity"], 0.0, 0.0,
    )
    result = dict(prior)
    result.update(
        baseline_id="engine_native_baseline",
        baseline_values=values,
        baseline_filmback=dict(camera["filmback"]),
        baseline_focus=dict(camera["focus"]),
        baseline_post=dict(camera["post"]),
        current_id="engine_native_baseline",
        current_values=values,
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
    contracts.require(len(nodes) == (40 if args.paste else 41), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    camera_guard = nodes["K2Node_IfThenElse_0"]
    if args.paste:
        contracts.require(not camera_guard.pins["execute"].links, "paste root unwired")
    else:
        contracts.require_link(entries[0], "then", camera_guard, "execute", "entry reaches camera guard")

    text = args.graph.read_text(encoding="utf-8")
    component = one(nodes, cls="K2Node_VariableGet", name="DroneCamera")
    contracts.require("BP_EDD_DroneCamera.BP_EDD_DroneCamera_C" in component.text, "component getter has explicit actor owner")
    contracts.require("bSelfContext=True" not in component.text, "component getter cannot alias director self")
    contracts.require(text.count('MemberName="Array_Add"') == 15, "exact fifteen canonical baseline appends")
    contracts.require(text.count('MemberName="Array_Clear"') == 1, "baseline clears exactly once")
    contracts.require(text.count('MemberName="IsValid"') == 1, "one camera validity preflight")
    contracts.require(len([node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]) == 2, "camera and active-session guards")
    contracts.require(not any("K2Node_VariableSet" in node.node_class and member(node) in {"Filmback", "FocusSettings", "PostProcessSettings", "CurrentFocalLength", "CurrentAperture"} for node in nodes.values()), "capture performs no engine writes")
    for engine_name in ("Filmback", "FocusSettings", "PostProcessSettings", "CurrentFocalLength", "CurrentAperture"):
        contracts.require(len([node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == engine_name]) == 1, f"one {engine_name} read")
    for baseline_name, struct_id in (
        ("CameraApplyBaselineFilmbackSettingsV1", "/Script/CinematicCamera.CameraFilmbackSettings"),
        ("CameraApplyBaselineFocusSettingsV1", "/Script/CinematicCamera.CameraFocusSettings"),
        ("CameraApplyBaselinePostProcessSettingsV1", "/Script/Engine.PostProcessSettings"),
    ):
        setter = one(nodes, cls="K2Node_VariableSet", name=baseline_name)
        contracts.require(struct_id in setter.pins[baseline_name].body, f"{baseline_name} native type")
    forbidden = ("CameraChannelInput", "CameraChannelCandidate", "CameraChannelCompiled", "AirframeSource", "AirframeDesired")
    contracts.require(not any(marker in text for marker in forbidden), "capture cannot mutate upstream authored/compiled banks")

    rng = random.Random(0xEDD713)
    for index in range(40):
        camera = {
            "filmback": {"SensorWidth": 20.0 + rng.random() * 30.0, "SensorHeight": 10.0 + rng.random() * 20.0, "Opaque": index},
            "focus": {"ManualFocusDistance": 10.0 + rng.random() * 10000.0, "TrackingActor": f"actor_{index}"},
            "post": {"AutoExposureBias": rng.uniform(-4.0, 4.0), "BloomIntensity": rng.random(), "VignetteIntensity": rng.random(), "MotionBlurAmount": rng.random(), "SceneFringeIntensity": rng.random(), "bOverride_BloomIntensity": bool(index % 2), "OpaqueCurve": (index, index + 1)},
            "focal": 10.0 + rng.random() * 200.0,
            "aperture": 0.5 + rng.random() * 20.0,
        }
        prior = {"active": False, "stage_valid": True, "failure": "", "baseline_values": (999.0,), "sentinel": object()}
        result = simulate(prior, camera)
        contracts.require(result["active"] and len(result["baseline_values"]) == 15, f"capture {index}")
        contracts.require(result["baseline_filmback"] == camera["filmback"], "whole filmback snapshot")
        contracts.require(result["baseline_focus"] == camera["focus"], "whole focus snapshot")
        contracts.require(result["baseline_post"] == camera["post"], "whole post-process snapshot")
        contracts.require(result["sentinel"] is prior["sentinel"], "unowned state identity")
        active = dict(result)
        replacement = simulate(active, {**camera, "focal": 999.0})
        contracts.require(replacement == active, "repeated capture cannot replace active baseline")
    failed = simulate({"active": False, "stage_valid": True, "failure": "", "baseline_values": (1.0,)}, None)
    contracts.require(not failed["stage_valid"] and failed["baseline_values"] == (1.0,), "invalid camera preserves baseline and fails stage")
    print(f"Camera engine capture contracts passed ({'paste' if args.paste else 'full'}): 40 exact native snapshots")


if __name__ == "__main__":
    main()
