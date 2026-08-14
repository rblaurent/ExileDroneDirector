"""Build the fail-closed, state-preserving camera operator-step reset."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION="ResetCameraOperatorOverrideStepV1"
SCALARS=(
    ("CameraOperatorValidationValidV1","bool","false"),
    ("CameraOperatorCandidateModeV1","string","directed"),
    ("CameraOperatorCandidateRecenterActiveV1","bool","false"),
    ("CameraOperatorCandidateTranslationOffsetV1","vector","0, 0, 0"),
    ("CameraOperatorCandidateTranslationVelocityV1","vector","0, 0, 0"),
    ("CameraOperatorCandidateLookOffsetQuatV1","quat","0, 0, 0, 1"),
    ("CameraOperatorCandidateAngularVelocityV1","vector","0, 0, 0"),
    ("CameraOperatorCandidatePositionV1","vector","0, 0, 0"),
    ("CameraOperatorCandidateBodyQuatV1","quat","0, 0, 0, 1"),
    ("CameraOperatorCandidateGimbalQuatV1","quat","0, 0, 0, 1"),
    ("CameraOperatorCandidateOverrideActiveV1","bool","false"),
    ("CameraOperatorCandidateTransitionActiveV1","bool","false"),
    ("CameraOperatorCandidateTetherAppliedV1","bool","false"),
    ("CameraOperatorCandidateValidV1","bool","false"),
    ("CameraOperatorResultValidV1","bool","false"),
    ("CameraOperatorFailureCodeV1","string",""),
    ("CameraOperatorScratchValidV1","bool","false"),
)


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--project-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--paste-output",type=Path)
    args=parser.parse_args()
    camera=load(args.project_root/"tools/blueprint/Build-CameraChannelCompileResetGraph.py","edd_operator_reset_camera")
    reset=camera.load(args.project_root);bp=reset.load(args.project_root);bp.TARGET_GRAPH=FUNCTION
    capture=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    start=bp.read_blocks(args.project_root/"tools/blueprint/snippets/start-linear-playback.eddgraph")
    vector_live=bp.read_blocks(args.project_root/"tools/blueprint/live-snippets/evaluate-quintic-vector-v1.eddgraph")
    quat_live=bp.read_blocks(args.project_root/"tools/blueprint/live-snippets/evaluate-spherical-bezier-quaternion-v1.eddgraph")
    entry=bp.Node.clone("entry",bp.find_block(capture,r"K2Node_FunctionEntry"),"K2Node_FunctionEntry_0",0,0)
    entry.text=re.sub(r'FunctionReference=\(MemberName="[^"]+"\)',f'FunctionReference=(MemberName="{FUNCTION}")',entry.text,1)
    scalar_form=bp.find_block(start,r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    vector_form=bp.find_block(vector_live,r'K2Node_VariableSet.*MemberName="TrajectoryResultPositionVectorV1"')
    quat_form=bp.find_block(quat_live,r'K2Node_VariableSet.*MemberName="TrajectoryResultOrientationQuatV1"')
    nodes=[entry];chain=[]
    for index,(name,kind,value) in enumerate(SCALARS):
        if kind=="vector":form,old=vector_form,"TrajectoryResultPositionVectorV1"
        elif kind=="quat":form,old=quat_form,"TrajectoryResultOrientationQuatV1"
        else:form,old=scalar_form,"PlaybackActive"
        node=bp.Node.clone(f"set_{index}",form,f"K2Node_VariableSet_{index}",256+index*416,0)
        camera.string_variable(node,old,name) if kind=="string" else reset.variable(node,old,name,kind)
        reset.default(node,name,value);nodes.append(node);chain.append(node)
    bp.connect(entry,"then",chain[0],"execute")
    for left,right in zip(chain,chain[1:]):bp.connect(left,"then",right,"execute")
    full="\n".join(node.text for node in nodes)+"\n"
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
    if args.paste_output:
        paste="\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in nodes[1:])+"\n"
        args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text(paste,encoding="utf-8")


if __name__=="__main__":main()
