"""Structural and executable contracts for decision-only event authorization."""

from __future__ import annotations

import argparse
import importlib.util
import math
import re
import sys
from pathlib import Path


EXPECTED_CODES = {
    "event_selection_invalid", "event_identity_invalid",
    "adapter_operation_unavailable", "authorized_local",
    "local_scope_not_isolated", "event_session_token_missing",
    "target_binding_requires_rebind", "target_binding_adapter_mismatch",
    "target_region_mismatch", "target_unresolved", "target_distance_invalid",
    "target_out_of_range", "permission_denied", "event_rate_limited",
    "server_world_event_disabled", "authorized_remote",
}


def load(path):
    spec = importlib.util.spec_from_file_location("edd_event_authorization_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def cue(operation="subtitle"):
    cases = {
        "subtitle": ("local.presentation", 1, "subtitle", "local_cinematic", "", "", "", 0, False, False),
        "marker": ("local.recording", 1, "marker", "local_cinematic", "", "", "", 0, False, False),
        "wait": ("door", 1, "wait_until_open", "viewer_interaction", "door-main", "exiled-lands", "door", 1, True, True),
        "interact": ("door", 1, "request_normal_interaction", "viewer_interaction", "door-main", "exiled-lands", "door", 1, True, True),
        "lease": ("door", 1, "cinematic_state_lease", "server_world", "door-main", "exiled-lands", "door", 1, True, True),
    }
    values = cases[operation]
    return dict(zip((
        "adapter", "version", "operation", "scope", "binding_id",
        "binding_region", "binding_adapter", "binding_version",
        "binding_enabled", "binding_reauthorized",
    ), values))


def context(**changes):
    values = dict(
        selection_valid=True, selected_index=0,
        selection_code="event_authorization_pending",
        flypath_id="flypath-7", session_id="session-9", requester_id="player-a",
        token="token-11", region="exiled-lands",
        resolved_ids=("door-main",), resolved_distances=(100.0,),
        permissions=("door.observe", "door.interact", "door.lease.admin"),
        rate_budget=8, server_enabled=False, server_approved=False,
    )
    values.update(changes)
    return values


def authorize(selected_cues, execution):
    result = dict(result_valid=False, authorized=False, code=execution["selection_code"])
    if not execution["selection_valid"]:
        return result
    index = execution["selected_index"]
    if index < 0:
        result["result_valid"] = True
        return result
    if index >= len(selected_cues):
        return dict(result_valid=True, authorized=False, code="event_selection_invalid")
    item = selected_cues[index]
    if not execution["flypath_id"] or not execution["session_id"] or not execution["requester_id"]:
        return dict(result_valid=True, authorized=False, code="event_identity_invalid")
    manifest = (
        ("local.presentation", 1, "subtitle", "local_cinematic"),
        ("local.recording", 1, "marker", "local_cinematic"),
        ("door", 1, "wait_until_open", "viewer_interaction"),
        ("door", 1, "request_normal_interaction", "viewer_interaction"),
        ("door", 1, "cinematic_state_lease", "server_world"),
    )
    key = (item["adapter"], item["version"], item["operation"], item["scope"])
    if key not in manifest:
        return dict(result_valid=True, authorized=False, code="adapter_operation_unavailable")
    local = item["scope"] == "local_cinematic"
    if local:
        isolated = (
            not item["binding_id"] and not item["binding_adapter"]
            and item["binding_enabled"] is False
            and item["binding_reauthorized"] is False
        )
        return dict(
            result_valid=True, authorized=isolated,
            code="authorized_local" if isolated else "local_scope_not_isolated",
        )
    if not execution["token"]:
        return dict(result_valid=True, authorized=False, code="event_session_token_missing")
    if not item["binding_id"] or not item["binding_enabled"] or not item["binding_reauthorized"]:
        return dict(result_valid=True, authorized=False, code="target_binding_requires_rebind")
    if item["binding_adapter"] != item["adapter"] or item["binding_version"] != item["version"]:
        return dict(result_valid=True, authorized=False, code="target_binding_adapter_mismatch")
    if item["binding_region"] != execution["region"]:
        return dict(result_valid=True, authorized=False, code="target_region_mismatch")
    try:
        resolved_index = execution["resolved_ids"].index(item["binding_id"])
    except ValueError:
        return dict(result_valid=True, authorized=False, code="target_unresolved")
    distance = execution["resolved_distances"][resolved_index]
    if not math.isfinite(distance) or distance < 0.0:
        return dict(result_valid=True, authorized=False, code="target_distance_invalid")
    maximum_range = 5000.0 if item["operation"] == "wait_until_open" else 250.0
    if distance > maximum_range:
        return dict(result_valid=True, authorized=False, code="target_out_of_range")
    required = {
        "wait_until_open": "door.observe",
        "request_normal_interaction": "door.interact",
        "cinematic_state_lease": "door.lease.admin",
    }[item["operation"]]
    if required not in execution["permissions"]:
        return dict(result_valid=True, authorized=False, code="permission_denied")
    if execution["rate_budget"] <= 0:
        return dict(result_valid=True, authorized=False, code="event_rate_limited")
    if item["operation"] == "cinematic_state_lease" and not (
        execution["server_enabled"] and execution["server_approved"]
    ):
        return dict(result_valid=True, authorized=False, code="server_world_event_disabled")
    return dict(result_valid=True, authorized=True, code="authorized_remote")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes) == (178 if args.paste else 179), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_VariableSet_0"]
    contracts.require(member(root) == "EventDispatchResultValidV1", "authorization execution root")
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(entries[0], "then", root, "execute", "entry invalidates result authority")
    contracts.require(sum("K2Node_GetArrayItem" in node.node_class for node in nodes.values()) == 11, "ten selected fields plus resolved distance")
    contracts.require(text.count('MemberName="Array_Find"') == 4, "resolved target plus three permissions")
    contracts.require(text.count('MemberName="Array_IsValidIndex"') == 1, "selected index revalidated")
    contracts.require(text.count('MemberName="EqualEqual_StrStr"') == 20, "closed manifest, identity, and binding comparisons")
    contracts.require(text.count("KismetStringLibrary") == 20, "string comparisons use reflected owner")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values()) == 17, "exact typed rejection chain")
    writes = [member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require(set(writes) == {"EventDispatchResultValidV1", "EventDispatchAuthorizedV1", "EventDispatchCodeV1"}, "decision-only write ownership")
    contracts.require("EventDispatchIndexV1" not in writes, "selected index immutable")
    contracts.require(all(code in text for code in EXPECTED_CODES), "all typed decision codes frozen")
    for required in (
        "EventSelectionValidV1", "EventFlypathIdV1", "EventSessionIdV1",
        "EventRequesterIdV1", "EventSessionTokenV1", "EventRegionIdV1",
        "EventResolvedBindingIdsV1", "EventResolvedBindingDistancesV1",
        "EventGrantedPermissionsV1", "EventRemainingRateBudgetV1",
        "EventServerWorldEnabledV1", "EventServerRevisionApprovedV1",
    ):
        contracts.require(required in text, f"required authorization input {required}")
    contracts.require("EventCuePayloadsV1" not in text, "payload remains compiled-plan owned and uninterpreted")
    for forbidden in (
        "EventLedgerIdsV1", "EventCrossedIndicesV1", "CameraTransform",
        "DroneCamera", "Repository", "K2_SetActor", "K2_SetRelative",
        "Interact", "OpenDoor", "CloseDoor", "HUD", "UI",
    ):
        contracts.require(forbidden not in text, f"execution/owner forbidden {forbidden}")

    local_subtitle = authorize((cue("subtitle"),), context())
    local_marker = authorize((cue("marker"),), context())
    wait = authorize((cue("wait"),), context())
    interact = authorize((cue("interact"),), context())
    lease = authorize((cue("lease"),), context(server_enabled=True, server_approved=True))
    contracts.require(local_subtitle == {"result_valid": True, "authorized": True, "code": "authorized_local"}, "subtitle authorized")
    contracts.require(local_marker == local_subtitle, "recording marker authorized locally")
    contracts.require(wait == {"result_valid": True, "authorized": True, "code": "authorized_remote"}, "read-only door gate authorized")
    contracts.require(interact == wait and lease == wait, "bounded mutating requests authorized only as decisions")
    no_selection = authorize((), context(selected_index=-1, selection_code="no_event_crossing"))
    contracts.require(no_selection == {"result_valid": True, "authorized": False, "code": "no_event_crossing"}, "typed no-selection preserved")
    inactive = authorize((cue(),), context(selection_valid=False, selection_code="event_selection_invalid"))
    contracts.require(not inactive["result_valid"] and not inactive["authorized"], "invalid selection has no result authority")
    invalid_index = authorize((cue(),), context(selected_index=2))
    contracts.require(invalid_index["code"] == "event_selection_invalid", "selected index rechecked")

    local_bound = cue("subtitle"); local_bound.update(binding_id="unexpected", binding_adapter="door", binding_enabled=True)
    failures = (
        ((local_bound,), context(), "local_scope_not_isolated"),
        ((cue("wait"),), context(token=""), "event_session_token_missing"),
        ((cue("wait"),), context(resolved_ids=()), "target_unresolved"),
        ((cue("wait"),), context(region="siptah"), "target_region_mismatch"),
        ((cue("wait"),), context(resolved_distances=(math.nan,)), "target_distance_invalid"),
        ((cue("wait"),), context(resolved_distances=(5000.1,)), "target_out_of_range"),
        ((cue("wait"),), context(permissions=()), "permission_denied"),
        ((cue("wait"),), context(rate_budget=0), "event_rate_limited"),
        ((cue("lease"),), context(), "server_world_event_disabled"),
        (({**cue("wait"), "binding_reauthorized": False},), context(), "target_binding_requires_rebind"),
        (({**cue("wait"), "binding_adapter": "arbitrary"},), context(), "target_binding_adapter_mismatch"),
        (({**cue("wait"), "operation": "arbitrary_function"},), context(), "adapter_operation_unavailable"),
    )
    for selected_cues, execution, code in failures:
        observed = authorize(selected_cues, execution)
        contracts.require(observed == {"result_valid": True, "authorized": False, "code": code}, code)
    for field in ("flypath_id", "session_id", "requester_id"):
        observed = authorize((cue(),), context(**{field: ""}))
        contracts.require(observed["code"] == "event_identity_invalid", f"identity {field}")
    print(
        f"Bounded event authorization contracts passed "
        f"({'paste' if args.paste else 'full'}): five capabilities and typed failures"
    )


if __name__ == "__main__":
    main()
