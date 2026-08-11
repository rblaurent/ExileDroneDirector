"""Build modular semantic validators for the staged Blueprint repository.

The repository actor cannot expose reliable generated function parameters in
Enhanced, so every helper consumes the explicit ``Scratch*V1`` transaction
state.  ``ValidateDocumentV1`` is the only document entry point that resets
validity.  The waypoint/segment helpers may only turn validity off; record
helpers are similarly monotonic after the record root guard succeeds.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
import re
import sys


def load_encoder(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_validation_encoder_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def retarget_function(node, member: str) -> None:
    node.text = re.sub(r'MemberName="[^"]+"', f'MemberName="{member}"', node.text, count=1)


def remove_pin(node, pin_name: str) -> None:
    pin_id = node.pins.pop(pin_name)
    node.text = "\n".join(line for line in node.text.splitlines() if f"PinId={pin_id}" not in line)


def array_find_form(node, enc, kind: str) -> None:
    retarget_function(node, "Array_Find")
    enc.rename_pin(node, "IndexToTest", "ItemToFind")
    enc.set_pin_type(node, "TargetArray", kind, array=True)
    enc.set_pin_type(node, "ItemToFind", kind)
    enc.set_pin_type(node, "ReturnValue", "int")
    enc.set_default(node, "ReturnValue", "-1")


def array_length_form(node, enc, kind: str) -> None:
    enc.set_pin_type(node, "TargetArray", kind, array=True)
    enc.set_pin_type(node, "ReturnValue", "int")


def array_valid_index_form(node, enc, kind: str) -> None:
    enc.set_pin_type(node, "TargetArray", kind, array=True)


def array_item_form(node, enc, kind: str) -> None:
    enc.set_pin_type(node, "Array", kind, array=True)
    enc.set_pin_type(node, "Output", kind)


def load_templates(project_root: Path, bp, enc) -> dict[str, str]:
    root = project_root / "tools" / "blueprint"
    templates = enc.load_templates(project_root, bp)
    sync = bp.read_blocks(root / "snippets" / "sync-draft-waypoints-v1.eddgraph")
    start = bp.read_blocks(root / "snippets" / "start-linear-playback.eddgraph")
    edit = bp.read_blocks(root / "templates" / "waypoint-edit-node-forms.eddgraph")
    decoder = bp.read_blocks(root / "templates" / "repository-decoder-native-node-forms.eddgraph")
    linear = bp.read_blocks(root / "templates" / "linear-playback-node-forms.eddgraph")
    templates.update(
        {
            "branch": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse "),
            "int_math": bp.find_block(sync, r'MemberName="EqualEqual_IntInt"'),
            "double_math": bp.find_block(start, r'MemberName="GreaterEqual_DoubleDouble"'),
            "string_math": bp.find_block(decoder, r'MemberName="EqualEqual_StrStr"'),
            "array_length": bp.find_block(edit, r'MemberName="Array_Length"'),
            "array_valid_index": bp.find_block(edit, r'MemberName="Array_IsValidIndex"'),
            "array_find": bp.find_block(edit, r'MemberName="Array_IsValidIndex"'),
            "array_item": bp.find_block(decoder, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_GetArrayItem "),
            "int_subtract": bp.find_block(linear, r'MemberName="Subtract_IntInt"'),
        }
    )
    return templates


class ValidationBuilder:
    def __init__(self, bp, enc, templates: dict[str, str], graph: str):
        self.bp = bp
        self.enc = enc
        self.b = enc.Builder(bp, templates, graph)

    @property
    def entry(self):
        return self.b.entry

    @property
    def nodes(self):
        return self.b.nodes

    def branch(self, x: int, y: int):
        return self.b.add(f"branch_{len(self.nodes)}", "branch", x, y)

    def int_math(self, function: str, x: int, y: int, *, b_default: str | None = None):
        node = self.b.add(f"{function}_{len(self.nodes)}", "int_math", x, y)
        retarget_function(node, function)
        if function in {"Add_IntInt", "Subtract_IntInt", "Max_IntInt", "Min_IntInt"}:
            self.enc.set_pin_type(node, "ReturnValue", "int")
        if b_default is not None:
            self.enc.set_default(node, "B", b_default)
        return node

    def double_math(self, function: str, x: int, y: int, *, b_default: str | None = None):
        node = self.b.add(f"{function}_{len(self.nodes)}", "double_math", x, y)
        retarget_function(node, function)
        if function in {"Add_DoubleDouble", "Subtract_DoubleDouble"}:
            self.enc.set_pin_type(node, "ReturnValue", "real")
        if b_default is not None:
            self.enc.set_default(node, "B", b_default)
        return node

    def string_math(self, function: str, x: int, y: int, *, b_default: str | None = None):
        node = self.b.add(f"{function}_{len(self.nodes)}", "string_math", x, y)
        retarget_function(node, function)
        if b_default is not None:
            self.enc.set_default(node, "B", b_default)
        return node

    def bool_math(self, function: str, x: int, y: int):
        node = self.b.add(f"{function}_{len(self.nodes)}", "int_math", x, y)
        retarget_function(node, function)
        for pin in ("A", "B", "ReturnValue"):
            self.enc.set_pin_type(node, pin, "bool")
        return node

    def and_all(self, conditions, x: int, y: int):
        if not conditions:
            raise RuntimeError("and_all requires at least one condition")
        result = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            node = self.bool_math("BooleanAND", x + index * 224, y)
            self.bp.connect(result, "ReturnValue", node, "A")
            self.bp.connect(condition, "ReturnValue", node, "B")
            result = node
        return result

    def or_all(self, conditions, x: int, y: int):
        if not conditions:
            raise RuntimeError("or_all requires at least one condition")
        result = conditions[0]
        for index, condition in enumerate(conditions[1:]):
            node = self.bool_math("BooleanOR", x + index * 224, y)
            self.bp.connect(result, "ReturnValue", node, "A")
            self.bp.connect(condition, "ReturnValue", node, "B")
            result = node
        return result

    def finite(self, source, pin: str, x: int, y: int):
        subtract = self.double_math("Subtract_DoubleDouble", x, y)
        equal = self.double_math("EqualEqual_DoubleDouble", x + 224, y, b_default="0.0")
        self.bp.connect(source, pin, subtract, "A")
        self.bp.connect(source, pin, subtract, "B")
        self.bp.connect(subtract, "ReturnValue", equal, "A")
        return equal

    def length(self, source, source_pin: str, kind: str, x: int, y: int):
        node = self.b.add(f"length_{len(self.nodes)}", "array_length", x, y)
        array_length_form(node, self.enc, kind)
        self.bp.connect(source, source_pin, node, "TargetArray")
        return node

    def valid_index(self, source, source_pin: str, index_source, index_pin: str, kind: str, x: int, y: int):
        node = self.b.add(f"valid_index_{len(self.nodes)}", "array_valid_index", x, y)
        array_valid_index_form(node, self.enc, kind)
        self.bp.connect(source, source_pin, node, "TargetArray")
        self.bp.connect(index_source, index_pin, node, "IndexToTest")
        return node

    def array_item(self, source, source_pin: str, index_source, index_pin: str, kind: str, x: int, y: int):
        node = self.b.add(f"array_item_{len(self.nodes)}", "array_item", x, y)
        array_item_form(node, self.enc, kind)
        self.bp.connect(source, source_pin, node, "Array")
        self.bp.connect(index_source, index_pin, node, "Dimension 1")
        return node


def connect_exec(bp, nodes) -> None:
    for left, right in zip(nodes, nodes[1:]):
        bp.connect(left, "then", right, "execute")


def fold_paste_layout(nodes):
    """Center the execution seam while compacting large validator selections.

    Unreal centers pasted nodes on their bounding box.  Keeping the first body
    execution node at the selection centre makes the one required native-entry
    wire deterministic, while alternating rows keep every other node nearby.
    Only paste coordinates change; identities, pins, and links are untouched.
    """
    folded = copy.deepcopy(nodes)
    body = [node for node in folded[1:]]
    roots = [
        node for node in body
        if re.search(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", node.text)
    ]
    if len(roots) != 1:
        raise RuntimeError(f"Validation graph must own exactly one body root; found {len(roots)}")
    root = roots[0]
    ordered = [root, *(node for node in body if node is not root)]
    positions = {root.name: (800, 0)}
    for index, node in enumerate(ordered[1:]):
        column = index % 6
        row = index // 6 + 1
        magnitude = ((row + 1) // 2) * 384
        y = magnitude if row % 2 else -magnitude
        positions[node.name] = (column * 320, y)
    for node in body:
        x, y = positions[node.name]
        node.text = re.sub(r"(?m)^(\s*NodePosX=)-?\d+$", rf"\g<1>{x}", node.text)
        node.text = re.sub(r"(?m)^(\s*NodePosY=)-?\d+$", rf"\g<1>{y}", node.text)
    return folded


def build_waypoint(bp, enc, templates):
    v = ValidationBuilder(bp, enc, templates, "ValidateWaypointV1")
    b = v.b
    waypoint = b.getter("ScratchWaypointV1", "waypoint", 0, 480)
    split = b.add("break_waypoint", "break_waypoint", 256, 480)
    transform = b.add("break_transform", "break_transform", 512, 480)
    location = b.add("break_location", "break_vector", 768, 480)
    scale = b.add("break_scale", "break_vector", 768, 720)
    quat = b.add("rotation_quaternion", "rotator_to_quat", 768, 960)
    break_quat = b.add("break_quaternion", "break_quat", 1024, 960)
    bp.connect(waypoint, "ScratchWaypointV1", split, "ST_EDD_Waypoint")
    bp.connect(split, enc.WP_TRANSFORM, transform, "InTransform")
    bp.connect(transform, "Location", location, "InVec")
    bp.connect(transform, "Scale", scale, "InVec")
    bp.connect(transform, "Rotation", quat, "InRot")
    bp.connect(quat, "ReturnValue", break_quat, "InQuat")

    ids = b.getter("ScratchIntegerArrayV1", "int", 1024, 1280, array=True)
    find_id = b.add("find_waypoint_id", "array_find", 1280, 1280)
    array_find_form(find_id, enc, "int")
    bp.connect(ids, "ScratchIntegerArrayV1", find_id, "TargetArray")
    bp.connect(split, enc.WP_ID, find_id, "ItemToFind")

    conditions = []
    positive_id = v.int_math("Greater_IntInt", 1280, 480, b_default="0")
    bp.connect(split, enc.WP_ID, positive_id, "A")
    conditions.append(positive_id)
    unique_id = v.int_math("EqualEqual_IntInt", 1504, 1280, b_default="-1")
    bp.connect(find_id, "ReturnValue", unique_id, "A")
    conditions.append(unique_id)

    y = 480
    for source, pin in (
        (location, "X"), (location, "Y"), (location, "Z"),
        (break_quat, "X"), (break_quat, "Y"), (break_quat, "Z"), (break_quat, "W"),
        (split, enc.WP_FOCAL), (split, enc.WP_APERTURE), (split, enc.WP_FOCUS), (split, enc.WP_HOLD),
    ):
        conditions.append(v.finite(source, pin, 1728, y))
        y += 144

    for source, pin in ((scale, "X"), (scale, "Y"), (scale, "Z")):
        equal = v.double_math("EqualEqual_DoubleDouble", 2176, y, b_default="1.0")
        bp.connect(source, pin, equal, "A")
        conditions.append(equal)
        y += 144

    for pin, function in (
        (enc.WP_FOCAL, "Greater_DoubleDouble"),
        (enc.WP_APERTURE, "Greater_DoubleDouble"),
        (enc.WP_FOCUS, "GreaterEqual_DoubleDouble"),
        (enc.WP_HOLD, "GreaterEqual_DoubleDouble"),
    ):
        domain = v.double_math(function, 2400, y, b_default="0.0")
        bp.connect(split, pin, domain, "A")
        conditions.append(domain)
        y += 144

    combined = v.and_all(conditions, 2848, 480)
    branch_x = 2848 + len(conditions) * 224
    branch = v.branch(branch_x, 0)
    bp.connect(combined, "ReturnValue", branch, "Condition")
    bp.connect(v.entry, "then", branch, "execute")

    invalid = b.setter("ScratchValidV1", "bool", branch_x + 256, -256)
    enc.set_default(invalid, "ScratchValidV1", "false")
    bp.connect(branch, "else", invalid, "execute")

    add_id = b.array_add("int", branch_x + 256, 0)
    bp.connect(ids, "ScratchIntegerArrayV1", add_id, "TargetArray")
    bp.connect(split, enc.WP_ID, add_id, "NewItem")
    duration = b.getter("ScratchCalculatedDurationV1", "real", branch_x + 256, 400)
    add_duration = v.double_math("Add_DoubleDouble", branch_x + 512, 400)
    bp.connect(duration, "ScratchCalculatedDurationV1", add_duration, "A")
    bp.connect(split, enc.WP_HOLD, add_duration, "B")
    store_duration = b.setter("ScratchCalculatedDurationV1", "real", branch_x + 512, 0)
    bp.connect(add_duration, "ReturnValue", store_duration, "ScratchCalculatedDurationV1")
    bp.connect(branch, "then", add_id, "execute")
    bp.connect(add_id, "then", store_duration, "execute")
    return v.nodes


def build_segment(bp, enc, templates):
    v = ValidationBuilder(bp, enc, templates, "ValidateSegmentV1")
    b = v.b
    segment = b.getter("ScratchSegmentV1", "segment", 0, 480)
    split = b.add("break_segment", "break_segment", 256, 480)
    document = b.getter("ScratchDocumentV1", "document", 0, 800)
    break_document = b.add("break_document", "break_document", 256, 800)
    index = b.getter("ScratchIndexV1", "int", 512, 800)
    next_index = v.int_math("Add_IntInt", 736, 800, b_default="1")
    bp.connect(segment, "ScratchSegmentV1", split, "ST_EDD_Segment")
    bp.connect(document, "ScratchDocumentV1", break_document, "ST_EDD_FlypathDocument")
    bp.connect(index, "ScratchIndexV1", next_index, "A")

    valid_from = v.valid_index(break_document, enc.DOC_WAYPOINTS, index, "ScratchIndexV1", "waypoint", 960, 720)
    valid_to = v.valid_index(break_document, enc.DOC_WAYPOINTS, next_index, "ReturnValue", "waypoint", 960, 880)
    valid_indices = v.and_all([valid_from, valid_to], 1184, 720)
    index_branch = v.branch(1408, 0)
    bp.connect(valid_indices, "ReturnValue", index_branch, "Condition")
    bp.connect(v.entry, "then", index_branch, "execute")
    invalid_index = b.setter("ScratchValidV1", "bool", 1664, -256)
    enc.set_default(invalid_index, "ScratchValidV1", "false")
    bp.connect(index_branch, "else", invalid_index, "execute")

    from_item = v.array_item(break_document, enc.DOC_WAYPOINTS, index, "ScratchIndexV1", "waypoint", 1664, 640)
    to_item = v.array_item(break_document, enc.DOC_WAYPOINTS, next_index, "ReturnValue", "waypoint", 1664, 880)
    from_waypoint = b.add("break_from_waypoint", "break_waypoint", 1888, 640)
    to_waypoint = b.add("break_to_waypoint", "break_waypoint", 1888, 880)
    bp.connect(from_item, "Output", from_waypoint, "ST_EDD_Waypoint")
    bp.connect(to_item, "Output", to_waypoint, "ST_EDD_Waypoint")

    ids = b.getter("ScratchIntegerArrayV1", "int", 1888, 1120, array=True)
    find_id = b.add("find_segment_id", "array_find", 2112, 1120)
    array_find_form(find_id, enc, "int")
    bp.connect(ids, "ScratchIntegerArrayV1", find_id, "TargetArray")
    bp.connect(split, enc.SEGMENT_ID, find_id, "ItemToFind")

    conditions = []
    for source_pin, function, default in (
        (enc.SEGMENT_ID, "Greater_IntInt", "0"),
        (enc.SEGMENT_FROM, "EqualEqual_IntInt", None),
        (enc.SEGMENT_TO, "EqualEqual_IntInt", None),
    ):
        node = v.int_math(function, 2336, 480 + len(conditions) * 144, b_default=default)
        bp.connect(split, source_pin, node, "A")
        if source_pin == enc.SEGMENT_FROM:
            bp.connect(from_waypoint, enc.WP_ID, node, "B")
        elif source_pin == enc.SEGMENT_TO:
            bp.connect(to_waypoint, enc.WP_ID, node, "B")
        conditions.append(node)
    unique = v.int_math("EqualEqual_IntInt", 2336, 912, b_default="-1")
    bp.connect(find_id, "ReturnValue", unique, "A")
    conditions.append(unique)
    finite_duration = v.finite(split, enc.SEGMENT_DURATION, 2336, 1056)
    conditions.append(finite_duration)
    positive_duration = v.double_math("Greater_DoubleDouble", 2336, 1200, b_default="0.0")
    bp.connect(split, enc.SEGMENT_DURATION, positive_duration, "A")
    conditions.append(positive_duration)
    for source_pin in (enc.SEGMENT_CURVE, enc.SEGMENT_TIME):
        nonempty = v.string_math("NotEqual_StrStr", 2336, 1344 + len(conditions) * 64, b_default="")
        bp.connect(split, source_pin, nonempty, "A")
        conditions.append(nonempty)

    combined = v.and_all(conditions, 2784, 480)
    value_branch_x = 2784 + len(conditions) * 224
    value_branch = v.branch(value_branch_x, 0)
    bp.connect(combined, "ReturnValue", value_branch, "Condition")
    bp.connect(index_branch, "then", value_branch, "execute")
    invalid_value = b.setter("ScratchValidV1", "bool", value_branch_x + 256, -256)
    enc.set_default(invalid_value, "ScratchValidV1", "false")
    bp.connect(value_branch, "else", invalid_value, "execute")

    add_id = b.array_add("int", value_branch_x + 256, 0)
    bp.connect(ids, "ScratchIntegerArrayV1", add_id, "TargetArray")
    bp.connect(split, enc.SEGMENT_ID, add_id, "NewItem")
    duration = b.getter("ScratchCalculatedDurationV1", "real", value_branch_x + 256, 400)
    add_duration = v.double_math("Add_DoubleDouble", value_branch_x + 512, 400)
    bp.connect(duration, "ScratchCalculatedDurationV1", add_duration, "A")
    bp.connect(split, enc.SEGMENT_DURATION, add_duration, "B")
    store_duration = b.setter("ScratchCalculatedDurationV1", "real", value_branch_x + 512, 0)
    bp.connect(add_duration, "ReturnValue", store_duration, "ScratchCalculatedDurationV1")
    bp.connect(value_branch, "then", add_id, "execute")
    bp.connect(add_id, "then", store_duration, "execute")
    return v.nodes


def build_document(bp, enc, templates):
    v = ValidationBuilder(bp, enc, templates, "ValidateDocumentV1")
    b = v.b
    document = b.getter("ScratchDocumentV1", "document", 0, 560)
    split = b.add("break_document", "break_document", 256, 560)
    bp.connect(document, "ScratchDocumentV1", split, "ST_EDD_FlypathDocument")

    waypoint_length = v.length(split, enc.DOC_WAYPOINTS, "waypoint", 512, 560)
    segment_length = v.length(split, enc.DOC_SEGMENTS, "segment", 512, 720)
    waypoint_zero = v.int_math("EqualEqual_IntInt", 736, 400, b_default="0")
    segment_zero = v.int_math("EqualEqual_IntInt", 736, 560, b_default="0")
    empty_topology = v.bool_math("BooleanAND", 960, 400)
    waypoint_positive = v.int_math("Greater_IntInt", 736, 720, b_default="0")
    minus_one = v.int_math("Subtract_IntInt", 960, 720, b_default="1")
    segment_count = v.int_math("EqualEqual_IntInt", 1184, 720)
    nonempty_topology = v.bool_math("BooleanAND", 1408, 720)
    topology_valid = v.bool_math("BooleanOR", 1632, 560)
    bp.connect(waypoint_length, "ReturnValue", waypoint_zero, "A")
    bp.connect(segment_length, "ReturnValue", segment_zero, "A")
    bp.connect(waypoint_zero, "ReturnValue", empty_topology, "A")
    bp.connect(segment_zero, "ReturnValue", empty_topology, "B")
    bp.connect(waypoint_length, "ReturnValue", waypoint_positive, "A")
    bp.connect(waypoint_length, "ReturnValue", minus_one, "A")
    bp.connect(minus_one, "ReturnValue", segment_count, "A")
    bp.connect(segment_length, "ReturnValue", segment_count, "B")
    bp.connect(waypoint_positive, "ReturnValue", nonempty_topology, "A")
    bp.connect(segment_count, "ReturnValue", nonempty_topology, "B")
    bp.connect(empty_topology, "ReturnValue", topology_valid, "A")
    bp.connect(nonempty_topology, "ReturnValue", topology_valid, "B")

    conditions = [topology_valid]
    for pin, function, default in (
        (enc.DOC_SCHEMA, "EqualEqual_IntInt", "1"),
        (enc.DOC_ENGINE, "EqualEqual_IntInt", "1"),
        (enc.DOC_REVISION, "Greater_IntInt", "0"),
    ):
        node = v.int_math(function, 512, 880 + len(conditions) * 144, b_default=default)
        bp.connect(split, pin, node, "A")
        conditions.append(node)
    for pin in (enc.DOC_REGION, enc.DOC_PROFILE):
        node = v.string_math("NotEqual_StrStr", 736, 880 + len(conditions) * 144, b_default="")
        bp.connect(split, pin, node, "A")
        conditions.append(node)
    hash_empty = v.string_math("EqualEqual_StrStr", 736, 880 + len(conditions) * 144, b_default="")
    bp.connect(split, enc.DOC_HASH, hash_empty, "A")
    conditions.append(hash_empty)
    duration_finite = v.finite(split, enc.DOC_DURATION, 960, 880 + len(conditions) * 144)
    conditions.append(duration_finite)
    duration_nonnegative = v.double_math("GreaterEqual_DoubleDouble", 960, 880 + len(conditions) * 144, b_default="0.0")
    bp.connect(split, enc.DOC_DURATION, duration_nonnegative, "A")
    conditions.append(duration_nonnegative)

    combined = v.and_all(conditions, 1408, 560)
    valid_x = 1408 + len(conditions) * 224
    valid_set = b.setter("ScratchValidV1", "bool", valid_x, 0)
    bp.connect(combined, "ReturnValue", valid_set, "ScratchValidV1")
    ids = b.getter("ScratchIntegerArrayV1", "int", valid_x, 400, array=True)
    clear_waypoint_ids = b.array_clear("int", valid_x + 256, 0)
    bp.connect(ids, "ScratchIntegerArrayV1", clear_waypoint_ids, "TargetArray")
    duration_reset = b.setter("ScratchCalculatedDurationV1", "real", valid_x + 512, 0)
    enc.set_default(duration_reset, "ScratchCalculatedDurationV1", "0.0")
    waypoints = b.foreach("waypoint", valid_x + 768, 0)
    bp.connect(split, enc.DOC_WAYPOINTS, waypoints, "Array")
    stage_waypoint = b.setter("ScratchWaypointV1", "waypoint", valid_x + 1024, 0)
    validate_waypoint = b.call("ValidateWaypointV1", valid_x + 1280, 0)
    bp.connect(waypoints, "Array Element", stage_waypoint, "ScratchWaypointV1")

    clear_segment_ids = b.array_clear("int", valid_x + 1024, 480)
    bp.connect(ids, "ScratchIntegerArrayV1", clear_segment_ids, "TargetArray")
    segments = b.foreach("segment", valid_x + 1280, 480)
    bp.connect(split, enc.DOC_SEGMENTS, segments, "Array")
    stage_index = b.setter("ScratchIndexV1", "int", valid_x + 1536, 480)
    stage_segment = b.setter("ScratchSegmentV1", "segment", valid_x + 1792, 480)
    validate_segment = b.call("ValidateSegmentV1", valid_x + 2048, 480)
    bp.connect(segments, "Array Index", stage_index, "ScratchIndexV1")
    bp.connect(segments, "Array Element", stage_segment, "ScratchSegmentV1")

    calculated = b.getter("ScratchCalculatedDurationV1", "real", valid_x + 2304, 800)
    duration_equal = v.double_math("EqualEqual_DoubleDouble", valid_x + 2528, 800)
    bp.connect(calculated, "ScratchCalculatedDurationV1", duration_equal, "A")
    bp.connect(split, enc.DOC_DURATION, duration_equal, "B")
    prior_valid = b.getter("ScratchValidV1", "bool", valid_x + 2304, 960)
    final_and = v.bool_math("BooleanAND", valid_x + 2752, 800)
    bp.connect(prior_valid, "ScratchValidV1", final_and, "A")
    bp.connect(duration_equal, "ReturnValue", final_and, "B")
    final_set = b.setter("ScratchValidV1", "bool", valid_x + 2976, 480)
    bp.connect(final_and, "ReturnValue", final_set, "ScratchValidV1")

    bp.connect(v.entry, "then", valid_set, "execute")
    connect_exec(bp, [valid_set, clear_waypoint_ids, duration_reset])
    bp.connect(duration_reset, "then", waypoints, "Exec")
    bp.connect(waypoints, "LoopBody", stage_waypoint, "execute")
    bp.connect(stage_waypoint, "then", validate_waypoint, "execute")
    bp.connect(waypoints, "Completed", clear_segment_ids, "execute")
    bp.connect(clear_segment_ids, "then", segments, "Exec")
    bp.connect(segments, "LoopBody", stage_index, "execute")
    bp.connect(stage_index, "then", stage_segment, "execute")
    bp.connect(stage_segment, "then", validate_segment, "execute")
    bp.connect(segments, "Completed", final_set, "execute")
    return v.nodes


def record_scalar_conditions(v: ValidationBuilder):
    b = v.b
    conditions = []
    y = 480
    for variable in (
        "ScratchRecordFlypathIdV1", "ScratchRecordOwnerAccountIdV1", "ScratchRecordTitleV1",
        "ScratchRecordRegionIdV1", "ScratchRecordCreatedUtcV1", "ScratchRecordUpdatedUtcV1",
    ):
        getter = b.getter(variable, "string", 0, y)
        condition = v.string_math("NotEqual_StrStr", 256, y, b_default="")
        v.bp.connect(getter, variable, condition, "A")
        conditions.append(condition)
        y += 144
    visibility = b.getter("ScratchRecordVisibilityV1", "string", 0, y)
    private = v.string_math("EqualEqual_StrStr", 256, y, b_default="private")
    public = v.string_math("EqualEqual_StrStr", 256, y + 144, b_default="public")
    v.bp.connect(visibility, "ScratchRecordVisibilityV1", private, "A")
    v.bp.connect(visibility, "ScratchRecordVisibilityV1", public, "A")
    conditions.append(v.or_all([private, public], 480, y))

    draft = b.getter("ScratchRecordDraftDocumentV1", "document", 0, y + 320)
    break_draft = b.add("break_draft", "break_document", 256, y + 320)
    region = b.getter("ScratchRecordRegionIdV1", "string", 0, y + 560)
    draft_revision = b.getter("ScratchRecordDraftRevisionNumberV1", "int", 0, y + 704)
    region_equal = v.string_math("EqualEqual_StrStr", 480, y + 320)
    revision_equal = v.int_math("EqualEqual_IntInt", 480, y + 464)
    v.bp.connect(draft, "ScratchRecordDraftDocumentV1", break_draft, "ST_EDD_FlypathDocument")
    v.bp.connect(break_draft, v.enc.DOC_REGION, region_equal, "A")
    v.bp.connect(region, "ScratchRecordRegionIdV1", region_equal, "B")
    v.bp.connect(break_draft, v.enc.DOC_REVISION, revision_equal, "A")
    v.bp.connect(draft_revision, "ScratchRecordDraftRevisionNumberV1", revision_equal, "B")
    conditions.extend([region_equal, revision_equal])
    return conditions, draft, public


def build_record_published(bp, enc, templates):
    v = ValidationBuilder(bp, enc, templates, "ValidateRecordPublishedV1")
    b = v.b
    has_published = b.getter("ScratchRecordHasPublishedRevisionV1", "bool", 0, 360)
    branch = v.branch(256, 0)
    bp.connect(has_published, "ScratchRecordHasPublishedRevisionV1", branch, "Condition")
    bp.connect(v.entry, "then", branch, "execute")
    published = b.getter("ScratchRecordPublishedDocumentV1", "document", 512, 480)
    stage = b.setter("ScratchDocumentV1", "document", 512, 0)
    validate = b.call("ValidateDocumentV1", 768, 0)
    bp.connect(published, "ScratchRecordPublishedDocumentV1", stage, "ScratchDocumentV1")
    bp.connect(branch, "then", stage, "execute")
    bp.connect(stage, "then", validate, "execute")
    valid = b.getter("ScratchValidV1", "bool", 1024, 360)
    valid_branch = v.branch(1248, 0)
    bp.connect(valid, "ScratchValidV1", valid_branch, "Condition")
    bp.connect(validate, "then", valid_branch, "execute")

    break_published = b.add("break_published", "break_document", 1024, 560)
    bp.connect(published, "ScratchRecordPublishedDocumentV1", break_published, "ST_EDD_FlypathDocument")
    record_region = b.getter("ScratchRecordRegionIdV1", "string", 1024, 800)
    published_revision = b.getter("ScratchRecordPublishedRevisionNumberV1", "int", 1024, 944)
    draft_revision = b.getter("ScratchRecordDraftRevisionNumberV1", "int", 1024, 1088)
    region_equal = v.string_math("EqualEqual_StrStr", 1472, 560)
    revision_equal = v.int_math("EqualEqual_IntInt", 1472, 704)
    revision_order = v.int_math("LessEqual_IntInt", 1472, 848)
    bp.connect(break_published, enc.DOC_REGION, region_equal, "A")
    bp.connect(record_region, "ScratchRecordRegionIdV1", region_equal, "B")
    bp.connect(break_published, enc.DOC_REVISION, revision_equal, "A")
    bp.connect(published_revision, "ScratchRecordPublishedRevisionNumberV1", revision_equal, "B")
    bp.connect(published_revision, "ScratchRecordPublishedRevisionNumberV1", revision_order, "A")
    bp.connect(draft_revision, "ScratchRecordDraftRevisionNumberV1", revision_order, "B")
    combined = v.and_all([region_equal, revision_equal, revision_order], 1696, 560)
    store = b.setter("ScratchValidV1", "bool", 2368, 0)
    bp.connect(combined, "ReturnValue", store, "ScratchValidV1")
    bp.connect(valid_branch, "then", store, "execute")
    return v.nodes


def build_record_source(bp, enc, templates):
    v = ValidationBuilder(bp, enc, templates, "ValidateRecordSourceAttributionV1")
    b = v.b
    has_source = b.getter("ScratchRecordHasSourceAttributionV1", "bool", 0, 360)
    branch = v.branch(256, 0)
    bp.connect(has_source, "ScratchRecordHasSourceAttributionV1", branch, "Condition")
    bp.connect(v.entry, "then", branch, "execute")
    conditions = []
    y = 480
    for variable in ("ScratchRecordSourceFlypathIdV1", "ScratchRecordSourceTitleV1"):
        getter = b.getter(variable, "string", 512, y)
        nonempty = v.string_math("NotEqual_StrStr", 736, y, b_default="")
        bp.connect(getter, variable, nonempty, "A")
        conditions.append(nonempty)
        y += 144
    revision = b.getter("ScratchRecordSourceRevisionNumberV1", "int", 512, y)
    positive = v.int_math("Greater_IntInt", 736, y, b_default="0")
    bp.connect(revision, "ScratchRecordSourceRevisionNumberV1", positive, "A")
    conditions.append(positive)
    combined = v.and_all(conditions, 960, 480)
    store = b.setter("ScratchValidV1", "bool", 1632, 0)
    bp.connect(combined, "ReturnValue", store, "ScratchValidV1")
    bp.connect(branch, "then", store, "execute")
    return v.nodes


def build_record(bp, enc, templates):
    v = ValidationBuilder(bp, enc, templates, "ValidateRecordV1")
    b = v.b
    conditions, draft, visibility_public = record_scalar_conditions(v)
    combined = v.and_all(conditions, 960, 480)
    root_x = 960 + len(conditions) * 224
    root_set = b.setter("ScratchValidV1", "bool", root_x, 0)
    bp.connect(combined, "ReturnValue", root_set, "ScratchValidV1")
    root_branch = v.branch(root_x + 256, 0)
    root_valid = b.getter("ScratchValidV1", "bool", root_x + 256, 360)
    bp.connect(root_valid, "ScratchValidV1", root_branch, "Condition")
    stage_draft = b.setter("ScratchDocumentV1", "document", root_x + 512, 0)
    validate_draft = b.call("ValidateDocumentV1", root_x + 768, 0)
    bp.connect(draft, "ScratchRecordDraftDocumentV1", stage_draft, "ScratchDocumentV1")

    draft_valid = b.getter("ScratchValidV1", "bool", root_x + 1024, 360)
    draft_branch = v.branch(root_x + 1248, 0)
    bp.connect(draft_valid, "ScratchValidV1", draft_branch, "Condition")
    has_published = b.getter("ScratchRecordHasPublishedRevisionV1", "bool", root_x + 1024, 560)
    public_requirement = v.bool_math("BooleanOR", root_x + 1248, 560)
    not_public = v.bool_math("EqualEqual_BoolBool", root_x + 1024, 704)
    enc.set_default(not_public, "B", "false")
    bp.connect(visibility_public, "ReturnValue", not_public, "A")
    bp.connect(not_public, "ReturnValue", public_requirement, "A")
    bp.connect(has_published, "ScratchRecordHasPublishedRevisionV1", public_requirement, "B")
    publication_branch = v.branch(root_x + 1504, 0)
    bp.connect(public_requirement, "ReturnValue", publication_branch, "Condition")
    publication_invalid = b.setter("ScratchValidV1", "bool", root_x + 1760, -256)
    enc.set_default(publication_invalid, "ScratchValidV1", "false")
    validate_published = b.call("ValidateRecordPublishedV1", root_x + 1760, 0)
    published_valid = b.getter("ScratchValidV1", "bool", root_x + 2016, 360)
    published_branch = v.branch(root_x + 2240, 0)
    validate_source = b.call("ValidateRecordSourceAttributionV1", root_x + 2496, 0)
    bp.connect(published_valid, "ScratchValidV1", published_branch, "Condition")

    bp.connect(v.entry, "then", root_set, "execute")
    bp.connect(root_set, "then", root_branch, "execute")
    bp.connect(root_branch, "then", stage_draft, "execute")
    bp.connect(stage_draft, "then", validate_draft, "execute")
    bp.connect(validate_draft, "then", draft_branch, "execute")
    bp.connect(draft_branch, "then", publication_branch, "execute")
    bp.connect(publication_branch, "else", publication_invalid, "execute")
    bp.connect(publication_branch, "then", validate_published, "execute")
    bp.connect(validate_published, "then", published_branch, "execute")
    bp.connect(published_branch, "then", validate_source, "execute")
    return v.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    enc = load_encoder(args.project_root)
    bp = enc.load_helpers(args.project_root)
    templates = load_templates(args.project_root, bp, enc)
    graphs = {
        "validate-waypoint-v1.eddgraph": build_waypoint(bp, enc, templates),
        "validate-segment-v1.eddgraph": build_segment(bp, enc, templates),
        "validate-document-v1.eddgraph": build_document(bp, enc, templates),
        "validate-record-published-v1.eddgraph": build_record_published(bp, enc, templates),
        "validate-record-source-attribution-v1.eddgraph": build_record_source(bp, enc, templates),
        "validate-record-v1.eddgraph": build_record(bp, enc, templates),
    }
    for filename, nodes in graphs.items():
        enc.write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            enc.write(
                fold_paste_layout(nodes),
                args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"),
                paste=True,
            )


if __name__ == "__main__":
    main()
