"""Structural and executable contracts for generated scalar trajectory graphs."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


PROFILES = (
    "linear", "smoothstep", "smootherstep", "cinematic_s_curve",
    "accelerate_through", "brake_into",
)


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_scalar_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


class Interpreter:
    def __init__(self, contracts, nodes, inputs):
        self.c, self.nodes, self.state = contracts, nodes, dict(inputs)
        self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match: self.pin_owner[(node.name, match.group(1))] = (node, pin)

    @staticmethod
    def default(pin):
        match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', pin.body)
        if match is None: return 0.0
        value = match.group(1)
        if value == "true": return True
        if value == "false": return False
        try: return float(value)
        except ValueError: return value

    def source(self, node, pin_name):
        pin = node.pins[pin_name]
        for link in pin.links:
            linked_node, linked_pin = self.pin_owner[link]
            if 'Direction="EGPD_Output"' in linked_pin.body:
                return linked_node, linked_pin.name
        return None

    def value(self, node, pin_name):
        linked = self.source(node, pin_name)
        if linked is not None: return self.output(*linked)
        return self.default(node.pins[pin_name])

    def variable_name(self, node):
        match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
        if match is None: raise RuntimeError(f"No variable on {node.name}")
        return match.group(1)

    def output(self, node, pin_name):
        if "K2Node_VariableGet" in node.node_class:
            return self.state[self.variable_name(node)]
        member = re.search(r'MemberName="([^"]+)"', node.text)
        if member is None: raise RuntimeError(f"No callable member on {node.name}")
        name = member.group(1)
        if name == "FClamp":
            return max(self.value(node, "Min"), min(self.value(node, "Max"), self.value(node, "Value")))
        a, b = self.value(node, "A"), self.value(node, "B")
        if name == "Add_DoubleDouble": return a + b
        if name == "Subtract_DoubleDouble": return a - b
        if name == "Multiply_DoubleDouble": return a * b
        if name == "GreaterEqual_DoubleDouble": return a >= b
        if name == "LessEqual_DoubleDouble": return a <= b
        if name == "EqualEqual_DoubleDouble": return a == b
        if name == "EqualEqual_StrStr": return a == b
        if name == "BooleanAND": return bool(a) and bool(b)
        raise RuntimeError(f"Unsupported graph operation {name}")

    def next_exec(self, node, pin_name="then"):
        if pin_name not in node.pins: return None
        for link in node.pins[pin_name].links:
            target, pin = self.pin_owner[link]
            if pin.name == "execute": return target
        return None

    def run(self):
        entries = [n for n in self.nodes.values() if "K2Node_FunctionEntry" in n.node_class]
        if entries:
            current = self.next_exec(entries[0])
        else:
            executable = [n for n in self.nodes.values() if "execute" in n.pins]
            roots = [n for n in executable if not n.pins["execute"].links]
            if len(roots) != 1: raise RuntimeError(f"Expected one paste root, found {len(roots)}")
            current = roots[0]
        visited = 0
        while current is not None:
            visited += 1
            if visited > 100: raise RuntimeError("Execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = self.variable_name(current)
                self.state[name] = self.value(current, name)
                current = self.next_exec(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.next_exec(current, "then" if self.value(current, "Condition") else "else")
            else:
                raise RuntimeError(f"Unsupported executable node {current.name}")
        return self.state


def default_state():
    return {
        "TrajectoryInputProfileV1": "", "TrajectoryInputAlphaV1": 0.0,
        "TrajectoryInputStartValueV1": 0.0, "TrajectoryInputStartVelocityUV1": 0.0,
        "TrajectoryInputStartAccelerationUV1": 0.0, "TrajectoryInputEndValueV1": 0.0,
        "TrajectoryInputEndVelocityUV1": 0.0, "TrajectoryInputEndAccelerationUV1": 0.0,
        "TrajectoryResultValueV1": 123.0, "TrajectoryResultDerivativeUV1": 456.0,
        "TrajectoryResultSecondDerivativeUV1": 789.0, "TrajectoryResultValidV1": True,
    }


def call_nodes(nodes, name):
    return [n for n in nodes.values() if f'MemberName="{name}"' in n.text and "K2Node_CallFunction" in n.node_class]


def variables(nodes, name, kind=None):
    return [n for n in nodes.values() if f'VariableReference=(MemberName="{name}"' in n.text and (kind is None or kind in n.node_class)]


def assert_common(c, nodes, function, expected, paste):
    c.require(len(nodes) == expected - (1 if paste else 0), f"{function}: node count changed")
    entries = [n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class]
    c.require(len(entries) == (0 if paste else 1), f"{function}: entry count changed")
    text = "\n".join(n.text for n in nodes.values())
    c.require("bOrphanedPin=True" not in text, f"{function}: orphaned pin")
    c.require("ErrorType=" not in text and "ErrorMsg=" not in text, f"{function}: serialized compiler error")
    known = set(nodes)
    external = {name for n in nodes.values() for p in n.pins.values() for name, _ in p.links if name not in known}
    c.require(not external, f"{function}: external links {sorted(external)}")


def assert_time(c, nodes, paste):
    assert_common(c, nodes, "EvaluateTimeProfileV1", 67, paste)
    c.require(len(call_nodes(nodes, "FClamp")) == 1, "Time alpha must clamp once")
    c.require(len(call_nodes(nodes, "Subtract_DoubleDouble")) == 5, "Time subtraction topology changed")
    c.require(len(call_nodes(nodes, "Multiply_DoubleDouble")) == 24, "Time multiplication topology changed")
    c.require(len(call_nodes(nodes, "GreaterEqual_DoubleDouble")) == 1, "Time lower finite bound changed")
    c.require(len(call_nodes(nodes, "LessEqual_DoubleDouble")) == 1, "Time upper finite bound changed")
    c.require(len(call_nodes(nodes, "BooleanAND")) == 1, "Time finite conjunction changed")
    equals = call_nodes(nodes, "EqualEqual_StrStr")
    c.require(len(equals) == 6, "Time profile dispatch count changed")
    defaults = {Interpreter.default(n.pins["B"]) for n in equals}
    c.require(defaults == set(PROFILES), f"Time profile dispatch set changed: {defaults}")
    for name in ("TrajectoryResultValueV1", "TrajectoryResultDerivativeUV1", "TrajectoryResultSecondDerivativeUV1"):
        c.require(len(variables(nodes, name, "K2Node_VariableSet")) == (7 if name == "TrajectoryResultValueV1" else 1), f"{name}: setter count changed")
    c.require(len(variables(nodes, "TrajectoryResultValidV1", "K2Node_VariableSet")) == 7, "Time validity commits changed")


def assert_quintic(c, nodes, paste):
    assert_common(c, nodes, "EvaluateQuinticScalarV1", 117, paste)
    c.require(len(call_nodes(nodes, "FClamp")) == 1, "Quintic alpha must clamp once")
    c.require(len(call_nodes(nodes, "GreaterEqual_DoubleDouble")) == 7, "Quintic lower finite bounds changed")
    c.require(len(call_nodes(nodes, "LessEqual_DoubleDouble")) == 7, "Quintic upper finite bounds changed")
    c.require(len(call_nodes(nodes, "BooleanAND")) == 13, "Quintic finite conjunction changed")
    for name in ("TrajectoryResultValueV1", "TrajectoryResultDerivativeUV1", "TrajectoryResultSecondDerivativeUV1", "TrajectoryResultValidV1"):
        c.require(len(variables(nodes, name, "K2Node_VariableSet")) == 2, f"{name}: atomic reset/commit changed")


def reference_quintic(values, u):
    p0,v0,a0,p1,v1,a1 = values
    x=max(0.0,min(1.0,u)); x2=x*x; x3=x2*x; x4=x3*x; x5=x4*x
    basis=(1-10*x3+15*x4-6*x5, x-6*x3+8*x4-3*x5, .5*(x2-3*x3+3*x4-x5),
           10*x3-15*x4+6*x5, -4*x3+7*x4-3*x5, .5*(x3-2*x4+x5))
    d1=(-30*x2+60*x3-30*x4,1-18*x2+32*x3-15*x4,x-4.5*x2+6*x3-2.5*x4,
        30*x2-60*x3+30*x4,-12*x2+28*x3-15*x4,1.5*x2-4*x3+2.5*x4)
    d2=(-60*x+180*x2-120*x3,-36*x+96*x2-60*x3,1-9*x+18*x2-10*x3,
        60*x-180*x2+120*x3,-24*x+84*x2-60*x3,3*x-12*x2+10*x3)
    return tuple(sum(a*b for a,b in zip(weights,values)) for weights in (basis,d1,d2))


def executable_proof(c, time_nodes, quintic_nodes):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trajectory"))
    from cinematic_reference import evaluate_time_profile
    for name in PROFILES:
        prior = -1.0
        for i in range(1001):
            alpha = i / 1000.0
            state=default_state(); state.update(TrajectoryInputProfileV1=name,TrajectoryInputAlphaV1=alpha)
            result=Interpreter(c,time_nodes,state).run()
            actual=float(result["TrajectoryResultValueV1"]); expected=evaluate_time_profile(name,alpha)
            c.require(result["TrajectoryResultValidV1"] is True, f"{name}/{alpha}: invalid")
            c.require(abs(actual-expected)<=2e-12, f"{name}/{alpha}: {actual} != {expected}")
            c.require(actual+2e-14>=prior, f"{name}: nonmonotonic")
            prior=actual
    for name,alpha in (("bounce",.5),("",.5),("linear",math.nan),("linear",math.inf),("linear",-math.inf)):
        state=default_state(); state.update(TrajectoryInputProfileV1=name,TrajectoryInputAlphaV1=alpha)
        result=Interpreter(c,time_nodes,state).run()
        c.require(result["TrajectoryResultValidV1"] is False, f"invalid time input accepted: {name}/{alpha}")
        c.require(result["TrajectoryResultValueV1"]==0.0, "invalid time input leaked stale value")
    randomizer=random.Random(0xEDD053)
    fixtures=[((0,0,0,10,0,0),-2.0),((0,4,0,10,7,0),0.0),((0,4,0,10,7,0),1.0),((0,4,2,10,7,-3),2.0)]
    fixtures += [(tuple(randomizer.uniform(-100,100) for _ in range(6)),randomizer.uniform(-1,2)) for _ in range(250)]
    input_names=("TrajectoryInputStartValueV1","TrajectoryInputStartVelocityUV1","TrajectoryInputStartAccelerationUV1",
                 "TrajectoryInputEndValueV1","TrajectoryInputEndVelocityUV1","TrajectoryInputEndAccelerationUV1")
    for values,u in fixtures:
        state=default_state(); state["TrajectoryInputAlphaV1"]=u; state.update(dict(zip(input_names,values)))
        result=Interpreter(c,quintic_nodes,state).run(); expected=reference_quintic(values,u)
        c.require(result["TrajectoryResultValidV1"] is True, f"valid quintic rejected: {values}/{u}")
        for key,wanted in zip(("TrajectoryResultValueV1","TrajectoryResultDerivativeUV1","TrajectoryResultSecondDerivativeUV1"),expected):
            actual=float(result[key]); c.require(abs(actual-wanted)<=1e-9*max(1,abs(wanted)),f"{key}: {actual} != {wanted}")
    for nonfinite in (math.nan, math.inf, -math.inf):
        for bad_index in range(7):
            values=[1.0]*7; values[bad_index]=nonfinite
            state=default_state(); state["TrajectoryInputAlphaV1"]=values[0]; state.update(dict(zip(input_names,values[1:])))
            result=Interpreter(c,quintic_nodes,state).run()
            c.require(result["TrajectoryResultValidV1"] is False, f"nonfinite quintic input {bad_index}/{nonfinite} accepted")
            c.require(all(result[k]==0.0 for k in ("TrajectoryResultValueV1","TrajectoryResultDerivativeUV1","TrajectoryResultSecondDerivativeUV1")),"invalid quintic leaked stale outputs")


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--project-root",type=Path,required=True); parser.add_argument("--input-dir",type=Path,required=True); parser.add_argument("--paste",action="store_true")
    args=parser.parse_args(); c=load_contracts(args.project_root)
    time_nodes=c.parse_graph(args.input_dir/"evaluate-time-profile-v1.eddgraph")
    quintic_nodes=c.parse_graph(args.input_dir/"evaluate-quintic-scalar-v1.eddgraph")
    assert_time(c,time_nodes,args.paste); assert_quintic(c,quintic_nodes,args.paste)
    executable_proof(c,time_nodes,quintic_nodes)
    print(f"Trajectory scalar evaluator contracts passed ({'paste' if args.paste else 'full'}).")


if __name__ == "__main__": main()
