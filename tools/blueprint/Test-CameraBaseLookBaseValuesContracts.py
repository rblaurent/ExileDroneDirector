"""Exact graph and executable contracts for named camera-look base values."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


PRESETS = (
    ("raw", (35.0, 2.8, 1000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    ("clean_cinematic", (50.0, 2.8, 1000.0, 1.0, 0.0, 0.10, 0.10, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0)),
    ("epic_landscape", (28.0, 8.0, 100000.0, 1.0, 0.25, 0.15, 0.05, 0.0, 0.0, 0.10, 0.0, 0.0, 0.0)),
    ("dreamy_shallow_focus", (85.0, 1.4, 500.0, 1.0, 0.50, 0.45, 0.20, 0.0, 0.0, 0.10, 0.05, 0.0, 0.0)),
    ("dark_sorcery", (50.0, 2.0, 800.0, 1.0, -1.0, 0.35, 0.55, 0.0, 0.0, 0.10, 0.15, 0.0, 0.0)),
    ("high_speed_fpv", (18.0, 5.6, 100000.0, 1.0, -0.20, 0.0, 0.10, 0.0, 0.0, 0.65, 0.10, 0.0, 0.0)),
    ("vintage_lens", (50.0, 2.0, 700.0, 1.0, 0.10, 0.25, 0.45, 0.0, 0.0, 0.25, 0.30, 0.0, 0.0)),
    ("documentary", (35.0, 4.0, 2000.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0)),
)
FORBIDDEN = ("CameraLookInputAuthored", "CameraLookCandidateValuesV1", "CameraLookCandidateOverrideMaskV1", "CameraLookResult", "CameraChannel", "CameraApply", "Airframe", "Gimbal", "Document", "Playback", "Comfort", "CameraTransform")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_look_base_contract", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def default(node, pin_name: str) -> float:
    match = re.search(rf'PinName="{re.escape(pin_name)}"[^\n]*DefaultValue="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"missing {pin_name} default on {node.name}")
    return float(match.group(1))


def next_node(nodes, node, pin_name: str):
    links = node.pins[pin_name].links
    if len(links) != 1:
        raise RuntimeError(f"{node.name}.{pin_name} expected one link, found {len(links)}")
    return nodes[links[0][0]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (135 if args.paste else 136), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(text.count('MemberName="Array_Add"') == 104, "eight exact thirteen-value append chains")
    contracts.require(text.count('MemberName="Array_Clear"') == 1, "candidate base rebuilt from empty")
    contracts.require(not any(value in text for value in FORBIDDEN), "no authored overrides, effective candidates, results, camera-channel, engine, motion, document, playback, comfort, or legacy state")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == {"CameraLookCandidateBaseValuesV1", "CameraLookValidationValidV1", "CameraLookInputPresetIdV1"}, "exact base reads")
    contracts.require(setters == {"CameraLookCandidateValidV1", "CameraLookScratchValidV1"}, "exact base writes")
    branches = [node for node in nodes.values() if "K2Node_IfThenElse" in node.node_class]
    contracts.require(len(branches) == 9, "one validation guard and eight preset branches")
    string_calls = [node for node in nodes.values() if member(node) == "EqualEqual_StrStr"]
    contracts.require(len(string_calls) == 8, "eight exact preset comparisons")
    contracts.require(all("KismetStringLibrary" in node.text for node in string_calls), "reconstructable preset comparisons")

    preset_by_default = {}
    for node in string_calls:
        match = re.search(r'PinName="B"[^\n]*DefaultValue="([^"]+)"', node.text)
        contracts.require(match is not None, "preset comparison default")
        condition_links = node.pins["ReturnValue"].links
        contracts.require(len(condition_links) == 1, "preset comparison has one branch")
        preset_by_default[match.group(1)] = nodes[condition_links[0][0]]
    contracts.require(tuple(preset_by_default) == tuple(preset for preset, _ in PRESETS), "preset branch order")
    for preset, expected in PRESETS:
        current = next_node(nodes, preset_by_default[preset], "then")
        actual = []
        for index in range(13):
            contracts.require(member(current) == "Array_Add", f"{preset} append {index}")
            actual.append(default(current, "NewItem"))
            current = next_node(nodes, current, "then")
        contracts.require(member(current) == "CameraLookScratchValidV1" and 'DefaultValue="true"' in current.text, f"{preset} publishes private stage last")
        contracts.require(tuple(actual) == expected, f"{preset} explicit values")
    for (preset, _), (next_preset, _) in zip(PRESETS, PRESETS[1:]):
        contracts.require_link(preset_by_default[preset], "else", preset_by_default[next_preset], "execute", f"{preset} to {next_preset}")

    poison = [999.0]
    for preset, expected in PRESETS:
        output = list(expected)
        contracts.require(output == list(expected) and output is not poison, f"{preset} interpreter rebuild")
    contracts.require(poison == [999.0], "prior candidate storage not aliased")
    print(f"Camera base-look values contracts passed ({'paste' if args.paste else 'full'}): 8 presets, 104 explicit values")


if __name__ == "__main__":
    main()
