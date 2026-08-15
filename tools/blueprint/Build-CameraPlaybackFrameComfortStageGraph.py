"""Stage the accepted operator view and raw channels into viewer comfort."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageCameraComfortFromPlaybackV1"
COPIES = (
    ("CameraOperatorResultPositionV1", "CameraComfortInputPositionV1", "vector", False),
    ("CameraOperatorResultGimbalQuatV1", "CameraComfortInputGimbalQuatV1", "quat", False),
    ("CameraPlaybackInputProceduralTranslationOffsetV1", "CameraComfortInputProceduralTranslationOffsetV1", "vector", False),
    ("CameraPlaybackInputProceduralRotationOffsetV1", "CameraComfortInputProceduralRotationOffsetV1", "quat", False),
    ("CameraChannelResultValuesV1", "CameraComfortInputChannelValuesV1", "real", True),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_comfort_stage_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
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
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name: str, kind: str, x: int, y: int, default: str | None = None, array: bool = False):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind, array)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def and_pair(left, left_pin: str, right, right_pin: str, x: int, y: int):
        node = builder.add(f"and_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"):
            pin_kind(node, pin, "bool")
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    operator_stage = get("CameraPlaybackOperatorStageValidV1", "bool", 0, 0)
    operator_result = get("CameraOperatorResultValidV1", "bool", 0, 160)
    sources_valid = get("CameraPlaybackSourcesValidV1", "bool", 0, 400)
    channels_valid = get("CameraChannelResultValidV1", "bool", 0, 560)
    operator_ready = and_pair(operator_stage, "CameraPlaybackOperatorStageValidV1", operator_result, "CameraOperatorResultValidV1", 320, 80)
    source_ready = and_pair(sources_valid, "CameraPlaybackSourcesValidV1", channels_valid, "CameraChannelResultValidV1", 320, 480)
    sources = {
        source_name: get(source_name, kind, 0, 880 + index * 192, array)
        for index, (source_name, _target, kind, array) in enumerate(COPIES)
    }

    invalidate_stage = set_("CameraPlaybackComfortStageValidV1", "bool", 640, 2080, "false")
    invalidate_input = set_("CameraComfortInputFrameValidV1", "bool", 896, 2080, "false")
    operator_guard = builder.add("operator_guard", "branch", 1152, 2080)
    source_guard = builder.add("source_guard", "branch", 1408, 2080)
    bp.connect(builder.entry, "then", invalidate_stage, "execute")
    bp.connect(invalidate_stage, "then", invalidate_input, "execute")
    bp.connect(invalidate_input, "then", operator_guard, "execute")
    bp.connect(operator_ready, "ReturnValue", operator_guard, "Condition")
    bp.connect(operator_guard, "then", source_guard, "execute")
    bp.connect(source_ready, "ReturnValue", source_guard, "Condition")
    operator_failure = set_("CameraPlaybackFailureCodeV1", "string", 1408, 2320, "operator_invalid")
    source_failure = set_("CameraPlaybackFailureCodeV1", "string", 1664, 2400, "source_invalid")
    bp.connect(operator_guard, "else", operator_failure, "execute")
    bp.connect(source_guard, "else", source_failure, "execute")

    clear_failure = set_("CameraPlaybackFailureCodeV1", "string", 1664, 2080, "")
    bp.connect(source_guard, "then", clear_failure, "execute")
    setters = []
    for index, (source_name, target_name, kind, array) in enumerate(COPIES):
        setter = set_(target_name, kind, 1920 + index * 256, 2080, array=array)
        bp.connect(sources[source_name], source_name, setter, target_name)
        setters.append(setter)
    bp.connect(clear_failure, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
        bp.connect(left, "then", right, "execute")
    publish_stage = set_("CameraPlaybackComfortStageValidV1", "bool", 3200, 2080, "true")
    publish_input = set_("CameraComfortInputFrameValidV1", "bool", 3456, 2080, "true")
    bp.connect(setters[-1], "then", publish_stage, "execute")
    bp.connect(publish_stage, "then", publish_input, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(
            re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", node.text)
            for node in builder.nodes[1:]
        ) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
