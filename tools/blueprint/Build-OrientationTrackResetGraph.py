"""Build the fail-closed candidate/result reset for orientation track assembly."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetOrientationTrackCandidateV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
ARRAYS = (
    ("OrientationTrackCandidateAlignedQuatsV1", "quat"),
    ("OrientationTrackCandidateForwardDeltasV1", "vector"),
    ("OrientationTrackCandidateTangentRatesV1", "vector"),
    ("OrientationTrackCandidateSegmentStartsV1", "real"),
    ("OrientationTrackCandidateStartControlsV1", "quat"),
    ("OrientationTrackCandidateEndControlsV1", "quat"),
    ("OrientationTrackCompiledAlignedQuatsV1", "quat"),
    ("OrientationTrackCompiledDurationsV1", "real"),
    ("OrientationTrackCompiledTangentRatesV1", "vector"),
    ("OrientationTrackCompiledSegmentStartsV1", "real"),
    ("OrientationTrackCompiledStartControlsV1", "quat"),
    ("OrientationTrackCompiledEndControlsV1", "quat"),
)
SCALARS = (
    ("OrientationTrackCandidateTotalSecondsV1", "real", "0.0"),
    ("OrientationTrackStageValidV1", "bool", "false"),
    ("OrientationTrackCompiledTotalSecondsV1", "real", "0.0"),
    ("OrientationTrackCompileValidV1", "bool", "false"),
    ("OrientationTrackResultSegmentIndexV1", "int", "-1"),
    ("OrientationTrackResultAlphaV1", "real", "0.0"),
    ("OrientationTrackResultQuatV1", "quat", "0, 0, 0, 1"),
    ("OrientationTrackResultCompleteV1", "bool", "false"),
    ("OrientationTrackResultValidV1", "bool", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_orientation_track_reset_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]
    def mutate(line):
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1)
        line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1)
        line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
    node.mutate_pin(pin_name, mutate)


def variable(node, old, new, kind, array=False):
    node.text=re.sub(rf'VariableReference=\(MemberName="{old}"[^)]*\)',f'VariableReference=(MemberName="{new}",bSelfContext=True)',node.text,1)
    node.text=node.text.replace(f'PinName="{old}"',f'PinName="{new}"'); node.pins[new]=node.pins.pop(old)
    pin_kind(node,new,kind,array)
    if "Output_Get" in node.pins: pin_kind(node,"Output_Get",kind)


def default(node, pin, value):
    node.mutate_pin(pin,lambda line: re.sub(r'DefaultValue="[^"]*"',f'DefaultValue="{value}"',line,1) if "DefaultValue=" in line else line.replace(",PersistentGuid=",f',DefaultValue="{value}",PersistentGuid=',1))


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args()
    bp=load(a.project_root);bp.TARGET_ASSET=TARGET;bp.TARGET_GRAPH=FUNCTION
    capture=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    sync=bp.read_blocks(a.project_root/"tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph")
    start=bp.read_blocks(a.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph")
    qlive=bp.read_blocks(a.project_root/"tools/blueprint/live-snippets/evaluate-spherical-bezier-quaternion-v1.eddgraph")
    entry_form=bp.find_block(capture,r"K2Node_FunctionEntry")
    array_form=bp.find_block(sync,r'MemberName="DraftWaypointIds"')
    clear_form=bp.find_block(sync,r'MemberName="Array_Clear"')
    setter_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    qsetter_form=bp.find_block(qlive,r'K2Node_VariableSet.*MemberName="TrajectoryResultOrientationQuatV1"')
    nodes=[]
    entry=bp.Node.clone("entry",entry_form,"K2Node_FunctionEntry_0",0,0);entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1);nodes.append(entry)
    chain=[]
    for index,(name,kind) in enumerate(ARRAYS):
        getter=bp.Node.clone(f"get{index}",array_form,f"K2Node_VariableGet_{index}",256+index*416,256);variable(getter,"DraftWaypointIds",name,kind,True);nodes.append(getter)
        clear=bp.Node.clone(f"clear{index}",clear_form,f"K2Node_CallArrayFunction_{index}",256+index*416,0);pin_kind(clear,"TargetArray",kind,True);nodes.append(clear)
        bp.connect(getter,name,clear,"TargetArray");chain.append(clear)
    for index,(name,kind,value) in enumerate(SCALARS):
        form=qsetter_form if kind=="quat" else setter_form
        old="TrajectoryResultOrientationQuatV1" if kind=="quat" else "PlaybackActive"
        setter=bp.Node.clone(f"set{index}",form,f"K2Node_VariableSet_{index}",256+(len(ARRAYS)+index)*416,0);variable(setter,old,name,kind);default(setter,name,value);nodes.append(setter);chain.append(setter)
    bp.connect(entry,"then",chain[0],"execute")
    for left,right in zip(chain,chain[1:]):bp.connect(left,"then",right,"execute")
    full="\n".join(node.text for node in nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in nodes[1:]]
        a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")


if __name__=="__main__":main()
