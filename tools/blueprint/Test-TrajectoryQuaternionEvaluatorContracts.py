"""Structural and executable contracts for spherical quaternion Bezier."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


INPUTS = (
    "TrajectoryInputOrientationStartQuatV1",
    "TrajectoryInputOrientationStartControlQuatV1",
    "TrajectoryInputOrientationEndControlQuatV1",
    "TrajectoryInputOrientationEndQuatV1",
)
OUTPUT = "TrajectoryResultOrientationQuatV1"
VALID = "TrajectoryResultOrientationValidV1"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


class Interpreter:
    def __init__(self, c, nodes, state, orientation):
        self.c, self.nodes, self.state, self.orientation = c, nodes, dict(state), orientation
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match: self.pin_owner[(node.name, match.group(1))] = (node, pin)

    @staticmethod
    def variable(node):
        match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
        if not match: raise RuntimeError(node.name)
        return match.group(1)

    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            linked_node, linked_pin = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in linked_pin.body: return linked_node, linked_pin.name
        return None

    def value(self, node, pin_name):
        source = self.source(node, pin_name)
        if source: return self.output(*source)
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin_name].body)
        value = "" if not match else match.group(1)
        if value == "true": return True
        if value == "false": return False
        named_quat = re.fullmatch(
            r"\(X=([^,]+),Y=([^,]+),Z=([^,]+),W=([^\)]+)\)", value
        )
        if named_quat:
            return tuple(float(component) for component in named_quat.groups())
        if "," in value: return tuple(float(part.strip()) for part in value.split(","))
        try: return float(value)
        except ValueError: return value

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class: return self.state[self.variable(node)]
        member = re.search(r'MemberName="([^"]+)"', node.text)
        if not member: raise RuntimeError(node.name)
        name = member.group(1)
        if name == "FClamp": return max(self.value(node,"Min"),min(self.value(node,"Max"),self.value(node,"Value")))
        if name == "Quat_IsFinite": return all(math.isfinite(v) for v in self.value(node,"Q"))
        if name == "Quat_IsNormalized":
            q=self.value(node,"Q"); return abs(sum(v*v for v in q)-1.0) < 1e-4
        if name == "Quat_Slerp": return self.orientation.slerp(self.value(node,"A"),self.value(node,"B"),self.value(node,"Alpha"))
        a,b=self.value(node,"A"),self.value(node,"B")
        if name == "GreaterEqual_DoubleDouble": return a>=b
        if name == "LessEqual_DoubleDouble": return a<=b
        if name == "BooleanAND": return bool(a) and bool(b)
        raise RuntimeError(name)

    def next_exec(self,node,pin="then"):
        if pin not in node.pins:return None
        for link in node.pins[pin].links:
            target,target_pin=self.pin_owner[link]
            if target_pin.name=="execute":return target
        return None

    def run(self):
        entries=[n for n in self.nodes.values() if "K2Node_FunctionEntry" in n.node_class]
        if entries:
            if len(entries) != 1: raise RuntimeError(f"entries: {len(entries)}")
            current=self.next_exec(entries[0])
            if current is None: raise RuntimeError("native entry is disconnected")
        else:
            roots=[n for n in self.nodes.values() if "execute" in n.pins and not n.pins["execute"].links]
            if len(roots)!=1: raise RuntimeError(f"paste roots: {len(roots)}")
            current=roots[0]
        while current:
            if "K2Node_VariableSet" in current.node_class:
                name=self.variable(current); self.state[name]=self.value(current,name); current=self.next_exec(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current=self.next_exec(current,"then" if self.value(current,"Condition") else "else")
            else: raise RuntimeError(current.name)
        return self.state


def variables(nodes,name,kind):
    return [n for n in nodes.values() if kind in n.node_class and f'VariableReference=(MemberName="{name}"' in n.text]


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--project-root",type=Path,required=True); parser.add_argument("--graph",type=Path,required=True); parser.add_argument("--paste",action="store_true")
    args=parser.parse_args()
    scalar=load(args.project_root/"tools/blueprint/Test-TrajectoryScalarEvaluatorContracts.py","edd_quat_scalar_contract")
    c=scalar.load_contracts(args.project_root); nodes=c.parse_graph(args.graph)
    orientation=load(args.project_root/"tools/trajectory/orientation_reference.py","edd_quat_oracle")
    expected=36 if args.paste else 37; c.require(len(nodes)==expected,f"node count {len(nodes)}")
    text="\n".join(n.text for n in nodes.values())
    c.require("K2Node_Knot" not in text,"reroute node present")
    c.require("SubPins=(" not in text and "ParentPin=" not in text,"split quaternion pin present")
    c.require(text.count('MemberName="Quat_Slerp"')==6,"SLERP topology changed")
    c.require(text.count('MemberName="Quat_IsFinite"')==4,"finite guards changed")
    c.require(text.count('MemberName="Quat_IsNormalized"')==4,"normalized guards changed")
    # One conjunction validates finite alpha, four pair finite/normalized
    # quaternion guards, and four reductions combine all five predicates.
    c.require(text.count('MemberName="BooleanAND"')==9,"guard conjunction changed")
    entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class]
    c.require(len(entries)==(0 if args.paste else 1),"entry count changed")
    if not args.paste:
        c.require(bool(entries[0].pins["then"].links),"native entry seam is disconnected")
    for name in INPUTS: c.require(len(variables(nodes,name,"K2Node_VariableGet"))==1,f"{name} getter")
    c.require(len(variables(nodes,OUTPUT,"K2Node_VariableSet"))==2,"result reset/commit")
    c.require(len(variables(nodes,VALID,"K2Node_VariableSet"))==2,"valid reset/commit")

    def state(quats,alpha):
        result=dict(zip(INPUTS,quats)); result["TrajectoryInputAlphaV1"]=alpha
        result[OUTPUT]=(9.0,9.0,9.0,9.0); result[VALID]=True; return result
    rng=random.Random(0xEDD058)
    fixtures=[((0,0,0,1),(0,0,0,1),(0,0,0,1),(0,0,0,1))]
    for _ in range(100):
        fixtures.append(tuple(orientation.normalize(tuple(rng.uniform(-1,1) for _ in range(4))) for _ in range(4)))
    valid=0
    for quats in fixtures:
        segment=orientation.CompiledOrientationSegment(0,1,*quats)
        for alpha in (-1,0,.125,.5,.875,1,2):
            actual=Interpreter(c,nodes,state(quats,alpha),orientation).run()
            expected_q=orientation._spherical_bezier(segment,max(0,min(1,alpha)))
            c.require(actual[VALID] is True,"valid rejected")
            error=math.sqrt(sum(v*v for v in orientation.logarithmic_delta(actual[OUTPUT],expected_q)))
            c.require(error<1e-10,f"rotation mismatch {error}"); valid+=1
    invalid=0
    identity=(0.0,0.0,0.0,1.0)
    for alpha in (math.nan,math.inf,-math.inf):
        result=Interpreter(c,nodes,state((identity,)*4,alpha),orientation).run()
        c.require(result[VALID] is False and result[OUTPUT]==identity,"bad alpha accepted/leaked"); invalid+=1
    for index in range(4):
        for bad in ((0,0,0,0),(0,0,0,2),(math.nan,0,0,1),(math.inf,0,0,1)):
            quats=[identity]*4; quats[index]=bad
            result=Interpreter(c,nodes,state(tuple(quats),.5),orientation).run()
            c.require(result[VALID] is False and result[OUTPUT]==identity,"bad quat accepted/leaked"); invalid+=1
    print(f"Trajectory quaternion evaluator contracts passed ({'paste' if args.paste else 'full'}): {valid} valid, {invalid} invalid")


if __name__=="__main__":main()
