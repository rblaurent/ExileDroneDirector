"""Structural and semantic contracts for packed camera-channel validation."""
from __future__ import annotations
import argparse,importlib.util,math,random,re,sys
from pathlib import Path

CHANNELS=("focal_length_mm","aperture_fstop","focus_distance_cm","focus_influence","exposure_ev","bloom_weight","vignette_weight","color_grading_weight","tint_weight","motion_blur_weight","chromatic_aberration_weight","sharpening_weight","matte_weight")
ARRAYS=("CameraChannelInputChannelIdsV1","CameraChannelInputKeyOffsetsV1","CameraChannelInputKeyCountsV1","CameraChannelInputKeyTimesV1","CameraChannelInputKeyValuesV1","CameraChannelInputInterpolationModesV1","CameraChannelInputArriveTangentsV1","CameraChannelInputLeaveTangentsV1","CameraChannelInputDomainsV1")
def load(path):s=importlib.util.spec_from_file_location("edd_camera_channel_validation_contract_base",path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def valid(state):
 ids=state["ids"];offsets=state["offsets"];counts=state["counts"];times=state["times"];values=state["values"];modes=state["modes"];arrives=state["arrives"];leaves=state["leaves"];domains=state["domains"]
 numbers=(state["duration"],state["width"],state["height"])
 if not all(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(float(value)) for value in numbers):return False
 if state["duration"]<0 or not isinstance(state["preset"],str) or state["preset"]=="" or state["width"]<=0 or state["height"]<=0:return False
 n=len(ids)
 if not 0<=n<=13 or len(offsets)!=n or len(counts)!=n or len(domains)!=n:return False
 if len(times)!=len(values) or len(times)!=len(arrives) or len(times)!=len(leaves):return False
 expected=0
 for index,(channel_id,offset,count,domain) in enumerate(zip(ids,offsets,counts,domains)):
  if channel_id not in CHANNELS or ids.index(channel_id)!=index:return False
  if isinstance(offset,bool) or not isinstance(offset,int) or offset!=expected:return False
  if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=512:return False
  if domain not in (("linear","reciprocal") if channel_id=="focus_distance_cm" else ("linear",)):return False
  expected+=count
 return expected==len(times) and len(modes)==expected-n
def packed(rng,ids,duration=4.0):
 offsets=[];counts=[];times=[];values=[];modes=[];arrives=[];leaves=[];domains=[];offset=0
 for channel_id in ids:
  count=rng.randint(1,5);offsets.append(offset);counts.append(count);domains.append(rng.choice(("linear","reciprocal")) if channel_id=="focus_distance_cm" else "linear")
  if count==1:local_times=[0.0];
  else:local_times=[duration*i/(count-1) for i in range(count)]
  times.extend(local_times);values.extend(rng.uniform(1.0,10.0) for _ in range(count));arrives.extend(0.0 for _ in range(count));leaves.extend(0.0 for _ in range(count));modes.extend("linear" for _ in range(count-1));offset+=count
 return dict(ids=list(ids),offsets=offsets,counts=counts,times=times,values=values,modes=modes,arrives=arrives,leaves=leaves,domains=domains,duration=duration,preset="full_frame_36x24",width=36.0,height=24.0)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(125 if x.paste else 126),f"node count {len(nodes)}")
 entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");loops=[n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class];c.require(len(loops)==1,"one bounded channel loop");finds=[n for n in nodes.values() if member(n)=="Array_Find"];c.require(len(finds)==1,"one uniqueness lookup");setters={member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class};c.require(setters=={"CameraChannelScratchValidV1","CameraChannelScratchKeyIndexV1","CameraChannelScratchChannelIndexV1","CameraChannelFailureCodeV1"},"validation setter ownership")
 text=x.graph.read_text(encoding="utf-8");c.require(all(name in text for name in ARRAYS),"all packed arrays read");c.require(all(channel_id in text for channel_id in CHANNELS),"canonical channel allowlist");c.require("CameraChannelCompiled" not in text and "CameraChannelCandidate" not in text,"no candidate/compiled mutation");c.require("CameraTransform" not in text,"no legacy camera alias")
 rng=random.Random(0xEDD610);cases=[packed(rng,())]
 for _ in range(80):
  selected=rng.sample(CHANNELS,rng.randint(0,len(CHANNELS)));cases.append(packed(rng,selected,0.0 if not selected and rng.random()<0.5 else 4.0))
 c.require(all(valid(case) for case in cases),"seeded valid banks")
 base=packed(random.Random(7),("focal_length_mm","focus_distance_cm","bloom_weight"));broken=[]
 def clone():return {key:(list(value) if isinstance(value,list) else value) for key,value in base.items()}
 for mutate in (
  lambda s:s.update(duration=-1.0),lambda s:s.update(duration=math.nan),lambda s:s.update(preset=""),lambda s:s.update(width=0.0),lambda s:s.update(height=math.inf),lambda s:s["ids"].append("unknown"),lambda s:s["ids"].__setitem__(1,s["ids"][0]),lambda s:s["offsets"].__setitem__(1,999),lambda s:s["counts"].__setitem__(0,0),lambda s:s["counts"].__setitem__(0,513),lambda s:s["domains"].__setitem__(0,"reciprocal"),lambda s:s["domains"].__setitem__(1,"bad"),lambda s:s["values"].pop(),lambda s:s["modes"].pop(),lambda s:s["arrives"].pop(),lambda s:s["leaves"].pop(),lambda s:s["domains"].pop(),
 ):
  state=clone();mutate(state);broken.append(state)
 c.require(all(not valid(state) for state in broken),"failure families")
 print(f"Camera channel validation contracts passed ({'paste' if x.paste else 'full'}): {len(cases)} valid and {len(broken)} failure cases")
if __name__=="__main__":main()

