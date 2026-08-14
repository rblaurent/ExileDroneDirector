"""Structural and executable contracts for application input validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


READS = {
    "CameraApplyInputValidV1",
    "CameraApplyCapabilityEngineVersionV1",
    "CameraApplyCapabilityManifestIdV1",
    "CameraApplyInputFilmbackPresetIdV1",
    "CameraApplyCapabilityAvailableV1",
    "CameraApplyInputTargetValuesV1",
}
WRITES = {"CameraApplyScratchStageValidV1", "CameraApplyFailureCodeV1"}
FORBIDDEN = (
    "CameraApplyBaseline",
    "CameraApplyCurrent",
    "CameraApplySessionActiveV1",
    "CameraApplyAppliedFrameCountV1",
    "CameraChannelInput",
    "CameraChannelCandidate",
    "CameraChannelCompiled",
    "DroneCameraRef",
    "PostProcessSettings",
)
BOUNDS = (
    (0.0, None, False),
    (0.0, None, False),
    (1.0, 1000.0, True),
    (0.1, 64.0, True),
    (1.0, 1.0e9, True),
    (0.0, 1.0, True),
    (-20.0, 20.0, True),
    *((0.0, 1.0, True) for _ in range(8)),
)
ENGINE_VERSION = "5.6.1-370197+++exiles+release"
MANIFEST_ID = "0425CCF862121F06C64732519AF40703C2AC73104B3FA10A3E065F914E1FB26E"


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_apply_validation_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def valid(state: dict) -> bool:
    if state.get("input_valid") is not True:
        return False
    if state.get("engine_version") != ENGINE_VERSION:
        return False
    if state.get("manifest_id") != MANIFEST_ID:
        return False
    if not isinstance(state.get("preset_id"), str) or not state["preset_id"]:
        return False
    capabilities = state.get("capabilities")
    values = state.get("values")
    if not isinstance(capabilities, tuple) or len(capabilities) != 15 or any(not isinstance(item, bool) for item in capabilities):
        return False
    if not all(capabilities[:5]):
        return False
    if not isinstance(values, tuple) or len(values) != 15:
        return False
    for value, (minimum, maximum, inclusive) in zip(values, BOUNDS):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False
        if value < minimum or (not inclusive and value == minimum):
            return False
        if maximum is not None and value > maximum:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    expected = 170 if args.paste else 171
    contracts.require(len(nodes) == expected, f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to validation root")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(getters == READS, f"exact validation reads: {getters}")
    contracts.require(set(setters) == WRITES, f"exact validation writes: {setters}")
    contracts.require(setters.count("CameraApplyScratchStageValidV1") == 2, "stage invalidates then publishes")
    contracts.require(setters[-1] == "CameraApplyScratchStageValidV1", "stage validity publishes last")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in FORBIDDEN), "validation cannot touch engine/session/protected storage")
    contracts.require(
        sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 20,
        "five required capability plus fifteen value reads",
    )
    string_calls = [
        node for node in nodes.values()
        if 'MemberName="NotEqual_StrStr"' in node.text or 'MemberName="EqualEqual_StrStr"' in node.text
    ]
    contracts.require(len(string_calls) == 3, "exact three nonempty string comparisons")
    contracts.require(
        all("KismetStringLibrary" in node.text for node in string_calls),
        "string comparisons use string library",
    )
    contracts.require(ENGINE_VERSION in text, "exact probed engine version guard")
    contracts.require(MANIFEST_ID in text, "exact probed manifest identity guard")

    rng = random.Random(0xEDD712)
    valid_cases = []
    for index in range(80):
        values = []
        for minimum, maximum, inclusive in BOUNDS:
            if maximum is None:
                values.append(minimum + 1.0 + rng.random() * 100.0)
            else:
                values.append(minimum + rng.random() * (maximum - minimum))
        capabilities = tuple(True if item < 5 else bool(rng.getrandbits(1)) for item in range(15))
        case = {
            "input_valid": True,
            "engine_version": ENGINE_VERSION,
            "manifest_id": MANIFEST_ID,
            "preset_id": f"filmback_{index}",
            "capabilities": capabilities,
            "values": tuple(values),
        }
        contracts.require(valid(case), f"seeded valid {index}")
        valid_cases.append(case)

    base = valid_cases[0]
    failures = [
        {**base, "input_valid": False},
        {**base, "engine_version": "5.6.1-wrong-build"},
        {**base, "manifest_id": "F" * 64},
        {**base, "preset_id": ""},
        {**base, "capabilities": base["capabilities"][:-1]},
        {**base, "capabilities": (*base["capabilities"], True)},
        {**base, "values": base["values"][:-1]},
        {**base, "values": (*base["values"], 0.0)},
    ]
    for index in range(5):
        capabilities = list(base["capabilities"])
        capabilities[index] = False
        failures.append({**base, "capabilities": tuple(capabilities)})
    for index, (minimum, maximum, inclusive) in enumerate(BOUNDS):
        poisoned = list(base["values"])
        poisoned[index] = math.nan
        failures.append({**base, "values": tuple(poisoned)})
        poisoned = list(base["values"])
        poisoned[index] = minimum if not inclusive else minimum - 1.0
        failures.append({**base, "values": tuple(poisoned)})
        if maximum is not None:
            poisoned = list(base["values"])
            poisoned[index] = maximum + 1.0
            failures.append({**base, "values": tuple(poisoned)})
    for index, case in enumerate(failures):
        contracts.require(not valid(case), f"failure {index}")
    print(
        f"Camera engine application validation contracts passed "
        f"({'paste' if args.paste else 'full'}): 80 valid, {len(failures)} failures"
    )


if __name__ == "__main__":
    main()
