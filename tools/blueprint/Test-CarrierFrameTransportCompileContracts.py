"""Exact ordered contracts for CompileCarrierFrameTransportV1."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
CALLS=("ResetCarrierFrameTransportV1","StageCarrierFrameTransportInputsV1","ValidateCarrierFrameTransportInputsV1","BuildCarrierFrameTangentsV1","BuildCarrierFrameTransportSamplesV1","CommitCompiledCarrierFrameTransportV1")
def load(path):s=importlib.util.spec_from_file_location("edd_carrier_compile_contract_base",path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(a.graph);c.require(len(nodes)==(6 if a.paste else 7),f"coordinator node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry");calls=[next(n for n in nodes.values() if member(n)==name) for name in CALLS];c.require(all('bSelfContext=True' in n.text for n in calls),"self calls")
 if entries:c.require_link(entries[0],"then",calls[0],"execute","reset first")
 else:c.require(not calls[0].pins["execute"].links,"paste root")
 for left,right in zip(calls,calls[1:]):c.require_link(left,"then",right,"execute","exact ordered carrier transaction")
 c.require(not [n for n in nodes.values() if "K2Node_Variable" in n.node_class or "K2Node_IfThenElse" in n.node_class or "K2Node_MacroInstance" in n.node_class],"coordinator owns no policy or state");known=set(nodes);c.require(not {target for n in nodes.values() for pin in n.pins.values() for target,_ in pin.links if target not in known},"external links");c.require(not any("K2Node_Knot" in n.node_class for n in nodes.values()),"reroute")
 for failure in (None,*CALLS[1:]):
  state={"calls":[],"valid":False}
  for name in CALLS:
   state["calls"].append(name)
   if name==CALLS[0]:state["valid"]=False
   elif name==failure:state["valid"]=False
   elif name==CALLS[-1] and failure is None:state["valid"]=True
  c.require(state["calls"]==list(CALLS),f"all calls execute:{failure}");c.require(state["valid"] is (failure is None),f"result:{failure}")
 print(f"Carrier-frame compile contracts passed ({'paste' if a.paste else 'full'}): exact six-call order")
if __name__=="__main__":main()
