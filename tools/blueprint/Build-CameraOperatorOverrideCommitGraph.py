"""Build atomic publication of one complete viewer-local operator frame."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCameraOperatorOverrideV1"
MODES = ("directed", "free_look", "carrier_freecam")
VECTORS = (
    "CameraOperatorCandidateTranslationOffsetV1", "CameraOperatorCandidateTranslationVelocityV1",
    "CameraOperatorCandidateAngularVelocityV1", "CameraOperatorCandidatePositionV1",
)
QUATS = (
    "CameraOperatorCandidateLookOffsetQuatV1", "CameraOperatorCandidateBodyQuatV1",
    "CameraOperatorCandidateGimbalQuatV1",
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_operator_commit_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str) -> None:
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
    node.mutate_pin(pin_name, mutate)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    vector_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    quat_forms = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    forms.update(
        break_vector=bp.find_block(vector_forms, r'MemberName="BreakVector"'),
        quat_finite=bp.find_block(quat_forms, r'MemberName="Quat_IsFinite"'),
        quat_size=bp.find_block(quat_compiler, r'MemberName="Quat_Size"'),
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
    def combine(conditions, x: int, y: int):
        current, current_pin = conditions[0]
        for index, (condition, condition_pin) in enumerate(conditions[1:]):
            node = b.add(f"BooleanAND_{len(b.nodes)}", "compare", x + index * 208, y); scalar.retarget_function(node, "BooleanAND")
            for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
            bp.connect(current, current_pin, node, "A"); bp.connect(condition, condition_pin, node, "B"); current, current_pin = node, "ReturnValue"
        return current, current_pin

    validation = get("CameraOperatorValidationValidV1", "bool", 0, 0)
    scratch = get("CameraOperatorScratchValidV1", "bool", 0, 160)
    candidate_valid = get("CameraOperatorCandidateValidV1", "bool", 0, 320)
    upstream = combine(((validation, "CameraOperatorValidationValidV1"), (scratch, "CameraOperatorScratchValidV1"), (candidate_valid, "CameraOperatorCandidateValidV1")), 320, 160)
    invalidate = set_("CameraOperatorResultValidV1", "bool", 256, 4400, default="false")
    upstream_guard = b.add("upstream_guard", "branch", 768, 4400); bp.connect(b.entry, "then", invalidate, "execute"); bp.connect(invalidate, "then", upstream_guard, "execute"); bp.connect(upstream[0], upstream[1], upstream_guard, "Condition")

    conditions = []
    mode = get("CameraOperatorCandidateModeV1", "string", 0, 576)
    mode_flags = [compare("EqualEqual_StrStr", mode, "CameraOperatorCandidateModeV1", value, "string", 320 + index * 208, 576) for index, value in enumerate(MODES)]
    mode_valid = mode_flags[0]
    for index, flag in enumerate(mode_flags[1:]):
        node = b.add(f"BooleanOR_{len(b.nodes)}", "compare", 944 + index * 208, 576); scalar.retarget_function(node, "BooleanOR")
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(mode_valid, "ReturnValue", node, "A"); bp.connect(flag, "ReturnValue", node, "B"); mode_valid = node
    conditions.append((mode_valid, "ReturnValue"))

    sources = {}
    for index, name in enumerate(VECTORS):
        y = 896 + index * 592; source = get(name, "vector", 0, y); sources[name] = source
        split = add_form(f"break_{name}", "break_vector", 320, y); pin_kind(split, "InVec", "vector"); bp.connect(source, name, split, "InVec")
        for component_index, component in enumerate(("X", "Y", "Z")):
            pin_kind(split, component, "real"); finite = b.finite(split, component, 640, y + component_index * 144); conditions.append((finite, "ReturnValue"))
    for index, name in enumerate(QUATS):
        y = 3264 + index * 480; source = get(name, "quat", 2048, y); sources[name] = source
        finite = add_form(f"finite_{name}", "quat_finite", 2368, y); pin_kind(finite, "Q", "quat"); pin_kind(finite, "ReturnValue", "bool"); bp.connect(source, name, finite, "Q")
        size = add_form(f"size_{name}", "quat_size", 2368, y + 160); pin_kind(size, "Q", "quat"); pin_kind(size, "ReturnValue", "real"); bp.connect(source, name, size, "Q")
        lower = compare("GreaterEqual_DoubleDouble", size, "ReturnValue", "0.999999", "real", 2592, y + 112)
        upper = compare("LessEqual_DoubleDouble", size, "ReturnValue", "1.000001", "real", 2816, y + 256)
        conditions.extend(((finite, "ReturnValue"), (lower, "ReturnValue"), (upper, "ReturnValue")))
    shape_valid = combine(conditions, 4096, 3600)
    shape_guard = b.add("shape_guard", "branch", 1024, 4400); bp.connect(upstream_guard, "then", shape_guard, "execute"); bp.connect(shape_valid[0], shape_valid[1], shape_guard, "Condition")
    poison_failure = set_("CameraOperatorFailureCodeV1", "string", 1280, 4592, default="candidate_invalid"); bp.connect(shape_guard, "else", poison_failure, "execute")

    recenter = get("CameraOperatorCandidateRecenterActiveV1", "bool", 2048, 4800); sources["CameraOperatorCandidateRecenterActiveV1"] = recenter
    override = get("CameraOperatorCandidateOverrideActiveV1", "bool", 2048, 4960); sources["CameraOperatorCandidateOverrideActiveV1"] = override
    transition = get("CameraOperatorCandidateTransitionActiveV1", "bool", 2048, 5120); sources["CameraOperatorCandidateTransitionActiveV1"] = transition
    tether = get("CameraOperatorCandidateTetherAppliedV1", "bool", 2048, 5280); sources["CameraOperatorCandidateTetherAppliedV1"] = tether
    success_failure = set_("CameraOperatorFailureCodeV1", "string", 1280, 4400, default="")
    publications = [
        success_failure,
        set_("CameraOperatorStateInitializedV1", "bool", 1536, 4400, default="true"),
        set_("CameraOperatorStateModeV1", "string", 1792, 4400, mode, "CameraOperatorCandidateModeV1"),
        set_("CameraOperatorStateRecenterActiveV1", "bool", 2048, 4400, recenter, "CameraOperatorCandidateRecenterActiveV1"),
        set_("CameraOperatorStateTranslationOffsetV1", "vector", 2304, 4400, sources["CameraOperatorCandidateTranslationOffsetV1"], "CameraOperatorCandidateTranslationOffsetV1"),
        set_("CameraOperatorStateTranslationVelocityV1", "vector", 2560, 4400, sources["CameraOperatorCandidateTranslationVelocityV1"], "CameraOperatorCandidateTranslationVelocityV1"),
        set_("CameraOperatorStateLookOffsetQuatV1", "quat", 2816, 4400, sources["CameraOperatorCandidateLookOffsetQuatV1"], "CameraOperatorCandidateLookOffsetQuatV1"),
        set_("CameraOperatorStateAngularVelocityV1", "vector", 3072, 4400, sources["CameraOperatorCandidateAngularVelocityV1"], "CameraOperatorCandidateAngularVelocityV1"),
        set_("CameraOperatorResultPositionV1", "vector", 3328, 4400, sources["CameraOperatorCandidatePositionV1"], "CameraOperatorCandidatePositionV1"),
        set_("CameraOperatorResultBodyQuatV1", "quat", 3584, 4400, sources["CameraOperatorCandidateBodyQuatV1"], "CameraOperatorCandidateBodyQuatV1"),
        set_("CameraOperatorResultGimbalQuatV1", "quat", 3840, 4400, sources["CameraOperatorCandidateGimbalQuatV1"], "CameraOperatorCandidateGimbalQuatV1"),
        set_("CameraOperatorResultModeV1", "string", 4096, 4400, mode, "CameraOperatorCandidateModeV1"),
        set_("CameraOperatorResultOverrideActiveV1", "bool", 4352, 4400, override, "CameraOperatorCandidateOverrideActiveV1"),
        set_("CameraOperatorResultTransitionActiveV1", "bool", 4608, 4400, transition, "CameraOperatorCandidateTransitionActiveV1"),
        set_("CameraOperatorResultTetherAppliedV1", "bool", 4864, 4400, tether, "CameraOperatorCandidateTetherAppliedV1"),
        set_("CameraOperatorResultValidV1", "bool", 5120, 4400, default="true"),
    ]
    bp.connect(shape_guard, "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]): bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
