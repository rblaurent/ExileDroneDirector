"""Build bounded local-look and complete operator-frame candidates."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCameraOperatorLookV1"
VECTOR_EPSILON = "1e-9"
SETTLE_ANGLE = "0.00001"
SETTLE_SPEED = "0.0001"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_operator_look_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, kind: str) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', 'PinType.ContainerType=None', line, 1)
    node.mutate_pin(pin, mutate)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    orientation = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    quat_native = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    break_quat = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-break-quat-node-form.eddgraph")
    airframe = bp.read_blocks(args.project_root / "tools/blueprint/templates/airframe-gimbal-native-node-forms.eddgraph")
    position = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-compiled-position-route-v1.eddgraph")
    velocity = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/compute-position-route-velocities-v1.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    source_samples = bp.read_blocks(args.project_root / "tools/blueprint/snippets/build-airframe-source-position-body-profile-samples-v1.eddgraph")
    bool_forms = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-roll-and-horizon-input.eddgraph")
    forms.update(
        select=bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
        make_vector=bp.find_block(velocity, r'MemberName="MakeVector"'),
        break_vector=bp.find_block(bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph"), r'MemberName="BreakVector"'),
        vector_add=bp.find_block(position, r'MemberName="Add_VectorVector"'),
        vector_subtract=bp.find_block(position, r'MemberName="Subtract_VectorVector"'),
        vector_multiply=bp.find_block(position, r'MemberName="Multiply_VectorVector"'),
        vsize=bp.find_block(orientation, r'MemberName="VSize"'),
        normal=bp.find_block(airframe, r'MemberName="Normal"'),
        quat_multiply=bp.find_block(orientation, r'MemberName="Multiply_QuatQuat"'),
        quat_normalized=bp.find_block(quat_native, r'MemberName="Quat_Normalized"'),
        break_quat=bp.find_block(break_quat, r'MemberName="BreakQuat"'),
        quat_set=bp.find_block(orientation, r'MemberName="Quat_SetComponents"'),
        minimum=bp.find_block(source_samples, r'MemberName="FMin"'),
        bool_not=bp.find_block(bool_forms, r'MemberName="Not_PreBool"'),
        clamp=bp.find_block(bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph"), r'MemberName="FClamp"'),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def variable(node, name: str, kind: str) -> None:
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else kind); pin_kind(node, name, kind)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)
    def get(name: str, kind: str, x: int, y: int):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind); return node
    def set_(name: str, kind: str, x: int, y: int, source=None, source_pin: str | None = None, default: str | None = None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind)
        if source is not None: bp.connect(source, source_pin, node, name)
        elif default is not None: scalar.set_default(node, name, default)
        return node
    def compare(member_name: str, left, left_pin: str, default: str, kind: str, x: int, y: int):
        node = b.add(f"{member_name}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member_name)
        if member_name in ("EqualEqual_StrStr", "NotEqual_StrStr"): node.text = node.text.replace("KismetMathLibrary", "KismetStringLibrary")
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A"); scalar.set_default(node, "B", default); return node
    def bool_binary(member_name: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.add(f"{member_name}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member_name)
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A"); bp.connect(right, right_pin, node, "B"); return node
    def bool_not(source, source_pin: str, x: int, y: int):
        node = add_form(f"not_{len(b.nodes)}", "bool_not", x, y); pin_kind(node, "A", "bool"); pin_kind(node, "ReturnValue", "bool"); bp.connect(source, source_pin, node, "A"); return node
    def select(condition, condition_pin: str, false_source, false_pin: str | None, false_default: str | None,
               true_source, true_pin: str | None, true_default: str | None, kind: str, x: int, y: int):
        node = b.add(f"select_{kind}_{len(b.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"): pin_kind(node, pin, kind)
        pin_kind(node, "Index", "bool"); bp.connect(condition, condition_pin, node, "Index")
        if false_source is None: scalar.set_default(node, "Option 0", false_default)
        else: bp.connect(false_source, false_pin, node, "Option 0")
        if true_source is None: scalar.set_default(node, "Option 1", true_default)
        else: bp.connect(true_source, true_pin, node, "Option 1")
        return node
    def scalar_math(member_name: str, left, left_pin: str, right=None, right_pin: str | None = None,
                    default: str | None = None, x: int = 0, y: int = 0):
        node = b.math(member_name, x, y); bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default)
        else: bp.connect(right, right_pin, node, "B")
        return node
    def unary(member_name: str, source, source_pin: str, x: int, y: int):
        node = add_form(f"{member_name}_{len(b.nodes)}", "bool_not", x, y); scalar.retarget_function(node, member_name)
        pin_kind(node, "A", "real"); pin_kind(node, "ReturnValue", "real"); bp.connect(source, source_pin, node, "A"); return node
    def vector_binary(form: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = add_form(f"{form}_{len(b.nodes)}", form, x, y)
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "vector")
        bp.connect(left, left_pin, node, "A"); bp.connect(right, right_pin, node, "B"); return node
    def vsize(source, source_pin: str, x: int, y: int):
        node = add_form(f"vsize_{len(b.nodes)}", "vsize", x, y); pin_kind(node, "A", "vector"); pin_kind(node, "ReturnValue", "real"); bp.connect(source, source_pin, node, "A"); return node
    def normal(source, source_pin: str, x: int, y: int):
        node = add_form(f"normal_{len(b.nodes)}", "normal", x, y); pin_kind(node, "A", "vector"); pin_kind(node, "ReturnValue", "vector"); bp.connect(source, source_pin, node, "A"); scalar.set_default(node, "Tolerance", VECTOR_EPSILON); return node
    def make_scalar_vector(source, source_pin: str, x: int, y: int):
        node = add_form(f"scalar_vector_{len(b.nodes)}", "make_vector", x, y)
        for pin in ("X", "Y", "Z"): pin_kind(node, pin, "real"); bp.connect(source, source_pin, node, pin)
        pin_kind(node, "ReturnValue", "vector"); return node
    def scale_vector(source, source_pin: str, factor_source, factor_pin: str, x: int, y: int):
        factor = make_scalar_vector(factor_source, factor_pin, x, y + 96)
        return vector_binary("vector_multiply", source, source_pin, factor, "ReturnValue", x + 224, y)
    def quat_normalized(source, source_pin: str, x: int, y: int):
        node = add_form(f"quat_normalized_{len(b.nodes)}", "quat_normalized", x, y); pin_kind(node, "Q", "quat"); pin_kind(node, "ReturnValue", "quat"); bp.connect(source, source_pin, node, "Q"); scalar.set_default(node, "Tolerance", VECTOR_EPSILON); return node
    def break_quaternion(source, source_pin: str, x: int, y: int):
        node = add_form(f"break_quat_{len(b.nodes)}", "break_quat", x, y); pin_kind(node, "InQuat", "quat"); bp.connect(source, source_pin, node, "InQuat")
        for pin in ("X", "Y", "Z", "W"): pin_kind(node, pin, "real")
        return node
    def angle_from_quat(source, source_pin: str, x: int, y: int):
        unit = quat_normalized(source, source_pin, x, y); split = break_quaternion(unit, "ReturnValue", x + 224, y)
        negative = compare("Less_DoubleDouble", split, "W", "0.0", "real", x + 448, y)
        neg_w = scalar_math("Multiply_DoubleDouble", split, "W", default="-1.0", x=x + 448, y=y + 128)
        aligned_w = select(negative, "ReturnValue", split, "W", None, neg_w, "ReturnValue", None, "real", x + 672, y)
        clamp = add_form(f"clamp_w_{len(b.nodes)}", "clamp", x + 896, y); pin_kind(clamp, "Value", "real"); pin_kind(clamp, "Min", "real"); pin_kind(clamp, "Max", "real"); pin_kind(clamp, "ReturnValue", "real"); bp.connect(aligned_w, "ReturnValue", clamp, "Value"); scalar.set_default(clamp, "Min", "-1.0"); scalar.set_default(clamp, "Max", "1.0")
        half = unary("DegAcos", clamp, "ReturnValue", x + 1120, y)
        angle = scalar_math("Multiply_DoubleDouble", half, "ReturnValue", default="2.0", x=x + 1344, y=y)
        return unit, split, negative, aligned_w, half, angle

    scratch = get("CameraOperatorScratchValidV1", "bool", 0, 0)
    guard = b.add("translation_guard", "branch", 256, 4200); bp.connect(b.entry, "then", guard, "execute"); bp.connect(scratch, "CameraOperatorScratchValidV1", guard, "Condition")
    initialized = get("CameraOperatorStateInitializedV1", "bool", 0, 192)
    mode = get("CameraOperatorCandidateModeV1", "string", 0, 352)
    recenter = get("CameraOperatorCandidateRecenterActiveV1", "bool", 0, 512)
    mode_free = compare("EqualEqual_StrStr", mode, "CameraOperatorCandidateModeV1", "free_look", "string", 320, 288)
    mode_carrier = compare("EqualEqual_StrStr", mode, "CameraOperatorCandidateModeV1", "carrier_freecam", "string", 320, 448)
    mode_directed = compare("EqualEqual_StrStr", mode, "CameraOperatorCandidateModeV1", "directed", "string", 320, 608)
    free_or_carrier = bool_binary("BooleanOR", mode_free, "ReturnValue", mode_carrier, "ReturnValue", 544, 368)
    no_recenter = bool_not(recenter, "CameraOperatorCandidateRecenterActiveV1", 544, 528)
    interactive_mode = bool_binary("BooleanAND", free_or_carrier, "ReturnValue", no_recenter, "ReturnValue", 768, 448)
    interactive = bool_binary("BooleanAND", initialized, "CameraOperatorStateInitializedV1", interactive_mode, "ReturnValue", 992, 448)

    look_input = get("CameraOperatorInputLookV1", "vector", 0, 800)
    look_length = vsize(look_input, "CameraOperatorInputLookV1", 320, 800)
    input_normal = normal(look_input, "CameraOperatorInputLookV1", 320, 960)
    over_one = compare("Greater_DoubleDouble", look_length, "ReturnValue", "1.0", "real", 544, 800)
    bounded_input = select(over_one, "ReturnValue", look_input, "CameraOperatorInputLookV1", None, input_normal, "ReturnValue", None, "vector", 768, 800)
    max_speed = get("CameraOperatorPolicyMaximumAngularSpeedV1", "real", 0, 1120)
    desired_interactive = scale_vector(bounded_input, "ReturnValue", max_speed, "CameraOperatorPolicyMaximumAngularSpeedV1", 992, 800)

    prior_look = get("CameraOperatorStateLookOffsetQuatV1", "quat", 0, 1376)
    unit, split, negative, aligned_w, half_angle, prior_angle = angle_from_quat(prior_look, "CameraOperatorStateLookOffsetQuatV1", 320, 1376)
    sine = unary("DegSin", half_angle, "ReturnValue", 1888, 1536)
    sine_small = compare("LessEqual_DoubleDouble", sine, "ReturnValue", VECTOR_EPSILON, "real", 2112, 1536)
    safe_sine = select(sine_small, "ReturnValue", sine, "ReturnValue", None, None, None, "1.0", "real", 2336, 1536)
    aligned_components = []
    for index, component in enumerate(("X", "Y", "Z")):
        negated = scalar_math("Multiply_DoubleDouble", split, component, default="-1.0", x=1888, y=1760 + index * 144)
        aligned = select(negative, "ReturnValue", split, component, None, negated, "ReturnValue", None, "real", 2112, 1760 + index * 144)
        divided = scalar_math("Divide_DoubleDouble", aligned, "ReturnValue", safe_sine, "ReturnValue", x=2560, y=1760 + index * 144)
        aligned_components.append(divided)
    axis = add_form("prior_axis", "make_vector", 2784, 1904)
    for component, source in zip(("X", "Y", "Z"), aligned_components): pin_kind(axis, component, "real"); bp.connect(source, "ReturnValue", axis, component)
    pin_kind(axis, "ReturnValue", "vector")
    delta = get("CameraOperatorInputDeltaSecondsV1", "real", 0, 2240)
    angle_rate = scalar_math("Divide_DoubleDouble", prior_angle, "ReturnValue", delta, "CameraOperatorInputDeltaSecondsV1", x=1888, y=2240)
    recenter_speed = get("CameraOperatorPolicyRecenterAngularSpeedV1", "real", 0, 2400)
    limited_rate = add_form("limited_recenter_rate", "minimum", 2112, 2240); pin_kind(limited_rate, "A", "real"); pin_kind(limited_rate, "B", "real"); pin_kind(limited_rate, "ReturnValue", "real"); bp.connect(recenter_speed, "CameraOperatorPolicyRecenterAngularSpeedV1", limited_rate, "A"); bp.connect(angle_rate, "ReturnValue", limited_rate, "B")
    negative_rate = scalar_math("Multiply_DoubleDouble", limited_rate, "ReturnValue", default="-1.0", x=2336, y=2240)
    desired_decay_nonzero = scale_vector(axis, "ReturnValue", negative_rate, "ReturnValue", 3008, 1904)
    prior_settled = compare("LessEqual_DoubleDouble", prior_angle, "ReturnValue", SETTLE_ANGLE, "real", 1888, 2400)
    desired_decay = select(prior_settled, "ReturnValue", desired_decay_nonzero, "ReturnValue", None, None, None, "0, 0, 0", "vector", 3456, 2080)
    desired = select(interactive, "ReturnValue", desired_decay, "ReturnValue", None, desired_interactive, "ReturnValue", None, "vector", 3680, 1376)

    prior_velocity = get("CameraOperatorStateAngularVelocityV1", "vector", 3456, 1600)
    velocity_difference = vector_binary("vector_subtract", desired, "ReturnValue", prior_velocity, "CameraOperatorStateAngularVelocityV1", 3904, 1472)
    difference_length = vsize(velocity_difference, "ReturnValue", 4128, 1472)
    acceleration = get("CameraOperatorPolicyAngularAccelerationV1", "real", 3456, 1760)
    max_delta = scalar_math("Multiply_DoubleDouble", acceleration, "CameraOperatorPolicyAngularAccelerationV1", delta, "CameraOperatorInputDeltaSecondsV1", x=3904, y=1760)
    reaches = compare("LessEqual_DoubleDouble", difference_length, "ReturnValue", "0.0", "real", 4352, 1472); bp.connect(max_delta, "ReturnValue", reaches, "B")
    difference_normal = normal(velocity_difference, "ReturnValue", 4352, 1632)
    bounded_delta = scale_vector(difference_normal, "ReturnValue", max_delta, "ReturnValue", 4576, 1632)
    moved_velocity = vector_binary("vector_add", prior_velocity, "CameraOperatorStateAngularVelocityV1", bounded_delta, "ReturnValue", 5024, 1632)
    velocity_value = select(reaches, "ReturnValue", moved_velocity, "ReturnValue", None, desired, "ReturnValue", None, "vector", 5248, 1472)

    rotation_step = scale_vector(velocity_value, "ReturnValue", delta, "CameraOperatorInputDeltaSecondsV1", 5472, 1472)
    step_length = vsize(rotation_step, "ReturnValue", 5920, 1472)
    step_small = compare("LessEqual_DoubleDouble", step_length, "ReturnValue", VECTOR_EPSILON, "real", 6144, 1472)
    safe_step_length = select(step_small, "ReturnValue", step_length, "ReturnValue", None, None, None, "1.0", "real", 6368, 1472)
    # Divide by length: reciprocal first, then component-wise vector scale.
    reciprocal_step = b.math("Divide_DoubleDouble", 6368, 1696); scalar.set_default(reciprocal_step, "A", "1.0"); bp.connect(safe_step_length, "ReturnValue", reciprocal_step, "B")
    step_axis = scale_vector(rotation_step, "ReturnValue", reciprocal_step, "ReturnValue", 6816, 1472)
    half_step = scalar_math("Multiply_DoubleDouble", step_length, "ReturnValue", default="0.5", x=7040, y=1696)
    step_sine = unary("DegSin", half_step, "ReturnValue", 7264, 1696)
    step_cosine = unary("DegCos", half_step, "ReturnValue", 7488, 1696)
    sine_axis = scale_vector(step_axis, "ReturnValue", step_sine, "ReturnValue", 7264, 1472)
    split_sine_axis = add_form("split_sine_axis", "break_vector", 7712, 1472); pin_kind(split_sine_axis, "InVec", "vector"); bp.connect(sine_axis, "ReturnValue", split_sine_axis, "InVec")
    for component in ("X", "Y", "Z"): pin_kind(split_sine_axis, component, "real")
    delta_components = [select(step_small, "ReturnValue", split_sine_axis, component, None, None, None, "0.0", "real", 7936, 1376 + index * 144) for index, component in enumerate(("X", "Y", "Z"))]
    delta_w = select(step_small, "ReturnValue", step_cosine, "ReturnValue", None, None, None, "1.0", "real", 7936, 1808)
    delta_storage = get("CameraOperatorCandidateLookOffsetQuatV1", "quat", 7712, 2080)
    set_delta = add_form("set_delta_quaternion", "quat_set", 8384, 2080); pin_kind(set_delta, "Q", "quat"); bp.connect(delta_storage, "CameraOperatorCandidateLookOffsetQuatV1", set_delta, "Q")
    for component, source in zip(("X", "Y", "Z"), delta_components): bp.connect(source, "ReturnValue", set_delta, component)
    bp.connect(delta_w, "ReturnValue", set_delta, "W")

    delta_read = get("CameraOperatorCandidateLookOffsetQuatV1", "quat", 8608, 1376)
    raw_look_multiply = add_form("raw_look_multiply", "quat_multiply", 8832, 1376); pin_kind(raw_look_multiply, "A", "quat"); pin_kind(raw_look_multiply, "B", "quat"); pin_kind(raw_look_multiply, "ReturnValue", "quat"); bp.connect(prior_look, "CameraOperatorStateLookOffsetQuatV1", raw_look_multiply, "A"); bp.connect(delta_read, "CameraOperatorCandidateLookOffsetQuatV1", raw_look_multiply, "B")
    raw_look = quat_normalized(raw_look_multiply, "ReturnValue", 9056, 1376)
    _, _, _, _, _, new_angle = angle_from_quat(raw_look, "ReturnValue", 9280, 1376)
    velocity_length = vsize(velocity_value, "ReturnValue", 9280, 1600)
    look_angle_small = compare("LessEqual_DoubleDouble", new_angle, "ReturnValue", SETTLE_ANGLE, "real", 10848, 1376)
    look_velocity_small = compare("LessEqual_DoubleDouble", velocity_length, "ReturnValue", SETTLE_SPEED, "real", 10848, 1536)
    settled_look = bool_binary("BooleanAND", look_angle_small, "ReturnValue", look_velocity_small, "ReturnValue", 11072, 1456)
    final_look = select(settled_look, "ReturnValue", raw_look, "ReturnValue", None, None, None, "0, 0, 0, 1", "quat", 11296, 1376)
    final_velocity = select(settled_look, "ReturnValue", velocity_value, "ReturnValue", None, None, None, "0, 0, 0", "vector", 11296, 1536)

    # These two setters freeze the delta-dependent values before CandidateLook
    # is replaced. Downstream pure nodes read their Output_Get pins only.
    angular_publication = set_("CameraOperatorCandidateAngularVelocityV1", "vector", 8608, 4200, final_velocity, "ReturnValue")
    look_publication = set_("CameraOperatorCandidateLookOffsetQuatV1", "quat", 8864, 4200, final_look, "ReturnValue")
    _, _, _, _, _, published_look_angle = angle_from_quat(look_publication, "Output_Get", 11520, 1120)
    published_velocity_length = vsize(angular_publication, "Output_Get", 11520, 1680)
    published_angle_small = compare("LessEqual_DoubleDouble", published_look_angle, "ReturnValue", SETTLE_ANGLE, "real", 13088, 1120)
    published_velocity_small = compare("LessEqual_DoubleDouble", published_velocity_length, "ReturnValue", SETTLE_SPEED, "real", 13088, 1280)
    published_look_settled = bool_binary("BooleanAND", published_angle_small, "ReturnValue", published_velocity_small, "ReturnValue", 13312, 1200)
    published_look_identity = compare("LessEqual_DoubleDouble", published_look_angle, "ReturnValue", "0.0", "real", 13312, 1360)

    translation_offset = get("CameraOperatorCandidateTranslationOffsetV1", "vector", 9280, 2000)
    translation_velocity = get("CameraOperatorCandidateTranslationVelocityV1", "vector", 9280, 2160)
    offset_length = vsize(translation_offset, "CameraOperatorCandidateTranslationOffsetV1", 9504, 2000)
    translation_speed = vsize(translation_velocity, "CameraOperatorCandidateTranslationVelocityV1", 9504, 2160)
    offset_zero = compare("LessEqual_DoubleDouble", offset_length, "ReturnValue", "0.0", "real", 9728, 2000)
    translation_zero = compare("LessEqual_DoubleDouble", translation_speed, "ReturnValue", "0.0", "real", 9728, 2160)
    settled_translation = bool_binary("BooleanAND", offset_zero, "ReturnValue", translation_zero, "ReturnValue", 9952, 2080)
    both_settled = bool_binary("BooleanAND", settled_translation, "ReturnValue", published_look_settled, "ReturnValue", 13536, 1840)
    not_both = bool_not(both_settled, "ReturnValue", 11520, 1840)
    next_recenter = bool_binary("BooleanAND", recenter, "CameraOperatorCandidateRecenterActiveV1", not_both, "ReturnValue", 11744, 1840)
    not_translation = bool_not(settled_translation, "ReturnValue", 10176, 2080)
    directed_or_recenter = bool_binary("BooleanOR", mode_directed, "ReturnValue", recenter, "CameraOperatorCandidateRecenterActiveV1", 10240, 2240)
    directed_transition = bool_binary("BooleanAND", directed_or_recenter, "ReturnValue", not_both, "ReturnValue", 11744, 2240)
    free_transition = bool_binary("BooleanAND", mode_free, "ReturnValue", not_translation, "ReturnValue", 10464, 2080)
    transition = bool_binary("BooleanOR", directed_transition, "ReturnValue", free_transition, "ReturnValue", 11968, 2160)
    not_directed = bool_not(mode_directed, "ReturnValue", 10240, 2400)
    override = bool_binary("BooleanOR", not_directed, "ReturnValue", not_both, "ReturnValue", 11744, 2400)

    authored_position = get("CameraOperatorInputAuthoredPositionV1", "vector", 9952, 2640)
    position_value = vector_binary("vector_add", authored_position, "CameraOperatorInputAuthoredPositionV1", translation_offset, "CameraOperatorCandidateTranslationOffsetV1", 10240, 2640)
    authored_body = get("CameraOperatorInputAuthoredBodyQuatV1", "quat", 9952, 2800)
    authored_gimbal = get("CameraOperatorInputAuthoredGimbalQuatV1", "quat", 9952, 2960)
    composed_gimbal_raw = add_form("composed_gimbal_raw", "quat_multiply", 11520, 2800); pin_kind(composed_gimbal_raw, "A", "quat"); pin_kind(composed_gimbal_raw, "B", "quat"); pin_kind(composed_gimbal_raw, "ReturnValue", "quat"); bp.connect(authored_gimbal, "CameraOperatorInputAuthoredGimbalQuatV1", composed_gimbal_raw, "A"); bp.connect(look_publication, "Output_Get", composed_gimbal_raw, "B")
    composed_gimbal = quat_normalized(composed_gimbal_raw, "ReturnValue", 11744, 2800)
    final_gimbal = select(published_look_identity, "ReturnValue", composed_gimbal, "ReturnValue", None, authored_gimbal, "CameraOperatorInputAuthoredGimbalQuatV1", None, "quat", 13536, 2800)

    publications = [
        angular_publication,
        look_publication,
        set_("CameraOperatorCandidateRecenterActiveV1", "bool", 9120, 4200, next_recenter, "ReturnValue"),
        set_("CameraOperatorCandidatePositionV1", "vector", 9376, 4200, position_value, "ReturnValue"),
        set_("CameraOperatorCandidateBodyQuatV1", "quat", 9632, 4200, authored_body, "CameraOperatorInputAuthoredBodyQuatV1"),
        set_("CameraOperatorCandidateGimbalQuatV1", "quat", 9888, 4200, final_gimbal, "ReturnValue"),
        set_("CameraOperatorCandidateOverrideActiveV1", "bool", 10144, 4200, override, "ReturnValue"),
        set_("CameraOperatorCandidateTransitionActiveV1", "bool", 10400, 4200, transition, "ReturnValue"),
        set_("CameraOperatorCandidateValidV1", "bool", 10656, 4200, default="true"),
    ]
    bp.connect(guard, "then", set_delta, "execute"); bp.connect(set_delta, "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]): bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
