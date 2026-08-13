"""Ordered executable contracts for CompileAirframeDesiredStreamV1."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
CALLS=("ResetAirframeDesiredStreamV1","ValidateAirframeDesiredStreamInputsV1","BuildAirframeDesiredVelocitySamplesV1","BuildAirframeDesiredAccelerationSamplesV1","BuildAirframeDesiredJerkSamplesV1","SolveAirframeDesiredPoseSamplesV1","CommitAirframeDesiredStreamToPrebakeV1")
def load(p):
 s=importlib.util.spec_from_file_location("edd_desired_compile_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(7 if x.paste else 8),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry")
 calls=[next(n for n in nodes.values() if member(n)==name) for name in CALLS];c.require(all('bSelfContext=True' in n.text for n in calls),"self calls")
 if entries:c.require_link(entries[0],"then",calls[0],"execute","reset first")
 else:c.require(not calls[0].pins["execute"].links,"paste root")
 for left,right in zip(calls,calls[1:]):c.require_link(left,"then",right,"execute","ordered chain")
 known=set(nodes);c.require(not {t for n in nodes.values() for p in n.pins.values() for t,_ in p.links if t not in known},"external");c.require(not any("K2Node_Knot" in n.node_class for n in nodes.values()),"reroute")
 def execute(fail=None):
  state={"stage":False,"stream":True,"prebake":True,"calls":[]}
  for name in CALLS:
   state["calls"].append(name)
   if name==CALLS[0]:state.update(stage=False,stream=False,prebake=False)
   elif name==CALLS[1]:state["stage"]=fail not in ("validation",)
   elif name in CALLS[2:6] and fail==name:state["stage"]=False
   elif name==CALLS[6] and state["stage"] and fail!="downstream":state.update(stream=True,prebake=True)
  return state
 good=execute();c.require(good["calls"]==list(CALLS) and good["stage"] and good["stream"] and good["prebake"],"success")
 for failure in ("validation",*CALLS[2:6],"downstream"):
  result=execute(failure);c.require(result["calls"]==list(CALLS) and not result["stream"] and not result["prebake"],failure)
 c.require(execute()==good,"invocation independence")
 print(f"Airframe desired-stream compile contracts passed ({'paste' if x.paste else 'full'}): exact seven-stage order, success, 6 fail-closed injections")
if __name__=="__main__":main()
