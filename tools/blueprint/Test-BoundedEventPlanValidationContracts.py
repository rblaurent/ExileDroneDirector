"""Structural and executable contracts for bounded event-plan validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


CUE_ARRAYS = (
    "Ids", "Times", "AdapterIds", "AdapterVersions", "OperationIds", "Scopes",
    "Payloads", "DirectionPolicies", "RepeatPolicies", "FailurePolicies",
    "BindingIds", "BindingRegions", "BindingAdapterIds", "BindingAdapterVersions",
    "BindingEnabled", "BindingReauthorized",
)


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_validation_contract_base", path)
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
    count = rng.randint(1, 20)
    values = {
        "PlanValid": True,
        "ImmutableRevision": rng.randint(1, 100),
        "PlaybackStarted": True,
        "Scrubbing": False,
        "PreviousTime": rng.uniform(0.0, 10.0),
        "CurrentTime": rng.uniform(10.0, 20.0),
        "Loop": rng.randint(0, 20),
        "Direction": 1,
        "ResolvedIds": [f"binding-{index}" for index in range(rng.randint(0, 8))],
        "Permissions": [f"permission-{index}" for index in range(rng.randint(0, 8))],
        "RateBudget": rng.randint(0, 32),
    }
    values["RequestedRevision"] = values["ImmutableRevision"]
    values["ResolvedDistances"] = [float(index) for index in range(len(values["ResolvedIds"]))]
    for name in CUE_ARRAYS:
        values[name] = [f"{name}-{index}" for index in range(count)]
    values["Times"] = [float(index) for index in range(count)]
    values["AdapterVersions"] = [1] * count
    values["BindingAdapterVersions"] = [1] * count
    values["BindingEnabled"] = [True] * count
    values["BindingReauthorized"] = [True] * count
    return values


def validate(value):
    count = len(value["Ids"])
    valid = value["PlanValid"] is True and 1 <= count <= 256
    valid = valid and all(len(value[name]) == count for name in CUE_ARRAYS)
    valid = valid and value["ImmutableRevision"] > 0
    valid = valid and value["RequestedRevision"] == value["ImmutableRevision"]
    valid = valid and (value["PlaybackStarted"] is True or value["Scrubbing"] is True)
    valid = valid and math.isfinite(value["PreviousTime"]) and math.isfinite(value["CurrentTime"])
    valid = valid and value["Loop"] >= 0 and value["Direction"] in (-1, 1)
    valid = valid and len(value["ResolvedIds"]) == len(value["ResolvedDistances"])
    valid = valid and len(value["ResolvedIds"]) <= 256
    valid = valid and len(value["Permissions"]) <= 64
    valid = valid and value["RateBudget"] >= 0
    return valid, "" if valid else "event_plan_invalid"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (116 if args.paste else 117), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    contracts.require(member(root) == "EventPlanValidationValidV1", "validation execution root")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry to fail-closed validation")
    for name in CUE_ARRAYS:
        contracts.require(f'MemberName="EventCue{name}V1"' in text, f"parallel Cue array {name}")
    contracts.require(text.count('MemberName="Array_Length"') == 19, "sixteen Cue plus three authorization lengths")
    contracts.require("StandardMacros:ForEachLoop" not in text, "structural validator has no element loop")
    contracts.require(
        sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 1,
        "one final authority branch",
    )
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("EventPlanValidationValidV1") == 2, "fail-closed then success stage")
    contracts.require(writes.count("EventDispatchCodeV1") == 2, "failure then success diagnostic")
    contracts.require(len(writes) == 4, "validator owns exactly stage and diagnostic")
    for forbidden in (
        "EventCrossedIndicesV1", "EventLedgerIdsV1", "EventDispatchIndexV1",
        "EventDispatchAuthorizedV1", "EventDispatchResultValidV1",
        "CameraTransform", "CameraPlaybackResult", "DroneCamera", "Repository",
        "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden ownership {forbidden}")

    for seed in range(80):
        valid, code = validate(make(0xEDD900 + seed))
        contracts.require(valid and code == "", f"seeded valid {seed}")
    mutations = {
        "authority": lambda x: x.update(PlanValid=False),
        "empty": lambda x: x.update(Ids=[]),
        "oversize": lambda x: [x.__setitem__(name, [x[name][0]] * 257) for name in CUE_ARRAYS],
        "shape": lambda x: x["Payloads"].pop(),
        "immutable": lambda x: x.update(ImmutableRevision=0),
        "revision": lambda x: x.update(RequestedRevision=x["ImmutableRevision"] + 1),
        "inactive": lambda x: x.update(PlaybackStarted=False, Scrubbing=False),
        "previous_nan": lambda x: x.update(PreviousTime=float("nan")),
        "current_inf": lambda x: x.update(CurrentTime=float("inf")),
        "loop": lambda x: x.update(Loop=-1),
        "direction": lambda x: x.update(Direction=0),
        "resolved_shape": lambda x: x["ResolvedDistances"].append(1.0),
        "resolved_limit": lambda x: x.update(ResolvedIds=["x"] * 257, ResolvedDistances=[0.0] * 257),
        "permission_limit": lambda x: x.update(Permissions=["x"] * 65),
        "rate": lambda x: x.update(RateBudget=-1),
    }
    for label, mutate in mutations.items():
        value = make(0xEDD999)
        mutate(value)
        valid, code = validate(value)
        contracts.require(not valid and code == "event_plan_invalid", label)
    print(
        f"Bounded event plan validation contracts passed "
        f"({'paste' if args.paste else 'full'}): 80 plans and {len(mutations)} failures"
    )


if __name__ == "__main__":
    main()
