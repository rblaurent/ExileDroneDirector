"""Structural and executable contracts for exact native camera restoration."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_restore_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return match.group(1) if match else None


def simulate(session: dict, *, camera_valid=True, baseline_shape=True) -> dict:
    if not session["active"]:
        return dict(session)
    if not camera_valid or not baseline_shape:
        failed = dict(session)
        failed.update(result=False, failure="restore_preflight_failed")
        return failed
    restored = dict(session)
    restored.update(
        engine={
            **session["engine"],
            "filmback": session["baseline_filmback"],
            "focal": session["baseline_values"][2],
            "aperture": session["baseline_values"][3],
            "focus": session["baseline_focus"],
            "post": session["baseline_post"],
        },
        current_id=session["baseline_id"],
        current_values=session["baseline_values"],
        active=False,
        result=True,
        failure="",
    )
    return restored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (27 if args.paste else 28), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    active_guard = nodes["K2Node_IfThenElse_0"]
    if args.paste:
        contracts.require(not active_guard.pins["execute"].links, "paste root unwired")
    else:
        contracts.require_link(entries[0], "then", active_guard, "execute", "entry reaches active-session guard")
    contracts.require(not active_guard.pins["else"].links, "inactive repeated restore is a stable no-op")

    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len([node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]) == 2, "active and complete restore preflight")
    contracts.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 2, "only focal/aperture scalar baseline reads")
    contracts.require('DefaultValue="2"' in text and 'DefaultValue="3"' in text, "exact focal/aperture indices")
    contracts.require('MemberName="Array_Length"' in text and 'DefaultValue="15"' in text, "baseline cardinality preflight")
    for name in ("Filmback", "FocusSettings", "PostProcessSettings", "CurrentFocalLength", "CurrentAperture"):
        contracts.require(len([node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == name]) == 1, f"one exact {name} restoration write")
    contracts.require(not any("K2Node_SetFieldsInStruct" in node.node_class for node in nodes.values()), "restore writes whole structs without exposed-member reconstruction")
    for baseline_name, identity in (
        ("CameraApplyBaselineFilmbackSettingsV1", "/Script/CinematicCamera.CameraFilmbackSettings"),
        ("CameraApplyBaselineFocusSettingsV1", "/Script/CinematicCamera.CameraFocusSettings"),
        ("CameraApplyBaselinePostProcessSettingsV1", "/Script/Engine.PostProcessSettings"),
    ):
        getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == baseline_name]
        contracts.require(len(getters) == 1 and identity in getters[0].pins[baseline_name].body, f"exact {baseline_name}")
    contracts.require("CameraChannelInput" not in text and "CameraChannelCompiled" not in text, "restore owns no authored/compiled storage")

    rng = random.Random(0xEDD715)
    for index in range(40):
        baseline_values = tuple(rng.random() * 100.0 for _ in range(15))
        baseline_filmback = {"SensorWidth": 36.0, "SensorHeight": 24.0, "OpaqueOffset": index}
        baseline_focus = {"ManualFocusDistance": 1000.0, "TrackingActor": f"actor_{index}"}
        baseline_post = {"BloomIntensity": 0.25, "bOverride_BloomIntensity": bool(index % 2), "OpaqueCurve": (index, index + 1)}
        session = {
            "active": True, "engine": {"filmback": {}, "focus": {}, "post": {}, "focal": 1.0, "aperture": 1.0, "external": object()},
            "baseline_id": f"baseline_{index}", "baseline_values": baseline_values,
            "baseline_filmback": baseline_filmback, "baseline_focus": baseline_focus, "baseline_post": baseline_post,
            "current_id": "applied", "current_values": (), "result": False, "failure": "poison",
        }
        restored = simulate(session)
        contracts.require(restored["engine"]["filmback"] is baseline_filmback, "verbatim filmback restore")
        contracts.require(restored["engine"]["focus"] is baseline_focus, "verbatim focus restore")
        contracts.require(restored["engine"]["post"] is baseline_post, "verbatim post-process/override restore")
        contracts.require(restored["engine"]["external"] is session["engine"]["external"], "unowned engine state")
        contracts.require(simulate(restored) == restored, "idempotent repeated restore")
        failed = simulate(session, camera_valid=False)
        contracts.require(failed["engine"] is session["engine"] and failed["active"], "failed preflight is zero-write and retryable")
    print(f"Camera engine restore contracts passed ({'paste' if args.paste else 'full'}): 40 exact whole-struct restores")


if __name__ == "__main__":
    main()
