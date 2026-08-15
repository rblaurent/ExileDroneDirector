"""Atomically publish one complete camera-playback frame."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCameraPlaybackFrameV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_playback_commit_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
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
    templates = args.project_root / "tools/blueprint/templates"
    edit = bp.read_blocks(templates / "waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    quat_eval = bp.read_blocks(templates / "trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(templates / "orientation-compiler-native-node-forms.eddgraph")
    quat_break = bp.read_blocks(templates / "repository-codec-break-quat-node-form.eddgraph")
    vector = bp.read_blocks(templates / "repository-codec-vector-node-forms.eddgraph")
    forms.update(
        length=bp.find_block(edit, r'MemberName="Array_Length"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        quat_finite=bp.find_block(quat_eval, r'MemberName="Quat_IsFinite"'),
        quat_size=bp.find_block(quat_compiler, r'MemberName="Quat_Size"'),
        quat_inverse=bp.find_block(quat_compiler, r'MemberName="Quat_Inversed"'),
        quat_multiply=bp.find_block(quat_compiler, r'MemberName="Multiply_QuatQuat"'),
        break_quat=bp.find_block(quat_break, r'MemberName="BreakQuat"'),
        break_vector=bp.find_block(vector, r'MemberName="BreakVector"'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def add_form(key: str, form: str, x: int, y: int):
        match = bp.BLOCK_RE.match(forms[form])
        cls = match.group("class").rsplit(".", 1)[-1]
        index = builder.serial.get(cls, 0)
        builder.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y)
        builder.nodes.append(node)
        return node

    def variable(node, name: str, kind: str, array: bool = False) -> None:
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind))
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name: str, kind: str, x: int, y: int, array: bool = False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name: str, kind: str, x: int, y: int, source=None, source_pin: str | None = None,
             default: str | None = None, array: bool = False):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind, array)
        if source is not None:
            bp.connect(source, source_pin, node, name)
        elif default is not None:
            scalar.set_default(node, name, default)
        return node

    def retarget(node, member_name: str, kinds: dict[str, str]):
        scalar.retarget_function(node, member_name)
        if member_name in ("EqualEqual_StrStr", "NotEqual_StrStr"):
            node.text = node.text.replace("KismetMathLibrary", "KismetStringLibrary")
        for pin_name, kind in kinds.items():
            pin_kind(node, pin_name, kind)
        return node

    def compare(member_name: str, left, left_pin: str, x: int, y: int, kind: str,
                right=None, right_pin: str | None = None, default: str | None = None):
        node = builder.add(f"cmp_{member_name}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, member_name, {"A": kind, "B": kind, "ReturnValue": "bool"})
        bp.connect(left, left_pin, node, "A")
        if right is not None:
            bp.connect(right, right_pin, node, "B")
        else:
            scalar.set_default(node, "B", default)
        return node

    def and_all(items, x: int, y: int):
        current, current_pin = items[0]
        for index, (other, other_pin) in enumerate(items[1:]):
            node = compare("BooleanAND", current, current_pin, x + index * 208, y, "bool", other, other_pin)
            current, current_pin = node, "ReturnValue"
        return current, current_pin

    def length(source, source_pin: str, x: int, y: int):
        node = add_form(f"length_{len(builder.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", "real", True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def item(source, source_pin: str, index: int, x: int, y: int):
        node = add_form(f"item_{source_pin}_{index}", "item", x, y)
        pin_kind(node, "Array", "real", True)
        pin_kind(node, "Output", "real")
        scalar.set_default(node, "Dimension 1", str(index))
        bp.connect(source, source_pin, node, "Array")
        return node

    # Accepted boundary authority and values.  Body and gimbal deliberately come
    # from different accepted helpers; no cinematic rotation is read here.
    stage = get("CameraPlaybackComfortStageValidV1", "bool", 0, 0)
    operator_valid = get("CameraOperatorResultValidV1", "bool", 0, 160)
    comfort_valid = get("CameraComfortResultValidV1", "bool", 0, 320)
    channels_valid = get("CameraChannelResultValidV1", "bool", 0, 480)
    position = get("CameraComfortResultPositionV1", "vector", 0, 720)
    body = get("CameraOperatorResultBodyQuatV1", "quat", 0, 960)
    gimbal = get("CameraComfortResultGimbalQuatV1", "quat", 0, 1200)
    preset = get("CameraChannelResultFilmbackPresetIdV1", "string", 0, 1440)
    width = get("CameraChannelResultFilmbackSensorWidthMmV1", "real", 0, 1600)
    height = get("CameraChannelResultFilmbackSensorHeightMmV1", "real", 0, 1760)
    channels = get("CameraComfortResultChannelValuesV1", "real", 0, 2000, True)
    complete = get("CameraChannelResultCompleteV1", "bool", 0, 2160)
    mode = get("CameraOperatorResultModeV1", "string", 0, 2320)
    override = get("CameraOperatorResultOverrideActiveV1", "bool", 0, 2480)
    transition = get("CameraOperatorResultTransitionActiveV1", "bool", 0, 2640)
    tether = get("CameraOperatorResultTetherAppliedV1", "bool", 0, 2800)
    weights = get("CameraComfortResultEffectiveWeightsV1", "real", 0, 2960, True)
    comfort_applied = get("CameraComfortResultAppliedV1", "bool", 0, 3120)

    checks = [(stage, "CameraPlaybackComfortStageValidV1"), (operator_valid, "CameraOperatorResultValidV1"),
              (comfort_valid, "CameraComfortResultValidV1"), (channels_valid, "CameraChannelResultValidV1")]

    broken_position = add_form("break_position", "break_vector", 384, 720)
    pin_kind(broken_position, "InVec", "vector")
    bp.connect(position, "CameraComfortResultPositionV1", broken_position, "InVec")
    for index, axis in enumerate("XYZ"):
        pin_kind(broken_position, axis, "real")
        finite = builder.finite(broken_position, axis, 640, 720 + index * 128)
        checks.append((finite, "ReturnValue"))

    quat_nodes = {}
    for index, (label, source, source_pin) in enumerate((("body", body, "CameraOperatorResultBodyQuatV1"),
                                                         ("gimbal", gimbal, "CameraComfortResultGimbalQuatV1"))):
        y = 1120 + index * 480
        finite = add_form(f"{label}_finite", "quat_finite", 384, y)
        size = add_form(f"{label}_size", "quat_size", 384, y + 144)
        for node in (finite, size):
            pin_kind(node, "Q", "quat")
            bp.connect(source, source_pin, node, "Q")
        pin_kind(finite, "ReturnValue", "bool")
        pin_kind(size, "ReturnValue", "real")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", 640, y + 96, "real", default="0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", 864, y + 224, "real", default="1.000001")
        checks.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))
        quat_nodes[label] = source

    inverse = add_form("inverse_body", "quat_inverse", 1216, 1120)
    pin_kind(inverse, "Q", "quat"); pin_kind(inverse, "ReturnValue", "quat")
    bp.connect(body, "CameraOperatorResultBodyQuatV1", inverse, "Q")
    relative = add_form("relative_gimbal", "quat_multiply", 1472, 1120)
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(relative, pin, "quat")
    bp.connect(inverse, "ReturnValue", relative, "A")
    bp.connect(gimbal, "CameraComfortResultGimbalQuatV1", relative, "B")
    recomposed = add_form("recomposed_gimbal", "quat_multiply", 1728, 1120)
    for pin in ("A", "B", "ReturnValue"):
        pin_kind(recomposed, pin, "quat")
    bp.connect(body, "CameraOperatorResultBodyQuatV1", recomposed, "A")
    bp.connect(relative, "ReturnValue", recomposed, "B")

    for index, (label, source) in enumerate((("relative", relative), ("recomposed", recomposed))):
        y = 2080 + index * 352
        finite = add_form(f"{label}_finite", "quat_finite", 1216, y)
        size = add_form(f"{label}_size", "quat_size", 1216, y + 144)
        for node in (finite, size):
            pin_kind(node, "Q", "quat")
            bp.connect(source, "ReturnValue", node, "Q")
        pin_kind(finite, "ReturnValue", "bool"); pin_kind(size, "ReturnValue", "real")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", 1472, y + 96, "real", default="0.999999")
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", 1696, y + 224, "real", default="1.000001")
        checks.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))

    expected_break = add_form("break_expected_gimbal", "break_quat", 2048, 1120)
    actual_break = add_form("break_recomposed_gimbal", "break_quat", 2048, 1600)
    for node, source, pin in ((expected_break, gimbal, "CameraComfortResultGimbalQuatV1"),
                              (actual_break, recomposed, "ReturnValue")):
        pin_kind(node, "InQuat", "quat")
        for axis in "XYZW":
            pin_kind(node, axis, "real")
        bp.connect(source, pin, node, "InQuat")
    for index, axis in enumerate("XYZW"):
        delta = builder.add(f"reconstruction_delta_{axis}", "math", 2304, 1120 + index * 160)
        retarget(delta, "Subtract_DoubleDouble", {"A": "real", "B": "real", "ReturnValue": "real"})
        bp.connect(actual_break, axis, delta, "A"); bp.connect(expected_break, axis, delta, "B")
        lower = compare("GreaterEqual_DoubleDouble", delta, "ReturnValue", 2528, 1080 + index * 160, "real", default="-0.000001")
        upper = compare("LessEqual_DoubleDouble", delta, "ReturnValue", 2752, 1160 + index * 160, "real", default="0.000001")
        checks.extend(((lower, "ReturnValue"), (upper, "ReturnValue")))

    preset_ok = compare("NotEqual_StrStr", preset, "CameraChannelResultFilmbackPresetIdV1", 384, 3360, "string", default="")
    width_finite = builder.finite(width, "CameraChannelResultFilmbackSensorWidthMmV1", 384, 3520)
    width_positive = compare("Greater_DoubleDouble", width, "CameraChannelResultFilmbackSensorWidthMmV1", 608, 3520, "real", default="0.0")
    height_finite = builder.finite(height, "CameraChannelResultFilmbackSensorHeightMmV1", 384, 3680)
    height_positive = compare("Greater_DoubleDouble", height, "CameraChannelResultFilmbackSensorHeightMmV1", 608, 3680, "real", default="0.0")
    channel_length = length(channels, "CameraComfortResultChannelValuesV1", 384, 3920)
    channel_count = compare("EqualEqual_IntInt", channel_length, "ReturnValue", 608, 3920, "int", default="13")
    weight_length = length(weights, "CameraComfortResultEffectiveWeightsV1", 384, 4080)
    weight_count = compare("EqualEqual_IntInt", weight_length, "ReturnValue", 608, 4080, "int", default="5")
    checks.extend(((preset_ok, "ReturnValue"), (width_finite, "ReturnValue"), (width_positive, "ReturnValue"),
                   (height_finite, "ReturnValue"), (height_positive, "ReturnValue"),
                   (channel_count, "ReturnValue"), (weight_count, "ReturnValue")))

    for index in range(13):
        sample = item(channels, "CameraComfortResultChannelValuesV1", index, 896 + index * 192, 3920)
        finite = builder.finite(sample, "Output", 1088 + index * 192, 3920)
        checks.append((finite, "ReturnValue"))
    for index in range(5):
        sample = item(weights, "CameraComfortResultEffectiveWeightsV1", index, 896 + index * 384, 4240)
        finite = builder.finite(sample, "Output", 1088 + index * 384, 4240)
        lower = compare("GreaterEqual_DoubleDouble", sample, "Output", 1280 + index * 384, 4200, "real", default="0.0")
        upper = compare("LessEqual_DoubleDouble", sample, "Output", 1472 + index * 384, 4280, "real", default="1.0")
        checks.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))

    ready = and_all(checks, 3328, 4480)
    invalidate = set_("CameraPlaybackResultValidV1", "bool", 256, 5200, default="false")
    failure = set_("CameraPlaybackFailureCodeV1", "string", 512, 5200, default="commit_failed")
    guard = builder.add("commit_guard", "branch", 768, 5200)
    bp.connect(builder.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", failure, "execute")
    bp.connect(failure, "then", guard, "execute")
    bp.connect(ready[0], ready[1], guard, "Condition")

    publications = (
        set_("CameraPlaybackResultPositionV1", "vector", 1024, 5200, position, "CameraComfortResultPositionV1"),
        set_("CameraPlaybackResultBodyWorldQuatV1", "quat", 1280, 5200, body, "CameraOperatorResultBodyQuatV1"),
        set_("CameraPlaybackResultGimbalWorldQuatV1", "quat", 1536, 5200, gimbal, "CameraComfortResultGimbalQuatV1"),
        set_("CameraPlaybackResultGimbalRelativeQuatV1", "quat", 1792, 5200, relative, "ReturnValue"),
        set_("CameraPlaybackResultFilmbackPresetIdV1", "string", 2048, 5200, preset, "CameraChannelResultFilmbackPresetIdV1"),
        set_("CameraPlaybackResultFilmbackSensorWidthMmV1", "real", 2304, 5200, width, "CameraChannelResultFilmbackSensorWidthMmV1"),
        set_("CameraPlaybackResultFilmbackSensorHeightMmV1", "real", 2560, 5200, height, "CameraChannelResultFilmbackSensorHeightMmV1"),
        set_("CameraPlaybackResultChannelValuesV1", "real", 2816, 5200, channels, "CameraComfortResultChannelValuesV1", array=True),
        set_("CameraPlaybackResultCompleteV1", "bool", 3072, 5200, complete, "CameraChannelResultCompleteV1"),
        set_("CameraPlaybackResultModeV1", "string", 3328, 5200, mode, "CameraOperatorResultModeV1"),
        set_("CameraPlaybackResultOverrideActiveV1", "bool", 3584, 5200, override, "CameraOperatorResultOverrideActiveV1"),
        set_("CameraPlaybackResultTransitionActiveV1", "bool", 3840, 5200, transition, "CameraOperatorResultTransitionActiveV1"),
        set_("CameraPlaybackResultTetherAppliedV1", "bool", 4096, 5200, tether, "CameraOperatorResultTetherAppliedV1"),
        set_("CameraPlaybackResultComfortEffectiveWeightsV1", "real", 4352, 5200, weights, "CameraComfortResultEffectiveWeightsV1", array=True),
        set_("CameraPlaybackResultComfortAppliedV1", "bool", 4608, 5200, comfort_applied, "CameraComfortResultAppliedV1"),
        set_("CameraPlaybackFailureCodeV1", "string", 4864, 5200, default=""),
        set_("CameraPlaybackResultValidV1", "bool", 5120, 5200, default="true"),
    )
    bp.connect(guard, "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]):
        bp.connect(left, "then", right, "execute")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(node.text for node in builder.nodes) + "\n", encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in builder.nodes[1:]
        ) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
