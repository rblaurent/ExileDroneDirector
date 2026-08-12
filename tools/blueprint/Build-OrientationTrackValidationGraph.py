"""Build fail-closed validation for multi-key orientation track inputs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ValidateOrientationTrackInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_orientation_validation_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[kind]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin_name, mutate)


def array_get(scalar, builder, name, kind, x, y):
    node = builder.get(name, "real" if kind == "real" else "vector", x, y)
    pin_kind(node, name, kind, True)
    if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)
    return node


def retarget_call(scalar, node, member, pin_types):
    scalar.retarget_function(node, member)
    for pin, kind in pin_types.items(): pin_kind(node, pin, kind)
    return node


def main():
    p=argparse.ArgumentParser(); p.add_argument("--project-root",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--paste-output",type=Path); a=p.parse_args()
    scalar=load(a.project_root); bp=scalar.load_helpers(a.project_root); forms=scalar.load_templates(a.project_root,bp); b=scalar.Builder(bp,forms,FUNCTION)
    raw=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    qforms=bp.read_blocks(a.project_root/"tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    qeval=bp.read_blocks(a.project_root/"tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    foreach_form=bp.find_block(raw,r"K2Node_MacroInstance")
    length_form=bp.find_block(edit,r'MemberName="Array_Length"')
    qfinite_form=bp.find_block(qeval,r'MemberName="Quat_IsFinite"')
    qsize_form=bp.find_block(qforms,r'MemberName="Quat_Size"')

    def add_form(key,form,x,y):
        match=bp.BLOCK_RE.match(form); cls=match.group("class").rsplit(".",1)[-1]
        index=b.serial.get(cls,0); b.serial[cls]=index+1
        node=bp.Node.clone(key,form,f"{cls}_{index}",x,y); b.nodes.append(node); return node
    def compare(member,x,y,kind="int",default_b=None):
        n=b.add(f"{member}_{len(b.nodes)}","compare",x,y); retarget_call(scalar,n,member,{"A":kind,"B":kind,"ReturnValue":"bool"})
        if default_b is not None: scalar.set_default(n,"B",default_b)
        return n
    def bool_and(left,right,x,y):
        n=compare("BooleanAND",x,y,"bool"); bp.connect(left,"ReturnValue",n,"A"); bp.connect(right,"ReturnValue",n,"B"); return n
    def array_length(source,name,kind,x,y):
        n=add_form(f"len_{name}",length_form,x,y); pin_kind(n,"TargetArray",kind,True); bp.connect(source,name,n,"TargetArray"); return n
    def foreach(source,name,kind,x,y):
        n=add_form(f"foreach_{name}",foreach_form,x,y); pin_kind(n,"Array",kind,True); pin_kind(n,"Array Element",kind); bp.connect(source,name,n,"Array"); return n

    reset=b.set("OrientationTrackStageValidV1","bool",256,1450,"false")
    bp.connect(b.entry,"then",reset,"execute")
    quats=array_get(scalar,b,"OrientationTrackInputWaypointQuatsV1","quat",0,160)
    durations=array_get(scalar,b,"OrientationTrackInputDurationsV1","real",0,400)
    qlen=array_length(quats,"OrientationTrackInputWaypointQuatsV1","quat",288,160)
    dlen=array_length(durations,"OrientationTrackInputDurationsV1","real",288,400)
    at_least=compare("GreaterEqual_IntInt",560,80,"int","2"); bp.connect(qlen,"ReturnValue",at_least,"A")
    at_most=compare("LessEqual_IntInt",560,208,"int","512"); bp.connect(qlen,"ReturnValue",at_most,"A")
    minus=retarget_call(scalar,b.math("Subtract_DoubleDouble",560,400),"Subtract_IntInt",{"A":"int","B":"int","ReturnValue":"int"}); scalar.set_default(minus,"B","1"); bp.connect(qlen,"ReturnValue",minus,"A")
    shape=compare("EqualEqual_IntInt",816,400,"int"); bp.connect(dlen,"ReturnValue",shape,"A"); bp.connect(minus,"ReturnValue",shape,"B")
    bounds=bool_and(at_least,at_most,1056,128); all_shape=bool_and(bounds,shape,1280,256)
    shape_branch=b.add("shape_branch","branch",1536,1450); bp.connect(reset,"then",shape_branch,"execute"); bp.connect(all_shape,"ReturnValue",shape_branch,"Condition")
    accept=b.set("OrientationTrackStageValidV1","bool",1792,1450,"true"); bp.connect(shape_branch,"then",accept,"execute")

    fq=foreach(quats,"OrientationTrackInputWaypointQuatsV1","quat",2048,320)
    bp.connect(accept,"then",fq,"Exec")
    qfinite=add_form("qfinite",qfinite_form,2320,240); bp.connect(fq,"Array Element",qfinite,"Q")
    qsize=add_form("qsize",qsize_form,2320,432); pin_kind(qsize,"ReturnValue","real"); bp.connect(fq,"Array Element",qsize,"Q")
    qnonzero=compare("Greater_DoubleDouble",2576,432,"real","1e-12"); bp.connect(qsize,"ReturnValue",qnonzero,"A")
    qvalid=bool_and(qfinite,qnonzero,2816,320)
    qbranch=b.add("q_branch","branch",3056,320); bp.connect(fq,"LoopBody",qbranch,"execute"); bp.connect(qvalid,"ReturnValue",qbranch,"Condition")
    qreject=b.set("OrientationTrackStageValidV1","bool",3296,480,"false"); bp.connect(qbranch,"else",qreject,"execute")

    fd=foreach(durations,"OrientationTrackInputDurationsV1","real",3568,960); bp.connect(fq,"Completed",fd,"Exec")
    dfinite=b.finite(fd,"Array Element",3840,800)
    dpositive=compare("Greater_DoubleDouble",3840,1056,"real","0.0"); bp.connect(fd,"Array Element",dpositive,"A")
    dvalid=bool_and(dfinite,dpositive,4304,944)
    dbranch=b.add("d_branch","branch",4544,960); bp.connect(fd,"LoopBody",dbranch,"execute"); bp.connect(dvalid,"ReturnValue",dbranch,"Condition")
    dreject=b.set("OrientationTrackStageValidV1","bool",4784,1120,"false"); bp.connect(dbranch,"else",dreject,"execute")
    full="\n".join(n.text for n in b.nodes)+"\n"; a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]]
        a.paste_output.parent.mkdir(parents=True,exist_ok=True); a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")


if __name__=="__main__": main()
