"""Executable contracts for atomic source-to-desired stream publication."""
from __future__ import annotations
import argparse, copy, importlib.util, math, random, re, sys
from pathlib import Path

ARRAYS=(
 ("AirframeSourceCandidatePositionsV1","AirframeDesiredStreamInputPositionsV1","positions"),
 ("AirframeSourceCandidateBodyQuatsV1","AirframeDesiredStreamInputAuthoredBodyQuatsV1","body"),
 ("AirframeSourceCandidateGimbalQuatsV1","AirframeDesiredStreamInputAuthoredGimbalQuatsV1","gimbal"),
 ("AirframeSourceCandidatePathFollowWeightsV1","AirframeDesiredStreamInputPathFollowWeightsV1","path_follow_weight"),
 ("AirframeSourceCandidateHorizonStabilizationWeightsV1","AirframeDesiredStreamInputHorizonStabilizationWeightsV1","horizon_stabilization_weight"),
 ("AirframeSourceCandidateLookAheadSecondsV1","AirframeDesiredStreamInputLookAheadSecondsV1","look_ahead_seconds"),
 ("AirframeSourceCandidateBankGainsV1","AirframeDesiredStreamInputBankGainsV1","bank_gain"),
 ("AirframeSourceCandidateMaxBankDegreesV1","AirframeDesiredStreamInputMaxBankDegreesV1","max_bank_degrees"),
 ("AirframeSourceCandidateCameraUptiltDegreesV1","AirframeDesiredStreamInputCameraUptiltDegreesV1","camera_uptilt_degrees"),
 ("AirframeSourceCandidateMaxAngularRatesDegreesPerSecondV1","AirframeDesiredStreamInputMaxAngularRatesDegreesPerSecondV1","max_angular_rate_degrees_per_second"),
 ("AirframeSourceCandidateMaxAccelerationsCmPerSecondSquaredV1","AirframeDesiredStreamInputMaxAccelerationsCmPerSecondSquaredV1","max_acceleration_cm_per_second_squared"),
 ("AirframeSourceCandidateMaxJerksCmPerSecondCubedV1","AirframeDesiredStreamInputMaxJerksCmPerSecondCubedV1","max_jerk_cm_per_second_cubed"),
 ("AirframeSourceCandidateMinimumTurnRadiiCmV1","AirframeDesiredStreamInputMinimumTurnRadiiCmV1","minimum_turn_radius_cm"),
)
VALID="AirframeSourceCompileValidV1";STAGE="AirframeSourceStageValidV1";COUNT="AirframeSourceExpectedSampleCountV1";TOTAL="AirframeSourceTotalSecondsV1";STEP="AirframeSourceInputFixedStepSecondsV1"
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(n):
 m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def default(n,p):
 m=re.search(r'(?:^|,)DefaultValue="([^"]*)"',n.pins[p].body);return None if m is None else m.group(1)
class Interpreter:
 def __init__(self,nodes,state,desired,gimbal,force_desired=False,force_prebake=False):
  self.nodes=nodes;self.state=dict(state);self.desired=desired;self.gimbal=gimbal;self.force_desired=force_desired;self.force_prebake=force_prebake;self.calls=[];self.owners={};self.cache={}
  for n in nodes.values():
   for p in n.pins.values():
    m=re.search(r"PinId=([0-9A-F]{32})",p.body)
    if m:self.owners[(n.name,m.group(1))]=(n,p)
 def source(self,n,p):
  for link in n.pins[p].links:
   target=self.owners[link]
   if 'Direction="EGPD_Output"' in target[1].body:return target[0],target[1].name
 def value(self,n,p):
  source=self.source(n,p)
  if source:return self.output(*source)
  text=default(n,p)
  if text=="true":return True
  if text=="false":return False
  if text is None or text=="":
   body=n.pins[p].body
   if 'PinType.PinCategory="int"' in body:return 0
   if 'PinType.PinCategory="real"' in body:return 0.0
   if 'PinType.PinCategory="bool"' in body:return False
  try:return int(text) if re.fullmatch(r"-?\d+",text or "") else float(text)
  except:return text
 def output(self,n,p):
  key=(n.name,p)
  if key in self.cache:return self.cache[key]
  if "K2Node_Variable" in n.node_class:value=self.state[member(n)]
  elif member(n)=="Array_Length":value=len(self.value(n,"TargetArray"))
  else:
   name=member(n);a,b=self.value(n,"A"),self.value(n,"B")
   if name=="GreaterEqual_IntInt":value=int(a)>=int(b)
   elif name=="LessEqual_IntInt":value=int(a)<=int(b)
   elif name=="EqualEqual_IntInt":value=int(a)==int(b)
   elif name=="BooleanAND":value=bool(a) and bool(b)
   else:raise RuntimeError(name)
  self.cache[key]=value;return value
 def nxt(self,n,p="then"):
  if p not in n.pins:return None
  for link in n.pins[p].links:
   target=self.owners[link]
   if target[1].name=="execute":return target[0]
 def invoke(self):
  self.calls.append("CompileAirframeDesiredStreamV1")
  profiles=[]
  for i in range(len(self.state[ARRAYS[0][1]])):
   profiles.append(self.gimbal.AirframeGimbalProfile(**{field:self.state[target][i] for _source,target,field in ARRAYS[3:]}))
  try:
   if self.force_desired:raise ValueError("desired injected")
   self.desired.compile_airframe_desired_stream(self.state[ARRAYS[0][1]],self.state[ARRAYS[1][1]],self.state[ARRAYS[2][1]],profiles,self.state["AirframeDesiredStreamInputTotalSecondsV1"],self.state["AirframeDesiredStreamInputFixedStepSecondsV1"])
  except Exception:self.state["AirframeDesiredStreamCompileValidV1"]=False;self.state["AirframePrebakeCompileValidV1"]=False
  else:self.state["AirframeDesiredStreamCompileValidV1"]=True;self.state["AirframePrebakeCompileValidV1"]=not self.force_prebake
 def run(self):
  entries=[n for n in self.nodes.values() if "K2Node_FunctionEntry" in n.node_class];cur=self.nxt(entries[0]) if entries else next(n for n in self.nodes.values() if "execute" in n.pins and not n.pins["execute"].links)
  while cur:
   name=member(cur)
   if "K2Node_VariableSet" in cur.node_class:
    value=self.value(cur,name);self.state[name]=list(value) if "PinType.ContainerType=Array" in cur.pins[name].body else value;self.cache.clear();cur=self.nxt(cur)
   elif "K2Node_IfThenElse" in cur.node_class:cur=self.nxt(cur,"then" if self.value(cur,"Condition") else "else")
   elif name=="CompileAirframeDesiredStreamV1":self.invoke();self.cache.clear();cur=self.nxt(cur)
   else:raise RuntimeError(name)
  return self.state
