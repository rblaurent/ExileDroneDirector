"""Build bounded viewer-local translation candidates for camera operator override."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCameraOperatorTranslationV1"
VECTOR_EPSILON = "1e-9"
SETTLE_POSITION = "0.0001"
SETTLE_SPEED = "0.0001"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_operator_translation_base", path)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    airframe = bp.read_blocks(args.project_root / "tools/blueprint/templates/airframe-gimbal-native-node-forms.eddgraph")
    orientation = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    position = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-compiled-position-route-v1.eddgraph")
    velocity = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/compute-position-route-velocities-v1.eddgraph")
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    source_samples = bp.read_blocks(args.project_root / "tools/blueprint/snippets/build-airframe-source-position-body-profile-samples-v1.eddgraph")
    bool_forms = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-roll-and-horizon-input.eddgraph")
    forms.update(
        select=bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select "),
        make_vector=bp.find_block(velocity, r'MemberName="MakeVector"'),
        vector_add=bp.find_block(position, r'MemberName="Add_VectorVector"'),
        vector_subtract=bp.find_block(position, r'MemberName="Subtract_VectorVector"'),
        vector_multiply=bp.find_block(position, r'MemberName="Multiply_VectorVector"'),
        vsize=bp.find_block(orientation, r'MemberName="VSize"'),
        normal=bp.find_block(airframe, r'MemberName="Normal"'),
        rotate=bp.find_block(airframe, r'MemberName="Quat_RotateVector"'),
        dot=bp.find_block(airframe, r'MemberName="Dot_VectorVector"'),
        minimum=bp.find_block(source_samples, r'MemberName="FMin"'),
        bool_not=bp.find_block(bool_forms, r'MemberName="Not_PreBool"'),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

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
    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def compare(member: str, left, left_pin: str, default: str, kind: str, x: int, y: int):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        if member in ("EqualEqual_StrStr", "NotEqual_StrStr"): node.text = node.text.replace("KismetMathLibrary", "KismetStringLibrary")
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A"); scalar.set_default(node, "B", default); return node
    def bool_binary(member: str, left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A"); bp.connect(right, right_pin, node, "B"); return node
    def bool_not(source, source_pin: str, x: int, y: int):
        node = add_form(f"not_{len(b.nodes)}", "bool_not", x, y)
        pin_kind(node, "A", "bool"); pin_kind(node, "ReturnValue", "bool"); bp.connect(source, source_pin, node, "A"); return node
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
    def scalar_math(member: str, left, left_pin: str, right=None, right_pin: str | None = None,
                    default: str | None = None, x: int = 0, y: int = 0):
        node = b.math(member, x, y)
        bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default)
        else: bp.connect(right, right_pin, node, "B")
        return node
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
    def scale_vector(source, source_pin: str, scalar_source, scalar_pin: str, x: int, y: int):
        factor = make_scalar_vector(scalar_source, scalar_pin, x, y + 96)
        return vector_binary("vector_multiply", source, source_pin, factor, "ReturnValue", x + 224, y)

    validation = get("CameraOperatorValidationValidV1", "bool", 0, 0)
    guard = b.add("validation_guard", "branch", 256, 3900); bp.connect(b.entry, "then", guard, "execute"); bp.connect(validation, "CameraOperatorValidationValidV1", guard, "Condition")
    requested = get("CameraOperatorInputRequestedModeV1", "string", 0, 192)
    return_directed = get("CameraOperatorInputReturnToDirectedRequestedV1", "bool", 0, 352)
    mode = select(return_directed, "CameraOperatorInputReturnToDirectedRequestedV1", requested, "CameraOperatorInputRequestedModeV1", None, None, None, "directed", "string", 320, 224)
    mode_carrier = compare("EqualEqual_StrStr", mode, "ReturnValue", "carrier_freecam", "string", 576, 160)
    mode_directed = compare("EqualEqual_StrStr", mode, "ReturnValue", "directed", "string", 576, 320)
    not_directed = bool_not(mode_directed, "ReturnValue", 800, 320)

    initialized = get("CameraOperatorStateInitializedV1", "bool", 0, 576)
    prior_recenter = get("CameraOperatorStateRecenterActiveV1", "bool", 0, 736)
    recenter_requested = get("CameraOperatorInputRecenterRequestedV1", "bool", 0, 896)
    translation_input = get("CameraOperatorInputTranslationV1", "vector", 0, 1088)
    look_input = get("CameraOperatorInputLookV1", "vector", 0, 1248)
    translation_length = vsize(translation_input, "CameraOperatorInputTranslationV1", 320, 1088)
    look_length = vsize(look_input, "CameraOperatorInputLookV1", 320, 1248)
    translation_active = compare("Greater_DoubleDouble", translation_length, "ReturnValue", VECTOR_EPSILON, "real", 544, 1088)
    look_active = compare("Greater_DoubleDouble", look_length, "ReturnValue", VECTOR_EPSILON, "real", 544, 1248)
    carrier_translation_active = bool_binary("BooleanAND", mode_carrier, "ReturnValue", translation_active, "ReturnValue", 768, 1088)
    operator_active = bool_binary("BooleanOR", look_active, "ReturnValue", carrier_translation_active, "ReturnValue", 992, 1168)
    no_operator_active = bool_not(operator_active, "ReturnValue", 1216, 1168)
    latched_recenter = bool_binary("BooleanAND", prior_recenter, "CameraOperatorStateRecenterActiveV1", no_operator_active, "ReturnValue", 1440, 800)
    requested_or_latched = bool_binary("BooleanOR", recenter_requested, "CameraOperatorInputRecenterRequestedV1", latched_recenter, "ReturnValue", 1664, 864)
    recenter_raw = bool_binary("BooleanAND", not_directed, "ReturnValue", requested_or_latched, "ReturnValue", 1888, 864)
    recenter = select(initialized, "CameraOperatorStateInitializedV1", None, None, "false", recenter_raw, "ReturnValue", None, "bool", 2112, 864)
    no_recenter = bool_not(recenter, "ReturnValue", 2336, 864)
    carrier_unrecentered = bool_binary("BooleanAND", mode_carrier, "ReturnValue", no_recenter, "ReturnValue", 2560, 864)
    interactive = bool_binary("BooleanAND", initialized, "CameraOperatorStateInitializedV1", carrier_unrecentered, "ReturnValue", 2784, 864)

    input_normal = normal(translation_input, "CameraOperatorInputTranslationV1", 544, 1456)
    input_over_one = compare("Greater_DoubleDouble", translation_length, "ReturnValue", "1.0", "real", 544, 1616)
    bounded_input = select(input_over_one, "ReturnValue", translation_input, "CameraOperatorInputTranslationV1", None, input_normal, "ReturnValue", None, "vector", 768, 1504)
    carrier_quat = get("CameraOperatorInputCarrierFrameQuatV1", "quat", 0, 1776)
    rotated = add_form("carrier_rotated_input", "rotate", 992, 1664); pin_kind(rotated, "Q", "quat"); pin_kind(rotated, "V", "vector"); pin_kind(rotated, "ReturnValue", "vector"); bp.connect(carrier_quat, "CameraOperatorInputCarrierFrameQuatV1", rotated, "Q"); bp.connect(bounded_input, "ReturnValue", rotated, "V")
    translation_frame = get("CameraOperatorPolicyTranslationFrameV1", "string", 0, 1936)
    carrier_frame = compare("EqualEqual_StrStr", translation_frame, "CameraOperatorPolicyTranslationFrameV1", "carrier", "string", 320, 1936)
    framed_direction = select(carrier_frame, "ReturnValue", bounded_input, "ReturnValue", None, rotated, "ReturnValue", None, "vector", 1216, 1664)
    max_speed = get("CameraOperatorPolicyMaximumTranslationSpeedV1", "real", 0, 2096)
    desired_interactive = scale_vector(framed_direction, "ReturnValue", max_speed, "CameraOperatorPolicyMaximumTranslationSpeedV1", 1440, 1664)

    prior_offset = get("CameraOperatorStateTranslationOffsetV1", "vector", 0, 2320)
    prior_velocity = get("CameraOperatorStateTranslationVelocityV1", "vector", 0, 2480)
    offset_length = vsize(prior_offset, "CameraOperatorStateTranslationOffsetV1", 320, 2320)
    delta = get("CameraOperatorInputDeltaSecondsV1", "real", 0, 2640)
    distance_speed = scalar_math("Divide_DoubleDouble", offset_length, "ReturnValue", delta, "CameraOperatorInputDeltaSecondsV1", x=544, y=2320)
    recenter_speed = get("CameraOperatorPolicyRecenterTranslationSpeedV1", "real", 0, 2800)
    minimum = add_form("bounded_recenter_speed", "minimum", 768, 2320); pin_kind(minimum, "A", "real"); pin_kind(minimum, "B", "real"); pin_kind(minimum, "ReturnValue", "real"); bp.connect(recenter_speed, "CameraOperatorPolicyRecenterTranslationSpeedV1", minimum, "A"); bp.connect(distance_speed, "ReturnValue", minimum, "B")
    negative_speed = scalar_math("Multiply_DoubleDouble", minimum, "ReturnValue", default="-1.0", x=992, y=2320)
    offset_settled = compare("LessEqual_DoubleDouble", offset_length, "ReturnValue", SETTLE_POSITION, "real", 544, 2480)
    safe_offset_length = select(offset_settled, "ReturnValue", offset_length, "ReturnValue", None, None, None, "1.0", "real", 768, 2480)
    decay_factor = scalar_math("Divide_DoubleDouble", negative_speed, "ReturnValue", safe_offset_length, "ReturnValue", x=1216, y=2320)
    decay_nonzero = scale_vector(prior_offset, "CameraOperatorStateTranslationOffsetV1", decay_factor, "ReturnValue", 1440, 2320)
    desired_decay = select(offset_settled, "ReturnValue", decay_nonzero, "ReturnValue", None, None, None, "0, 0, 0", "vector", 1888, 2320)
    desired_velocity = select(interactive, "ReturnValue", desired_decay, "ReturnValue", None, desired_interactive, "ReturnValue", None, "vector", 3008, 1664)

    velocity_delta = vector_binary("vector_subtract", desired_velocity, "ReturnValue", prior_velocity, "CameraOperatorStateTranslationVelocityV1", 3232, 1760)
    velocity_delta_length = vsize(velocity_delta, "ReturnValue", 3456, 1760)
    acceleration = get("CameraOperatorPolicyTranslationAccelerationV1", "real", 3008, 2080)
    max_velocity_delta = scalar_math("Multiply_DoubleDouble", acceleration, "CameraOperatorPolicyTranslationAccelerationV1", delta, "CameraOperatorInputDeltaSecondsV1", x=3232, y=2080)
    reaches_target = compare("LessEqual_DoubleDouble", velocity_delta_length, "ReturnValue", "0.0", "real", 3680, 1760)
    bp.connect(max_velocity_delta, "ReturnValue", reaches_target, "B")
    velocity_delta_normal = normal(velocity_delta, "ReturnValue", 3680, 1920)
    bounded_delta = scale_vector(velocity_delta_normal, "ReturnValue", max_velocity_delta, "ReturnValue", 3904, 1920)
    moved_velocity = vector_binary("vector_add", prior_velocity, "CameraOperatorStateTranslationVelocityV1", bounded_delta, "ReturnValue", 4352, 1920)
    velocity = select(reaches_target, "ReturnValue", moved_velocity, "ReturnValue", None, desired_velocity, "ReturnValue", None, "vector", 4576, 1760)
    velocity_dt = scale_vector(velocity, "ReturnValue", delta, "CameraOperatorInputDeltaSecondsV1", 4800, 1920)
    raw_offset = vector_binary("vector_add", prior_offset, "CameraOperatorStateTranslationOffsetV1", velocity_dt, "ReturnValue", 5248, 1920)
    crossing_dot = add_form("crossing_dot", "dot", 5472, 1920); pin_kind(crossing_dot, "A", "vector"); pin_kind(crossing_dot, "B", "vector"); pin_kind(crossing_dot, "ReturnValue", "real"); bp.connect(prior_offset, "CameraOperatorStateTranslationOffsetV1", crossing_dot, "A"); bp.connect(raw_offset, "ReturnValue", crossing_dot, "B")
    crossed_zero = compare("LessEqual_DoubleDouble", crossing_dot, "ReturnValue", "0.0", "real", 5696, 1920)
    not_interactive = bool_not(interactive, "ReturnValue", 5696, 2080)
    decay_crossed = bool_binary("BooleanAND", not_interactive, "ReturnValue", crossed_zero, "ReturnValue", 5920, 2000)
    uncrossed_offset = select(decay_crossed, "ReturnValue", raw_offset, "ReturnValue", None, None, None, "0, 0, 0", "vector", 6144, 1920)
    uncrossed_velocity = select(decay_crossed, "ReturnValue", velocity, "ReturnValue", None, None, None, "0, 0, 0", "vector", 6144, 2080)

    tether_enabled = get("CameraOperatorPolicyTetherEnabledV1", "bool", 5024, 2320)
    tether_distance = get("CameraOperatorPolicyTetherDistanceV1", "real", 5024, 2480)
    uncrossed_length = vsize(uncrossed_offset, "ReturnValue", 6368, 2320)
    beyond_tether = compare("Greater_DoubleDouble", uncrossed_length, "ReturnValue", "0.0", "real", 6592, 2320)
    bp.connect(tether_distance, "CameraOperatorPolicyTetherDistanceV1", beyond_tether, "B")
    tether_applied_raw = bool_binary("BooleanAND", tether_enabled, "CameraOperatorPolicyTetherEnabledV1", beyond_tether, "ReturnValue", 6816, 2320)
    tether_normal = normal(uncrossed_offset, "ReturnValue", 6592, 2480)
    tether_offset = scale_vector(tether_normal, "ReturnValue", tether_distance, "CameraOperatorPolicyTetherDistanceV1", 6816, 2480)
    outward_speed = add_form("outward_speed", "dot", 7264, 2480); pin_kind(outward_speed, "A", "vector"); pin_kind(outward_speed, "B", "vector"); pin_kind(outward_speed, "ReturnValue", "real"); bp.connect(uncrossed_velocity, "ReturnValue", outward_speed, "A"); bp.connect(tether_normal, "ReturnValue", outward_speed, "B")
    outward = compare("Greater_DoubleDouble", outward_speed, "ReturnValue", "0.0", "real", 7488, 2480)
    outward_component = scale_vector(tether_normal, "ReturnValue", outward_speed, "ReturnValue", 7488, 2640)
    radial_removed = vector_binary("vector_subtract", uncrossed_velocity, "ReturnValue", outward_component, "ReturnValue", 7936, 2640)
    tether_velocity = select(outward, "ReturnValue", uncrossed_velocity, "ReturnValue", None, radial_removed, "ReturnValue", None, "vector", 8160, 2480)
    bounded_offset = select(tether_applied_raw, "ReturnValue", uncrossed_offset, "ReturnValue", None, tether_offset, "ReturnValue", None, "vector", 8384, 2320)
    bounded_velocity = select(tether_applied_raw, "ReturnValue", uncrossed_velocity, "ReturnValue", None, tether_velocity, "ReturnValue", None, "vector", 8384, 2480)

    final_offset_length = vsize(bounded_offset, "ReturnValue", 8608, 2320)
    final_velocity_length = vsize(bounded_velocity, "ReturnValue", 8608, 2480)
    offset_small = compare("LessEqual_DoubleDouble", final_offset_length, "ReturnValue", SETTLE_POSITION, "real", 8832, 2320)
    velocity_small = compare("LessEqual_DoubleDouble", final_velocity_length, "ReturnValue", SETTLE_SPEED, "real", 8832, 2480)
    settled = bool_binary("BooleanAND", offset_small, "ReturnValue", velocity_small, "ReturnValue", 9056, 2400)
    settled_offset = select(settled, "ReturnValue", bounded_offset, "ReturnValue", None, None, None, "0, 0, 0", "vector", 9280, 2320)
    settled_velocity = select(settled, "ReturnValue", bounded_velocity, "ReturnValue", None, None, None, "0, 0, 0", "vector", 9280, 2480)
    final_offset = select(initialized, "CameraOperatorStateInitializedV1", None, None, "0, 0, 0", settled_offset, "ReturnValue", None, "vector", 9504, 2320)
    final_velocity = select(initialized, "CameraOperatorStateInitializedV1", None, None, "0, 0, 0", settled_velocity, "ReturnValue", None, "vector", 9504, 2480)
    final_tether = select(initialized, "CameraOperatorStateInitializedV1", None, None, "false", tether_applied_raw, "ReturnValue", None, "bool", 9504, 2640)

    publications = [
        set_("CameraOperatorCandidateModeV1", "string", 512, 3900, mode, "ReturnValue"),
        set_("CameraOperatorCandidateRecenterActiveV1", "bool", 768, 3900, recenter, "ReturnValue"),
        set_("CameraOperatorCandidateTranslationOffsetV1", "vector", 1024, 3900, final_offset, "ReturnValue"),
        set_("CameraOperatorCandidateTranslationVelocityV1", "vector", 1280, 3900, final_velocity, "ReturnValue"),
        set_("CameraOperatorCandidateTetherAppliedV1", "bool", 1536, 3900, final_tether, "ReturnValue"),
        set_("CameraOperatorScratchValidV1", "bool", 1792, 3900, default="true"),
    ]
    bp.connect(guard, "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]): bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
