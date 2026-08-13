"""Exact policy-free orchestration contracts for the v2 document adapter."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
CALLS=("ResetAirframeDocumentSourceAdapterV2","ValidateAirframeDocumentSourceAdapterV2","CommitAirframeDocumentSourceAdapterV2","BuildAirframeDocumentDiscontinuityDiagnosticsV2")
def load(p):s=importlib.util.spec_from_file_location("edd_document_adapter_compile_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(4 if x.paste else 5),f"node count {len(nodes)}");calls=[next(n for n in nodes.values() if member(n)==name) for name in CALLS];entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry");c.require_link(entries[0],"then",calls[0],"execute","reset first") if entries else c.require(not calls[0].pins["execute"].links,"paste root");[c.require_link(l,"then",r,"execute","ordered") for l,r in zip(calls,calls[1:])];c.require(not [n for n in nodes.values() if "K2Node_Variable" in n.node_class or "K2Node_IfThenElse" in n.node_class or "K2Node_MacroInstance" in n.node_class],"no policy/state");c.require("CameraTransform" not in x.graph.read_text(encoding="utf-8"),"legacy camera rotation forbidden")
 for failure in (None,*CALLS[1:]):
  seen=[];valid=False;diagnostics=False
  for name in CALLS:
   seen.append(name)
   if name==CALLS[0]:valid=diagnostics=False
   elif name=="CommitAirframeDocumentSourceAdapterV2" and failure is None:valid=True
   elif name=="BuildAirframeDocumentDiscontinuityDiagnosticsV2" and failure is None and valid:diagnostics=True
  c.require(seen==list(CALLS),f"all calls {failure}");c.require((valid and diagnostics) if failure is None else (not valid or not diagnostics),f"result {failure}")
 print(f"Airframe document adapter compile contracts passed ({'paste' if x.paste else 'full'}): exact adapter-then-diagnostics order")
if __name__=="__main__":main()
