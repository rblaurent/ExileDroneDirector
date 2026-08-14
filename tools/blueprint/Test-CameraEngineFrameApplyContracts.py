"""Structural and executable contracts for transactional native camera apply."""

from __future__ import annotations

import argparse
import importlib.util
import random
import re
import sys
from pathlib import Path


SUPPORTED = {0, 1, 2, 3, 4, 6, 7, 8, 11, 12}
UNSUPPORTED_NEUTRAL = {5: 1.0, 9: 0.0, 10: 0.0, 13: 0.0, 14: 0.0}
POST_FIELDS = {6: "AutoExposureBias", 7: "BloomIntensity", 8: "VignetteIntensity", 11: "MotionBlurAmount", 12: "SceneFringeIntensity"}


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_apply_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return match.group(1) if match else None


def simulate(session: dict, values: tuple[float, ...], *, camera_valid=True, stage_valid=True) -> tuple[dict, dict]:
    engine = session["engine"]
    if not camera_valid or not stage_valid or not session["active"] or any(values[index] != neutral for index, neutral in UNSUPPORTED_NEUTRAL.items()):
        failed = dict(session)
        failed.update(result=False, failure="application_preflight_failed")
        return failed, engine
    next_engine = {
        **engine,
        "filmback": {**engine["filmback"], "SensorWidth": values[0], "SensorHeight": values[1]},
        "focal": values[2],
        "aperture": values[3],
        "focus": {**engine["focus"], "ManualFocusDistance": values[4]},
        "post": dict(engine["post"]),
    }
    for index, field in POST_FIELDS.items():
        next_engine["post"][field] = values[index]
        next_engine["post"][f"bOverride_{field}"] = True
    applied = dict(session)
    applied.update(engine=next_engine, current_values=values, count=session["count"] + 1, result=True, failure="")
    return applied, next_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (59 if args.paste else 60), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    guard = nodes["K2Node_IfThenElse_0"]
    if args.paste:
        contracts.require(not guard.pins["execute"].links, "paste root unwired")
    else:
        contracts.require_link(entries[0], "then", guard, "execute", "entry reaches complete preflight")

    text = args.graph.read_text(encoding="utf-8")
    components = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class and member(node) == "DroneCamera"]
    contracts.require(len(components) == 1 and "BP_EDD_DroneCamera.BP_EDD_DroneCamera_C" in components[0].text, "component getter has explicit actor owner")
    contracts.require("bSelfContext=True" not in components[0].text, "component getter cannot alias director self")
    engine_members = ("Filmback", "FocusSettings", "PostProcessSettings", "CurrentFocalLength", "CurrentAperture")
    for name in engine_members:
        setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == name]
        contracts.require(len(setters) == 1, f"one {name} write")
        contracts.require(contracts.linked(guard, "then", setters[0], "execute") or setters[0].pins["execute"].links, f"{name} write belongs to guarded chain")
    contracts.require(len([node for node in nodes.values() if "K2Node_SetFieldsInStruct" in node.node_class]) == 3, "exact three owned struct mutations")
    contracts.require(len([node for node in nodes.values() if "K2Node_GetArrayItem" in node.node_class]) == 15, "one canonical read per target")
    contracts.require(text.count('MemberName="EqualEqual_DoubleDouble"') == 5, "five unavailable-neutral guards")
    for index, neutral in UNSUPPORTED_NEUTRAL.items():
        contracts.require(f'DefaultValue="{index}"' in text, f"unavailable index {index}")
        contracts.require(f'DefaultValue="{neutral}"' in text, f"unavailable neutral {index}")
    contracts.require("CameraApplyBaseline" not in text, "apply never mutates or reads restoration baseline")
    contracts.require("CameraChannelInput" not in text and "CameraChannelCompiled" not in text, "apply owns no authored/compiled storage")
    post_members = [node for node in nodes.values() if "K2Node_SetFieldsInStruct" in node.node_class and "/Script/Engine.PostProcessSettings" in node.text]
    contracts.require(len(post_members) == 1, "one post-process Set Members")
    contracts.require(set(post_members[0].pins) == {"execute", "then", "StructRef", "StructOut", *POST_FIELDS.values()}, "exact supported post-process fields")

    rng = random.Random(0xEDD714)
    for index in range(40):
        values = [rng.uniform(0.1, 10.0) for _ in range(15)]
        values[0], values[1], values[2], values[3], values[4] = 36.0, 24.0, 35.0 + index, 2.8, 1000.0 + index
        for target, neutral in UNSUPPORTED_NEUTRAL.items():
            values[target] = neutral
        engine = {
            "filmback": {"SensorWidth": 50.0, "SensorHeight": 20.0, "OpaqueOffset": index},
            "focal": 50.0, "aperture": 4.0,
            "focus": {"ManualFocusDistance": 500.0, "TrackingActor": f"actor_{index}"},
            "post": {"OpaqueToneCurve": (index, index + 1), "bOverride_BloomIntensity": False},
        }
        session = {"active": True, "engine": engine, "current_values": (), "count": index, "result": False, "failure": ""}
        applied, mutated = simulate(session, tuple(values))
        contracts.require(applied["result"] and applied["count"] == index + 1, f"apply {index}")
        contracts.require(mutated["filmback"]["OpaqueOffset"] == index, "filmback opaque preservation")
        contracts.require(mutated["focus"]["TrackingActor"] == f"actor_{index}", "focus opaque preservation")
        contracts.require(mutated["post"]["OpaqueToneCurve"] == (index, index + 1), "post-process opaque preservation")
        poisoned = list(values); poisoned[13] = 0.25
        failed, failed_engine = simulate(session, tuple(poisoned))
        contracts.require(not failed["result"] and failed_engine is engine and failed["count"] == index, "unavailable request is zero-write")
    print(f"Camera engine apply contracts passed ({'paste' if args.paste else 'full'}): 40 transactional frames")


if __name__ == "__main__":
    main()
