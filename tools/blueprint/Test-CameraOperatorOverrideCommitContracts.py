"""Structural and executable contracts for atomic camera operator publication."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from dataclasses import asdict
from pathlib import Path


READS = {
    "CameraOperatorValidationValidV1", "CameraOperatorScratchValidV1", "CameraOperatorCandidateValidV1",
    "CameraOperatorCandidateModeV1", "CameraOperatorCandidateRecenterActiveV1",
    "CameraOperatorCandidateTranslationOffsetV1", "CameraOperatorCandidateTranslationVelocityV1",
    "CameraOperatorCandidateLookOffsetQuatV1", "CameraOperatorCandidateAngularVelocityV1",
    "CameraOperatorCandidatePositionV1", "CameraOperatorCandidateBodyQuatV1",
    "CameraOperatorCandidateGimbalQuatV1", "CameraOperatorCandidateOverrideActiveV1",
    "CameraOperatorCandidateTransitionActiveV1", "CameraOperatorCandidateTetherAppliedV1",
}
WRITES = {
    "CameraOperatorFailureCodeV1", "CameraOperatorStateInitializedV1", "CameraOperatorStateModeV1",
    "CameraOperatorStateRecenterActiveV1", "CameraOperatorStateTranslationOffsetV1",
    "CameraOperatorStateTranslationVelocityV1", "CameraOperatorStateLookOffsetQuatV1",
    "CameraOperatorStateAngularVelocityV1", "CameraOperatorResultPositionV1",
    "CameraOperatorResultBodyQuatV1", "CameraOperatorResultGimbalQuatV1", "CameraOperatorResultModeV1",
    "CameraOperatorResultOverrideActiveV1", "CameraOperatorResultTransitionActiveV1",
    "CameraOperatorResultTetherAppliedV1", "CameraOperatorResultValidV1",
}
FORBIDDEN = (
    "CameraOperatorInput", "CameraOperatorPolicy", "CameraTransform", "CameraComfort", "CameraChannel",
    "CameraApply", "Airframe", "Flypath", "Repository", "PlaybackTime", "Event", "Cue", "StateClip", "Server",
)
VECTOR_NAMES = (
    "translation_offset", "translation_velocity", "angular_velocity", "position",
)
QUAT_NAMES = ("look", "body", "gimbal")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def finite_vector(value): return len(value) == 3 and all(math.isfinite(component) for component in value)
def valid_quat(value): return len(value) == 4 and all(math.isfinite(component) for component in value) and 0.999999 <= math.sqrt(sum(component * component for component in value)) <= 1.000001


def commit(candidate, upstream, prior_state, prior_result, failure):
    result = dict(prior_result); result["valid"] = False
    if not all(upstream): return dict(prior_state), result, failure
    valid = candidate["mode"] in ("directed", "free_look", "carrier_freecam")
    valid = valid and all(finite_vector(candidate[name]) for name in VECTOR_NAMES)
    valid = valid and all(valid_quat(candidate[name]) for name in QUAT_NAMES)
    if not valid: return dict(prior_state), result, "candidate_invalid"
    state = {
        "initialized": True, "mode": candidate["mode"], "recenter_active": candidate["recenter"],
        "translation_offset_cm": candidate["translation_offset"],
        "translation_velocity_cm_s": candidate["translation_velocity"],
        "look_offset": candidate["look"], "angular_velocity_deg_s": candidate["angular_velocity"],
    }
    result = {
        "position": candidate["position"], "body_rotation": candidate["body"],
        "gimbal_rotation": candidate["gimbal"], "mode": candidate["mode"],
        "override_active": candidate["override"], "transition_active": candidate["transition"],
        "tether_applied": candidate["tether"], "valid": True,
    }
    return state, result, ""


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_operator_commit_contract_base")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (115 if args.paste else 116), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == READS, "exact commit reads"); contracts.require(setters == WRITES, "exact commit writes")
    expected = {
        "BreakVector": 4, "Quat_IsFinite": 3, "Quat_Size": 3,
        "EqualEqual_StrStr": 3, "GreaterEqual_DoubleDouble": 15,
        "LessEqual_DoubleDouble": 15, "BooleanAND": 35, "BooleanOR": 2,
    }
    actual = {name: sum(member(node) == name for node in nodes.values()) for name in expected}
    contracts.require(actual == expected, f"native commit calls {actual}")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 2, "upstream and shape guards only")
    contracts.require(sum(member(node) == "CameraOperatorResultValidV1" for node in nodes.values()) == 2, "invalidate first and publish last")
    contracts.require(sum(member(node) == "CameraOperatorFailureCodeV1" for node in nodes.values()) == 2, "poison and success failure codes")
    contracts.require(not any("K2Node_Select" in node.node_class or "K2Node_Knot" in node.node_class for node in nodes.values()), "no hidden selection or reroute")
    text = args.graph.read_text(encoding="utf-8"); contracts.require(not any(value in text for value in FORBIDDEN), "no input/policy/external mutation")
    for literal in ("directed", "free_look", "carrier_freecam", "candidate_invalid", "0.999999", "1.000001"):
        contracts.require(literal in text, f"required commit literal {literal}")
    def explicit_bool_default(node, value):
        return re.search(
            rf'(?:^|,)(?<!Autogenerated)DefaultValue="{value}"(?:,|$)',
            node.pins["CameraOperatorResultValidV1"].body,
        ) is not None

    invalidators = [node for node in nodes.values() if member(node) == "CameraOperatorResultValidV1" and explicit_bool_default(node, "false")]
    publishers = [node for node in nodes.values() if member(node) == "CameraOperatorResultValidV1" and explicit_bool_default(node, "true")]
    contracts.require(len(invalidators) == len(publishers) == 1, "one invalidator and publisher")
    if args.paste: contracts.require(not invalidators[0].pins["execute"].links, "paste execution root")
    else: contracts.require_link(entries[0], "then", invalidators[0], "execute", "native entry invalidates first")
    contracts.require(not publishers[0].pins["then"].links, "result validity publishes last")
    body_get = next(node for node in nodes.values() if member(node) == "CameraOperatorCandidateBodyQuatV1")
    body_set = next(node for node in nodes.values() if member(node) == "CameraOperatorResultBodyQuatV1")
    gimbal_get = next(node for node in nodes.values() if member(node) == "CameraOperatorCandidateGimbalQuatV1")
    gimbal_set = next(node for node in nodes.values() if member(node) == "CameraOperatorResultGimbalQuatV1")
    contracts.require_link(body_get, "CameraOperatorCandidateBodyQuatV1", body_set, "CameraOperatorResultBodyQuatV1", "body result remains distinct")
    contracts.require_link(gimbal_get, "CameraOperatorCandidateGimbalQuatV1", gimbal_set, "CameraOperatorResultGimbalQuatV1", "gimbal result remains distinct")

    sys.path.insert(0, str(args.project_root / "tools/trajectory"))
    operator = load(args.project_root / "tools/trajectory/camera_operator_override_reference.py", "edd_operator_commit_reference")
    rng = random.Random(0xEDDC0117)
    def quat():
        axis = [rng.uniform(-1.0, 1.0) for _ in range(3)]; magnitude = math.sqrt(sum(value * value for value in axis)) or 1.0
        axis = [value / magnitude for value in axis]; half = math.radians(rng.uniform(-170.0, 170.0)) * 0.5
        return tuple(value * math.sin(half) for value in axis) + (math.cos(half),)
    state = operator.CameraOperatorStateV1(); snapshots = []
    for index in range(100):
        requested = rng.choice(operator.MODES_V1); position = tuple(rng.uniform(-1e5, 1e5) for _ in range(3)); body = quat(); gimbal = quat()
        frame = operator.apply_camera_operator_override_v1(
            True, requested, position, body, gimbal, quat(), tuple(rng.uniform(-1.0, 1.0) for _ in range(3)),
            tuple(rng.uniform(-1.0, 1.0) for _ in range(3)), rng.uniform(1.0 / 240.0, 0.25),
            index % 17 == 0, index % 29 == 0, operator.CameraOperatorPolicyV1(), state,
        )
        candidate = {
            "mode": frame.state.mode, "recenter": frame.state.recenter_active,
            "translation_offset": frame.state.translation_offset_cm,
            "translation_velocity": frame.state.translation_velocity_cm_s,
            "look": frame.state.look_offset, "angular_velocity": frame.state.angular_velocity_deg_s,
            "position": frame.position, "body": frame.body_rotation, "gimbal": frame.gimbal_rotation,
            "override": frame.override_active, "transition": frame.transition_active, "tether": frame.tether_applied,
        }
        prior_state = {"sentinel": object()}; prior_result = {"sentinel": object(), "valid": True}
        published_state, published_result, failure = commit(candidate, (True, True, True), prior_state, prior_result, "stale")
        contracts.require(published_state == asdict(frame.state), f"complete state snapshot at {index}")
        expected_result = {
            "position": frame.position, "body_rotation": frame.body_rotation, "gimbal_rotation": frame.gimbal_rotation,
            "mode": frame.state.mode, "override_active": frame.override_active,
            "transition_active": frame.transition_active, "tether_applied": frame.tether_applied, "valid": True,
        }
        contracts.require(published_result == expected_result and failure == "", f"complete result snapshot at {index}")
        contracts.require(published_result["body_rotation"] == body, f"body authorship exact at {index}")
        snapshots.append((candidate, published_state, published_result)); state = frame.state
    before = tuple(snapshots); [commit(candidate, (True, True, True), {}, {"valid": False}, "") for candidate, _, _ in reversed(snapshots)]
    contracts.require(tuple(snapshots) == before, "candidate and accepted snapshots immutable")

    canonical = dict(snapshots[-1][0]); poison = [{"mode": "bad"}]
    poison.extend({name: (math.nan, 0.0, 0.0)} for name in VECTOR_NAMES)
    for name in QUAT_NAMES:
        poison.extend(({name: (math.nan, 0.0, 0.0, 1.0)}, {name: (0.0, 0.0, 0.0, 2.0)}))
    prior_state = {"state": object()}; prior_result = {"result": object(), "valid": True}
    for overrides in poison:
        candidate = dict(canonical); candidate.update(overrides)
        failed_state, failed_result, failure = commit(candidate, (True, True, True), prior_state, prior_result, "")
        contracts.require(failed_state == prior_state and failed_state["state"] is prior_state["state"], "poison preserves prior state")
        contracts.require(failed_result["result"] is prior_result["result"] and failed_result["valid"] is False, "poison preserves result values and invalidates")
        contracts.require(failure == "candidate_invalid", "poison has stable failure")
    for upstream in ((False, True, True), (True, False, True), (True, True, False)):
        failed_state, failed_result, failure = commit(canonical, upstream, prior_state, prior_result, "validation_failed")
        contracts.require(failed_state == prior_state and failed_result["valid"] is False and failure == "validation_failed", "incomplete upstream is fail-closed no-op")
    print(f"Camera operator commit contracts passed ({'paste' if args.paste else 'full'}): {len(snapshots)} snapshots, {len(poison)} poisoned, 3 incomplete")


if __name__ == "__main__": main()
