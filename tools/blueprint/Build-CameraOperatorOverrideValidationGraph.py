"""Build fail-closed preflight for one camera operator-override step."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION="ValidateCameraOperatorOverrideInputsV1"
MODES=("directed","free_look","carrier_freecam")
TRANSLATION_FRAMES=("world","carrier")
VECTOR_INPUTS=(
    ("CameraOperatorInputAuthoredPositionV1",False,False),
    ("CameraOperatorInputTranslationV1",True,False),
    ("CameraOperatorInputLookV1",True,False),
    ("CameraOperatorStateTranslationOffsetV1",False,True),
    ("CameraOperatorStateTranslationVelocityV1",False,True),
    ("CameraOperatorStateAngularVelocityV1",False,True),
)
QUAT_INPUTS=(
    ("CameraOperatorInputAuthoredBodyQuatV1",False),
    ("CameraOperatorInputAuthoredGimbalQuatV1",False),
    ("CameraOperatorInputCarrierFrameQuatV1",False),
    ("CameraOperatorStateLookOffsetQuatV1",True),
)
POSITIVE_POLICIES=(
    "CameraOperatorPolicyMaximumTranslationSpeedV1",
    "CameraOperatorPolicyTranslationAccelerationV1",
    "CameraOperatorPolicyRecenterTranslationSpeedV1",
    "CameraOperatorPolicyMaximumAngularSpeedV1",
    "CameraOperatorPolicyAngularAccelerationV1",
    "CameraOperatorPolicyRecenterAngularSpeedV1",
    "CameraOperatorPolicyTetherDistanceV1",
)


def load(root:Path):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec=importlib.util.spec_from_file_location("edd_operator_validation_base",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def pin_kind(node,pin_name:str,kind:str)->None:
    category,subcategory,obj={
        "bool":("bool","","None"),"real":("real","double","None"),"string":("string","","None"),
        "vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]
    def mutate(line:str)->str:
        line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1)
        line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1)
        line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)','PinType.ContainerType=None',line,1)
    node.mutate_pin(pin_name,mutate)


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args()
    scalar=load(args.project_root);bp=scalar.load_helpers(args.project_root);forms=scalar.load_templates(args.project_root,bp)
    vector_forms=bp.read_blocks(args.project_root/"tools/blueprint/templates/repository-codec-vector-node-forms.eddgraph")
    quat_forms=bp.read_blocks(args.project_root/"tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    quat_compiler=bp.read_blocks(args.project_root/"tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    break_quat_forms=bp.read_blocks(args.project_root/"tools/blueprint/templates/repository-codec-break-quat-node-form.eddgraph")
    forms.update(
        break_vector=bp.find_block(vector_forms,r'MemberName="BreakVector"'),
        quat_finite=bp.find_block(quat_forms,r'MemberName="Quat_IsFinite"'),
        quat_size=bp.find_block(quat_compiler,r'MemberName="Quat_Size"'),
        break_quat=bp.find_block(break_quat_forms,r'MemberName="BreakQuat"'),
    )
    b=scalar.Builder(bp,forms,FUNCTION)

    def add_form(key:str,form:str,x:int,y:int):
        match=bp.BLOCK_RE.match(forms[form]);cls=match.group("class").rsplit(".",1)[-1]
        index=b.serial.get(cls,0);b.serial[cls]=index+1
        node=bp.Node.clone(key,forms[form],f"{cls}_{index}",x,y);b.nodes.append(node);return node

    def variable(node,name:str,kind:str):
        scalar.retarget_variable(node,name,"vector" if kind=="quat" else kind);pin_kind(node,name,kind)
        if "Output_Get" in node.pins:pin_kind(node,"Output_Get",kind)

    def get(name:str,kind:str,x:int,y:int):
        node=b.add(f"get_{name}_{len(b.nodes)}","get",x,y);variable(node,name,kind);return node

    def set_(name:str,kind:str,x:int,y:int,value:str):
        node=b.add(f"set_{name}_{len(b.nodes)}","set",x,y);variable(node,name,kind);scalar.set_default(node,name,value);return node

    def compare(member:str,left,left_pin:str,x:int,y:int,kind:str="real",default:str=""):
        node=b.add(f"{member}_{len(b.nodes)}","compare",x,y);scalar.retarget_function(node,member)
        if member in ("EqualEqual_StrStr","NotEqual_StrStr"):node.text=node.text.replace("KismetMathLibrary","KismetStringLibrary")
        for pin in ("A","B"):pin_kind(node,pin,kind)
        pin_kind(node,"ReturnValue","bool");bp.connect(left,left_pin,node,"A");scalar.set_default(node,"B",default);return node

    def combine(member:str,conditions,x:int,y:int):
        current,current_pin=conditions[0]
        for index,(condition,condition_pin) in enumerate(conditions[1:]):
            node=b.add(f"{member}_{len(b.nodes)}","compare",x+index*208,y);scalar.retarget_function(node,member)
            for pin in ("A","B","ReturnValue"):pin_kind(node,pin,"bool")
            bp.connect(current,current_pin,node,"A");bp.connect(condition,condition_pin,node,"B");current,current_pin=node,"ReturnValue"
        return current,current_pin

    conditions=[];canonical=[]
    source=get("CameraOperatorInputSourceValidV1","bool",0,0);conditions.append((source,"CameraOperatorInputSourceValidV1"))
    requested=get("CameraOperatorInputRequestedModeV1","string",0,192)
    requested_flags=[compare("EqualEqual_StrStr",requested,"CameraOperatorInputRequestedModeV1",320+i*208,192,"string",mode) for i,mode in enumerate(MODES)]
    conditions.append(combine("BooleanOR",[(node,"ReturnValue") for node in requested_flags],944,192))

    for index,(name,bounded,is_state) in enumerate(VECTOR_INPUTS):
        y=512+index*608;source_vector=get(name,"vector",0,y)
        split=add_form(f"break_{name}","break_vector",320,y);pin_kind(split,"InVec","vector")
        for pin in ("X","Y","Z"):pin_kind(split,pin,"real")
        bp.connect(source_vector,name,split,"InVec")
        for component_index,component in enumerate(("X","Y","Z")):
            component_y=y+component_index*144;finite=b.finite(split,component,640,component_y);conditions.append((finite,"ReturnValue"))
            if bounded:
                lower=compare("GreaterEqual_DoubleDouble",split,component,864,component_y,"real","-1.0")
                upper=compare("LessEqual_DoubleDouble",split,component,1088,component_y,"real","1.0")
                conditions.extend(((lower,"ReturnValue"),(upper,"ReturnValue")))
            if is_state:
                equal=compare("EqualEqual_DoubleDouble",split,component,1312,component_y,"real","0.0");canonical.append((equal,"ReturnValue"))

    for index,(name,is_state) in enumerate(QUAT_INPUTS):
        y=4320+index*672;source_quat=get(name,"quat",0,y)
        finite=add_form(f"finite_{name}","quat_finite",320,y);pin_kind(finite,"Q","quat");pin_kind(finite,"ReturnValue","bool");bp.connect(source_quat,name,finite,"Q")
        size=add_form(f"size_{name}","quat_size",320,y+160);pin_kind(size,"Q","quat");pin_kind(size,"ReturnValue","real");bp.connect(source_quat,name,size,"Q")
        lower=compare("GreaterEqual_DoubleDouble",size,"ReturnValue",640,y+112,"real","0.999999")
        upper=compare("LessEqual_DoubleDouble",size,"ReturnValue",864,y+256,"real","1.000001")
        conditions.extend(((finite,"ReturnValue"),(lower,"ReturnValue"),(upper,"ReturnValue")))
        if is_state:
            split=add_form("break_state_look","break_quat",1088,y);pin_kind(split,"InQuat","quat");bp.connect(source_quat,name,split,"InQuat")
            for component_index,(component,wanted) in enumerate((("X","0.0"),("Y","0.0"),("Z","0.0"),("W","1.0"))):
                equal=compare("EqualEqual_DoubleDouble",split,component,1312,y+component_index*144,"real",wanted);canonical.append((equal,"ReturnValue"))

    delta=get("CameraOperatorInputDeltaSecondsV1","real",2048,0)
    delta_finite=b.finite(delta,"CameraOperatorInputDeltaSecondsV1",2368,0)
    delta_positive=compare("Greater_DoubleDouble",delta,"CameraOperatorInputDeltaSecondsV1",2592,0,"real","0.0")
    delta_max=compare("LessEqual_DoubleDouble",delta,"CameraOperatorInputDeltaSecondsV1",2816,0,"real","0.5")
    conditions.extend(((delta_finite,"ReturnValue"),(delta_positive,"ReturnValue"),(delta_max,"ReturnValue")))

    translation_frame=get("CameraOperatorPolicyTranslationFrameV1","string",2048,256)
    frame_flags=[compare("EqualEqual_StrStr",translation_frame,"CameraOperatorPolicyTranslationFrameV1",2368+i*208,256,"string",value) for i,value in enumerate(TRANSLATION_FRAMES)]
    conditions.append(combine("BooleanOR",[(node,"ReturnValue") for node in frame_flags],2784,256))
    for index,name in enumerate(POSITIVE_POLICIES):
        y=512+index*288;source_policy=get(name,"real",2048,y)
        finite=b.finite(source_policy,name,2368,y);positive=compare("Greater_DoubleDouble",source_policy,name,2592,y,"real","0.0")
        conditions.extend(((finite,"ReturnValue"),(positive,"ReturnValue")))
        if name=="CameraOperatorPolicyTetherDistanceV1":
            maximum=compare("LessEqual_DoubleDouble",source_policy,name,2816,y,"real","100000.0");conditions.append((maximum,"ReturnValue"))

    initialized=get("CameraOperatorStateInitializedV1","bool",2048,2816)
    state_mode=get("CameraOperatorStateModeV1","string",2048,3008)
    state_mode_flags=[compare("EqualEqual_StrStr",state_mode,"CameraOperatorStateModeV1",2368+i*208,3008,"string",mode) for i,mode in enumerate(MODES)]
    state_mode_valid=combine("BooleanOR",[(node,"ReturnValue") for node in state_mode_flags],2992,3008);conditions.append(state_mode_valid)
    canonical.append((state_mode_flags[0],"ReturnValue"))
    state_recenter=get("CameraOperatorStateRecenterActiveV1","bool",2048,3232)
    recenter_false=compare("EqualEqual_BoolBool",state_recenter,"CameraOperatorStateRecenterActiveV1",2368,3232,"bool","false");canonical.append((recenter_false,"ReturnValue"))
    canonical_valid=combine("BooleanAND",canonical,3200,3392)
    initialization_valid=combine("BooleanOR",[(initialized,"CameraOperatorStateInitializedV1"),canonical_valid],6320,3392);conditions.append(initialization_valid)

    ready=combine("BooleanAND",conditions,4096,7600)
    invalidate=set_("CameraOperatorValidationValidV1","bool",256,8000,"false")
    failure=set_("CameraOperatorFailureCodeV1","string",480,8000,"validation_failed")
    guard=b.add("validation_guard","branch",16384,8000)
    success=set_("CameraOperatorFailureCodeV1","string",16608,8000,"")
    publish=set_("CameraOperatorValidationValidV1","bool",16832,8000,"true")
    bp.connect(b.entry,"then",invalidate,"execute");bp.connect(invalidate,"then",failure,"execute");bp.connect(failure,"then",guard,"execute")
    bp.connect(ready[0],ready[1],guard,"Condition");bp.connect(guard,"then",success,"execute");bp.connect(success,"then",publish,"execute")
    full="\n".join(node.text for node in b.nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True,exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:])+"\n",encoding="utf-8")


if __name__=="__main__":main()
