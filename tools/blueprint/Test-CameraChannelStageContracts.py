"""Ownership and semantic contracts for compiled camera-channel staging."""
from __future__ import annotations
import argparse,copy,importlib.util,random,re,sys
from pathlib import Path
def load(path,name):s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_channel_stage_graph_base");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(118 if x.paste else 119),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");text=x.graph.read_text(encoding="utf-8");c.require('MemberName="CompileCameraScalarTrackV1"' not in text,"staging never recompiles");c.require("CameraChannelInputKey" not in text,"staging never reads authored keys");c.require('VariableReference=(MemberName="CameraChannelCompiled' in text and 'K2Node_VariableSet.*CameraChannelCompiled' not in text,"compiled bank read only");c.require(text.count('MemberName="Array_Clear"')==5,"five generic candidate resets");c.require(len([n for n in nodes.values() if "K2Node_MacroInstance" in n.node_class])==1,"one bounded slice loop")
 setters={member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class};expected={"CameraChannelScratchValidV1","CameraScalarTrackCompileValidV1","CameraScalarTrackInputDurationV1","CameraScalarTrackInputDomainV1","CameraScalarTrackInputHasMinimumV1","CameraScalarTrackInputMinimumV1","CameraScalarTrackInputHasMaximumV1","CameraScalarTrackInputMaximumV1","CameraScalarTrackInputClampOutputV1"};c.require(setters==expected,"staging setter ownership")
 sys.path.insert(0,str(x.project_root/"tools/trajectory"));scalar=load(x.project_root/"tools/trajectory/camera_scalar_track_reference.py","camera_scalar_track_reference");ref=load(x.project_root/"tools/trajectory/camera_channel_assembly_reference.py","edd_camera_channel_stage_reference");policies={item.channel_id:item for item in ref.CHANNEL_POLICIES_V1}
 def flatten(assembly):
  bank=dict(offsets=[],counts=[],times=[],values=[],modes=[],arrives=[],leaves=[],domains=[],duration=assembly.duration_seconds,valid=True)
  for channel in assembly.channels:bank["offsets"].append(len(bank["times"]));bank["counts"].append(len(channel.track.key_times));bank["times"].extend(channel.track.key_times);bank["values"].extend(channel.track.domain_values);bank["modes"].extend(channel.track.interpolation_modes);bank["arrives"].extend(channel.track.arrive_tangents);bank["leaves"].extend(channel.track.leave_tangents);bank["domains"].append(channel.track.domain)
  return bank
 def stage(bank,index):
  if not bank.get("valid") or not isinstance(index,int) or isinstance(index,bool) or not 0<=index<13:return None
  if not all(len(bank[name])==13 for name in ("offsets","counts","domains")):return None
  offset,count,domain=bank["offsets"][index],bank["counts"][index],bank["domains"][index];mode_start=offset-index
  if not isinstance(offset,int) or not isinstance(count,int) or offset<0 or not 1<=count<=512 or mode_start<0:return None
  if domain not in (("linear","reciprocal") if index==2 else ("linear",)):return None
  if any(offset+count>len(bank[name]) for name in ("times","values","arrives","leaves")) or mode_start+count-1>len(bank["modes"]):return None
  policy=policies[ref.CHANNEL_IDS_V1[index]]
  return scalar.CompiledCameraScalarTrack(tuple(bank["times"][offset:offset+count]),tuple(bank["values"][offset:offset+count]),tuple(bank["modes"][mode_start:mode_start+count-1]),tuple(bank["arrives"][offset:offset+count]),tuple(bank["leaves"][offset:offset+count]),bank["duration"],domain,policy.minimum is not None,0.0 if policy.minimum is None else policy.minimum,policy.maximum is not None,0.0 if policy.maximum is None else policy.maximum,policy.clamp_output)
 rng=random.Random(0xEDD630)
 for case_index in range(40):
  duration=rng.choice((0.0,2.0,4.0));authored=[]
  for channel_id in rng.sample(ref.CHANNEL_IDS_V1,rng.randint(0,13)):
   policy=policies[channel_id]
   if duration==0:keys=(scalar.CameraScalarKey(0.0,policy.default_value),)
   else:keys=(scalar.CameraScalarKey(0.0,policy.default_value,"linear"),scalar.CameraScalarKey(duration,policy.default_value))
   authored.append(ref.AuthoredCameraChannelV1(channel_id,keys,rng.choice(policy.permitted_domains)))
  assembly=ref.compile_camera_channel_assembly_v1(duration,ref.FilmbackSnapshotV1("test",36.0,24.0),authored);bank=flatten(assembly)
  for index,channel in enumerate(assembly.channels):
   staged=stage(bank,index);c.require(staged is not None,f"staged channel {case_index}/{index}")
   for query in (-1.0,0.0,duration/2.0,duration,duration+1.0):c.require(scalar.evaluate_camera_scalar_track(staged,query)==scalar.evaluate_camera_scalar_track(channel.track,query),"staged evaluation equivalence")
 base=flatten(ref.compile_camera_channel_assembly_v1(2.0,ref.FilmbackSnapshotV1("test",36.0,24.0),()))
 poisoned=[]
 for mutate in (lambda b:b.update(valid=False),lambda b:b["offsets"].pop(),lambda b:b["counts"].pop(),lambda b:b["domains"].pop(),lambda b:b["offsets"].__setitem__(3,-1),lambda b:b["counts"].__setitem__(3,0),lambda b:b["counts"].__setitem__(3,513),lambda b:b["times"].pop(),lambda b:b["values"].pop(),lambda b:b["modes"].pop(),lambda b:b["arrives"].pop(),lambda b:b["leaves"].pop(),lambda b:b["domains"].__setitem__(0,"reciprocal"),lambda b:b["domains"].__setitem__(2,"bad")):
  bank=copy.deepcopy(base);mutate(bank);poisoned.append(bank)
 poison_indices=(3,3,3,3,3,3,3,12,12,12,12,12,0,2);c.require(all(stage(bank,index) is None for bank,index in zip(poisoned,poison_indices)),"poisoned slice failures");c.require(stage(base,-1) is None and stage(base,13) is None,"index failures")
 print(f"Camera channel staging contracts passed ({'paste' if x.paste else 'full'}): 520 channels, 5 queries each, {len(poisoned)+2} failures")
if __name__=="__main__":main()
