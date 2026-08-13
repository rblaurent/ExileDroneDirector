"""Exact reset contracts for the v2 compiled-document source adapter."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
ARRAYS=("AirframeDocumentDiagnosticWaypointIdsV2","AirframeDocumentDiagnosticPositionVelocityJumpsV2","AirframeDocumentDiagnosticPositionAccelerationJumpsV2","AirframeDocumentDiagnosticBodyAngularRateJumpsV2","AirframeDocumentDiagnosticGimbalAngularRateJumpsV2","AirframeDocumentDiagnosticDiscontinuousFlagsV2")
SCALARS=("AirframeDocumentAdapterStageValidV2","AirframeDocumentAdapterDurationAccumulatorV2","AirframeDocumentAdapterCompileValidV2","AirframeDocumentAdapterFailureCodeV2","AirframeDocumentDiagnosticStageValidV2","AirframeDocumentDiagnosticScratchBodyLeftRateV2","AirframeDocumentDiagnosticScratchGimbalLeftRateV2","AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2","AirframeDocumentDiagnosticCountV2","AirframeDocumentDiagnosticsValidV2")
PRESERVED=("AirframeDocumentInputWaypointBodyQuatsV2","AirframeDocumentInputWaypointGimbalQuatsV2","AirframeDocumentInputWaypointPositionsV2")
def load(p):s=importlib.util.spec_from_file_location("edd_document_adapter_reset_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(23 if x.paste else 24),f"node count {len(nodes)}")
 calls=[n for n in nodes.values() if member(n)=="ResetAirframeSourceSamplingV1"];c.require(len(calls)==1,"one downstream reset")
 clears=[n for n in nodes.values() if member(n)=="Array_Clear"];c.require(len(clears)==6,"six diagnostic clears")
 getters=[n for n in nodes.values() if "K2Node_VariableGet" in n.node_class];c.require({member(n) for n in getters}==set(ARRAYS),"diagnostic clear ownership")
 setters=[n for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require({member(n) for n in setters}==set(SCALARS),"scalar reset ownership")
 text=x.graph.read_text(encoding="utf-8");c.require("CameraTransform" not in text,"legacy camera rotation forbidden");c.require(not any(name in text for name in PRESERVED),"authored v2 inputs must be preserved")
 state={name:[name,"poison"] for name in ARRAYS};state.update({name:"poison" for name in SCALARS});state.update({name:[name] for name in PRESERVED});before={name:state[name] for name in PRESERVED};calls_seen=["ResetAirframeSourceSamplingV1"]
 for name in ARRAYS:state[name]=[]
 state.update(AirframeDocumentAdapterStageValidV2=False,AirframeDocumentAdapterDurationAccumulatorV2=0.0,AirframeDocumentAdapterCompileValidV2=False,AirframeDocumentAdapterFailureCodeV2="",AirframeDocumentDiagnosticStageValidV2=False,AirframeDocumentDiagnosticScratchBodyLeftRateV2=(0.0,0.0,0.0),AirframeDocumentDiagnosticScratchGimbalLeftRateV2=(0.0,0.0,0.0),AirframeDocumentDiagnosticScratchBodyAngularRateJumpV2=0.0,AirframeDocumentDiagnosticCountV2=0,AirframeDocumentDiagnosticsValidV2=False)
 c.require(calls_seen==["ResetAirframeSourceSamplingV1"] and all(state[name]==[] for name in ARRAYS),"reset execution")
 c.require(all(state[name]==before[name] for name in PRESERVED),"authored input mutation")
 print(f"Airframe document adapter reset contracts passed ({'paste' if x.paste else 'full'}): {len(nodes)} nodes")
if __name__=="__main__":main()
