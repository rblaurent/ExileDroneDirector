"""History-free end-to-end contracts for top-level scalar-track evaluation."""
from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
from pathlib import Path


def load(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class Interpreter:
    def __init__(self, base, reference, nodes, state):
        self.base=base;self.reference=reference;self.nodes=nodes;self.inner=base.Interpreter(nodes,state);self.state=self.inner.state;self.inner.output=self.output;self.loop_context={};self.selection_correct=True;self.loop_iterations=0;self.trace=[]

    def output(self,node,pin_name):
        if "K2Node_MacroInstance" in node.node_class and pin_name in ("Array Index","Array Element"):
            index,element=self.loop_context[node.name];return index if pin_name=="Array Index" else element
        if "K2Node_GetArrayItem" in node.node_class:
            return self.inner.value(node,"Array")[int(self.inner.value(node,"Dimension 1"))]
        if "K2Node_VariableGet" in node.node_class or "K2Node_Select" in node.node_class:return self.base.Interpreter.output(self.inner,node,pin_name)
        name=self.base.Interpreter.member(node)
        if name=="Array_Length":return len(self.inner.value(node,"TargetArray"))
        a=self.inner.value(node,"A");b=self.inner.value(node,"B")
        if name in ("Add_IntInt",):return int(a)+int(b)
        if name in ("Subtract_IntInt",):return int(a)-int(b)
        if name in ("GreaterEqual_DoubleDouble","GreaterEqual_IntInt"):return a>=b
        if name=="LessEqual_DoubleDouble":return a<=b
        if name in ("EqualEqual_IntInt","EqualEqual_BoolBool"):return a==b
        if name=="BooleanAND":return bool(a) and bool(b)
        if name=="BooleanOR":return bool(a) or bool(b)
        raise RuntimeError(f"Unsupported evaluator operation {name}")

    def compiled_track(self):
        return self.reference.CompiledCameraScalarTrack(
            tuple(self.state["CameraScalarTrackCandidateKeyTimesV1"]),tuple(self.state["CameraScalarTrackCandidateDomainValuesV1"]),tuple(self.state["CameraScalarTrackCandidateInterpolationModesV1"]),tuple(self.state["CameraScalarTrackCandidateArriveTangentsV1"]),tuple(self.state["CameraScalarTrackCandidateLeaveTangentsV1"]),self.state["CameraScalarTrackInputDurationV1"],self.state["CameraScalarTrackInputDomainV1"],self.state["CameraScalarTrackInputHasMinimumV1"],self.state["CameraScalarTrackInputMinimumV1"],self.state["CameraScalarTrackInputHasMaximumV1"],self.state["CameraScalarTrackInputMaximumV1"],self.state["CameraScalarTrackInputClampOutputV1"])

    def next_exec(self,node,pin_name="then"):
        if pin_name not in node.pins:return None
        for link in node.pins[pin_name].links:
            target,pin=self.inner.pin_owner[link]
            if pin.name in ("execute","Exec"):return target
        return None

    def publish(self):
        self.state["CameraScalarTrackResultValidV1"]=False
        if not self.state["CameraScalarTrackCompileValidV1"] or not self.state["CameraScalarTrackScratchValidV1"]:return
        value=self.state["CameraScalarTrackScratchDomainValueV1"];velocity=self.state["CameraScalarTrackScratchDomainVelocityV1"];acceleration=self.state["CameraScalarTrackScratchDomainAccelerationV1"]
        if not all(math.isfinite(number) for number in (value,velocity,acceleration)):return
        if self.state["CameraScalarTrackInputDomainV1"]=="reciprocal":
            if value<=0:return
            value,velocity,acceleration=1/value,-velocity/(value*value),2*velocity*velocity/(value**3)-acceleration/(value*value)
        original=value
        if self.state["CameraScalarTrackInputClampOutputV1"]:
            if self.state["CameraScalarTrackInputHasMinimumV1"]:value=max(value,self.state["CameraScalarTrackInputMinimumV1"])
            if self.state["CameraScalarTrackInputHasMaximumV1"]:value=min(value,self.state["CameraScalarTrackInputMaximumV1"])
            if value!=original:velocity=acceleration=0.0
        self.state.update(CameraScalarTrackResultValueV1=value,CameraScalarTrackResultVelocityV1=velocity,CameraScalarTrackResultAccelerationV1=acceleration,CameraScalarTrackResultValidV1=True)

    def call(self,name):
        if name=="ResetCameraScalarTrackResultV1":
            self.state.update(CameraScalarTrackResultValueV1=0.0,CameraScalarTrackResultVelocityV1=0.0,CameraScalarTrackResultAccelerationV1=0.0,CameraScalarTrackResultSegmentIndexV1=-1,CameraScalarTrackResultLocalAlphaV1=0.0,CameraScalarTrackResultCompleteV1=False,CameraScalarTrackResultValidV1=False,CameraScalarTrackScratchIndexV1=0,CameraScalarTrackScratchValidV1=False,CameraScalarTrackScratchDomainValueV1=0.0,CameraScalarTrackScratchDomainVelocityV1=0.0,CameraScalarTrackScratchDomainAccelerationV1=0.0)
        elif name=="PublishCameraScalarTrackSampleV1":self.publish()
        elif name=="EvaluateCameraScalarTrackSegmentV1":
            if not self.state["CameraScalarTrackScratchValidV1"]:return
            track=self.compiled_track();query=self.state["CameraScalarTrackQueryTimeV1"];clamped=min(max(query,0.0),track.duration_seconds);wanted=len(track.interpolation_modes)-1
            for index,right in enumerate(track.key_times[1:]):
                if clamped<=right:wanted=index;break
            self.selection_correct=self.selection_correct and self.state["CameraScalarTrackScratchIndexV1"]==wanted
            sample=self.reference.evaluate_camera_scalar_track(track,query)
            self.state.update(CameraScalarTrackResultValueV1=sample.value,CameraScalarTrackResultVelocityV1=sample.velocity,CameraScalarTrackResultAccelerationV1=sample.acceleration,CameraScalarTrackResultSegmentIndexV1=sample.segment_index,CameraScalarTrackResultLocalAlphaV1=sample.local_alpha,CameraScalarTrackResultValidV1=True)
        else:raise RuntimeError(name)

    def execute(self,current):
        steps=0
        while current is not None:
            steps+=1
            if steps>100:raise RuntimeError("Execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name=self.base.Interpreter.member(current);self.state[name]=self.inner.value(current,name);current=self.next_exec(current)
            elif "K2Node_IfThenElse" in current.node_class:
                condition=self.inner.value(current,"Condition");self.trace.append((current.name,condition));current=self.next_exec(current,"then" if condition else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                values=list(self.inner.value(current,"Array"))
                for index,element in enumerate(values):
                    self.loop_iterations+=1;self.loop_context[current.name]=(index,element);self.execute(self.next_exec(current,"LoopBody"))
                current=self.next_exec(current,"Completed")
            elif "K2Node_CallFunction" in current.node_class:
                self.call(self.base.Interpreter.member(current));current=self.next_exec(current)
            else:raise RuntimeError(f"Unsupported executable {current.name}")

    def run(self):
        entries=[node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries:root=self.next_exec(entries[0])
        else:
            executable=[node for node in self.nodes.values() if "execute" in node.pins];roots=[node for node in executable if not node.pins["execute"].links]
            if len(roots)!=1:raise RuntimeError(f"Expected one paste root, found {len(roots)}")
            root=roots[0]
        self.execute(root);return self.state


def state_for(track,query):
    return {"CameraScalarTrackCompileValidV1":True,"CameraScalarTrackQueryTimeV1":query,"CameraScalarTrackInputDurationV1":track.duration_seconds,"CameraScalarTrackCandidateKeyTimesV1":list(track.key_times),"CameraScalarTrackCandidateDomainValuesV1":list(track.domain_values),"CameraScalarTrackCandidateInterpolationModesV1":list(track.interpolation_modes),"CameraScalarTrackCandidateArriveTangentsV1":list(track.arrive_tangents),"CameraScalarTrackCandidateLeaveTangentsV1":list(track.leave_tangents),"CameraScalarTrackInputDomainV1":track.domain,"CameraScalarTrackInputHasMinimumV1":track.has_minimum,"CameraScalarTrackInputMinimumV1":track.minimum,"CameraScalarTrackInputHasMaximumV1":track.has_maximum,"CameraScalarTrackInputMaximumV1":track.maximum,"CameraScalarTrackInputClampOutputV1":track.clamp_output,"CameraScalarTrackResultValueV1":999.0,"CameraScalarTrackResultVelocityV1":999.0,"CameraScalarTrackResultAccelerationV1":999.0,"CameraScalarTrackResultSegmentIndexV1":99,"CameraScalarTrackResultLocalAlphaV1":99.0,"CameraScalarTrackResultCompleteV1":True,"CameraScalarTrackResultValidV1":True,"CameraScalarTrackScratchIndexV1":99,"CameraScalarTrackScratchValidV1":True,"CameraScalarTrackScratchDomainValueV1":999.0,"CameraScalarTrackScratchDomainVelocityV1":999.0,"CameraScalarTrackScratchDomainAccelerationV1":999.0}


def close(left,right):return abs(left-right)<=4e-9*max(1.0,abs(right))


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args()
    contracts=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_scalar_evaluate_graph");base=load(args.project_root/"tools/blueprint/Test-CameraScalarTrackPublishContracts.py","edd_camera_scalar_evaluate_base");reference=load(args.project_root/"tools/trajectory/camera_scalar_track_reference.py","edd_camera_scalar_evaluate_reference");nodes=contracts.parse_graph(args.graph);text=args.graph.read_text(encoding="utf-8")
    contracts.require(len(nodes)==(39 if args.paste else 40),f"node count {len(nodes)}");entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];contracts.require(len(entries)==(0 if args.paste else 1),"entry count")
    for helper in ("ResetCameraScalarTrackResultV1","EvaluateCameraScalarTrackSegmentV1","PublishCameraScalarTrackSampleV1"):contracts.require(text.count(f'MemberName="{helper}"')==1,f"{helper} exact call")
    contracts.require(len([node for node in nodes.values() if "K2Node_MacroInstance" in node.node_class])==1,"one bounded selector loop")
    rng=random.Random(0xEDD5E7);tracks=[]
    for seed in range(24):
        count=1 if seed<4 else rng.randint(2,7);domain=rng.choice(reference.DOMAINS);times=[0.0]
        for _ in range(count-1):times.append(times[-1]+rng.uniform(.2,2.0))
        values=[rng.uniform(20,300) if domain=="reciprocal" else rng.uniform(-50,50) for _ in times];modes=[];arrive=[0.0]*count;leave=[0.0]*count
        for index in range(count-1):
            mode=rng.choice(reference.MODES);modes.append(mode)
            if mode=="hermite":leave[index]=rng.uniform(-.005,.005) if domain=="reciprocal" else rng.uniform(-8,8);arrive[index+1]=rng.uniform(-.005,.005) if domain=="reciprocal" else rng.uniform(-8,8)
        keys=tuple(reference.CameraScalarKey(times[index],values[index],modes[index] if index<count-1 else "cinematic",arrive[index],leave[index]) for index in range(count));tracks.append(reference.compile_camera_scalar_track(keys,times[-1],domain=domain))
    cases=[]
    for track in tracks:
        queries=[-1.0,0.0,track.duration_seconds,track.duration_seconds+1.0]
        queries += [rng.uniform(0.0,track.duration_seconds) if track.duration_seconds else 0.0 for _ in range(8)]
        for query in queries:cases.append((track,query))
    for order in (cases,list(reversed(cases))):
        for track,query in order:
            interpreter=Interpreter(base,reference,nodes,state_for(track,query));result=interpreter.run();wanted=reference.evaluate_camera_scalar_track(track,query)
            contracts.require(interpreter.selection_correct,f"wrong segment selected for {track.key_times}/{query}");contracts.require(result["CameraScalarTrackResultValidV1"] is True,f"valid query rejected for {track.key_times}/{query}: scratch={result['CameraScalarTrackScratchValidV1']} index={result['CameraScalarTrackScratchIndexV1']} loops={interpreter.loop_iterations} trace={interpreter.trace}")
            actual=(result["CameraScalarTrackResultValueV1"],result["CameraScalarTrackResultVelocityV1"],result["CameraScalarTrackResultAccelerationV1"]);expected=(wanted.value,wanted.velocity,wanted.acceleration);contracts.require(all(close(a,b) for a,b in zip(actual,expected)),f"sample mismatch {actual} != {expected}")
            contracts.require(result["CameraScalarTrackResultSegmentIndexV1"]==wanted.segment_index,"segment result");contracts.require(close(result["CameraScalarTrackResultLocalAlphaV1"],wanted.local_alpha),"alpha result");contracts.require(result["CameraScalarTrackResultCompleteV1"]==wanted.complete,"complete result")
    base_track=tracks[-1];invalid=[]
    state=state_for(base_track,.5);state["CameraScalarTrackCompileValidV1"]=False;invalid.append(state)
    for query in (math.nan,math.inf,-math.inf):invalid.append(state_for(base_track,query))
    for state in invalid:
        result=Interpreter(base,reference,nodes,state).run();contracts.require(result["CameraScalarTrackResultValidV1"] is False,"invalid top-level query published");contracts.require(result["CameraScalarTrackResultValueV1"]==0.0,"reset did not clear stale result")
    print(f"Camera scalar evaluate contracts passed ({'paste' if args.paste else 'full'}): {len(cases)} forward + reverse queries, {len(invalid)} failures")


if __name__=="__main__":main()
