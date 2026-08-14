"""Structural and executable contracts for camera operator input validation."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from dataclasses import replace
from pathlib import Path


READS={
    "CameraOperatorInputSourceValidV1","CameraOperatorInputRequestedModeV1",
    "CameraOperatorInputAuthoredPositionV1","CameraOperatorInputAuthoredBodyQuatV1",
    "CameraOperatorInputAuthoredGimbalQuatV1","CameraOperatorInputCarrierFrameQuatV1",
    "CameraOperatorInputTranslationV1","CameraOperatorInputLookV1","CameraOperatorInputDeltaSecondsV1",
    "CameraOperatorPolicyTranslationFrameV1","CameraOperatorPolicyMaximumTranslationSpeedV1",
    "CameraOperatorPolicyTranslationAccelerationV1","CameraOperatorPolicyRecenterTranslationSpeedV1",
    "CameraOperatorPolicyMaximumAngularSpeedV1","CameraOperatorPolicyAngularAccelerationV1",
    "CameraOperatorPolicyRecenterAngularSpeedV1","CameraOperatorPolicyTetherDistanceV1",
    "CameraOperatorStateInitializedV1","CameraOperatorStateModeV1","CameraOperatorStateRecenterActiveV1",
    "CameraOperatorStateTranslationOffsetV1","CameraOperatorStateTranslationVelocityV1",
    "CameraOperatorStateLookOffsetQuatV1","CameraOperatorStateAngularVelocityV1",
}
WRITES={"CameraOperatorValidationValidV1","CameraOperatorFailureCodeV1"}
FORBIDDEN=(
    "CameraOperatorCandidate","CameraOperatorResultPosition","CameraOperatorResultBody",
    "CameraOperatorResultGimbal","CameraOperatorResultMode","CameraOperatorResultOverride",
    "CameraOperatorResultTransition","CameraOperatorResultTether","CameraComfort","CameraChannel",
    "CameraApply","CameraTransform","Airframe","Flypath","Repository","PlaybackTime","Event",
    "Cue","StateClip","Server",
)


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def member(node):
    match=re.search(r'MemberName="([^"]+)"',node.text)
    return None if match is None else match.group(1)


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args()
    contracts=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_operator_validation_contract_base")
    nodes=contracts.parse_graph(args.graph);contracts.require(len(nodes)==(258 if args.paste else 259),f"node count {len(nodes)}")
    entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries)==(0 if args.paste else 1),"entry count")
    getters={member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters={member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters==READS,"exact validation reads");contracts.require(setters==WRITES,"exact validation writes")
    counts={name:sum(member(node)==name for node in nodes.values()) for name in (
        "BreakVector","BreakQuat","Quat_IsFinite","Quat_Size","EqualEqual_StrStr",
        "EqualEqual_DoubleDouble","EqualEqual_BoolBool","Greater_DoubleDouble",
    )}
    contracts.require(counts=={
        "BreakVector":6,"BreakQuat":1,"Quat_IsFinite":4,"Quat_Size":4,"EqualEqual_StrStr":8,
        "EqualEqual_DoubleDouble":13,"EqualEqual_BoolBool":1,"Greater_DoubleDouble":8,
    },f"native validation calls {counts}")
    contracts.require(sum("K2Node_IfThenElse" in node.node_class for node in nodes.values())==1,"single final publication branch")
    contracts.require(not any("K2Node_Knot" in node.node_class for node in nodes.values()),"no reroute knots")
    text=args.graph.read_text(encoding="utf-8")
    contracts.require(
        text.count('MemberParent="/Script/CoreUObject.Class\'/Script/Engine.KismetStringLibrary\'"')==8,
        "all string comparisons use KismetStringLibrary",
    )
    contracts.require(not any(value in text for value in FORBIDDEN),"no candidate/result/external mutation")
    for literal in ("directed","free_look","carrier_freecam","world","carrier","0.999999","1.000001","0.5","100000.0","-1.0","1.0"):
        contracts.require(literal in text,f"required validation literal {literal}")
    invalidators=[node for node in nodes.values() if member(node)=="CameraOperatorValidationValidV1" and 'DefaultValue="true"' not in node.text]
    contracts.require(len(invalidators)==1,"validation invalidated first")
    if args.paste:contracts.require(not invalidators[0].pins["execute"].links,"paste execution root")
    else:contracts.require_link(entries[0],"then",invalidators[0],"execute","native entry to validation root")

    sys.path.insert(0,str(args.project_root/"tools/trajectory"))
    operator=load(args.project_root/"tools/trajectory/camera_operator_override_reference.py","edd_operator_validation_reference")
    rng=random.Random(0xEDD0F5E8)
    def quat():
        axis=[rng.uniform(-1.0,1.0) for _ in range(3)];length=math.sqrt(sum(value*value for value in axis)) or 1.0
        axis=[value/length for value in axis];half=math.radians(rng.uniform(-175.0,175.0))*0.5
        return tuple(axis[index]*math.sin(half) for index in range(3))+(math.cos(half),)
    def base(state=None):
        return {
            "source_valid":True,"requested_mode":rng.choice(operator.MODES_V1),
            "authored_position":tuple(rng.uniform(-1e6,1e6) for _ in range(3)),
            "authored_body_rotation":quat(),"authored_gimbal_rotation":quat(),"carrier_frame_rotation":quat(),
            "translation_input":tuple(rng.uniform(-1.0,1.0) for _ in range(3)),
            "look_input":tuple(rng.uniform(-1.0,1.0) for _ in range(3)),
            "delta_seconds":rng.uniform(1.0/240.0,0.5),"recenter_requested":False,
            "return_to_directed_requested":False,"policy":operator.CameraOperatorPolicyV1(),
            "previous_state":operator.CameraOperatorStateV1() if state is None else state,
        }
    state=operator.CameraOperatorStateV1();valid=[]
    for _ in range(100):
        case=base(state);frame=operator.apply_camera_operator_override_v1(**case);state=frame.state;valid.append(case)
    contracts.require(len(valid)==100,"valid case count")

    canonical=base(operator.CameraOperatorStateV1())
    policy=canonical["policy"];state0=canonical["previous_state"]
    invalid=(
        {"source_valid":False},{"requested_mode":"orbit"},{"authored_position":(math.nan,0.0,0.0)},
        {"authored_body_rotation":(0.0,0.0,0.0,2.0)},{"authored_gimbal_rotation":(0.0,math.inf,0.0,1.0)},
        {"carrier_frame_rotation":(0.0,0.0,0.0)},{"translation_input":(1.01,0.0,0.0)},
        {"look_input":(0.0,math.nan,0.0)},{"delta_seconds":0.0},{"delta_seconds":0.501},
        {"policy":replace(policy,translation_frame="body")},{"policy":replace(policy,maximum_translation_speed_cm_s=0.0)},
        {"policy":replace(policy,translation_acceleration_cm_s2=math.nan)},
        {"policy":replace(policy,recenter_translation_speed_cm_s=-1.0)},
        {"policy":replace(policy,maximum_angular_speed_deg_s=0.0)},
        {"policy":replace(policy,angular_acceleration_deg_s2=math.inf)},
        {"policy":replace(policy,recenter_angular_speed_deg_s=-1.0)},
        {"policy":replace(policy,tether_distance_cm=0.0)},
        {"policy":replace(policy,tether_distance_cm=operator.MAX_TETHER_CM+1.0)},
        {"previous_state":replace(state0,mode="bad")},
        {"previous_state":replace(state0,translation_offset_cm=(math.nan,0.0,0.0))},
        {"previous_state":replace(state0,translation_velocity_cm_s=(math.inf,0.0,0.0))},
        {"previous_state":replace(state0,angular_velocity_deg_s=(0.0,math.nan,0.0))},
        {"previous_state":replace(state0,look_offset=(0.0,0.0,0.0,2.0))},
        {"previous_state":replace(state0,mode="free_look")},
        {"previous_state":replace(state0,recenter_active=True)},
        {"previous_state":replace(state0,translation_offset_cm=(1.0,0.0,0.0))},
        {"previous_state":replace(state0,translation_velocity_cm_s=(1.0,0.0,0.0))},
        {"previous_state":replace(state0,look_offset=quat())},
        {"previous_state":replace(state0,angular_velocity_deg_s=(0.0,1.0,0.0))},
    )
    rejected=0
    for overrides in invalid:
        case=dict(canonical);case.update(overrides)
        try:operator.apply_camera_operator_override_v1(**case)
        except operator.CameraOperatorOverrideError:rejected+=1
    contracts.require(rejected==len(invalid),f"rejected {rejected}/{len(invalid)}")
    snapshot=tuple(valid);[operator.apply_camera_operator_override_v1(**case) for case in reversed(valid)]
    contracts.require(tuple(valid)==snapshot,"inputs, policy, and prior state immutable")
    print(f"Camera operator validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid)} valid, {len(invalid)} failures")


if __name__=="__main__":main()
