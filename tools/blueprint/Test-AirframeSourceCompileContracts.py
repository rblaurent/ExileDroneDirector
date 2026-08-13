"""Exact ordered contracts for CompileAirframeSourceSamplingV1."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
CALLS=("ResetAirframeSourceSamplingV1","ValidateAirframeSourceSamplingInputsV1","CompileAirframeSourcePositionProfilesV1","BuildAirframeSourcePositionBodyProfileSamplesV1","BuildAirframeSourceGimbalSamplesV1","CommitAirframeSourceSamplesToDesiredV1")
def load(p):
 s=importlib.util.spec_from_file_location("edd_source_compile_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(6 if x.paste else 7),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry")
 calls=[next(n for n in nodes.values() if member(n)==name) for name in CALLS];c.require(all('bSelfContext=True' in n.text for n in calls),"self calls")
 if entries:c.require_link(entries[0],"then",calls[0],"execute","reset first")
 else:c.require(not calls[0].pins["execute"].links,"paste root")
 for left,right in zip(calls,calls[1:]):c.require_link(left,"then",right,"execute","ordered chain")
 c.require(not [n for n in nodes.values() if "K2Node_Variable" in n.node_class or "K2Node_IfThenElse" in n.node_class or "K2Node_MacroInstance" in n.node_class],"orchestrator owns no policy or state")
 known=set(nodes);c.require(not {t for n in nodes.values() for p in n.pins.values() for t,_ in p.links if t not in known},"external");c.require(not any("K2Node_Knot" in n.node_class for n in nodes.values()),"reroute")
 for failure in (None,*CALLS[1:]):
  state={"calls":[],"source":True,"desired":True,"prebake":True}
  for name in CALLS:
   state["calls"].append(name)
   if name==CALLS[0]:state.update(source=False,desired=False,prebake=False)
   elif name==failure:state["source"]=False
   elif name==CALLS[-1] and failure is None:state.update(source=True,desired=True,prebake=True)
  c.require(state["calls"]==list(CALLS),f"all calls execute {failure}")
  if failure is None:c.require(state["source"] and state["desired"] and state["prebake"],"success")
  else:c.require(not state["source"] and not state["desired"] and not state["prebake"],f"failure {failure}")
 print(f"Airframe source compile contracts passed ({'paste' if x.paste else 'full'}): exact six-call order, success, five fail-closed injections")
if __name__=="__main__":main()
