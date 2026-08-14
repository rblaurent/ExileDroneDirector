"""Exact ownership and semantic contracts for one camera-channel candidate."""
from __future__ import annotations
import argparse,copy,importlib.util,random,re,sys
from pathlib import Path

def load(path,name):s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_channel_candidate_graph_base");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(185 if x.paste else 186),f"node count {len(nodes)}")
 entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");text=x.graph.read_text(encoding="utf-8");c.require(text.count('MemberName="CompileCameraScalarTrackV1"')==3,"three mutually exclusive scalar compile paths");c.require(text.count('MemberName="Array_Clear"')==5,"five generic input clears");c.require(text.count('MemberName="Array_Find"')==1,"one authored channel lookup");c.require("CameraChannelCompiled" not in text,"candidate helper cannot mutate compiled bank");c.require("CameraTransform" not in text,"no legacy camera alias")
 setter_names={member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class};allowed={"CameraScalarTrackInputDurationV1","CameraScalarTrackInputHasMinimumV1","CameraScalarTrackInputMinimumV1","CameraScalarTrackInputHasMaximumV1","CameraScalarTrackInputMaximumV1","CameraScalarTrackInputClampOutputV1","CameraScalarTrackInputDomainV1","CameraChannelScratchValidV1","CameraChannelFailureCodeV1"};c.require(setter_names==allowed,"setter ownership")
 for target in ("CameraChannelCandidateKeyOffsetsV1","CameraChannelCandidateKeyCountsV1","CameraChannelCandidateKeyTimesV1","CameraChannelCandidateDomainValuesV1","CameraChannelCandidateInterpolationModesV1","CameraChannelCandidateArriveTangentsV1","CameraChannelCandidateLeaveTangentsV1","CameraChannelCandidateDomainsV1"):c.require(target in text,f"candidate publication {target}")
 sys.path.insert(0,str(x.project_root/"tools/trajectory"));ref=load(x.project_root/"tools/trajectory/camera_channel_assembly_reference.py","edd_camera_channel_candidate_reference");scalar=load(x.project_root/"tools/trajectory/camera_scalar_track_reference.py","camera_scalar_track_reference")
 policies={item.channel_id:item for item in ref.CHANNEL_POLICIES_V1}
 def pack(authored,duration):
  ids=[];offsets=[];counts=[];times=[];values=[];modes=[];arrives=[];leaves=[];domains=[]
  for channel in authored:
   ids.append(channel.channel_id);offsets.append(len(times));counts.append(len(channel.keys));domains.append(channel.domain);times.extend(key.time_seconds for key in channel.keys);values.extend(key.value for key in channel.keys);modes.extend(key.interpolation_out for key in channel.keys[:-1]);arrives.extend(key.arrive_tangent for key in channel.keys);leaves.extend(key.leave_tangent for key in channel.keys)
  return dict(ids=ids,offsets=offsets,counts=counts,times=times,values=values,modes=modes,arrives=arrives,leaves=leaves,domains=domains,duration=duration)
 def empty():return dict(offsets=[],counts=[],times=[],domain_values=[],modes=[],arrives=[],leaves=[],domains=[])
 def simulate(state,index,bank):
  channel_id=ref.CHANNEL_IDS_V1[index];policy=policies[channel_id]
  if channel_id in state["ids"]:
   authored_index=state["ids"].index(channel_id);offset=state["offsets"][authored_index];count=state["counts"][authored_index];mode_offset=offset-authored_index;keys=tuple(scalar.CameraScalarKey(state["times"][offset+i],state["values"][offset+i],state["modes"][mode_offset+i] if i<count-1 else "linear",state["arrives"][offset+i],state["leaves"][offset+i]) for i in range(count));domain=state["domains"][authored_index]
  else:
   keys=ref._constant_keys(policy.default_value,state["duration"]);domain="linear"
  try:track=scalar.compile_camera_scalar_track(keys,state["duration"],domain=domain,minimum=policy.minimum,maximum=policy.maximum,clamp_output=policy.clamp_output)
  except scalar.CameraScalarTrackError:return False
  bank["offsets"].append(len(bank["times"]));bank["counts"].append(len(track.key_times));bank["times"].extend(track.key_times);bank["domain_values"].extend(track.domain_values);bank["modes"].extend(track.interpolation_modes);bank["arrives"].extend(track.arrive_tangents);bank["leaves"].extend(track.leave_tangents);bank["domains"].append(track.domain);return True
 rng=random.Random(0xEDD620)
 for case_index in range(40):
  duration=rng.choice((0.0,2.0,4.0));selected=rng.sample(ref.CHANNEL_IDS_V1,rng.randint(0,13));authored=[]
  for channel_id in selected:
   policy=policies[channel_id];left=policy.default_value;right=left
   if duration>0:
    low=policy.minimum if policy.minimum is not None else -1.0;high=policy.maximum if policy.maximum is not None else 1.0;left=rng.uniform(low,high);right=rng.uniform(low,high);keys=(scalar.CameraScalarKey(0.0,left,"linear"),scalar.CameraScalarKey(duration,right))
   else:keys=(scalar.CameraScalarKey(0.0,left),)
   domain=rng.choice(policy.permitted_domains);authored.append(ref.AuthoredCameraChannelV1(channel_id,keys,domain))
  state=pack(authored,duration);bank=empty();c.require(all(simulate(state,index,bank) for index in range(13)),f"seeded compile {case_index}");oracle=ref.compile_camera_channel_assembly_v1(duration,ref.FilmbackSnapshotV1("test",36.0,24.0),authored);c.require(bank["offsets"]==[sum(len(item.track.key_times) for item in oracle.channels[:i]) for i in range(13)],"disjoint offsets");c.require(bank["counts"]==[len(item.track.key_times) for item in oracle.channels],"owned counts");c.require(tuple(bank["domains"])==tuple(item.track.domain for item in oracle.channels),"domain order");c.require(tuple(bank["domain_values"])==tuple(value for item in oracle.channels for value in item.track.domain_values),"compiled values")
 bad=pack((ref.AuthoredCameraChannelV1("bloom_weight",(scalar.CameraScalarKey(0.0,-1.0),),"linear"),),0.0);bank=empty();before=copy.deepcopy(bank);c.require(not simulate(bad,5,bank),"invalid authored candidate rejects");c.require(bank==before,"failed candidate preserves prior bank")
 print(f"Camera channel candidate contracts passed ({'paste' if x.paste else 'full'}): 40 complete banks, sparse defaults, atomic failure")
if __name__=="__main__":main()

