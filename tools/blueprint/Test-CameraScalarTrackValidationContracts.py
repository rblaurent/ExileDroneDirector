"""Exact exported-link and executable contracts for camera scalar validation."""
from __future__ import annotations
import argparse,importlib.util,random,re,sys
from dataclasses import replace
from pathlib import Path
ARRAYS=("CameraScalarTrackInputKeyTimesV1","CameraScalarTrackInputKeyValuesV1","CameraScalarTrackInputInterpolationModesV1","CameraScalarTrackInputArriveTangentsV1","CameraScalarTrackInputLeaveTangentsV1")
def load(path,name):s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_scalar_validation_graph");nodes=c.parse_graph(x.graph);text=x.graph.read_text(encoding="utf-8");c.require(len(nodes)==(137 if x.paste else 138),f"node count {len(nodes)}")
 entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");root=nodes["K2Node_VariableSet_0"];c.require(member(root)=="CameraScalarTrackScratchValidV1","validation root");c.require(not root.pins["execute"].links,"paste execution root") if x.paste else c.require_link(entries[0],"then",root,"execute","native entry to validation root")
 loops=[n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class];c.require(len(loops)==2,"key and segment-mode loops");sets=[member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require(set(sets)=={"CameraScalarTrackScratchValidV1","CameraScalarTrackFailureCodeV1"},"validation write ownership");c.require(sets.count("CameraScalarTrackScratchValidV1")==5 and sets.count("CameraScalarTrackFailureCodeV1")==2,"validation write counts")
 for name in ARRAYS:c.require(name in text,f"required authored array {name}")
 for mode in ("hold","linear","smooth","cinematic","hermite"):c.require(f'DefaultValue="{mode}"' in text,f"mode {mode}")
 for required in ("Max_IntInt","Greater_DoubleDouble","GreaterEqual_DoubleDouble","LessEqual_DoubleDouble","EqualEqual_StrStr","BooleanOR","BooleanAND"):c.require(f'MemberName="{required}"' in text,f"operator {required}")
 c.require('DefaultValue="5.562684646268003e-309"' in text,"reciprocal conversion must stay finite");c.require("CameraScalarTrackCandidate" not in text and "CameraScalarTrackCompileValidV1" not in text,"validation cannot publish candidates")

 ref=load(x.project_root/"tools/trajectory/camera_scalar_track_reference.py","edd_camera_scalar_validation_reference");valid=[]
 for seed in range(80):
  rng=random.Random(0xEDD510+seed);count=rng.randint(1,8);domain=rng.choice(("linear","reciprocal"));times=[0.0] if count==1 else [float(i) for i in range(count)];duration=times[-1];values=[rng.uniform(10.0,500.0) for _ in times];modes=[];arrive=[0.0]*count;leave=[0.0]*count
  for i in range(count-1):
   mode=rng.choice(ref.MODES);modes.append(mode)
   if mode=="hermite":leave[i]=rng.uniform(-0.01,0.01) if domain=="reciprocal" else rng.uniform(-5.0,5.0);arrive[i+1]=rng.uniform(-0.01,0.01) if domain=="reciprocal" else rng.uniform(-5.0,5.0)
  keys=tuple(ref.CameraScalarKey(times[i],values[i],modes[i] if i<count-1 else "cinematic",arrive[i],leave[i]) for i in range(count));valid.append((keys,duration,domain))
 for keys,duration,domain in valid:ref.compile_camera_scalar_track(keys,duration,domain=domain,minimum=1.0,maximum=1000.0)
 base=(ref.CameraScalarKey(0.0,10.0,"linear"),ref.CameraScalarKey(1.0,20.0))
 invalid=((),(replace(base[0],time_seconds=1.0),base[1]),(base[0],replace(base[1],time_seconds=0.0)),(replace(base[0],value=float("nan")),base[1]),(replace(base[0],interpolation_out="bad"),base[1]),(replace(base[0],leave_tangent=2.0),base[1]),(replace(base[0],arrive_tangent=2.0),base[1]),(base[0],replace(base[1],leave_tangent=2.0)),(replace(base[0],value=1e-320),base[1]))
 failures=0
 for keys in invalid:
  try:ref.compile_camera_scalar_track(keys,1.0,domain="reciprocal" if keys and keys[0].value==1e-320 else "linear")
  except ref.CameraScalarTrackError:failures+=1
 c.require(failures==len(invalid),"invalid validation classes");print(f"Camera scalar-track validation contracts passed ({'paste' if x.paste else 'full'}): 80 valid and {failures} failure classes")
if __name__=="__main__":main()
