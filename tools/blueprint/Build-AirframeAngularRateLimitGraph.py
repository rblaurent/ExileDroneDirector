"""Build the atomic single-sample quaternion angular-rate limiter."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ApplyAirframeAngularRateLimitV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-OrientationCompilerGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_rate_limit_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    base = load(args.project_root)
    compiler = base.Compiler(args.project_root, FUNCTION)
    builder, bp, scalar = compiler.b, compiler.bp, compiler.scalar
    native = bp.read_blocks(args.project_root / "tools/blueprint/templates/airframe-prebake-native-node-forms.eddgraph")
    orientation_native = bp.read_blocks(
        args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph"
    )
    builder.forms["qangular"] = bp.find_block(native, r'MemberName="Quat_AngularDistance"')
    builder.forms["qsize"] = bp.find_block(orientation_native, r'MemberName="Quat_Size"')

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None):
        node = compiler.call("compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            scalar.set_pin_type(node, pin, "real")
        scalar.set_pin_type(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        elif default_b is not None:
            scalar.set_default(node, "B", default_b)
        return node

    def boolean(member, left, right, x, y):
        node = compiler.call("compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"):
            scalar.set_pin_type(node, pin, "bool")
        bp.connect(left, "ReturnValue", node, "A")
        bp.connect(right, "ReturnValue", node, "B")
        return node

    def and_all(values, x, y):
        current = values[0]
        for index, value in enumerate(values[1:]):
            current = boolean("BooleanAND", current, value, x + index * 224, y)
        return current

    def or_all(values, x, y):
        current = values[0]
        for index, value in enumerate(values[1:]):
            current = boolean("BooleanOR", current, value, x + index * 224, y)
        return current

    def strict_quat(source, source_pin, x, y):
        finite = compiler.call("qfinite", x, y)
        bp.connect(source, source_pin, finite, "Q")
        size = compiler.call("qsize", x, y + 128)
        bp.connect(source, source_pin, size, "Q")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", x + 256, y + 96, default_b="0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", x + 256, y + 224, default_b="1.000001")
        return and_all((finite, lower, upper), x + 512, y + 96)

    def canonicalize(normalized, normalized_pin, scratch_name, x, y, key):
        broken = compiler.call("qbreak", x, y)
        bp.connect(normalized, normalized_pin, broken, "InQuat")
        negatives = {}
        zeroes = {}
        for index, component in enumerate(("W", "X", "Y", "Z")):
            negatives[component] = compare("Less_DoubleDouble", broken, component, x + 256, y + index * 128, default_b="0.0")
            zeroes[component] = compare("EqualEqual_DoubleDouble", broken, component, x + 480, y + index * 128, default_b="0.0")
        x_term = boolean("BooleanAND", zeroes["W"], negatives["X"], x + 704, y + 128)
        wx_zero = boolean("BooleanAND", zeroes["W"], zeroes["X"], x + 704, y + 256)
        y_term = boolean("BooleanAND", wx_zero, negatives["Y"], x + 928, y + 256)
        wxy_zero = boolean("BooleanAND", wx_zero, zeroes["Y"], x + 928, y + 384)
        z_term = boolean("BooleanAND", wxy_zero, negatives["Z"], x + 1152, y + 384)
        negate = or_all((negatives["W"], x_term, y_term, z_term), x + 1376, y + 128)
        selected = {}
        for index, component in enumerate(("X", "Y", "Z", "W")):
            inverse = compiler.math("Multiply_DoubleDouble", x + 2080, y + index * 144, "-1.0")
            bp.connect(broken, component, inverse, "A")
            choose = compiler.call("select", x + 2304, y + index * 144)
            bp.connect(inverse, "ReturnValue", choose, "A")
            bp.connect(broken, component, choose, "B")
            bp.connect(negate, "ReturnValue", choose, "bPickA")
            selected[component] = choose
        scratch = compiler.qget(scratch_name, x + 2560, y + 192)
        setter = compiler.call("qsetcomponents", x + 2816, y + 192)
        bp.connect(scratch, scratch_name, setter, "Q")
        for component in ("X", "Y", "Z", "W"):
            bp.connect(selected[component], "ReturnValue", setter, component)
        return setter, scratch

    def preserve_normalized(normalized, normalized_pin, scratch_name, x, y):
        broken = compiler.call("qbreak", x, y)
        bp.connect(normalized, normalized_pin, broken, "InQuat")
        scratch = compiler.qget(scratch_name, x + 256, y)
        setter = compiler.call("qsetcomponents", x + 512, y)
        bp.connect(scratch, scratch_name, setter, "Q")
        for component in ("X", "Y", "Z", "W"):
            bp.connect(broken, component, setter, component)
        return setter, scratch

    reset_quat = compiler.qset("AirframePrebakeScratchResultQuatV1", 256, 4000, "0, 0, 0, 1")
    reset_rate = builder.set("AirframePrebakeScratchResultAngularRateDegreesPerSecondV1", "real", 512, 4000, "0.0")
    reset_limited = builder.set("AirframePrebakeScratchResultRateLimitedV1", "bool", 768, 4000, "false")
    reset_valid = builder.set("AirframePrebakeScratchResultValidV1", "bool", 1024, 4000, "false")
    for left, right in zip((builder.entry, reset_quat, reset_rate, reset_limited), (reset_quat, reset_rate, reset_limited, reset_valid)):
        bp.connect(left, "then", right, "execute")

    previous = compiler.qget("AirframePrebakeScratchPreviousQuatV1", 0, 160)
    desired = compiler.qget("AirframePrebakeScratchDesiredQuatV1", 0, 640)
    delta = builder.get("AirframePrebakeScratchDeltaSecondsV1", "real", 0, 1120)
    maximum = builder.get("AirframePrebakeScratchMaximumRateDegreesPerSecondV1", "real", 0, 1440)
    guards = [strict_quat(previous, "AirframePrebakeScratchPreviousQuatV1", 256, 160),
              strict_quat(desired, "AirframePrebakeScratchDesiredQuatV1", 256, 640),
              builder.finite(delta, "AirframePrebakeScratchDeltaSecondsV1", 256, 1120),
              compare("Greater_DoubleDouble", delta, "AirframePrebakeScratchDeltaSecondsV1", 704, 1120, default_b="0.0"),
              compare("LessEqual_DoubleDouble", delta, "AirframePrebakeScratchDeltaSecondsV1", 928, 1120, default_b="0.5"),
              builder.finite(maximum, "AirframePrebakeScratchMaximumRateDegreesPerSecondV1", 256, 1440),
              compare("Greater_DoubleDouble", maximum, "AirframePrebakeScratchMaximumRateDegreesPerSecondV1", 704, 1440, default_b="0.0"),
              compare("LessEqual_DoubleDouble", maximum, "AirframePrebakeScratchMaximumRateDegreesPerSecondV1", 928, 1440, default_b="720.0")]
    all_valid = and_all(guards, 1280, 1760)
    branch = builder.add("guard_branch", "branch", 3072, 4000)
    bp.connect(reset_valid, "then", branch, "execute")
    bp.connect(all_valid, "ReturnValue", branch, "Condition")

    previous_normal = compiler.call("qnormalize", 3072, 160)
    desired_normal = compiler.call("qnormalize", 3072, 640)
    bp.connect(previous, "AirframePrebakeScratchPreviousQuatV1", previous_normal, "Q")
    bp.connect(desired, "AirframePrebakeScratchDesiredQuatV1", desired_normal, "Q")
    previous_set, canonical_previous = preserve_normalized(
        previous_normal, "ReturnValue", "AirframePrebakeScratchCanonicalPreviousQuatV1", 3328, 0
    )
    desired_set, canonical_desired = canonicalize(desired_normal, "ReturnValue", "AirframePrebakeScratchCanonicalDesiredQuatV1", 3328, 960, "desired")
    bp.connect(branch, "then", previous_set, "execute")
    bp.connect(previous_set, "then", desired_set, "execute")

    previous_break = compiler.call("qbreak", 6656, 1760)
    desired_break = compiler.call("qbreak", 6656, 2240)
    bp.connect(canonical_previous, "AirframePrebakeScratchCanonicalPreviousQuatV1", previous_break, "InQuat")
    bp.connect(canonical_desired, "AirframePrebakeScratchCanonicalDesiredQuatV1", desired_break, "InQuat")
    products = []
    for index, component in enumerate(("X", "Y", "Z", "W")):
        product = compiler.math("Multiply_DoubleDouble", 6912, 1760 + index * 128)
        bp.connect(previous_break, component, product, "A")
        bp.connect(desired_break, component, product, "B")
        products.append(product)
    sums = []
    current = products[0]
    for index, product in enumerate(products[1:]):
        added = compiler.math("Add_DoubleDouble", 7168 + index * 224, 1920)
        bp.connect(current, "ReturnValue", added, "A")
        bp.connect(product, "ReturnValue", added, "B")
        sums.append(added)
        current = added
    align_negative = compare("Less_DoubleDouble", current, "ReturnValue", 7840, 1920, default_b="0.0")
    aligned_components = {}
    for index, component in enumerate(("X", "Y", "Z", "W")):
        inverse = compiler.math("Multiply_DoubleDouble", 8064, 1760 + index * 144, "-1.0")
        bp.connect(desired_break, component, inverse, "A")
        choose = compiler.call("select", 8288, 1760 + index * 144)
        bp.connect(inverse, "ReturnValue", choose, "A")
        bp.connect(desired_break, component, choose, "B")
        bp.connect(align_negative, "ReturnValue", choose, "bPickA")
        aligned_components[component] = choose
    aligned = compiler.qget("AirframePrebakeScratchAlignedDesiredQuatV1", 8544, 1920)
    aligned_set = compiler.call("qsetcomponents", 8800, 1920)
    bp.connect(aligned, "AirframePrebakeScratchAlignedDesiredQuatV1", aligned_set, "Q")
    for component in ("X", "Y", "Z", "W"):
        bp.connect(aligned_components[component], "ReturnValue", aligned_set, component)
    bp.connect(desired_set, "then", aligned_set, "execute")

    angular_radians = compiler.call("qangular", 9056, 1600)
    bp.connect(canonical_previous, "AirframePrebakeScratchCanonicalPreviousQuatV1", angular_radians, "A")
    bp.connect(aligned, "AirframePrebakeScratchAlignedDesiredQuatV1", angular_radians, "B")
    angular_degrees = compiler.math("Multiply_DoubleDouble", 9312, 1600, "57.29577951308232")
    bp.connect(angular_radians, "ReturnValue", angular_degrees, "A")
    allowed = compiler.math("Multiply_DoubleDouble", 9312, 1920)
    bp.connect(delta, "AirframePrebakeScratchDeltaSecondsV1", allowed, "A")
    bp.connect(maximum, "AirframePrebakeScratchMaximumRateDegreesPerSecondV1", allowed, "B")
    limited = compare("Greater_DoubleDouble", angular_degrees, "ReturnValue", 9568, 1760, right=allowed, right_pin="ReturnValue")
    angle_positive = compare("Greater_DoubleDouble", angular_degrees, "ReturnValue", 9568, 2080, default_b="1e-12")
    safe_angle = compiler.call("select", 9792, 2080)
    bp.connect(angular_degrees, "ReturnValue", safe_angle, "A")
    scalar.set_default(safe_angle, "B", "1.0")
    bp.connect(angle_positive, "ReturnValue", safe_angle, "bPickA")
    alpha_raw = compiler.math("Divide_DoubleDouble", 10048, 1920)
    bp.connect(allowed, "ReturnValue", alpha_raw, "A")
    bp.connect(safe_angle, "ReturnValue", alpha_raw, "B")
    alpha = builder.add("alpha_clamp", "clamp", 10272, 1920)
    scalar.set_default(alpha, "Min", "0.0")
    scalar.set_default(alpha, "Max", "1.0")
    bp.connect(alpha_raw, "ReturnValue", alpha, "Value")
    result_raw = compiler.call("qslerp", 10528, 1760)
    bp.connect(canonical_previous, "AirframePrebakeScratchCanonicalPreviousQuatV1", result_raw, "A")
    bp.connect(aligned, "AirframePrebakeScratchAlignedDesiredQuatV1", result_raw, "B")
    bp.connect(alpha, "ReturnValue", result_raw, "Alpha")
    result = compiler.call("qnormalize", 10784, 1760)
    bp.connect(result_raw, "ReturnValue", result, "Q")
    delta_positive = compare(
        "Greater_DoubleDouble", delta, "AirframePrebakeScratchDeltaSecondsV1",
        9568, 2400, default_b="0.0"
    )
    safe_delta = compiler.call("select", 9792, 2400)
    bp.connect(delta, "AirframePrebakeScratchDeltaSecondsV1", safe_delta, "A")
    scalar.set_default(safe_delta, "B", "1.0")
    bp.connect(delta_positive, "ReturnValue", safe_delta, "bPickA")
    unlimited_rate = compiler.math("Divide_DoubleDouble", 10048, 2240)
    bp.connect(angular_degrees, "ReturnValue", unlimited_rate, "A")
    bp.connect(safe_delta, "ReturnValue", unlimited_rate, "B")
    selected_rate = compiler.call("select", 10528, 2240)
    bp.connect(maximum, "AirframePrebakeScratchMaximumRateDegreesPerSecondV1", selected_rate, "A")
    bp.connect(unlimited_rate, "ReturnValue", selected_rate, "B")
    bp.connect(limited, "ReturnValue", selected_rate, "bPickA")

    store_quat = compiler.qset("AirframePrebakeScratchResultQuatV1", 11040, 4000)
    store_rate = builder.set("AirframePrebakeScratchResultAngularRateDegreesPerSecondV1", "real", 11296, 4000)
    store_limited = builder.set("AirframePrebakeScratchResultRateLimitedV1", "bool", 11552, 4000)
    store_valid = builder.set("AirframePrebakeScratchResultValidV1", "bool", 11808, 4000, "true")
    bp.connect(aligned_set, "then", store_quat, "execute")
    bp.connect(store_quat, "then", store_rate, "execute")
    bp.connect(store_rate, "then", store_limited, "execute")
    bp.connect(store_limited, "then", store_valid, "execute")
    bp.connect(result, "ReturnValue", store_quat, "AirframePrebakeScratchResultQuatV1")
    bp.connect(selected_rate, "ReturnValue", store_rate, "AirframePrebakeScratchResultAngularRateDegreesPerSecondV1")
    bp.connect(limited, "ReturnValue", store_limited, "AirframePrebakeScratchResultRateLimitedV1")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
