"""Executable contracts for desired-stream transactional prebake handoff."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

CANDS=(("AirframeDesiredStreamCandidateLookAheadVelocitiesV1",None),("AirframeDesiredStreamCandidateBodyQuatsV1","AirframePrebakeInputDesiredBodyQuatsV1"),("AirframeDesiredStreamCandidateGimbalQuatsV1","AirframePrebakeInputDesiredGimbalQuatsV1"),("AirframeDesiredStreamCandidateMaxAngularRatesDegreesPerSecondV1","AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"))
STAGE="AirframeDesiredStreamStageValidV1";INDEX="AirframeDesiredStreamStageIndexV1";VALID="AirframeDesiredStreamCompileValidV1";TOTAL="AirframeDesiredStreamInputTotalSecondsV1";STEP="AirframeDesiredStreamInputFixedStepSecondsV1"
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def default(n,p):
 m=re.search(r'(?:^|,)DefaultValue="([^"]*)"',n.pins[p].body);return "" if m is None else m.group(1)
class I:
 def __init__(self,nodes,state,prebake,force_fail=False):
  self.nodes=nodes;self.state=dict(state);self.prebake=prebake;self.force_fail=force_fail;self.owners={}
  for n in nodes.values():
   for p in n.pins.values():
    m=re.search(r"PinId=([0-9A-F]{32})",p.body)
    if m:self.owners[(n.name,m.group(1))]=(n,p)
 def source(self,n,p):
  for l in n.pins[p].links:
   t=self.owners[l]
   if 'Direction="EGPD_Output"' in t[1].body:return t[0],t[1].name
 def value(self,n,p):
  q=self.source(n,p)
  if q:return self.output(*q)
  t=default(n,p)
  if t=="true":return True
  if t=="false":return False
  try:return int(t) if re.fullmatch(r"-?\d+",t) else float(t)
  except:return t
 def output(self,n,p):
  if "K2Node_Variable" in n.node_class:return self.state[member(n)]
  m=member(n)
  if m=="Array_Length":return len(self.value(n,"TargetArray"))
  a,b=self.value(n,"A"),self.value(n,"B")
  if m=="Subtract_IntInt":return int(a)-int(b)
  if m=="GreaterEqual_IntInt":return int(a)>=int(b)
  if m=="LessEqual_IntInt":return int(a)<=int(b)
  if m=="EqualEqual_IntInt":return int(a)==int(b)
  if m=="BooleanAND":return bool(a) and bool(b)
  raise RuntimeError(m)
 def nxt(self,n,p="then"):
  if p not in n.pins:return None
  for l in n.pins[p].links:
   t=self.owners[l]
   if t[1].name=="execute":return t[0]
 def run(self):
  es=[n for n in self.nodes.values() if "K2Node_FunctionEntry" in n.node_class];cur=self.nxt(es[0]) if es else next(n for n in self.nodes.values() if "execute" in n.pins and not n.pins["execute"].links)
  while cur:
   m=member(cur)
   if "K2Node_VariableSet" in cur.node_class:
    v=self.value(cur,m);self.state[m]=list(v) if "PinType.ContainerType=Array" in cur.pins[m].body else v;cur=self.nxt(cur)
   elif "K2Node_IfThenElse" in cur.node_class:cur=self.nxt(cur,"then" if self.value(cur,"Condition") else "else")
   elif m=="CompileAirframePrebakeV1":
    try:
     if self.force_fail:raise ValueError("injected")
     self.prebake.compile_airframe_gimbal_motion(self.state["AirframePrebakeInputDesiredBodyQuatsV1"],self.state["AirframePrebakeInputDesiredGimbalQuatsV1"],self.state["AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1"],self.state["AirframePrebakeInputTotalSecondsV1"],self.state["AirframePrebakeInputFixedStepSecondsV1"])
    except Exception:self.state["AirframePrebakeCompileValidV1"]=False
    else:self.state["AirframePrebakeCompileValidV1"]=True
    cur=self.nxt(cur)
   else:raise RuntimeError(m)
  return self.state
def state(count=5):
 q=[(0.0,0.0,0.0,1.0)]*count
 d={CANDS[0][0]:[(float(i),0.0,0.0) for i in range(count)],CANDS[1][0]:q,CANDS[2][0]:q,CANDS[3][0]:[180.0]*count,STAGE:True,INDEX:count-1,VALID:True,TOTAL:1.0,STEP:0.25,"AirframePrebakeCompileValidV1":True,"AirframePrebakeInputDesiredBodyQuatsV1":["stale"],"AirframePrebakeInputDesiredGimbalQuatsV1":["stale"],"AirframePrebakeInputMaxAngularRatesDegreesPerSecondV1":["stale"],"AirframePrebakeInputTotalSecondsV1":99.0,"AirframePrebakeInputFixedStepSecondsV1":99.0};return d
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_desired_commit_contract_base");sys.path.insert(0,str(x.project_root/"tools/trajectory"));p=load(x.project_root/"tools/trajectory/airframe_gimbal_prebake_reference.py","edd_desired_commit_prebake");nodes=c.parse_graph(x.graph)
 c.require(len(nodes)==(36 if x.paste else 37),f"node count {len(nodes)}");c.require(len([n for n in nodes.values() if member(n)=="Array_Length"])==4,"four lengths");c.require(len([n for n in nodes.values() if member(n)=="CompileAirframePrebakeV1"])==1,"one compile call");c.require(len([n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class])==2,"two guards")
 writes=[member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require(writes.count(VALID)==2 and len(writes)==7,"exact write boundary");known=set(nodes);c.require(not {t for n in nodes.values() for z in n.pins.values() for t,_ in z.links if t not in known},"external")
 good=state();original={k:good[k] for k,_ in CANDS};r=I(nodes,good,p).run();c.require(r[VALID] is True and r["AirframePrebakeCompileValidV1"] is True,"valid commit")
 for source,target in CANDS[1:]:c.require(r[target]==good[source] and r[target] is not original[source] and r[source] is original[source],source)
 c.require(r["AirframePrebakeInputTotalSecondsV1"]==1.0 and r["AirframePrebakeInputFixedStepSecondsV1"]==0.25,"schedule copy")
 invalid=[]
 for mutation in (lambda d:d.update({STAGE:False}),lambda d:d.update({INDEX:2}),lambda d:d[CANDS[0][0]].pop(),lambda d:d[CANDS[2][0]].pop()):
  d=state();mutation(d);invalid.append(d)
 for i,d in enumerate(invalid):
  before=[d["AirframePrebakeInputDesiredBodyQuatsV1"]];r=I(nodes,d,p).run();c.require(r[VALID] is False and r["AirframePrebakeInputDesiredBodyQuatsV1"] is before[0],f"preflight {i}")
 failed=I(nodes,state(),p,True).run();c.require(failed[VALID] is False and failed["AirframePrebakeCompileValidV1"] is False,"downstream failure")
 second=I(nodes,{**r,**state(),STAGE:False},p).run();c.require(second[VALID] is False,"repeat failure")
 print(f"Airframe desired-stream commit contracts passed ({'paste' if x.paste else 'full'}): valid handoff, 4 preflight failures, downstream failure, invocation independence")
if __name__=="__main__":main()
