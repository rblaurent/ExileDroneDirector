"""Structural and executable contracts for State Clip plan-shape validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


ARRAYS = (
    "Ids", "StartTimes", "EndTimes", "DesiredStates", "EnterLeadSeconds",
    "ExitLeadSeconds", "Scopes", "RestorePolicies", "ConflictPolicies",
    "FailurePolicies", "TimeoutSeconds", "PreviewPolicies", "BindingIds",
    "BindingTypes", "BindingRegions", "BindingAdapterIds",
    "BindingAdapterVersions", "BindingEnabled", "BindingReauthorized",
)


def load(path):
    spec = importlib.util.spec_from_file_location("edd_state_clip_validation_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def make(seed):
    rng = random.Random(seed)
    count = rng.randint(0, 20)
    value = {"PlanValid": True, "Duration": rng.uniform(0.0, 30.0)}
    for name in ARRAYS:
        value[name] = [f"{name}-{index}" for index in range(count)]
    value["StartTimes"] = [float(index) for index in range(count)]
    value["EndTimes"] = [float(index + 1) for index in range(count)]
    value["EnterLeadSeconds"] = [0.0] * count
    value["ExitLeadSeconds"] = [0.0] * count
    value["TimeoutSeconds"] = [2.0] * count
    value["BindingAdapterVersions"] = [1] * count
    value["BindingEnabled"] = [True] * count
    value["BindingReauthorized"] = [True] * count
    return value


def validate(value):
    count = len(value["Ids"])
    valid = value["PlanValid"] is True and count <= 128
    valid = valid and all(len(value[name]) == count for name in ARRAYS)
    valid = valid and math.isfinite(value["Duration"]) and value["Duration"] >= 0.0
    return valid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (87 if args.paste else 88), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    contracts.require(member(root) == "StateClipValidationValidV1", "validation root")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "native entry to validation")
    for name in ARRAYS:
        contracts.require(f'MemberName="StateClip{name}V1"' in text, f"parallel array {name}")
    contracts.require(text.count('MemberName="Array_Length"') == 19, "nineteen array lengths")
    contracts.require("StandardMacros:ForEachLoop" not in text, "structural validation owns no row loop")
    contracts.require(
        sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 1,
        "one final authority branch",
    )
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes == ["StateClipValidationValidV1", "StateClipValidationValidV1"], "stage-only ownership")
    for forbidden in (
        "StateClipCandidateIdsV1", "StateClipResultIdsV1", "EventLedgerIdsV1",
        "EventDispatchAuthorizedV1", "CameraTransform", "DroneCamera",
        "Repository", "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden ownership {forbidden}")

    for seed in range(80):
        contracts.require(validate(make(0xEDDA00 + seed)), f"seeded valid {seed}")
    mutations = {
        "authority": lambda x: x.update(PlanValid=False),
        "oversize": lambda x: [x.__setitem__(name, [0] * 129) for name in ARRAYS],
        "duration_nan": lambda x: x.update(Duration=float("nan")),
        "duration_negative": lambda x: x.update(Duration=-1.0),
    }
    for name in ARRAYS[1:]:
        mutations[f"shape_{name}"] = lambda x, key=name: x[key].append("poison")
    for label, mutate in mutations.items():
        value = make(0xEDDA99)
        mutate(value)
        contracts.require(not validate(value), label)
    print(
        f"State Clip plan validation contracts passed ({'paste' if args.paste else 'full'}): "
        f"80 plans and {len(mutations)} failures"
    )


if __name__ == "__main__":
    main()
