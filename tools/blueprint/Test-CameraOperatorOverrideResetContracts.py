"""Exact ownership and execution contracts for camera operator-step reset."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


DEFAULTS={
    "CameraOperatorValidationValidV1":"false",
    "CameraOperatorCandidateModeV1":"directed",
    "CameraOperatorCandidateRecenterActiveV1":"false",
    "CameraOperatorCandidateTranslationOffsetV1":"0, 0, 0",
    "CameraOperatorCandidateTranslationVelocityV1":"0, 0, 0",
    "CameraOperatorCandidateLookOffsetQuatV1":"0, 0, 0, 1",
    "CameraOperatorCandidateAngularVelocityV1":"0, 0, 0",
    "CameraOperatorCandidatePositionV1":"0, 0, 0",
    "CameraOperatorCandidateBodyQuatV1":"0, 0, 0, 1",
    "CameraOperatorCandidateGimbalQuatV1":"0, 0, 0, 1",
    "CameraOperatorCandidateOverrideActiveV1":"false",
    "CameraOperatorCandidateTransitionActiveV1":"false",
    "CameraOperatorCandidateTetherAppliedV1":"false",
    "CameraOperatorCandidateValidV1":"false",
    "CameraOperatorResultValidV1":"false",
    "CameraOperatorFailureCodeV1":"",
    "CameraOperatorScratchValidV1":"false",
}
PRESERVED=(
    "CameraOperatorInputSourceValidV1","CameraOperatorInputRequestedModeV1",
    "CameraOperatorInputAuthoredPositionV1","CameraOperatorInputAuthoredBodyQuatV1",
    "CameraOperatorInputAuthoredGimbalQuatV1","CameraOperatorInputCarrierFrameQuatV1",
    "CameraOperatorInputTranslationV1","CameraOperatorInputLookV1","CameraOperatorInputDeltaSecondsV1",
    "CameraOperatorInputRecenterRequestedV1","CameraOperatorInputReturnToDirectedRequestedV1",
    "CameraOperatorPolicyTranslationFrameV1","CameraOperatorPolicyMaximumTranslationSpeedV1",
    "CameraOperatorPolicyTranslationAccelerationV1","CameraOperatorPolicyRecenterTranslationSpeedV1",
    "CameraOperatorPolicyMaximumAngularSpeedV1","CameraOperatorPolicyAngularAccelerationV1",
    "CameraOperatorPolicyRecenterAngularSpeedV1","CameraOperatorPolicyTetherEnabledV1",
    "CameraOperatorPolicyTetherDistanceV1","CameraOperatorStateInitializedV1","CameraOperatorStateModeV1",
    "CameraOperatorStateRecenterActiveV1","CameraOperatorStateTranslationOffsetV1",
    "CameraOperatorStateTranslationVelocityV1","CameraOperatorStateLookOffsetQuatV1",
    "CameraOperatorStateAngularVelocityV1","CameraOperatorResultPositionV1",
    "CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1","CameraOperatorResultModeV1",
    "CameraOperatorResultOverrideActiveV1","CameraOperatorResultTransitionActiveV1",
    "CameraOperatorResultTetherAppliedV1",
)
FORBIDDEN=("CameraTransform","CameraComfort","CameraChannel","CameraApply","Airframe","Flypath","Repository","PlaybackTime","Event","Cue","StateClip","Server")


def load(path:Path):
    spec=importlib.util.spec_from_file_location("edd_operator_reset_contract_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def member(node):
    match=re.search(r'MemberName="([^"]+)"',node.text)
    return None if match is None else match.group(1)


def default(node,name):
    pin=node.pins[name].body
    match=re.search(r'(?:^|,)DefaultValue="([^"]*)"',pin)
    return "" if match is None else match.group(1)


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args()
    contracts=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes=contracts.parse_graph(args.graph);contracts.require(len(nodes)==(17 if args.paste else 18),f"node count {len(nodes)}")
    entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries)==(0 if args.paste else 1),"entry count")
    setters=sorted((node for node in nodes.values() if "K2Node_VariableSet" in node.node_class),key=lambda node:int(node.name.rsplit("_",1)[1]))
    contracts.require(len(setters)==17,"exact setter count")
    contracts.require({member(node) for node in setters}==set(DEFAULTS),"exact transient reset ownership")
    if args.paste:contracts.require(not setters[0].pins["execute"].links,"paste execution root")
    else:contracts.require_link(entries[0],"then",setters[0],"execute","native entry to reset root")
    for left,right in zip(setters,setters[1:]):contracts.require_link(left,"then",right,"execute",f"ordered reset seam {left.name} to {right.name}")
    for node in setters:
        name=member(node);actual=default(node,name)
        contracts.require(actual==DEFAULTS[name],f"{name} default {actual!r}")
    text=args.graph.read_text(encoding="utf-8")
    contracts.require(not any(name in text for name in PRESERVED),"inputs, policy, state, and prior accepted result preserved")
    contracts.require(not any(name in text for name in FORBIDDEN),"external ownership forbidden")
    state={name:object() for name in PRESERVED};before=dict(state);state.update({name:value for name,value in DEFAULTS.items()})
    contracts.require(all(state[name] is before[name] for name in PRESERVED),"preserved object identity")
    contracts.require(state["CameraOperatorCandidateModeV1"]=="directed","candidate mode reset")
    contracts.require(state["CameraOperatorCandidateLookOffsetQuatV1"]=="0, 0, 0, 1","look candidate reset")
    contracts.require(all(state[name]=="false" for name in ("CameraOperatorValidationValidV1","CameraOperatorCandidateValidV1","CameraOperatorResultValidV1","CameraOperatorScratchValidV1")),"fail-closed flags")
    contracts.require(state["CameraOperatorFailureCodeV1"]=="","failure cleared")
    print(f"Camera operator reset contracts passed ({'paste' if args.paste else 'full'}): complete state and prior result preserved")


if __name__=="__main__":main()
