"""Structural and executable contracts for orientation-control primitives."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


class Interpreter:
    def __init__(self, c, nodes, state, oracle):
        self.c, self.nodes, self.state, self.o = c, nodes, dict(state), oracle
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match: self.pin_owner[(node.name, match.group(1))] = (node, pin)

    @staticmethod
    def var(node):
        value = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
        if not value: raise RuntimeError(node.name)
        return value.group(1)

    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            n, p = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in p.body: return n, p.name
        return None

    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        if source: return self.output(*source)
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
        value = "" if not match else match.group(1)
        if value == "true": return True
        if value == "false": return False
        named = re.fullmatch(r"\(X=([^,]+),Y=([^,]+),Z=([^,]+),W=([^)]+)\)", value)
        if named: return tuple(float(x) for x in named.groups())
        if "," in value: return tuple(float(x.strip()) for x in value.split(","))
        try: return float(value)
        except ValueError: return value

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class: return self.state[self.var(node)]
        member = re.search(r'MemberName="([^"]+)"', node.text)
        if not member: raise RuntimeError(node.name)
        name = member.group(1)
        if name == "BreakQuat": return self.value(node, "InQuat")["XYZW".index(pin_name)]
        if name == "BreakVector": return self.value(node, "InVec")["XYZ".index(pin_name)]
        if name == "MakeVector": return tuple(self.value(node, axis) for axis in "XYZ")
        if name == "Quat_IsFinite": return all(math.isfinite(x) for x in self.value(node, "Q"))
        if name == "Quat_IsNormalized":
            q = self.value(node, "Q"); return abs(sum(x*x for x in q)-1) < 1e-4
        if name == "Quat_Normalized": return self.o.normalize(self.value(node, "Q"))
        if name == "Quat_Slerp": return self.o.slerp(self.value(node, "A"), self.value(node, "B"), self.value(node, "Alpha"))
        if name == "Quat_Inversed": return self.o.inverse_unit(self.value(node, "Q"))
        if name == "Multiply_QuatQuat": return self.o.multiply(self.value(node, "A"), self.value(node, "B"))
        if name == "Quat_Log":
            v = self.o._log_unit(self.value(node,"Q")); return (*v,0.0)
        if name == "Quat_Exp": return self.o._exp_vector(self.value(node,"Q")[:3])
        if name == "Quat_Size": return math.sqrt(sum(x*x for x in self.value(node,"Q")))
        if name == "VSize": return math.sqrt(sum(x*x for x in self.value(node,"A")))
        if name == "SelectFloat": return self.value(node,"A") if self.value(node,"bPickA") else self.value(node,"B")
        a,b=self.value(node,"A"),self.value(node,"B")
        if name == "Add_DoubleDouble": return a+b
        if name == "Multiply_DoubleDouble": return a*b
        if name == "Divide_DoubleDouble": return a/b
        if name == "Greater_DoubleDouble": return a>b
        if name == "GreaterEqual_DoubleDouble": return a>=b
        if name == "LessEqual_DoubleDouble": return a<=b
        if name == "EqualEqual_DoubleDouble": return a==b
        if name == "BooleanAND": return bool(a) and bool(b)
        raise RuntimeError(name)

    def next(self,node,pin="then"):
        if pin not in node.pins:return None
        for link in node.pins[pin].links:
            n,p=self.pin_owner[link]
            if p.name=="execute":return n
        return None

    def run(self):
        entries=[n for n in self.nodes.values() if "K2Node_FunctionEntry" in n.node_class]
        if entries:
            if len(entries)!=1:raise RuntimeError("entry count")
            current=self.next(entries[0])
        else:
            roots=[n for n in self.nodes.values() if "execute" in n.pins and not n.pins["execute"].links]
            if len(roots)!=1:raise RuntimeError(f"roots {len(roots)}")
            current=roots[0]
        count=0
        while current:
            count+=1
            if count>100:raise RuntimeError("cycle")
            if "K2Node_VariableSet" in current.node_class:
                name=self.var(current);self.state[name]=self.value(current,name);current=self.next(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current=self.next(current,"then" if self.value(current,"Condition") else "else")
            elif 'MemberName="Quat_SetComponents"' in current.text:
                source=self.source(current,"Q")
                if source is None or "K2Node_VariableGet" not in source[0].node_class: raise RuntimeError("Quat_SetComponents Q")
                self.state[self.var(source[0])]=tuple(self.value(current,axis) for axis in "XYZW")
                current=self.next(current)
            else:raise RuntimeError(current.name)
        return self.state


def angle_error(o, a, b):
    return math.sqrt(sum(x*x for x in o.logarithmic_delta(a,b)))


def qvec(v): return (v[0],v[1],v[2],0.0)


def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--input-dir",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args()
    scalar=load(a.project_root/"tools/blueprint/Test-TrajectoryScalarEvaluatorContracts.py","edd_oc_scalar")
    c=scalar.load_contracts(a.project_root)
    o=load(a.project_root/"tools/trajectory/orientation_reference.py","edd_oc_oracle")
    names={
        "compute-orientation-log-delta-v1":26,
        "compute-orientation-tangent-rate-v1":85,
        "build-orientation-segment-controls-v1":76,
    }
    graphs={}
    for stem,count in names.items():
        path=a.input_dir/f"{stem}{'-paste' if a.paste else ''}.eddgraph"
        nodes=c.parse_graph(path);graphs[stem]=nodes
        c.require(len(nodes)==count-(1 if a.paste else 0),f"{stem} count {len(nodes)}")
        text="\n".join(n.text for n in nodes.values())
        c.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text,f"{stem} unsafe form")
        c.require("Quat_EnforceShortestArcWith" not in text and "K2Node_MakeStruct" not in text,f"{stem} unsafe quat node")
        c.require(text.count('MemberName="Quat_SetComponents"')==(2 if stem=="build-orientation-segment-controls-v1" else 0),f"{stem} quat assembly boundary")
        entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class]
        c.require(len(entries)==(0 if a.paste else 1),f"{stem} entry")

    identity=(0.,0.,0.,1.)
    rng=random.Random(0xEDD059)
    valid=invalid=0
    log_nodes=graphs["compute-orientation-log-delta-v1"]
    pairs=[(identity,identity)]
    for _ in range(150):
        pairs.append((o.normalize(tuple(rng.uniform(-1,1) for _ in range(4))),
                      o.normalize(tuple(rng.uniform(-1,1) for _ in range(4)))))
    for start,end in pairs:
        state={"OrientationInputStartQuatV1":start,"OrientationInputEndQuatV1":end,
               "OrientationResultDeltaVectorV1":(9,9,9),"OrientationResultAlignedEndQuatV1":(9,9,9,9),"OrientationResultValidV1":True}
        result=Interpreter(c,log_nodes,state,o).run()
        expected=o.logarithmic_delta(start,end)
        c.require(result["OrientationResultValidV1"] is True,"log rejected")
        c.require(math.sqrt(sum((x-y)**2 for x,y in zip(result["OrientationResultDeltaVectorV1"],expected)))<1e-10,"log mismatch")
        c.require(angle_error(o,result["OrientationResultAlignedEndQuatV1"],end)<1e-10,"aligned end mismatch");valid+=1
    for bad in ((0,0,0,0),(0,0,0,2),(math.nan,0,0,1),(math.inf,0,0,1)):
        state={"OrientationInputStartQuatV1":bad,"OrientationInputEndQuatV1":identity,
               "OrientationResultDeltaVectorV1":(9,9,9),"OrientationResultAlignedEndQuatV1":(9,9,9,9),"OrientationResultValidV1":True}
        result=Interpreter(c,log_nodes,state,o).run()
        c.require(result["OrientationResultValidV1"] is False and result["OrientationResultDeltaVectorV1"]==(0,0,0) and result["OrientationResultAlignedEndQuatV1"]==identity,"log invalid leak");invalid+=1

    tangent_nodes=graphs["compute-orientation-tangent-rate-v1"]
    tangent_cases=[((0,0,0),(0,0,0),1,1),((1,0,0),(1,0,0),1,1),((10,0,0),(-1,0,0),.1,10)]
    tangent_cases += [(tuple(rng.uniform(-3,3) for _ in range(3)),tuple(rng.uniform(-3,3) for _ in range(3)),
                       10**rng.uniform(-2,1),10**rng.uniform(-2,1)) for _ in range(200)]
    for prev,nxt,pd,nd in tangent_cases:
        state={"OrientationInputPreviousDeltaVectorV1":prev,"OrientationInputNextDeltaVectorV1":nxt,
               "OrientationInputPreviousDurationV1":pd,"OrientationInputNextDurationV1":nd,
               "OrientationResultTangentRateVectorV1":(9,9,9),"OrientationResultValidV1":True}
        result=Interpreter(c,tangent_nodes,state,o).run()
        left=tuple(x/pd for x in prev);right=tuple(x/nd for x in nxt)
        candidate=tuple((x+y)*.5 for x,y in zip(left,right))
        mag=math.sqrt(sum(x*x for x in candidate));limit=3*min(math.sqrt(sum(x*x for x in left)),math.sqrt(sum(x*x for x in right)))
        expected=tuple(x*(limit/mag) for x in candidate) if mag>limit and mag>1e-12 else candidate
        actual=result["OrientationResultTangentRateVectorV1"]
        c.require(result["OrientationResultValidV1"] is True and math.sqrt(sum((x-y)**2 for x,y in zip(actual,expected)))<1e-9,"tangent mismatch");valid+=1
    for duration in (0,-1,math.nan,math.inf):
        state={"OrientationInputPreviousDeltaVectorV1":(1,0,0),"OrientationInputNextDeltaVectorV1":(1,0,0),
               "OrientationInputPreviousDurationV1":duration,"OrientationInputNextDurationV1":1,
               "OrientationResultTangentRateVectorV1":(9,9,9),"OrientationResultValidV1":True}
        result=Interpreter(c,tangent_nodes,state,o).run()
        c.require(result["OrientationResultValidV1"] is False and result["OrientationResultTangentRateVectorV1"]==(0,0,0),"tangent invalid leak");invalid+=1
    for bad_component in (math.nan,math.inf,-math.inf):
        state={"OrientationInputPreviousDeltaVectorV1":(bad_component,0,0),"OrientationInputNextDeltaVectorV1":(1,0,0),
               "OrientationInputPreviousDurationV1":1,"OrientationInputNextDurationV1":1,
               "OrientationResultTangentRateVectorV1":(9,9,9),"OrientationResultValidV1":True}
        result=Interpreter(c,tangent_nodes,state,o).run()
        c.require(result["OrientationResultValidV1"] is False and result["OrientationResultTangentRateVectorV1"]==(0,0,0),"tangent nonfinite accepted");invalid+=1

    control_nodes=graphs["build-orientation-segment-controls-v1"]
    for _ in range(200):
        start=o.normalize(tuple(rng.uniform(-1,1) for _ in range(4)));end=o.normalize(tuple(rng.uniform(-1,1) for _ in range(4)))
        sr=tuple(rng.uniform(-2,2) for _ in range(3));er=tuple(rng.uniform(-2,2) for _ in range(3));duration=10**rng.uniform(-2,1)
        state={"OrientationInputStartQuatV1":start,"OrientationInputEndQuatV1":end,
               "OrientationInputStartTangentRateVectorV1":sr,"OrientationInputEndTangentRateVectorV1":er,
               "OrientationInputDurationV1":duration,"OrientationResultStartControlQuatV1":(9,9,9,9),
               "OrientationResultEndControlQuatV1":(9,9,9,9),"OrientationResultValidV1":True,
               "OrientationScratchStartExponentQuatV1":identity,"OrientationScratchEndExponentQuatV1":identity}
        result=Interpreter(c,control_nodes,state,o).run()
        esc=o.normalize(o.multiply(start,o._exp_vector(tuple(x*duration/6 for x in sr))))
        eec=o.normalize(o.multiply(end,o._exp_vector(tuple(x*-duration/6 for x in er))))
        c.require(result["OrientationResultValidV1"] is True and angle_error(o,result["OrientationResultStartControlQuatV1"],esc)<1e-9 and angle_error(o,result["OrientationResultEndControlQuatV1"],eec)<1e-9,"control mismatch");valid+=1
    for duration in (0,-1,math.nan,math.inf):
        state={"OrientationInputStartQuatV1":identity,"OrientationInputEndQuatV1":identity,
               "OrientationInputStartTangentRateVectorV1":(1,0,0),"OrientationInputEndTangentRateVectorV1":(1,0,0),
               "OrientationInputDurationV1":duration,"OrientationResultStartControlQuatV1":(9,9,9,9),
               "OrientationResultEndControlQuatV1":(9,9,9,9),"OrientationResultValidV1":True,
               "OrientationScratchStartExponentQuatV1":identity,"OrientationScratchEndExponentQuatV1":identity}
        result=Interpreter(c,control_nodes,state,o).run()
        c.require(result["OrientationResultValidV1"] is False and result["OrientationResultStartControlQuatV1"]==identity and result["OrientationResultEndControlQuatV1"]==identity,"control invalid leak");invalid+=1
    for bad_component in (math.nan,math.inf,-math.inf):
        state={"OrientationInputStartQuatV1":identity,"OrientationInputEndQuatV1":identity,
               "OrientationInputStartTangentRateVectorV1":(bad_component,0,0),"OrientationInputEndTangentRateVectorV1":(1,0,0),
               "OrientationInputDurationV1":1,"OrientationResultStartControlQuatV1":(9,9,9,9),
               "OrientationResultEndControlQuatV1":(9,9,9,9),"OrientationResultValidV1":True,
               "OrientationScratchStartExponentQuatV1":identity,"OrientationScratchEndExponentQuatV1":identity}
        result=Interpreter(c,control_nodes,state,o).run()
        c.require(result["OrientationResultValidV1"] is False and result["OrientationResultStartControlQuatV1"]==identity and result["OrientationResultEndControlQuatV1"]==identity,"control nonfinite accepted");invalid+=1
    print(f"Orientation compiler contracts passed ({'paste' if a.paste else 'full'}): {valid} valid, {invalid} invalid")


if __name__=="__main__":main()
