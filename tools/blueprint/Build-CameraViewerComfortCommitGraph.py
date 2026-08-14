"""Atomically publish one complete viewer-local comfort frame."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCameraViewerComfortV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"; spec = importlib.util.spec_from_file_location("edd_camera_comfort_commit_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def pin_kind(node, pin, kind, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"), "real": ("real", "double", "None"), "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1); line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1); return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path); args = parser.parse_args()
    scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph"); forms["length"] = bp.find_block(edit, r'MemberName="Array_Length"')
    b = scalar.Builder(bp, forms, FUNCTION)
    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(forms[form]); cls = match.group("class").rsplit(".", 1)[-1]; index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, forms[form], f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "vector" if kind == "quat" else ("real" if kind == "int" else kind)); pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind, array)
    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind, array); return node
    def set_(name, kind, x, y, source=None, source_pin=None, default=None, array=False):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind, array)
        if source is None: scalar.set_default(node, name, default)
        else: bp.connect(source, source_pin, node, name)
        return node
    def length(source, source_pin, x, y):
        node = add_form(f"length_{len(b.nodes)}", "length", x, y); pin_kind(node, "TargetArray", "real", True); pin_kind(node, "ReturnValue", "int"); bp.connect(source, source_pin, node, "TargetArray"); return node
    def compare(member, left, left_pin, x, y, kind, right=None, right_pin=None, default=None):
        node = b.add(f"{member}_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default)
        else: bp.connect(right, right_pin, node, "B")
        return node

    candidate_valid = get("CameraComfortCandidateValidV1", "bool", 0, 0)
    position = get("CameraComfortCandidatePositionV1", "vector", 0, 224)
    gimbal = get("CameraComfortCandidateGimbalQuatV1", "quat", 0, 448)
    channels = get("CameraComfortCandidateChannelValuesV1", "real", 0, 672, True)
    weights = get("CameraComfortCandidateEffectiveWeightsV1", "real", 0, 896, True)
    applied = get("CameraComfortCandidateAppliedV1", "bool", 0, 1120)
    channel_length = length(channels, "CameraComfortCandidateChannelValuesV1", 320, 672)
    weight_length = length(weights, "CameraComfortCandidateEffectiveWeightsV1", 320, 896)
    channels_exact = compare("EqualEqual_IntInt", channel_length, "ReturnValue", 544, 672, "int", default="13")
    weights_exact = compare("EqualEqual_IntInt", weight_length, "ReturnValue", 544, 896, "int", default="5")
    shape = compare("BooleanAND", channels_exact, "ReturnValue", 768, 784, "bool", weights_exact, "ReturnValue")
    ready = compare("BooleanAND", candidate_valid, "CameraComfortCandidateValidV1", 992, 784, "bool", shape, "ReturnValue")
    invalidate = set_("CameraComfortResultValidV1", "bool", 256, 2560, default="false")
    failure = set_("CameraComfortFailureCodeV1", "string", 480, 2560, default="commit_failed")
    guard = b.add("commit_guard", "branch", 1216, 2560); bp.connect(b.entry, "then", invalidate, "execute"); bp.connect(invalidate, "then", failure, "execute"); bp.connect(failure, "then", guard, "execute"); bp.connect(ready, "ReturnValue", guard, "Condition")
    publications = (
        set_("CameraComfortResultPositionV1", "vector", 1440, 2560, position, "CameraComfortCandidatePositionV1"),
        set_("CameraComfortResultGimbalQuatV1", "quat", 1664, 2560, gimbal, "CameraComfortCandidateGimbalQuatV1"),
        set_("CameraComfortResultChannelValuesV1", "real", 1888, 2560, channels, "CameraComfortCandidateChannelValuesV1", array=True),
        set_("CameraComfortResultEffectiveWeightsV1", "real", 2112, 2560, weights, "CameraComfortCandidateEffectiveWeightsV1", array=True),
        set_("CameraComfortResultAppliedV1", "bool", 2336, 2560, applied, "CameraComfortCandidateAppliedV1"),
        set_("CameraComfortFailureCodeV1", "string", 2560, 2560, default=""),
        set_("CameraComfortResultValidV1", "bool", 2784, 2560, default="true"),
    )
    bp.connect(guard, "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]): bp.connect(left, "then", right, "execute")
    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
