"""Build non-authoritative join diagnostics after accepted document adaptation."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildAirframeDocumentDiscontinuityDiagnosticsV2"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
RAD_TO_DEG = "57.29577951308232"
OUTPUTS = (
    ("AirframeDocumentDiagnosticWaypointIdsV2", "int"),
    ("AirframeDocumentDiagnosticPositionVelocityJumpsV2", "real"),
    ("AirframeDocumentDiagnosticPositionAccelerationJumpsV2", "real"),
    ("AirframeDocumentDiagnosticBodyAngularRateJumpsV2", "real"),
    ("AirframeDocumentDiagnosticGimbalAngularRateJumpsV2", "real"),
    ("AirframeDocumentDiagnosticDiscontinuousFlagsV2", "bool"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_document_diagnostics_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-document-source-adapter-v2.eddgraph")
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    translation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-translation-input.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"K2Node_MacroInstance"),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "vsize": bp.find_block(native, r'MemberName="VSize"'),
        "make_vector": bp.find_block(marker, r'MemberName="MakeVector"'),
        "vector_math": bp.find_block(translation, r'MemberName="Multiply_VectorVector"'),
        "select": bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
        "self_call": bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind in ("vector", "quat") else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, value=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind)
        if value is not None:
            scalar.set_default(node, name, value)
        return node

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0)
        b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        b.nodes.append(node)
        return node

    def retarget(node, member, kinds):
        scalar.retarget_function(node, member)
        for pin, kind in kinds.items():
            pin_kind(node, pin, kind)
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def math(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, kind="real"):
        node = b.math("Add_DoubleDouble", x, y)
        retarget(node, member, {"A": kind, "B": kind, "ReturnValue": kind})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default_b)
        return node

    def boolop(member, left, left_pin, right, right_pin, x, y):
        return compare(member, left, left_pin, x, y, right, right_pin, kind="bool")

    def array_clear(source, source_pin, kind, x, y):
        node = add_form(f"clear_{source_pin}_{len(b.nodes)}", "array_clear", x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def array_add(target, target_pin, kind, value, value_pin, x, y, default=None):
        node = add_form(f"append_{target_pin}_{len(b.nodes)}", "array_add", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "NewItem", kind)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(target, target_pin, node, "TargetArray")
        if value is None:
            scalar.set_default(node, "NewItem", default)
        else:
            bp.connect(value, value_pin, node, "NewItem")
        return node

    def foreach(source, source_pin, kind, x, y):
        node = add_form(f"foreach_{len(b.nodes)}", "foreach", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Array Element", kind)
        pin_kind(node, "Array Index", "int")
        bp.connect(source, source_pin, node, "Array")
        return node

    def length(source, source_pin, kind, x, y):
        node = add_form(f"length_{len(b.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = add_form(f"item_{source_pin}_{len(b.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True)
        pin_kind(node, "Output", kind)
        bp.connect(source, source_pin, node, "Array")
        bp.connect(index, index_pin, node, "Dimension 1")
        return node

    def vector_math(member, left, left_pin, right, right_pin, x, y):
        node = add_form(f"{member}_{len(b.nodes)}", "vector_math", x, y)
        retarget(node, member, {"A": "vector", "B": "vector", "ReturnValue": "vector"})
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def uniform_vector(value, value_pin, x, y):
        node = add_form(f"uniform_{len(b.nodes)}", "make_vector", x, y)
        for axis in "XYZ":
            pin_kind(node, axis, "real")
            bp.connect(value, value_pin, node, axis)
        pin_kind(node, "ReturnValue", "vector")
        return node

    def vsize(value, value_pin, x, y):
        node = add_form(f"vsize_{len(b.nodes)}", "vsize", x, y)
        bp.connect(value, value_pin, node, "A")
        return node

    def select_vector(condition, false_value, false_pin, true_value, true_pin, x, y):
        node = add_form(f"select_{len(b.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"):
            pin_kind(node, pin, "vector")
        pin_kind(node, "Index", "bool")
        bp.connect(condition, "ReturnValue", node, "Index")
        bp.connect(false_value, false_pin, node, "Option 0")
        bp.connect(true_value, true_pin, node, "Option 1")
        return node

    def call(member, x, y):
        node = add_form(f"call_{member}_{len(b.nodes)}", "self_call", x, y)
        node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET}", line, 1))
        return node

    outputs = {name: get(name, kind, 0, index * 144, True) for index, (name, kind) in enumerate(OUTPUTS)}
    clears = [array_clear(outputs[name], name, kind, 256 + index * 224, 3520) for index, (name, kind) in enumerate(OUTPUTS)]
    bp.connect(b.entry, "then", clears[0], "execute")
    for left, right in zip(clears, clears[1:]):
        bp.connect(left, "then", right, "execute")
    reset_count = set_("AirframeDocumentDiagnosticCountV2", "int", 1600, 3520, "0")
    reset_valid = set_("AirframeDocumentDiagnosticsValidV2", "bool", 1824, 3520, "false")
    reset_stage = set_("AirframeDocumentDiagnosticStageValidV2", "bool", 2048, 3520, "false")
    reset_body_left = set_("AirframeDocumentDiagnosticScratchBodyLeftRateV2", "vector", 2272, 3520, "0, 0, 0")
    reset_gimbal_left = set_("AirframeDocumentDiagnosticScratchGimbalLeftRateV2", "vector", 2496, 3520, "0, 0, 0")
    reset_body_jump = set_("AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2", "real", 2720, 3520, "0.0")
    bp.connect(clears[-1], "then", reset_count, "execute")
    for left, right in zip((reset_count, reset_valid, reset_stage, reset_body_left, reset_gimbal_left), (reset_valid, reset_stage, reset_body_left, reset_gimbal_left, reset_body_jump)):
        bp.connect(left, "then", right, "execute")

    adapter = get("AirframeDocumentAdapterCompileValidV2", "bool", 0, 1120)
    velocity_threshold = get("AirframeDocumentDiagnosticPositionVelocityThresholdV2", "real", 0, 1280)
    acceleration_threshold = get("AirframeDocumentDiagnosticPositionAccelerationThresholdV2", "real", 0, 1440)
    angular_threshold = get("AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2", "real", 0, 1600)
    threshold_conditions = [adapter]
    for index, threshold in enumerate((velocity_threshold, acceleration_threshold, angular_threshold)):
        name = ("AirframeDocumentDiagnosticPositionVelocityThresholdV2", "AirframeDocumentDiagnosticPositionAccelerationThresholdV2", "AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2")[index]
        finite = b.finite(threshold, name, 256, 1120 + index * 240)
        nonnegative = compare("GreaterEqual_DoubleDouble", threshold, name, 480, 1120 + index * 240, default_b="0.0")
        threshold_conditions.append(boolop("BooleanAND", finite, "ReturnValue", nonnegative, "ReturnValue", 704, 1120 + index * 240))
    valid_thresholds = boolop("BooleanAND", adapter, "AirframeDocumentAdapterCompileValidV2", threshold_conditions[1], "ReturnValue", 928, 1120)
    valid_thresholds = boolop("BooleanAND", valid_thresholds, "ReturnValue", threshold_conditions[2], "ReturnValue", 1152, 1240)
    valid_thresholds = boolop("BooleanAND", valid_thresholds, "ReturnValue", threshold_conditions[3], "ReturnValue", 1376, 1360)
    outer = b.add("outer_guard", "branch", 2944, 3520)
    bp.connect(reset_body_jump, "then", outer, "execute")
    bp.connect(valid_thresholds, "ReturnValue", outer, "Condition")
    accept_stage = set_("AirframeDocumentDiagnosticStageValidV2", "bool", 3168, 3520, "true")
    bp.connect(outer, "then", accept_stage, "execute")

    waypoint_ids = get("AirframeDocumentInputWaypointIdsV2", "int", 0, 1920, True)
    positions = get("PositionRouteCompiledWaypointPositionsV1", "vector", 0, 2080, True)
    durations = get("PositionRouteCompiledDurationsV1", "real", 0, 2240, True)
    curves = get("PositionRouteCompiledSpatialCurveTypesV1", "string", 0, 2400, True)
    velocities = get("PositionRouteCompiledWaypointVelocitiesV1", "vector", 0, 2560, True)
    body = get("AirframeDocumentInputWaypointBodyQuatsV2", "quat", 0, 2720, True)
    gimbal = get("AirframeDocumentInputWaypointGimbalQuatsV2", "quat", 0, 2880, True)
    loop = foreach(waypoint_ids, "AirframeDocumentInputWaypointIdsV2", "int", 3392, 3520)
    bp.connect(accept_stage, "then", loop, "Exec")
    count = length(waypoint_ids, "AirframeDocumentInputWaypointIdsV2", "int", 3392, 1920)
    last = math("Subtract_IntInt", count, "ReturnValue", 3616, 1920, default_b="1", kind="int")
    after_first = compare("Greater_IntInt", loop, "Array Index", 3616, 2080, default_b="0", kind="int")
    before_last = compare("Less_IntInt", loop, "Array Index", 3616, 2240, last, "ReturnValue", kind="int")
    internal = boolop("BooleanAND", after_first, "ReturnValue", before_last, "ReturnValue", 3840, 2160)
    stage = get("AirframeDocumentDiagnosticStageValidV2", "bool", 3616, 2400)
    active = boolop("BooleanAND", stage, "AirframeDocumentDiagnosticStageValidV2", internal, "ReturnValue", 4064, 2240)
    inner = b.add("inner_guard", "branch", 4288, 3520)
    bp.connect(loop, "LoopBody", inner, "execute")
    bp.connect(active, "ReturnValue", inner, "Condition")

    previous = math("Subtract_IntInt", loop, "Array Index", 4512, 1920, default_b="1", kind="int")
    following = math("Add_IntInt", loop, "Array Index", 4512, 2080, default_b="1", kind="int")
    p_previous = item(positions, "PositionRouteCompiledWaypointPositionsV1", "vector", previous, "ReturnValue", 4736, 1600)
    p_current = item(positions, "PositionRouteCompiledWaypointPositionsV1", "vector", loop, "Array Index", 4736, 1760)
    p_following = item(positions, "PositionRouteCompiledWaypointPositionsV1", "vector", following, "ReturnValue", 4736, 1920)
    duration_left = item(durations, "PositionRouteCompiledDurationsV1", "real", previous, "ReturnValue", 4736, 2080)
    duration_right = item(durations, "PositionRouteCompiledDurationsV1", "real", loop, "Array Index", 4736, 2240)
    curve_left = item(curves, "PositionRouteCompiledSpatialCurveTypesV1", "string", previous, "ReturnValue", 4736, 2400)
    curve_right = item(curves, "PositionRouteCompiledSpatialCurveTypesV1", "string", loop, "Array Index", 4736, 2560)
    compiled_velocity = item(velocities, "PositionRouteCompiledWaypointVelocitiesV1", "vector", loop, "Array Index", 4736, 2720)
    left_delta = vector_math("Subtract_VectorVector", p_current, "Output", p_previous, "Output", 4992, 1680)
    right_delta = vector_math("Subtract_VectorVector", p_following, "Output", p_current, "Output", 4992, 1920)
    left_duration_vector = uniform_vector(duration_left, "Output", 4992, 2160)
    right_duration_vector = uniform_vector(duration_right, "Output", 4992, 2320)
    left_secant = vector_math("Divide_VectorVector", left_delta, "ReturnValue", left_duration_vector, "ReturnValue", 5248, 1760)
    right_secant = vector_math("Divide_VectorVector", right_delta, "ReturnValue", right_duration_vector, "ReturnValue", 5248, 2000)
    left_linear = b.equal_string(5248, 2400, "linear")
    right_linear = b.equal_string(5248, 2560, "linear")
    bp.connect(curve_left, "Output", left_linear, "A")
    bp.connect(curve_right, "Output", right_linear, "A")
    left_velocity = select_vector(left_linear, compiled_velocity, "Output", left_secant, "ReturnValue", 5472, 1840)
    right_velocity = select_vector(right_linear, compiled_velocity, "Output", right_secant, "ReturnValue", 5472, 2080)
    velocity_delta = vector_math("Subtract_VectorVector", right_velocity, "ReturnValue", left_velocity, "ReturnValue", 5696, 1960)
    velocity_jump = vsize(velocity_delta, "ReturnValue", 5920, 1960)

    q_body_previous = item(body, "AirframeDocumentInputWaypointBodyQuatsV2", "quat", previous, "ReturnValue", 4736, 2880)
    q_body_current = item(body, "AirframeDocumentInputWaypointBodyQuatsV2", "quat", loop, "Array Index", 4736, 3040)
    q_body_following = item(body, "AirframeDocumentInputWaypointBodyQuatsV2", "quat", following, "ReturnValue", 4736, 3200)
    q_gimbal_previous = item(gimbal, "AirframeDocumentInputWaypointGimbalQuatsV2", "quat", previous, "ReturnValue", 4992, 2880)
    q_gimbal_current = item(gimbal, "AirframeDocumentInputWaypointGimbalQuatsV2", "quat", loop, "Array Index", 4992, 3040)
    q_gimbal_following = item(gimbal, "AirframeDocumentInputWaypointGimbalQuatsV2", "quat", following, "ReturnValue", 4992, 3200)

    primitive_result = get("OrientationResultDeltaVectorV1", "vector", 6144, 1600)
    primitive_valid = get("OrientationResultValidV1", "bool", 6144, 1760)

    def primitive_stage(label, start_value, end_value, duration_value, exec_source, exec_pin, x, y, store_name=None):
        set_start = set_("OrientationInputStartQuatV1", "quat", x, y)
        set_end = set_("OrientationInputEndQuatV1", "quat", x + 224, y)
        primitive = call("ComputeOrientationLogDeltaV1", x + 448, y)
        guard = b.add(f"{label}_guard", "branch", x + 672, y)
        reject = set_("AirframeDocumentDiagnosticStageValidV2", "bool", x + 896, y + 160, "false")
        bp.connect(exec_source, exec_pin, set_start, "execute")
        bp.connect(start_value, "Output", set_start, "OrientationInputStartQuatV1")
        bp.connect(set_start, "then", set_end, "execute")
        bp.connect(end_value, "Output", set_end, "OrientationInputEndQuatV1")
        bp.connect(set_end, "then", primitive, "execute")
        bp.connect(primitive, "then", guard, "execute")
        bp.connect(primitive_valid, "OrientationResultValidV1", guard, "Condition")
        bp.connect(guard, "else", reject, "execute")
        duration_vector = uniform_vector(duration_value, "Output", x + 672, y - 240)
        rate = vector_math("Divide_VectorVector", primitive_result, "OrientationResultDeltaVectorV1", duration_vector, "ReturnValue", x + 896, y - 240)
        if store_name is None:
            return guard, rate
        store = set_(store_name, "vector", x + 896, y)
        bp.connect(rate, "ReturnValue", store, store_name)
        bp.connect(guard, "then", store, "execute")
        return store, rate

    body_left_exec, _ = primitive_stage("body_left", q_body_previous, q_body_current, duration_left, inner, "then", 6144, 3520, "AirframeDocumentDiagnosticScratchBodyLeftRateV2")
    body_right_guard, body_right_rate = primitive_stage("body_right", q_body_current, q_body_following, duration_right, body_left_exec, "then", 7264, 3520)
    body_left_rate = get("AirframeDocumentDiagnosticScratchBodyLeftRateV2", "vector", 8160, 2880)
    body_rate_delta = vector_math("Subtract_VectorVector", body_right_rate, "ReturnValue", body_left_rate, "AirframeDocumentDiagnosticScratchBodyLeftRateV2", 8384, 2880)
    body_rate_radians = vsize(body_rate_delta, "ReturnValue", 8608, 2880)
    body_rate_degrees = math("Multiply_DoubleDouble", body_rate_radians, "ReturnValue", 8832, 2880, default_b=RAD_TO_DEG)
    store_body_jump = set_("AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2", "real", 9056, 3520)
    bp.connect(body_rate_degrees, "ReturnValue", store_body_jump, "AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2")
    bp.connect(body_right_guard, "then", store_body_jump, "execute")

    gimbal_left_exec, _ = primitive_stage("gimbal_left", q_gimbal_previous, q_gimbal_current, duration_left, store_body_jump, "then", 9280, 3520, "AirframeDocumentDiagnosticScratchGimbalLeftRateV2")
    gimbal_right_guard, gimbal_right_rate = primitive_stage("gimbal_right", q_gimbal_current, q_gimbal_following, duration_right, gimbal_left_exec, "then", 10400, 3520)
    gimbal_left_rate = get("AirframeDocumentDiagnosticScratchGimbalLeftRateV2", "vector", 11296, 2880)
    gimbal_rate_delta = vector_math("Subtract_VectorVector", gimbal_right_rate, "ReturnValue", gimbal_left_rate, "AirframeDocumentDiagnosticScratchGimbalLeftRateV2", 11520, 2880)
    gimbal_rate_radians = vsize(gimbal_rate_delta, "ReturnValue", 11744, 2880)
    gimbal_rate_degrees = math("Multiply_DoubleDouble", gimbal_rate_radians, "ReturnValue", 11968, 2880, default_b=RAD_TO_DEG)
    body_jump = get("AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2", "real", 11968, 3040)

    velocity_bad = compare("Greater_DoubleDouble", velocity_jump, "ReturnValue", 12192, 2400, velocity_threshold, "AirframeDocumentDiagnosticPositionVelocityThresholdV2")
    acceleration_bad = compare("Greater_DoubleDouble", reset_body_jump, "Output_Get", 12192, 2560, acceleration_threshold, "AirframeDocumentDiagnosticPositionAccelerationThresholdV2")
    body_bad = compare("Greater_DoubleDouble", body_jump, "AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2", 12192, 2720, angular_threshold, "AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2")
    gimbal_bad = compare("Greater_DoubleDouble", gimbal_rate_degrees, "ReturnValue", 12192, 2880, angular_threshold, "AirframeDocumentDiagnosticAuthoredAngularRateThresholdV2")
    any_bad = boolop("BooleanOR", velocity_bad, "ReturnValue", acceleration_bad, "ReturnValue", 12416, 2480)
    any_bad = boolop("BooleanOR", any_bad, "ReturnValue", body_bad, "ReturnValue", 12640, 2600)
    any_bad = boolop("BooleanOR", any_bad, "ReturnValue", gimbal_bad, "ReturnValue", 12864, 2720)

    appends = [
        array_add(outputs[OUTPUTS[0][0]], OUTPUTS[0][0], "int", loop, "Array Element", 12192, 3520),
        array_add(outputs[OUTPUTS[1][0]], OUTPUTS[1][0], "real", velocity_jump, "ReturnValue", 12416, 3520),
        array_add(outputs[OUTPUTS[2][0]], OUTPUTS[2][0], "real", None, "", 12640, 3520, "0.0"),
        array_add(outputs[OUTPUTS[3][0]], OUTPUTS[3][0], "real", body_jump, "AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2", 12864, 3520),
        array_add(outputs[OUTPUTS[4][0]], OUTPUTS[4][0], "real", gimbal_rate_degrees, "ReturnValue", 13088, 3520),
        array_add(outputs[OUTPUTS[5][0]], OUTPUTS[5][0], "bool", any_bad, "ReturnValue", 13312, 3520),
    ]
    bp.connect(gimbal_right_guard, "then", appends[0], "execute")
    for left, right in zip(appends, appends[1:]):
        bp.connect(left, "then", right, "execute")
    flagged = b.add("flagged_branch", "branch", 13536, 3520)
    bp.connect(appends[-1], "then", flagged, "execute")
    bp.connect(any_bad, "ReturnValue", flagged, "Condition")
    diagnostic_count = get("AirframeDocumentDiagnosticCountV2", "int", 13536, 3040)
    increment = math("Add_IntInt", diagnostic_count, "AirframeDocumentDiagnosticCountV2", 13760, 3040, default_b="1", kind="int")
    store_count = set_("AirframeDocumentDiagnosticCountV2", "int", 13760, 3520)
    bp.connect(increment, "ReturnValue", store_count, "AirframeDocumentDiagnosticCountV2")
    bp.connect(flagged, "then", store_count, "execute")

    final_stage = get("AirframeDocumentDiagnosticStageValidV2", "bool", 14016, 3200)
    complete = b.add("complete_guard", "branch", 14016, 3840)
    bp.connect(loop, "Completed", complete, "execute")
    bp.connect(final_stage, "AirframeDocumentDiagnosticStageValidV2", complete, "Condition")
    publish = set_("AirframeDocumentDiagnosticsValidV2", "bool", 14240, 3840, "true")
    bp.connect(complete, "then", publish, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body_nodes = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body_nodes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
