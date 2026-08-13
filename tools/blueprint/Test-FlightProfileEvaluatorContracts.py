"""Exact fail-closed compiled flight-profile evaluation contracts."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

CHANNELS=(("Ids","Id"),("PathFollowWeights","PathFollowWeight"),("HorizonStabilizationWeights","HorizonStabilizationWeight"),("LookAheadSeconds","LookAheadSeconds"),("BankGains","BankGain"),("MaxBankDegrees","MaxBankDegrees"),("CameraUptiltDegrees","CameraUptiltDegrees"),("MaxAngularRatesDegreesPerSecond","MaxAngularRateDegreesPerSecond"),("MaxAccelerationsCmPerSecondSquared","MaxAccelerationCmPerSecondSquared"),("MaxJerksCmPerSecondCubed","MaxJerkCmPerSecondCubed"),("MinimumTurnRadiiCm","MinimumTurnRadiusCm"))
RESETS=(("FlightProfileEvaluationStageValidV1","false"),("FlightProfileResultIdV1",""),("FlightProfileResultPathFollowWeightV1","0.0"),("FlightProfileResultHorizonStabilizationWeightV1","0.0"),("FlightProfileResultLookAheadSecondsV1","0.0"),("FlightProfileResultBankGainV1","0.0"),("FlightProfileResultMaxBankDegreesV1","0.0"),("FlightProfileResultCameraUptiltDegreesV1","0.0"),("FlightProfileResultMaxAngularRateDegreesPerSecondV1","0.0"),("FlightProfileResultMaxAccelerationCmPerSecondSquaredV1","0.0"),("FlightProfileResultMaxJerkCmPerSecondCubedV1","0.0"),("FlightProfileResultMinimumTurnRadiusCmV1","0.0"),("FlightProfileResultValidV1","false"))
def load(root):
 p=root/"tools/blueprint/Test-WaypointCaptureContracts.py";s=importlib.util.spec_from_file_location("edd_flight_profile_evaluator_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def default(n,p):
 m=re.search(r'(?:^|,)DefaultValue="([^"]*)"',n.pins[p].body);return None if m is None else m.group(1)
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);ns=c.parse_graph(a.graph);c.require(len(ns)==(141 if a.paste else 142),f"evaluator node count {len(ns)}")
 entries=[n for n in ns.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
 reset_nodes=[]
 for name,value in RESETS:
  matches=[n for n in ns.values() if f'MemberName="{name}"' in n.text and "K2Node_VariableSet" in n.node_class and default(n,name)==value];c.require(matches,f"reset missing {name}");reset_nodes.append(matches[0])
 if a.paste:c.require(not reset_nodes[0].pins["execute"].links,"paste root")
 else:c.require_link(entries[0],"then",reset_nodes[0],"execute","entry reset")
 for l,r in zip(reset_nodes,reset_nodes[1:]):c.require_link(l,"then",r,"execute","result reset order")
 compiled=[];lengths=[n for n in ns.values() if 'MemberName="Array_Length"' in n.text];c.require(len(lengths)==11,"eleven compiled lengths")
 for suf,_rs in CHANNELS:
  name=f"FlightProfileCompiled{suf}V1";g=c.one(ns,f'MemberName="{name}"');compiled.append(g);c.require(any(c.linked(g,name,n,"TargetArray") for n in lengths),f"length {name}")
 count=next(n for n in lengths if c.linked(compiled[0],"FlightProfileCompiledIdsV1",n,"TargetArray"));valid=c.one(ns,'MemberName="FlightProfileCompileValidV1"');index=c.one(ns,'MemberName="FlightProfileInputSegmentIndexV1"')
 ge=[n for n in ns.values() if 'MemberName="GreaterEqual_IntInt"' in n.text];le=c.one(ns,'MemberName="LessEqual_IntInt"');lt=c.one(ns,'MemberName="Less_IntInt"');c.require(len(ge)==2,"count/index lower bounds");c.require(default(le,"B")=="511","maximum bound")
 c.require(any(default(n,"B")=="1" and c.linked(count,"ReturnValue",n,"A") for n in ge),"minimum count");c.require(any(default(n,"B")=="0" and c.linked(index,"FlightProfileInputSegmentIndexV1",n,"A") for n in ge),"minimum index");c.require_link(index,"FlightProfileInputSegmentIndexV1",lt,"A","index upper source");c.require_link(count,"ReturnValue",lt,"B","index upper bound")
 int_eq=[n for n in ns.values() if 'MemberName="EqualEqual_IntInt"' in n.text];c.require(len(int_eq)==10,"ten remaining cardinalities")
 for ln in lengths[1:]:c.require(any(c.linked(ln,"ReturnValue",n,"A") and c.linked(count,"ReturnValue",n,"B") for n in int_eq),"compiled cardinality equality")
 branches=[n for n in ns.values() if "K2Node_IfThenElse" in n.node_class];c.require(len(branches)==3,"pre/integrity/final guards");pre=next(n for n in branches if c.linked(reset_nodes[-1],"then",n,"execute"))
 stage_sets=[n for n in ns.values() if 'MemberName="FlightProfileEvaluationStageValidV1"' in n.text and "K2Node_VariableSet" in n.node_class];c.require(len(stage_sets)==3,"evaluation stage reset/accept/reject");accept=next(n for n in stage_sets if default(n,"FlightProfileEvaluationStageValidV1")=="true");reject=next(n for n in stage_sets if n is not reset_nodes[0] and default(n,"FlightProfileEvaluationStageValidV1")=="false");c.require_link(pre,"then",accept,"execute","valid preconditions begin scan");c.require_link(pre,"else",reject,"execute","precondition failure rejects")
 loops=[n for n in ns.values() if "K2Node_MacroInstance" in n.node_class];c.require(len(loops)==1,"one integrity loop");loop=loops[0];c.require_link(compiled[0],"FlightProfileCompiledIdsV1",loop,"Array","compiled ID scan");c.require_link(accept,"then",loop,"Exec","stage acceptance starts scan")
 resolver_input=c.one(ns,'MemberName="FlightProfileResolveInputIdV1"');resolver=c.one(ns,'MemberName="ResolveFlightProfilePresetV1"');c.require_link(loop,"Array Element",resolver_input,"FlightProfileResolveInputIdV1","resolver staging");c.require_link(resolver_input,"then",resolver,"execute","resolver call")
 rvalid=c.one(ns,'MemberName="FlightProfileResolveResultValidV1"');rid=c.one(ns,'MemberName="FlightProfileResolveResultIdV1"');ideq=c.one(ns,'MemberName="EqualEqual_StrStr"');c.require_link(rid,"FlightProfileResolveResultIdV1",ideq,"A","resolved identity");c.require_link(loop,"Array Element",ideq,"B","compiled identity")
 items=[n for n in ns.values() if "K2Node_GetArrayItem" in n.node_class];real_eq=[n for n in ns.values() if 'MemberName="EqualEqual_DoubleDouble"' in n.text];c.require(len(items)==21 and len(real_eq)==10,"scan and selected reads")
 scan_items=[];selected_items=[]
 for (suf,rs),cg in zip(CHANNELS,compiled):
  cn=f"FlightProfileCompiled{suf}V1";reads=[n for n in items if c.linked(cg,cn,n,"Array")];c.require(len(reads)==(1 if suf=="Ids" else 2),f"reads {cn}")
  if suf!="Ids":
   scan=next(n for n in reads if c.linked(loop,"Array Index",n,"Dimension 1"));scan_items.append(scan);rn=f"FlightProfileResolveResult{rs}V1";rg=c.one(ns,f'MemberName="{rn}"');c.require(any(c.linked(scan,"Output",eq,"A") and c.linked(rg,rn,eq,"B") for eq in real_eq),f"integrity {suf}")
  selected=next(n for n in reads if c.linked(index,"FlightProfileInputSegmentIndexV1",n,"Dimension 1"));selected_items.append(selected)
 integrity=next(n for n in branches if c.linked(resolver,"then",n,"execute"));c.require_link(integrity,"else",reject,"execute","corruption rejects")
 stage_get=[n for n in ns.values() if 'MemberName="FlightProfileEvaluationStageValidV1"' in n.text and "K2Node_VariableGet" in n.node_class];c.require(len(stage_get)==1,"one final stage read");final=next(n for n in branches if c.linked(loop,"Completed",n,"execute") and c.linked(stage_get[0],"FlightProfileEvaluationStageValidV1",n,"Condition"))
 pubs=[]
 for (suf,rs),selected in zip(CHANNELS,selected_items):
  rn=f"FlightProfileResult{rs}V1";matches=[n for n in ns.values() if f'MemberName="{rn}"' in n.text and "K2Node_VariableSet" in n.node_class and n not in reset_nodes];c.require(len(matches)==1,f"publication {rn}");c.require_link(selected,"Output",matches[0],rn,f"selected source {rn}");pubs.append(matches[0])
 c.require_link(final,"then",pubs[0],"execute","final validation begins publication")
 for l,r in zip(pubs,pubs[1:]):c.require_link(l,"then",r,"execute","result publication order")
 done=[n for n in ns.values() if 'MemberName="FlightProfileResultValidV1"' in n.text and "K2Node_VariableSet" in n.node_class and default(n,"FlightProfileResultValidV1")=="true"];c.require(len(done)==1,"validity publication");c.require_link(pubs[-1],"then",done[0],"execute","result validity last")
 known=set(ns);external={t for n in ns.values() for pin in n.pins.values() for t,_ in pin.links if t not in known};c.require(not external,f"external links {external}");print(f"Flight-profile evaluator contracts passed ({'paste' if a.paste else 'full'}): {len(ns)} nodes")
if __name__=="__main__":main()
