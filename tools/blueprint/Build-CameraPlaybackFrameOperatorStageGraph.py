"""Validate one four-source frame and stage distinct camera-operator inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "StageCameraOperatorFromPlaybackV1"
COMPILE_VALID = (
    "CinematicPoseCompileValidV1", "AirframePrebakeCompileValidV1",
    "CarrierFrameCompileValidV1", "CameraChannelCompileValidV1",
)
RESULT_VALID = (
    "CinematicPoseResultValidV1", "AirframePrebakeResultValidV1",
    "CarrierFrameResultValidV1", "CameraChannelResultValidV1",
)
TOTALS = (
    "CinematicPoseCompiledTotalSecondsV1", "AirframePrebakeCompiledTotalSecondsV1",
    "CarrierFrameCompiledTotalSecondsV1", "CameraChannelCompiledDurationV1",
)
COMPLETE = (
    "CinematicPoseResultCompleteV1", "AirframePrebakeResultCompleteV1",
    "CarrierFrameResultCompleteV1", "CameraChannelResultCompleteV1",
)
COPIES = (
    ("CameraPlaybackInputRequestedModeV1", "CameraOperatorInputRequestedModeV1", "string"),
    ("CinematicPoseResultPositionV1", "CameraOperatorInputAuthoredPositionV1", "vector"),
    ("AirframePrebakeResultBodyQuatV1", "CameraOperatorInputAuthoredBodyQuatV1", "quat"),
    ("AirframePrebakeResultGimbalQuatV1", "CameraOperatorInputAuthoredGimbalQuatV1", "quat"),
    ("CarrierFrameResultQuatV1", "CameraOperatorInputCarrierFrameQuatV1", "quat"),
    ("CameraPlaybackInputTranslationV1", "CameraOperatorInputTranslationV1", "vector"),
    ("CameraPlaybackInputLookV1", "CameraOperatorInputLookV1", "vector"),
    ("CameraPlaybackInputDeltaSecondsV1", "CameraOperatorInputDeltaSecondsV1", "real"),
    ("CameraPlaybackInputRecenterRequestedV1", "CameraOperatorInputRecenterRequestedV1", "bool"),
    ("CameraPlaybackInputReturnToDirectedRequestedV1", "CameraOperatorInputReturnToDirectedRequestedV1", "bool"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_operator_stage_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "real": ("real", "double", "None"),
        "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", "PinType.ContainerType=None", line, 1)

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

    def variable(node, name: str, kind: str) -> None:
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else kind)
        pin_kind(node, name, kind)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name: str, kind: str, x: int, y: int):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind)
        return node

    def set_(name: str, kind: str, x: int, y: int, default: str | None = None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def compare(member_name: str, left, left_pin: str, right, right_pin: str, kind: str, x: int, y: int):
        node = builder.add(f"{member_name}_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member_name)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B")
        return node

    def positive(source, source_pin: str, x: int, y: int):
        node = builder.add(f"positive_{len(builder.nodes)}", "compare", x, y)
        scalar.retarget_function(node, "Greater_DoubleDouble")
        for pin in ("A", "B"):
            pin_kind(node, pin, "real")
        pin_kind(node, "ReturnValue", "bool")
        scalar.set_default(node, "B", "0.0")
        bp.connect(source, source_pin, node, "A")
        return node

    def and_all(conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            node = builder.add(f"and_{len(builder.nodes)}", "compare", x + index * 208, y)
            scalar.retarget_function(node, "BooleanAND")
            for pin in ("A", "B", "ReturnValue"):
                pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A")
            bp.connect(condition, condition_pin, node, "B")
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    stage = get("CameraPlaybackStageValidV1", "bool", 0, 0)
    compile_valid = [get(name, "bool", 0, 192 + index * 128) for index, name in enumerate(COMPILE_VALID)]
    result_valid = [get(name, "bool", 0, 768 + index * 128) for index, name in enumerate(RESULT_VALID)]
    ready = and_all(
        [(node, name) for node, name in zip(compile_valid, COMPILE_VALID)]
        + [(node, name) for node, name in zip(result_valid, RESULT_VALID)],
        384, 576,
    )

    totals = [get(name, "real", 0, 1408 + index * 320) for index, name in enumerate(TOTALS)]
    timeline_conditions = []
    for index, (node, name) in enumerate(zip(totals, TOTALS)):
        timeline_conditions.append((builder.finite(node, name, 384, 1408 + index * 320), "ReturnValue"))
        timeline_conditions.append((positive(node, name, 1008, 1408 + index * 320), "ReturnValue"))
    for index, node in enumerate(totals[1:]):
        timeline_conditions.append((compare(
            "EqualEqual_DoubleDouble", totals[0], TOTALS[0], node, TOTALS[index + 1],
            "real", 1232 + index * 208, 2688,
        ), "ReturnValue"))
    timeline = and_all(timeline_conditions, 1856, 2688)

    completions = [get(name, "bool", 0, 3008 + index * 160) for index, name in enumerate(COMPLETE)]
    completion_conditions = [
        (compare(
            "EqualEqual_BoolBool", completions[0], COMPLETE[0], node, COMPLETE[index + 1],
            "bool", 384 + index * 208, 3488,
        ), "ReturnValue")
        for index, node in enumerate(completions[1:])
    ]
    completion = and_all(completion_conditions, 1024, 3488)

    sources = {}
    for index, (source_name, _target_name, kind) in enumerate(COPIES):
        sources[source_name] = get(source_name, kind, 0, 3808 + index * 160)

    invalidate_sources = set_("CameraPlaybackSourcesValidV1", "bool", 896, 5760, "false")
    invalidate_operator = set_("CameraPlaybackOperatorStageValidV1", "bool", 1152, 5760, "false")
    invalidate_input = set_("CameraOperatorInputSourceValidV1", "bool", 1408, 5760, "false")
    stage_guard = builder.add("stage_guard", "branch", 1664, 5760)
    ready_guard = builder.add("ready_guard", "branch", 1920, 5760)
    timeline_guard = builder.add("timeline_guard", "branch", 2176, 5760)
    completion_guard = builder.add("completion_guard", "branch", 2432, 5760)
    bp.connect(builder.entry, "then", invalidate_sources, "execute")
    bp.connect(invalidate_sources, "then", invalidate_operator, "execute")
    bp.connect(invalidate_operator, "then", invalidate_input, "execute")
    bp.connect(invalidate_input, "then", stage_guard, "execute")
    bp.connect(stage, "CameraPlaybackStageValidV1", stage_guard, "Condition")
    bp.connect(stage_guard, "then", ready_guard, "execute")
    bp.connect(ready[0], ready[1], ready_guard, "Condition")
    bp.connect(ready_guard, "then", timeline_guard, "execute")
    bp.connect(timeline[0], timeline[1], timeline_guard, "Condition")
    bp.connect(timeline_guard, "then", completion_guard, "execute")
    bp.connect(completion[0], completion[1], completion_guard, "Condition")

    source_failure = set_("CameraPlaybackFailureCodeV1", "string", 2176, 6000, "source_invalid")
    timeline_failure = set_("CameraPlaybackFailureCodeV1", "string", 2432, 6080, "timeline_mismatch")
    completion_failure = set_("CameraPlaybackFailureCodeV1", "string", 2688, 6160, "completion_mismatch")
    bp.connect(ready_guard, "else", source_failure, "execute")
    bp.connect(timeline_guard, "else", timeline_failure, "execute")
    bp.connect(completion_guard, "else", completion_failure, "execute")

    clear_failure = set_("CameraPlaybackFailureCodeV1", "string", 2688, 5760, "")
    publish_sources = set_("CameraPlaybackSourcesValidV1", "bool", 2944, 5760, "true")
    bp.connect(completion_guard, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", publish_sources, "execute")
    copy_setters = []
    for index, (source_name, target_name, kind) in enumerate(COPIES):
        setter = set_(target_name, kind, 3200 + index * 256, 5760)
        bp.connect(sources[source_name], source_name, setter, target_name)
        copy_setters.append(setter)
    bp.connect(publish_sources, "then", copy_setters[0], "execute")
    for left, right in zip(copy_setters, copy_setters[1:]):
        bp.connect(left, "then", right, "execute")
    publish_operator = set_("CameraPlaybackOperatorStageValidV1", "bool", 5760, 5760, "true")
    publish_input = set_("CameraOperatorInputSourceValidV1", "bool", 6016, 5760, "true")
    bp.connect(copy_setters[-1], "then", publish_operator, "execute")
    bp.connect(publish_operator, "then", publish_input, "execute")

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
