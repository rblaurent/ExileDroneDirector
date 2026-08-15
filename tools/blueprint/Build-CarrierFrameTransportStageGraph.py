"""Build the source-validity-gated carrier-frame transport input snapshot."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageCarrierFrameTransportInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_stage_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", f"PinType.ContainerType={'Array' if array else 'None'}", line, 1)

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
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, "real" if kind == "vector" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_value(name: str, kind: str, x: int, y: int, default=None, array: bool = False):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind, array)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    source_valid = get("AirframeDesiredStreamCompileValidV1", "bool", 0, 0)
    source_positions = get("AirframeDesiredStreamInputPositionsV1", "vector", 0, 192, True)
    source_total = get("AirframeDesiredStreamInputTotalSecondsV1", "real", 0, 384)
    source_step = get("AirframeDesiredStreamInputFixedStepSecondsV1", "real", 0, 576)

    invalidate = set_value("CarrierFrameStageValidV1", "bool", 256, 1024, "false")
    clear_failure = set_value("CarrierFrameFailureCodeV1", "string", 576, 1024, "")
    guard = builder.add("source_guard", "branch", 896, 1024)
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", guard, "execute")
    bp.connect(source_valid, "AirframeDesiredStreamCompileValidV1", guard, "Condition")

    set_positions = set_value("CarrierFrameInputPositionsV1", "vector", 1152, 1024, array=True)
    set_total = set_value("CarrierFrameInputTotalSecondsV1", "real", 1536, 1024)
    set_step = set_value("CarrierFrameInputFixedStepSecondsV1", "real", 1920, 1024)
    publish = set_value("CarrierFrameStageValidV1", "bool", 2304, 1024, "true")
    bp.connect(source_positions, "AirframeDesiredStreamInputPositionsV1", set_positions, "CarrierFrameInputPositionsV1")
    bp.connect(source_total, "AirframeDesiredStreamInputTotalSecondsV1", set_total, "CarrierFrameInputTotalSecondsV1")
    bp.connect(source_step, "AirframeDesiredStreamInputFixedStepSecondsV1", set_step, "CarrierFrameInputFixedStepSecondsV1")
    bp.connect(guard, "then", set_positions, "execute")
    bp.connect(set_positions, "then", set_total, "execute")
    bp.connect(set_total, "then", set_step, "execute")
    bp.connect(set_step, "then", publish, "execute")

    failure = set_value("CarrierFrameFailureCodeV1", "string", 1152, 1264, "source_invalid")
    bp.connect(guard, "else", failure, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text)
            for node in builder.nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
