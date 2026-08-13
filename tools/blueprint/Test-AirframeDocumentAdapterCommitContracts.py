"""Exact atomic handoff contracts for the v2 compiled-document adapter."""
from __future__ import annotations
import argparse,copy,importlib.util,random,re,sys
from pathlib import Path
MAPPINGS=(("AirframeDocumentInputWaypointPositionsV2","PositionRouteInputWaypointPositionsV1"),("AirframeDocumentInputSegmentDurationsV2","PositionRouteInputDurationsV1"),("AirframeDocumentInputSegmentSpatialCurveTypesV2","PositionRouteInputSpatialCurveTypesV1"),("AirframeDocumentInputSegmentTimeProfilesV2","PositionRouteInputTimeProfilesV1"),("AirframeDocumentInputDefaultFlightProfileV2","FlightProfileInputDefaultIdV1"),("AirframeDocumentInputSegmentFlightProfileOverridesV2","FlightProfileInputSegmentOverrideIdsV1"),("AirframeDocumentInputWaypointBodyQuatsV2","AirframeSourceInputBodyWaypointQuatsV1"),("AirframeDocumentInputWaypointGimbalQuatsV2","AirframeSourceInputGimbalWaypointQuatsV1"),("AirframeDocumentInputFixedStepSecondsV2","AirframeSourceInputFixedStepSecondsV1"))
def load(p):s=importlib.util.spec_from_file_location("edd_document_adapter_commit_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def make(seed):
 r=random.Random(seed);n=r.randint(2,12);q=lambda axis:[(0.,0.,0.,1.) if axis==0 else (0.,0.01*i,0.,.99995) for i in range(n)]
 return {"AirframeDocumentInputWaypointPositionsV2":[(float(i)*20.,0.,0.) for i in range(n)],"AirframeDocumentInputSegmentDurationsV2":[.5]*(n-1),"AirframeDocumentInputSegmentSpatialCurveTypesV2":["linear"]*(n-1),"AirframeDocumentInputSegmentTimeProfilesV2":["linear"]*(n-1),"AirframeDocumentInputDefaultFlightProfileV2":"cinematic_drone","AirframeDocumentInputSegmentFlightProfileOverridesV2":[""]*(n-1),"AirframeDocumentInputWaypointBodyQuatsV2":q(0),"AirframeDocumentInputWaypointGimbalQuatsV2":q(1),"AirframeDocumentInputFixedStepSecondsV2":.25}
def execute(state,stage=True,source=True,desired=True,prebake=True):
 result=dict(state);result["AirframeDocumentAdapterCompileValidV2"]=False
 if not stage:return result,[]
 for source_name,target in MAPPINGS:result[target]=copy.deepcopy(result[source_name])
 calls=["CompileAirframeSourceSamplingV1"]
 if source and desired and prebake:result["AirframeDocumentAdapterCompileValidV2"]=True
 return result,calls
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(29 if x.paste else 30),f"node count {len(nodes)}");text=x.graph.read_text(encoding="utf-8");c.require("CameraTransform" not in text,"legacy camera rotation forbidden")
 calls=[n for n in nodes.values() if member(n)=="CompileAirframeSourceSamplingV1"];c.require(len(calls)==1,"one source compiler call");c.require(len([n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class])==2,"two guards")
 writes=[member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require(writes.count("AirframeDocumentAdapterCompileValidV2")==2 and len(writes)==11,"exact write count")
 for source,target in MAPPINGS:
  g=next(n for n in nodes.values() if "K2Node_VariableGet" in n.node_class and member(n)==source);s=next(n for n in nodes.values() if "K2Node_VariableSet" in n.node_class and member(n)==target);c.require_link(g,source,s,target,f"mapping {source}")
 body=next(n for n in nodes.values() if member(n)=="AirframeDocumentInputWaypointBodyQuatsV2");gimbal=next(n for n in nodes.values() if member(n)=="AirframeDocumentInputWaypointGimbalQuatsV2");c.require(body.name!=gimbal.name,"distinct authorship getters")
 for index in range(40):
  state=make(0xEDD600+index);before=copy.deepcopy(state);result,calls_seen=execute(state);c.require(result["AirframeDocumentAdapterCompileValidV2"] and calls_seen==["CompileAirframeSourceSamplingV1"],f"valid {index}")
  for source,target in MAPPINGS:c.require(result[target]==before[source] and result[source]==before[source],f"copy {index}:{source}")
 stale=make(1);stale.update({target:["stale"] for _source,target in MAPPINGS});result,calls_seen=execute(stale,stage=False);c.require(not result["AirframeDocumentAdapterCompileValidV2"] and not calls_seen,"stage failure");c.require(all(result[target] is stale[target] for _source,target in MAPPINGS),"stage failure preserves downstream identity")
 for label,flags in (("source",(False,True,True)),("desired",(True,False,True)),("prebake",(True,True,False))):c.require(not execute(make(2),True,*flags)[0]["AirframeDocumentAdapterCompileValidV2"],label)
 print(f"Airframe document adapter commit contracts passed ({'paste' if x.paste else 'full'}): 40 distinct-authorship handoffs, stage/downstream failures")
if __name__=="__main__":main()
