"""Structural and executable contracts for bounded Cue crossing collection."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_crossing_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def collect(*, plan_valid=True, playback_started=True, scrubbing=False,
            previous=0.0, current=10.0, direction=1, times=(), policies=()):
    crossed = []
    stage = False
    code = "event_crossing_invalid"
    if not plan_valid:
        return stage, crossed, code
    if scrubbing:
        return True, crossed, ""
    query_valid = playback_started is True and direction in (-1, 1)
    query_valid = query_valid and (
        (direction == 1 and current >= previous)
        or (direction == -1 and previous >= current)
    )
    if not query_valid:
        return stage, crossed, code
    stage = True
    for index, cue_time in enumerate(times):
        if not math.isfinite(cue_time):
            stage = False
            code = "event_cue_time_invalid"
            continue
        policy = policies[index]
        forward = (
            direction == 1 and previous < cue_time <= current
            and policy in ("forward", "both")
        )
        reverse = (
            direction == -1 and current <= cue_time < previous
            and policy in ("reverse", "reverse_undo", "both")
        )
        if stage and (forward or reverse):
            if len(crossed) >= 32:
                stage = False
                code = "event_crossing_limit"
            else:
                crossed.append(index)
    if stage:
        code = ""
    return stage, crossed, code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (66 if args.paste else 67), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    clear = next(node for node in nodes.values() if member(node) == "Array_Clear")
    if args.paste:
        contracts.require(not clear.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", clear, "execute", "entry clears prior crossings")
    contracts.require(text.count('MemberName="Array_Clear"') == 1, "one exact scratch clear")
    contracts.require(text.count('MemberName="Array_Add"') == 1, "one bounded append")
    contracts.require(text.count('MemberName="Array_Length"') == 1, "one capacity read")
    contracts.require(text.count("StandardMacros:ForEachLoop") == 1, "one canonical-time loop")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 1, "one direction-policy lookup")
    contracts.require(text.count('MemberName="EqualEqual_StrStr"') == 4, "closed direction-policy comparisons")
    contracts.require(text.count("KismetStringLibrary") == 4, "string comparisons use reflected owner")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 7, "exact control guards")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(writes.count("EventCrossingCollectionValidV1") == 5, "fail-close, scrub/live success, and two bounded failures")
    contracts.require(writes.count("EventDispatchCodeV1") == 5, "generic, scrub, time, limit, and final diagnostics")
    contracts.require(len(writes) == 10, "collector owns only stage and diagnostic")
    for required in (
        "EventPlanValidationValidV1", "EventScrubbingV1", "EventPlaybackStartedV1",
        "EventDirectionV1", "EventPreviousTimeV1", "EventCurrentTimeV1",
        "EventCueTimesV1", "EventCueDirectionPoliciesV1", "EventCrossedIndicesV1",
    ):
        contracts.require(required in text, f"required crossing input {required}")
    for forbidden in (
        "EventLedgerIdsV1", "EventLedgerLoopsV1", "EventLedgerDirectionsV1",
        "EventResolvedBindingIdsV1", "EventGrantedPermissionsV1",
        "EventDispatchIndexV1", "EventDispatchAuthorizedV1", "EventDispatchResultValidV1",
        "CameraTransform", "DroneCamera", "Repository", "K2_SetActor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"forbidden ownership {forbidden}")

    rng = random.Random(0xEDD910)
    for case in range(80):
        count = rng.randint(1, 32)
        times = tuple(sorted(rng.uniform(0.0, 20.0) for _ in range(count)))
        policies = tuple(rng.choice(("forward", "reverse", "both", "reverse_undo")) for _ in times)
        low, high = sorted((rng.uniform(0.0, 20.0), rng.uniform(0.0, 20.0)))
        for direction, previous, current in ((1, low, high), (-1, high, low)):
            stage, indices, code = collect(
                previous=previous, current=current, direction=direction,
                times=times, policies=policies,
            )
            expected = [
                index for index, (cue_time, policy) in enumerate(zip(times, policies))
                if (
                    direction == 1 and previous < cue_time <= current and policy in ("forward", "both")
                ) or (
                    direction == -1 and current <= cue_time < previous and policy in ("reverse", "reverse_undo", "both")
                )
            ]
            contracts.require(stage and indices == expected and code == "", f"seeded crossing {case}/{direction}")
    contracts.require(collect(scrubbing=True, times=(1.0,), policies=("both",)) == (True, [], ""), "scrub zero-dispatch")
    contracts.require(not collect(plan_valid=False)[0], "invalid plan fail closed")
    contracts.require(not collect(playback_started=False)[0], "inactive playback fail closed")
    contracts.require(not collect(previous=2.0, current=1.0, direction=1)[0], "forward order fail closed")
    contracts.require(not collect(previous=1.0, current=2.0, direction=-1)[0], "reverse order fail closed")
    time_failure = collect(times=(1.0, math.nan), policies=("both", "both"))
    contracts.require(time_failure == (False, [0], "event_cue_time_invalid"), "nonfinite time invalidates bounded scratch")
    limit_failure = collect(times=tuple(float(index + 1) for index in range(40)), policies=("both",) * 40, current=100.0)
    contracts.require(limit_failure == (False, list(range(32)), "event_crossing_limit"), "crossing cap is exact")
    print(
        f"Bounded event crossing collection contracts passed "
        f"({'paste' if args.paste else 'full'}): 160 ordered queries plus failures"
    )


if __name__ == "__main__":
    main()
