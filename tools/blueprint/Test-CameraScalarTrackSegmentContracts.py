"""Structural and executable contracts for selected scalar-track segments."""
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
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SegmentInterpreter:
    def __init__(self, base, nodes, state):
        self.base = base
        self.inner = base.Interpreter(nodes, state)
        self.nodes = nodes
        self.state = self.inner.state
        self.inner.output = self.output

    def output(self, node, pin_name):
        if "K2Node_GetArrayItem" in node.node_class:
            array = self.inner.value(node, "Array")
            index = int(self.inner.value(node, "Dimension 1"))
            return array[index]
        if "K2Node_VariableGet" in node.node_class or "K2Node_Select" in node.node_class:
            return self.base.Interpreter.output(self.inner, node, pin_name)
        name = self.base.Interpreter.member(node)
        if name == "Array_Length":
            return len(self.inner.value(node, "TargetArray"))
        if name == "FClamp":
            return max(self.inner.value(node, "Min"), min(self.inner.value(node, "Max"), self.inner.value(node, "Value")))
        a = self.inner.value(node, "A"); b = self.inner.value(node, "B")
        if name in ("Add_DoubleDouble", "Add_IntInt"):
            return a + b
        if name == "Subtract_DoubleDouble":
            return a - b
        if name == "Multiply_DoubleDouble":
            return a * b
        if name == "Divide_DoubleDouble":
            return a / b
        if name in ("GreaterEqual_DoubleDouble", "GreaterEqual_IntInt"):
            return a >= b
        if name == "Less_IntInt":
            return a < b
        if name == "EqualEqual_StrStr":
            return a == b
        if name == "BooleanAND":
            return bool(a) and bool(b)
        if name == "BooleanOR":
            return bool(a) or bool(b)
        raise RuntimeError(f"Unsupported segment operation {name}")

    @staticmethod
    def time_profile(name, alpha):
        u = min(max(float(alpha), 0.0), 1.0)
        if name == "linear": return u
        if name == "smoothstep": return 3.0*u*u - 2.0*u*u*u
        if name == "smootherstep": return 10.0*u**3 - 15.0*u**4 + 6.0*u**5
        raise ValueError(name)

    @staticmethod
    def quintic(values, u):
        p0,v0,a0,p1,v1,a1 = values
        x=min(max(float(u),0.0),1.0);x2=x*x;x3=x2*x;x4=x3*x;x5=x4*x
        basis=(1-10*x3+15*x4-6*x5,x-6*x3+8*x4-3*x5,.5*(x2-3*x3+3*x4-x5),10*x3-15*x4+6*x5,-4*x3+7*x4-3*x5,.5*(x3-2*x4+x5))
        d1=(-30*x2+60*x3-30*x4,1-18*x2+32*x3-15*x4,x-4.5*x2+6*x3-2.5*x4,30*x2-60*x3+30*x4,-12*x2+28*x3-15*x4,1.5*x2-4*x3+2.5*x4)
        d2=(-60*x+180*x2-120*x3,-36*x+96*x2-60*x3,1-9*x+18*x2-10*x3,60*x-180*x2+120*x3,-24*x+84*x2-60*x3,3*x-12*x2+10*x3)
        return tuple(sum(weight*value for weight,value in zip(weights,values)) for weights in (basis,d1,d2))

    def execute_call(self, name):
        if name == "EvaluateTimeProfileV1":
            try:
                self.state["TrajectoryResultValueV1"] = self.time_profile(self.state["TrajectoryInputProfileV1"], self.state["TrajectoryInputAlphaV1"])
                self.state["TrajectoryResultValidV1"] = math.isfinite(self.state["TrajectoryInputAlphaV1"])
            except (ValueError, TypeError):
                self.state["TrajectoryResultValueV1"] = 0.0; self.state["TrajectoryResultValidV1"] = False
        elif name == "EvaluateQuinticScalarV1":
            keys = (
                "TrajectoryInputStartValueV1", "TrajectoryInputStartVelocityUV1",
                "TrajectoryInputStartAccelerationUV1", "TrajectoryInputEndValueV1",
                "TrajectoryInputEndVelocityUV1", "TrajectoryInputEndAccelerationUV1",
            )
            values = tuple(self.state[key] for key in keys)
            alpha = self.state["TrajectoryInputAlphaV1"]
            if all(math.isfinite(value) for value in values + (alpha,)):
                value, d1, d2 = self.quintic(values, alpha)
                self.state.update(TrajectoryResultValueV1=value, TrajectoryResultDerivativeUV1=d1, TrajectoryResultSecondDerivativeUV1=d2, TrajectoryResultValidV1=True)
            else:
                self.state.update(TrajectoryResultValueV1=0.0, TrajectoryResultDerivativeUV1=0.0, TrajectoryResultSecondDerivativeUV1=0.0, TrajectoryResultValidV1=False)
        elif name == "PublishCameraScalarTrackSampleV1":
            self.state["CameraScalarTrackResultValidV1"] = False
            required = (
                self.state["CameraScalarTrackCompileValidV1"], self.state["CameraScalarTrackScratchValidV1"],
                all(math.isfinite(self.state[key]) for key in (
                    "CameraScalarTrackScratchDomainValueV1", "CameraScalarTrackScratchDomainVelocityV1",
                    "CameraScalarTrackScratchDomainAccelerationV1",
                )),
            )
            domain = self.state["CameraScalarTrackInputDomainV1"]
            if not all(required) or domain not in ("linear", "reciprocal"):
                return
            value = self.state["CameraScalarTrackScratchDomainValueV1"]
            velocity = self.state["CameraScalarTrackScratchDomainVelocityV1"]
            acceleration = self.state["CameraScalarTrackScratchDomainAccelerationV1"]
            if domain == "reciprocal":
                if value <= 0.0: return
                value, velocity, acceleration = 1.0/value, -velocity/(value*value), 2.0*velocity*velocity/(value**3)-acceleration/(value*value)
            if not all(math.isfinite(number) for number in (value,velocity,acceleration)): return
            original = value
            if self.state["CameraScalarTrackInputClampOutputV1"]:
                if self.state["CameraScalarTrackInputHasMinimumV1"]: value=max(value,self.state["CameraScalarTrackInputMinimumV1"])
                if self.state["CameraScalarTrackInputHasMaximumV1"]: value=min(value,self.state["CameraScalarTrackInputMaximumV1"])
                if value != original: velocity=acceleration=0.0
            self.state.update(CameraScalarTrackResultValueV1=value,CameraScalarTrackResultVelocityV1=velocity,CameraScalarTrackResultAccelerationV1=acceleration,CameraScalarTrackResultValidV1=True)
        else:
            raise RuntimeError(name)

    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:
            current = self.inner.next_exec(entries[0])
        else:
            executable = [node for node in self.nodes.values() if "execute" in node.pins]
            roots = [node for node in executable if not node.pins["execute"].links]
            if len(roots) != 1: raise RuntimeError(f"Expected one paste root, found {len(roots)}")
            current = roots[0]
        steps = 0
        while current is not None:
            steps += 1
            if steps > 50: raise RuntimeError("Execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = self.base.Interpreter.member(current)
                self.state[name] = self.inner.value(current, name)
                current = self.inner.next_exec(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.inner.next_exec(current, "then" if self.inner.value(current, "Condition") else "else")
            elif "K2Node_CallFunction" in current.node_class:
                self.execute_call(self.base.Interpreter.member(current)); current = self.inner.next_exec(current)
            else:
                raise RuntimeError(f"Unsupported executable {current.name}")
        return self.state


def state_for(track, query, index):
    return {
        "CameraScalarTrackCompileValidV1": True, "CameraScalarTrackScratchValidV1": True,
        "CameraScalarTrackScratchIndexV1": index, "CameraScalarTrackQueryTimeV1": query,
        "CameraScalarTrackCandidateKeyTimesV1": list(track.key_times),
        "CameraScalarTrackCandidateDomainValuesV1": list(track.domain_values),
        "CameraScalarTrackCandidateInterpolationModesV1": list(track.interpolation_modes),
        "CameraScalarTrackCandidateArriveTangentsV1": list(track.arrive_tangents),
        "CameraScalarTrackCandidateLeaveTangentsV1": list(track.leave_tangents),
        "CameraScalarTrackInputDomainV1": track.domain,
        "CameraScalarTrackInputHasMinimumV1": track.has_minimum, "CameraScalarTrackInputMinimumV1": track.minimum,
        "CameraScalarTrackInputHasMaximumV1": track.has_maximum, "CameraScalarTrackInputMaximumV1": track.maximum,
        "CameraScalarTrackInputClampOutputV1": track.clamp_output,
        "CameraScalarTrackResultValueV1": 111.0, "CameraScalarTrackResultVelocityV1": 222.0,
        "CameraScalarTrackResultAccelerationV1": 333.0, "CameraScalarTrackResultSegmentIndexV1": -9,
        "CameraScalarTrackResultLocalAlphaV1": -9.0, "CameraScalarTrackResultValidV1": False,
        "CameraScalarTrackScratchDomainValueV1": 444.0, "CameraScalarTrackScratchDomainVelocityV1": 555.0,
        "CameraScalarTrackScratchDomainAccelerationV1": 666.0,
        "TrajectoryInputProfileV1": "", "TrajectoryInputAlphaV1": 0.0,
        "TrajectoryInputStartValueV1": 0.0, "TrajectoryInputStartVelocityUV1": 0.0,
        "TrajectoryInputStartAccelerationUV1": 0.0, "TrajectoryInputEndValueV1": 0.0,
        "TrajectoryInputEndVelocityUV1": 0.0, "TrajectoryInputEndAccelerationUV1": 0.0,
        "TrajectoryResultValueV1": 0.0, "TrajectoryResultDerivativeUV1": 0.0,
        "TrajectoryResultSecondDerivativeUV1": 0.0, "TrajectoryResultValidV1": False,
    }


def close(left, right): return abs(left-right) <= 3e-9*max(1.0,abs(right))


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true")
    args=parser.parse_args();contracts=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_scalar_segment_graph");base=load(args.project_root/"tools/blueprint/Test-CameraScalarTrackPublishContracts.py","edd_camera_scalar_publish_interpreter")
    reference=load(args.project_root/"tools/trajectory/camera_scalar_track_reference.py","edd_camera_scalar_segment_reference");nodes=contracts.parse_graph(args.graph);text=args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes)==(123 if args.paste else 124),f"node count {len(nodes)}")
    entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];contracts.require(len(entries)==(0 if args.paste else 1),"entry count")
    for helper,count in (("EvaluateTimeProfileV1",1),("EvaluateQuinticScalarV1",1),("PublishCameraScalarTrackSampleV1",3)):
        contracts.require(text.count(f'MemberName="{helper}"')==count,f"{helper} call count")
    setters=[base.Interpreter.member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    allowed={"CameraScalarTrackScratchValidV1","CameraScalarTrackScratchDomainValueV1","CameraScalarTrackScratchDomainVelocityV1","CameraScalarTrackScratchDomainAccelerationV1","CameraScalarTrackResultSegmentIndexV1","CameraScalarTrackResultLocalAlphaV1","TrajectoryInputProfileV1","TrajectoryInputAlphaV1","TrajectoryInputStartValueV1","TrajectoryInputStartVelocityUV1","TrajectoryInputStartAccelerationUV1","TrajectoryInputEndValueV1","TrajectoryInputEndVelocityUV1","TrajectoryInputEndAccelerationUV1"}
    contracts.require(set(setters)<=allowed,"segment write ownership");contracts.require("CameraScalarTrackResultValidV1" not in setters,"publisher alone owns public validity")
    rng=random.Random(0xEDD5E6);cases=[]
    for mode in reference.MODES:
        for domain in reference.DOMAINS:
            for alpha in (0.0,0.2,0.5,0.9,1.0):
                span=rng.uniform(0.25,4.0);v0=rng.uniform(20.0,200.0) if domain=="reciprocal" else rng.uniform(-30.0,30.0);v1=rng.uniform(20.0,200.0) if domain=="reciprocal" else rng.uniform(-30.0,30.0)
                arrive=[0.0,0.0];leave=[0.0,0.0]
                if mode=="hermite":leave[0]=rng.uniform(-0.01,0.01) if domain=="reciprocal" else rng.uniform(-10,10);arrive[1]=rng.uniform(-0.01,0.01) if domain=="reciprocal" else rng.uniform(-10,10)
                keys=(reference.CameraScalarKey(0.0,v0,mode,arrive[0],leave[0]),reference.CameraScalarKey(span,v1,"cinematic",arrive[1],leave[1]))
                track=reference.compile_camera_scalar_track(keys,span,domain=domain);query=alpha*span;cases.append((track,query,reference.evaluate_camera_scalar_track(track,query)))
    for track,query,wanted in cases:
        result=SegmentInterpreter(base,nodes,state_for(track,query,0)).run();contracts.require(result["CameraScalarTrackResultValidV1"] is True,"valid segment rejected")
        actual=(result["CameraScalarTrackResultValueV1"],result["CameraScalarTrackResultVelocityV1"],result["CameraScalarTrackResultAccelerationV1"]);expected=(wanted.value,wanted.velocity,wanted.acceleration)
        contracts.require(all(close(a,b) for a,b in zip(actual,expected)),f"segment mismatch {actual} != {expected}");contracts.require(result["CameraScalarTrackResultSegmentIndexV1"]==0,"segment index");contracts.require(close(result["CameraScalarTrackResultLocalAlphaV1"],wanted.local_alpha),"local alpha")
    base_track=reference.compile_camera_scalar_track((reference.CameraScalarKey(0.0,1.0,"linear"),reference.CameraScalarKey(1.0,2.0)),1.0)
    invalid=[]
    for field,value in (("CameraScalarTrackCompileValidV1",False),("CameraScalarTrackScratchValidV1",False),("CameraScalarTrackScratchIndexV1",-1),("CameraScalarTrackScratchIndexV1",1)):
        state=state_for(base_track,0.5,0);state[field]=value;invalid.append(state)
    state=state_for(base_track,0.5,0);state["CameraScalarTrackCandidateInterpolationModesV1"]=["bad"];invalid.append(state)
    for state in invalid:
        result=SegmentInterpreter(base,nodes,state).run();contracts.require(result["CameraScalarTrackResultValidV1"] is False,"invalid segment published")
    print(f"Camera scalar segment contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} mode/domain samples, {len(invalid)} failures")


if __name__=="__main__":main()
