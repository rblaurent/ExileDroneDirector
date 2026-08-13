"""Build selected-segment interpolation for the camera scalar-track engine."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

FUNCTION = "EvaluateCameraScalarTrackSegmentV1"
TARGET = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_scalar_segment_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, kind: str, array: bool = False) -> None:
    category, subcategory = {"bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double"), "string": ("string", "")}[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin, mutate)


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
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    activate = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({
        "length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "select": bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
        "call": bp.find_block(activate, r'MemberName="SwitchToDroneView"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0); builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        builder.nodes.append(node); return node

    def variable(node, name: str, kind: str, array: bool = False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y); variable(node, name, kind, array); return node

    def set_(name: str, kind: str, x: int, y: int, default: str | None = None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y); variable(node, name, kind)
        if default is not None: scalar.set_default(node, name, default)
        return node

    def length(source, source_pin: str, kind: str, x: int, y: int):
        node = add_form(f"length_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", kind, True); pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray"); return node

    def item(source, source_pin: str, kind: str, index, index_pin: str, x: int, y: int):
        node = add_form(f"item_{len(builder.nodes)}", "item", x, y)
        pin_kind(node, "Array", kind, True); pin_kind(node, "Output", kind); pin_kind(node, "Dimension 1", "int")
        bp.connect(source, source_pin, node, "Array"); bp.connect(index, index_pin, node, "Dimension 1"); return node

    def operation(member: str, left, left_pin: str | None, x: int, y: int, right=None, right_pin: str | None = None, default_a: str | None = None, default_b: str | None = None, kind: str = "real", result: str | None = None):
        output_kind = result or kind
        node = builder.add(f"op_{member}_{len(builder.nodes)}", "compare" if output_kind == "bool" else "math", x, y)
        scalar.retarget_function(node, member)
        input_kind = "bool" if member in ("BooleanAND", "BooleanOR") else kind
        pin_kind(node, "A", input_kind); pin_kind(node, "B", input_kind); pin_kind(node, "ReturnValue", output_kind)
        if left is None: scalar.set_default(node, "A", default_a)
        else: bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default_b)
        else: bp.connect(right, right_pin, node, "B")
        return node

    def and_all(values, x: int, y: int):
        current, current_pin = values[0]
        for index, (value, value_pin) in enumerate(values[1:]):
            current = operation("BooleanAND", current, current_pin, x + index * 208, y, value, value_pin, kind="bool", result="bool")
            current_pin = "ReturnValue"
        return current

    def equal_string(source, source_pin: str, expected: str, x: int, y: int):
        node = builder.equal_string(x, y, expected); bp.connect(source, source_pin, node, "A"); return node

    def select(condition, condition_pin: str, false_source, false_pin: str | None, true_source, true_pin: str | None, kind: str, x: int, y: int, false_default: str | None = None, true_default: str | None = None):
        node = add_form(f"select_{len(builder.nodes)}", "select", x, y)
        pin_kind(node, "Index", "bool")
        for pin in ("Option 0", "Option 1", "ReturnValue"): pin_kind(node, pin, kind)
        bp.connect(condition, condition_pin, node, "Index")
        if false_source is None: scalar.set_default(node, "Option 0", false_default)
        else: bp.connect(false_source, false_pin, node, "Option 0")
        if true_source is None: scalar.set_default(node, "Option 1", true_default)
        else: bp.connect(true_source, true_pin, node, "Option 1")
        return node

    def call(member: str, x: int, y: int):
        node = add_form(f"call_{member}_{len(builder.nodes)}", "call", x, y)
        node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET}", line, 1))
        return node

    compile_valid = get("CameraScalarTrackCompileValidV1", "bool", 0, 0)
    staged = get("CameraScalarTrackScratchValidV1", "bool", 0, 128)
    initial_valid = and_all([(compile_valid, "CameraScalarTrackCompileValidV1"), (staged, "CameraScalarTrackScratchValidV1")], 256, 64)
    initial_guard = builder.add("initial_guard", "branch", 512, 3200)
    bp.connect(builder.entry, "then", initial_guard, "execute"); bp.connect(initial_valid, "ReturnValue", initial_guard, "Condition")
    invalidate_stage = set_("CameraScalarTrackScratchValidV1", "bool", 736, 3200, "false")
    bp.connect(initial_guard, "then", invalidate_stage, "execute")

    index = get("CameraScalarTrackScratchIndexV1", "int", 0, 320)
    modes = get("CameraScalarTrackCandidateInterpolationModesV1", "string", 0, 448, True)
    mode_count = length(modes, "CameraScalarTrackCandidateInterpolationModesV1", "string", 256, 448)
    index_nonnegative = operation("GreaterEqual_IntInt", index, "CameraScalarTrackScratchIndexV1", 480, 320, default_b="0", kind="int", result="bool")
    index_bounded = operation("Less_IntInt", index, "CameraScalarTrackScratchIndexV1", 480, 448, mode_count, "ReturnValue", kind="int", result="bool")
    index_valid = and_all([(index_nonnegative, "ReturnValue"), (index_bounded, "ReturnValue")], 704, 384)
    index_guard = builder.add("index_guard", "branch", 960, 3200)
    bp.connect(invalidate_stage, "then", index_guard, "execute"); bp.connect(index_valid, "ReturnValue", index_guard, "Condition")

    times = get("CameraScalarTrackCandidateKeyTimesV1", "real", 0, 704, True)
    values = get("CameraScalarTrackCandidateDomainValuesV1", "real", 0, 832, True)
    arrives = get("CameraScalarTrackCandidateArriveTangentsV1", "real", 0, 960, True)
    leaves = get("CameraScalarTrackCandidateLeaveTangentsV1", "real", 0, 1088, True)
    next_index = operation("Add_IntInt", index, "CameraScalarTrackScratchIndexV1", 256, 1152, default_b="1", kind="int")
    left_time = item(times, "CameraScalarTrackCandidateKeyTimesV1", "real", index, "CameraScalarTrackScratchIndexV1", 480, 704)
    right_time = item(times, "CameraScalarTrackCandidateKeyTimesV1", "real", next_index, "ReturnValue", 480, 832)
    left_value = item(values, "CameraScalarTrackCandidateDomainValuesV1", "real", index, "CameraScalarTrackScratchIndexV1", 480, 960)
    right_value = item(values, "CameraScalarTrackCandidateDomainValuesV1", "real", next_index, "ReturnValue", 480, 1088)
    left_tangent = item(leaves, "CameraScalarTrackCandidateLeaveTangentsV1", "real", index, "CameraScalarTrackScratchIndexV1", 480, 1216)
    right_tangent = item(arrives, "CameraScalarTrackCandidateArriveTangentsV1", "real", next_index, "ReturnValue", 480, 1344)
    mode = item(modes, "CameraScalarTrackCandidateInterpolationModesV1", "string", index, "CameraScalarTrackScratchIndexV1", 480, 1472)
    query = get("CameraScalarTrackQueryTimeV1", "real", 0, 1472)
    span = operation("Subtract_DoubleDouble", right_time, "Output", 736, 704, left_time, "Output")
    offset = operation("Subtract_DoubleDouble", query, "CameraScalarTrackQueryTimeV1", 736, 832, left_time, "Output")
    raw_alpha = operation("Divide_DoubleDouble", offset, "ReturnValue", 960, 768, span, "ReturnValue")
    alpha = builder.clamp(raw_alpha, "ReturnValue", 1184, 768)
    delta = operation("Subtract_DoubleDouble", right_value, "Output", 736, 960, left_value, "Output")
    set_index = set_("CameraScalarTrackResultSegmentIndexV1", "int", 1184, 3200)
    set_alpha = set_("CameraScalarTrackResultLocalAlphaV1", "real", 1408, 3200)
    bp.connect(index_guard, "then", set_index, "execute"); bp.connect(index, "CameraScalarTrackScratchIndexV1", set_index, "CameraScalarTrackResultSegmentIndexV1")
    bp.connect(set_index, "then", set_alpha, "execute"); bp.connect(alpha, "ReturnValue", set_alpha, "CameraScalarTrackResultLocalAlphaV1")

    is_hold = equal_string(mode, "Output", "hold", 1184, 1152)
    is_linear = equal_string(mode, "Output", "linear", 1184, 1280)
    is_smooth = equal_string(mode, "Output", "smooth", 1184, 1408)
    is_cinematic = equal_string(mode, "Output", "cinematic", 1184, 1536)
    is_hermite = equal_string(mode, "Output", "hermite", 1184, 1664)
    profile_supported_left = operation("BooleanOR", is_linear, "ReturnValue", 1408, 1344, is_smooth, "ReturnValue", kind="bool", result="bool")
    profile_supported = operation("BooleanOR", profile_supported_left, "ReturnValue", 1616, 1408, is_cinematic, "ReturnValue", kind="bool", result="bool")
    hold_branch = builder.add("hold_branch", "branch", 1632, 3200)
    profile_branch = builder.add("profile_branch", "branch", 1856, 3360)
    hermite_branch = builder.add("hermite_branch", "branch", 2080, 3520)
    bp.connect(set_alpha, "then", hold_branch, "execute"); bp.connect(is_hold, "ReturnValue", hold_branch, "Condition")
    bp.connect(hold_branch, "else", profile_branch, "execute"); bp.connect(profile_supported, "ReturnValue", profile_branch, "Condition")
    bp.connect(profile_branch, "else", hermite_branch, "execute"); bp.connect(is_hermite, "ReturnValue", hermite_branch, "Condition")

    at_end = operation("GreaterEqual_DoubleDouble", alpha, "ReturnValue", 1408, 1024, default_b="1.0", result="bool")
    hold_value = select(at_end, "ReturnValue", left_value, "Output", right_value, "Output", "real", 1632, 1024)
    hold_set_value = set_("CameraScalarTrackScratchDomainValueV1", "real", 1856, 3040)
    hold_set_velocity = set_("CameraScalarTrackScratchDomainVelocityV1", "real", 2080, 3040, "0.0")
    hold_set_acceleration = set_("CameraScalarTrackScratchDomainAccelerationV1", "real", 2304, 3040, "0.0")
    hold_set_valid = set_("CameraScalarTrackScratchValidV1", "bool", 2528, 3040, "true")
    hold_publish = call("PublishCameraScalarTrackSampleV1", 2752, 3040)
    bp.connect(hold_branch, "then", hold_set_value, "execute"); bp.connect(hold_value, "ReturnValue", hold_set_value, "CameraScalarTrackScratchDomainValueV1")
    for left, right in zip((hold_set_value, hold_set_velocity, hold_set_acceleration, hold_set_valid), (hold_set_velocity, hold_set_acceleration, hold_set_valid, hold_publish)): bp.connect(left, "then", right, "execute")

    profile_first = select(is_smooth, "ReturnValue", None, None, None, None, "string", 1856, 1280, false_default="linear", true_default="smoothstep")
    profile_name = select(is_cinematic, "ReturnValue", profile_first, "ReturnValue", None, None, "string", 2080, 1408, true_default="smootherstep")
    set_profile = set_("TrajectoryInputProfileV1", "string", 2080, 3200)
    set_profile_alpha = set_("TrajectoryInputAlphaV1", "real", 2304, 3200)
    call_profile = call("EvaluateTimeProfileV1", 2528, 3200)
    profile_result_valid = get("TrajectoryResultValidV1", "bool", 2528, 1888)
    profile_result_guard = builder.add("profile_result_guard", "branch", 2752, 3200)
    bp.connect(profile_branch, "then", set_profile, "execute"); bp.connect(profile_name, "ReturnValue", set_profile, "TrajectoryInputProfileV1")
    bp.connect(set_profile, "then", set_profile_alpha, "execute"); bp.connect(alpha, "ReturnValue", set_profile_alpha, "TrajectoryInputAlphaV1")
    bp.connect(set_profile_alpha, "then", call_profile, "execute"); bp.connect(call_profile, "then", profile_result_guard, "execute"); bp.connect(profile_result_valid, "TrajectoryResultValidV1", profile_result_guard, "Condition")
    blend = get("TrajectoryResultValueV1", "real", 2528, 2016)
    u2 = operation("Multiply_DoubleDouble", alpha, "ReturnValue", 1856, 1792, alpha, "ReturnValue")
    u3 = operation("Multiply_DoubleDouble", u2, "ReturnValue", 2080, 1792, alpha, "ReturnValue")
    u4 = operation("Multiply_DoubleDouble", u3, "ReturnValue", 2304, 1792, alpha, "ReturnValue")
    six_u = operation("Multiply_DoubleDouble", alpha, "ReturnValue", 1856, 1952, default_b="6.0")
    six_u2 = operation("Multiply_DoubleDouble", u2, "ReturnValue", 2080, 1952, default_b="6.0")
    smooth_d1 = operation("Subtract_DoubleDouble", six_u, "ReturnValue", 2304, 1952, six_u2, "ReturnValue")
    twelve_u = operation("Multiply_DoubleDouble", alpha, "ReturnValue", 1856, 2112, default_b="12.0")
    smooth_d2 = operation("Subtract_DoubleDouble", None, None, 2304, 2112, twelve_u, "ReturnValue", default_a="6.0")
    thirty_u2 = operation("Multiply_DoubleDouble", u2, "ReturnValue", 2528, 1792, default_b="30.0")
    sixty_u3 = operation("Multiply_DoubleDouble", u3, "ReturnValue", 2528, 1952, default_b="60.0")
    thirty_u4 = operation("Multiply_DoubleDouble", u4, "ReturnValue", 2528, 2112, default_b="30.0")
    cine_d1_left = operation("Subtract_DoubleDouble", thirty_u2, "ReturnValue", 2752, 1856, sixty_u3, "ReturnValue")
    cine_d1 = operation("Add_DoubleDouble", cine_d1_left, "ReturnValue", 2976, 1856, thirty_u4, "ReturnValue")
    sixty_u = operation("Multiply_DoubleDouble", alpha, "ReturnValue", 2528, 2272, default_b="60.0")
    one_eighty_u2 = operation("Multiply_DoubleDouble", u2, "ReturnValue", 2528, 2432, default_b="180.0")
    one_twenty_u3 = operation("Multiply_DoubleDouble", u3, "ReturnValue", 2528, 2592, default_b="120.0")
    cine_d2_left = operation("Subtract_DoubleDouble", sixty_u, "ReturnValue", 2752, 2352, one_eighty_u2, "ReturnValue")
    cine_d2 = operation("Add_DoubleDouble", cine_d2_left, "ReturnValue", 2976, 2352, one_twenty_u3, "ReturnValue")
    profile_d1_first = select(is_smooth, "ReturnValue", None, None, smooth_d1, "ReturnValue", "real", 3200, 1952, false_default="1.0")
    profile_d1 = select(is_cinematic, "ReturnValue", profile_d1_first, "ReturnValue", cine_d1, "ReturnValue", "real", 3424, 1952)
    profile_d2_first = select(is_smooth, "ReturnValue", None, None, smooth_d2, "ReturnValue", "real", 3200, 2272, false_default="0.0")
    profile_d2 = select(is_cinematic, "ReturnValue", profile_d2_first, "ReturnValue", cine_d2, "ReturnValue", "real", 3424, 2272)
    value_delta = operation("Multiply_DoubleDouble", delta, "ReturnValue", 3648, 1792, blend, "TrajectoryResultValueV1")
    profile_value = operation("Add_DoubleDouble", left_value, "Output", 3872, 1792, value_delta, "ReturnValue")
    velocity_u = operation("Multiply_DoubleDouble", delta, "ReturnValue", 3648, 1952, profile_d1, "ReturnValue")
    profile_velocity = operation("Divide_DoubleDouble", velocity_u, "ReturnValue", 3872, 1952, span, "ReturnValue")
    span_squared = operation("Multiply_DoubleDouble", span, "ReturnValue", 3648, 2272, span, "ReturnValue")
    acceleration_u = operation("Multiply_DoubleDouble", delta, "ReturnValue", 3872, 2272, profile_d2, "ReturnValue")
    profile_acceleration = operation("Divide_DoubleDouble", acceleration_u, "ReturnValue", 4096, 2272, span_squared, "ReturnValue")
    profile_set_value = set_("CameraScalarTrackScratchDomainValueV1", "real", 4320, 3200)
    profile_set_velocity = set_("CameraScalarTrackScratchDomainVelocityV1", "real", 4544, 3200)
    profile_set_acceleration = set_("CameraScalarTrackScratchDomainAccelerationV1", "real", 4768, 3200)
    profile_set_valid = set_("CameraScalarTrackScratchValidV1", "bool", 4992, 3200, "true")
    profile_publish = call("PublishCameraScalarTrackSampleV1", 5216, 3200)
    bp.connect(profile_result_guard, "then", profile_set_value, "execute"); bp.connect(profile_value, "ReturnValue", profile_set_value, "CameraScalarTrackScratchDomainValueV1")
    bp.connect(profile_set_value, "then", profile_set_velocity, "execute"); bp.connect(profile_velocity, "ReturnValue", profile_set_velocity, "CameraScalarTrackScratchDomainVelocityV1")
    bp.connect(profile_set_velocity, "then", profile_set_acceleration, "execute"); bp.connect(profile_acceleration, "ReturnValue", profile_set_acceleration, "CameraScalarTrackScratchDomainAccelerationV1")
    bp.connect(profile_set_acceleration, "then", profile_set_valid, "execute"); bp.connect(profile_set_valid, "then", profile_publish, "execute")

    v0u = operation("Multiply_DoubleDouble", left_tangent, "Output", 2304, 2592, span, "ReturnValue")
    v1u = operation("Multiply_DoubleDouble", right_tangent, "Output", 2304, 2720, span, "ReturnValue")
    six_delta = operation("Multiply_DoubleDouble", delta, "ReturnValue", 2528, 2720, default_b="6.0")
    four_v0 = operation("Multiply_DoubleDouble", v0u, "ReturnValue", 2528, 2848, default_b="4.0")
    two_v1 = operation("Multiply_DoubleDouble", v1u, "ReturnValue", 2528, 2976, default_b="2.0")
    a0_left = operation("Subtract_DoubleDouble", six_delta, "ReturnValue", 2752, 2784, four_v0, "ReturnValue")
    a0u = operation("Subtract_DoubleDouble", a0_left, "ReturnValue", 2976, 2784, two_v1, "ReturnValue")
    neg_six_delta = operation("Multiply_DoubleDouble", delta, "ReturnValue", 2528, 3104, default_b="-6.0")
    two_v0 = operation("Multiply_DoubleDouble", v0u, "ReturnValue", 2752, 3104, default_b="2.0")
    four_v1 = operation("Multiply_DoubleDouble", v1u, "ReturnValue", 2752, 3232, default_b="4.0")
    a1_left = operation("Add_DoubleDouble", neg_six_delta, "ReturnValue", 2976, 3104, two_v0, "ReturnValue")
    a1u = operation("Add_DoubleDouble", a1_left, "ReturnValue", 3200, 3104, four_v1, "ReturnValue")
    quintic_inputs = (
        ("TrajectoryInputAlphaV1", alpha, "ReturnValue"),
        ("TrajectoryInputStartValueV1", left_value, "Output"),
        ("TrajectoryInputStartVelocityUV1", v0u, "ReturnValue"),
        ("TrajectoryInputStartAccelerationUV1", a0u, "ReturnValue"),
        ("TrajectoryInputEndValueV1", right_value, "Output"),
        ("TrajectoryInputEndVelocityUV1", v1u, "ReturnValue"),
        ("TrajectoryInputEndAccelerationUV1", a1u, "ReturnValue"),
    )
    quintic_setters = []
    for offset_index, (name, source, source_pin) in enumerate(quintic_inputs):
        setter = set_(name, "real", 2304 + offset_index * 224, 3680)
        bp.connect(source, source_pin, setter, name); quintic_setters.append(setter)
    call_quintic = call("EvaluateQuinticScalarV1", 3872, 3680)
    quintic_valid = get("TrajectoryResultValidV1", "bool", 3872, 3424)
    quintic_guard = builder.add("quintic_guard", "branch", 4096, 3680)
    bp.connect(hermite_branch, "then", quintic_setters[0], "execute")
    for left, right in zip(quintic_setters, quintic_setters[1:] + [call_quintic]): bp.connect(left, "then", right, "execute")
    bp.connect(call_quintic, "then", quintic_guard, "execute"); bp.connect(quintic_valid, "TrajectoryResultValidV1", quintic_guard, "Condition")
    quintic_value = get("TrajectoryResultValueV1", "real", 4096, 3424)
    quintic_d1 = get("TrajectoryResultDerivativeUV1", "real", 4096, 3488)
    quintic_d2 = get("TrajectoryResultSecondDerivativeUV1", "real", 4096, 3552)
    hermite_velocity = operation("Divide_DoubleDouble", quintic_d1, "TrajectoryResultDerivativeUV1", 4320, 3488, span, "ReturnValue")
    hermite_acceleration = operation("Divide_DoubleDouble", quintic_d2, "TrajectoryResultSecondDerivativeUV1", 4320, 3552, span_squared, "ReturnValue")
    hermite_set_value = set_("CameraScalarTrackScratchDomainValueV1", "real", 4320, 3680)
    hermite_set_velocity = set_("CameraScalarTrackScratchDomainVelocityV1", "real", 4544, 3680)
    hermite_set_acceleration = set_("CameraScalarTrackScratchDomainAccelerationV1", "real", 4768, 3680)
    hermite_set_valid = set_("CameraScalarTrackScratchValidV1", "bool", 4992, 3680, "true")
    hermite_publish = call("PublishCameraScalarTrackSampleV1", 5216, 3680)
    bp.connect(quintic_guard, "then", hermite_set_value, "execute"); bp.connect(quintic_value, "TrajectoryResultValueV1", hermite_set_value, "CameraScalarTrackScratchDomainValueV1")
    bp.connect(hermite_set_value, "then", hermite_set_velocity, "execute"); bp.connect(hermite_velocity, "ReturnValue", hermite_set_velocity, "CameraScalarTrackScratchDomainVelocityV1")
    bp.connect(hermite_set_velocity, "then", hermite_set_acceleration, "execute"); bp.connect(hermite_acceleration, "ReturnValue", hermite_set_acceleration, "CameraScalarTrackScratchDomainAccelerationV1")
    bp.connect(hermite_set_acceleration, "then", hermite_set_valid, "execute"); bp.connect(hermite_set_valid, "then", hermite_publish, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
