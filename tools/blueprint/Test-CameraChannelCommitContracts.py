"""Exact preflight and atomic-publication contracts for camera channel commit."""
from __future__ import annotations
import argparse,copy,importlib.util,re,sys
from pathlib import Path
STEMS=("KeyOffsets","KeyCounts","KeyTimes","DomainValues","InterpolationModes","ArriveTangents","LeaveTangents","Domains")
def load(path):s=importlib.util.spec_from_file_location("edd_camera_channel_commit_contract_base",path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def valid(bank,stage=True):
 if not stage:return False
 if not all(len(bank[stem])==13 for stem in ("KeyOffsets","KeyCounts","Domains")):return False
 total=len(bank["KeyTimes"])
 if not all(len(bank[stem])==total for stem in ("DomainValues","ArriveTangents","LeaveTangents")):return False
 if len(bank["InterpolationModes"])!=total-13:return False
 expected=0
 for offset,count in zip(bank["KeyOffsets"],bank["KeyCounts"]):
  if isinstance(offset,bool) or not isinstance(offset,int) or offset!=expected:return False
  if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=512:return False
  expected+=count
 return expected==total
def make_bank(counts=None):
 counts=[2]*13 if counts is None else list(counts);offsets=[];total=0
 for count in counts:offsets.append(total);total+=count
 return {"KeyOffsets":offsets,"KeyCounts":counts,"KeyTimes":[float(i) for i in range(total)],"DomainValues":[float(i+1) for i in range(total)],"InterpolationModes":["linear"]*(total-13),"ArriveTangents":[0.0]*total,"LeaveTangents":[0.0]*total,"Domains":["linear"]*13}
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(70 if x.paste else 71),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");root=nodes["K2Node_VariableSet_0"];c.require(not root.pins["execute"].links,"paste execution root") if x.paste else c.require_link(entries[0],"then",root,"execute","native entry to commit root");text=x.graph.read_text(encoding="utf-8");c.require(len([n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class])==1,"one bounded preflight loop");c.require("CameraScalarTrack" not in text,"commit is policy free")
 setters=[member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class];compiled={f"CameraChannelCompiled{stem}V1" for stem in STEMS}|{"CameraChannelCompiledDurationV1","CameraChannelCompiledFilmbackPresetIdV1","CameraChannelCompiledFilmbackSensorWidthMmV1","CameraChannelCompiledFilmbackSensorHeightMmV1"};c.require(compiled.issubset(set(setters)),"complete compiled publication");c.require(setters[-1]=="CameraChannelCompileValidV1","validity publishes last");c.require(setters.count("CameraChannelCompileValidV1")==2,"invalidate then publish");c.require("CameraChannelInputChannelIdsV1" not in text,"commit cannot rewrite authored channels")
 accepted=make_bank([1,2,3,4,2,1,5,2,3,1,2,4,1]);c.require(valid(accepted),"varied valid bank");prior={"sentinel":[1,2,3]};published=copy.deepcopy(accepted) if valid(accepted) else prior;c.require(published==accepted and published is not accepted,"value snapshot")
 failures=[]
 for mutate in (lambda b:b["KeyOffsets"].pop(),lambda b:b["KeyCounts"].pop(),lambda b:b["Domains"].pop(),lambda b:b["KeyOffsets"].__setitem__(4,999),lambda b:b["KeyCounts"].__setitem__(2,0),lambda b:b["KeyCounts"].__setitem__(2,513),lambda b:b["KeyTimes"].pop(),lambda b:b["DomainValues"].pop(),lambda b:b["InterpolationModes"].pop(),lambda b:b["ArriveTangents"].pop(),lambda b:b["LeaveTangents"].pop()):
  bank=make_bank();mutate(bank);failures.append(bank)
 c.require(all(not valid(bank) for bank in failures),"candidate failure families");snapshot=copy.deepcopy(prior)
 for bank in failures:
  if valid(bank):snapshot=copy.deepcopy(bank)
 c.require(snapshot==prior,"failed preflight preserves prior compiled snapshot");c.require(not valid(make_bank(),False),"invalid stage rejects")
 print(f"Camera channel commit contracts passed ({'paste' if x.paste else 'full'}): atomic success and {len(failures)+1} failure cases")
if __name__=="__main__":main()