def make_state(count=5,step=.25,total=None):
 total=(count-1)*step if total is None else total;identity=(0.,0.,0.,1.);defaults=(.65,.7,.45,.55,25.,4.,120.,900.,1800.,250.)
 times=[min(i*step,total) for i in range(count)];sources=[[(20.*time,0.,0.) for time in times],[identity]*count,[identity]*count,*[[value]*count for value in defaults]]
 state={source:value for (source,_target,_field),value in zip(ARRAYS,sources)};state.update({STAGE:True,COUNT:count,TOTAL:total,STEP:step,VALID:True,"AirframeDesiredStreamCompileValidV1":True,"AirframePrebakeCompileValidV1":True,"AirframeDesiredStreamInputTotalSecondsV1":99.,"AirframeDesiredStreamInputFixedStepSecondsV1":99.})
 for _source,target,_field in ARRAYS:state[target]=["downstream-stale"]
 return state
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_source_commit_contract_base");trajectory=str(x.project_root/"tools/trajectory");sys.path.insert(0,trajectory) if trajectory not in sys.path else None;desired=load(x.project_root/"tools/trajectory/airframe_desired_stream_reference.py","airframe_desired_stream_reference");gimbal=sys.modules["airframe_gimbal_reference"];nodes=c.parse_graph(x.graph)
 c.require(len(nodes)==(83 if x.paste else 84),f"node count {len(nodes)}");c.require(len([n for n in nodes.values() if member(n)=="Array_Length"])==13,"thirteen lengths");c.require(len([n for n in nodes.values() if member(n)=="CompileAirframeDesiredStreamV1"])==1,"one desired call");c.require(len([n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class])==2,"two guards")
 writes=[member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require(writes.count(VALID)==2 and len(writes)==17,"exact write boundary");c.require(set(writes)=={VALID,"AirframeDesiredStreamInputTotalSecondsV1","AirframeDesiredStreamInputFixedStepSecondsV1",*(target for _source,target,_field in ARRAYS)},"only desired publication writes")
 known=set(nodes);c.require(not {t for n in nodes.values() for p in n.pins.values() for t,_ in p.links if t not in known},"external");c.require(not any("K2Node_Knot" in n.node_class for n in nodes.values()),"reroute")
 rng=random.Random(0xEDD5507)
 for index in range(44):
  count=6 if index==0 else rng.randint(2,30);step=.25 if index==0 else rng.choice((.25,.5));state=make_state(count,step,1.1) if index==0 else make_state(count,step);source_snapshot={source:copy.deepcopy(state[source]) for source,_target,_field in ARRAYS};result=Interpreter(nodes,state,desired,gimbal).run();c.require(result[VALID] is True and result["AirframeDesiredStreamCompileValidV1"] and result["AirframePrebakeCompileValidV1"],f"valid {index}")
  for source,target,_field in ARRAYS:c.require(result[target]==state[source] and result[source]==source_snapshot[source],f"copy/immutability {index}:{source}")
  c.require(result["AirframeDesiredStreamInputTotalSecondsV1"]==state[TOTAL] and result["AirframeDesiredStreamInputFixedStepSecondsV1"]==state[STEP],f"schedule {index}")
 base=make_state();downstream={target:base[target] for _source,target,_field in ARRAYS};downstream.update({"AirframeDesiredStreamInputTotalSecondsV1":base["AirframeDesiredStreamInputTotalSecondsV1"],"AirframeDesiredStreamInputFixedStepSecondsV1":base["AirframeDesiredStreamInputFixedStepSecondsV1"]})
 invalid=[]
 d=make_state();d[STAGE]=False;invalid.append(d);d=make_state();d[COUNT]=4;invalid.append(d)
 for source,_target,_field in ARRAYS:
  d=make_state();d[source]=d[source][:-1];invalid.append(d)
 d=make_state(2);d[COUNT]=1;invalid.append(d)
 for i,d in enumerate(invalid):
  machine=Interpreter(nodes,d,desired,gimbal);result=machine.run();c.require(result[VALID] is False and not machine.calls,f"preflight validity {i}")
  for key,value in downstream.items():c.require(result[key] is d[key],f"preflight downstream identity {i}:{key}")
 for label,desired_fail,prebake_fail in (("desired",True,False),("prebake",False,True)):
  result=Interpreter(nodes,make_state(),desired,gimbal,desired_fail,prebake_fail).run();c.require(result[VALID] is False,f"{label} rejection")
 print(f"Airframe source commit contracts passed ({'paste' if x.paste else 'full'}): 44 oracle-valid handoffs, {len(invalid)} preflight failures, desired/prebake failures")
if __name__=="__main__":main()
