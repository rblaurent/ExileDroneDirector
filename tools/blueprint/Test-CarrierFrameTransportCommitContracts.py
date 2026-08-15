"""Structural and executable contracts for atomic carrier-frame commit."""
from __future__ import annotations
import argparse,importlib.util,math,random,re,sys
from pathlib import Path
READS={"CarrierFrameCandidateTangentsV1","CarrierFrameCandidateQuatsV1","CarrierFrameInputPositionsV1","CarrierFrameScratchValidV1","CarrierFrameInputTotalSecondsV1","CarrierFrameInputFixedStepSecondsV1"}
WRITES={"CarrierFrameCompileValidV1","CarrierFrameScratchValidV1","CarrierFrameFailureCodeV1","CarrierFrameCompiledTangentsV1","CarrierFrameCompiledQuatsV1","CarrierFrameCompiledTotalSecondsV1","CarrierFrameCompiledFixedStepSecondsV1"}
FORBIDDEN=("AirframeDesired","AuthoredBody","AuthoredGimbal","CameraTransform","CarrierFrameResult","CameraOperator","PlaybackTime","Event","Repository","Server")
def load(path,name):s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def member(n):m=re.search(r'MemberName="([^"]+)"',n.text);return None if m is None else m.group(1)
def default(n,p):m=re.search(r'(?:^|,)DefaultValue="([^"]*)"',n.pins[p].body);return "" if m is None else m.group(1)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def length(v):return math.sqrt(dot(v,v))
def rotate(q,v):
 x,y,z,w=q
 def mul(a,b):
  ax,ay,az,aw=a;bx,by,bz,bw=b;return (aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz)
 return mul(mul(q,(v[0],v[1],v[2],0.0)),(-x,-y,-z,w))[:3]
def commit(state,prior):
 result=dict(prior);result["valid"]=False;t=state["tangents"];q=state["quats"];count=len(t)
 if not state["stage"] or not 2<=count<=65536 or len(q)!=count or len(state["positions"])!=count:return result,"candidate_invalid"
 for i,(tv,qv) in enumerate(zip(t,q)):
  if not all(math.isfinite(x) for x in (*tv,*qv)) or not 0.999999<=length(tv)<=1.000001 or not 0.999999<=length(qv)<=1.000001:return result,"candidate_invalid"
  if length(tuple(x-y for x,y in zip(rotate(qv,(1.,0.,0.)),tv)))>0.000001:return result,"candidate_invalid"
  if i and dot(q[i-1],qv)<-0.000001:return result,"candidate_invalid"
 result.update(tangents=list(t),quats=list(q),total=state["total"],step=state["step"],valid=True);return result,""
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_carrier_commit_contract_base");nodes=c.parse_graph(a.graph);c.require(len(nodes)==(66 if a.paste else 67),f"commit node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"commit entry count");getters=[n for n in nodes.values() if "K2Node_VariableGet" in n.node_class];setters=[n for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require({member(n) for n in getters}==READS,"exact commit reads");c.require({member(n) for n in setters}==WRITES,"exact commit writes");c.require(sum("K2Node_MacroInstance" in n.node_class for n in nodes.values())==1,"one validation loop");c.require(sum("K2Node_GetArrayItem" in n.node_class for n in nodes.values())==2,"current/prior quaternion items");c.require(sum("K2Node_IfThenElse" in n.node_class for n in nodes.values())==5,"five commit guards")
 names=[member(n) for n in nodes.values()]
 for name,count in {"Array_Length":3,"Quat_IsFinite":1,"Quat_Size":1,"Quat_GetAxisX":1,"Subtract_VectorVector":1,"VSize":2,"BreakQuat":2}.items():c.require(names.count(name)==count,f"{name} count")
 text=a.graph.read_text(encoding="utf-8");c.require(not any(v in text for v in FORBIDDEN),"authored/external ownership forbidden")
 for token in ('DefaultValue="0.999999"','DefaultValue="1.000001"','DefaultValue="0.000001"','DefaultValue="-0.000001"','DefaultValue="candidate_invalid"'):c.require(token in text,f"frozen commit token:{token}")
 invalidators=[n for n in setters if member(n)=="CarrierFrameCompileValidV1" and default(n,"CarrierFrameCompileValidV1")=="false"];publishers=[n for n in setters if member(n)=="CarrierFrameCompileValidV1" and default(n,"CarrierFrameCompileValidV1")=="true"];c.require(len(invalidators)==len(publishers)==1,"validity invalidates/publishes once")
 if a.paste:c.require(not invalidators[0].pins["execute"].links,"paste root")
 else:c.require_link(entries[0],"then",invalidators[0],"execute","entry invalidates first")
 c.require(not publishers[0].pins["then"].links,"compiled validity publishes terminally")
 compiled={member(n):n for n in setters if member(n).startswith("CarrierFrameCompiled")};c.require(set(compiled)=={"CarrierFrameCompiledTangentsV1","CarrierFrameCompiledQuatsV1","CarrierFrameCompiledTotalSecondsV1","CarrierFrameCompiledFixedStepSecondsV1"},"whole compiled snapshot ownership")
 ref=load(a.project_root/"tools/trajectory/carrier_frame_transport_reference.py","edd_carrier_commit_reference");rng=random.Random(0xC011117);cases=[]
 for _ in range(100):
  points=[(0.,0.,0.)]
  for i in range(1,rng.randint(2,60)):points.append(points[-1] if i%17==0 else tuple(x+rng.uniform(-4,4) for x in points[-1]))
  positions=tuple(points);track=ref.compile_carrier_frame_transport_v1(positions,(len(positions)-1)*0.125,0.125);cases.append((positions,track))
 for i,(positions,track) in enumerate(cases):
  state={"positions":positions,"tangents":track.tangents,"quats":track.rotations,"total":track.total_seconds,"step":track.fixed_step_seconds,"stage":True};prior={"tangents":object(),"quats":object(),"total":object(),"step":object(),"valid":True};result,failure=commit(state,prior);c.require(result["valid"] and failure=="",f"valid {i}");c.require(result["tangents"]==list(track.tangents) and result["quats"]==list(track.rotations),f"snapshot {i}");c.require(state["positions"] is positions,f"immutable {i}")
 positions,track=cases[0];base={"positions":positions,"tangents":track.tangents,"quats":track.rotations,"total":track.total_seconds,"step":track.fixed_step_seconds,"stage":True};poisons=({**base,"stage":False},{**base,"tangents":track.tangents[:-1]},{**base,"quats":track.rotations[:-1]},{**base,"positions":positions[:-1]},{**base,"tangents":((2.,0.,0.),)+track.tangents[1:]},{**base,"quats":((0.,0.,0.,2.),)+track.rotations[1:]},{**base,"quats":((0.,0.,0.,1.),(0.,0.,1.,0.))+track.rotations[2:]})
 for i,state in enumerate(poisons):
  prior={"tangents":object(),"quats":object(),"total":object(),"step":object(),"valid":True};result,failure=commit(state,prior);c.require(not result["valid"] and failure=="candidate_invalid",f"poison {i}");c.require(all(result[k] is prior[k] for k in ("tangents","quats","total","step")),f"prior snapshot preserved {i}")
 print(f"Carrier-frame commit contracts passed ({'paste' if a.paste else 'full'}): 100 snapshots, {len(poisons)} failures")
if __name__=="__main__":main()
