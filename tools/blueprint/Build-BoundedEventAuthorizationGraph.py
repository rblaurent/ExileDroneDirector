"""Build closed-manifest, decision-only authorization for one selected Cue."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "AuthorizeSelectedCueV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_event_authorization_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""),
        "real": ("real", "double"), "string": ("string", ""),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    find_source = bp.read_blocks(args.project_root / "tools/blueprint/snippets/find-record-index-v1.eddgraph")
    forms.update({
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "valid_index": bp.find_block(edit, r'MemberName="Array_IsValidIndex"'),
        "find": bp.find_block(find_source, r'MemberName="Array_Find"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if value is not None:
            scalar.set_default(node, name, value)
        return node

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def array_get(name, kind, x, y):
        return get(name, kind, x, y, True)

    def item(source, source_pin, kind, index, x, y):
        node = add_form(f"item_{len(builder.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True); pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, "EventDispatchIndexV1", node, "Dimension 1")
        return node

    def find(source, source_pin, value, value_pin, kind, x, y):
        node = add_form(f"find_{len(builder.nodes)}", "find", x, y)
        pin_kind(node, "TargetArray", kind, True); pin_kind(node, "ItemToFind", kind); pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        if value is not None:
            bp.connect(value, value_pin, node, "ItemToFind")
        return node

    def retarget(node, member, kinds, parent=None):
        scalar.retarget_function(node, member)
        if parent is not None:
            node.text = re.sub(
                r'MemberParent="[^"]+"',
                f'MemberParent="/Script/CoreUObject.Class\'/Script/Engine.{parent}\'"',
                node.text, 1,
            )
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member, left, left_pin, x, y, *, right=None, right_pin=None, default_b=None, kind="int", parent=None):
        node = builder.add(f"{member}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"}, parent)
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(member, left, right, x, y):
        return compare(member, left, "ReturnValue", x, y, right=right, right_pin="ReturnValue", kind="bool")

    def and_all(conditions, x, y):
        current = conditions[0]
        for offset, condition in enumerate(conditions[1:]):
            current = boolean("BooleanAND", current, condition, x + offset * 224, y)
        return current

    def or_all(conditions, x, y):
        current = conditions[0]
        for offset, condition in enumerate(conditions[1:]):
            current = boolean("BooleanOR", current, condition, x + offset * 224, y)
        return current

    def string_equal(left, left_pin, *, right=None, right_pin=None, value=None, x=0, y=0):
        return compare(
            "EqualEqual_StrStr", left, left_pin, x, y,
            right=right, right_pin=right_pin, default_b=value,
            kind="string", parent="KismetStringLibrary",
        )

    def string_not_empty(left, left_pin, x, y):
        empty = string_equal(left, left_pin, value="", x=x, y=y)
        return compare("EqualEqual_BoolBool", empty, "ReturnValue", x + 224, y, default_b="false", kind="bool")

    def bool_value(left, left_pin, x, y):
        return compare("BooleanAND", left, left_pin, x, y, right=left, right_pin=left_pin, kind="bool")

    def terminal(code, authorized, x, y):
        first = set_("EventDispatchAuthorizedV1", "bool", x, y, "true" if authorized else "false") if authorized else None
        code_node = set_("EventDispatchCodeV1", "string", x + (224 if authorized else 0), y, code)
        valid = set_("EventDispatchResultValidV1", "bool", x + (448 if authorized else 224), y, "true")
        if first is not None:
            bp.connect(first, "then", code_node, "execute")
        bp.connect(code_node, "then", valid, "execute")
        return first or code_node

    result_false = set_("EventDispatchResultValidV1", "bool", 256, 5920, "false")
    authorized_false = set_("EventDispatchAuthorizedV1", "bool", 480, 5920, "false")
    bp.connect(builder.entry, "then", result_false, "execute")
    bp.connect(result_false, "then", authorized_false, "execute")

    selection_valid = get("EventSelectionValidV1", "bool", 0, 0)
    selection_guard = builder.add("selection_guard", "branch", 928, 5920)
    bp.connect(authorized_false, "then", selection_guard, "execute")
    bp.connect(selection_valid, "EventSelectionValidV1", selection_guard, "Condition")
    selected_index = get("EventDispatchIndexV1", "int", 0, 160)
    has_selection = compare("GreaterEqual_IntInt", selected_index, "EventDispatchIndexV1", 256, 160, default_b="0")
    selected_guard = builder.add("selected_guard", "branch", 1152, 5920)
    bp.connect(selection_guard, "then", selected_guard, "execute")
    bp.connect(has_selection, "ReturnValue", selected_guard, "Condition")
    no_selection_valid = set_("EventDispatchResultValidV1", "bool", 1376, 6240, "true")
    bp.connect(selected_guard, "else", no_selection_valid, "execute")

    arrays = {
        "adapter": array_get("EventCueAdapterIdsV1", "string", 0, 480),
        "version": array_get("EventCueAdapterVersionsV1", "int", 0, 640),
        "operation": array_get("EventCueOperationIdsV1", "string", 0, 800),
        "scope": array_get("EventCueScopesV1", "string", 0, 960),
        "binding_id": array_get("EventCueBindingIdsV1", "string", 0, 1120),
        "binding_region": array_get("EventCueBindingRegionsV1", "string", 0, 1280),
        "binding_adapter": array_get("EventCueBindingAdapterIdsV1", "string", 0, 1440),
        "binding_version": array_get("EventCueBindingAdapterVersionsV1", "int", 0, 1600),
        "binding_enabled": array_get("EventCueBindingEnabledV1", "bool", 0, 1760),
        "binding_reauthorized": array_get("EventCueBindingReauthorizedV1", "bool", 0, 1920),
    }
    valid_index = add_form("valid_index", "valid_index", 256, 480)
    pin_kind(valid_index, "TargetArray", "string", True); pin_kind(valid_index, "IndexToTest", "int"); pin_kind(valid_index, "ReturnValue", "bool")
    bp.connect(arrays["adapter"], "EventCueAdapterIdsV1", valid_index, "TargetArray")
    bp.connect(selected_index, "EventDispatchIndexV1", valid_index, "IndexToTest")
    index_guard = builder.add("index_guard", "branch", 1376, 5920)
    bp.connect(selected_guard, "then", index_guard, "execute")
    bp.connect(valid_index, "ReturnValue", index_guard, "Condition")
    invalid_index_terminal = terminal("event_selection_invalid", False, 1600, 6400)
    bp.connect(index_guard, "else", invalid_index_terminal, "execute")

    selected = {
        key: item(node, {
            "adapter": "EventCueAdapterIdsV1", "version": "EventCueAdapterVersionsV1",
            "operation": "EventCueOperationIdsV1", "scope": "EventCueScopesV1",
            "binding_id": "EventCueBindingIdsV1", "binding_region": "EventCueBindingRegionsV1",
            "binding_adapter": "EventCueBindingAdapterIdsV1", "binding_version": "EventCueBindingAdapterVersionsV1",
            "binding_enabled": "EventCueBindingEnabledV1", "binding_reauthorized": "EventCueBindingReauthorizedV1",
        }[key], {
            "version": "int", "binding_version": "int",
            "binding_enabled": "bool", "binding_reauthorized": "bool",
        }.get(key, "string"), selected_index, 512 + (index % 3) * 256, 2240 + (index // 3) * 160)
        for index, (key, node) in enumerate(arrays.items())
    }
    adapter = selected["adapter"]; version = selected["version"]; operation = selected["operation"]; scope = selected["scope"]
    is_version_one = compare("EqualEqual_IntInt", version, "Output", 1536, 480, default_b="1")
    adapter_local_presentation = string_equal(adapter, "Output", value="local.presentation", x=768, y=480)
    adapter_local_recording = string_equal(adapter, "Output", value="local.recording", x=768, y=640)
    adapter_door = string_equal(adapter, "Output", value="door", x=768, y=800)
    op_subtitle = string_equal(operation, "Output", value="subtitle", x=992, y=960)
    op_marker = string_equal(operation, "Output", value="marker", x=992, y=1120)
    op_wait = string_equal(operation, "Output", value="wait_until_open", x=992, y=1280)
    op_interact = string_equal(operation, "Output", value="request_normal_interaction", x=992, y=1440)
    op_lease = string_equal(operation, "Output", value="cinematic_state_lease", x=992, y=1600)
    scope_local = string_equal(scope, "Output", value="local_cinematic", x=1216, y=1760)
    scope_viewer = string_equal(scope, "Output", value="viewer_interaction", x=1216, y=1920)
    scope_server = string_equal(scope, "Output", value="server_world", x=1216, y=2080)
    subtitle_case = and_all((adapter_local_presentation, is_version_one, op_subtitle, scope_local), 1792, 800)
    marker_case = and_all((adapter_local_recording, is_version_one, op_marker, scope_local), 1792, 1040)
    wait_case = and_all((adapter_door, is_version_one, op_wait, scope_viewer), 1792, 1280)
    interact_case = and_all((adapter_door, is_version_one, op_interact, scope_viewer), 1792, 1520)
    lease_case = and_all((adapter_door, is_version_one, op_lease, scope_server), 1792, 1760)
    local_case = boolean("BooleanOR", subtitle_case, marker_case, 2464, 920)
    remote_case = or_all((wait_case, interact_case, lease_case), 2464, 1440)
    manifest_ready = boolean("BooleanOR", local_case, remote_case, 2912, 1120)

    flypath = get("EventFlypathIdV1", "string", 0, 2240)
    session_id = get("EventSessionIdV1", "string", 0, 2400)
    requester = get("EventRequesterIdV1", "string", 0, 2560)
    identity_ready = and_all((
        string_not_empty(flypath, "EventFlypathIdV1", 256, 2240),
        string_not_empty(session_id, "EventSessionIdV1", 704, 2400),
        string_not_empty(requester, "EventRequesterIdV1", 1152, 2560),
    ), 1792, 2400)
    identity_guard = builder.add("identity_guard", "branch", 1600, 5920)
    bp.connect(index_guard, "then", identity_guard, "execute")
    bp.connect(identity_ready, "ReturnValue", identity_guard, "Condition")
    identity_terminal = terminal("event_identity_invalid", False, 1824, 6560)
    bp.connect(identity_guard, "else", identity_terminal, "execute")
    manifest_guard = builder.add("manifest_guard", "branch", 1824, 5920)
    bp.connect(identity_guard, "then", manifest_guard, "execute")
    bp.connect(manifest_ready, "ReturnValue", manifest_guard, "Condition")
    manifest_terminal = terminal("adapter_operation_unavailable", False, 2048, 6720)
    bp.connect(manifest_guard, "else", manifest_terminal, "execute")
    local_guard = builder.add("local_guard", "branch", 2048, 5920)
    bp.connect(manifest_guard, "then", local_guard, "execute")
    bp.connect(local_case, "ReturnValue", local_guard, "Condition")

    binding_id_empty = string_equal(selected["binding_id"], "Output", value="", x=3136, y=2240)
    binding_adapter_empty = string_equal(selected["binding_adapter"], "Output", value="", x=3136, y=2400)
    binding_disabled = compare("EqualEqual_BoolBool", selected["binding_enabled"], "Output", 3136, 2560, default_b="false", kind="bool")
    binding_not_reauthorized = compare("EqualEqual_BoolBool", selected["binding_reauthorized"], "Output", 3136, 2720, default_b="false", kind="bool")
    local_isolated = and_all((binding_id_empty, binding_adapter_empty, binding_disabled, binding_not_reauthorized), 3584, 2480)
    local_isolation_guard = builder.add("local_isolation_guard", "branch", 2272, 5760)
    bp.connect(local_guard, "then", local_isolation_guard, "execute")
    bp.connect(local_isolated, "ReturnValue", local_isolation_guard, "Condition")
    local_success = terminal("authorized_local", True, 2496, 5600)
    local_failure = terminal("local_scope_not_isolated", False, 2496, 6880)
    bp.connect(local_isolation_guard, "then", local_success, "execute")
    bp.connect(local_isolation_guard, "else", local_failure, "execute")

    token = get("EventSessionTokenV1", "string", 0, 2880)
    token_ready = string_not_empty(token, "EventSessionTokenV1", 3136, 2880)
    token_guard = builder.add("token_guard", "branch", 2272, 6080)
    bp.connect(local_guard, "else", token_guard, "execute")
    bp.connect(token_ready, "ReturnValue", token_guard, "Condition")
    token_failure = terminal("event_session_token_missing", False, 2496, 7040)
    bp.connect(token_guard, "else", token_failure, "execute")

    binding_present = string_not_empty(selected["binding_id"], "Output", 4032, 2240)
    binding_enabled = bool_value(selected["binding_enabled"], "Output", 4032, 2400)
    binding_reauthorized = bool_value(selected["binding_reauthorized"], "Output", 4032, 2560)
    binding_ready = and_all((binding_present, binding_enabled, binding_reauthorized), 4480, 2400)
    binding_guard = builder.add("binding_guard", "branch", 2496, 6080)
    bp.connect(token_guard, "then", binding_guard, "execute")
    bp.connect(binding_ready, "ReturnValue", binding_guard, "Condition")
    binding_failure = terminal("target_binding_requires_rebind", False, 2720, 7200)
    bp.connect(binding_guard, "else", binding_failure, "execute")

    binding_adapter_match = string_equal(selected["binding_adapter"], "Output", right=adapter, right_pin="Output", x=4928, y=2240)
    binding_version_match = compare("EqualEqual_IntInt", selected["binding_version"], "Output", 4928, 2400, right=version, right_pin="Output")
    adapter_match = boolean("BooleanAND", binding_adapter_match, binding_version_match, 5152, 2320)
    adapter_guard = builder.add("adapter_guard", "branch", 2720, 6080)
    bp.connect(binding_guard, "then", adapter_guard, "execute")
    bp.connect(adapter_match, "ReturnValue", adapter_guard, "Condition")
    adapter_failure = terminal("target_binding_adapter_mismatch", False, 2944, 7360)
    bp.connect(adapter_guard, "else", adapter_failure, "execute")

    region = get("EventRegionIdV1", "string", 0, 3040)
    region_match = string_equal(selected["binding_region"], "Output", right=region, right_pin="EventRegionIdV1", x=5376, y=2480)
    region_guard = builder.add("region_guard", "branch", 2944, 6080)
    bp.connect(adapter_guard, "then", region_guard, "execute")
    bp.connect(region_match, "ReturnValue", region_guard, "Condition")
    region_failure = terminal("target_region_mismatch", False, 3168, 7520)
    bp.connect(region_guard, "else", region_failure, "execute")

    resolved_ids = array_get("EventResolvedBindingIdsV1", "string", 0, 3200)
    resolved_distances = array_get("EventResolvedBindingDistancesV1", "real", 0, 3360)
    resolved_index = find(resolved_ids, "EventResolvedBindingIdsV1", selected["binding_id"], "Output", "string", 5600, 2640)
    resolved = compare("GreaterEqual_IntInt", resolved_index, "ReturnValue", 5824, 2640, default_b="0")
    resolved_guard = builder.add("resolved_guard", "branch", 3168, 6080)
    bp.connect(region_guard, "then", resolved_guard, "execute")
    bp.connect(resolved, "ReturnValue", resolved_guard, "Condition")
    resolved_failure = terminal("target_unresolved", False, 3392, 7680)
    bp.connect(resolved_guard, "else", resolved_failure, "execute")
    distance = add_form("resolved_distance", "item", 6048, 2800)
    pin_kind(distance, "Array", "real", True); pin_kind(distance, "Output", "real")
    bp.connect(resolved_distances, "EventResolvedBindingDistancesV1", distance, "Array")
    bp.connect(resolved_index, "ReturnValue", distance, "Dimension 1")
    distance_finite = builder.finite(distance, "Output", 6272, 2800)
    distance_nonnegative = compare("GreaterEqual_DoubleDouble", distance, "Output", 6496, 2800, default_b="0.0", kind="real")
    distance_ready = boolean("BooleanAND", distance_finite, distance_nonnegative, 6720, 2800)
    distance_guard = builder.add("distance_guard", "branch", 3392, 6080)
    bp.connect(resolved_guard, "then", distance_guard, "execute")
    bp.connect(distance_ready, "ReturnValue", distance_guard, "Condition")
    distance_failure = terminal("target_distance_invalid", False, 3616, 7840)
    bp.connect(distance_guard, "else", distance_failure, "execute")

    within_wait = compare("LessEqual_DoubleDouble", distance, "Output", 6944, 2880, default_b="5000.0", kind="real")
    within_mutation = compare("LessEqual_DoubleDouble", distance, "Output", 6944, 3040, default_b="250.0", kind="real")
    wait_range = boolean("BooleanAND", wait_case, within_wait, 7168, 2880)
    mutation_case = boolean("BooleanOR", interact_case, lease_case, 7168, 3040)
    mutation_range = boolean("BooleanAND", mutation_case, within_mutation, 7392, 3040)
    range_ready = boolean("BooleanOR", wait_range, mutation_range, 7616, 2960)
    range_guard = builder.add("range_guard", "branch", 3616, 6080)
    bp.connect(distance_guard, "then", range_guard, "execute")
    bp.connect(range_ready, "ReturnValue", range_guard, "Condition")
    range_failure = terminal("target_out_of_range", False, 3840, 8000)
    bp.connect(range_guard, "else", range_failure, "execute")

    permissions = array_get("EventGrantedPermissionsV1", "string", 0, 3520)
    observe_find = find(permissions, "EventGrantedPermissionsV1", None, None, "string", 7840, 3200); scalar.set_default(observe_find, "ItemToFind", "door.observe")
    interact_find = find(permissions, "EventGrantedPermissionsV1", None, None, "string", 7840, 3360); scalar.set_default(interact_find, "ItemToFind", "door.interact")
    lease_find = find(permissions, "EventGrantedPermissionsV1", None, None, "string", 7840, 3520); scalar.set_default(lease_find, "ItemToFind", "door.lease.admin")
    observe_allowed = compare("GreaterEqual_IntInt", observe_find, "ReturnValue", 8064, 3200, default_b="0")
    interact_allowed = compare("GreaterEqual_IntInt", interact_find, "ReturnValue", 8064, 3360, default_b="0")
    lease_allowed = compare("GreaterEqual_IntInt", lease_find, "ReturnValue", 8064, 3520, default_b="0")
    permission_ready = or_all((
        boolean("BooleanAND", wait_case, observe_allowed, 8288, 3200),
        boolean("BooleanAND", interact_case, interact_allowed, 8288, 3360),
        boolean("BooleanAND", lease_case, lease_allowed, 8288, 3520),
    ), 8512, 3360)
    permission_guard = builder.add("permission_guard", "branch", 3840, 6080)
    bp.connect(range_guard, "then", permission_guard, "execute")
    bp.connect(permission_ready, "ReturnValue", permission_guard, "Condition")
    permission_failure = terminal("permission_denied", False, 4064, 8160)
    bp.connect(permission_guard, "else", permission_failure, "execute")

    rate = get("EventRemainingRateBudgetV1", "int", 0, 3680)
    rate_ready = compare("Greater_IntInt", rate, "EventRemainingRateBudgetV1", 8960, 3680, default_b="0")
    rate_guard = builder.add("rate_guard", "branch", 4064, 6080)
    bp.connect(permission_guard, "then", rate_guard, "execute")
    bp.connect(rate_ready, "ReturnValue", rate_guard, "Condition")
    rate_failure = terminal("event_rate_limited", False, 4288, 8320)
    bp.connect(rate_guard, "else", rate_failure, "execute")

    server_enabled = get("EventServerWorldEnabledV1", "bool", 0, 3840)
    server_approved = get("EventServerRevisionApprovedV1", "bool", 0, 4000)
    server_enabled_value = bool_value(server_enabled, "EventServerWorldEnabledV1", 9184, 3840)
    server_approved_value = bool_value(server_approved, "EventServerRevisionApprovedV1", 9184, 4000)
    server_allowed = boolean("BooleanAND", server_enabled_value, server_approved_value, 9408, 3920)
    not_lease = compare("EqualEqual_BoolBool", lease_case, "ReturnValue", 9408, 3760, default_b="false", kind="bool")
    policy_ready = boolean("BooleanOR", not_lease, server_allowed, 9632, 3840)
    policy_guard = builder.add("policy_guard", "branch", 4288, 6080)
    bp.connect(rate_guard, "then", policy_guard, "execute")
    bp.connect(policy_ready, "ReturnValue", policy_guard, "Condition")
    policy_failure = terminal("server_world_event_disabled", False, 4512, 8480)
    remote_success = terminal("authorized_remote", True, 4512, 5920)
    bp.connect(policy_guard, "else", policy_failure, "execute")
    bp.connect(policy_guard, "then", remote_success, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
