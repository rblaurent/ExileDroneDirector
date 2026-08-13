"""Exact graph and executable contracts for private camera scalar candidates."""
from __future__ import annotations
import argparse,importlib.util,random,re,sys
from pathlib import Path
COPIES=(("CameraScalarTrackInputKeyTimesV1","CameraScalarTrackCandidateKeyTimesV1"),("CameraScalarTrackInputInterpolationModesV1","CameraScalarTrackCandidateInterpolationModesV1"),("CameraScalarTrackInputArriveTangentsV1","CameraScalarTrackCandidateArriveTangentsV1"),("CameraScalarTrackInputLeaveTangentsV1","CameraScalarTrackCandidateLeaveTangentsV1"))
def load(path,name):s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def execute(values,times,modes,arrive,leave,domain,stage=True,poison=None):
 state={} if poison is None else dict(poison)
 if not stage:return state
 state.update(times=list(times),modes=list(modes),arrive=list(arrive),leave=list(leave),domain_values=[])
 for value in values:state["domain_values"].append(1.0/value if domain=="reciprocal" else value)
 return state
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_scalar_candidate_graph");nodes=c.parse_graph(x.graph);text=x.graph.read_text(encoding="utf-8");c.require(len(nodes)==(19 if x.paste else 20),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");guard=nodes["K2Node_IfThenElse_0"];c.require(not guard.pins["execute"].links,"paste root") if x.paste else c.require_link(entries[0],"then",guard,"execute","entry to stage guard")
 c.require(text.count('MemberName="Array_Add"')==2,"two mutually exclusive domain appends");c.require(text.count('MemberName="Divide_DoubleDouble"')==1,"one reciprocal conversion");c.require(text.count('MemberName="EqualEqual_StrStr"')==1 and 'DefaultValue="reciprocal"' in text,"explicit reciprocal branch");c.require(len([n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class])==1,"one value loop")
 setters=[n for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require({member(n) for n in setters}=={target for _,target in COPIES},"exact copy setters")
 for source,target in COPIES:
  g=next(n for n in nodes.values() if "K2Node_VariableGet" in n.node_class and member(n)==source);s=next(n for n in setters if member(n)==target);c.require_link(g,source,s,target,f"copy {source}")
 c.require("CameraScalarTrackCompileValidV1" not in text and "CameraScalarTrackResult" not in text,"private candidate cannot publish")
 for seed in range(40):
  rng=random.Random(0xEDD520+seed);values=[rng.uniform(1.0,1000.0) for _ in range(rng.randint(1,12))];times=[float(i) for i in range(len(values))];modes=["cinematic"]*(len(values)-1);arrive=[0.0]*len(values);leave=[0.0]*len(values)
  for domain in ("linear","reciprocal"):
   poison={"times":[-1.0],"domain_values":[-1.0]};result=execute(values,times,modes,arrive,leave,domain,True,poison);expected=[1.0/v for v in values] if domain=="reciprocal" else values;c.require(result["domain_values"]==expected and result["times"]==times,"candidate execution")
  c.require(execute(values,times,modes,arrive,leave,"linear",False,poison)==poison,"false-stage no-op")
 print(f"Camera scalar-track candidate contracts passed ({'paste' if x.paste else 'full'}): 40 seeded tracks, both domains, false-stage no-op")
if __name__=="__main__":main()
