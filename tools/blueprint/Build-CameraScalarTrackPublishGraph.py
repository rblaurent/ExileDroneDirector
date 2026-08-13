"""Build atomic physical publication for one staged camera scalar sample."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

FUNCTION = "PublishCameraScalarTrackSampleV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_scalar_publish_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str) -> None:
    category, subcategory = {"bool": ("bool", ""), "real": ("real", "double"), "string": ("string", "")}[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', "PinType.ContainerType=None", line, 1)

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
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    forms["select"] = bp.find_block(public_list, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_Select ")
    builder = scalar.Builder(bp, forms, FUNCTION)

    def get(name: str, kind: str, x: int, y: int):
        node = builder.get(name, kind, x, y)
        pin_kind(node, name, kind)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)
        return node

    def set_(name: str, kind: str, x: int, y: int, default: str | None = None):
        node = builder.set(name, kind, x, y, default)
        pin_kind(node, name, kind)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)
        return node

    def operation(member: str, left, left_pin: str | None, x: int, y: int, right=None, right_pin: str | None = None, default_a: str | None = None, default_b: str | None = None, result: str = "real"):
        form = "compare" if result == "bool" else "math"
        node = builder.add(f"op_{member}_{len(builder.nodes)}", form, x, y)
        scalar.retarget_function(node, member)
        input_kind = "bool" if member in ("BooleanAND", "BooleanOR") else "real"
        for pin in ("A", "B"):
            pin_kind(node, pin, input_kind)
        pin_kind(node, "ReturnValue", result)
        if left is None:
            scalar.set_default(node, "A", default_a)
        else:
            bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default_b)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def and_all(values, x: int, y: int):
        current = values[0]
        for index, value in enumerate(values[1:]):
            current = operation("BooleanAND", current, "ReturnValue", x + index * 208, y, value, "ReturnValue", result="bool")
        return current

    def select(condition, false_source, false_pin: str | None, true_source, true_pin: str | None, x: int, y: int, false_default: str | None = None, true_default: str | None = None):
        node = builder.add(f"select_{len(builder.nodes)}", "select", x, y)
        pin_kind(node, "Index", "bool")
        for pin in ("Option 0", "Option 1", "ReturnValue"):
            pin_kind(node, pin, "real")
        if "ReturnValue" in condition.pins:
            condition_pin = "ReturnValue"
        else:
            match = re.search(r'VariableReference=\(MemberName="([^"]+)"', condition.text)
            if match is None:
                raise RuntimeError(f"No Boolean output pin on {condition.key}")
            condition_pin = match.group(1)
        bp.connect(condition, condition_pin, node, "Index")
        if false_source is None:
            scalar.set_default(node, "Option 0", false_default)
        else:
            bp.connect(false_source, false_pin, node, "Option 0")
        if true_source is None:
            scalar.set_default(node, "Option 1", true_default)
        else:
            bp.connect(true_source, true_pin, node, "Option 1")
        return node

    invalidate = set_("CameraScalarTrackResultValidV1", "bool", 256, 2400, "false")
    bp.connect(builder.entry, "then", invalidate, "execute")
    compile_valid = get("CameraScalarTrackCompileValidV1", "bool", 0, 0)
    scratch_valid = get("CameraScalarTrackScratchValidV1", "bool", 0, 128)
    domain = get("CameraScalarTrackInputDomainV1", "string", 0, 256)
    domain_value = get("CameraScalarTrackScratchDomainValueV1", "real", 0, 512)
    domain_velocity = get("CameraScalarTrackScratchDomainVelocityV1", "real", 0, 640)
    domain_acceleration = get("CameraScalarTrackScratchDomainAccelerationV1", "real", 0, 768)
    linear = builder.equal_string(256, 256, "linear")
    reciprocal = builder.equal_string(256, 384, "reciprocal")
    bp.connect(domain, "CameraScalarTrackInputDomainV1", linear, "A")
    bp.connect(domain, "CameraScalarTrackInputDomainV1", reciprocal, "A")
    positive = operation("Greater_DoubleDouble", domain_value, "CameraScalarTrackScratchDomainValueV1", 256, 512, default_b="0.0", result="bool")
    reciprocal_valid = operation("BooleanAND", reciprocal, "ReturnValue", 480, 384, positive, "ReturnValue", result="bool")
    domain_valid = operation("BooleanOR", linear, "ReturnValue", 688, 320, reciprocal_valid, "ReturnValue", result="bool")
    finite_value = builder.finite(domain_value, "CameraScalarTrackScratchDomainValueV1", 256, 768)
    finite_velocity = builder.finite(domain_velocity, "CameraScalarTrackScratchDomainVelocityV1", 256, 960)
    finite_acceleration = builder.finite(domain_acceleration, "CameraScalarTrackScratchDomainAccelerationV1", 256, 1152)

    safe_domain = select(reciprocal_valid, None, None, domain_value, "CameraScalarTrackScratchDomainValueV1", 912, 512, false_default="1.0")
    domain_squared = operation("Multiply_DoubleDouble", safe_domain, "ReturnValue", 1136, 512, safe_domain, "ReturnValue")
    domain_cubed = operation("Multiply_DoubleDouble", domain_squared, "ReturnValue", 1360, 512, safe_domain, "ReturnValue")
    reciprocal_value = operation("Divide_DoubleDouble", None, None, 1584, 512, safe_domain, "ReturnValue", default_a="1.0")
    negated_velocity = operation("Multiply_DoubleDouble", domain_velocity, "CameraScalarTrackScratchDomainVelocityV1", 1136, 672, default_b="-1.0")
    reciprocal_velocity = operation("Divide_DoubleDouble", negated_velocity, "ReturnValue", 1584, 672, domain_squared, "ReturnValue")
    velocity_squared = operation("Multiply_DoubleDouble", domain_velocity, "CameraScalarTrackScratchDomainVelocityV1", 1136, 832, domain_velocity, "CameraScalarTrackScratchDomainVelocityV1")
    twice_velocity_squared = operation("Multiply_DoubleDouble", velocity_squared, "ReturnValue", 1360, 832, default_b="2.0")
    acceleration_first = operation("Divide_DoubleDouble", twice_velocity_squared, "ReturnValue", 1584, 832, domain_cubed, "ReturnValue")
    acceleration_second = operation("Divide_DoubleDouble", domain_acceleration, "CameraScalarTrackScratchDomainAccelerationV1", 1584, 960, domain_squared, "ReturnValue")
    reciprocal_acceleration = operation("Subtract_DoubleDouble", acceleration_first, "ReturnValue", 1808, 896, acceleration_second, "ReturnValue")
    physical_value = select(reciprocal, domain_value, "CameraScalarTrackScratchDomainValueV1", reciprocal_value, "ReturnValue", 2032, 512)
    physical_velocity = select(reciprocal, domain_velocity, "CameraScalarTrackScratchDomainVelocityV1", reciprocal_velocity, "ReturnValue", 2032, 672)
    physical_acceleration = select(reciprocal, domain_acceleration, "CameraScalarTrackScratchDomainAccelerationV1", reciprocal_acceleration, "ReturnValue", 2032, 832)
    finite_physical_value = builder.finite(physical_value, "ReturnValue", 2256, 512)
    finite_physical_velocity = builder.finite(physical_velocity, "ReturnValue", 2256, 704)
    finite_physical_acceleration = builder.finite(physical_acceleration, "ReturnValue", 2256, 896)
    conditions = [compile_valid, scratch_valid, domain_valid, finite_value, finite_velocity, finite_acceleration, finite_physical_value, finite_physical_velocity, finite_physical_acceleration]
    condition_pins = ["CameraScalarTrackCompileValidV1", "CameraScalarTrackScratchValidV1"] + ["ReturnValue"] * 7
    normalized = []
    for source, pin in zip(conditions, condition_pins):
        if pin == "ReturnValue":
            normalized.append(source)
        else:
            wrapper = operation("BooleanAND", source, pin, 2752, 128 * len(normalized), default_b="true", result="bool")
            normalized.append(wrapper)
    guard_value = and_all(normalized, 2960, 640)
    guard = builder.add("publish_guard", "branch", 4624, 2400)
    bp.connect(invalidate, "then", guard, "execute")
    bp.connect(guard_value, "ReturnValue", guard, "Condition")

    has_minimum = get("CameraScalarTrackInputHasMinimumV1", "bool", 2752, 1344)
    minimum = get("CameraScalarTrackInputMinimumV1", "real", 2752, 1472)
    has_maximum = get("CameraScalarTrackInputHasMaximumV1", "bool", 2752, 1600)
    maximum = get("CameraScalarTrackInputMaximumV1", "real", 2752, 1728)
    clamp_output = get("CameraScalarTrackInputClampOutputV1", "bool", 2752, 1856)
    minimum_applied = operation("Max_DoubleDouble", physical_value, "ReturnValue", 3200, 1472, minimum, "CameraScalarTrackInputMinimumV1")
    after_minimum = select(has_minimum, physical_value, "ReturnValue", minimum_applied, "ReturnValue", 3424, 1472)
    maximum_applied = operation("Min_DoubleDouble", after_minimum, "ReturnValue", 3648, 1600, maximum, "CameraScalarTrackInputMaximumV1")
    after_maximum = select(has_maximum, after_minimum, "ReturnValue", maximum_applied, "ReturnValue", 3872, 1600)
    bounded_value = select(clamp_output, physical_value, "ReturnValue", after_maximum, "ReturnValue", 4096, 1536)
    below = operation("Less_DoubleDouble", physical_value, "ReturnValue", 3200, 1792, minimum, "CameraScalarTrackInputMinimumV1", result="bool")
    above = operation("Greater_DoubleDouble", physical_value, "ReturnValue", 3200, 1920, maximum, "CameraScalarTrackInputMaximumV1", result="bool")
    below_enabled = operation("BooleanAND", has_minimum, "CameraScalarTrackInputHasMinimumV1", 3424, 1792, below, "ReturnValue", result="bool")
    above_enabled = operation("BooleanAND", has_maximum, "CameraScalarTrackInputHasMaximumV1", 3424, 1920, above, "ReturnValue", result="bool")
    outside = operation("BooleanOR", below_enabled, "ReturnValue", 3648, 1856, above_enabled, "ReturnValue", result="bool")
    clamped = operation("BooleanAND", clamp_output, "CameraScalarTrackInputClampOutputV1", 3872, 1856, outside, "ReturnValue", result="bool")
    bounded_velocity = select(clamped, physical_velocity, "ReturnValue", None, None, 4096, 1792, true_default="0.0")
    bounded_acceleration = select(clamped, physical_acceleration, "ReturnValue", None, None, 4096, 1984, true_default="0.0")
    store_value = set_("CameraScalarTrackResultValueV1", "real", 4848, 2400)
    store_velocity = set_("CameraScalarTrackResultVelocityV1", "real", 5072, 2400)
    store_acceleration = set_("CameraScalarTrackResultAccelerationV1", "real", 5296, 2400)
    publish_valid = set_("CameraScalarTrackResultValidV1", "bool", 5520, 2400, "true")
    bp.connect(guard, "then", store_value, "execute")
    bp.connect(bounded_value, "ReturnValue", store_value, "CameraScalarTrackResultValueV1")
    bp.connect(store_value, "then", store_velocity, "execute")
    bp.connect(bounded_velocity, "ReturnValue", store_velocity, "CameraScalarTrackResultVelocityV1")
    bp.connect(store_velocity, "then", store_acceleration, "execute")
    bp.connect(bounded_acceleration, "ReturnValue", store_acceleration, "CameraScalarTrackResultAccelerationV1")
    bp.connect(store_acceleration, "then", publish_valid, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
