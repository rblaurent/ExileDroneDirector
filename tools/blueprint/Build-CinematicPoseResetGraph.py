"""Build the fail-closed combined cinematic-pose reset transaction."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetCinematicPoseV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
SCALARS = (
    ("CinematicPoseStageValidV1", "bool", "false"),
    ("CinematicPoseCompiledTotalSecondsV1", "real", "0.0"),
    ("CinematicPoseCompileValidV1", "bool", "false"),
    ("CinematicPoseResultSegmentIndexV1", "int", "-1"),
    ("CinematicPoseResultLocalTimeAlphaV1", "real", "0.0"),
    ("CinematicPoseResultDistanceAlphaV1", "real", "0.0"),
    ("CinematicPoseResultCurveUV1", "real", "0.0"),
    ("CinematicPoseResultPositionV1", "vector", "0, 0, 0"),
    ("CinematicPoseResultQuatV1", "quat", "0, 0, 0, 1"),
    ("CinematicPoseResultCompleteV1", "bool", "false"),
    ("CinematicPoseResultValidV1", "bool", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_cinematic_pose_reset_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"),
        "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        return re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)

    node.mutate_pin(pin_name, mutate)


def variable(node, old, new, kind):
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{old}"[^)]*\)',
        f'VariableReference=(MemberName="{new}",bSelfContext=True)',
        node.text,
        count=1,
    )
    node.text = node.text.replace(f'PinName="{old}"', f'PinName="{new}"')
    node.pins[new] = node.pins.pop(old)
    pin_kind(node, new, kind)


def default(node, pin, value):
    node.mutate_pin(
        pin,
        lambda line: re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, 1)
        if "DefaultValue=" in line
        else line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    bp = load(args.project_root)
    bp.TARGET_ASSET = TARGET
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    vector_live = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-quintic-vector-v1.eddgraph")
    quat_live = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/evaluate-spherical-bezier-quaternion-v1.eddgraph")
    entry_form = bp.find_block(capture, r"K2Node_FunctionEntry")
    scalar_form = bp.find_block(playback, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    vector_form = bp.find_block(vector_live, r'K2Node_VariableSet.*MemberName="TrajectoryResultPositionVectorV1"')
    quat_form = bp.find_block(quat_live, r'K2Node_VariableSet.*MemberName="TrajectoryResultOrientationQuatV1"')

    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(r'FunctionReference=\(MemberName="[^"]+"\)', f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1)
    nodes = [entry]
    setters = []
    for index, (name, kind, value) in enumerate(SCALARS):
        if kind == "vector":
            form, old = vector_form, "TrajectoryResultPositionVectorV1"
        elif kind == "quat":
            form, old = quat_form, "TrajectoryResultOrientationQuatV1"
        else:
            form, old = scalar_form, "PlaybackActive"
        setter = bp.Node.clone(f"set_{index}", form, f"K2Node_VariableSet_{index}", 256 + index * 384, 0)
        variable(setter, old, name, kind)
        default(setter, name, value)
        nodes.append(setter)
        setters.append(setter)
    bp.connect(entry, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
        bp.connect(left, "then", right, "execute")
    full = "\n".join(node.text for node in nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [
            re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text)
            for node in nodes[1:]
        ]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
