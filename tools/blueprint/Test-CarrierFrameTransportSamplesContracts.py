"""Structural and executable contracts for twist-minimizing carrier samples."""
from __future__ import annotations
import argparse, importlib.util, math, random, re, sys
from pathlib import Path

READS={"CarrierFrameCandidateTangentsV1","CarrierFrameCandidateQuatsV1","CarrierFrameScratchValidV1","CarrierFrameScratchIndexV1","CarrierFrameScratchForwardV1","CarrierFrameScratchRightV1","CarrierFrameScratchUpV1","CarrierFrameScratchQuatV1"}
WRITES={"CarrierFrameScratchIndexV1","CarrierFrameScratchForwardV1","CarrierFrameScratchRightV1","CarrierFrameScratchUpV1","CarrierFrameScratchQuatV1","CarrierFrameScratchValidV1","CarrierFrameFailureCodeV1"}
FORBIDDEN=("AirframeDesired","AuthoredBody","AuthoredGimbal","CameraTransform","CarrierFrameInputPositions","CarrierFrameCompiled","CarrierFrameResult","CameraOperator","PlaybackTime","Event","Repository","Server","Frenet")
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def member(node):
 m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def default(node,p):
 m=re.search(r'(?:^|,)DefaultValue="([^"]*)"',node.pins[p].body);return "" if m is None else m.group(1)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def length(v):return math.sqrt(dot(v,v))
def rotate(q,v):
 x,y,z,w=q
 def mul(a,b):
  ax,ay,az,aw=a;bx,by,bz,bw=b;return (aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz)
 return mul(mul(q,(v[0],v[1],v[2],0.0)),(-x,-y,-z,w))[:3]
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_carrier_transport_contract_base");nodes=c.parse_graph(a.graph)
 c.require(len(nodes)==(127 if a.paste else 128),f"transport node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"transport entry count")
 getters=[n for n in nodes.values() if "K2Node_VariableGet" in n.node_class];setters=[n for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require({member(n) for n in getters}==READS,"exact transport reads");c.require({member(n) for n in setters}==WRITES,"exact transport writes")
 c.require(sum("K2Node_MacroInstance" in n.node_class for n in nodes.values())==1,"single ordered sample loop");c.require(sum("K2Node_GetArrayItem" in n.node_class for n in nodes.values())==2,"current tangent and prior quaternion reads");c.require(sum("K2Node_IfThenElse" in n.node_class for n in nodes.values())==9,"exact transport phase guards")
 names=[member(n) for n in nodes.values()]
 for name,count in {"Array_Clear":1,"Array_Length":2,"Array_Add":1,"MakeRotFromXZ":2,"Conv_RotatorToQuaternion":2,"Quat_Normalized":3,"Quat_SetComponents":3,"BreakQuat":2,"Quat_RotateVector":1,"Cross_VectorVector":6,"Dot_VectorVector":5,"VSize":7}.items():c.require(names.count(name)==count,f"{name} count {names.count(name)}")
 text=a.graph.read_text(encoding="utf-8");c.require(not any(v in text for v in FORBIDDEN),"authored/external/Frenet ownership forbidden")
 for token in ('DefaultValue="0.999999"','DefaultValue="-0.999999999"','DefaultValue="0.999999999"','DefaultValue="1e-9"','DefaultValue="transport_build_failed"'):c.require(token in text,f"frozen transport token missing:{token}")
 clear=next(n for n in nodes.values() if member(n)=="Array_Clear");candidate=next(n for n in getters if member(n)=="CarrierFrameCandidateQuatsV1");c.require_link(candidate,"CarrierFrameCandidateQuatsV1",clear,"TargetArray","candidate quaternion clear")
 if a.paste:c.require(not clear.pins["execute"].links,"paste root")
 else:c.require_link(entries[0],"then",clear,"execute","entry clears only owned quaternion candidates")
 append=next(n for n in nodes.values() if member(n)=="Array_Add");scratch=next(n for n in getters if member(n)=="CarrierFrameScratchQuatV1" and any(t==append.name for pin in n.pins.values() for t,_ in pin.links));c.require_link(scratch,"CarrierFrameScratchQuatV1",append,"NewItem","single frozen quaternion append")
 publishes=[n for n in setters if member(n)=="CarrierFrameScratchValidV1" and default(n,"CarrierFrameScratchValidV1")=="true"];c.require(len(publishes)==1 and not publishes[0].pins["then"].links,"transport validity publishes terminally")

 ref=load(a.project_root/"tools/trajectory/carrier_frame_transport_reference.py","edd_carrier_transport_reference_contract")
 cases=[((0.,0.,0.),(1.,0.,0.),(2.,0.,0.)),((0.,0.,0.),(0.,0.,1.),(0.,0.,2.)),((0.,0.,0.),(1.,0.,0.),(1.,0.,0.),(1.,0.,0.),(0.,0.,0.)),tuple((math.cos(i*math.pi/8),math.sin(i*math.pi/8),0.) for i in range(5))]
 rng=random.Random(0x7A4A5A0);generated=[]
 for _ in range(100):
  points=[(0.,0.,0.)]
  for i in range(1,rng.randint(2,80)):
   if i%13==0:points.append(points[-1])
   else:points.append(tuple(x+rng.uniform(-4,4) for x in points[-1]))
  generated.append(tuple(points))
 cases.extend(generated);results=[]
 for index,positions in enumerate(cases):
  step=0.125;total=(len(positions)-1)*step;track=ref.compile_carrier_frame_transport_v1(positions,total,step);results.append(track.rotations)
  c.require(len(track.rotations)==len(track.tangents)==len(positions),f"cardinality {index}")
  for sample,(tangent,q) in enumerate(zip(track.tangents,track.rotations)):
   c.require(abs(length(q)-1.0)<=1e-6,f"unit quaternion {index}:{sample}");c.require(length(tuple(x-y for x,y in zip(rotate(q,(1.,0.,0.)),tangent)))<=1e-6,f"forward alignment {index}:{sample}")
  c.require(all(dot(left,right)>=-1e-9 for left,right in zip(track.rotations,track.rotations[1:])),f"hemisphere {index}")
 c.require(list(reversed([ref.compile_carrier_frame_transport_v1(v,(len(v)-1)*0.125,0.125).rotations for v in reversed(cases)]))==results,"forward/reverse deterministic transport")
 planar=ref.compile_carrier_frame_transport_v1(cases[3],0.5,0.125);c.require(all(rotate(q,(0.,0.,1.))[2]>0.999999 for q in planar.rotations),"planar world-up stability")
 vertical=ref.compile_carrier_frame_transport_v1(cases[1],0.25,0.125);c.require(vertical.rotations==ref.compile_carrier_frame_transport_v1(cases[1],0.25,0.125).rotations,"vertical fallback determinism")
 print(f"Carrier-frame transport sample contracts passed ({'paste' if a.paste else 'full'}): {len(cases)} forward/reverse paths")
if __name__=="__main__":main()
